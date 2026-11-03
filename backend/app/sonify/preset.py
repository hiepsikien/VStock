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


@dataclass(frozen=True)
class ColorSpec:
    """Typed colour for one variant. The FFmpeg chain is generated from this."""

    name: str
    highshelf_hz: int = 0
    highshelf_db: float = 0.0
    eq_hz: int = 0
    eq_width: int = 0
    eq_db: float = 0.0
    echo: tuple[tuple[int, float], ...] = ()
    softclip_threshold: float | None = None
    echo_before_clip: bool = False
    noise: float = 0.0
    gate_noise: bool = False

    def chain(self, amount: float) -> str:
        return _ordered_chain(self, amount)


def _ordered_chain(spec: ColorSpec, amount: float) -> str:
    """Emit the same order as the hardcoded chain: shelf, eq, clip, echo."""
    parts: list[str] = []
    if spec.highshelf_hz and spec.highshelf_db:
        gain = spec.highshelf_db * amount
        if gain:
            parts.append(f"highshelf=f={spec.highshelf_hz}:g={gain:g}")
    if spec.eq_hz and spec.eq_db:
        gain = spec.eq_db * amount
        if gain:
            parts.append(f"equalizer=f={spec.eq_hz}:t=h:w={spec.eq_width}:g={gain:g}")
    clip = ""
    if spec.softclip_threshold is not None:
        threshold = 1.0 - (1.0 - spec.softclip_threshold) * amount
        if threshold < 1.0:
            clip = f"asoftclip=type=tanh:threshold={threshold:g}:oversample=1"
    taps = [(delay, decay * amount) for delay, decay in spec.echo if decay * amount > 0]
    echo = ""
    if taps:
        delays = "|".join(str(delay) for delay, _decay in taps)
        decays = "|".join(f"{decay:g}" for _delay, decay in taps)
        echo = f"aecho=1:1:{delays}:{decays}"
    if spec.echo_before_clip:
        parts.extend(filter(None, (echo, clip)))
    else:
        parts.extend(filter(None, (clip, echo)))
    return ",".join(parts)


_COLOR_SPECS: dict[str, ColorSpec] = {
    "symphony": ColorSpec(
        "vintage",
        highshelf_hz=8000,
        highshelf_db=-2,
        eq_hz=300,
        eq_width=200,
        eq_db=1.5,
        echo=((24, 0.07), (40, 0.045), (58, 0.03)),
        softclip_threshold=0.9,
        noise=_SYMPHONY_NOISE,
    ),
    "guitar": ColorSpec(
        "vintage",
        highshelf_hz=8000,
        highshelf_db=-1,
        eq_hz=280,
        eq_width=180,
        eq_db=1.2,
        echo=((12, 0.05), (20, 0.03)),
        noise=_GUITAR_NOISE,
        gate_noise=True,
    ),
    "jazz": ColorSpec(
        "club",
        echo=((22, 0.08), (36, 0.05), (48, 0.03)),
        softclip_threshold=0.9,
        echo_before_clip=True,
    ),
    "minimalist": ColorSpec("wood", echo=((18, 0.07), (32, 0.04))),
    "ambient": ColorSpec(
        "air",
        highshelf_hz=7000,
        highshelf_db=-1.5,
        echo=((28, 0.06), (48, 0.035)),
    ),
}


@dataclass(frozen=True)
class PresetChain:
    """FFmpeg graph for one variant, plus a deterministic noise bed."""

    name: str
    ffmpeg: str
    noise: float = 0.0
    gate_noise: bool = False


def preset_chain(variant: str, *, amount: float = 1.0, noise: float = 1.0) -> PresetChain | None:
    spec = _COLOR_SPECS.get(variant)
    if spec is None:
        return None
    chain = spec.chain(amount)
    if not chain:
        return None
    return PresetChain(spec.name, chain, noise=spec.noise * noise, gate_noise=spec.gate_noise)


def apply_preset(
    dry_path: Path,
    colored_path: Path,
    variant: str,
    *,
    params=None,
) -> bool:
    """Write a colored WAV the same length as `dry_path`. False keeps the dry file."""
    from app.sonify.params import active_params

    values = active_params() if params is None else params
    amount = float(values.get("color", 1.0))
    if amount <= 0:
        return False
    chain = preset_chain(
        variant, amount=amount, noise=float(values.get("noise", 1.0))
    )
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


def _unit_scale(samples: array) -> float:
    """Float samples sit in [-1, 1]. MuseScore 3 writes 16-bit integers."""
    return 32767.0 if samples.typecode == "h" else 1.0


def _mix_noise(heard: array, dry: array, channels: int, amplitude: float, gate: bool) -> None:
    frames = len(heard) // channels
    span = amplitude * _unit_scale(heard)
    gate_at = _GUITAR_GATE * _unit_scale(dry)
    for frame in range(frames):
        base = frame * channels
        if gate:
            level = 0.0
            for channel in range(channels):
                level = max(level, abs(float(dry[base + channel])))
            if level < gate_at:
                continue
        for channel in range(channels):
            sample = float(heard[base + channel]) + span * _unit_noise(frame, channel)
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
