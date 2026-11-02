"""PAFI: the price line must stay readable through the writing, not just sound nice."""

from __future__ import annotations

import math

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import stocks
from app.schemas import RecapResponse
from app.services import pafi as pafi_service
from app.sonify.model import Bar, NoteEvent
from app.sonify.pafi import (
    PafiBreakdown,
    _Point,
    _band,
    _motion,
    _shape,
    _volume,
    compute,
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
    assert frozen_score is None
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
        assert max(scores) - min(scores) <= 3, (variant, scores)


def test_guitar_ensembles_do_not_lose_the_line_to_register_choices() -> None:
    bars = _bars()
    for ensemble in ("bach", "classic", "villa", "barrios", "brouwer", "torroba"):
        breakdown = compute(
            render(bars, variant="guitar", ensemble=ensemble),  # type: ignore[arg-type]
            variant="guitar",
            ensemble=ensemble,
        )
        assert breakdown is not None, ensemble
        assert breakdown.coverage > 0.8, (ensemble, breakdown.coverage)


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
        "pafi": {
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
            "version": "1",
        },
    }
    response = RecapResponse(**payload)
    assert response.pafi is not None
    assert response.pafi.score == 78.0
    assert response.pafi.band == "clear"


def _breakdown(score: float) -> PafiBreakdown:
    return PafiBreakdown(
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
    async def fake_day(symbol, day, rows, humanize=True, color=True):
        return [
            pafi_service.PafiPieceResult(
                variant, ensemble, None, _breakdown(70.0 + index), False, "2026-11-02T09:00:00Z"
            )
            for index, (variant, ensemble) in enumerate(rows)
        ]

    monkeypatch.setattr(pafi_service, "pieces_for_day", fake_day)
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get(
        "/v1/sonify/pafi/pieces?symbol=vnm&bucket=day&date=2026-11-02&variant=symphony"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "VNM"
    assert body["bucket"] == "day"
    assert len(body["pieces"]) == 3
    assert body["pieces"][0]["pafi"]["score"] == 70.0


def test_pieces_endpoint_needs_a_date_for_a_day() -> None:
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get("/v1/sonify/pafi/pieces?symbol=vnm&bucket=day&variant=symphony")
    assert response.status_code == 422


def test_signatures_endpoint_is_empty_until_the_artifact_exists() -> None:
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get("/v1/sonify/pafi/signatures?bucket=day")
    assert response.status_code == 200
    assert response.json() == []


def test_pieces_endpoint_rejects_an_unknown_ensemble() -> None:
    app = FastAPI()
    app.include_router(stocks.router)
    client = TestClient(app)
    response = client.get(
        "/v1/sonify/pafi/pieces?symbol=vnm&bucket=day&date=2026-11-02&variant=symphony&ensemble=organ"
    )
    assert response.status_code == 422
