"""Color a dry MuseScore WAV with one preset per line.

The chains are biquads and short echoes, with no lookahead, so the attack
stays on the note. `anoisesrc` is not deterministic across processes, so the
noise bed is mixed here from a fixed counter. Guitar noise follows the dry
signal and stays off in rests. The colored file is cut back to the dry length
because `aecho` appends a tail.
"""

from __future__ import annotations

import shutil
import subprocess
from array import array
from dataclasses import dataclass
from pathlib import Path

from app.sonify.audio import _wav_samples, write_wav

# Symphony bed, about -60 dB. Guitar is lower and gated.
_SYMPHONY_NOISE = 0.001
_GUITAR_NOISE = 0.0003
_GUITAR_GATE = 0.01

_SYMPHONY = (
    "highshelf=f=8000:g=-2,equalizer=f=300:t=h:w=200:g=1.5,"
    "asoftclip=type=tanh:threshold=0.9:oversample=1,aecho=1:1:24|40|58:0.07|0.045|0.03"
)
_GUITAR = "highshelf=f=8000:g=-1,equalizer=f=280:t=h:w=180:g=1.2,aecho=1:1:12|20:0.05|0.03"
_JAZZ = "aecho=1:1:22|36|48:0.08|0.05|0.03,asoftclip=type=tanh:threshold=0.9:oversample=1"
_MINIMALIST = "aecho=1:1:18|32:0.07|0.04"
_AMBIENT = "highshelf=f=7000:g=-1.5,aecho=1:1:28|48:0.06|0.035"


@dataclass(frozen=True)
class PresetChain:
    """FFmpeg graph for one variant, plus a deterministic noise bed."""

    name: str
    ffmpeg: str
    noise: float = 0.0
    gate_noise: bool = False


_CHAINS: dict[str, PresetChain] = {
    "symphony": PresetChain("vintage", _SYMPHONY, noise=_SYMPHONY_NOISE, gate_noise=False),
    "guitar": PresetChain("vintage", _GUITAR, noise=_GUITAR_NOISE, gate_noise=True),
    "jazz": PresetChain("club", _JAZZ),
    "minimalist": PresetChain("wood", _MINIMALIST),
    "ambient": PresetChain("air", _AMBIENT),
}


def preset_chain(variant: str) -> PresetChain | None:
    return _CHAINS.get(variant)


def apply_preset(dry_path: Path, colored_path: Path, variant: str) -> bool:
    """Write a colored WAV the same length as `dry_path`. False keeps the dry file."""
    chain = preset_chain(variant)
    ffmpeg = shutil.which("ffmpeg")
    if chain is None or ffmpeg is None or not dry_path.is_file():
        return False
    channels, rate, dry = _wav_samples(dry_path)
    if channels not in (1, 2) or rate <= 0 or not dry:
        return False
    frames = len(dry) // channels
    # Raw PCM avoids FFmpeg's WAVE_FORMAT_EXTENSIBLE header.
    raw = colored_path.with_name(colored_path.stem + ".pcm")
    sample_format = "f32le" if dry.typecode == "f" else "s16le"
    command = [ffmpeg, "-y", "-i", str(dry_path), "-af", chain.ffmpeg, "-f", sample_format, str(raw)]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raw.unlink(missing_ok=True)
        return False
    if completed.returncode != 0 or not raw.is_file():
        raw.unlink(missing_ok=True)
        return False
    payload = raw.read_bytes()
    raw.unlink(missing_ok=True)
    width = 4 if dry.typecode == "f" else 2
    count = len(payload) // width
    heard = array(dry.typecode)
    heard.frombytes(payload[: count * width])
    heard = array(heard.typecode, heard[: frames * channels])
    if len(heard) < frames * channels:
        return False
    if chain.noise:
        _mix_noise(heard, dry, channels, chain.noise, chain.gate_noise)
    _limit_peak(heard, dry)
    write_wav(colored_path, channels, rate, heard)
    return colored_path.is_file()


def _mix_noise(heard: array, dry: array, channels: int, amplitude: float, gate: bool) -> None:
    frames = len(heard) // channels
    for frame in range(frames):
        base = frame * channels
        if gate:
            level = 0.0
            for channel in range(channels):
                level = max(level, abs(float(dry[base + channel])))
            if level < _GUITAR_GATE:
                continue
        for channel in range(channels):
            sample = float(heard[base + channel]) + amplitude * _unit_noise(frame, channel)
            if heard.typecode == "f":
                heard[base + channel] = sample
            else:
                heard[base + channel] = max(-32768, min(32767, int(sample)))


def _unit_noise(frame: int, channel: int) -> float:
    value = ((frame + 1) * 1664525 + (channel + 1) * 1013904223) & 0xFFFFFFFF
    value ^= (value << 13) & 0xFFFFFFFF
    value ^= value >> 17
    value ^= (value << 5) & 0xFFFFFFFF
    value &= 0xFFFFFFFF
    return (value / 0x7FFFFFFF) - 1.0


def _limit_peak(heard: array, dry: array) -> None:
    dry_peak = max((abs(float(sample)) for sample in dry), default=0.0)
    heard_peak = max((abs(float(sample)) for sample in heard), default=0.0)
    if dry_peak <= 0 or heard_peak <= dry_peak:
        return
    gain = dry_peak / heard_peak
    for index, sample in enumerate(heard):
        scaled = float(sample) * gain
        if heard.typecode == "f":
            heard[index] = scaled
        else:
            heard[index] = max(-32768, min(32767, int(scaled)))
