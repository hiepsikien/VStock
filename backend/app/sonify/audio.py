"""Render a score to an audio file with MuseScore and remember it.

The first request for a symbol, session, variant, and candle count writes the
file. A later request for the same piece returns that file. A still-open
session is rendered again when new 1-minute candles arrive.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import threading
import time
import zipfile
from array import array
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, NamedTuple
from xml.etree import ElementTree as ET

from app.sonify.ensemble import Ensemble
from app.sonify.model import ENSEMBLES, VARIANTS, Bar, Variant
from app.sonify.musicxml import score_to_musicxml
from app.sonify.playback import piece_seconds
from app.sonify.render import render
from app.sonify.session import VN, is_session_closed

logger = logging.getLogger(__name__)

# Bump when the score or the sound changes, so old files are not replayed.
RECAP_REVISION = "58"
# Long-form files live beside the daily recap and use their own revision.
SPAN_REVISION = "44"
PEAK_BUCKETS = 96
# One MuseScore at a time on the 2-vCPU API. Extra Listen presses wait.
EXPORT_SLOTS = max(1, int(os.environ.get("VSTOCK_MUSESCORE_SLOTS", "1")))
AUDIO_MAX_AGE_DAYS = max(1, int(os.environ.get("VSTOCK_AUDIO_MAX_AGE_DAYS", "30")))
# Export temps under work/ outlive a crashed MuseScore. A live export is at most
# the 180s deadline, so anything older than this is leftover.
WORK_KEEP_SEC = 15 * 60
_STORED_NAME = re.compile(
    r"^[A-Z0-9]+_\d{4}-\d{2}-\d{2}_(?:"
    + "|".join(VARIANTS)
    + r")(?:-(?:"
    + "|".join(name for name in ENSEMBLES if name != "classic")
    + r"))?_(?P<rev>[^_]+)_\d+\.(?:m4a|wav|json)$"
)
_export_cancel = threading.local()
_export_timeout = threading.local()
_config_folder_support: dict[str, bool] = {}

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


class RecapCancelled(RuntimeError):
    """The client went away before MuseScore finished."""


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
    ensemble: Ensemble = "classic"
    character: str | None = None
    key_label: str = ""

    @property
    def audio_url(self) -> str:
        extra = "" if self.ensemble == "classic" else f"&ensemble={self.ensemble}"
        return (
            f"/v1/stocks/{self.symbol}/sessions/{self.day.isoformat()}"
            f"/recap/audio.m4a?variant={self.variant}&v={self.bar_count}&r={RECAP_REVISION}{extra}"
        )


@dataclass(frozen=True)
class SpanAsset:
    symbol: str
    span: str
    index: int
    variant: Variant
    audio_path: Path
    duration_sec: float
    map_duration_sec: float
    peaks: list[float]
    bar_count: int
    media_type: str
    fingerprint: str


def write_wav(path: Path, channels: int, rate: int, samples: array) -> None:
    payload = samples.tobytes()
    bits = 16 if samples.typecode == "h" else 32
    block = channels * (bits // 8)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(payload),
        b"WAVE",
        b"fmt ",
        16,
        1 if bits == 16 else 3,
        channels,
        rate,
        rate * block,
        block,
        bits,
        b"data",
        len(payload),
    )
    path.write_bytes(header + payload)


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
    """Duration and normalized peak envelope of a WAV file.

    MuseScore 3 writes 16-bit integer samples. MuseScore 4 writes 32-bit float,
    which the stdlib ``wave`` reader rejects.
    """
    channels, rate, samples = _wav_samples(path)
    count = len(samples) // channels if channels else 0
    duration = count / rate if rate else 0.0
    if count < 1 or channels < 1:
        return duration, [0.0] * buckets
    peaks: list[float] = []
    loudest = 0.0
    for index in range(buckets):
        start = index * count // buckets
        end = max(start + 1, (index + 1) * count // buckets)
        stride = max(1, (end - start) // 64)
        local = 0.0
        for frame in range(start, end, stride):
            base = frame * channels
            level = 0.0
            for channel in range(channels):
                level += abs(float(samples[base + channel]))
            level /= channels
            if level > local:
                local = level
        if local > loudest:
            loudest = local
        peaks.append(local)
    if loudest <= 0:
        return duration, [0.0] * buckets
    return duration, [round(peak / loudest, 4) for peak in peaks]


def join_chunks(
    chunks: list[tuple[int, int, array]],
    musical_seconds: list[float],
    crossfade_seconds: float = 0.015,
) -> tuple[int, int, array]:
    """Trim every chunk but the last to the written length, then overlap the joins.

    The live movement export does not call this. It writes one MuseScore file
    per movement. This stays for a sliced export: mid-file tails are dropped,
    the last tail is kept, and 32-bit float samples are mixed as floats.
    """
    if not chunks or len(chunks) != len(musical_seconds):
        raise ValueError("each chunk needs a written length")
    channels, rate, _samples = chunks[0]
    if channels < 1 or rate < 1:
        raise ValueError("chunks need a sample rate")
    if any(item_channels != channels or item_rate != rate for item_channels, item_rate, _item in chunks):
        raise ValueError("chunks must share a sample rate and channel count")
    fade = max(0, round(crossfade_seconds * rate))
    frame = channels

    def frames_of(samples: array) -> int:
        return len(samples) // frame

    trimmed: list[array] = []
    for index, ((_item_channels, _item_rate, samples), seconds) in enumerate(zip(chunks, musical_seconds)):
        keep = frames_of(samples)
        if index != len(chunks) - 1:
            keep = min(keep, max(1, round(seconds * rate)))
        trimmed.append(array(samples.typecode, samples[: keep * frame]))

    if len(trimmed) == 1 or fade == 0:
        joined: array = array(trimmed[0].typecode)
        for part in trimmed:
            joined.extend(part)
        return channels, rate, joined

    joined = array(trimmed[0].typecode)
    for index, part in enumerate(trimmed):
        if index == 0:
            joined.extend(part)
            continue
        overlap = min(fade, frames_of(part), len(joined) // frame)
        if overlap <= 0:
            joined.extend(part)
            continue
        tail = len(joined) - overlap * frame
        for step in range(overlap):
            weight = (step + 1) / (overlap + 1)
            for channel in range(frame):
                position = tail + step * frame + channel
                incoming = part[step * frame + channel]
                mixed = joined[position] * (1.0 - weight) + incoming * weight
                if joined.typecode == "f":
                    joined[position] = mixed
                else:
                    joined[position] = max(-32768, min(32767, int(mixed)))
        joined.extend(part[overlap * frame :])
    return channels, rate, joined


def _wav_samples(path: Path) -> tuple[int, int, array]:
    data = path.read_bytes()
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return 0, 0, array("h")
    audio_format = 0
    channels = 0
    rate = 0
    bits = 0
    payload = b""
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        start = offset + 8
        body = data[start : start + size]
        if chunk_id == b"fmt " and len(body) >= 16:
            audio_format, channels, rate, _byte_rate, _align, bits = struct.unpack_from("<HHIIHH", body)
        elif chunk_id == b"data":
            payload = body
        offset = start + size + (size & 1)
    if audio_format == 1 and bits == 16:
        count = len(payload) // 2
        samples = array("h")
        samples.frombytes(payload[: count * 2])
        return channels, rate, samples
    if audio_format == 3 and bits == 32:
        count = len(payload) // 4
        samples = array("f")
        samples.frombytes(payload[: count * 4])
        return channels, rate, samples
    raise RecapUnavailable(f"unsupported wav format {audio_format} ({bits}-bit)")


def _media_type(path: Path) -> str:
    if path.suffix == ".m4a":
        return "audio/mp4"
    if path.suffix == ".wav":
        return "audio/wav"
    return "application/octet-stream"


def write_synthesizer_config(folder: Path, soundfont: Path) -> None:
    """Point a MuseScore 3 config directory at one Fluid soundfont.

    MuseScore matches the synthesizer entry by filename, and only looks in
    its install sound directory plus ``application/paths/mySoundfonts``.
    The ini entry adds the file's own directory so an absolute path is found.
    """
    folder.mkdir(parents=True, exist_ok=True)
    escaped = (
        str(soundfont)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    (folder / "synthesizer.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Synthesizer>\n"
        "  <Fluid>\n"
        f'    <val id="0">{escaped}</val>\n'
        "  </Fluid>\n"
        "</Synthesizer>\n",
        encoding="utf-8",
    )
    settings = folder / "MuseScore"
    settings.mkdir(parents=True, exist_ok=True)
    directory = str(soundfont.parent).replace("\n", "").replace("\r", "")
    (settings / "MuseScore3.ini").write_text(
        "[application]\n"
        f"paths\\mySoundfonts={directory}\n",
        encoding="utf-8",
    )


def _supports_config_folder(binary: str) -> bool:
    cached = _config_folder_support.get(binary)
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(
            [binary, "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        _config_folder_support[binary] = False
        return False
    supported = "--config-folder" in f"{completed.stdout}\n{completed.stderr}"
    _config_folder_support[binary] = supported
    return supported


def _raise_if_cancelled_event(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise RecapCancelled("export cancelled")


def _raise_if_cancelled() -> None:
    cancel = getattr(_export_cancel, "event", None)
    if isinstance(cancel, threading.Event) and cancel.is_set():
        raise RecapCancelled("export cancelled")


# MuseScore 4 mixes this playback click into a command-line export.
# ``--factory-settings`` also drops the click, but that process writes the
# empty factory file over the user's preferences when it exits.
_METRONOME_DOMAIN = "org.musescore.MuseScore4"
_METRONOME_KEY = "application.playback.metronomeEnabled"


def _silence_metronome() -> Callable[[], None]:
    """Turn MuseScore 4's playback click off and leave it off.

    A missing preference uses the app default, which shows the metronome as
    on. Restoring the old value after export turned that switch back on.
    """
    if sys.platform != "darwin":
        return lambda: None
    subprocess.run(
        ["defaults", "write", _METRONOME_DOMAIN, _METRONOME_KEY, "-bool", "false"],
        check=False,
        capture_output=True,
        text=True,
    )
    return lambda: None


class _MuseVoice(NamedTuple):
    """One recap instrument and the MuseSounds library voice that plays it."""

    instrument_ids: tuple[str, ...]
    xml_names: tuple[str, ...]
    sound: str


# MusicXML import names MuseScore writes into the score. Synths have no
# MuseSounds library, so they stay on MS Basic. Acoustic bass uses the
# installed electric bass: the libraries have no upright bass. Ambient
# voices are bowed or sung, because the GM pad programs decay after the attack.
_MUSE_VOICES = (
    _MuseVoice(("wind.flutes.flute",), ("Flute",), "Flute 1"),
    _MuseVoice(("wind.flutes.flute.alto",), ("Alto Flute",), "Alto Flute"),
    _MuseVoice(("wind.flutes.flute.bass",), ("Bass Flute",), "Bass Flute"),
    _MuseVoice(("strings.violin",), ("Violin",), "Violins 1"),
    _MuseVoice(("strings.cello", "strings.violoncello", "strings.baryton"), ("Cello",), "Cellos"),
    _MuseVoice(("strings.contrabass",), ("Contrabass",), "Contrabasses"),
    _MuseVoice(("keyboard.piano",), ("Piano",), "Piano"),
    _MuseVoice(("pluck.bass.electric",), ("Electric Bass (finger)",), "Electric Bass"),
    _MuseVoice(("pitched-percussion.vibraphone",), ("Vibraphone",), "Vibraphone"),
    _MuseVoice(("wind.reed.saxophone.alto",), ("Alto Sax",), "Alto Saxophone"),
    _MuseVoice(("wind.reed.saxophone.tenor",), ("Tenor Sax",), "Tenor Saxophone"),
    _MuseVoice(("keyboard.piano.electric",), ("Electric Piano 1",), "Suitcase Piano"),
    _MuseVoice(("pluck.bass.acoustic",), ("Acoustic Bass",), "Electric Bass"),
    _MuseVoice(
        ("pitched-percussion.celesta", "keyboard.celesta", "celesta"),
        ("Celesta",),
        "Celesta",
    ),
    _MuseVoice(("strings.viola",), ("Viola",), "Violas"),
    _MuseVoice(("pluck.harp",), ("Harp",), "Harp"),
    _MuseVoice(("brass.french-horn",), ("Horn in F",), "French Horn"),
    _MuseVoice(
        (
            "voice.vocals",
            "voice.soprano",
            "voice.mezzo-soprano",
            "voice.alto",
            "voice.baritone",
            "voice.child",
            "voice.female",
            "voice.male",
        ),
        ("Voice",),
        "Full Choir",
    ),
    _MuseVoice(("wind.flutes.flute.piccolo",), ("Piccolo",), "Piccolo"),
    _MuseVoice(("wind.reed.oboe",), ("Oboe",), "Oboe"),
    _MuseVoice(
        ("wind.reed.clarinet.bflat", "wind.reed.clarinet"),
        ("Clarinet",),
        "Clarinet in Bb",
    ),
    _MuseVoice(("wind.reed.contrabassoon",), ("Contrabassoon",), "Contrabassoon"),
    _MuseVoice(("pitched-percussion.glockenspiel",), ("Glockenspiel",), "Glockenspiel"),
    _MuseVoice(("brass.trumpet.bflat", "brass.trumpet", "brass.trumpet.c"), ("Trumpet",), "Trumpet"),
    _MuseVoice(("brass.trombone", "brass.trombone.tenor"), ("Trombone",), "Trombone"),
    _MuseVoice((), ("French Horns a6",), "French Horns a6"),
    _MuseVoice(("brass.tuba", "brass.tuba.bass"), ("Tuba",), "Tuba"),
    _MuseVoice((), ("Electric LP - Clean",), "Electric LP - Clean"),
    _MuseVoice((), ("Electric SC - Clean",), "Electric SC - Clean"),
    _MuseVoice((), ("Wurly 200A",), "Wurly 200A"),
    _MuseVoice(("wind.reed.saxophone.soprano",), ("Soprano Saxophone",), "Soprano Saxophone"),
    _MuseVoice(("wind.reed.saxophone.baritone",), ("Baritone Saxophone",), "Baritone Saxophone"),
    _MuseVoice(("keyboard.organ.drawbar",), ("Hammond Organ",), "Hammond Organ"),
    _MuseVoice(("metal.crotales",), ("Crotales",), "Crotales"),
    _MuseVoice(("pitched-percussion.marimba",), ("Marimba",), "Marimba"),
    _MuseVoice(("keyboard.harpsichord",), ("Harpsichord",), "Harpsichord"),
    _MuseVoice((), ("Flute 2",), "Flute 2"),
    _MuseVoice((), ("Acoustic Steel Plucked",), "Acoustic Steel Plucked"),
    _MuseVoice(
        ("pluck.guitar.nylon-string",),
        ("Classical Guitar", "Acoustic Nylon"),
        "Acoustic Nylon",
    ),
    _MuseVoice(("keyboard.piano.upright",), ("Upright Piano",), "Upright Piano"),
    _MuseVoice((), ("Handchimes",), "Handchimes"),
    _MuseVoice(("wind.reed.english-horn",), ("English Horn",), "English Horn"),
    _MuseVoice(("wind.reed.clarinet.bass",), ("Bass Clarinet",), "Bass Clarinet"),
    _MuseVoice((), ("Trombones a3",), "Trombones a3"),
    _MuseVoice(("pitched-percussion.handbells",), ("Hand Bells",), "Handbells"),
    _MuseVoice(("voice.tenor",), ("Tenor",), "Tenors"),
    _MuseVoice(("voice.bass",), ("Bass",), "Basses"),
)
_VOICE_BY_INSTRUMENT = {
    instrument_id: voice for voice in _MUSE_VOICES for instrument_id in voice.instrument_ids
}
_VOICE_BY_SOUND = {voice.sound: voice for voice in _MUSE_VOICES}
_muse_sounds_cache: dict[str, tuple[str, str]] | None = None


def _instruments_dir() -> Path | None:
    override = os.environ.get("MUSESOUNDS_DIR")
    if override:
        return Path(override)
    candidates = (
        Path.home() / "Library/Application Support/MuseSampler/.config",
        Path.home() / ".local/share/MuseSampler/.config",
    )
    for config in candidates:
        try:
            text = config.read_text(encoding="utf-8")
        except OSError:
            continue
        folder = Path(text.strip())
        if folder.is_dir():
            return folder
    return None


def _installed_muse_sounds() -> dict[str, tuple[str, str]]:
    """Library voice name to ``(sound id, pack name)`` for installed packs."""
    global _muse_sounds_cache
    if _muse_sounds_cache is not None:
        return _muse_sounds_cache
    folder = _instruments_dir()
    database = folder / ".instruments" if folder is not None else None
    found: dict[str, tuple[str, str]] = {}
    if database is not None and database.is_file():
        try:
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
                rows = connection.execute(
                    """
                    SELECT instruments.name, instruments.id, packages.name
                    FROM instruments
                    JOIN packages ON instruments.package_key = packages.key
                    WHERE instruments.state = 1
                    """
                )
                for name, sound_id, pack in rows:
                    # "Violins 1" is stored with a leading space.
                    found.setdefault(str(name).strip(), (str(sound_id), str(pack)))
        except sqlite3.Error as exc:
            logger.warning("MuseSounds library could not be read: %s", exc)
    _muse_sounds_cache = found
    return found


def _xml_requests_muse_sounds(xml_path: Path, library: dict[str, tuple[str, str]]) -> bool:
    try:
        text = xml_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(
        voice.sound in library
        and (
            f"<instrument-name>{name}</instrument-name>" in text
            or f"<part-name>{name}</part-name>" in text
        )
        for voice in _MUSE_VOICES
        for name in (*voice.xml_names, voice.sound)
    )


def _xml_part_sounds(xml_path: Path) -> list[str | None]:
    """MuseSounds voice requested by each score-part, in part-list order."""
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError):
        return []
    sounds: list[str | None] = []
    for part in root.findall("part-list/score-part"):
        part_name = (part.findtext("part-name") or "").strip()
        instrument_name = (part.findtext("score-instrument/instrument-name") or "").strip()
        if part_name in _VOICE_BY_SOUND:
            sounds.append(part_name)
        elif instrument_name in _VOICE_BY_SOUND:
            sounds.append(instrument_name)
        else:
            sounds.append(None)
    return sounds


def _score_parts(mscx: str) -> list[tuple[str, str, str]]:
    try:
        root = ET.fromstring(mscx)
    except ET.ParseError:
        return []
    parts: list[tuple[str, str, str]] = []
    for part in root.iter("Part"):
        part_id = part.get("id") or ""
        instrument = next(part.iter("Instrument"), None)
        if instrument is None:
            continue
        kind_node = instrument.find("instrumentId")
        kind = kind_node.text or "" if kind_node is not None else ""
        instrument_id = instrument.get("id") or ""
        if part_id and instrument_id and kind:
            parts.append((part_id, instrument_id, kind))
    return parts


_VOICE_VOLUME_DB: dict[str, float] = {
    "Flute 1": 5,
    "Glockenspiel": 10,
    "Crotales": 12,
    "Vibraphone": 3,
    "Electric LP - Clean": 4,
    "Electric SC - Clean": 4,
    "Celesta": 6,
    "Violins 1": 2,
    "Oboe": 6,
    "Trumpet": 6,
    "Clarinet in Bb": 3,
    "Marimba": 10,
    "Acoustic Steel Plucked": 8,
    "Acoustic Nylon": 6,
    "Cellos": 4,
    "Trombone": 8,
    "Full Choir": 8,
    "Tenors": 2,
    "Bass Flute": -5,
    "Piano": -2,
    "Harp": 8,
    "French Horns a6": -5,
    "Suitcase Piano": -2,
    "Violas": 3,
    "Electric Bass": -6,
    "Contrabassoon": 10,
    "Tuba": -5,
}
_HARMONY_BLOCK = re.compile(r"<Harmony\b[^>]*>.*?</Harmony>", re.DOTALL)


def _mute_mscx_harmony(mscx: bytes) -> bytes:
    """Stop MuseScore playing the hidden piano inside each <Harmony> chord symbol."""
    try:
        text = mscx.decode("utf-8")
    except UnicodeDecodeError:
        return mscx

    def mute(match: re.Match[str]) -> str:
        block = match.group(0)
        if "<play>" in block:
            return re.sub(r"<play>\s*[^<]*\s*</play>", "<play>0</play>", block)
        return block.replace("</Harmony>", "<play>0</play></Harmony>", 1)

    updated = _HARMONY_BLOCK.sub(mute, text)
    return updated.encode("utf-8") if updated != text else mscx


def _sound_track(
    part_id: str,
    instrument_id: str,
    resource_id: str,
    resource_type: str,
    vendor: str,
    attributes: dict[str, str],
    volume_db: float = 0,
) -> dict:
    return {
        "instrumentId": instrument_id,
        "partId": part_id,
        "soloMuteState": {"mute": False, "solo": False},
        "in": {
            "resourceMeta": {
                "id": resource_id,
                "type": resource_type,
                "vendor": vendor,
                "hasNativeEditorSupport": False,
                "attributes": attributes,
            },
            "unitConfiguration": {},
        },
        "out": {"balance": 0, "fxChain": {}, "volumeDb": volume_db},
    }


def _assign_installed_sounds(
    mscz: Path,
    library: dict[str, tuple[str, str]],
    xml_path: Path | None = None,
) -> bool:
    """Point each matching part at an installed MuseSounds voice.

    MuseScore 4's ``--sound-profile`` flag reports the voice it would use and
    still renders MS Basic. The sampler plays only when the score stores that
    voice's id in ``attributes.museUID``.
    """
    if not zipfile.is_zipfile(mscz):
        return False
    with zipfile.ZipFile(mscz) as archive:
        names = archive.namelist()
        mscx_name = next((name for name in names if name.endswith(".mscx")), None)
        if mscx_name is None or "audiosettings.json" not in names:
            return False
        parts = _score_parts(archive.read(mscx_name).decode("utf-8"))
        try:
            settings = json.loads(archive.read("audiosettings.json"))
        except json.JSONDecodeError:
            return False
        payloads = {name: archive.read(name) for name in names}
    requested = _xml_part_sounds(xml_path) if xml_path is not None else []
    tracks = []
    assigned: list[str] = []
    prepared_basic = False
    for index, (part_id, instrument_id, kind) in enumerate(parts):
        named = requested[index] if index < len(requested) else None
        voice = _VOICE_BY_SOUND.get(named) if named else None
        if voice is not None and voice.sound not in library:
            voice = None
        if voice is None:
            voice = _VOICE_BY_INSTRUMENT.get(kind)
        if voice is not None and voice.sound == "Acoustic Nylon":
            # MuseSounds nylon renders every note at the part's printed
            # dynamic and ignores per-note velocity (verified: opposite
            # velocities export byte-identical audio). The guitar balance
            # is written note by note, so this part stays on MS Basic,
            # where velocity actually speaks.
            tracks.append(
                _sound_track(
                    part_id,
                    instrument_id,
                    "MS Basic",
                    "fluid_soundfont",
                    "Fluid",
                    {"playbackSetupData": "last.last.last", "soundFontName": "MS Basic"},
                    volume_db=_VOICE_VOLUME_DB.get(voice.sound, 0),
                )
            )
            prepared_basic = True
            continue
        installed = library.get(voice.sound) if voice is not None else None
        if installed is None:
            tracks.append(
                _sound_track(
                    part_id,
                    instrument_id,
                    "MS Basic",
                    "fluid_soundfont",
                    "Fluid",
                    {"playbackSetupData": "last.last.last", "soundFontName": "MS Basic"},
                )
            )
            continue
        sound_id, pack = installed
        tracks.append(
            _sound_track(
                part_id,
                instrument_id,
                sound_id,
                "muse_sampler_sound_pack",
                "MuseSounds",
                {
                    "museUID": sound_id,
                    "museName": voice.sound,
                    "musePack": pack,
                    "museCategory": pack,
                    "museVendorName": "Muse",
                },
                volume_db=_VOICE_VOLUME_DB.get(voice.sound, 0),
            )
        )
        assigned.append(f"{kind} -> {voice.sound}")
    if not assigned and not prepared_basic:
        return False
    if not isinstance(settings, dict):
        settings = {}
    settings["activeSoundProfile"] = "MuseSounds" if assigned else "MS Basic"
    settings["tracks"] = tracks
    payloads["audiosettings.json"] = json.dumps(settings, indent=2).encode("utf-8")
    payloads[mscx_name] = _mute_mscx_harmony(payloads[mscx_name])
    temporary = mscz.with_suffix(".mscz.tmp")
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, payload in payloads.items():
                archive.writestr(name, payload)
        temporary.replace(mscz)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    logger.info(
        "MuseSounds assigned: %s",
        ", ".join(assigned) if assigned else "none (nylon guitar stays on MS Basic)",
    )
    return True


def _run_musescore(command: list[str], env: dict[str, str]) -> None:
    output = Path(command[command.index("-o") + 1])
    _raise_if_cancelled()
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except OSError as exc:
        raise RecapUnavailable(str(exc)) from exc
    allowance = getattr(_export_timeout, "seconds", None)
    deadline = time.monotonic() + (180 if allowance is None else allowance)
    stdout = ""
    stderr = ""
    try:
        while True:
            _raise_if_cancelled_killing(process)
            try:
                stdout, stderr = process.communicate(timeout=0.4)
                break
            except subprocess.TimeoutExpired:
                if time.monotonic() > deadline:
                    process.kill()
                    raise RecapUnavailable("MuseScore export timed out")
    finally:
        if process.poll() is None:
            process.kill()
    # Converting to mscz can crash while the process exits, after the score
    # has already been saved. A readable score is still worth using.
    saved = output.is_file() and output.stat().st_size >= 64
    if output.suffix == ".mscz" and saved and zipfile.is_zipfile(output):
        return
    if process.returncode != 0 or not saved:
        detail = (stderr or stdout or "MuseScore export failed").strip()
        raise RecapUnavailable(detail[-400:])


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
    source = xml_path
    mscz_path = wav_path.with_suffix(".mscz")
    config: Path | None = None
    use_config = soundfont is not None and _supports_config_folder(binary)
    library = {} if use_config else _installed_muse_sounds()
    command = [binary, "-o", str(wav_path), str(source)]
    if use_config:
        config = wav_path.parent / f"{wav_path.stem}-mscore"
        write_synthesizer_config(config, soundfont)
        command = [binary, "-c", str(config), "-o", str(wav_path), str(xml_path)]
    elif soundfont is not None:
        logger.warning(
            "MuseScore at %s has no --config-folder, so MUSESCORE_SOUNDFONT is not applied",
            binary,
        )
    restore_metronome = _silence_metronome()
    try:
        if library and _xml_requests_muse_sounds(xml_path, library):
            try:
                _run_musescore([binary, "-o", str(mscz_path), str(xml_path)], env)
                if _assign_installed_sounds(mscz_path, library, xml_path):
                    source = mscz_path
                    command = [binary, "-o", str(wav_path), str(source)]
            except RecapUnavailable as exc:
                logger.warning("MuseSounds prepare failed; exporting with MS Basic: %s", exc)
                source = xml_path
                command = [binary, "-o", str(wav_path), str(source)]
        try:
            _run_musescore(command, env)
        finally:
            if config is not None:
                shutil.rmtree(config, ignore_errors=True)
    finally:
        mscz_path.unlink(missing_ok=True)
        mscz_path.with_suffix(".mscz.tmp").unlink(missing_ok=True)
        restore_metronome()


def _raise_if_cancelled_killing(process: subprocess.Popen[str]) -> None:
    cancel = getattr(_export_cancel, "event", None)
    if isinstance(cancel, threading.Event) and cancel.is_set():
        process.kill()
        raise RecapCancelled("export cancelled")


# Dry MS Basic nylon. A short high shelf, three early reflections, and a
# slight widening stand in for the glass of a cathedral dome.
_GUITAR_HALL = "highshelf=f=4200:g=2.5,aecho=0.88:0.82:38|67|105:0.20|0.14|0.09,extrastereo=m=1.18"


def _ffmpeg_aac(ffmpeg: str, wav_path: Path, m4a_path: Path, audio_filter: str | None) -> bool:
    command = [ffmpeg, "-y", "-i", str(wav_path)]
    if audio_filter:
        command.extend(["-af", audio_filter])
    command.extend(["-c:a", "aac", "-b:a", "160k", str(m4a_path)])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and m4a_path.is_file() and m4a_path.stat().st_size > 64


def _transcode_m4a(wav_path: Path, m4a_path: Path, *, variant: str | None = None) -> bool:
    del variant
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return False
    return _ffmpeg_aac(ffmpeg, wav_path, m4a_path, None)


class RecapStore:
    def __init__(
        self,
        root: Path | None = None,
        exporter: ExportFn | None = None,
        *,
        slots: int | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.root = root or audio_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self._exporter = exporter or musescore_export
        self._slots = threading.BoundedSemaphore(EXPORT_SLOTS if slots is None else max(1, slots))
        self._clock = clock or (lambda: datetime.now(VN))
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _tag(self, variant: Variant, ensemble: Ensemble) -> str:
        if ensemble == "classic":
            return variant
        return f"{variant}-{ensemble}"

    def _piece(self, symbol: str, day: date, variant: Variant, ensemble: Ensemble = "classic") -> str:
        return f"{symbol}_{day.isoformat()}_{self._tag(variant, ensemble)}"

    def _stem(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        bar_count: int,
        ensemble: Ensemble = "classic",
    ) -> str:
        return f"{self._piece(symbol, day, variant, ensemble)}_{RECAP_REVISION}_{bar_count}"

    def _is_closed(self, day: date) -> bool:
        return is_session_closed(day, self._clock())

    def get(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        bar_count: int,
        ensemble: Ensemble = "classic",
    ) -> RecapAsset | None:
        """Serve one finished file. Does not compose."""
        self.prune()
        return self._read(symbol, day, variant, self._stem(symbol, day, variant, bar_count, ensemble))

    def ensure(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        bars: list[Bar],
        cancel: threading.Event | None = None,
        ensemble: Ensemble = "classic",
    ) -> RecapAsset:
        if not bars:
            raise ValueError("need at least one price bar")
        self.prune()
        piece = self._piece(symbol, day, variant, ensemble)
        with self._lock(piece):
            _raise_if_cancelled_event(cancel)
            cached = self._cached(symbol, day, variant, len(bars), ensemble)
            if cached is not None:
                return cached
            _raise_if_cancelled_event(cancel)
            with self._slots:
                _raise_if_cancelled_event(cancel)
                cached = self._cached(symbol, day, variant, len(bars), ensemble)
                if cached is not None:
                    return cached
                return self._render(symbol, day, variant, bars, cancel, ensemble)

    def prune(self) -> None:
        """Drop other score revisions, expired files, and leftover export temps."""
        cutoff = time.time() - AUDIO_MAX_AGE_DAYS * 86400
        for path in list(self.root.iterdir()):
            if path.is_dir():
                if path.name == "work":
                    self._prune_work(path)
                elif path.name == "spans":
                    self._prune_spans(path, cutoff)
                continue
            if not path.is_file():
                continue
            match = _STORED_NAME.match(path.name)
            current = match is not None and match.group("rev") == RECAP_REVISION
            try:
                expired = path.stat().st_mtime < cutoff
            except OSError:
                continue
            if not current or expired:
                path.unlink(missing_ok=True)

    def _prune_spans(self, spans: Path, cutoff: float) -> None:
        for path in list(spans.iterdir()):
            try:
                expired = path.stat().st_mtime < cutoff
            except OSError:
                continue
            current = any(
                f"_{variant}_{SPAN_REVISION}_" in path.name
                or any(
                    f"_{variant}_{ensemble}_{SPAN_REVISION}_" in path.name
                    for ensemble in ENSEMBLES
                    if ensemble != "classic"
                )
                for variant in VARIANTS
            )
            if not current or expired:
                path.unlink(missing_ok=True)

    def _span_dir(self) -> Path:
        folder = self.root / "spans"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _span_stem(
        self,
        symbol: str,
        span: str,
        index: int,
        variant: Variant,
        candle_count: int,
        fingerprint: str,
        ensemble: Ensemble = "classic",
    ) -> str:
        token = fingerprint.replace(".", "p").replace("-", "_")
        marker = variant if ensemble == "classic" else f"{variant}_{ensemble}"
        return f"{symbol}_{span}_{index}_{marker}_{SPAN_REVISION}_{candle_count}_{token}"

    def get_movement(
        self,
        symbol: str,
        span: str,
        index: int,
        variant: Variant,
        candle_count: int,
        fingerprint: str,
        ensemble: Ensemble = "classic",
    ) -> SpanAsset | None:
        self.prune()
        stem = self._span_stem(symbol, span, index, variant, candle_count, fingerprint, ensemble)
        return self._read_span(symbol, span, index, variant, stem, fingerprint)

    def ensure_movement(
        self,
        symbol: str,
        span: str,
        index: int,
        variant: Variant,
        movement,  # PreparedMovement; kept untyped to avoid an import cycle
        cancel: threading.Event | None = None,
        ensemble: Ensemble = "classic",
    ) -> SpanAsset:
        fingerprint = movement.scale_fingerprint
        candle_count = movement.candle_count
        piece = f"span:{symbol}:{span}:{index}:{self._tag(variant, ensemble)}"
        with self._lock(piece):
            _raise_if_cancelled_event(cancel)
            cached = self.get_movement(
                symbol, span, index, variant, candle_count, fingerprint, ensemble
            )
            if cached is not None:
                return cached
            with self._slots:
                _raise_if_cancelled_event(cancel)
                cached = self.get_movement(
                    symbol, span, index, variant, candle_count, fingerprint, ensemble
                )
                if cached is not None:
                    return cached
                return self._render_movement(symbol, span, index, variant, movement, cancel, ensemble)

    def _render_movement(
        self,
        symbol: str,
        span: str,
        index: int,
        variant: Variant,
        movement,
        cancel: threading.Event | None,
        ensemble: Ensemble = "classic",
    ) -> SpanAsset:
        stem = self._span_stem(
            symbol,
            span,
            index,
            variant,
            movement.candle_count,
            movement.scale_fingerprint,
            ensemble,
        )
        score = render(
            movement.bars,
            title=f"{symbol} {span} {movement.label}",
            variant=variant,
            form=movement.spec,
            source_groups=movement.groups,
            key=movement.key,
            character=movement.character,
            outro_override=movement.outro_override,
            framed=False,
            mode=movement.mode,
            home_pedal=movement.home_pedal,
            character_at=movement.bar_characters,
            gap_leads=movement.gap_leads,
            ensemble=ensemble,
        )
        work = self.root / "work"
        work.mkdir(parents=True, exist_ok=True)
        xml_path = work / f"{stem}.musicxml"
        wav_path = work / f"{stem}.wav"
        xml_path.write_text(score_to_musicxml(score), encoding="utf-8")
        musical = piece_seconds(score.bars, score.bpm, score.bar_beats)
        previous = getattr(_export_cancel, "event", None)
        previous_timeout = getattr(_export_timeout, "seconds", None)
        _export_cancel.event = cancel
        # A week is several minutes of audio. One MuseScore launch writes the
        # whole movement; slicing it would open the Mac app once per session.
        _export_timeout.seconds = max(180, int(musical * 2) + 60)
        try:
            _raise_if_cancelled_event(cancel)
            self._exporter(xml_path, wav_path)
            if not wav_path.is_file() or wav_path.stat().st_size < 64:
                raise RecapUnavailable("MuseScore wrote an empty movement")
            duration, peaks = waveform_peaks(wav_path)
            if duration <= 0:
                duration = musical
            map_duration = musical if 0 < musical <= duration else duration
            joined_path = wav_path
            m4a_tmp = work / f"{stem}.m4a"
            if _transcode_m4a(joined_path, m4a_tmp, variant=variant):
                audio_path = self._publish(m4a_tmp, self._span_dir() / f"{stem}.m4a")
                joined_path.unlink(missing_ok=True)
            else:
                audio_path = self._publish(joined_path, self._span_dir() / f"{stem}.wav")
                m4a_tmp.unlink(missing_ok=True)
            payload = {
                "symbol": symbol,
                "span": span,
                "index": index,
                "variant": variant,
                "durationSec": round(duration, 3),
                "mapDurationSec": round(map_duration, 3),
                "barCount": movement.candle_count,
                "peaks": peaks,
                "audio": audio_path.name,
                "fingerprint": movement.scale_fingerprint,
            }
            meta_tmp = work / f"{stem}.json"
            meta_tmp.write_text(json.dumps(payload), encoding="utf-8")
            self._publish(meta_tmp, self._span_dir() / f"{stem}.json")
            asset = self._read_span(symbol, span, index, variant, stem, movement.scale_fingerprint)
            if asset is None:
                raise RecapUnavailable("movement audio was not stored")
            return asset
        finally:
            _export_cancel.event = previous
            _export_timeout.seconds = previous_timeout
            xml_path.unlink(missing_ok=True)

    def _read_span(
        self,
        symbol: str,
        span: str,
        index: int,
        variant: Variant,
        stem: str,
        fingerprint: str,
    ) -> SpanAsset | None:
        folder = self.root / "spans"
        meta_path = folder / f"{stem}.json"
        if not meta_path.is_file():
            return None
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        name = str(payload.get("audio") or "")
        audio_path = folder / name
        if not name or audio_path.name != name or not audio_path.is_file():
            return None
        if str(payload.get("fingerprint") or "") != fingerprint:
            return None
        peaks = payload.get("peaks") or []
        return SpanAsset(
            symbol=symbol,
            span=span,
            index=index,
            variant=variant,
            audio_path=audio_path,
            duration_sec=float(payload.get("durationSec") or 0.0),
            map_duration_sec=float(payload.get("mapDurationSec") or 0.0),
            peaks=[float(peak) for peak in peaks],
            bar_count=int(payload.get("barCount") or 0),
            media_type=_media_type(audio_path),
            fingerprint=fingerprint,
        )

    def _prune_work(self, work: Path) -> None:
        cutoff = time.time() - WORK_KEEP_SEC
        for path in list(work.iterdir()):
            try:
                stale = path.stat().st_mtime < cutoff
            except OSError:
                continue
            if not stale:
                continue
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)

    def _render(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        bars: list[Bar],
        cancel: threading.Event | None,
        ensemble: Ensemble = "classic",
    ) -> RecapAsset:
        key = self._stem(symbol, day, variant, len(bars), ensemble)
        from app.sonify.keys import movement_character, stock_home_key

        score = render(
            bars,
            title=f"{symbol} {day.isoformat()}",
            variant=variant,
            ensemble=ensemble,
            key=stock_home_key(symbol),
            character=movement_character([bar.close for bar in bars], "1D"),
        )
        work = self.root / "work"
        work.mkdir(parents=True, exist_ok=True)
        xml_path = work / f"{key}.musicxml"
        wav_path = work / f"{key}.wav"
        xml_path.write_text(score_to_musicxml(score), encoding="utf-8")
        previous = getattr(_export_cancel, "event", None)
        _export_cancel.event = cancel
        try:
            _raise_if_cancelled_event(cancel)
            self._exporter(xml_path, wav_path)
            duration, peaks = waveform_peaks(wav_path)
            musical = piece_seconds(score.bars, score.bpm, score.bar_beats)
            if duration <= 0:
                duration = musical
            # MuseScore leaves a short release after the last note. The chart
            # follows the written piece, then rests on the close during that tail.
            map_duration = musical if 0 < musical <= duration else duration
            m4a_tmp = work / f"{key}.m4a"
            if _transcode_m4a(wav_path, m4a_tmp, variant=variant):
                audio_path = self._publish(m4a_tmp, self.root / f"{key}.m4a")
                wav_path.unlink(missing_ok=True)
            else:
                audio_path = self._publish(wav_path, self.root / f"{key}.wav")
                m4a_tmp.unlink(missing_ok=True)
            payload = {
                "symbol": symbol,
                "date": day.isoformat(),
                "variant": variant,
                "ensemble": ensemble,
                "durationSec": round(duration, 3),
                "mapDurationSec": round(map_duration, 3),
                "barCount": len(bars),
                "peaks": peaks,
                "audio": audio_path.name,
                "closed": self._is_closed(day),
            }
            meta_tmp = work / f"{key}.json"
            meta_tmp.write_text(json.dumps(payload), encoding="utf-8")
            self._publish(meta_tmp, self.root / f"{key}.json")
            if self._is_closed(day):
                self._drop_other_counts(symbol, day, variant, len(bars), ensemble)
            return self._asset(symbol, day, variant, audio_path, payload)
        finally:
            _export_cancel.event = previous
            xml_path.unlink(missing_ok=True)

    def _publish(self, source: Path, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, dest)
        return dest

    def _cached(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        bar_count: int,
        ensemble: Ensemble = "classic",
    ) -> RecapAsset | None:
        cached = self._read(symbol, day, variant, self._stem(symbol, day, variant, bar_count, ensemble))
        if cached is not None and self._is_closed(day):
            self._drop_other_counts(symbol, day, variant, bar_count, ensemble)
        return cached

    def _drop_other_counts(
        self,
        symbol: str,
        day: date,
        variant: Variant,
        keep: int,
        ensemble: Ensemble = "classic",
    ) -> None:
        prefix = f"{self._piece(symbol, day, variant, ensemble)}_{RECAP_REVISION}_"
        keep_stem = f"{prefix}{keep}"
        for path in list(self.root.iterdir()):
            if path.stem.startswith(prefix) and path.stem != keep_stem:
                path.unlink(missing_ok=True)

    def _read(self, symbol: str, day: date, variant: Variant, key: str) -> RecapAsset | None:
        meta_path = self.root / f"{key}.json"
        if not meta_path.is_file():
            return None
        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if int(payload.get("barCount") or 0) <= 0:
            return None
        name = str(payload.get("audio") or "")
        audio_path = self.root / name
        if not name or audio_path.name != name or not audio_path.is_file():
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
            ensemble=payload.get("ensemble") or "classic",
        )


_store: RecapStore | None = None


def recap_store() -> RecapStore:
    global _store
    if _store is None:
        _store = RecapStore()
    return _store
