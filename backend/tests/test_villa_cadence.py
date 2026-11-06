"""`VILLA_CADENCE`: one sustained chord, no overflow, half-cadence warning."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from app.sonify.chords import C, G
from app.sonify.form import METER_24, METER_44
from app.sonify.guitar_villa_figures import (
    VILLA_CADENCE,
    VILLA_FIGURE_NAMES,
    VILLA_FIGURES,
    _cadence_bar,
    _nearest_chord_root,
    is_half_cadence,
)
from tests.guitar_fixture import meter_named, pattern_case


def _ctx(meter, bars: int = 2, *, chords=None):
    ctx, _phrases = pattern_case(
        "probe",
        meter_named("4/4"),
        ensemble="villa",
        mood="calm",
        band="mf",
        bpm=96,
        bars=bars,
        first_body=True,
        previous=[],
    )
    if meter is METER_24:
        ctx = replace(
            ctx,
            bars=bars,
            epb=meter.eighths_per_bar,
            kind="2/4",
            bar_beats=meter.quarter_beats,
            strong=tuple(meter.strong_eighths),
            melody=[
                60 + index for index in range(bars * meter.eighths_per_bar)
            ],
            raw=[
                60 + index for index in range(bars * meter.eighths_per_bar)
            ],
        )
    if chords is not None:
        ctx = replace(ctx, chord_at=dict(chords))
    return ctx


@pytest.mark.parametrize("meter", [METER_44, METER_24])
def test_cadence_is_one_sustained_attack_with_no_overflow(meter) -> None:
    ctx = _ctx(meter)
    high, mid, low = _cadence_bar(ctx, 0, None)
    assert high and mid and low
    for voice in (high, mid, low):
        assert voice[0].beat == 0
        assert {event.midi for event in voice} == {voice[0].midi}
        assert sum(event.duration_beats for event in voice) == pytest.approx(
            meter.quarter_beats
        )
        assert all(
            event.beat + event.duration_beats <= meter.quarter_beats
            for event in voice
        )


def test_cadence_is_registered_without_a_contour() -> None:
    assert VILLA_CADENCE == 5
    assert VILLA_FIGURE_NAMES[VILLA_CADENCE] == "villa_cadence"
    assert VILLA_FIGURES[VILLA_CADENCE] is _cadence_bar


def test_nearest_chord_root_tracks_previous_and_guards_empty() -> None:
    ctx = _ctx(METER_44)
    found = _nearest_chord_root(
        ctx, G, 2, ctx.treble_floor, ctx.treble_top
    )
    assert found is not None
    assert found % 12 == G.pitches[0] % 12
    assert ctx.treble_floor <= found <= ctx.treble_top
    assert _nearest_chord_root(replace(ctx, melody=[]), G, 2, 60, 80) is None


def test_last_chord_root_means_close_not_half_cadence() -> None:
    ctx = _ctx(METER_44, chords={0: C, 1: C})
    assert is_half_cadence(ctx, 1) is False
    _cadence_bar(ctx, 1, None)


def test_closing_on_v_warns_as_a_half_cadence(caplog) -> None:
    ctx = _ctx(METER_44, chords={0: C, 1: G})
    assert is_half_cadence(ctx, 1) is True
    with caplog.at_level(logging.WARNING):
        _cadence_bar(ctx, 1, None)
    assert any(
        "half cadence" in record.getMessage().lower()
        for record in caplog.records
    )
