"""MusicXML upload + passage preview for the Texture Studio.

Prefix: ``/v1/studio/import``. This is the API seam between a score file and
the existing offline ``TextureSpec`` validator plus the code-only preview
synth. It does not publish, register a pattern, call Gemini, or touch the
database:

* ``POST /musicxml``                      — multipart upload, parsed once
* ``GET  /musicxml/{importId}``           — the stored summary/notes/warnings
* ``POST /musicxml/{importId}/passage``   — one bar range → spec + synth notes
* ``GET  /musicxml/passages/{passageId}`` — the passage built by the POST

Bars are **1-based and inclusive** in requests, matching the measure numbers a
musician reads in the score. Parser notes are 0-based internally; the response
spec/notes are rebased so ``barStart`` is bar 0 of the passage.

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
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.sonify.form import METER_34, METER_44, METER_68, Meter
from app.studio import audio as studio_audio
from app.studio import musicxml_source
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

# MusicXML meter → runtime form meter. ``6/8`` is three quarter-note beats,
# matching ``app.studio.audio._METER_BEATS``.
_SUPPORTED_METERS: dict[str, tuple[Meter, int]] = {
    "3/4": (METER_34, 3),
    "4/4": (METER_44, 4),
    "6/8": (METER_68, 3),
}

_PARSER_ERRORS = (ValueError, TypeError, KeyError, IndexError, ET.ParseError)


# ---------------------------------------------------------------------------
# Request/response models


class ErrorOut(BaseModel):
    path: str
    message: str


class ImportSummary(BaseModel):
    title: str
    meter: str
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
    voices: list[int] | None = None


class PassageResponse(BaseModel):
    ok: bool
    passageId: str | None = None
    spec: dict[str, Any] | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)
    audioUrl: str | None = None
    durationSec: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorOut] = Field(default_factory=list)


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
    filename: str
    score: Any
    summary: ImportSummary
    notes: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...]
    created_at: float


@dataclass
class _PassageRecord:
    passage_id: str
    import_id: str
    payload: dict[str, Any]
    created_at: float


_LOCK = threading.RLock()
_IMPORTS: dict[str, _ImportRecord] = {}
_PASSAGES: dict[str, _PassageRecord] = {}


def clear_store() -> None:
    """Drop every in-memory record. Tests use this between cases."""
    with _LOCK:
        _IMPORTS.clear()
        _PASSAGES.clear()


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
    return ImportSummary(
        title=str(
            raw.get("title", getattr(score, "title", None)) or filename or "Untitled"
        ),
        meter=str(meter or ""),
        measureCount=measure_count,
        keyFifths=int(raw.get("keyFifths", getattr(score, "key_fifths", 0)) or 0),
        keyMode=raw.get("keyMode", getattr(score, "key_mode", None)),
        tempo=raw.get("tempo", getattr(score, "tempo", None)),
        noteCount=int(raw.get("noteCount", len(notes)) or 0),
        voices=list(raw.get("voices", voices) or []),
        sourceHash=_source_hash(
            raw.get("sourceHash", getattr(score, "source_hash", ""))
        ),
        meterSupported=_normalize_meter(meter) is not None,
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
async def upload_musicxml(file: UploadFile = File(...)) -> Any:
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

    digest = hashlib.sha256(raw).hexdigest()
    import_id = f"{_IMPORT_ID_PREFIX}{digest[:16]}"
    summary = _summary(score, filename)
    record = _ImportRecord(
        import_id=import_id,
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
def get_musicxml_import(import_id: str) -> Any:
    """Return the stored summary/notes/warnings for one upload."""
    with _LOCK:
        _prune_locked(time.time())
        record = _IMPORTS.get(import_id)
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
        if not isinstance(voice, int) or not 1 <= voice <= _MAX_AUTHORED_VOICES:
            errors.append(
                _error(
                    f"voices[{index}]",
                    f"voice must be in 1..{_MAX_AUTHORED_VOICES}",
                )
            )
    return errors


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
    import_id: str, bar_start: int, bar_end: int, voices: list[int]
) -> str:
    seed = json.dumps(
        {
            "importId": import_id,
            "barStart": bar_start,
            "barEnd": bar_end,
            "voices": sorted(voices),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return _PASSAGE_ID_PREFIX + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _passage_payload(
    *,
    import_id: str,
    bar_start: int,
    bar_end: int,
    voices: list[int],
    record: _ImportRecord,
) -> dict[str, Any]:
    score = record.score
    start0 = bar_start - 1
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

    notes = _rebase(raw_notes, start0, bar_end)
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

    meter = _normalize_meter(record.summary.meter)
    if meter is None:
        return PassageResponse(
            ok=False,
            warnings=warnings,
            errors=[
                _error(
                    "meter",
                    f"meter {record.summary.meter!r} is not supported yet "
                    "(3/4, 4/4, 6/8)",
                )
            ],
        ).model_dump()
    form_meter, beats_per_bar = _SUPPORTED_METERS[meter]

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

    synth_notes = [
        {
            "bar": int(event.bar),
            "beat": float(event.beat),
            "duration": float(event.duration_beats),
            "midi": int(event.pitch.value or 0),
            "voice": int(event.voice),
            "velocity": 64,
            "accent": bool(event.accent),
            "staccato": bool(event.staccato),
        }
        for event in events
    ]

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

    passage_id = _passage_id(import_id, bar_start, bar_end, list(voices))
    response = PassageResponse(
        ok=not errors,
        passageId=passage_id,
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
def create_musicxml_passage(import_id: str, body: PassageRequest) -> Any:
    """Validate and preview one 1-based, inclusive bar range."""
    with _LOCK:
        _prune_locked(time.time())
        record = _IMPORTS.get(import_id)
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
        bar_start=body.barStart,
        bar_end=body.barEnd,
        voices=voices,
        record=record,
    )


@router.get(
    "/musicxml/passages/{passage_id}",
    response_model=PassageResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_musicxml_passage(passage_id: str) -> Any:
    """Return a passage built by ``POST .../passage`` until its TTL expires."""
    with _LOCK:
        _prune_locked(time.time())
        record = _PASSAGES.get(passage_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "passage_not_found", "message": "No such passage"},
        )
    return record.payload
