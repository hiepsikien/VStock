"""Long-form geometry stays off the 30-bar daily path."""

import asyncio
import math
from array import array
from datetime import date, datetime
from pathlib import Path

from app.sonify.audio import RecapStore, SpanAsset, join_chunks, write_wav
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
from app.sonify.form import FormSection, FormSpec, METER_44
from app.sonify.session import SessionPoint
from app.sonify.span import (
    attach_frame,
    quarter_parts,
    month_parts,
    month_specs,
    plan_month,
    prepare_month,
    prepare_quarter,
    prepare_week,
    prepare_year,
    plan_week,
    quarter_specs,
    retarget_torroba_meter,
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


def test_span_response_volumes_match_each_movement(monkeypatch) -> None:
    import asyncio

    from app.routers.stocks import get_span
    from app.services.spans import SpanPlan

    sessions = [
        (date(2026, 1, 5), [Bar(10.0, 100.0), Bar(10.4, 0.0)]),
        (date(2026, 1, 6), [Bar(11.0, 40.0)]),
        (date(2026, 1, 7), [Bar(11.5)]),
        (date(2026, 1, 8), [Bar(12.0, 5.0), Bar(12.2, 8.0)]),
    ]
    movements = prepare_month(sessions, "VNM")

    async def fake_plan(*_args, **_kwargs):
        return SpanPlan(movements, date(2026, 1, 8))

    monkeypatch.setattr("app.routers.stocks.plan_span", fake_plan)
    monkeypatch.setattr("app.routers.stocks.ready_movement", lambda *_args, **_kwargs: None)
    response = asyncio.run(get_span("vnm", "1M", "symphony", "classic", True, True))
    assert len(response.movements) == len(movements)
    from app.services.spans import movement_duration

    for row, movement in zip(response.movements, movements, strict=True):
        written = round(movement_duration(movement), 3)
        assert len(row.volumes) == len(row.prices)
        assert row.prices == [round(bar.close, 2) for bar in movement.bars]
        assert row.volumes == [round(float(bar.volume), 4) for bar in movement.bars]
        assert row.durationSec == written
        assert row.mapDurationSec == written

    class Cached:
        duration_sec = 263.0
        map_duration_sec = 260.0
        movement_name = ""

    monkeypatch.setattr("app.routers.stocks.ready_movement", lambda *_args, **_kwargs: Cached())
    cached = asyncio.run(get_span("vnm", "1M", "symphony", "classic", True, True))
    assert cached.movements[0].durationSec == 263.0
    assert cached.movements[0].mapDurationSec == 260.0


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


def _meter(spec) -> tuple[int, int]:
    return spec.meter.beats, spec.meter.beat_type


def _frame_lengths(spec) -> tuple[int, int]:
    warm = next(section for section in spec.sections if section.kind == "warmup")
    cool = next(section for section in spec.sections if section.kind == "cooldown")
    return warm.end - warm.start, cool.end - cool.start


def _fingerprint_meter(movement) -> tuple[int, int]:
    _key, _mode, _character, _coda, beats, beat_type, *_rest = movement.scale_fingerprint.split("-")
    return int(beats), int(beat_type)


def _line(start: float, end: float, count: int) -> list[Bar]:
    step = (end - start) / (count - 1)
    return [Bar(start + step * index) for index in range(count)]


def _flat(price: float, count: int) -> list[Bar]:
    return [Bar(price) for _ in range(count)]


def _week_of(day: int, bars: list[Bar]) -> tuple[date, list[Bar]]:
    return date(2026, 1, day), bars


def test_torroba_meter_follows_character_and_keeps_tempo() -> None:
    body = month_specs("guitar")[0]
    assert (_meter(body), body.bpm) == ((4, 4), 96)
    calm = retarget_torroba_meter(body, "calm")
    selloff = retarget_torroba_meter(body, "selloff")
    assert (_meter(calm), calm.bpm) == ((3, 4), 96)
    assert (_meter(selloff), selloff.bpm) == ((3, 4), 96)
    assert retarget_torroba_meter(body, "rally") == body
    assert retarget_torroba_meter(body, "volatile") == body
    slow = month_specs("guitar")[1]
    scherzo = month_specs("guitar")[2]
    assert _meter(slow) == (3, 4)
    assert _meter(scherzo) == (6, 8)
    assert retarget_torroba_meter(slow, "rally") == slow
    assert retarget_torroba_meter(scherzo, "selloff") == scherzo


def test_torroba_month_frames_after_the_meter_change() -> None:
    sessions = [
        _week_of(5, _flat(100.0, 8)),
        _week_of(12, _line(100.0, 110.0, 8)),
        _week_of(19, _flat(100.0, 8)),
        _week_of(26, _line(100.0, 103.0, 8)),
    ]
    torroba = prepare_month(sessions, "VNM", "guitar", "torroba")
    classic = prepare_month(sessions, "VNM", "guitar", "classic")
    symphony = prepare_month(sessions, "VNM", "symphony", "torroba")
    bodies = month_specs("guitar")
    assert [movement.character for movement in torroba] == ["calm", "rally", "calm", "rally"]
    assert _meter(torroba[0].spec) == (3, 4)
    assert torroba[0].spec.bpm == 96
    assert _frame_lengths(torroba[0].spec) == (6, 6)
    assert torroba[0].spec.bars == bodies[0].bars + 12
    assert _fingerprint_meter(torroba[0]) == (3, 4)
    assert torroba[1].spec == attach_frame(bodies[1], "1M")
    assert torroba[1].spec.bpm == 72
    assert torroba[2].spec == attach_frame(bodies[2], "1M")
    assert _meter(torroba[2].spec) == (6, 8)
    assert torroba[3].spec == attach_frame(bodies[3], "1M")
    assert (_meter(torroba[3].spec), torroba[3].spec.bpm) == ((4, 4), 96)
    assert _frame_lengths(torroba[3].spec) == (4, 4)
    assert _fingerprint_meter(torroba[3]) == (4, 4)
    assert [movement.spec for movement in classic] == [
        movement.spec for movement in plan_month([len(part) for part in month_parts(sessions)], "guitar")
    ]
    assert _meter(symphony[0].spec) == (4, 4)


def test_torroba_quarter_and_year_use_the_frame_of_the_new_meter() -> None:
    stamped = [
        (date(2026, month, 1), bar)
        for month, bars in (
            (7, _line(100.0, 90.0, 160)),
            (8, _line(100.0, 110.0, 160)),
            (9, [Bar(100.0 if index % 2 == 0 else 108.0) for index in range(159)] + [Bar(101.0)]),
        )
        for bar in bars
    ]
    quarter = prepare_quarter(stamped, "VNM", "guitar", "torroba")
    bodies = quarter_specs("guitar")
    assert [movement.character for movement in quarter] == ["selloff", "rally", "volatile"]
    assert _meter(quarter[0].spec) == (3, 4)
    assert quarter[0].spec.bpm == 96
    assert _frame_lengths(quarter[0].spec) == (6, 6)
    assert quarter[0].spec.bars == bodies[0].bars + 12
    assert quarter[1].spec == attach_frame(bodies[1], "3M")
    assert _meter(quarter[1].spec) == (3, 4)
    assert quarter[1].spec.bpm == 60
    assert quarter[2].spec == attach_frame(bodies[2], "3M")
    assert (_meter(quarter[2].spec), quarter[2].spec.bpm) == ((4, 4), 108)
    assert _frame_lengths(quarter[2].spec) == (4, 4)
    plain = prepare_quarter(stamped, "VNM", "guitar", "barrios")
    assert plain[0].spec == attach_frame(bodies[0], "3M")

    year_stamped = [
        (date(2026, 1, 1), Bar(100.0)),
    ] * 40 + [
        (date(2026, 2, 1), bar) for bar in _line(100.0, 110.0, 40)
    ] + [
        (date(2026, 12, 1), bar) for bar in _line(100.0, 110.0, 40)
    ]
    year = prepare_year(year_stamped, "VNM", "guitar", "torroba")
    specs = year_specs("guitar")
    assert [movement.label for movement in year] == ["01/26", "02/26", "12/26"]
    assert [movement.character for movement in year] == ["calm", "rally", "rally"]
    assert _meter(year[0].spec) == (3, 4)
    assert year[0].spec.bpm == 100
    assert _frame_lengths(year[0].spec) == (3, 3)
    assert year[0].spec.bars == specs[0].bars + 6
    assert year[1].spec == attach_frame(specs[1], "1Y")
    assert _meter(year[1].spec) == (3, 4)
    assert year[2].spec == attach_frame(specs[11], "1Y")
    assert (_meter(year[2].spec), year[2].spec.bpm) == ((4, 4), 96)
    assert _frame_lengths(year[2].spec) == (2, 2)
    untouched = prepare_year(year_stamped, "VNM", "guitar", "bach")
    assert untouched[0].spec == attach_frame(specs[0], "1Y")
    assert untouched[-1].spec.bars == 112


def test_torroba_week_uses_the_opening_session_and_has_no_frame() -> None:
    calm = _flat(100.0, 8)
    rally = _line(100.0, 110.0, 8)
    opening_calm = prepare_week([calm, rally], "VNM", variant="guitar", ensemble="torroba")[0]
    assert opening_calm.session_characters[0] == "calm"
    assert opening_calm.character == "rally"
    assert _meter(opening_calm.spec) == (3, 4)
    assert opening_calm.spec.bpm == 90
    assert opening_calm.spec.bars == week_spec(2).bars
    assert all(section.kind != "warmup" for section in opening_calm.spec.sections)
    assert _fingerprint_meter(opening_calm) == (3, 4)

    crash = _line(104.0, 90.0, 8)
    opening_rally = prepare_week([_line(100.0, 104.0, 8), crash], variant="guitar", ensemble="torroba")[0]
    assert opening_rally.session_characters[0] == "rally"
    assert opening_rally.character == "selloff"
    assert _meter(opening_rally.spec) == (4, 4)
    assert _fingerprint_meter(opening_rally) == (4, 4)

    classic = prepare_week([calm, rally], variant="guitar", ensemble="classic")[0]
    assert _meter(classic.spec) == (4, 4)
    assert classic.spec.bars == week_spec(2).bars


def test_daily_torroba_changes_meter_without_a_frame_or_a_passed_form(monkeypatch) -> None:
    seen: list[object] = []
    import app.sonify.guitar as guitar

    real = guitar.render_guitar_score

    def spy(**kwargs):
        seen.append(kwargs.get("movement_index", "ABSENT"))
        kwargs.pop("movement_index", None)
        return real(**kwargs)

    monkeypatch.setattr(guitar, "render_guitar_score", spy)
    bars = _flat(100.0, 12)
    calm = render(bars, variant="guitar", ensemble="torroba", character="calm", movement_index=0)
    rally = render(bars, variant="guitar", ensemble="torroba", character="rally", movement_index=0)
    selloff = render(bars, variant="guitar", ensemble="torroba", character="selloff", movement_index=0)
    other = render(bars, variant="guitar", ensemble="classic", character="calm", movement_index=0)
    assert (calm.bars, calm.beats, calm.beat_type) == (34, 3, 4)
    assert (rally.bars, rally.beats, rally.beat_type) == (34, 4, 4)
    assert (selloff.bars, selloff.beats, selloff.beat_type) == (34, 3, 4)
    assert (other.bars, other.beats, other.beat_type) == (34, 4, 4)
    held = FormSpec(
        bars=8,
        bpm=96,
        sections=(
            FormSection(0, 8, "phrase", 0),
        ),
        chunks=(8,),
        meter=METER_44,
    )
    kept = render(
        bars,
        variant="guitar",
        ensemble="torroba",
        character="calm",
        form=held,
        framed=False,
        movement_index=3,
    )
    assert (kept.bars, kept.beats, kept.beat_type) == (8, 4, 4)
    assert seen == [0, 0, 0, 0, 3]


def test_audio_passes_movement_index(monkeypatch, tmp_path) -> None:
    seen: list[object] = []
    import app.sonify.audio as audio

    real = audio.render

    def spy(*args, **kwargs):
        seen.append(kwargs["movement_index"])
        return real(*args, **kwargs)

    monkeypatch.setattr(audio, "render", spy)

    def export(xml, wav) -> None:
        write_wav(wav, 1, 8000, array("h", [1000] * 800))

    store = RecapStore(tmp_path, exporter=export)
    movement = prepare_week([[Bar(10.0), Bar(10.1)]], "MBB")[0]
    store.ensure_movement("MBB", "1W", 0, "symphony", movement)
    store.ensure_movement("MBB", "1M", 2, "symphony", movement)
    store.ensure("MBB", date(2026, 1, 5), "symphony", [Bar(10.0), Bar(10.4)])
    assert seen == [0, 2, 0]


def _stub_span_io(monkeypatch) -> None:
    async def fake_fetch(*_args, **_kwargs):
        return {}

    monkeypatch.setattr("app.services.spans.fetch_ohlc", fake_fetch)
    monkeypatch.setattr("app.services.spans.fetch_minute_payload", fake_fetch)
    monkeypatch.setattr("app.services.spans.payload_truncated", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("app.services.spans.samples_from_ohlc", lambda _payload: [(0, 100.0, 1.0)])


def test_plan_span_forwards_ensemble(monkeypatch) -> None:
    from app.services.spans import plan_span

    _stub_span_io(monkeypatch)
    monkeypatch.setattr(
        "app.services.spans.session_dates",
        lambda _samples, limit=7: [date(2026, 1, day) for day in (5, 6)],
    )
    monkeypatch.setattr(
        "app.sonify.session.session_points",
        lambda _samples, day: [
            SessionPoint(datetime(day.year, day.month, day.day, 9, 20), Bar(100.0)),
            SessionPoint(datetime(day.year, day.month, day.day, 9, 21), Bar(100.0)),
        ],
    )
    week = asyncio.run(plan_span("VNM", "1W", "guitar", "torroba"))
    classic_week = asyncio.run(plan_span("VNM", "1W", "guitar", "classic"))
    assert _meter(week.movements[0].spec) == (3, 4)
    assert _meter(classic_week.movements[0].spec) == (4, 4)
    assert all(section.kind != "warmup" for section in week.movements[0].spec.sections)

    monkeypatch.setattr(
        "app.services.spans.session_dates",
        lambda _samples, limit=7: [date(2026, 1, day) for day in (5, 6, 7, 8)],
    )
    monkeypatch.setattr(
        "app.services.spans.session_bars",
        lambda _samples, _day: [Bar(100.0), Bar(100.0)],
    )
    month = asyncio.run(plan_span("VNM", "1M", "guitar", "torroba"))
    classic_month = asyncio.run(plan_span("VNM", "1M", "guitar", "bach"))
    assert _meter(month.movements[0].spec) == (3, 4)
    assert _frame_lengths(month.movements[0].spec) == (6, 6)
    assert _meter(classic_month.movements[0].spec) == (4, 4)

    monkeypatch.setattr(
        "app.services.spans.coarse_bars",
        lambda _samples: [
            (date(2026, 7, 1), Bar(100.0)),
            (date(2026, 8, 1), Bar(100.0)),
            (date(2026, 9, 1), Bar(100.0)),
        ],
    )
    quarter = asyncio.run(plan_span("VNM", "3M", "guitar", "torroba"))
    assert _meter(quarter.movements[0].spec) == (3, 4)
    assert _frame_lengths(quarter.movements[0].spec) == (6, 6)

    monkeypatch.setattr(
        "app.services.spans.coarse_bars",
        lambda _samples: [(date(2026, 1, 1), Bar(100.0)) for _ in range(30)],
    )
    year = asyncio.run(plan_span("SSI", "1Y", "guitar", "torroba"))
    plain_year = asyncio.run(plan_span("SSI", "1Y", "guitar", "classic"))
    assert _meter(year.movements[0].spec) == (3, 4)
    assert _frame_lengths(year.movements[0].spec) == (3, 3)
    assert _meter(plain_year.movements[0].spec) == (4, 4)
    assert _frame_lengths(plain_year.movements[0].spec) == (2, 2)


def test_span_routes_forward_ensemble(monkeypatch) -> None:
    from app.routers.stocks import get_span
    from app.services.spans import SpanPlan, load_movement_audio

    sessions = [
        (date(2026, 1, day), [Bar(10.0), Bar(10.1)])
        for day in (5, 6, 7, 8)
    ]
    movements = prepare_month(sessions, "VNM")
    seen: dict[str, object] = {}

    async def fake_plan(symbol, span, variant="symphony", ensemble="classic"):
        seen["plan"] = (symbol, span, variant, ensemble)
        return SpanPlan(movements, date(2026, 1, 8))

    monkeypatch.setattr("app.routers.stocks.plan_span", fake_plan)
    monkeypatch.setattr("app.routers.stocks.ready_movement", lambda *_args, **_kwargs: None)
    asyncio.run(get_span("vnm", "1M", "guitar", "torroba", True, True))
    assert seen["plan"] == ("VNM", "1M", "guitar", "torroba")

    async def fake_service_plan(symbol, span, variant="symphony", ensemble="classic"):
        seen["audio"] = (symbol, span, variant, ensemble)
        return SpanPlan(movements, date(2026, 1, 8))

    class Store:
        def ensure_movement(self, *args, **kwargs):
            seen["ensure"] = args[6] if len(args) > 6 else kwargs.get("ensemble")
            return SpanAsset(
                symbol="VNM",
                span="1M",
                index=0,
                variant="guitar",
                audio_path=Path("unused.m4a"),
                duration_sec=1.0,
                map_duration_sec=1.0,
                peaks=[],
                bar_count=1,
                media_type="audio/mp4",
                fingerprint="x",
            )

    monkeypatch.setattr("app.services.spans.plan_span", fake_service_plan)
    monkeypatch.setattr("app.services.spans.recap_store", lambda: Store())
    asyncio.run(load_movement_audio("VNM", "1M", 0, "guitar", None, "torroba"))
    assert seen["audio"] == ("VNM", "1M", "guitar", "torroba")
    assert seen["ensure"] == "torroba"
