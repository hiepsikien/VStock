"""Render a score to an audio file with MuseScore and remember it.

The first request for a symbol, session, variant, and candle count writes the
file. A later request for the same piece returns that file. A still-open
session is rendered again when new 1-minute candles arrive.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import wave
from array import array
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from app.sonify.form import BEATS_PER_BAR
from app.sonify.model import Bar, Variant
from app.sonify.musicxml import score_to_musicxml
from app.sonify.playback import piece_seconds
from app.sonify.render import render
from app.sonify.session import is_session_closed

logger = logging.getLogger(__name__)

# Bump when the score or the soundfont changes, so old files are not replayed.
RECAP_REVISION = "2"
PEAK_BUCKETS = 96

SOUNDFONT_CANDIDATES = (
    "/usr/share/sounds/sf3/MuseScore_General_Full.sf3",
    "/usr/share/sounds/sf3/MuseScore_General.sf3",
    "/usr/share/sounds/sf2/MuseScore_General.sf3",
)

MUSESCORE_BINARIES = ("mscore3", "musescore3", "mscore", "musescore", "MuseScore4")

# Homebrew's cask installs the app bundle and does not put a binary on PATH.
MAC_MUSESCORE_APPS = (
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
    "/Applications/MuseScore 4.app/Contents/MacOS/MuseScore4",
    "/Applications/MuseScore 3.app/Contents/MacOS/mscore",
    "/Applications/MuseScore.app/Contents/MacOS/mscore",
    "/opt/homebrew/bin/mscore",
    "/usr/local/bin/mscore",
)

ExportFn = Callable[[Path, Path], None]


class RecapUnavailable(RuntimeError):
    """MuseScore could not write an audio file."""


@dataclass(frozen=True)
class RecapAsset:
    symbol: str
    day: date
    variant: Variant
    audio_path: Path
    duration_sec: float
    map_duration_sec: float
    peaks: list[float]
    bar_count: int
    media_type: str

    @property
    def audio_url(self) -> str:
        return (
            f"/v1/stocks/{self.symbol}/sessions/{self.day.isoformat()}"
            f"/recap/audio?variant={self.variant}&v={self.bar_count}"
        )


def audio_root() -> Path:
    raw = os.environ.get("VSTOCK_AUDIO_DIR", "").strip()
    path = Path(raw) if raw else Path(__file__).resolve().parents[2] / "var" / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def general_soundfont() -> Path | None:
    """Muse's free General soundfont, when the package is installed."""
    configured = os.environ.get("MUSESCORE_SOUNDFONT", "").strip()
    candidates = (configured, *SOUNDFONT_CANDIDATES) if configured else SOUNDFONT_CANDIDATES
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    return None


def musescore_candidates() -> list[str]:
    configured = os.environ.get("MUSESCORE_BIN", "").strip()
    names = [configured] if configured else []
    names.extend(MUSESCORE_BINARIES)
    if sys.platform == "darwin":
        home = Path.home()
        names.extend(MAC_MUSESCORE_APPS)
        names.extend(
            str(home / relative)
            for relative in (
                "Applications/MuseScore 4.app/Contents/MacOS/mscore",
                "Applications/MuseScore 3.app/Contents/MacOS/mscore",
            )
        )
    return names


def resolve_executable(names: Iterable[str]) -> str | None:
    for name in names:
        if not name:
            continue
        path = Path(name)
        if path.is_absolute():
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
            continue
        found = shutil.which(name)
        if found:
            return found
    return None


def find_musescore() -> str | None:
    return resolve_executable(musescore_candidates())


def waveform_peaks(path: Path, buckets: int = PEAK_BUCKETS) -> tuple[float, list[float]]:
    """Duration and normalized peak envelope of a 16-bit PCM wav."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    duration = frames / rate if rate else 0.0
    if width != 2 or frames < 1 or channels < 1:
        return duration, [0.0] * buckets
    samples = array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    count = len(samples) // channels
    if count < 1:
        return duration, [0.0] * buckets
    peaks: list[float] = []
    loudest = 1
    for index in range(buckets):
        start = index * count // buckets
        end = max(start + 1, (index + 1) * count // buckets)
        stride = max(1, (end - start) // 64)
        local = 0
        for frame in range(start, end, stride):
            level = 0
            base = frame * channels
            for channel in range(channels):
                level += abs(int(samples[base + channel]))
            level //= channels
            if level > local:
                local = level
        if local > loudest:
            loudest = local
        peaks.append(float(local))
    return duration, [round(peak / loudest, 4) for peak in peaks]


def _media_type(path: Path) -> str:
    if path.suffix == ".m4a":
        return "audio/mp4"
    if path.suffix == ".wav":
        return "audio/wav"
    return "application/octet-stream"


def musescore_export(xml_path: Path, wav_path: Path) -> None:
    binary = find_musescore()
    if binary is None:
        raise RecapUnavailable("MuseScore is not installed")
    soundfont = general_soundfont()
    if soundfont is None:
        logger.warning(
            "MuseScore General soundfont is not installed; playback uses MuseScore's built-in font"
        )
    runtime = os.environ.get("XDG_RUNTIME_DIR", "/tmp/runtime-mscore")
    Path(runtime).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Linux servers have no display. On macOS this flag keeps MuseScore from exporting.
    if sys.platform.startswith("linux"):
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["XDG_RUNTIME_DIR"] = runtime
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    command = [binary, "-o", str(wav_path), str(xml_path)]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RecapUnavailable("MuseScore export timed out") from exc
    if completed.returncode != 0 or not wav_path.is_file() or wav_path.stat().st_size < 64:
        detail = (completed.stderr or completed.stdout or "MuseScore export failed").strip()
        raise RecapUnavailable(detail[-400:])


def _transcode_m4a(wav_path: Path, m4a_path: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(wav_path),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(m4a_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return completed.returncode == 0 and m4a_path.is_file() and m4a_path.stat().st_size > 64


class RecapStore:
    def __init__(self, root: Path | None = None, exporter: ExportFn | None = None) -> None:
        self.root = root or audio_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._exporter = exporter or musescore_export
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _stem(self, symbol: str, day: date, variant: Variant) -> str:
        return f"{symbol}_{day.isoformat()}_{variant}_{RECAP_REVISION}"

    def ensure(self, symbol: str, day: date, variant: Variant, bars: list[Bar]) -> RecapAsset:
        if not bars:
            raise ValueError("need at least one price bar")
        key = self._stem(symbol, day, variant)
        with self._lock(key):
            cached = self._read(symbol, day, variant, key)
            if cached is not None and cached.bar_count == len(bars):
                return cached
            return self._render(symbol, day, variant, bars, key)

    def _render(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        bars: list[Bar],
        key: str,
    ) -> RecapAsset:
        score = render(bars, title=f"{symbol} {day.isoformat()}", variant=variant)
        work = self.root / "work"
        work.mkdir(parents=True, exist_ok=True)
        xml_path = work / f"{key}.musicxml"
        wav_path = work / f"{key}.wav"
        xml_path.write_text(score_to_musicxml(score), encoding="utf-8")
        try:
            self._exporter(xml_path, wav_path)
            duration, peaks = waveform_peaks(wav_path)
            musical = piece_seconds(score.bars, score.bpm, BEATS_PER_BAR)
            if duration <= 0:
                duration = musical
            # MuseScore leaves a short release after the last note. The chart
            # follows the written piece, then rests on the close during that tail.
            map_duration = musical if 0 < musical <= duration else duration
            m4a_path = self.root / f"{key}.m4a"
            wav_final = self.root / f"{key}.wav"
            if _transcode_m4a(wav_path, m4a_path):
                audio_path = m4a_path
                wav_path.unlink(missing_ok=True)
                wav_final.unlink(missing_ok=True)
            else:
                wav_path.replace(wav_final)
                audio_path = wav_final
                m4a_path.unlink(missing_ok=True)
            payload = {
                "symbol": symbol,
                "date": day.isoformat(),
                "variant": variant,
                "durationSec": round(duration, 3),
                "mapDurationSec": round(map_duration, 3),
                "barCount": len(bars),
                "peaks": peaks,
                "audio": audio_path.name,
                "closed": is_session_closed(day),
            }
            meta_path = self.root / f"{key}.json"
            temporary = meta_path.with_suffix(".json.part")
            temporary.write_text(json.dumps(payload), encoding="utf-8")
            temporary.replace(meta_path)
            return self._asset(symbol, day, variant, audio_path, payload)
        finally:
            xml_path.unlink(missing_ok=True)

    def _read(self, symbol: str, day: date, variant: Variant, key: str) -> RecapAsset | None:
        meta_path = self.root / f"{key}.json"
        if not meta_path.is_file():
            return None
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        name = str(payload.get("audio") or "")
        audio_path = self.root / name
        if not name or not audio_path.is_file():
            return None
        return self._asset(symbol, day, variant, audio_path, payload)

    def _asset(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        audio_path: Path,
        payload: dict,
    ) -> RecapAsset:
        peaks = payload.get("peaks") or []
        return RecapAsset(
            symbol=symbol,
            day=day,
            variant=variant,
            audio_path=audio_path,
            duration_sec=float(payload.get("durationSec") or 0.0),
            map_duration_sec=float(payload.get("mapDurationSec") or payload.get("durationSec") or 0.0),
            peaks=[float(peak) for peak in peaks],
            bar_count=int(payload.get("barCount") or 0),
            media_type=_media_type(audio_path),
        )


_store: RecapStore | None = None


def recap_store() -> RecapStore:
    global _store
    if _store is None:
        _store = RecapStore()
    return _store
