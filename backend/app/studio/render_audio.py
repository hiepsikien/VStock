"""Production WAV store for one Studio Render Piece.

Phase C2 (``docs/studio-render-piece-plan.md`` §13 W1–W4). This is a separate
store from the recap/span audio in :mod:`app.sonify.audio`:

* it never calls ``RecapStore._render_movement`` or the 45-second synth preview;
* it has its own directory, hash, sidecar, TTL, and LRU;
* it has its own semaphore (``VSTOCK_STUDIO_RENDER_SLOTS``) so a Studio export
  cannot wait behind (or block) the recap MuseScore queue;
* a missing/failed export raises a coded error. There is no synth fallback and
  no truncation: a short or malformed WAV is a failure, not a preview.

The service accepts either a :class:`~app.sonify.model.Score` (the normal path
from ``render_piece``) or an already-written MusicXML path (the async job path,
which avoids recomposing). Both paths share the same audio hash, because the
hash describes the render plus the audio pipeline, not the XML bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.sonify import audio as sonify_audio
from app.sonify.audio import (
    RecapUnavailable,
    general_soundfont,
    musescore_export,
    waveform_peaks_with_level,
)
from app.sonify.model import Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.params import active_params, params_hash
from app.sonify.playback import piece_seconds
from app.studio import render_store

__all__ = [
    "AUDIO_REVISION",
    "AUDIO_CACHE_TTL_SECONDS",
    "AUDIO_MAX_CACHE_FILES",
    "CACHE_TTL_SECONDS",
    "MAX_CACHE_FILES",
    "StudioAudioAsset",
    "StudioAudioError",
    "StudioAudioUnavailable",
    "StudioAudioTimeout",
    "StudioAudioFailed",
    "audio_hash_for",
    "audio_path",
    "audio_root",
    "cached_for_render",
    "load_audio",
    "musescore_version",
    "render_studio_wav",
    "soundfont_version",
]

#: Bump when the score, soundfont handling, or the expected export changes.
AUDIO_REVISION = 1

AUDIO_CACHE_TTL_SECONDS = 24 * 60 * 60
AUDIO_MAX_CACHE_FILES = 128
CACHE_TTL_SECONDS = AUDIO_CACHE_TTL_SECONDS
MAX_CACHE_FILES = AUDIO_MAX_CACHE_FILES
DEFAULT_SLOTS = max(1, int(os.environ.get("VSTOCK_STUDIO_RENDER_SLOTS", "1")))

_HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_SLOTS = threading.BoundedSemaphore(DEFAULT_SLOTS)

_VERSION_CACHE: str | None = None
_VERSION_GUARD = threading.Lock()

# Tests (and future callers) can replace either this module's ``musescore_export``
# or ``app.sonify.audio.musescore_export``. Keep the original so the dispatcher
# knows which one was actually replaced.
_ORIGINAL_EXPORT = musescore_export


def _exporter():
    local = globals().get("musescore_export")
    if local is not None and local is not _ORIGINAL_EXPORT:
        return local
    return getattr(sonify_audio, "musescore_export", _ORIGINAL_EXPORT)


# MuseScore writes silence/sub-second files too, so this only rejects an empty
# or truncated write, not a short movement.
_MIN_WAV_BYTES = 64


class StudioAudioError(RuntimeError):
    """Base class for a coded production-audio failure."""

    code = "audio_failed"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class StudioAudioUnavailable(StudioAudioError):
    """MuseScore or a required input is not available."""

    code = "audio_unavailable"


class StudioAudioTimeout(StudioAudioError):
    """MuseScore did not finish inside the piece-scaled deadline."""

    code = "audio_timeout"


class StudioAudioFailed(StudioAudioError):
    """The export ran but did not produce a valid WAV."""

    code = "audio_failed"


@dataclass(frozen=True)
class StudioAudioAsset:
    """One cached WAV plus its sidecar metadata."""

    audio_hash: str
    path: Path
    duration_sec: float
    meta: Mapping[str, Any]
    cached: bool = False

    @property
    def digest(self) -> str:
        return render_store.normalize_hash(self.audio_hash) or ""

    @property
    def audio_url(self) -> str:
        return f"/v1/studio/figure/render/{self.digest}.wav"


def _normalize_hash(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    match = _HASH_RE.fullmatch(value.strip().lower())
    return match.group(1) if match is not None else None


def _display_hash(digest: str) -> str:
    return f"sha256:{digest}"


def audio_root() -> Path:
    raw = os.environ.get("VSTOCK_STUDIO_RENDER_AUDIO_DIR", "").strip()
    path = (
        Path(raw)
        if raw
        else Path(__file__).resolve().parents[2] / "var" / "studio-render" / "audio"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_path(value: str) -> Path | None:
    """Resolve one safe ``<hash>.wav`` path; ``None`` means an invalid name."""
    digest = _normalize_hash(value)
    if digest is None:
        return None
    return audio_root() / f"{digest}.wav"


def _sidecar_path(digest: str) -> Path:
    return audio_root() / f"{digest}.json"


def _lock_for(digest: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(digest)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[digest] = lock
        return lock


def musescore_version() -> str:
    """A stable version token for the audio hash.

    ``VSTOCK_MUSESCORE_VERSION`` wins so a deploy can pin it without launching
    MuseScore. Otherwise ask the binary once per process. A missing binary is a
    valid token (the export will later report ``audio_unavailable``).
    """
    global _VERSION_CACHE
    configured = os.environ.get("VSTOCK_MUSESCORE_VERSION", "").strip()
    if configured:
        return configured
    with _VERSION_GUARD:
        if _VERSION_CACHE is not None:
            return _VERSION_CACHE
        binary = sonify_audio.find_musescore()
        if binary is None:
            _VERSION_CACHE = "none"
            return _VERSION_CACHE
        version = Path(binary).name
        try:
            completed = subprocess.run(
                [binary, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if completed is not None:
            text = f"{completed.stdout}\n{completed.stderr}".strip()
            first = next((line.strip() for line in text.splitlines() if line.strip()), "")
            if first:
                version = first[:120]
        _VERSION_CACHE = f"{Path(binary).name}:{version}"
        return _VERSION_CACHE


def soundfont_version() -> str:
    """A version token for the installed soundfont (name + size + mtime)."""
    configured = os.environ.get("VSTOCK_STUDIO_SOUNDFONT_VERSION", "").strip()
    if configured:
        return configured
    font = general_soundfont()
    if font is None:
        return "default"
    try:
        stat = font.stat()
    except OSError:
        return "default"
    return f"{font.name}:{stat.st_size}:{int(stat.st_mtime)}"


def _params_token(params: Mapping[str, Any] | str | None) -> str:
    if isinstance(params, str):
        token = params.strip()
        if token:
            return token
        return params_hash(active_params())
    return params_hash(active_params() if params is None else params)


def audio_hash_for(
    render_hash: str,
    params: Mapping[str, Any] | str | None = None,
) -> str:
    """``sha256(AUDIO_REVISION|renderHash|paramsHash|musescore|soundfont)``."""
    digest = _normalize_hash(render_hash)
    if digest is None:
        raise ValueError("renderHash must be 64 lowercase hex characters")
    payload = "|".join(
        (
            str(AUDIO_REVISION),
            _display_hash(digest),
            _params_token(params),
            musescore_version(),
            soundfont_version(),
        )
    )
    return _display_hash(hashlib.sha256(payload.encode("utf-8")).hexdigest())


def _atomic_write(path: Path, data: bytes) -> None:
    root = path.parent
    root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=root, prefix=f".{path.stem}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _is_expired(path: Path, now: float) -> bool:
    try:
        modified = path.stat().st_mtime
    except OSError:
        return True
    return modified < now - AUDIO_CACHE_TTL_SECONDS


def _prune(now: float | None = None) -> None:
    """Drop expired files and keep the newest ``AUDIO_MAX_CACHE_FILES`` WAVs."""
    root = audio_root()
    now = time.time() if now is None else now
    entries: list[tuple[float, str]] = []
    for path in root.glob("*.wav"):
        digest = _normalize_hash(path.stem)
        if digest is None:
            continue
        if _is_expired(path, now):
            path.unlink(missing_ok=True)
            _sidecar_path(digest).unlink(missing_ok=True)
            continue
        try:
            entries.append((path.stat().st_mtime, digest))
        except OSError:
            continue
    entries.sort()
    for _modified, digest in entries[: max(0, len(entries) - AUDIO_MAX_CACHE_FILES)]:
        (root / f"{digest}.wav").unlink(missing_ok=True)
        _sidecar_path(digest).unlink(missing_ok=True)
    # A crash between the WAV and the sidecar leaves an orphan sidecar.
    for path in root.glob("*.json"):
        if _normalize_hash(path.stem) is None:
            path.unlink(missing_ok=True)


def load_audio(value: str) -> StudioAudioAsset | None:
    """Read a cached WAV. Missing, expired, or malformed entries are misses."""
    digest = _normalize_hash(value)
    if digest is None:
        return None
    root = audio_root()
    wav = root / f"{digest}.wav"
    sidecar = _sidecar_path(digest)
    if not wav.is_file() or not sidecar.is_file():
        return None
    if _is_expired(wav, time.time()):
        wav.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        return None
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict):
        return None
    stored = _normalize_hash(str(meta.get("audioHash", "")))
    if stored != digest:
        return None
    try:
        duration = float(meta.get("durationSec") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    return StudioAudioAsset(
        audio_hash=_display_hash(digest),
        path=wav,
        duration_sec=duration,
        meta=meta,
        cached=True,
    )


def cached_for_render(
    render_hash: str,
    params: Mapping[str, Any] | str | None = None,
) -> StudioAudioAsset | None:
    """Look up the WAV for one render without running MuseScore."""
    try:
        value = audio_hash_for(render_hash, params)
    except (ValueError, OSError):
        return None
    return load_audio(value)


def _meter_beats(meter: str | None) -> float:
    if isinstance(meter, str) and "/" in meter:
        beats_text, _, beat_type_text = meter.partition("/")
        try:
            beats = float(beats_text.strip())
            beat_type = float(beat_type_text.strip())
        except ValueError:
            return 4.0
        if beats > 0 and beat_type > 0:
            return beats * 4.0 / beat_type
    return 4.0


def _musical_seconds(bars: int | None, bpm: float | None, meter: str | None) -> float:
    if not bars or bars < 1:
        return 0.0
    return piece_seconds(int(bars), float(bpm or 120), _meter_beats(meter))


def _write_temp_xml(xml: str) -> Path:
    fd, name = tempfile.mkstemp(
        dir=audio_root(), prefix=".studio-render-", suffix=".musicxml"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(xml)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
    return Path(name)


def _classify_export_error(exc: BaseException) -> StudioAudioError:
    if isinstance(exc, StudioAudioError):
        return exc
    message = str(exc).strip() or type(exc).__name__
    lower = message.lower()
    if isinstance(exc, (FileNotFoundError, PermissionError)):
        return StudioAudioUnavailable(message)
    if "not installed" in lower or "no such file" in lower or "not found" in lower:
        return StudioAudioUnavailable(message)
    if "timed out" in lower or "timeout" in lower:
        return StudioAudioTimeout(message)
    if isinstance(exc, RecapUnavailable):
        return StudioAudioFailed(message[-400:])
    return StudioAudioFailed(f"{type(exc).__name__}: {message}"[-400:])


def render_studio_wav(
    score_or_xml: Score | str | bytes | Path,
    *,
    render_hash: str,
    params: Mapping[str, Any] | str | None = None,
    title: str = "",
    meter: str | None = None,
    bars: int | None = None,
    bpm: float | None = None,
    timeout_seconds: float | None = None,
) -> StudioAudioAsset:
    """Render (or reuse) one production WAV for a Studio Piece.

    ``score_or_xml`` is either a rendered :class:`Score`, the MusicXML text, or
    a path to a cached ``.musicxml``. The async job passes the cached path so a
    cache hit never recomposes or re-renders. Raises a coded
    :class:`StudioAudioError` on failure; there is no synth fallback.
    """
    digest = _normalize_hash(render_hash)
    if digest is None:
        raise ValueError("renderHash must be 64 lowercase hex characters")
    display_render = _display_hash(digest)

    score = score_or_xml if isinstance(score_or_xml, Score) else None
    xml_path: Path | None = score_or_xml if isinstance(score_or_xml, Path) else None
    temporary_xml: Path | None = None
    xml_text: str | None = None
    musical = 0.0

    if score is not None:
        title = title or score.title
        bars = score.bars if bars is None else bars
        meter = meter or f"{score.beats}/{score.beat_type}"
        bpm = score.bpm if bpm is None else bpm
        musical = piece_seconds(score.bars, score.bpm, score.bar_beats)
        xml_text = score_to_musicxml(score)
        temporary_xml = _write_temp_xml(xml_text)
        xml_path = temporary_xml
    elif isinstance(score_or_xml, (str, bytes)):
        xml_text = (
            score_or_xml.decode("utf-8")
            if isinstance(score_or_xml, bytes)
            else score_or_xml
        )
        temporary_xml = _write_temp_xml(xml_text)
        xml_path = temporary_xml
    elif xml_path is None:
        raise StudioAudioFailed(
            "score_or_xml must be a Score, MusicXML text, or a .musicxml path"
        )
    else:
        try:
            xml_text = xml_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise StudioAudioUnavailable(str(exc)) from exc

    musical = musical or _musical_seconds(bars, bpm, meter)
    allowance = float(
        max(180, int(musical * 2) + 60) if timeout_seconds is None else timeout_seconds
    )

    audio_hash = audio_hash_for(display_render, params)
    audio_digest = _normalize_hash(audio_hash)
    assert audio_digest is not None
    cached = load_audio(audio_hash)
    if cached is not None:
        if temporary_xml is not None:
            temporary_xml.unlink(missing_ok=True)
        return cached

    wav_path = audio_root() / f"{audio_digest}.wav"
    sidecar = _sidecar_path(audio_digest)
    temp_wav: Path | None = None
    try:
        with _lock_for(audio_digest):
            cached = load_audio(audio_hash)
            if cached is not None:
                return cached
            with _SLOTS:
                assert xml_path is not None
                fd, name = tempfile.mkstemp(
                    dir=audio_root(), prefix=f".{audio_digest}.", suffix=".wav"
                )
                os.close(fd)
                temp_wav = Path(name)
                temp_wav.unlink(missing_ok=True)
                previous_timeout = getattr(sonify_audio._export_timeout, "seconds", None)
                sonify_audio._export_timeout.seconds = allowance
                started = time.monotonic()
                try:
                    _exporter()(xml_path, temp_wav)
                except Exception as exc:  # classify every export failure
                    raise _classify_export_error(exc) from exc
                finally:
                    sonify_audio._export_timeout.seconds = previous_timeout

                try:
                    size = temp_wav.stat().st_size
                except OSError as exc:
                    raise StudioAudioFailed(
                        "MuseScore did not write a WAV"
                    ) from exc
                if size < _MIN_WAV_BYTES:
                    raise StudioAudioFailed("MuseScore wrote an empty WAV")
                try:
                    duration, _peaks, _level = waveform_peaks_with_level(temp_wav)
                except RecapUnavailable as exc:
                    raise StudioAudioFailed(str(exc)) from exc
                except Exception as exc:  # malformed RIFF is a failure
                    raise StudioAudioFailed(
                        f"invalid WAV: {type(exc).__name__}: {exc}"
                    ) from exc
                if duration <= 0:
                    raise StudioAudioFailed("MuseScore wrote a zero-length WAV")

                os.replace(temp_wav, wav_path)
                temp_wav = None
                created = datetime.now(timezone.utc).isoformat(timespec="seconds")
                meta = {
                    "renderHash": display_render,
                    "audioHash": _display_hash(audio_digest),
                    "audioRevision": AUDIO_REVISION,
                    "durationSec": round(float(duration), 3),
                    "createdAt": created,
                    "title": title,
                    "meter": meter or "",
                    "bars": int(bars or 0),
                    "paramsHash": _params_token(params),
                    "musescoreVersion": musescore_version(),
                    "soundfontVersion": soundfont_version(),
                    "renderSec": round(time.monotonic() - started, 3),
                }
                _atomic_write(
                    sidecar,
                    json.dumps(meta, sort_keys=True, separators=(",", ":")).encode(
                        "utf-8"
                    ),
                )
                _prune()
                return StudioAudioAsset(
                    audio_hash=_display_hash(audio_digest),
                    path=wav_path,
                    duration_sec=float(duration),
                    meta=meta,
                    cached=False,
                )
    finally:
        if temp_wav is not None:
            temp_wav.unlink(missing_ok=True)
        if temporary_xml is not None:
            temporary_xml.unlink(missing_ok=True)
