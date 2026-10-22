"""Long-form geometry stays off the 30-bar daily path."""

import math
from array import array
from datetime import date

from app.sonify.audio import RecapStore, join_chunks, write_wav
from app.sonify.chords import A7, BF, BM7B5, C, EF, FDIM7, fifth_above_bass
from app.sonify.phrasing import quantize_strong_beats
from app.sonify.quantize import c_major_scale
from app.sonify.form import (
    _breaks_held_note_across_barline,
    BORROWED_HOLD_PROB,
    DAILY_SPEC,
    EXTENDED_STAY_PENALTY,
    LIQUIDITY_WINDOWS,
    TRANSITION_WEIGHT,
    _borrowed_allowed,
    liquidity_windows_for,
    plan_slots,
)
from app.sonify.model import Bar, NoteEvent, Score
from app.sonify.render import render
from app.sonify.span import (
    quarter_parts,
    month_parts,
    month_specs,
    plan_month,
    prepare_week,
    prepare_year,
    plan_week,
    quarter_specs,
    slice_score,
    split_into,
    week_source_groups,
    week_spec,
    year_specs,
)


def test_daily_windows_match_the_historical_grid():
    assert liquidity_windows_for(DAILY_SPEC) == LIQUIDITY_WINDOWS


def test_daily_spec_does_not_change_the_progression():
    regimes = ("uptrend", "sideway", "downtrend")
    pitches = [60] * 240
    assert plan_slots(regimes, pitches, spec=DAILY_SPEC) == plan_slots(regimes, pitches)


def test_week_hold_bar_is_the_last_bar_of_each_session_but_the_final_one():
    groups = week_source_groups([31, 31, 31, 31, 32])
    assert len(groups) == 160
    for bar in (31, 63, 95, 127):
        assert groups[bar] == []
        assert groups[bar - 1]
    assert groups[159]
    assert week_spec(5).bars == 160
    assert week_spec(3).bars == 96
    assert plan_week(5)[0].rest_after == 0.0


def test_short_week_does_not_stretch():
    spec = week_spec(2)
    assert spec.bars == 64
    assert spec.chunk_bounds() == ((0, 32), (32, 64))


def test_form_chunks_cover_every_bar():
    for spec in (*month_specs(), *quarter_specs(), *year_specs(), week_spec(5)):
        bounds = spec.chunk_bounds()
        assert bounds[0][0] == 0
        assert bounds[-1][1] == spec.bars
        assert all(right > left for left, right in bounds)


def test_month_split_keeps_the_extra_on_the_finale():
    assert split_into(10, 4) == [2, 2, 3, 3]
    movements = plan_month([5, 5, 5, 6])
    assert [item.label for item in movements] == ["I", "II", "III", "IV"]
    assert movements[0].rest_after == 6.0
    assert movements[-1].rest_after == 0.0


def test_a_new_month_joins_the_previous_quarter_movement():
    stamped = [
        (date(2026, month, 1), Bar(float(month)))
        for month, count in ((7, 400), (8, 800), (9, 800), (10, 12))
        for _ in range(count)
    ]
    parts = quarter_parts(stamped)
    assert [len(part) for part in parts] == [400, 800, 812]
    assert parts[-1][-1].close == 10.0


def test_year_skips_a_thin_month_and_rests_between_seasons():
    stamped = [
        (date(2026, month, 1), Bar(float(month)))
        for month in range(1, 13)
        for _ in range(10 if month == 3 else 40)
    ]
    movements = prepare_year(stamped)
    assert [item.label for item in movements] == [
        "01/26", "02/26", "04/26", "05/26", "06/26", "07/26", "08/26", "09/26", "10/26", "11/26", "12/26"
    ]
    february = movements[1]
    assert february.rest_after == 8.0
    assert movements[-1].rest_after == 0.0
    assert movements[-1].spec.bars == 112


def test_borrowed_chords_follow_the_regime_and_miss_the_downbeat():
    assert _borrowed_allowed(FDIM7, "sideway", phrase_downbeat=True) is False
    assert _borrowed_allowed(FDIM7, "sideway", phrase_downbeat=False) is True
    assert _borrowed_allowed(FDIM7, "uptrend", phrase_downbeat=False) is False
    assert _borrowed_allowed(BM7B5, "downtrend", phrase_downbeat=False) is True
    assert _borrowed_allowed(C, "uptrend", phrase_downbeat=True) is True
    assert _borrowed_allowed(A7, "sideway", phrase_downbeat=False) is True
    assert _borrowed_allowed(A7, "uptrend", phrase_downbeat=False) is False


def test_a_borrowed_hold_is_not_cheaper_than_staying_on_f():
    # The second bar uses a fixed stay cost. From the third bar on, the borrowed
    # self-probability matches F's root stay, so a borrowed chord is not parked
    # for many bars just because staying was free.
    borrowed = -TRANSITION_WEIGHT * math.log(BORROWED_HOLD_PROB) + EXTENDED_STAY_PENALTY
    diatonic_f = -TRANSITION_WEIGHT * math.log(0.16) + EXTENDED_STAY_PENALTY
    assert borrowed == diatonic_f
    assert borrowed > EXTENDED_STAY_PENALTY


def test_a_chromatic_shared_tone_does_not_stop_the_melody():
    scale = c_major_scale()
    held = [67] * 16
    snapped = quantize_strong_beats(held, {0: BF, 1: EF}, scale)
    assert all(note % 12 in {0, 2, 4, 5, 7, 9, 11} for note in snapped)
    assert snapped[0] % 12 in BF.pitch_classes
    assert snapped[8] % 12 in EF.pitch_classes
    index_of = {note: index for index, note in enumerate(scale)}
    _breaks_held_note_across_barline(67, BF, EF, scale, index_of)


def test_bass_fifth_is_perfect_on_c_and_diminished_on_b_half_diminished():
    assert fifth_above_bass(C) == C.bass_midi + 7
    assert fifth_above_bass(BM7B5) == BM7B5.bass_midi + 6


def test_slice_rebases_bars_and_drops_ties_that_cross_the_cut():
    score = Score(
        title="movement",
        bpm=90,
        bars=4,
        regimes=("sideway", "sideway", "sideway"),
        regime_samples=None,
        slots=(),
        high=(),
        lead=(
            NoteEvent(bar=0, beat=0, midi=60, duration_beats=1, voice=1, tie_start=True),
            NoteEvent(bar=1, beat=0, midi=60, duration_beats=1, voice=1, tie_stop=True, tie_start=True),
            NoteEvent(bar=2, beat=0, midi=62, duration_beats=1, voice=1),
        ),
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
    )
    chunk = slice_score(score, 0, 2)
    assert chunk.bars == 2
    assert [note.bar for note in chunk.lead] == [0, 1]
    assert chunk.lead[0].tie_start is True
    assert chunk.lead[1].tie_start is False
    assert chunk.lead[1].tie_stop is True


def test_fifth_week_folds_into_the_finale():
    mondays = [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26), date(2026, 2, 2)]
    sessions = [(day, [Bar(10.0 + index)]) for index, day in enumerate(mondays)]
    parts = month_parts(sessions)
    assert len(parts) == 4
    assert len(parts[-1]) == 2


def test_year_keeps_both_octobers_in_time_order():
    stamped = [(date(2025, 10, day), Bar(20.0)) for day in range(1, 32)]
    stamped += [(date(2026, 10, day), Bar(30.0)) for day in range(1, 32)]
    stamped += [(date(2026, 11, 1), Bar(31.0))]
    movements = prepare_year(stamped)
    assert [item.label for item in movements] == ["10/25", "10/26"]
    assert movements[0].bars[0].close == 20.0
    assert movements[1].bars[0].close == 30.0
    assert movements[0].rest_after == 8.0


def test_a_week_launches_musescore_once(tmp_path):
    calls: list[str] = []

    def export(xml, wav) -> None:
        calls.append(xml.name)
        write_wav(wav, 1, 8000, array("h", [1000] * 800))

    store = RecapStore(tmp_path, exporter=export)
    movement = prepare_week(
        [
            [Bar(10.0 + index * 0.1) for index in range(20)],
            [Bar(12.0 + index * 0.1) for index in range(20)],
        ]
    )[0]
    asset = store.ensure_movement("MBB", "1W", 0, "symphony", movement)
    assert len(calls) == 1
    assert asset.audio_path.is_file()


def test_week_score_uses_the_shared_series_and_the_week_form():
    sessions = [
        [Bar(10.0 + index * 0.2, volume=float(index + 1)) for index in range(31)],
        [Bar(12.0 + index * 0.2, volume=float(index + 1)) for index in range(32)],
    ]
    prepared = prepare_week(sessions)
    score = render(
        prepared[0].bars,
        title="week",
        variant="symphony",
        form=prepared[0].spec,
        source_groups=prepared[0].groups,
    )
    assert score.bars == 64
    assert score.bpm == 90
    assert len(prepared[0].groups) == 64
    assert prepared[0].groups[31] == []


def test_join_keeps_float_samples_audible():
    rate = 1000
    first = array("f", [0.5] * 100)
    second = array("f", [0.25] * 100)
    _channels, _rate, joined = join_chunks(
        [(1, rate, first), (1, rate, second)],
        [0.05, 0.1],
        crossfade_seconds=0.01,
    )
    assert joined.typecode == "f"
    assert max(joined) > 0.2


def test_join_trims_the_tail_of_every_chunk_but_the_last():
    rate = 1000
    first = array("h", [1000] * 2000 + [9] * 500)
    second = array("h", [2000] * 2000 + [8] * 800)
    _channels, _rate, joined = join_chunks(
        [(1, rate, first), (1, rate, second)],
        [2.0, 2.0],
        crossfade_seconds=0.0,
    )
    assert len(joined) == 2000 + 2800
    assert joined[1999] == 1000
    assert joined[-1] == 8
