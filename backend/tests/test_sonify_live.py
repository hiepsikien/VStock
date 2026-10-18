"""Live BTC tape: notes follow prints that have not finished arriving."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.routers.sonify import router
from app.sonify.live import follow, rank_top_symbols, trade_from_agg, valid_symbol
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


def test_rank_top_symbols_filters_stablecoins_and_sorts_by_quote_volume() -> None:
    rows = [
        {"symbol": "USDCUSDT", "quoteVolume": "1900000000", "lastPrice": "1.0001"},
        {"symbol": "FDUSDUSDT", "quoteVolume": "950000000", "lastPrice": "0.9999"},
        {"symbol": "BTCUPUSDT", "quoteVolume": "800000000", "lastPrice": "120.0"},
        {"symbol": "ETHDOWNUSDT", "quoteVolume": "700000000", "lastPrice": "0.045"},
        {"symbol": "ETHUSDT", "quoteVolume": "320000000", "lastPrice": "2410.5"},
        {"symbol": "BTCUSDT", "quoteVolume": "610000000", "lastPrice": "81700.0"},
        {"symbol": "JUPUSDT", "quoteVolume": "150000000", "lastPrice": "0.289"},
        {"symbol": "PUMPUSDT", "quoteVolume": "120000000", "lastPrice": "0.004"},
        {"symbol": "SOLUSDT", "quoteVolume": "110000000", "lastPrice": "103.6"},
    ]
    top = rank_top_symbols(rows, limit=10)
    assert [item["symbol"] for item in top] == [
        "BTCUSDT",
        "ETHUSDT",
        "JUPUSDT",
        "PUMPUSDT",
        "SOLUSDT",
    ]
    assert [item["base"] for item in top] == ["BTC", "ETH", "JUP", "PUMP", "SOL"]
    assert valid_symbol("USDCUSDT") is None
    assert valid_symbol("BTCUPUSDT") is None
    assert valid_symbol("ETHDOWNUSDT") is None
    assert valid_symbol("JUPUSDT") == "JUPUSDT"
    assert valid_symbol("SYRUPUSDT") == "SYRUPUSDT"
    assert valid_symbol("PUMPUSDT") == "PUMPUSDT"
    assert valid_symbol("ethusdt") == "ETHUSDT"


def test_history_source_only_accepts_btcusdt() -> None:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        with client.websocket_connect("/v1/sonify/ws?source=history&symbol=ETHUSDT") as socket:
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()


def test_symbols_endpoint_and_ambient_multi_coin_stream(monkeypatch) -> None:
    base = 10_000_000_000
    seen_symbols: list[str] = []

    async def fake_top(limit: int = 10):
        return [
            {"symbol": "BTCUSDT", "base": "BTC", "quote_volume": 600_000_000.0, "last_price": 81_700.0},
            {"symbol": "ETHUSDT", "base": "ETH", "quote_volume": 320_000_000.0, "last_price": 2_410.0},
        ][:limit]

    async def fake_trades(*, symbol: str = "BTCUSDT", url: str | None = None):
        seen_symbols.append(symbol)
        for index in range(4):
            yield Trade(base + index * BUCKET_MS, 2_410.0 + index * 2.0, 4.5)

    monkeypatch.setattr("app.sonify.live.top_volume_symbols", fake_top)
    monkeypatch.setattr("app.sonify.live.binance_trades", fake_trades)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        res = client.get("/v1/sonify/symbols")
        assert res.status_code == 200
        assert [item["symbol"] for item in res.json()["symbols"]] == ["BTCUSDT", "ETHUSDT"]

        with client.websocket_connect("/v1/sonify/ws?source=live&variant=ambient&symbol=ETHUSDT") as socket:
            hello = socket.receive_json()
            assert hello["source"] == "live"
            assert hello["variant"] == "ambient"
            assert hello["symbol"] == "ETHUSDT"
            first = socket.receive_json()
            assert first["type"] == "note"
            assert first["variant"] == "ambient"
            assert first["volume"] == 4.5
            assert any(voice["role"] in ("drone", "halo", "glass") for voice in first["voices"])
    assert seen_symbols == ["ETHUSDT"]
