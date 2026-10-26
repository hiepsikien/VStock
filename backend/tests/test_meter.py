"""Phase-1 daily symphony meter: fidelity, gates, and the four frozen-score controls."""

from __future__ import annotations

from app.sonify.chords import AM, C
from app.sonify.form import chord_bias, chords_for_spec
from app.sonify.meter import _Eighth, _direction, _owner, measure_daily, regime_lift
from app.sonify.model import Bar, NoteEvent
from app.sonify.quantize import c_major_scale
from app.sonify.render import render


def _bars(closes: list[float], volumes: list[float] | None = None, ma: float | None = None) -> list[Bar]:
    levels = volumes if volumes is not None else [1_000.0] * len(closes)
    return [
        Bar(close, volume, ma if ma is not None else close)
        for close, volume in zip(closes, levels)
    ]


def _note(bar: int, beat: float, midi: int) -> NoteEvent:
    return NoteEvent(bar, beat, midi, 1.0, 1)


def test_high_owns_the_flute_overlap_and_the_later_voice_owns_the_dovetail() -> None:
    high = _note(2, 0.0, 88)
    lead = _note(2, 0.0, 84)
    support = _note(2, 0.5, 55)
    assert _owner(high, lead, support)[0] == "high"
    assert _owner(None, lead, support)[0] == "support"
    assert _owner(None, _note(2, 1.0, 84), _note(2, 0.0, 55))[0] == "lead"
    assert _owner(None, None, support)[0] == "support"


def test_a_folded_flute_step_stays_in_f1() -> None:
    scale = c_major_scale()
    line = (
        _Eighth(0, 2, 0, 20, 88, scale.index(88), "high"),
        _Eighth(1, 2, 1, 21, 77, scale.index(77), "high"),
    )
    assert _direction(line) == 0.0


def test_regime_lift_is_catalog_minus_chosen() -> None:
    chords = (C,) * 4
    regimes = ("uptrend",) * 4
    catalog = chords_for_spec(True)
    chosen = sum(chord_bias(C, "uptrend", None) for _ in chords) / len(chords)
    catalog_mean = sum(chord_bias(chord, "uptrend", None) for chord in catalog) / len(catalog)
    assert regime_lift(chords, regimes, None) == catalog_mean - chosen
    assert regime_lift(chords, regimes, None) > 0


def test_shuffled_regimes_make_a_matched_chord_more_expensive() -> None:
    matched = regime_lift((C, AM), ("uptrend", "downtrend"), None)
    crossed = regime_lift((C, AM), ("downtrend", "uptrend"), None)
    assert matched > crossed
    assert matched > 0


def test_rising_session_tracks_price_and_keeps_the_four_controls() -> None:
    closes = [100.0 + index * 0.4 for index in range(40)]
    volumes = [1_000.0 * (index + 1) for index in range(len(closes))]
    bars = _bars(closes, volumes)
    score = render(bars)
    record = measure_daily(bars, score)
    body = [
        next(slot for slot in score.slots if slot.start <= bar < slot.start + slot.length)
        for bar in range(2, 32)
    ]

    assert record.gates.source_on_body
    assert record.gates.frame
    assert record.legality.m5_frame
    assert record.legality.m1_lead_support_holds
    assert record.fidelity.f1 is not None
    assert 0.0 <= record.fidelity.f1 <= 1.0
    assert record.fidelity.f1 > 0.5
    assert record.fidelity.f6 == regime_lift(
        [slot.chord for slot in body], [slot.regime for slot in body], None
    )
    assert record.fidelity.f3_lead_support is not None
    assert record.fidelity.f3_lead_support < 8
    assert record.fidelity.f4 is None
    assert record.stratum.high_eighths > 0
    assert record.fidelity.f3_high is not None

    reversed_f1 = record.controls.price_reversed.f1
    assert reversed_f1 is not None
    assert 0.0 <= reversed_f1 <= 1.0
    assert reversed_f1 < record.fidelity.f1
    assert reversed_f1 < 0.5
    assert record.controls.price_reversed.f5 == record.fidelity.f5

    assert record.fidelity.f5 is not None and record.fidelity.f5 > 0
    assert record.controls.volume_reversed.f5 is not None
    assert record.controls.volume_reversed.f5 < 0

    permuted = record.controls.pitches_permuted
    assert permuted.f1 is not None and permuted.f1 < record.fidelity.f1
    assert permuted.m1_lead_support is not None
    assert permuted.m1_lead_support < record.legality.m1_lead_support


def test_peaked_session_reports_turn_recall() -> None:
    closes = [100.0 + index * 0.5 for index in range(24)]
    closes += [closes[-1] - index * 0.8 for index in range(1, 17)]
    bars = _bars(closes, [2_000.0 + index * 100 for index in range(len(closes))])
    record = measure_daily(bars, render(bars))
    assert record.fidelity.f4 is not None
    assert 0.0 <= record.fidelity.f4 <= 1.0


def test_flat_session_omits_contour_and_does_not_gate_melody_span() -> None:
    bars = _bars([50.0] * 30)
    record = measure_daily(bars, render(bars))

    assert record.observations.distinct_scale_degrees < 3
    assert record.fidelity.f1 is None
    assert record.fidelity.f2 is None
    assert record.fidelity.f4 is None
    assert record.observations.melody_span is not None
    assert record.gates.source_on_body
    assert record.gates.frame
    assert record.gates.narrow_span_all_mf is True


def test_silent_window_stays_p_when_the_span_is_narrow() -> None:
    volumes = [1_000.0] * 30
    volumes[0] = 0.0
    volumes[1] = 0.0
    bars = _bars([100.0 + index * 0.3 for index in range(30)], volumes)
    record = measure_daily(bars, render(bars))

    assert record.stratum.volume_span_ratio is not None
    assert record.stratum.volume_span_ratio < 2
    assert record.gates.narrow_span_all_mf is None
    assert record.fidelity.f5 is not None
    assert record.legality.m4_liquidity_letters >= 2


def test_mode_observation_uses_the_closing_window() -> None:
    closes = [100.0] * 25
    closes[5] = 102.0
    closes[10] = 98.0
    closes.extend([99.0, 99.0, 99.0, 99.0, 100.0])
    bars = _bars(closes, ma=100.0)
    score = render(bars)
    record = measure_daily(bars, score)

    assert record.observations.character == "volatile"
    assert record.observations.closing_regime == "downtrend"
    assert score.regimes[-1] == "sideway"
    assert record.observations.expected_mode == "minor"
    assert record.observations.score_mode == "major"
    assert record.observations.mode_wired is False
    assert record.gates.frame
