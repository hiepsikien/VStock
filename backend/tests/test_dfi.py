"""DFI: the price line must stay readable through the writing, not just sound nice."""

from __future__ import annotations

import math
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import stocks
from app.schemas import DfiBreakdown as DfiBreakdownSchema
from app.schemas import RecapResponse
from app.services import dfi as dfi_service
from app.sonify import dfi as dfi_module
from app.sonify.model import Bar, NoteEvent, PriceTracePoint
from app.sonify.dfi import (
    DFI_VERSION,
    MOTION_ON_ANCHORS,
    DfiBreakdown,
    _Point,
    _band,
    _coverage,
    _motion,
    _overlaps,
    _shape,
    _volume,
    compute,
    fill_trace_from_notes,
    motion_points,
    trace_from_notes,
)
from app.sonify.render import render


def _bars(trend: float = 0.4) -> list[Bar]:
    return [
        Bar(close=100 + index * trend + math.sin(index / 2) * 0.8, volume=1000 + index * 50)
        for index in range(32)
    ]


def _points(prices: list[float], pitches: list[float | None]) -> list[_Point]:
    return [
        _Point(eighth=index, price=price, pitch=pitch, window=0, phrase=0)
        for index, (price, pitch) in enumerate(zip(prices, pitches))
    ]


def test_band_edges_speak_the_same_vocabulary() -> None:
    assert _band(100) == "very-clear"
    assert _band(85) == "very-clear"
    assert _band(84.9) == "clear"
    assert _band(70) == "clear"
    assert _band(69.9) == "fair"
    assert _band(55) == "fair"
    assert _band(54.9) == "faint"
    assert _band(40) == "faint"
    assert _band(39.9) == "very-faint"


def test_shape_rewards_the_written_contour() -> None:
    prices = [10.0, 11.0, 12.0, 13.0, 14.0]
    aligned = _points(prices, [60.0, 62.0, 64.0, 65.0, 67.0])
    inverted = _points(prices, [67.0, 65.0, 64.0, 62.0, 60.0])
    aligned_score, aligned_weight = _shape(aligned, eps=0.1)
    inverted_score, inverted_weight = _shape(inverted, eps=0.1)
    assert aligned_score == 1.0
    assert inverted_score == 0.0
    assert aligned_weight == inverted_weight == 5.0


def test_shape_returns_nothing_when_price_did_not_move() -> None:
    flat = _points([10.0] * 5, [60.0, 61.0, 60.0, 61.0, 60.0])
    assert _shape(flat, eps=0.1) == (None, 0.0)


def test_motion_reads_step_size_not_only_direction() -> None:
    prices = [10.0, 11.0, 13.0, 16.0, 20.0]
    matching = _points(prices, [60.0, 61.0, 63.0, 66.0, 70.0])
    frozen = _points(prices, [64.0, 64.0, 64.0, 64.0, 64.0])
    matching_score, _weight, low = _motion(matching, eps=0.1)
    frozen_score, _frozen_weight, _ = _motion(frozen, eps=0.1)
    assert matching_score == 1.0
    assert frozen_score == 0.0
    assert low is False


def test_motion_ignores_eighths_where_neither_price_nor_pitch_moved() -> None:
    # The eighths between two source bars repeat both price and pitch. They
    # are not holds over a moving price; counting them as ties used to pull a
    # perfect rank correlation down to ~0.27.
    prices = [10.0, 10.0, 11.0, 11.0, 13.0, 13.0, 16.0, 16.0, 20.0]
    pitches = [60.0, 60.0, 61.0, 61.0, 63.0, 63.0, 66.0, 66.0, 70.0]
    score, weight, _low = _motion(_points(prices, pitches), eps=0.0)
    assert score == 1.0
    assert weight == 4.0


def test_shape_scores_zero_when_the_line_holds_one_note() -> None:
    prices = [10.0, 11.0, 13.0, 16.0, 20.0]
    held = _points(prices, [64.0] * len(prices))
    score, weight = _shape(held, eps=0.1)
    assert score == 0.0
    assert weight == 5.0


def test_coverage_skips_bars_before_the_line_enters() -> None:
    score = SimpleNamespace(
        source_closes=(10.0, 11.0, 12.0),
        source_groups=((0,), (1,), (2,)),
        price_trace=(PriceTracePoint(bar=1, beat=0.0, price=0.0, pitch=60, duration_beats=4.0),),
        bar_beats=4.0,
    )
    coverage, _detail = _coverage(
        score,
        frozenset(),
        [(0, 3)],
        {0: 0.1},
        0.1,
        [],
        lambda _eighth: 60.0,
        2,
    )
    assert coverage == 1.0


def test_coverage_still_punishes_a_rest_inside_the_line() -> None:
    score = SimpleNamespace(
        source_closes=(10.0, 11.0, 12.0),
        source_groups=((0,), (1,), (2,)),
        price_trace=(
            PriceTracePoint(bar=0, beat=0.0, price=0.0, pitch=60, duration_beats=4.0),
            PriceTracePoint(bar=2, beat=0.0, price=0.0, pitch=62, duration_beats=4.0),
        ),
        bar_beats=4.0,
    )
    coverage, _detail = _coverage(
        score,
        frozenset(),
        [(0, 3)],
        {0: 0.1},
        0.1,
        [],
        lambda _eighth: 60.0,
        2,
    )
    assert 0.4 < coverage < 0.7


def test_coverage_does_not_shrink_to_a_partial_trace() -> None:
    source_count = 20
    score = SimpleNamespace(
        source_closes=tuple(10.0 + index * 0.1 for index in range(source_count)),
        source_groups=tuple((index,) for index in range(source_count)),
        price_trace=tuple(
            PriceTracePoint(
                bar=bar,
                beat=0.0,
                price=10.0 + bar * 0.1,
                pitch=60 + bar,
                duration_beats=4.0,
            )
            for bar in range(15, 20)
        ),
        bar_beats=4.0,
    )
    coverage, _detail = _coverage(
        score,
        frozenset(),
        [(0, source_count)],
        {0: 0.01},
        0.01,
        [],
        lambda _eighth: 60.0,
        2,
    )
    assert coverage < 0.8


def test_coverage_rejects_a_trace_that_only_covers_the_middle() -> None:
    source_count = 34
    score = SimpleNamespace(
        source_closes=tuple(10.0 + index * 0.05 for index in range(source_count)),
        source_groups=tuple((index,) for index in range(source_count)),
        price_trace=tuple(
            PriceTracePoint(
                bar=bar,
                beat=0.0,
                price=10.0 + bar * 0.05,
                pitch=60 + bar,
                duration_beats=4.0,
            )
            for bar in range(12, 23)
        ),
        bar_beats=4.0,
    )
    coverage, _detail = _coverage(
        score,
        frozenset(),
        [(0, source_count)],
        {0: 0.001},
        0.001,
        [],
        lambda _eighth: 60.0,
        2,
    )
    assert coverage < 0.8


def test_overlaps_sees_a_short_note_at_the_start_of_a_long_bar() -> None:
    # A sixteenth-note trace point at the start of a whole bar must count.
    # Scanning back from `end - max_span` skipped it and collapsed guitar
    # coverage.
    items = [(0.1, 0.15, None)]
    assert _overlaps(items, [0.1], 0.05, 0.0, 1.0)


def test_symphony_and_jazz_trace_the_lower_line_voice() -> None:
    # melody_parts splits the price line between violin + cello (symphony) and
    # alto + tenor (jazz). A downtrend puts the line in the lower voice; Shape
    # and Motion must see those bars, not just score.lead.
    bars = [
        Bar(close=100.0 - index * 1.5, volume=1000.0 + index * 100.0)
        for index in range(32)
    ]
    for variant in ("symphony", "jazz"):
        score = render(bars, variant=variant, ensemble="classic")  # type: ignore[arg-type]
        trace_bars = {point.bar for point in score.price_trace if point.pitch is not None}
        lead_bars = {note.bar for note in score.lead if note.midi is not None}
        support_bars = {note.bar for note in score.support if note.midi is not None}
        support_only = support_bars - lead_bars
        assert support_only, variant
        assert support_only & trace_bars, variant


def test_ready_movement_hides_dfi_when_the_bars_moved(monkeypatch) -> None:
    from pathlib import Path

    from app.services import spans as spans_service
    from app.sonify.audio import SpanAsset
    from app.sonify.dfi import DFI_VERSION, data_digest

    bars = [Bar(close=10.0, volume=100.0), Bar(close=11.0, volume=200.0)]
    asset = SpanAsset(
        symbol="AAM",
        span="3M",
        index=0,
        variant="jazz",
        audio_path=Path("x.m4a"),
        duration_sec=1.0,
        map_duration_sec=1.0,
        peaks=[],
        bar_count=2,
        media_type="audio/mp4",
        fingerprint="f",
        dfi={"score": 50.0},
        dfi_inputs="stale",
    )

    class Store:
        def get_movement(self, *_args, **_kwargs):
            return asset

    monkeypatch.setattr(spans_service, "recap_store", lambda: Store())
    movement = SimpleNamespace(candle_count=2, scale_fingerprint="f", bars=bars)
    stale = spans_service.ready_movement("AAM", "3M", 0, "jazz", movement)
    assert stale is not None and stale.dfi is None

    fresh = SpanAsset(
        **{
            **asset.__dict__,
            "dfi_inputs": data_digest(bars),
            "dfi_checked": DFI_VERSION,
        }
    )
    monkeypatch.setattr(Store, "get_movement", lambda self, *_a, **_k: fresh)
    kept = spans_service.ready_movement("AAM", "3M", 0, "jazz", movement)
    assert kept is not None and kept.dfi == {"score": 50.0}


def test_volume_hears_the_printed_dynamic() -> None:
    bars = [
        Bar(close=100 + math.sin(index / 3) * 2 + index * 0.1, volume=100 + index * 40)
        for index in range(80)
    ]
    score = render(bars, variant="symphony", ensemble="classic")
    value = _volume(score)
    assert value is not None
    assert value > 0.5



def test_trace_extends_a_tied_price_note_and_skips_off_grid_ornaments() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=2.0, voice=1, tie_start=True),
        NoteEvent(bar=0, beat=2.0, midi=67, duration_beats=1.0, voice=1, tie_stop=True),
        NoteEvent(bar=0, beat=3.25, midi=69, duration_beats=0.25, voice=1),
        NoteEvent(bar=1, beat=0.0, midi=64, duration_beats=1.0, voice=1),
    ]
    trace = trace_from_notes(
        notes,
        line=[67, 67, 67, 67, 67, 67, 67, 67],
        prices=[10.0] * 8,
        epb=8,
        bar_beats=4.0,
    )
    assert len(trace) == 1
    assert trace[0].bar == 0 and trace[0].beat == 0.0
    assert trace[0].duration_beats == 3.0
    assert trace[0].pitch == 67.0


def test_trace_drops_frame_bars() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=1.0, voice=1),
        NoteEvent(bar=2, beat=0.0, midi=72, duration_beats=1.0, voice=1),
    ]
    trace = trace_from_notes(
        notes,
        line=[67] * 8 + [67] * 8 + [72] * 8,
        prices=[10.0] * 24,
        epb=8,
        bar_beats=4.0,
        frame_bars=frozenset({2}),
    )
    assert [point.bar for point in trace] == [0]


def test_every_variant_writes_a_trace_and_scores_it() -> None:
    bars = _bars()
    for variant in ("symphony", "jazz", "minimalist", "ambient", "guitar"):
        ensemble = "bach" if variant == "guitar" else "classic"
        score = render(bars, variant=variant, ensemble=ensemble)
        assert score.price_trace, variant
        assert score.price_eighths, variant
        assert score.source_closes, variant
        breakdown = compute(score, variant=variant, ensemble=ensemble)
        assert breakdown is not None, variant
        assert 0 <= breakdown.score <= 100
        assert breakdown.n_moves >= 4
        assert breakdown.coverage > 0


def test_flat_session_returns_none_not_zero() -> None:
    flat = [Bar(close=100.0, volume=1000.0) for _ in range(32)]
    score = render(flat, variant="symphony", ensemble="classic")
    assert compute(score, variant="symphony", ensemble="classic") is None


def test_non_guitar_ensembles_keep_the_same_chart_clarity() -> None:
    bars = _bars()
    rows = {
        "symphony": ("classic", "wood", "brass"),
        "jazz": ("classic", "soul", "organ"),
        "minimalist": ("classic", "mallet", "guitar"),
        "ambient": ("classic", "breath", "choir"),
    }
    for variant, ensembles in rows.items():
        scores = []
        for ensemble in ensembles:
            breakdown = compute(
                render(bars, variant=variant, ensemble=ensemble),  # type: ignore[arg-type]
                variant=variant,
                ensemble=ensemble,
            )
            assert breakdown is not None, (variant, ensemble)
            scores.append(breakdown.score)
        # The trace now records the intended line, so the score spread is 0 by
        # design; this still catches a trace that drifts between ensembles.
        # `test_same_trace_across_symphony_ensembles` guards the audible contour.
        assert max(scores) - min(scores) <= 2, (variant, scores)


def test_guitar_ensembles_do_not_lose_the_line_to_register_choices() -> None:
    sessions = {
        "calm": _bars(),
        "volatile": [
            Bar(close=100.0 + (8.0 if index % 2 else -8.0) + index * 0.3, volume=1000.0 + index * 300.0)
            for index in range(32)
        ],
        "down": [
            Bar(close=140.0 - index * 2.0, volume=1000.0 + index * 100.0)
            for index in range(32)
        ],
    }
    for name, bars in sessions.items():
        for ensemble in ("bach", "classic", "villa", "barrios", "brouwer", "torroba"):
            breakdown = compute(
                render(bars, variant="guitar", ensemble=ensemble),  # type: ignore[arg-type]
                variant="guitar",
                ensemble=ensemble,
            )
            assert breakdown is not None, (name, ensemble)
            assert breakdown.coverage > 0.95, (name, ensemble, breakdown.coverage)


def test_recap_response_parses_the_breakdown() -> None:
    payload = {
        "symbol": "VNM",
        "date": "2026-11-02",
        "variant": "symphony",
        "ensemble": "classic",
        "durationSec": 120.0,
        "mapDurationSec": 119.0,
        "barCount": 32,
        "peaks": [0.5],
        "audioUrl": "/audio.m4a",
        "dfi": {
            "score": 78.0,
            "band": "clear",
            "shape": 0.84,
            "motion": 0.71,
            "structure": 0.76,
            "resolution": 0.63,
            "volume": 0.74,
            "coverage": 0.93,
            "coverage_detail": 0.9,
            "opportunity": 1.0,
            "confidence": "high",
            "n_moves": 30,
            "n_sounding": 60,
            "motion_pairs": 44,
            "version": "1",
        },
    }
    response = RecapResponse(**payload)
    assert response.dfi is not None
    assert response.dfi.score == 78.0
    assert response.dfi.band == "clear"
    assert response.dfi.motion_pairs == 44


def _breakdown(score: float) -> DfiBreakdown:
    return DfiBreakdown(
        score=score,
        band=_band(score),
        shape=0.8,
        motion=0.7,
        structure=0.7,
        resolution=0.7,
        volume=0.6,
        coverage=0.9,
        coverage_detail=0.9,
        opportunity=1.0,
        confidence="high",
        n_moves=30,
        n_sounding=60,
    )


def test_pieces_endpoint_returns_each_requested_row(monkeypatch) -> None:
    async def fake_day(symbol, day, rows, humanize=True, color=True, request=None):
        return [
            dfi_service.DfiPieceResult(
                variant, ensemble, None, _breakdown(70.0 + index), False, "2026-11-02T09:00:00Z"
            )
            for index, (variant, ensemble) in enumerate(rows)
        ]

    monkeypatch.setattr(dfi_service, "pieces_for_day", fake_day)
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get(
        "/v1/sonify/dfi/pieces?symbol=vnm&bucket=day&date=2026-11-02&variant=symphony"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "VNM"
    assert body["bucket"] == "day"
    assert len(body["pieces"]) == 3
    assert body["pieces"][0]["dfi"]["score"] == 70.0


def test_pieces_endpoint_needs_a_date_for_a_day() -> None:
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get("/v1/sonify/dfi/pieces?symbol=vnm&bucket=day&variant=symphony")
    assert response.status_code == 422


def test_signatures_endpoint_is_empty_until_the_artifact_exists() -> None:
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get("/v1/sonify/dfi/signatures?bucket=day")
    assert response.status_code == 200
    assert response.json() == []


def test_pieces_endpoint_rejects_an_unknown_ensemble() -> None:
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get(
        "/v1/sonify/dfi/pieces?symbol=vnm&bucket=day&date=2026-11-02&variant=symphony&ensemble=organ"
    )
    assert response.status_code == 422


def test_trace_snaps_to_the_intended_line() -> None:
    notes = [NoteEvent(bar=0, beat=0.0, midi=72, duration_beats=1.0, voice=1)]
    trace = trace_from_notes(
        notes,
        line=[60] * 8,
        prices=[10.0] * 8,
        epb=8,
        bar_beats=4.0,
        octave_tolerant=True,
        snap_to_line=True,
    )
    assert len(trace) == 1
    assert trace[0].pitch == 60.0
    assert trace[0].sounding_pitch == 72.0


def test_trace_keeps_the_longer_note_on_a_tie() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=60, duration_beats=1.0, voice=1),
        NoteEvent(bar=0, beat=0.0, midi=60, duration_beats=3.0, voice=2),
    ]
    trace = trace_from_notes(
        notes, line=[60] * 8, prices=[10.0] * 8, epb=8, bar_beats=4.0
    )
    assert len(trace) == 1
    assert trace[0].duration_beats == 3.0


def test_fill_trace_merges_high_ties() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=2.0, voice=5, tie_start=True),
        NoteEvent(bar=0, beat=2.0, midi=67, duration_beats=2.0, voice=5, tie_stop=True),
    ]
    trace = fill_trace_from_notes(
        (),
        notes,
        line=[60] * 8,
        prices=[10.0] * 8,
        epb=8,
        bar_beats=4.0,
        yield_spans=[(0, 8)],
    )
    assert len(trace) == 1
    assert trace[0].pitch == 60.0
    assert trace[0].sounding_pitch == 67.0
    assert trace[0].duration_beats == 4.0


def test_fill_trace_does_not_stack_overlapping_high_notes() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=2.0, voice=5),
        NoteEvent(bar=0, beat=1.0, midi=69, duration_beats=2.0, voice=5),
    ]
    trace = fill_trace_from_notes(
        (),
        notes,
        line=[60] * 8,
        prices=[10.0] * 8,
        epb=8,
        bar_beats=4.0,
        yield_spans=[(0, 8)],
    )
    assert len(trace) == 1


def test_fill_uses_yield_spans() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=1.0, voice=5),
        NoteEvent(bar=1, beat=0.0, midi=67, duration_beats=1.0, voice=5),
    ]
    trace = fill_trace_from_notes(
        (),
        notes,
        line=[60] * 16,
        prices=[10.0] * 16,
        epb=8,
        bar_beats=4.0,
        yield_spans=[(8, 16)],
    )
    assert len(trace) == 1
    assert trace[0].bar == 1


def test_fill_skips_a_note_attacking_just_before_the_span() -> None:
    notes = [NoteEvent(bar=0, beat=0.0, midi=67, duration_beats=4.0, voice=5)]
    trace = fill_trace_from_notes(
        (),
        notes,
        line=[60] * 8,
        prices=[10.0] * 8,
        epb=8,
        bar_beats=4.0,
        yield_spans=[(1, 8)],
    )
    assert trace == ()


def test_fill_without_yield_spans_adds_nothing() -> None:
    base = (
        PriceTracePoint(bar=0, beat=0.0, duration_beats=4.0, price=10.0, pitch=60.0),
    )
    notes = [NoteEvent(bar=1, beat=0.0, midi=67, duration_beats=1.0, voice=5)]
    trace = fill_trace_from_notes(
        base,
        notes,
        line=[60] * 16,
        prices=[10.0] * 16,
        epb=8,
        bar_beats=4.0,
        yield_spans=[],
    )
    assert trace == base


def test_motion_points_drops_frame_bars() -> None:
    trace = (
        PriceTracePoint(bar=0, beat=0.0, duration_beats=4.0, price=10.0, pitch=60.0),
        PriceTracePoint(bar=1, beat=0.0, duration_beats=4.0, price=11.0, pitch=62.0),
        PriceTracePoint(bar=2, beat=0.0, duration_beats=4.0, price=12.0, pitch=64.0),
    )
    score = SimpleNamespace(price_trace=trace, frame_bars=(2,), phrases=())
    points = motion_points(score, [(0, 3)], epb=4)
    assert [point.eighth for point in points[0]] == [0, 4]


def test_motion_points_deduplicates_base_and_fill() -> None:
    trace = (
        PriceTracePoint(
            bar=0, beat=0.0, duration_beats=4.0, price=10.0, pitch=60.0, voice="line"
        ),
        PriceTracePoint(
            bar=0, beat=0.0, duration_beats=1.0, price=10.0, pitch=60.0, voice="high"
        ),
        PriceTracePoint(
            bar=1, beat=0.0, duration_beats=4.0, price=11.0, pitch=62.0, voice="line"
        ),
    )
    score = SimpleNamespace(price_trace=trace, frame_bars=(), phrases=())
    points = motion_points(score, [(0, 2)], epb=4)
    assert len(points[0]) == 2


def test_motion_source_is_per_variant() -> None:
    assert MOTION_ON_ANCHORS["guitar"] is True
    assert MOTION_ON_ANCHORS["symphony"] is True
    assert MOTION_ON_ANCHORS["jazz"] is True
    assert MOTION_ON_ANCHORS["minimalist"] is True
    assert MOTION_ON_ANCHORS["ambient"] is False
    assert MOTION_ON_ANCHORS.get("unknown", True) is True


def test_motion_filters_below_the_window_eps() -> None:
    points = _points([10.0, 10.01, 10.02, 10.03, 10.04], [60, 60, 60, 60, 60])
    value, weight, _low = _motion(points, eps=0.1)
    assert value is None
    assert weight == 0.0


def test_schemas_version_matches_dfi_version() -> None:
    assert DfiBreakdownSchema.model_fields["version"].default == DFI_VERSION
    assert DfiBreakdownSchema.model_fields["motion_pairs"].default == 0


def test_guitar_sets_sounding_pitch_on_remap() -> None:
    volatile = [
        Bar(
            close=100.0 + (8.0 if index % 2 else -8.0) + index * 0.3,
            volume=1000 + index * 300,
        )
        for index in range(32)
    ]
    score = render(volatile, variant="guitar", ensemble="torroba")
    trace = [point for point in score.price_trace if point.pitch is not None]
    assert trace
    assert all(point.sounding_pitch is not None for point in trace)
    assert any(point.pitch != point.sounding_pitch for point in trace)


def test_sounding_pitch_keeps_the_flute_offset() -> None:
    notes = [
        NoteEvent(bar=0, beat=0.0, midi=63, duration_beats=1.0, voice=5),  # +3
        NoteEvent(bar=1, beat=0.0, midi=64, duration_beats=1.0, voice=5),  # +4
        NoteEvent(bar=2, beat=0.0, midi=67, duration_beats=1.0, voice=5),  # +7
        NoteEvent(bar=3, beat=0.0, midi=51, duration_beats=1.0, voice=5),  # -9
    ]
    trace = fill_trace_from_notes(
        (),
        notes,
        line=[60] * 32,
        prices=[10.0] * 32,
        epb=8,
        bar_beats=4.0,
        yield_spans=[(0, 32)],
    )
    assert len(trace) == 4
    offsets = []
    for point in trace:
        assert point.sounding_pitch is not None
        offsets.append(round(point.sounding_pitch - point.pitch) % 12)
    assert sorted(offsets) == [3, 3, 4, 7]


def test_symphony_trace_covers_a_flute_only_bar() -> None:
    base = (
        PriceTracePoint(bar=0, beat=0.0, duration_beats=4.0, price=10.0, pitch=60.0),
    )
    notes = [NoteEvent(bar=1, beat=0.0, midi=63, duration_beats=4.0, voice=5)]
    trace = fill_trace_from_notes(
        base,
        notes,
        line=[60] * 16,
        prices=[10.0] * 16,
        epb=8,
        bar_beats=4.0,
        yield_spans=[(8, 16)],
    )
    assert [point.bar for point in trace] == [0, 1]
    assert trace[1].voice == "high"


def test_same_trace_across_symphony_ensembles() -> None:
    """The intent trace is ensemble-invariant; the audible contour still follows it."""

    def rendered(ensemble: str):
        return render(_bars(trend=0.8), variant="symphony", ensemble=ensemble)  # type: ignore[arg-type]

    def intent(score) -> set[tuple[int, float, float]]:
        return {
            (point.bar, round(point.beat, 2), round(point.pitch, 1))
            for point in score.price_trace
            if point.pitch is not None
        }

    classic = rendered("classic")
    classic_intent = intent(classic)
    assert classic_intent
    for ensemble in ("wood", "brass"):
        score = rendered(ensemble)
        assert intent(score) == classic_intent
        breakdown = compute(score, variant="symphony", ensemble=ensemble)
        assert breakdown is not None
        assert breakdown.coverage > 0.5
        assert breakdown.volume is not None and breakdown.volume > 0
        # `compute` reads intent, so the score spread is 0 by design.  Guard the
        # audible pitch separately: an octave fold must not invert the contour.
        a = {
            (point.bar, round(point.beat, 3)): point.sounding_pitch
            for point in classic.price_trace
            if point.sounding_pitch is not None
        }
        b = {
            (point.bar, round(point.beat, 3)): point.sounding_pitch
            for point in score.price_trace
            if point.sounding_pitch is not None
        }
        keys = sorted(set(a) & set(b))
        agree = total = 0
        for left, right in zip(keys, keys[1:]):
            delta_a = a[right] - a[left]
            delta_b = b[right] - b[left]
            if delta_a == 0 and delta_b == 0:
                continue
            total += 1
            agree += (delta_a > 0) == (delta_b > 0)
        assert total
        assert agree / total >= 0.8, (ensemble, agree, total)


def test_compute_uses_anchors_for_guitar_and_grid_for_ambient(monkeypatch) -> None:
    calls: list[str] = []
    original = dfi_module.motion_points

    def spy(score, windows, epb):
        calls.append(score.variant)
        return original(score, windows, epb)

    monkeypatch.setattr(dfi_module, "motion_points", spy)
    guitar = compute(
        render(_bars(), variant="guitar", ensemble="bach"),
        variant="guitar",
        ensemble="bach",
    )
    assert guitar is not None
    assert calls == ["guitar"]

    calls.clear()
    ambient = compute(
        render(_bars(), variant="ambient", ensemble="classic"),
        variant="ambient",
        ensemble="classic",
    )
    assert ambient is not None
    assert calls == []


def test_motion_returns_zero_when_every_step_holds() -> None:
    points = _points([10, 11, 13, 16, 20], [64, 64, 64, 64, 64])
    value, weight, _low = _motion(points, eps=0.1)
    assert value == 0.0
    assert weight == 4.0
