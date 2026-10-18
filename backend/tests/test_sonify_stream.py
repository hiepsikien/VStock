"""Open-ended 250 ms stream: notes lock as soon as their bucket closes."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.sonify import router
from app.sonify.chords import CHORDS
from app.sonify.quantize import C_MAJOR_PCS
from app.sonify.replay import load_trades, pace
from app.sonify.stream import (
    BUCKET_MS,
    BAR_NOTES,
    BEAT_NOTES,
    StreamEngine,
    Trade,
    piece_bounds,
    pump,
    render_stream,
)

_CHORDS = {chord.name: chord for chord in CHORDS}


def _rising(seconds: int) -> list[Trade]:
    return [Trade(second * 1000, 100.0 + second, 1.0) for second in range(seconds)]


def test_empty_tape_is_silent() -> None:
    assert render_stream([]) == []


def test_gap_holds_the_last_price() -> None:
    engine = StreamEngine(seed=1)
    assert engine.push_trade(0, 100.0, 2.0) == []
    notes = engine.push_trade(1000, 110.0, 1.0)
    assert [note.t for note in notes] == [0, 250, 500, 750]
    assert [note.price for note in notes] == [100.0, 100.0, 100.0, 100.0]
    assert [note.dur_ms for note in notes] == [BUCKET_MS] * 4
    assert notes[0].velocity > notes[1].velocity
    assert notes[1].velocity == notes[2].velocity == notes[3].velocity


def test_late_trade_does_not_rewrite_a_closed_bucket() -> None:
    engine = StreamEngine(seed=1)
    engine.push_trade(1000, 50.0, 1.0)
    notes = engine.push_trade(0, 999.0, 5.0)
    assert notes == []
    closed = engine.push_trade(2000, 50.0, 1.0)
    assert closed[0].price == 50.0


def test_appending_trades_does_not_change_notes_already_emitted() -> None:
    """A bucket still accepting prints is not a note yet.

    Ending the tape early would close that bucket. Resuming the same engine
    must keep every note that had already closed.
    """
    trades = load_trades()
    start, end = piece_bounds(trades)
    midpoint = start + (end - start) // 2
    midpoint = (midpoint // BUCKET_MS) * BUCKET_MS
    engine = StreamEngine(seed=1)
    index, early = pump(engine, trades, 0, midpoint, end)
    _index, rest = pump(engine, trades, index, end, end)
    full = render_stream(trades)
    assert early
    assert early == full[: len(early)]
    assert early + rest == full
    assert early[-1].t + BUCKET_MS <= midpoint


def test_pumping_one_bucket_at_a_time_matches_the_whole_tape() -> None:
    trades = load_trades()
    start, end = piece_bounds(trades)
    engine = StreamEngine(seed=1)
    index = 0
    stepped = []
    horizon = start
    while horizon < end:
        horizon = min(end, horizon + BUCKET_MS)
        index, batch = pump(engine, trades, index, horizon, end)
        stepped.extend(batch)
    assert stepped == render_stream(trades)
    assert len(stepped) == (end - start) // BUCKET_MS
    assert [note.t for note in stepped] == list(range(start, end, BUCKET_MS))


def test_four_notes_fill_each_second_and_the_chord_waits_for_the_bar() -> None:
    trades = _rising(24)
    notes = render_stream(trades)
    start, end = piece_bounds(trades)
    assert len(notes) == (end - start) // BUCKET_MS
    assert all(any(voice.role == "violin" for voice in note.voices) for note in notes)
    for previous, current in zip(notes, notes[1:]):
        if current.seq % BAR_NOTES != 0:
            assert current.chord == previous.chord
    assert len({note.chord for note in notes}) > 1


def test_strong_beats_are_chord_tones_and_every_note_stays_on_the_scale() -> None:
    notes = render_stream(load_trades())
    for note in notes:
        assert note.midi % 12 in C_MAJOR_PCS
        if note.seq % BEAT_NOTES == 0:
            assert note.midi % 12 in _CHORDS[note.chord].pitch_classes


def test_a_one_cent_wiggle_does_not_cover_the_whole_scale() -> None:
    base = 81300.0
    trades = [Trade(index * BUCKET_MS, base + (0.01 if index % 2 else 0.0), 1.0) for index in range(40)]
    notes = render_stream(trades)
    assert max(note.midi for note in notes) - min(note.midi for note in notes) <= 1


def test_a_real_climb_raises_the_melody() -> None:
    base = 81300.0
    trades = [Trade(index * BUCKET_MS, base + index * 2.0, 1.0) for index in range(80)]
    notes = render_stream(trades)
    assert notes[-1].midi > notes[0].midi + 4


def test_regime_stays_sideway_until_twenty_seconds_then_follows_the_climb() -> None:
    notes = render_stream(_rising(25))
    assert {note.regime for note in notes[: 20 * BEAT_NOTES]} == {"sideway"}
    assert notes[20 * BEAT_NOTES].regime == "uptrend"


def test_same_seed_replays_the_same_piece() -> None:
    trades = _rising(12)
    assert render_stream(trades, seed=3) == render_stream(trades, seed=3)
    assert render_stream(trades, seed=3) != render_stream(trades, seed=4)


def test_websocket_plays_the_fixture_to_the_end() -> None:
    app = FastAPI()
    app.include_router(router)
    expected = len(render_stream(load_trades()))
    with TestClient(app) as client:
        with client.websocket_connect("/v1/sonify/ws?speed=500") as socket:
            hello = socket.receive_json()
            assert hello["type"] == "hello"
            assert hello["source"] == "history"
            assert hello["bucket_ms"] == BUCKET_MS
            assert hello["notes"] == expected
            count = 0
            while True:
                message = socket.receive_json()
                if message["type"] == "end":
                    assert message["notes"] == expected
                    break
                assert message["type"] == "note"
                assert message["seq"] == count
                assert message["dur_ms"] == BUCKET_MS
                count += 1
    assert count == expected


def test_pace_emits_the_same_notes_as_the_batch_renderer() -> None:
    trades = _rising(4)

    async def collect() -> list[dict[str, object]]:
        return [event async for event in pace(trades, speed=500)]

    events = asyncio.run(collect())
    notes = render_stream(trades)
    assert events[-1] == {"type": "end", "notes": len(notes)}
    assert [event["midi"] for event in events[:-1]] == [note.midi for note in notes]
