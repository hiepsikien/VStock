"""Short deterministic audio preview for a Studio sentence spec.

This is deliberately **not** the MuseScore export path. A preview already
returns bounded note events (`app.studio.preview`), so this module turns those
events into a small mono WAV with a fixed, code-only instrument: a decaying
harmonic tone per note, a fixed preview tempo, and a fixed sample rate. There
is no soundfont, no export queue, and no subprocess.

Cache
-----
Files live under ``VSTOCK_STUDIO_AUDIO_DIR`` (default ``backend/var/studio-audio``)
and are named by a 64-character SHA-256 key::

    sha256(f"{SYNTH_VERSION}|{SAMPLE_RATE}|{PREVIEW_BPM}|{beats_per_bar}|{render_hash}")

The preview's ``renderHash`` is part of that key, so changing the notes,
plan or row invalidates the audio. A sidecar ``.json`` records the render
hash, tempo, and duration; it lets a request that only knows the render hash
find an already synthesized file. Old files are pruned by age and by a small
file cap before a new file is written.

The preview tempo is fixed instead of read from the fixture's ``bpm``. The
render hash covers plan/row/notes only, so keeping tempo out of the synthesis
is what makes a cached file addressable by ``renderHash`` alone.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
import weakref
from array import array
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.sonify.audio import write_wav
from app.sonify.form import (
    METER_14,
    METER_24,
    METER_34,
    METER_44,
    METER_68,
)
from app.sonify.sentence_specs import METER_ANY, SentenceSpec

# Bump when the instrument or the mixing changes; old files stop being served.
SYNTH_VERSION = "studio-preview-1"
SAMPLE_RATE = 22050
PREVIEW_BPM = 96.0
MAX_AUDIO_SEC = 45.0
MAX_NOTES = 4096
TAIL_SEC = 0.5
ATTACK_SEC = 0.006
RELEASE_SEC = 0.08
HARMONICS = (1.0, 0.42, 0.20, 0.09)
VOICE_GAIN = {1: 1.0, 2: 0.55, 3: 0.72}
MAX_CACHE_FILES = max(1, int(os.environ.get("VSTOCK_STUDIO_AUDIO_MAX_FILES", "64")))
MAX_CACHE_AGE_DAYS = max(
    1, int(os.environ.get("VSTOCK_STUDIO_AUDIO_MAX_AGE_DAYS", "7"))
)
MAX_CONCURRENCY = max(1, int(os.environ.get("VSTOCK_STUDIO_AUDIO_SLOTS", "2")))
_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENCY)

_METER_BEATS = {
    "1/4": int(METER_14.quarter_beats),
    "2/4": int(METER_24.quarter_beats),
    "3/4": int(METER_34.quarter_beats),
    "4/4": int(METER_44.quarter_beats),
    "6/8": int(METER_68.quarter_beats),
}
_SUPPORTED_BEATS_PER_BAR = frozenset(_METER_BEATS.values())
_RENDER_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_AUDIO_NAME = re.compile(r"^[0-9a-f]{64}\.wav$")
_URL = "/v1/studio/sentence/audio/{name}"

_LOCKS: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()


class AudioUnavailable(ValueError):
    """The preview notes cannot become a bounded WAV."""


@dataclass(frozen=True)
class AudioAsset:
    """One synthesized preview file."""

    key: str
    path: Path
    duration_sec: float
    render_hash: str

    @property
    def audio_url(self) -> str:
        return _URL.format(name=f"{self.key}.wav")


@dataclass(frozen=True)
class AudioResult:
    """Raw audio result. The router owns the HTTP/JSON spelling."""

    ok: bool
    errors: tuple[tuple[str, str], ...] = ()
    asset: AudioAsset | None = None
    render_hash: str | None = None


# ---------------------------------------------------------------------------
# storage


def audio_root() -> Path:
    raw = os.environ.get("VSTOCK_STUDIO_AUDIO_DIR", "").strip()
    path = (
        Path(raw)
        if raw
        else Path(__file__).resolve().parents[2] / "var" / "studio-audio"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_path(name: str) -> Path | None:
    """Resolve one served name. Only a key WAV can be addressed."""
    if not _AUDIO_NAME.match(name):
        return None
    return audio_root() / name


def cache_key(render_hash: str, beats_per_bar: int) -> str:
    payload = (
        f"{SYNTH_VERSION}|{SAMPLE_RATE}|{PREVIEW_BPM}|{beats_per_bar}|{render_hash}"
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _lock_for(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _prune(root: Path) -> None:
    """Drop expired files and keep the newest ``MAX_CACHE_FILES`` WAVs."""
    cutoff = time.time() - MAX_CACHE_AGE_DAYS * 86400
    entries: list[tuple[float, Path]] = []
    for path in root.glob("*.wav"):
        if not _AUDIO_NAME.match(path.name):
            continue
        try:
            modified = path.stat().st_mtime
        except OSError:
            continue
        if modified < cutoff:
            path.unlink(missing_ok=True)
            path.with_suffix(".json").unlink(missing_ok=True)
            continue
        entries.append((modified, path))
    entries.sort()
    for _modified, path in entries[: max(0, len(entries) - MAX_CACHE_FILES)]:
        path.unlink(missing_ok=True)
        path.with_suffix(".json").unlink(missing_ok=True)
    # A crash between the WAV and sidecar writes leaves an orphan sidecar.
    for path in root.glob("*.json"):
        if not _AUDIO_NAME.match(path.with_suffix(".wav").name):
            path.unlink(missing_ok=True)


def _read_audio(root: Path, key: str, render_hash: str) -> AudioAsset | None:
    wav = root / f"{key}.wav"
    meta = root / f"{key}.json"
    if not wav.is_file() or not meta.is_file():
        return None
    try:
        payload = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("synthVersion") != SYNTH_VERSION
        or payload.get("renderHash") != render_hash
        or payload.get("key") != key
    ):
        return None
    duration = float(payload.get("durationSec") or 0.0)
    if duration <= 0.0 or duration > MAX_AUDIO_SEC:
        return None
    return AudioAsset(key=key, path=wav, duration_sec=duration, render_hash=render_hash)


def _write_audio(
    root: Path,
    key: str,
    render_hash: str,
    beats_per_bar: int,
    samples: array,
    duration_sec: float,
) -> AudioAsset:
    wav = root / f"{key}.wav"
    meta = root / f"{key}.json"
    token = f"{os.getpid()}-{threading.get_ident()}"
    wav_tmp = root / f".{key}.{token}.wav.tmp"
    meta_tmp = root / f".{key}.{token}.json.tmp"
    try:
        write_wav(wav_tmp, 1, SAMPLE_RATE, samples)
        wav_tmp.replace(wav)
        payload = {
            "durationSec": round(duration_sec, 6),
            "beatsPerBar": beats_per_bar,
            "key": key,
            "renderHash": render_hash,
            "sampleRate": SAMPLE_RATE,
            "synthVersion": SYNTH_VERSION,
        }
        meta_tmp.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        meta_tmp.replace(meta)
    finally:
        wav_tmp.unlink(missing_ok=True)
        meta_tmp.unlink(missing_ok=True)
    return AudioAsset(
        key=key, path=wav, duration_sec=round(duration_sec, 6), render_hash=render_hash
    )


# ---------------------------------------------------------------------------
# synthesis


def _frequency(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _note_gain(note: Mapping[str, Any]) -> float:
    velocity = note.get("velocity")
    level = 64 if velocity is None else int(velocity)
    gain = max(0.0, min(127, level)) / 127.0
    gain *= VOICE_GAIN.get(int(note.get("voice") or 1), 1.0)
    if note.get("accent"):
        gain *= 1.18
    return gain


def _synthesize_pcm(
    notes: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    beats_per_bar: int,
) -> tuple[array, float]:
    """Mix bounded notes into mono 16-bit samples. Deterministic for an input."""
    if not notes:
        raise AudioUnavailable("the preview has no notes to synthesize")
    if len(notes) > MAX_NOTES:
        raise AudioUnavailable(f"the preview has too many notes (max {MAX_NOTES})")

    seconds_per_beat = 60.0 / PREVIEW_BPM
    end_beat = max(
        float(note["bar"]) * beats_per_bar
        + float(note["beat"])
        + max(0.0, float(note["duration"]))
        for note in notes
    )
    duration_sec = end_beat * seconds_per_beat + TAIL_SEC
    if duration_sec > MAX_AUDIO_SEC:
        raise AudioUnavailable(
            f"the preview is longer than the {MAX_AUDIO_SEC:.0f}s audio cap"
        )
    frames = max(1, int(math.ceil(duration_sec * SAMPLE_RATE)))
    duration_sec = frames / SAMPLE_RATE
    mixed = [0.0] * frames

    harmonic_total = sum(HARMONICS)
    for note in notes:
        midi = note.get("midi")
        if midi is None:
            continue
        start = (
            float(note["bar"]) * beats_per_bar + float(note["beat"])
        ) * seconds_per_beat
        gate = max(
            0.02,
            float(note["duration"]) * seconds_per_beat
            * (0.55 if note.get("staccato") else 1.0),
        )
        first = max(0, int(round(start * SAMPLE_RATE)))
        if first >= frames:
            continue
        length = max(1, int(round((gate + RELEASE_SEC) * SAMPLE_RATE)))
        last = min(frames, first + length)
        frequency = _frequency(int(midi))
        gain = _note_gain(note)
        if gain <= 0.0:
            continue
        attack = max(1, int(round(ATTACK_SEC * SAMPLE_RATE)))
        release = max(1, int(round(RELEASE_SEC * SAMPLE_RATE)))
        decay_tau = max(0.08, gate * 0.9)
        angular = 2.0 * math.pi * frequency / SAMPLE_RATE
        for offset in range(last - first):
            t = offset / SAMPLE_RATE
            if offset < attack:
                envelope = offset / attack
            else:
                envelope = math.exp(-2.8 * t / decay_tau)
            if t > gate:
                envelope *= max(0.0, 1.0 - (t - gate) / RELEASE_SEC)
            if envelope <= 0.0:
                if offset > release:
                    break
                continue
            tone = 0.0
            for harmonic, weight in enumerate(HARMONICS, start=1):
                tone += weight * math.sin(angular * harmonic * offset)
            mixed[first + offset] += gain * envelope * tone / harmonic_total

    peak = max(abs(value) for value in mixed)
    scale = 0.85 / peak if peak > 0.85 else 1.0
    samples = array("h")
    for value in mixed:
        scaled = max(-1.0, min(1.0, value * scale))
        samples.append(max(-32768, min(32767, int(round(scaled * 32767.0)))))
    return samples, duration_sec


# ---------------------------------------------------------------------------
# public entry points


def ensure_audio(
    render_hash: str,
    notes: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    beats_per_bar: int,
) -> AudioAsset:
    """Return the cached WAV for these notes, synthesizing it once if needed."""
    if not _RENDER_HASH.match(render_hash):
        raise AudioUnavailable("renderHash must be sha256:<64 lowercase hex>")
    if beats_per_bar not in _SUPPORTED_BEATS_PER_BAR:
        raise AudioUnavailable("beats per bar must be 1, 2, 3, or 4")
    root = audio_root()
    key = cache_key(render_hash, beats_per_bar)
    with _lock_for(key):
        cached = _read_audio(root, key, render_hash)
        if cached is not None:
            return cached
        _prune(root)
        samples, duration_sec = _synthesize_pcm(notes, beats_per_bar)
        return _write_audio(
            root, key, render_hash, beats_per_bar, samples, duration_sec
        )


def cached_audio(render_hash: str) -> AudioAsset | None:
    """Find an already synthesized file for one render hash, newest first."""
    if not _RENDER_HASH.match(render_hash):
        return None
    root = audio_root()
    _prune(root)
    found: list[tuple[float, AudioAsset]] = []
    for meta in root.glob("*.json"):
        wav = meta.with_suffix(".wav")
        if not wav.is_file():
            continue
        try:
            payload = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            not isinstance(payload, dict)
            or payload.get("renderHash") != render_hash
            or payload.get("synthVersion") != SYNTH_VERSION
        ):
            continue
        duration = float(payload.get("durationSec") or 0.0)
        key = str(payload.get("key") or wav.stem)
        if duration <= 0.0 or duration > MAX_AUDIO_SEC or not _AUDIO_NAME.match(wav.name):
            continue
        try:
            modified = wav.stat().st_mtime
        except OSError:
            continue
        found.append(
            (
                modified,
                AudioAsset(
                    key=key,
                    path=wav,
                    duration_sec=round(duration, 6),
                    render_hash=render_hash,
                ),
            )
        )
    if not found:
        return None
    found.sort(key=lambda item: item[0], reverse=True)
    return found[0][1]


def beats_per_bar(spec: SentenceSpec, fixture: Mapping[str, Any] | None) -> int:
    """The meter's bar length in quarter notes, mirroring the preview default."""
    supplied = fixture or {}
    meter = supplied.get("meter", spec.meter if spec.meter != METER_ANY else "4/4")
    value = _METER_BEATS.get(str(meter))
    if value is None:
        raise AudioUnavailable(f"meter {meter!r} is not renderable")
    return value


def preview_audio(
    spec: SentenceSpec,
    fixture: Mapping[str, Any] | None = None,
    family: str | None = None,
) -> AudioResult:
    """Validate/render a preview and return its cached short WAV.

    `family` is the draft-only override forwarded to `dispatch`; production
    callers omit it and keep the pattern-derived family.
    """
    from app.studio import dispatch

    result = dispatch.preview_sentence(spec, fixture, family=family)
    if not result.ok or result.render_hash is None:
        return AudioResult(
            ok=False,
            errors=tuple((error.path, error.message) for error in result.errors),
            render_hash=result.render_hash,
        )
    if not _SLOTS.acquire(blocking=False):
        return AudioResult(
            ok=False,
            errors=(("audio", "preview audio is busy; retry"),),
            render_hash=result.render_hash,
        )
    try:
        meter_beats = beats_per_bar(spec, fixture)
        asset = ensure_audio(result.render_hash, result.notes, meter_beats)
    except AudioUnavailable as exc:
        return AudioResult(
            ok=False,
            errors=(("audio", str(exc)),),
            render_hash=result.render_hash,
        )
    finally:
        _SLOTS.release()
    return AudioResult(ok=True, asset=asset, render_hash=result.render_hash)


def audio_for_hash(render_hash: str) -> AudioResult:
    """Serve a cached file when the caller only has a preview render hash."""
    if not _RENDER_HASH.match(render_hash):
        return AudioResult(
            ok=False,
            errors=(("renderHash", "renderHash must be sha256:<64 lowercase hex>"),),
        )
    asset = cached_audio(render_hash)
    if asset is None:
        return AudioResult(
            ok=False,
            errors=(
                (
                    "renderHash",
                    "no cached preview audio for that renderHash; send spec and fixture",
                ),
            ),
            render_hash=render_hash,
        )
    return AudioResult(ok=True, asset=asset, render_hash=render_hash)


__all__ = [
    "AudioAsset",
    "AudioResult",
    "AudioUnavailable",
    "MAX_AUDIO_SEC",
    "PREVIEW_BPM",
    "SAMPLE_RATE",
    "SYNTH_VERSION",
    "audio_for_hash",
    "audio_path",
    "audio_root",
    "beats_per_bar",
    "cache_key",
    "cached_audio",
    "ensure_audio",
    "preview_audio",
]
