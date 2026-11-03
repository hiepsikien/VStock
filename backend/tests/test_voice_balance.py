"""The three guitar streams take their velocity offsets independently."""

from __future__ import annotations

import wave
from datetime import date
from pathlib import Path

import pytest

from app.sonify.audio import RecapStore
from app.sonify.dynamics import apply_voice_balance
from app.sonify.model import Bar, NoteEvent, Score
from app.sonify.musicxml import score_to_musicxml
from app.sonify.params import DEFAULT_PARAMS, compose_params


def _note(
    *,
    voice: int,
    velocity: int | None,
    midi: int | None = 60,
    bar: int = 0,
    beat: float = 0.0,
    duration: float = 1.0,
    tie_start: bool = False,
    tie_stop: bool = False,
    pinned: bool = False,
) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=voice,
        velocity=velocity,
        tie_start=tie_start,
        tie_stop=tie_stop,
        pinned=pinned,
    )


def _score(
    *,
    variant: str = "guitar",
    lead: tuple[NoteEvent, ...] = (),
    support: tuple[NoteEvent, ...] = (),
    low: tuple[NoteEvent, ...] = (),
) -> Score:
    return Score(
        title="Test",
        bpm=88,
        bars=1,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(),
        high=(),
        lead=lead,
        support=support,
        comp=(),
        low=low,
        dynamics=(),
        harmonies=(),
        liquidity=("mf",),
        phrases=(),
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant=variant,  # type: ignore[arg-type]
        ensemble="classic",
    )


def _base() -> Score:
    return _score(
        lead=(_note(voice=1, velocity=64),),
        support=(
            _note(voice=2, velocity=56, midi=55),
            _note(voice=4, velocity=56, midi=59),
        ),
        low=(_note(voice=3, velocity=60, midi=48),),
    )


def test_default_returns_the_same_score() -> None:
    score = _base()
    with compose_params(DEFAULT_PARAMS):
        assert apply_voice_balance(score) is score


@pytest.mark.parametrize("variant", ["symphony", "jazz", "minimalist", "ambient"])
def test_other_variants_are_untouched_even_with_guitar_params(variant: str) -> None:
    score = _score(
        variant=variant,
        lead=(_note(voice=1, velocity=64),),
    )
    with compose_params({**DEFAULT_PARAMS, "guitar_high": -8.0}):
        assert apply_voice_balance(score) is score


def test_high_moves_only_the_lead() -> None:
    with compose_params({**DEFAULT_PARAMS, "guitar_high": -8.0}):
        balanced = apply_voice_balance(_base())
    assert [note.velocity for note in balanced.lead] == [56]
    assert [note.velocity for note in balanced.support] == [56, 56]
    assert [note.velocity for note in balanced.low] == [60]


def test_mid_moves_both_support_voices() -> None:
    with compose_params({**DEFAULT_PARAMS, "guitar_mid": 8.0}):
        balanced = apply_voice_balance(_base())
    assert [note.velocity for note in balanced.support] == [64, 64]
    assert [note.velocity for note in balanced.lead] == [64]
    assert [note.velocity for note in balanced.low] == [60]


def test_bass_moves_only_the_low_stream() -> None:
    with compose_params({**DEFAULT_PARAMS, "guitar_bass": -8.0}):
        balanced = apply_voice_balance(_base())
    assert [note.velocity for note in balanced.low] == [52]
    assert [note.velocity for note in balanced.lead] == [64]
    assert [note.velocity for note in balanced.support] == [56, 56]


def test_velocity_clamps_to_the_midi_range() -> None:
    score = _score(
        lead=(_note(voice=1, velocity=127),),
        low=(_note(voice=3, velocity=1, midi=48),),
    )
    with compose_params(
        {**DEFAULT_PARAMS, "guitar_high": 12.0, "guitar_bass": -12.0}
    ):
        balanced = apply_voice_balance(score)
    assert [note.velocity for note in balanced.lead] == [127]
    assert [note.velocity for note in balanced.low] == [1]


def test_offset_is_exact() -> None:
    score = _score(lead=(_note(voice=1, velocity=64),))
    with compose_params({**DEFAULT_PARAMS, "guitar_high": 4.0}):
        balanced = apply_voice_balance(score)
    assert [note.velocity for note in balanced.lead] == [68]


def test_ties_and_pinned_notes_keep_the_same_offset() -> None:
    score = _score(
        lead=(
            _note(voice=1, velocity=64, tie_start=True),
            _note(voice=1, velocity=64, tie_stop=True),
            _note(voice=1, velocity=64, pinned=True),
        )
    )
    with compose_params({**DEFAULT_PARAMS, "guitar_high": -8.0}):
        balanced = apply_voice_balance(score)
    assert [note.velocity for note in balanced.lead] == [56, 56, 56]


def test_offsets_reach_musicxml() -> None:
    score = _score(low=(_note(voice=3, velocity=60, midi=48),))
    with compose_params(DEFAULT_PARAMS):
        default = score_to_musicxml(apply_voice_balance(score))
    with compose_params({**DEFAULT_PARAMS, "guitar_bass": -8.0}):
        soft = score_to_musicxml(apply_voice_balance(score))
    # 60 * 100 / 90 = 66.67; 52 * 100 / 90 = 57.78.
    assert 'dynamics="66.67"' in default
    assert 'dynamics="57.78"' in soft


def test_rests_keep_their_missing_velocity() -> None:
    score = _score(lead=(_note(voice=1, velocity=None, midi=None),))
    with compose_params({**DEFAULT_PARAMS, "guitar_high": -8.0}):
        balanced = apply_voice_balance(score)
    assert balanced.lead[0].velocity is None
    assert balanced.lead[0].midi is None


def _write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 400 + b"\xff\x7f" * 400)


def test_dfi_is_computed_before_balance(tmp_path: Path) -> None:
    """Moving balance before compute_dfi would make these two scores differ."""

    def export(_xml: Path, wav: Path) -> None:
        _write_wav(wav)

    store = RecapStore(tmp_path, exporter=export)
    day = date(2026, 10, 14)
    bars = [Bar(100.0 + index * 0.5, 10.0 * (index + 1), 100.0) for index in range(12)]
    base = store.ensure(
        "FPT",
        day,
        "guitar",
        bars,
        params={**DEFAULT_PARAMS, "guitar_bass": 0.0},
    )
    soft = store.ensure(
        "FPT",
        day,
        "guitar",
        bars,
        params={**DEFAULT_PARAMS, "guitar_bass": -8.0},
    )
    assert base.dfi is not None
    # `_volume()` reads note velocity. If balance ran first, the two DFI
    # scores would part ways; keeping them equal pins the pipeline order.
    assert base.dfi == soft.dfi


def test_balance_runs_when_humanize_is_off(tmp_path: Path) -> None:
    captured: list[str] = []

    def export(xml: Path, wav: Path) -> None:
        captured.append(xml.read_text(encoding="utf-8"))
        _write_wav(wav)

    store = RecapStore(tmp_path, exporter=export)
    day = date(2026, 10, 14)
    bars = [Bar(100.0 + index * 0.5, 10.0 * (index + 1), 100.0) for index in range(12)]
    off = {**DEFAULT_PARAMS, "humanize": 0.0, "breath": 0.0}
    store.ensure("FPT", day, "guitar", bars, params=off)
    store.ensure(
        "FPT",
        day,
        "guitar",
        bars,
        params={**off, "guitar_bass": -8.0},
    )
    assert len(captured) == 2
    # The pass must sit outside `if _humanize_on`; with humanize and breath
    # both off, only the bass offset can make the two exports differ.
    assert captured[0] != captured[1]
