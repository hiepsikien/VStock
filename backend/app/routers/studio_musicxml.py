"""MusicXML upload + passage preview for the Texture Studio.

Prefix: ``/v1/studio/import``. This is the API seam between a score file and
the existing offline ``TextureSpec`` validator plus the code-only preview
synth. It does not publish, register a pattern, call Gemini, or touch the
database:

* ``POST /musicxml``                      — multipart upload, parsed once
* ``GET  /musicxml/{importId}``           — the stored summary/notes/warnings
* ``POST /musicxml/{importId}/passage``   — one tick range → spec + synth notes
* ``GET  /musicxml/passages/{passageId}`` — the passage built by the POST

Bars are **1-based and inclusive** in requests, matching the measure numbers a
musician reads in the score. Parser notes are 0-based internally; the response
spec/notes are rebased so the selection start is bar 0 of the passage.

``beatStart``/``beatEnd`` are optional quarter-note offsets inside
``barStart``/``barEnd``. They select the absolute range
``[start_of(barStart) + beatStart, start_of(barEnd) + beatEnd)``; omitting
``beatEnd`` keeps the whole of ``barEnd``, so a bar-only request is unchanged.
Notes are clipped to the range and rebased to its start.

Storage is process-local and bounded: uploads are written under
``VSTOCK_STUDIO_DIR/imports`` (or ``backend/var/studio/imports``), parsed
scores and passage payloads live in small TTL/LRU dicts. A restart drops them;
the client re-uploads. No JSON response is larger than the parsed notes of one
score, and the upload is capped at 5 MB by default.

Audio reuses ``app.studio.audio.ensure_audio`` and the already-registered
``/v1/studio/sentence/audio/{key}.wav`` route. The passage is rendered at the
synth's fixed 96 BPM; ``6/8`` counts three quarter-note beats per bar, exactly
as ``app.studio.audio._METER_BEATS`` does. A passage that the synth rejects
(too long, unsupported meter, no notes) keeps its spec and notes and reports an
``audio`` error; only the URL is missing.

Meters are per measure. The parser records one meter per bar (a bar without a
``<time>`` inherits the previous one), and a passage may only select a range
with a single constant meter: ``1/4``, ``2/4``, ``3/4``, ``4/4``, or ``6/8``.
A mixed-meter range is rejected with a ``meter`` error instead of stretching a
bar to a foreign bar length.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StrictInt

from app.sonify.form import (
    METER_14,
    METER_24,
    METER_34,
    METER_44,
    METER_68,
    Meter,
)
from app.studio import audio as studio_audio
from app.studio import musicxml_sentence
from app.studio import musicxml_source
from app.studio import session as studio_session
from app.studio.store import studio_root
from app.studio.texture_spec import (
    AuthoredEvent,
    MeterSpec,
    MeterVariant,
    PitchRef,
    TextureSpec,
    check_texture_spec,
    texture_spec_to_mapping,
)

router = APIRouter(prefix="/v1/studio/import", tags=["studio-musicxml"])

_CHUNK = 1024 * 1024
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_DEFAULT_MAX_NOTES = 20000
_DEFAULT_IMPORT_TTL = 24 * 60 * 60
_DEFAULT_PASSAGE_TTL = 2 * 60 * 60
_DEFAULT_IMPORTS_MAX = 32
_DEFAULT_PASSAGES_MAX = 128
_EXTENSIONS = frozenset({".musicxml", ".xml"})
_IMPORT_ID_PREFIX = "mxi_"
_PASSAGE_ID_PREFIX = "mxp_"
_MAX_AUTHORED_VOICES = 4
_DEFAULT_DRAFTS_PER_DAY = 50
_DEFAULT_GLOBAL_DRAFTS_PER_DAY = 200
_GLOBAL_DRAFT_OWNER = "__global__"

# MusicXML meter → runtime form meter. ``6/8`` is three quarter-note beats,
# matching ``app.studio.audio._METER_BEATS``.
_SUPPORTED_METERS: dict[str, tuple[Meter, int]] = {
    "1/4": (METER_14, 1),
    "2/4": (METER_24, 2),
    "3/4": (METER_34, 3),
    "4/4": (METER_44, 4),
    "6/8": (METER_68, 3),
}

_PARSER_ERRORS = (
    ValueError,
    TypeError,
    KeyError,
    IndexError,
    OverflowError,
    ET.ParseError,
)


# ---------------------------------------------------------------------------
# Request/response models


class ErrorOut(BaseModel):
    path: str
    message: str


class MeterChange(BaseModel):
    """One printed meter change; ``bar`` is 1-based."""

    bar: int
    meter: str


class ImportSummary(BaseModel):
    title: str
    meter: str
    # One meter per printed measure; index 0 is bar 1.
    measureMeters: list[str] = Field(default_factory=list)
    # Changes after bar 1 only (bar 1 is the baseline, not a change).
    meterChanges: list[MeterChange] = Field(default_factory=list)
    measureCount: int
    keyFifths: int
    keyMode: str | None = None
    tempo: float | None = None
    noteCount: int
    voices: list[int] = Field(default_factory=list)
    sourceHash: str
    meterSupported: bool


class ImportResponse(BaseModel):
    ok: bool = True
    importId: str
    filename: str
    summary: ImportSummary
    notes: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PassageRequest(BaseModel):
    # 1-based, inclusive, matching the printed measure numbers.
    barStart: int
    barEnd: int
    # Quarter-note offsets inside barStart/barEnd. ``None`` means the omitted
    # default: 0 for beatStart and the end of barEnd for beatEnd.
    beatStart: float | None = None
    beatEnd: float | None = None
    voices: list[StrictInt] | None = None


class PassageResponse(BaseModel):
    ok: bool
    passageId: str | None = None
    # The selected range's single meter, so the UI can size a bar without
    # re-reading the import summary. Null when the passage was rejected.
    meter: str | None = None
    beatsPerBar: int | None = None
    # The preview synth's fixed tempo, so the UI can map audio.currentTime
    # to quarter-note ticks without duplicating the constant.
    bpm: int = int(round(studio_audio.PREVIEW_BPM))
    spec: dict[str, Any] | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)
    audioUrl: str | None = None
    durationSec: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorOut] = Field(default_factory=list)


class NewPatternRequest(BaseModel):
    """The pattern metadata a ``new`` draft needs.

    ``meter`` is optional: when omitted the passage meter is used. ``renderer``
    is ``villa`` in the MVP; other families stay out of the draft surface.
    """

    id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=120)
    composer: str = Field(min_length=1, max_length=120)
    renderer: str = Field(default="villa", max_length=40)
    meter: str | None = Field(default=None, max_length=16)
    templateId: str | None = Field(default=None, max_length=160)


class SentenceDraftRequest(BaseModel):
    # Whole-bar draft range. Beat offsets are accepted for UI symmetry but the
    # draft uses whole bars and returns a warning when they are partial.
    barStart: int
    beatStart: float = 0.0
    barEnd: int
    beatEnd: float | None = None
    mode: str
    pattern: str | None = Field(default=None, max_length=80)
    templateId: str | None = Field(default=None, max_length=160)
    newPattern: NewPatternRequest | None = None
    voices: list[StrictInt] | None = None


class ErrorResponse(BaseModel):
    ok: bool = False
    errors: list[ErrorOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Configuration


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def max_upload_bytes() -> int:
    return _env_int(
        "VSTOCK_STUDIO_MUSICXML_MAX_BYTES", _DEFAULT_MAX_BYTES, minimum=1
    )


def max_score_notes() -> int:
    return _env_int(
        "VSTOCK_STUDIO_MUSICXML_MAX_NOTES", _DEFAULT_MAX_NOTES, minimum=1
    )


def import_ttl_seconds() -> float:
    return float(
        _env_int("VSTOCK_STUDIO_MUSICXML_TTL_SECONDS", _DEFAULT_IMPORT_TTL)
    )


def passage_ttl_seconds() -> float:
    return float(
        _env_int("VSTOCK_STUDIO_MUSICXML_PASSAGE_TTL_SECONDS", _DEFAULT_PASSAGE_TTL)
    )


def imports_max() -> int:
    return _env_int("VSTOCK_STUDIO_MUSICXML_IMPORTS_MAX", _DEFAULT_IMPORTS_MAX)


def passages_max() -> int:
    return _env_int("VSTOCK_STUDIO_MUSICXML_PASSAGES_MAX", _DEFAULT_PASSAGES_MAX)


def drafts_per_day() -> int:
    """Per-owner daily draft cap, read per request so tests can tune it."""
    return _env_int(
        "VSTOCK_STUDIO_MUSICXML_DRAFTS_PER_DAY",
        _DEFAULT_DRAFTS_PER_DAY,
        minimum=0,
    )


def global_drafts_per_day() -> int:
    """Process-wide daily draft cap (still process-local, not multi-worker)."""
    return _env_int(
        "VSTOCK_STUDIO_MUSICXML_GLOBAL_DRAFTS_PER_DAY",
        _DEFAULT_GLOBAL_DRAFTS_PER_DAY,
        minimum=0,
    )


def imports_root() -> Path:
    path = studio_root() / "imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def import_path(import_id: str) -> Path:
    return imports_root() / f"{import_id}.musicxml"


# ---------------------------------------------------------------------------
# Bounded in-memory stores


@dataclass
class _ImportRecord:
    import_id: str
    owner_id: str
    filename: str
    score: Any
    summary: ImportSummary
    notes: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    created_at: float


@dataclass
class _PassageRecord:
    passage_id: str
    owner_id: str
    import_id: str
    payload: dict[str, Any]
    created_at: float


@dataclass(frozen=True)
class _DraftQuota:
    allowed: bool
    day: str
    used: int
    limit: int
    retry_after_seconds: int
    scope: str = "owner"


_LOCK = threading.RLock()
_IMPORTS: dict[str, _ImportRecord] = {}
_PASSAGES: dict[str, _PassageRecord] = {}

# Process-local draft counters. This is deliberately a small in-memory map:
# draft render is cheap next to upload/analyze, and a restart dropping the count
# is acceptable for the beta. It can be replaced by `app.studio.quota` (SQLite,
# `consume_with_global`) once drafts need to survive a deploy or share workers.
_DRAFT_LOCK = threading.Lock()
_DRAFT_USAGE: dict[tuple[str, str], int] = {}


def _utc_day(now: datetime | None = None) -> str:
    moment = now if now is not None else datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).date().isoformat()


def _seconds_until_utc_midnight(now: datetime | None = None) -> int:
    moment = now if now is not None else datetime.now(timezone.utc)
    moment = moment.astimezone(timezone.utc)
    tomorrow = (moment + timedelta(days=1)).date()
    reset = datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc
    )
    return max(1, int((reset - moment).total_seconds()))


def consume_draft(owner_id: str, *, now: datetime | None = None) -> _DraftQuota:
    """Spend one draft for ``owner_id`` and the process-wide pool."""
    day = _utc_day(now)
    limit = drafts_per_day()
    global_limit = global_drafts_per_day()
    retry_after = _seconds_until_utc_midnight(now)
    with _DRAFT_LOCK:
        # Keep only today's rows; the map is tiny but should not grow forever.
        for key in [key for key in _DRAFT_USAGE if key[1] != day]:
            del _DRAFT_USAGE[key]
        global_key = (_GLOBAL_DRAFT_OWNER, day)
        global_used = _DRAFT_USAGE.get(global_key, 0)
        if global_used >= global_limit:
            return _DraftQuota(
                allowed=False,
                day=day,
                used=global_used,
                limit=global_limit,
                retry_after_seconds=retry_after,
                scope="global",
            )
        key = (owner_id, day)
        used = _DRAFT_USAGE.get(key, 0)
        if used >= limit:
            return _DraftQuota(
                allowed=False,
                day=day,
                used=used,
                limit=limit,
                retry_after_seconds=retry_after,
            )
        used += 1
        _DRAFT_USAGE[key] = used
        _DRAFT_USAGE[global_key] = global_used + 1
    return _DraftQuota(
        allowed=True,
        day=day,
        used=used,
        limit=limit,
        retry_after_seconds=retry_after,
    )


def refund_draft(owner_id: str, day: str) -> None:
    """Return one reserved draft after a failed render."""
    with _DRAFT_LOCK:
        for key in ((owner_id, day), (_GLOBAL_DRAFT_OWNER, day)):
            used = _DRAFT_USAGE.get(key, 0)
            if used <= 0:
                _DRAFT_USAGE.pop(key, None)
            else:
                _DRAFT_USAGE[key] = used - 1


def clear_store() -> None:
    """Drop every in-memory record. Tests use this between cases."""
    with _LOCK:
        _IMPORTS.clear()
        _PASSAGES.clear()
    with _DRAFT_LOCK:
        _DRAFT_USAGE.clear()


def _prune_locked(now: float) -> None:
    import_cutoff = now - import_ttl_seconds()
    for import_id, record in list(_IMPORTS.items()):
        if record.created_at < import_cutoff:
            del _IMPORTS[import_id]
            import_path(import_id).unlink(missing_ok=True)

    overflow = len(_IMPORTS) - imports_max()
    if overflow > 0:
        oldest = sorted(_IMPORTS.values(), key=lambda item: item.created_at)
        for record in oldest[:overflow]:
            del _IMPORTS[record.import_id]
            import_path(record.import_id).unlink(missing_ok=True)

    passage_cutoff = now - passage_ttl_seconds()
    for passage_id, record in list(_PASSAGES.items()):
        if record.created_at < passage_cutoff:
            del _PASSAGES[passage_id]

    overflow = len(_PASSAGES) - passages_max()
    if overflow > 0:
        oldest = sorted(_PASSAGES.values(), key=lambda item: item.created_at)
        for record in oldest[:overflow]:
            del _PASSAGES[record.passage_id]

    # Orphan upload files left by a crash or a manual store reset.
    for path in imports_root().glob(f"{_IMPORT_ID_PREFIX}*.musicxml"):
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        if modified < import_cutoff:
            path.unlink(missing_ok=True)


def _import_for(import_id: str, owner_id: str) -> _ImportRecord | None:
    """Owner-scoped import lookup: another namespace is indistinguishable from 404."""
    with _LOCK:
        _prune_locked(time.time())
        record = _IMPORTS.get(import_id)
    if record is None or record.owner_id != owner_id:
        return None
    return record


def _passage_for(passage_id: str, owner_id: str) -> _PassageRecord | None:
    with _LOCK:
        _prune_locked(time.time())
        record = _PASSAGES.get(passage_id)
    if record is None or record.owner_id != owner_id:
        return None
    return record


def _write_upload(import_id: str, raw: bytes) -> None:
    root = imports_root()
    target = root / f"{import_id}.musicxml"
    token = f"{os.getpid()}-{threading.get_ident()}"
    temp = root / f".{import_id}.{token}.tmp"
    try:
        temp.write_bytes(raw)
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Response helpers


def _json_error(status_code: int, path: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "errors": [{"path": path, "message": message}],
        },
    )


def _error(path: str, message: str) -> ErrorOut:
    return ErrorOut(path=path, message=message)


def _normalize_meter(meter: Any) -> str | None:
    if not isinstance(meter, str):
        return None
    value = meter.strip().replace(" ", "")
    return value if value in _SUPPORTED_METERS else None


def _measure_meters(
    raw: Any, fallback_meter: Any, measure_count: int
) -> list[str]:
    """One meter per measure, always exactly ``measure_count`` entries."""
    values: list[str] = []
    if isinstance(raw, (list, tuple)):
        values = [item for item in raw if isinstance(item, str) and item.strip()]
    if len(values) != measure_count:
        fallback = str(fallback_meter or "")
        values = [fallback] * measure_count
    return values


def _meter_changes(measure_meters: list[str]) -> list[MeterChange]:
    """Meter changes after bar 1, with 1-based bars."""
    changes: list[MeterChange] = []
    if not measure_meters:
        return changes
    previous = measure_meters[0]
    for index, meter in enumerate(measure_meters[1:], start=2):
        if meter != previous:
            changes.append(MeterChange(bar=index, meter=meter))
        previous = meter
    return changes


def _summary(score: Any, filename: str) -> ImportSummary:
    """Build the stable API summary from the parser contract."""
    raw: Mapping[str, Any] = {}
    try:
        candidate = musicxml_source.score_summary(score)
    except (AttributeError, KeyError, TypeError, ValueError):
        candidate = None
    if isinstance(candidate, Mapping):
        raw = candidate

    notes = musicxml_source.score_notes(score)
    meter = raw.get("meter", getattr(score, "meter", None))
    voices = sorted(
        {
            int(note["voice"])
            for note in notes
            if not note.get("rest") and isinstance(note.get("voice"), int)
        }
    )
    try:
        measure_count = int(
            raw.get("measureCount", getattr(score, "measure_count", 0)) or 0
        )
    except (TypeError, ValueError):
        measure_count = 0
    raw_meters = raw.get("measureMeters", getattr(score, "measure_meters", None))
    measure_meters = _measure_meters(raw_meters, meter, measure_count)
    return ImportSummary(
        title=str(
            raw.get("title", getattr(score, "title", None)) or filename or "Untitled"
        ),
        meter=str(meter or ""),
        measureMeters=measure_meters,
        meterChanges=_meter_changes(measure_meters),
        measureCount=measure_count,
        keyFifths=int(raw.get("keyFifths", getattr(score, "key_fifths", 0)) or 0),
        keyMode=raw.get("keyMode", getattr(score, "key_mode", None)),
        tempo=raw.get("tempo", getattr(score, "tempo", None)),
        noteCount=int(raw.get("noteCount", len(notes)) or 0),
        voices=list(raw.get("voices", voices) or []),
        sourceHash=_source_hash(
            raw.get("sourceHash", getattr(score, "source_hash", ""))
        ),
        meterSupported=all(
            _normalize_meter(item) is not None for item in measure_meters
        ),
    )


def _source_hash(value: Any) -> str:
    """Use the same ``sha256:<hex>`` spelling as every other Studio hash."""
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("sha256:") else f"sha256:{text}"


def _warnings(score: Any) -> list[str]:
    raw = getattr(score, "warnings", ()) or ()
    return [str(item) for item in raw]


def _import_payload(record: _ImportRecord) -> dict[str, Any]:
    return {
        "ok": True,
        "importId": record.import_id,
        "filename": record.filename,
        "summary": record.summary.model_dump(),
        "notes": [dict(note) for note in record.notes],
        "warnings": list(record.warnings),
    }


# ---------------------------------------------------------------------------
# Upload / read


@router.post(
    "/musicxml",
    response_model=ImportResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
)
async def upload_musicxml(
    file: UploadFile = File(...),
    owner_id: str = Depends(studio_session.require_owner),
) -> Any:
    """Parse one ``.musicxml``/``.xml`` upload and keep it for passages."""
    filename = Path((file.filename or "").strip()).name[:255]
    suffix = Path(filename).suffix.lower() if filename else ""
    if suffix not in _EXTENSIONS:
        await file.close()
        return _json_error(
            415,
            "file",
            "upload a .musicxml or .xml file",
        )

    cap = max_upload_bytes()
    buffer = bytearray()
    try:
        while True:
            chunk = await file.read(_CHUNK)
            if not chunk:
                break
            buffer.extend(chunk)
            if len(buffer) > cap:
                return _json_error(
                    413,
                    "file",
                    f"MusicXML upload exceeds the {cap} byte limit",
                )
    finally:
        await file.close()

    raw = bytes(buffer)
    try:
        score = musicxml_source.parse_musicxml(raw, filename=filename)
    except _PARSER_ERRORS as exc:
        return _json_error(400, "file", str(exc) or "invalid MusicXML")

    parsed_notes = musicxml_source.score_notes(score)
    if not any(
        not note.get("rest") and note.get("midi") is not None
        for note in parsed_notes
    ):
        return _json_error(400, "file", "the score has no pitched notes")
    if len(parsed_notes) > max_score_notes():
        return _json_error(
            413,
            "file",
            f"the score has too many notes (max {max_score_notes()})",
        )

    # The owner is part of the id so two sessions uploading identical bytes get
    # separate records; within one session the id is still content-stable.
    digest = hashlib.sha256(owner_id.encode("utf-8") + b"\0" + raw).hexdigest()
    import_id = f"{_IMPORT_ID_PREFIX}{digest[:16]}"
    summary = _summary(score, filename)
    record = _ImportRecord(
        import_id=import_id,
        owner_id=owner_id,
        filename=filename,
        score=score,
        summary=summary,
        notes=parsed_notes,
        warnings=tuple(_warnings(score)),
        created_at=time.time(),
    )
    _write_upload(import_id, raw)
    with _LOCK:
        now = time.time()
        _IMPORTS[import_id] = record
        _prune_locked(now)
    return _import_payload(record)


@router.get(
    "/musicxml/{import_id}",
    response_model=ImportResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_musicxml_import(
    import_id: str,
    owner_id: str = Depends(studio_session.require_owner),
) -> Any:
    """Return the stored summary/notes/warnings for one owned upload."""
    record = _import_for(import_id, owner_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "import_not_found", "message": "No such import"},
        )
    return _import_payload(record)


# ---------------------------------------------------------------------------
# Passage


def _validate_range(
    bar_start: int, bar_end: int, measure_count: int
) -> list[ErrorOut]:
    errors: list[ErrorOut] = []
    if measure_count <= 0:
        return [_error("barStart", "the score has no measures")]
    if bar_start < 1:
        errors.append(_error("barStart", "barStart must be >= 1"))
    elif bar_start > measure_count:
        errors.append(
            _error(
                "barStart",
                f"barStart {bar_start} is outside 1..{measure_count}",
            )
        )
    if bar_end < 1:
        errors.append(_error("barEnd", "barEnd must be >= 1"))
    elif bar_end > measure_count:
        errors.append(
            _error("barEnd", f"barEnd {bar_end} is outside 1..{measure_count}")
        )
    if bar_start >= 1 and bar_end >= 1 and bar_end < bar_start:
        errors.append(_error("barEnd", "barEnd must be >= barStart"))
    return errors


def _validate_voices(voices: list[int] | None) -> list[ErrorOut]:
    if voices is None:
        return []
    if not voices:
        return [_error("voices", "voices must contain at least one voice number")]
    errors: list[ErrorOut] = []
    for index, voice in enumerate(voices):
        if (
            isinstance(voice, bool)
            or not isinstance(voice, int)
            or not 1 <= voice <= _MAX_AUTHORED_VOICES
        ):
            errors.append(
                _error(
                    f"voices[{index}]",
                    f"voice must be in 1..{_MAX_AUTHORED_VOICES}",
                )
            )
    return errors


_QUARTER_EPS = 1e-9


@dataclass(frozen=True)
class _BeatWindow:
    """One resolved beat range: a constant meter plus absolute quarter ticks."""

    meter: str
    bar_length: float
    beat_start: float
    beat_end: float
    first_bar: int
    first_bar_beat: float
    range_start: float
    range_end: float
    starts: tuple[float, ...]


def _meter_quarter_beats(raw: Any) -> float | None:
    """Quarter-note length of any ``n/d`` meter, supported or not."""
    if not isinstance(raw, str) or "/" not in raw:
        return None
    numerator, _, denominator = raw.partition("/")
    try:
        beats = int(numerator)
        beat_type = int(denominator)
    except ValueError:
        return None
    if beats <= 0 or beat_type <= 0:
        return None
    return beats * 4 / beat_type


def _quarter_lengths(measure_meters: list[str]) -> list[float]:
    """One bar length in quarter notes per measure.

    Unsupported meters still have a length; they are rejected only when the
    selected range touches them. That keeps absolute bar starts correct for a
    score whose later bars use a meter the preview cannot render.
    """
    return [
        length if length is not None else 4.0
        for length in (_meter_quarter_beats(raw) for raw in measure_meters)
    ]


def _resolve_beat_window(
    summary: ImportSummary,
    bar_start: int,
    bar_end: int,
    beat_start: float | None,
    beat_end: float | None,
) -> tuple[_BeatWindow | None, list[ErrorOut]]:
    """Resolve the meter and absolute tick window for a beat range.

    ``beatEnd`` is exclusive. Intersected bars must share one meter; a range
    that ends exactly on a bar boundary does not include the next bar.
    """
    start0 = bar_start - 1
    end0 = bar_end - 1
    lengths = _quarter_lengths(summary.measureMeters)
    if len(lengths) < bar_end:
        return None, [_error("meter", "the selected bars have no meter")]

    # Only bars that can be touched by this range need a supported meter.
    # Unsupported meters elsewhere still contribute their real bar length to
    # the absolute starts below.
    for index in range(start0, bar_end):
        raw = summary.measureMeters[index]
        if _normalize_meter(raw) is None:
            return None, [
                _error(
                    "meter",
                    f"meter {raw!r} is not supported yet "
                    f"({', '.join(_SUPPORTED_METERS)})",
                )
            ]

    start_length = lengths[start0]
    end_length = lengths[end0]
    if beat_start is None:
        beat_start = 0.0
    if beat_end is None:
        beat_end = end_length

    errors: list[ErrorOut] = []
    if not math.isfinite(beat_start):
        errors.append(_error("beatStart", "beatStart must be a finite number"))
    elif not 0.0 <= beat_start <= start_length:
        errors.append(
            _error(
                "beatStart",
                f"beatStart {beat_start:g} is outside 0..{start_length:g} "
                f"quarter beats of bar {bar_start}",
            )
        )
    if not math.isfinite(beat_end):
        errors.append(_error("beatEnd", "beatEnd must be a finite number"))
    elif not 0.0 <= beat_end <= end_length:
        errors.append(
            _error(
                "beatEnd",
                f"beatEnd {beat_end:g} is outside 0..{end_length:g} "
                f"quarter beats of bar {bar_end}",
            )
        )
    if errors:
        return None, errors

    starts: list[float] = []
    cursor = 0.0
    for length in lengths:
        starts.append(cursor)
        cursor += length

    range_start = starts[start0] + beat_start
    range_end = starts[end0] + beat_end
    if range_start >= range_end - _QUARTER_EPS:
        return None, [
            _error(
                "beatEnd",
                "the selected range is empty or reversed; beatEnd must be "
                "after beatStart",
            )
        ]

    bars = [
        index
        for index in range(start0, bar_end)
        if starts[index] < range_end - _QUARTER_EPS
        and starts[index] + lengths[index] > range_start + _QUARTER_EPS
    ]
    if not bars:
        return None, [_error("beatEnd", "the selected range has no bars")]

    distinct: list[str] = []
    for index in bars:
        meter = _normalize_meter(summary.measureMeters[index])
        if meter is not None and meter not in distinct:
            distinct.append(meter)
    if len(distinct) > 1:
        return None, [
            _error(
                "meter",
                f"bars {bars[0] + 1}-{bars[-1] + 1} mix meters "
                f"{', '.join(distinct)}; request a range with a single "
                "constant meter",
            )
        ]

    meter = distinct[0]
    first_bar = bars[0]
    return (
        _BeatWindow(
            meter=meter,
            bar_length=lengths[first_bar],
            beat_start=beat_start,
            beat_end=beat_end,
            first_bar=first_bar,
            first_bar_beat=range_start - starts[first_bar],
            range_start=range_start,
            range_end=range_end,
            starts=tuple(starts),
        ),
        [],
    )


def _tie_label(start: bool, stop: bool) -> str:
    if start and stop:
        return "continue"
    if start:
        return "start"
    if stop:
        return "stop"
    return "none"


def _clip_and_rebase(
    notes: list[dict[str, Any]], window: _BeatWindow
) -> list[dict[str, Any]]:
    """Clip notes to the tick window and rebase the selection start to bar 0.

    A note that starts before the window keeps its tail and moves to onset 0;
    a note that ends after the window is shortened. Notes that only touch a
    boundary (zero overlap) are dropped.
    """
    rebased: list[dict[str, Any]] = []
    for note in notes:
        try:
            bar = int(note["bar"])
            beat = float(note.get("beat") or 0.0)
            duration = float(note.get("duration") or 0.0)
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(beat) or not math.isfinite(duration):
            continue
        if duration <= 0.0 or bar < 0 or bar >= len(window.starts):
            continue

        onset = window.starts[bar] + beat
        end = onset + duration
        if end <= window.range_start + _QUARTER_EPS:
            continue
        if onset >= window.range_end - _QUARTER_EPS:
            continue

        start_clipped = onset < window.range_start - _QUARTER_EPS
        end_clipped = end > window.range_end + _QUARTER_EPS
        clipped_start = window.range_start if start_clipped else onset
        clipped_end = window.range_end if end_clipped else end
        clipped_duration = clipped_end - clipped_start
        if not math.isfinite(clipped_duration) or clipped_duration <= 0.0:
            continue

        if start_clipped:
            relative_bar = 0
            relative_beat = 0.0
        elif window.first_bar_beat == 0.0:
            # Whole-bar selection: keep the parser's exact beat value.
            relative_bar = bar - window.first_bar
            relative_beat = beat
        else:
            # The relative bar grid is anchored at the selection start, so a
            # note before the original barline's beat offset belongs to the
            # previous relative bar.
            shifted = beat - window.first_bar_beat
            if shifted >= 0.0:
                relative_bar = bar - window.first_bar
                relative_beat = shifted
            elif bar > window.first_bar:
                relative_bar = bar - window.first_bar - 1
                relative_beat = shifted + window.bar_length
            else:
                relative_bar = 0
                relative_beat = 0.0

        # A note may cross a relative barline that is offset from the source
        # barline (a beat range starts mid-bar). Split it there so every
        # authored event stays inside one bar, as the spec validator requires.
        remaining = (
            duration if not (start_clipped or end_clipped) else clipped_duration
        )
        pieces: list[dict[str, Any]] = []
        while remaining > _QUARTER_EPS:
            room = window.bar_length - relative_beat
            if room <= _QUARTER_EPS:
                relative_bar += 1
                relative_beat = 0.0
                continue
            piece = min(remaining, room)
            if remaining - piece <= _QUARTER_EPS:
                piece = remaining
            copy = dict(note)
            copy["bar"] = relative_bar
            copy["beat"] = relative_beat
            copy["duration"] = piece
            pieces.append(copy)
            remaining -= piece
            relative_bar += 1
            relative_beat = 0.0

        if len(pieces) > 1:
            original_tie = str(note.get("tie") or "none")
            original_start = original_tie in ("start", "continue", "next_bar") or bool(
                note.get("tie_start")
            )
            original_stop = original_tie in ("stop", "continue") or bool(
                note.get("tie_stop")
            )
            for index, piece in enumerate(pieces):
                start = index < len(pieces) - 1 or original_start
                stop = index > 0 or original_stop
                piece["tie"] = _tie_label(start, stop)
                piece["tie_start"] = start
                piece["tie_stop"] = stop
                # The audio path merges these pieces back into one sustained
                # note; keep a private id so the response notes do not retrigger
                # at the virtual barline.
                piece["_split_group"] = id(note)
        rebased.extend(pieces)
    return rebased


def _rebase(
    notes: list[dict[str, Any]], bar_start0: int, bar_end: int
) -> list[dict[str, Any]]:
    """Normalise parser bars to 0-based passage bars.

    The parser contract does not pin whether ``slice_score`` keeps absolute
    bars or rebases; the fallback keeps them absolute. If every returned bar is
    at/after the requested start, treat the values as absolute and subtract the
    requested start. Otherwise the slice is already rebased.
    """
    bars = [
        int(note["bar"])
        for note in notes
        if isinstance(note, Mapping) and isinstance(note.get("bar"), (int, float))
    ]
    if not bars:
        return []
    offset = bar_start0 if min(bars) >= bar_start0 else min(0, min(bars))
    width = max(0, bar_end - bar_start0)
    rebased: list[dict[str, Any]] = []
    for note in notes:
        try:
            bar = int(note["bar"])
        except (KeyError, TypeError, ValueError):
            continue
        relative = bar - offset
        if not 0 <= relative < width:
            continue
        copy = dict(note)
        copy["bar"] = relative
        rebased.append(copy)
    return rebased


def _sanitize_endpoints(notes: list[dict[str, Any]]) -> None:
    """Clear tie/slur starts or stops that do not pair inside the passage."""
    for field in ("tie", "slur"):
        by_voice: dict[int, list[int]] = {}
        for index, note in enumerate(notes):
            by_voice.setdefault(int(note.get("voice") or 1), []).append(index)
        for indexes in by_voice.values():
            indexes.sort(
                key=lambda index: (
                    int(notes[index].get("bar") or 0),
                    float(notes[index].get("beat") or 0.0),
                    index,
                )
            )
            open_starts: list[int] = []
            for index in indexes:
                value = notes[index].get(field, "none")
                if value in ("start", "next_bar"):
                    open_starts.append(index)
                elif value == "continue":
                    if not open_starts:
                        notes[index][field] = "none"
                elif value == "stop":
                    if open_starts:
                        open_starts.pop()
                    else:
                        notes[index][field] = "none"
            for index in open_starts:
                notes[index][field] = "none"


def _audio_notes(
    notes: list[dict[str, Any]], beats_per_bar: int
) -> list[dict[str, Any]]:
    """Synth notes, merging split fragments back into one sustained note.

    The authored spec keeps the split pieces with tie labels. The preview
    synth has no tie support, so a piece group is recombined here to avoid a
    second attack at the virtual barline.
    """
    result: list[dict[str, Any]] = []
    last_by_group: dict[tuple[Any, int], dict[str, Any]] = {}
    for note in notes:
        if note.get("rest"):
            continue
        try:
            midi = int(note.get("midi"))
            bar = int(note.get("bar") or 0)
            beat = float(note.get("beat") or 0.0)
            duration = float(note.get("duration") or 0.0)
            voice = int(note.get("voice") or 1)
        except (TypeError, ValueError):
            continue
        if duration <= 0.0:
            continue
        group = note.get("_split_group")
        if group is not None:
            previous = last_by_group.get((group, voice))
            if previous is not None:
                previous_end = (
                    previous["bar"] * beats_per_bar
                    + previous["beat"]
                    + previous["duration"]
                )
                onset = bar * beats_per_bar + beat
                if abs(previous_end - onset) <= _QUARTER_EPS:
                    previous["duration"] += duration
                    continue
        entry = {
            "bar": bar,
            "beat": beat,
            "duration": duration,
            "midi": midi,
            "voice": voice,
            "velocity": 64,
            "accent": bool(note.get("accent")),
            "staccato": bool(note.get("staccato")),
        }
        result.append(entry)
        if group is not None:
            last_by_group[(group, voice)] = entry
    return result


def _assign_playable_voices(
    notes: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    """Keep each authored voice monophonic.

    ``validate_authored`` rejects overlapping notes in one voice. MusicXML
    chords share one source voice, so simultaneous tones are spread over the
    free authored voices 1..4. A passage that needs no fix keeps the parser's
    voices unchanged.
    """
    ends: dict[tuple[int, int], float] = {}
    changed = False
    ordered = sorted(
        notes,
        key=lambda note: (
            int(note.get("bar") or 0),
            float(note.get("beat") or 0.0),
            -int(note.get("midi") or 0),
        ),
    )
    result: list[dict[str, Any]] = []
    for note in ordered:
        copy = dict(note)
        bar = int(copy.get("bar") or 0)
        start = float(copy.get("beat") or 0.0)
        duration = float(copy.get("duration") or 0.0)
        desired = int(copy.get("voice") or 1)
        if not 1 <= desired <= _MAX_AUTHORED_VOICES:
            desired = 1
        voice = desired
        if _voice_busy(ends, voice, bar, start):
            voice = next(
                (
                    candidate
                    for candidate in range(1, _MAX_AUTHORED_VOICES + 1)
                    if not _voice_busy(ends, candidate, bar, start)
                ),
                desired,
            )
        if voice != desired:
            changed = True
        copy["voice"] = voice
        ends[(voice, bar)] = max(
            ends.get((voice, bar), 0.0), start + max(0.0, duration)
        )
        result.append(copy)
    return result, changed


def _voice_busy(
    ends: dict[tuple[int, int], float], voice: int, bar: int, start: float
) -> bool:
    return ends.get((voice, bar), -1.0) > start + 1e-9


def _build_spec(
    *,
    import_id: str,
    filename: str,
    summary: ImportSummary,
    bar_start: int,
    bar_end: int,
    form_meter: Meter,
    events: list[AuthoredEvent],
) -> TextureSpec:
    meter_spec = MeterSpec.from_form_meter(form_meter)
    variant = MeterVariant(
        meter=meter_spec,
        materializer=None,
        transform="none",
        unsupported=True,
        reason=(
            "imported MusicXML: literal authored notes; no materializer exists"
        ),
        sentences=(),
    )
    return TextureSpec(
        id=f"musicxml_{import_id}_{bar_start}_{bar_end}",
        composer="unknown",
        kind="pattern",
        level="texture",
        parent=None,
        runtime="code",
        status="draft",
        source={
            "piece": summary.title,
            "filename": filename,
            "bars": [bar_start, bar_end],
            "notation": "musicxml",
            "import_id": import_id,
            "source_hash": summary.sourceHash,
        },
        meter_variants=(variant,),
        authored=tuple(events),
        provenance={
            "model": "musicxml-import",
            "parser": musicxml_source.PARSER_MODULE,
            "source_hash": summary.sourceHash,
            "reviewed_by": None,
        },
    )


def _render_hash(notes: list[dict[str, Any]]) -> str:
    payload = json.dumps(notes, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _passage_id(
    import_id: str,
    bar_start: int,
    bar_end: int,
    voices: list[int],
    beat_start: float | None = None,
    beat_end: float | None = None,
) -> str:
    seed: dict[str, Any] = {
        "importId": import_id,
        "barStart": bar_start,
        "barEnd": bar_end,
        "voices": sorted(voices),
    }
    # Keep the old id for a plain whole-bar request, but never let two beat
    # ranges inside the same bars collide.
    if beat_start is not None or beat_end is not None:
        seed["beatStart"] = float(beat_start or 0.0)
        seed["beatEnd"] = float(beat_end or 0.0)
    payload = json.dumps(seed, sort_keys=True, separators=(",", ":"))
    return _PASSAGE_ID_PREFIX + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _range_meter(
    summary: ImportSummary, bar_start: int, bar_end: int
) -> tuple[str | None, list[ErrorOut]]:
    """Resolve one constant meter for the 1-based inclusive bar range."""
    meters = summary.measureMeters
    selected = meters[bar_start - 1:bar_end] if meters else []
    if not selected:
        return None, [_error("meter", "the selected bars have no meter")]
    distinct = list(dict.fromkeys(selected))
    if len(distinct) > 1:
        return None, [
            _error(
                "meter",
                f"bars {bar_start}-{bar_end} mix meters "
                f"{', '.join(distinct)}; request a range with a single "
                "constant meter",
            )
        ]
    raw = distinct[0]
    meter = _normalize_meter(raw)
    if meter is None:
        return None, [
            _error(
                "meter",
                f"meter {raw!r} is not supported yet "
                f"({', '.join(_SUPPORTED_METERS)})",
            )
        ]
    return meter, []


def _passage_payload(
    *,
    import_id: str,
    owner_id: str,
    bar_start: int,
    bar_end: int,
    voices: list[int],
    record: _ImportRecord,
    beat_start: float | None = None,
    beat_end: float | None = None,
) -> dict[str, Any]:
    score = record.score
    start0 = bar_start - 1
    window: _BeatWindow | None = None
    if beat_start is not None or beat_end is not None:
        window, beat_errors = _resolve_beat_window(
            record.summary, bar_start, bar_end, beat_start, beat_end
        )
        if beat_errors or window is None:
            return PassageResponse(
                ok=False,
                warnings=list(record.warnings),
                errors=beat_errors,
            ).model_dump()
        meter = window.meter
    else:
        meter, meter_errors = _range_meter(record.summary, bar_start, bar_end)
        if meter_errors:
            return PassageResponse(
                ok=False,
                warnings=list(record.warnings),
                errors=meter_errors,
            ).model_dump()
    form_meter, beats_per_bar = _SUPPORTED_METERS[meter]

    try:
        sliced = musicxml_source.slice_score(
            score,
            bar_start=bar_start,
            bar_end=bar_end,
            voices=voices or None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return PassageResponse(
            ok=False,
            errors=[_error("passage", f"slice failed: {exc}")],
        ).model_dump()

    raw_notes = [dict(note) for note in sliced]
    warnings = list(
        dict.fromkeys(
            [str(item) for item in record.warnings]
            + [str(item) for item in _warnings(sliced)]
        )
    )

    notes = (
        _clip_and_rebase(raw_notes, window)
        if window is not None
        else _rebase(raw_notes, start0, bar_end)
    )
    missing_voices = sorted(
        {
            int(voice)
            for voice in voices
            if not any(int(note.get("voice") or 1) == int(voice) for note in notes)
        }
    )
    notes, voices_changed = _assign_playable_voices(notes)
    _sanitize_endpoints(notes)
    if voices_changed:
        warnings.append(
            "simultaneous notes were split across authored voices 1..4 to keep "
            "each voice monophonic"
        )
    if missing_voices:
        warnings.append(
            "no notes for requested voice(s): "
            + ", ".join(str(voice) for voice in missing_voices)
        )

    events: list[AuthoredEvent] = []
    for note in notes:
        # A rest is a matrix cell with no authored event. The UI draws the gap
        # as a rest; it is never a texture event and never a warning.
        if note.get("rest"):
            continue
        midi = note.get("midi")
        duration = note.get("duration")
        beat = note.get("beat")
        if not isinstance(midi, (int, float)) or not 0 <= int(midi) <= 127:
            warnings.append(
                f"bar {int(note.get('bar') or 0) + bar_start}: note without a "
                "MIDI pitch skipped"
            )
            continue
        if not isinstance(duration, (int, float)) or float(duration) <= 0:
            warnings.append(
                f"bar {int(note.get('bar') or 0) + bar_start}: note with a "
                "non-positive duration skipped"
            )
            continue
        if not isinstance(beat, (int, float)) or float(beat) < 0:
            beat = 0.0
        staff = note.get("staff")
        events.append(
            AuthoredEvent(
                bar=int(note.get("bar") or 0),
                beat=float(beat),
                duration_beats=float(duration),
                voice=int(note.get("voice") or 1),
                pitch=PitchRef.literal_midi(int(midi)),
                staff=staff if staff in (1, 2) else 1,
                tie=str(note.get("tie") or "none"),
                slur=str(note.get("slur") or "none"),
                accent=bool(note.get("accent")),
                tenuto=bool(note.get("tenuto")),
                staccato=bool(note.get("staccato")),
                string=(
                    note.get("string")
                    if isinstance(note.get("string"), int)
                    else None
                ),
                fret=(
                    note.get("fret")
                    if isinstance(note.get("fret"), int)
                    else None
                ),
                written_pitch=(
                    note.get("written_pitch")
                    if isinstance(note.get("written_pitch"), str)
                    else None
                ),
                sounding_pitch=(
                    note.get("sounding_pitch")
                    if isinstance(note.get("sounding_pitch"), str)
                    else None
                ),
                conflict=False,
                review="edited",
            )
        )

    spec = _build_spec(
        import_id=import_id,
        filename=record.filename,
        summary=record.summary,
        bar_start=bar_start,
        bar_end=bar_end,
        form_meter=form_meter,
        events=events,
    )
    spec_mapping = texture_spec_to_mapping(spec)
    errors = [
        _error(error.path, error.message)
        for error in check_texture_spec(
            spec_mapping, meter=spec.meter_variants[0].meter
        )
    ]

    synth_notes = _audio_notes(notes, beats_per_bar)

    audio_url: str | None = None
    duration_sec = 0.0
    if synth_notes:
        try:
            asset = studio_audio.ensure_audio(
                _render_hash(synth_notes), synth_notes, beats_per_bar
            )
        except studio_audio.AudioUnavailable as exc:
            errors.append(_error("audio", str(exc)))
        else:
            audio_url = asset.audio_url
            duration_sec = asset.duration_sec
    else:
        errors.append(_error("audio", "the passage has no notes to synthesize"))

    passage_id = _passage_id(
        import_id,
        bar_start,
        bar_end,
        list(voices),
        beat_start=window.beat_start if window is not None else None,
        beat_end=window.beat_end if window is not None else None,
    )
    response = PassageResponse(
        ok=not errors,
        passageId=passage_id,
        meter=meter,
        beatsPerBar=beats_per_bar,
        spec=spec_mapping,
        notes=synth_notes,
        audioUrl=audio_url,
        durationSec=duration_sec,
        warnings=warnings,
        errors=errors,
    )
    payload = response.model_dump()
    with _LOCK:
        now = time.time()
        _PASSAGES[passage_id] = _PassageRecord(
            passage_id=passage_id,
            owner_id=owner_id,
            import_id=import_id,
            payload=payload,
            created_at=now,
        )
        _prune_locked(now)
    return payload


@router.post(
    "/musicxml/{import_id}/passage",
    response_model=PassageResponse,
    responses={404: {"model": ErrorResponse}},
)
def create_musicxml_passage(
    import_id: str,
    body: PassageRequest,
    owner_id: str = Depends(studio_session.require_owner),
) -> Any:
    """Validate and preview one 1-based tick range (bars plus beat offsets)."""
    record = _import_for(import_id, owner_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "import_not_found", "message": "No such import"},
        )

    errors = _validate_range(
        body.barStart, body.barEnd, record.summary.measureCount
    )
    errors.extend(_validate_voices(body.voices))
    if errors:
        return PassageResponse(ok=False, errors=errors).model_dump()

    voices = sorted({int(voice) for voice in body.voices}) if body.voices else []
    return _passage_payload(
        import_id=import_id,
        owner_id=owner_id,
        bar_start=body.barStart,
        bar_end=body.barEnd,
        voices=voices,
        record=record,
        beat_start=body.beatStart,
        beat_end=body.beatEnd,
    )


@router.get(
    "/musicxml/passages/{passage_id}",
    response_model=PassageResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_musicxml_passage(
    passage_id: str,
    owner_id: str = Depends(studio_session.require_owner),
) -> Any:
    """Return an owned passage until its TTL expires."""
    record = _passage_for(passage_id, owner_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "passage_not_found", "message": "No such passage"},
        )
    return record.payload


# ---------------------------------------------------------------------------
# Sentence draft


def _draft_quota_response(decision: _DraftQuota) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "ok": False,
            "errors": [
                {
                    "path": "quota",
                    "message": (
                        f"{decision.scope} daily MusicXML draft quota "
                        f"({decision.limit}) is exhausted"
                    ),
                }
            ],
            "limit": decision.limit,
            "day": decision.day,
            "retryAfter": decision.retry_after_seconds,
        },
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


@router.post(
    "/musicxml/{import_id}/sentence-draft",
    responses={
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def create_sentence_draft(
    import_id: str,
    body: SentenceDraftRequest,
    owner_id: str = Depends(studio_session.require_owner),
) -> Any:
    """Build one sentence draft from a whole-bar passage.

    The response follows the Studio validator convention: structural errors are
    a 200 body ``{ok: false, errors: [...]}``. Missing/foreign records are 404;
    an exhausted per-owner draft quota is a structured 429.
    """
    record = _import_for(import_id, owner_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "import_not_found", "message": "No such import"},
        )

    errors = _validate_range(
        body.barStart, body.barEnd, record.summary.measureCount
    )
    errors.extend(_validate_voices(body.voices))
    if errors:
        return {"ok": False, "errors": [error.model_dump() for error in errors]}

    # The draft is whole-bar, so its meter is the constant meter of the whole
    # selected bar range. The beat window is still resolved to reject invalid
    # offsets and empty ranges; its meter is intentionally not substituted for
    # the whole-bar one when a partial range touches only some of the bars.
    meter, meter_errors = _range_meter(
        record.summary, body.barStart, body.barEnd
    )
    if meter_errors:
        return {
            "ok": False,
            "errors": [error.model_dump() for error in meter_errors],
        }

    window, window_errors = _resolve_beat_window(
        record.summary,
        body.barStart,
        body.barEnd,
        body.beatStart,
        body.beatEnd,
    )
    if window_errors or window is None:
        return {
            "ok": False,
            "errors": [error.model_dump() for error in window_errors],
        }

    draft = musicxml_sentence.prepare_draft(
        import_id=import_id,
        meter=meter,
        bar_start=body.barStart,
        bar_end=body.barEnd,
        mode=body.mode,
        pattern=body.pattern,
        template_id=body.templateId,
        new_pattern=(
            body.newPattern.model_dump() if body.newPattern is not None else None
        ),
        beat_start=window.beat_start,
        beat_end=window.beat_end,
    )
    if not draft.ok:
        return draft.as_error()

    decision = consume_draft(owner_id)
    if not decision.allowed:
        return _draft_quota_response(decision)
    try:
        payload = musicxml_sentence.render_draft(draft)
    except Exception:
        refund_draft(owner_id, decision.day)
        raise
    if not payload.get("ok"):
        refund_draft(owner_id, decision.day)
    return payload
