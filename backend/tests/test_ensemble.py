"""Instrument rows beside the four genres. Classic stays the row already shipping."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.sonify.audio import RECAP_REVISION, SPAN_REVISION, RecapAsset, RecapStore, _STORED_NAME
from app.sonify.chords import C
from app.sonify.ensemble import ensemble_for, fit_ensemble, tune_register
from app.sonify.keys import A_KEY, BB_KEY, C_KEY, compose_register, register_for
from app.sonify.model import Bar, NoteEvent
from app.sonify.musicxml import score_to_musicxml
from app.sonify.phrasing import fill_tones
from app.sonify.render import render


def _note(midi: int) -> NoteEvent:
    return NoteEvent(bar=0, beat=0.0, midi=midi, duration_beats=1.0, voice=1)


def _score():
    return render(
        [Bar(100.0, 100.0, 100.0)] * 30,
        framed=False,
        regimes=("sideway",) * 3,
    )


def test_classic_score_keeps_the_current_bass_writing() -> None:
    xml = score_to_musicxml(_score())
    assert "<instrument-name>Electric Bass (finger)</instrument-name>" in xml
    assert "<octave-change>-1</octave-change>" in xml
    assert "ensemble=" not in RecapAsset(
        symbol="VNM",
        day=date(2026, 10, 22),
        variant="symphony",
        audio_path=Path("x.m4a"),
        duration_sec=1,
        map_duration_sec=1,
        peaks=[],
        bar_count=30,
        media_type="audio/mp4",
    ).audio_url


def test_wood_names_and_pitch_floors() -> None:
    base = _score()
    planted = replace(base, ensemble="wood", lead=(_note(50),), support=(_note(48),))
    fitted = fit_ensemble(planted)
    assert fitted.lead[0].midi == 62
    assert fitted.support[0].midi == 60
    xml = score_to_musicxml(planted)
    assert "<part-name>Oboe</part-name>" in xml
    assert "<part-name>Clarinet in Bb</part-name>" in xml
    assert "<instrument-name>Clarinet</instrument-name>" in xml
    assert "<octave-change>-1</octave-change>" in xml


def test_a_major_wood_fold_uses_the_sounding_pitch() -> None:
    fitted = fit_ensemble(replace(_score(), ensemble="wood", key=A_KEY, lead=(_note(60),)))
    assert fitted.lead[0].midi == 72


def _full(notes: tuple[NoteEvent, ...], bars: int) -> None:
    """Every voice fills each bar once. A pasted handoff leaves a hole or a double."""
    width = bars * 8
    grids: dict[int, list[int]] = {}
    for note in notes:
        if note.staff != 1:
            continue
        start = note.bar * 8 + int(round(note.beat * 2))
        length = int(round(note.duration_beats * 2))
        grid = grids.setdefault(note.voice, [0] * width)
        for offset in range(length):
            grid[start + offset] += 1
    assert grids
    for grid in grids.values():
        assert grid == [1] * width


def test_brass_fill_stops_at_f5_under_the_folded_trumpet() -> None:
    reg = tune_register(register_for(C_KEY), "brass", 0)
    assert reg.violin_ceiling == 82
    assert reg.fill_high == 77
    with compose_register(C_KEY, reg):
        climbing = fill_tones(C, 84, "violin")
        under_folded = fill_tones(C, 72, "violin")
    assert climbing == sorted(climbing)
    assert max(climbing) <= 77
    assert 79 not in climbing
    assert max(under_folded) <= 72 - 3
    xml = score_to_musicxml(replace(_score(), ensemble="brass"))
    assert "<part-name>French Horns a6</part-name>" in xml
    assert "<instrument-name>Horn in F</instrument-name>" in xml


def test_brass_score_keeps_the_trumpet_and_the_fill_inside_range() -> None:
    closes = [50.0 + index * 5 for index in range(30)]
    bars = [Bar(close, 100.0, close) for close in closes]
    score = render(bars, ensemble="brass", framed=False, regimes=("uptrend",) * 3)
    assert all(note.midi is None or note.midi <= 82 for note in score.lead)
    assert all(note.midi is None or note.midi <= 77 for note in score.comp)


def test_organ_handoff_keeps_full_bars() -> None:
    closes = [80.0 - index for index in range(30)]
    bars = [Bar(close, 100.0, close) for close in closes]
    score = render(bars, variant="jazz", ensemble="organ", framed=False, regimes=("downtrend",) * 3)
    assert score.ensemble == "organ"
    assert all(note.midi is None or note.midi >= 56 for note in score.lead)
    _full(score.lead, score.bars)
    _full(score.support, score.bars)


def test_wood_frame_matches_the_folded_pitch() -> None:
    closes = [40.0] * 8 + [70.0] * 22
    bars = [Bar(close, 100.0, close) for close in closes]
    score = render(bars, ensemble="wood", regimes=("sideway",) * 3)
    assert all(note.midi is None or note.midi >= 58 for note in score.lead)
    assert all(note.midi is None or note.midi >= 50 for note in score.support)
    for stop in score.support:
        if not stop.tie_stop or stop.midi is None:
            continue
        assert any(
            start.tie_start and start.midi == stop.midi and _meets(start, stop)
            for start in score.support
        )
    for stop in score.lead:
        if not stop.tie_stop or stop.midi is None:
            continue
        assert any(
            start.tie_start and start.midi == stop.midi and _meets(start, stop)
            for start in score.lead
        )


def _meets(start: NoteEvent, stop: NoteEvent) -> bool:
    end = start.bar * 4 + start.beat + start.duration_beats
    begin = stop.bar * 4 + stop.beat
    return abs(end - begin) < 1e-6


@pytest.mark.parametrize("key", (A_KEY, BB_KEY))
def test_choir_fold_uses_the_key_render_attaches(key) -> None:
    score = render(
        [Bar(100.0, 100.0, 100.0)] * 30,
        variant="ambient",
        ensemble="choir",
        key=key,
        framed=False,
        regimes=("sideway",) * 3,
    )
    low = [note.midi + key.semitones for note in score.low if note.midi is not None]
    viola = [note.midi + key.semitones for note in score.comp if note.midi is not None]
    assert low
    assert min(low) >= 36
    assert all(midi >= 48 for midi in viola)


def test_choir_sings_at_pitch_and_clamps_viola_and_bass() -> None:
    base = replace(_score(), ensemble="choir", variant="ambient", comp=(_note(45),), low=(_note(35), _note(36)))
    fitted = fit_ensemble(base)
    assert fitted.comp[0].midi == 57
    assert [note.midi for note in fitted.low] == [47, 36]
    xml = score_to_musicxml(base)
    assert "<part-name>Basses</part-name>" in xml
    assert "<octave-change>" not in xml


def test_breath_keeps_the_english_horn_top() -> None:
    fitted = fit_ensemble(replace(_score(), ensemble="breath", variant="ambient", lead=(_note(84),)))
    assert fitted.lead[0].midi == 84


def test_ensemble_must_belong_to_the_variant() -> None:
    assert ensemble_for("jazz", "classic") == "classic"
    assert ensemble_for("jazz", "soul") == "soul"
    assert ensemble_for("guitar", "brouwer") == "brouwer"
    with pytest.raises(ValueError):
        ensemble_for("jazz", "wood")
    with pytest.raises(ValueError):
        ensemble_for("symphony", "brouwer")


def test_cache_names_keep_the_classic_stem(tmp_path: Path) -> None:
    store = RecapStore(tmp_path)
    day = date(2026, 10, 22)
    classic = store._stem("VNM", day, "symphony", 30)
    assert classic == f"VNM_2026-10-22_symphony_{RECAP_REVISION}_30"
    wood = store._stem("VNM", day, "symphony", 30, "wood")
    assert wood == f"VNM_2026-10-22_symphony-wood_{RECAP_REVISION}_30"
    assert _STORED_NAME.match(f"{classic}.m4a")
    assert _STORED_NAME.match(f"{wood}.json")
    span = store._span_stem("VNM", "1W", 0, "symphony", 5, "1.0")
    assert f"_symphony_{SPAN_REVISION}_" in span
    band = store._span_stem("VNM", "1W", 0, "symphony", 5, "1.0", "wood")
    assert f"_symphony_wood_{SPAN_REVISION}_" in band
    assert f"_symphony_{SPAN_REVISION}_" not in band
