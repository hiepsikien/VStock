"""Phase-1 daily symphony meter: fidelity, gates, and the four frozen-score controls."""

from __future__ import annotations

from types import SimpleNamespace

from app.sonify.chords import AM, C
from app.sonify.dynamics import average_liquidity
from app.sonify.form import DAILY_ENSEMBLE_SPEC, chord_bias, chords_for_spec, liquidity_windows_for
from app.sonify.meter import (
    _Eighth,
    _direction,
    _liquidity,
    _owner,
    _parallel_fifths,
    _reversed_volumes,
    measure_daily,
    regime_lift,
)
from app.sonify.model import Bar, NoteEvent
from app.sonify.quantize import c_major_scale
from app.sonify.render import _window_candles, assign_daily_ambient_bars, render


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
    assert record.controls.regime_shuffled.labels_changed is False
    assert record.controls.regime_shuffled.f6 is None


def test_parallel_fifths_require_both_voices_to_move_the_same_way() -> None:
    oblique = SimpleNamespace(
        low=(NoteEvent(2, 0.0, 36, 2.0, 1), NoteEvent(2, 2.0, 48, 2.0, 1))
    )
    still = (
        _Eighth(0, 2, 0, 0, 79, 0, "lead"),
        _Eighth(4, 2, 4, 0, 79, 0, "lead"),
    )
    contrary = SimpleNamespace(
        low=(NoteEvent(2, 0.0, 60, 2.0, 1), NoteEvent(2, 2.0, 53, 2.0, 1))
    )
    apart = (
        _Eighth(0, 2, 0, 0, 67, 0, "lead"),
        _Eighth(4, 2, 4, 0, 72, 0, "lead"),
    )
    parallel = SimpleNamespace(
        low=(NoteEvent(2, 0.0, 60, 2.0, 1), NoteEvent(2, 2.0, 65, 2.0, 1))
    )
    together = (
        _Eighth(0, 2, 0, 0, 67, 0, "lead"),
        _Eighth(4, 2, 4, 0, 72, 0, "lead"),
    )

    assert _parallel_fifths(oblique, still) == 0
    assert _parallel_fifths(contrary, apart) == 0
    assert _parallel_fifths(parallel, together) == 1


def test_one_regime_body_skips_the_shuffle_and_mixed_labels_move_f6() -> None:
    closes = [100.0 + index * 0.4 for index in range(40)]
    volumes = [1_000.0 * (index + 1) for index in range(len(closes))]
    bars = _bars(closes, volumes)
    single = measure_daily(bars, render(bars))
    assert single.controls.regime_shuffled.labels_changed is False
    assert single.controls.regime_shuffled.f6 is None

    mixed = render(bars, regimes=("uptrend", "sideway", "downtrend"))
    record = measure_daily(bars, mixed)
    shuffled_f6 = record.controls.regime_shuffled.f6
    assert record.controls.regime_shuffled.labels_changed is True
    assert record.fidelity.f6 is not None and abs(record.fidelity.f6) < 0.02
    assert shuffled_f6 is not None and shuffled_f6 < record.fidelity.f6
    assert shuffled_f6 < 0


def test_volume_reversal_carries_the_auction_flag() -> None:
    closes = [100.0 + index * 0.3 for index in range(30)]
    volumes = [1_000.0 * (index + 1) for index in range(30)]
    volumes[0] = 1_000_000.0
    bars = [
        Bar(close, volume, close, auction=(index == 0))
        for index, (close, volume) in enumerate(zip(closes, volumes))
    ]
    score = render(bars)
    record = measure_daily(bars, score)
    groups = assign_daily_ambient_bars(len(bars))
    windows = liquidity_windows_for(DAILY_ENSEMBLE_SPEC)
    letters = list(score.liquidity)

    def body_f5(series: list[Bar]) -> float | None:
        values = average_liquidity(
            [_window_candles(series, groups, start, length) for start, length in windows]
        )
        body_volumes = [
            volume
            for (start, length), volume in zip(windows, values)
            if start >= 2 and start + length <= 32
        ]
        body_letters = [
            marking
            for (start, length), marking in zip(windows, letters)
            if start >= 2 and start + length <= 32
        ]
        return _liquidity(body_volumes, body_letters)

    traveling = body_f5(_reversed_volumes(bars))
    stuck = [
        Bar(bar.close, bars[len(bars) - 1 - index].volume, bar.ma20, bar.auction)
        for index, bar in enumerate(bars)
    ]
    assert record.controls.volume_reversed.f5 == traveling
    assert body_f5(stuck) != traveling


def test_f6_prices_the_planner_character_the_caller_repeats() -> None:
    closes = [100.0 + index * 0.4 for index in range(40)]
    volumes = [1_000.0 * (index + 1) for index in range(len(closes))]
    bars = _bars(closes, volumes)
    score = render(bars, character="selloff")
    body = [
        next(slot for slot in score.slots if slot.start <= bar < slot.start + slot.length)
        for bar in range(2, 32)
    ]
    chords = [slot.chord for slot in body]
    regimes = [slot.regime for slot in body]
    omitted = measure_daily(bars, score)
    told = measure_daily(bars, score, planner_character="selloff")

    assert omitted.fidelity.f6 == regime_lift(chords, regimes, None)
    assert told.fidelity.f6 == regime_lift(chords, regimes, "selloff")
    assert omitted.fidelity.f6 != told.fidelity.f6


def test_source_groups_rebuild_the_raw_contour() -> None:
    bars = _bars([100.0 + index for index in range(10)])
    score = render(bars)
    piled: list[list[int]] = [[] for _ in range(34)]
    piled[2] = list(range(10))
    spread = measure_daily(bars, score)
    piled_record = measure_daily(bars, score, source_groups=piled)
    assert spread.fidelity.f1 != piled_record.fidelity.f1


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
