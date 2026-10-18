"""Live BTC tape: notes follow prints that have not finished arriving."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.routers.sonify import router
from app.sonify.live import follow, trade_from_agg
from app.sonify.stream import BUCKET_MS, Trade


def test_trade_from_agg_reads_the_print() -> None:
    raw = {"e": "aggTrade", "T": 1_700_000_000_000, "p": "81302.10", "q": "0.002"}
    assert trade_from_agg(raw) == Trade(1_700_000_000_000, 81302.10, 0.002)
    wrapped = {"stream": "btcusdt@aggTrade", "data": {"e": "aggTrade", "T": 5, "p": "1.5", "q": "2"}}
    assert trade_from_agg(wrapped) == Trade(5, 1.5, 2.0)
    assert trade_from_agg({"e": "kline"}) is None
    assert trade_from_agg({"e": "aggTrade", "T": "x", "p": "1", "q": "1"}) is None
    assert trade_from_agg(None) is None


def test_follow_closes_one_bucket_per_step_and_ignores_wall_clock() -> None:
    """Timestamps far from the machine clock must not unroll into a wall of notes."""
    base = 10_000_000_000

    async def tape():
        for index in range(4):
            yield Trade(base + index * BUCKET_MS, 81_000 + index * 10, 0.1)

    async def collect() -> list[dict[str, object]]:
        return [event async for event in follow(tape(), variant="jazz")]

    events = asyncio.run(collect())
    notes = [event for event in events if event["type"] == "note"]
    assert events[-1] == {"type": "end", "notes": len(notes)}
    assert [event["price"] for event in notes] == [81_000, 81_010, 81_020]
    assert notes[0]["swing"] is True
    assert len(notes) < 10


def test_a_quiet_stretch_holds_the_last_print(monkeypatch) -> None:
    clock = {"ms": 5_000_000}
    monkeypatch.setattr("app.sonify.live.now_ms", lambda: clock["ms"])
    started = asyncio.Event()
    release = asyncio.Event()

    async def tape():
        yield Trade(5_000_000, 42_000.0, 3.0)
        started.set()
        await release.wait()

    async def collect() -> list[dict[str, object]]:
        notes: list[dict[str, object]] = []

        async def consume() -> None:
            async for event in follow(tape(), variant="symphony"):
                if event["type"] == "note":
                    notes.append(event)

        task = asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), 1)
        await asyncio.sleep(0.08)
        clock["ms"] = 5_000_000 + 2 * BUCKET_MS
        deadline = asyncio.get_running_loop().time() + 1
        while asyncio.get_running_loop().time() < deadline and len(notes) < 2:
            await asyncio.sleep(0.05)
        release.set()
        await task
        return notes

    notes = asyncio.run(collect())
    assert [note["price"] for note in notes[:2]] == [42_000.0, 42_000.0]
    assert [note["t"] for note in notes[:2]] == [5_000_000, 5_000_000 + BUCKET_MS]


def test_a_dead_upstream_reports_an_error_before_any_note() -> None:
    async def tape():
        raise OSError("down")
        yield Trade(0, 1.0, 1.0)

    async def collect() -> list[dict[str, object]]:
        return [event async for event in follow(tape())]

    assert asyncio.run(collect()) == [{"type": "error", "text": "Không nối được Binance."}]


def test_live_socket_plays_the_injected_tape(monkeypatch) -> None:
    base = 10_000_000_000

    async def tape():
        for index in range(4):
            yield Trade(base + index * BUCKET_MS, 81_000 + index * 10, 0.2)

    monkeypatch.setattr("app.sonify.live.binance_trades", tape)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/sonify/ws?source=live&variant=jazz") as socket:
            hello = socket.receive_json()
            assert hello["source"] == "live"
            assert hello["variant"] == "jazz"
            assert "notes" not in hello
            notes = []
            while True:
                message = socket.receive_json()
                if message["type"] == "end":
                    break
                assert message["type"] == "note"
                notes.append(message)
    assert [note["price"] for note in notes] == [81_000, 81_010, 81_020]
    assert notes[0]["swing"] is True


def test_unknown_source_is_rejected() -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/sonify/ws?source=tape") as socket:
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
