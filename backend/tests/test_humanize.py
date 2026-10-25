"""Plateau humanize stays outside render(), and each line has its own color."""

from __future__ import annotations

import math
import struct
from array import array
from pathlib import Path

from app.sonify.humanize import chosen_offset, humanize
from app.sonify.model import NoteEvent, Score
from app.sonify.preset import _mix_noise, apply_preset, preset_chain


def _note(
    beat: float,
    velocity: int | None,
    midi: int | None = 64,
    *,
    voice: int = 2,
    duration_beats: float = 0.5,
    **kwargs,
) -> NoteEvent:
    return NoteEvent(
        bar=0,
        beat=beat,
        midi=midi,
        duration_beats=duration_beats,
        voice=voice,
        velocity=velocity,
        **kwargs,
    )


def _score(**fields) -> Score:
    base = dict(
        title="humanize",
        bpm=88,
        bars=1,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(),
        high=(),
        lead=(),
        support=(),
        comp=(),
        low=(),
        dynamics=(),
        harmonies=(),
        liquidity=(),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble="classic",
        divisions=4,
        bar_beats=4.0,
    )
    base.update(fields)
    return Score(**base)


def _velocities(notes: tuple[NoteEvent, ...]) -> list[int | None]:
    return [note.velocity for note in notes]


def test_a_flat_study_bar_moves_and_the_bass_stays_louder() -> None:
    support = tuple(_note(beat, 56, midi=67) for beat in (0.0, 1.0, 2.0, 3.0))
    low = tuple(_note(beat, 60, midi=48, voice=3) for beat in (0.0, 1.0, 2.0, 3.0))
    heard = humanize(_score(support=support, low=low))
    assert [note.velocity for note in heard.support] != [56, 56, 56, 56] or [
        note.velocity for note in heard.low
    ] != [60, 60, 60, 60]
    for inner, bass in zip(heard.support, heard.low):
        assert inner.velocity is not None and bass.velocity is not None
        assert 54 <= inner.velocity <= 58
        assert 58 <= bass.velocity <= 62
        assert bass.velocity > inner.velocity


def test_etude_steps_of_one_and_two_stay_put() -> None:
    etude11 = tuple(_note(index * 0.25, velocity) for index, velocity in enumerate((49, 50, 51, 51)))
    etude1 = tuple(
        _note(index * 0.25, velocity)
        for index, velocity in enumerate((50, 50, 50, 52, 52, 54, 54, 54, 52, 52, 50, 50, 50))
    )
    tremolo = tuple(_note(index * 0.5, velocity) for index, velocity in enumerate((54, 58, 62, 59)))
    fill = tuple(_note(index * 0.25, velocity, midi=70) for index, velocity in enumerate((52, 55, 54, 52)))
    assert _velocities(humanize(_score(support=etude11)).support) == [49, 50, 51, 51]
    assert _velocities(humanize(_score(support=etude1)).support) == [
        50, 50, 50, 52, 52, 54, 54, 54, 52, 52, 50, 50, 50,
    ]
    assert _velocities(humanize(_score(low=tremolo)).low) == [54, 58, 62, 59]
    assert _velocities(humanize(_score(lead=fill)).lead) == [52, 55, 54, 52]


def test_same_beat_notes_share_one_offset() -> None:
    dyad = (
        _note(0.0, 58, midi=40, voice=3),
        _note(0.0, 58, midi=47, voice=3),
        _note(1.0, 58, midi=40, voice=3),
        _note(1.0, 58, midi=47, voice=3),
    )
    chord = (
        _note(0.0, 64, midi=60),
        _note(0.0, 64, midi=64),
        _note(0.0, 64, midi=67),
        _note(1.0, 64, midi=60),
        _note(1.0, 64, midi=64),
        _note(1.0, 64, midi=67),
    )
    heard_dyad = humanize(_score(low=dyad)).low
    heard_chord = humanize(_score(support=chord)).support
    assert heard_dyad[0].velocity == heard_dyad[1].velocity == 58 + chosen_offset("guitar", "classic", "low", 0, 0.0)
    assert heard_dyad[2].velocity == heard_dyad[3].velocity
    assert len({note.velocity for note in heard_chord[:3]}) == 1
    assert heard_chord[0].velocity == 64 + chosen_offset("guitar", "classic", "support", 0, 0.0)


def test_an_inverting_offset_shrinks_toward_zero() -> None:
    def push(variant: str, ensemble: str, field: str, bar: int, beat: float) -> int:
        del variant, ensemble, bar
        if field == "low":
            return -2
        if field == "support":
            return 2
        return 0

    support = tuple(_note(beat, 56, midi=67) for beat in (0.0, 1.0))
    low = tuple(_note(beat, 60, midi=48, voice=3) for beat in (0.0, 1.0))
    heard = humanize(_score(support=support, low=low), offset_at=push)
    for inner, bass in zip(heard.support, heard.low):
        assert inner.velocity is not None and bass.velocity is not None
        assert bass.velocity > inner.velocity
        assert 56 <= inner.velocity <= 58
        assert 58 <= bass.velocity <= 60
        assert inner.velocity - 56 >= 0
        assert bass.velocity - 60 <= 0


def test_a_step_of_four_is_not_erased_when_both_plateaus_move() -> None:
    def apart(variant: str, ensemble: str, field: str, bar: int, beat: float) -> int:
        del variant, ensemble, field, bar
        return 2 if beat < 2 else -2

    notes = tuple(_note(beat, 50 if beat < 2 else 54) for beat in (0.0, 1.0, 2.0, 3.0))
    heard = humanize(_score(support=notes), offset_at=apart).support
    assert heard[1].velocity is not None and heard[2].velocity is not None
    assert heard[1].velocity < heard[2].velocity
    assert all(note.velocity is not None and abs(note.velocity - written) <= 2 for note, written in zip(heard, (50, 50, 54, 54)))
    assert all((note.velocity or 0) >= 50 for note in heard[:2])
    assert all((note.velocity or 0) <= 54 for note in heard[2:])


def test_tie_stop_copies_the_humanized_attack() -> None:
    def lift(variant: str, ensemble: str, field: str, bar: int, beat: float) -> int:
        del variant, ensemble, field, bar, beat
        return 1

    attack = _note(0.0, 56, midi=40, tie_start=True, duration_beats=1.0)
    other = _note(1.0, 56, midi=47)
    tied = _note(1.0, 56, midi=40, tie_stop=True, duration_beats=1.0)
    heard = humanize(_score(low=(attack, other, tied)), offset_at=lift).low
    assert heard[0].velocity == 57
    assert heard[2].velocity == 57
    assert heard[2].tie_stop


def test_a_swell_peak_keeps_its_written_velocity() -> None:
    def lift(variant: str, ensemble: str, field: str, bar: int, beat: float) -> int:
        del variant, ensemble, field, bar, beat
        return 1

    for peak in (64, 80):
        opening = _note(0.0, 49, midi=60, tie_start=True, duration_beats=1.0)
        neighbor = _note(0.5, 49, midi=67)
        crest = _note(1.0, peak, midi=60, tie_stop=True, duration_beats=1.0)
        heard = humanize(_score(comp=(opening, neighbor, crest)), offset_at=lift).comp
        assert heard[0].velocity == 50
        assert heard[1].velocity == 50
        assert heard[2].velocity == peak
        assert heard[2].tie_stop


def test_rests_and_unset_velocity_stay() -> None:
    rest = _note(0.0, 56, midi=None)
    unset = _note(1.0, None, midi=64)
    plateau = tuple(_note(beat, 70, midi=72) for beat in (2.0, 3.0))
    heard = humanize(_score(lead=(rest, unset, *plateau)))
    assert heard.lead[0] == rest
    assert heard.lead[1] == unset


def test_the_same_score_humanizes_the_same_way() -> None:
    notes = tuple(_note(beat, 56) for beat in (0.0, 0.5, 1.0, 1.5))
    score = _score(support=notes)
    assert humanize(score) == humanize(score)


def test_preset_chains_match_the_five_lines() -> None:
    symphony = preset_chain("symphony")
    guitar = preset_chain("guitar")
    jazz = preset_chain("jazz")
    wood = preset_chain("minimalist")
    air = preset_chain("ambient")
    assert symphony is not None and guitar is not None and jazz is not None and wood is not None and air is not None
    assert symphony.name == guitar.name == "vintage"
    assert symphony.ffmpeg != guitar.ffmpeg
    assert "highshelf=f=8000:g=-2" in symphony.ffmpeg
    assert "highshelf=f=8000:g=-1" in guitar.ffmpeg
    assert "extrastereo" not in guitar.ffmpeg and "extrastereo" not in symphony.ffmpeg
    assert symphony.noise == 0.001 and symphony.gate_noise is False
    assert guitar.noise < symphony.noise and guitar.gate_noise is True
    assert jazz.name == "club" and "aecho=" in jazz.ffmpeg and jazz.noise == 0
    assert wood.name == "wood" and "aecho=" in wood.ffmpeg and "asoftclip" not in wood.ffmpeg and wood.noise == 0
    assert air.name == "air" and "highshelf=" in air.ffmpeg and "aecho=" in air.ffmpeg and air.noise == 0
    assert "0.4" not in wood.ffmpeg


def test_colored_wav_keeps_the_dry_length_and_peak(tmp_path: Path) -> None:
    dry = tmp_path / "dry.wav"
    _tone_then_silence(dry)
    guitar = tmp_path / "guitar.wav"
    symphony = tmp_path / "symphony.wav"
    assert apply_preset(dry, guitar, "guitar")
    assert apply_preset(dry, symphony, "symphony")
    assert apply_preset(dry, tmp_path / "guitar-again.wav", "guitar")
    assert (tmp_path / "guitar-again.wav").read_bytes() == guitar.read_bytes()
    dry_channels, dry_rate, dry_samples = _samples(dry)
    for path in (guitar, symphony):
        channels, rate, samples = _samples(path)
        assert (channels, rate, len(samples)) == (dry_channels, dry_rate, len(dry_samples))
        assert _peak(samples) <= _peak(dry_samples) + 1e-6
    # The gated bed is quiet once the dry tone has been gone longer than the echo.
    assert _rms(guitar, start=0.75) < 1e-4
    assert _rms(symphony, start=0.75) > 2e-4


def test_vintage_noise_uses_the_sample_scale() -> None:
    rest = array("f", [0.0] * 64)
    heard = array("f", rest)
    _mix_noise(heard, rest, 1, 0.001, False)
    assert 0 < max(abs(sample) for sample in heard) < 0.0015

    quiet = array("f", [0.009] * 32)
    gated = array("f", quiet)
    _mix_noise(gated, quiet, 1, 0.0003, True)
    assert list(gated) == list(quiet)

    pcm = array("h", [0] * 128 + [1000] * 128)
    mixed = array("h", pcm)
    _mix_noise(mixed, pcm, 1, 0.001, False)
    bed = max(abs(sample) for sample in mixed[:128])
    assert 16 <= bed <= 33
    assert max(abs(sample - 1000) for sample in mixed[128:]) >= 16

    below_gate = array("h", [100] * 64)
    held = array("h", below_gate)
    _mix_noise(held, below_gate, 1, 0.0003, True)
    assert list(held) == list(below_gate)
    above_gate = array("h", [1000] * 64)
    opened = array("h", above_gate)
    _mix_noise(opened, above_gate, 1, 0.0003, True)
    assert opened != above_gate


def _tone_then_silence(path: Path) -> None:
    rate = 44100
    frames = rate
    samples = array("f")
    for index in range(frames):
        level = 0.4 * math.sin(2 * math.pi * 440 * index / rate) if index < frames // 2 else 0.0
        samples.append(level)
        samples.append(level)
    _write(path, 2, rate, samples)


def _write(path: Path, channels: int, rate: int, samples: array) -> None:
    payload = samples.tobytes()
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(payload),
        b"WAVE",
        b"fmt ",
        16,
        3,
        channels,
        rate,
        rate * channels * 4,
        channels * 4,
        32,
        b"data",
        len(payload),
    )
    path.write_bytes(header + payload)


def _samples(path: Path) -> tuple[int, int, array]:
    data = path.read_bytes()
    offset = 12
    channels = rate = 0
    payload = b""
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        body = data[offset + 8 : offset + 8 + size]
        if chunk == b"fmt ":
            _fmt, channels, rate, _byte_rate, _align, _bits = struct.unpack_from("<HHIIHH", body)
        elif chunk == b"data":
            payload = body
        offset += 8 + size + (size & 1)
    samples = array("f")
    samples.frombytes(payload)
    return channels, rate, samples


def _peak(samples: array) -> float:
    return max(abs(float(sample)) for sample in samples)


def _rms(path: Path, start: float) -> float:
    channels, rate, samples = _samples(path)
    begin = int(start * rate) * channels
    window = samples[begin:]
    if not window:
        return 0.0
    return math.sqrt(sum(float(sample) ** 2 for sample in window) / len(window))
