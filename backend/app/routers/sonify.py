"""Browser player for the open-ended crypto tape."""

from __future__ import annotations

import inspect
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.sonify import live as live_tape
from app.sonify.model import STREAM_VARIANTS, StreamVariant
from app.sonify.replay import hello, load_trades, pace
from app.sonify.stream import BUCKET_MS, piece_bounds

router = APIRouter(prefix="/v1/sonify", tags=["sonify"])
_PLAYER = Path(__file__).resolve().parents[1] / "sonify" / "player.html"
_SOURCES = {"history", "live"}


@router.get("", response_class=HTMLResponse)
def player() -> str:
    return _PLAYER.read_text()


@router.get("/symbols")
async def symbols() -> dict[str, object]:
    top = await live_tape.top_volume_symbols(limit=10)
    return {"symbols": top}


@router.websocket("/ws")
async def stream(
    websocket: WebSocket,
    speed: float = 1.0,
    variant: StreamVariant = "symphony",
    source: str = "history",
    symbol: str = "BTCUSDT",
) -> None:
    await websocket.accept()
    checked_symbol = live_tape.valid_symbol(symbol)
    if variant not in STREAM_VARIANTS or source not in _SOURCES or checked_symbol is None:
        await websocket.close(code=1008)
        return
    if source == "history" and checked_symbol != "BTCUSDT":
        await websocket.close(code=1008)
        return
    if source == "live":
        await _live(websocket, variant, checked_symbol)
        return
    trades = load_trades()
    paced = min(500.0, max(0.25, speed))
    start, end = piece_bounds(trades)
    await websocket.send_json(
        hello((end - start) // BUCKET_MS, variant, source="history", symbol="BTCUSDT")
    )
    try:
        async for event in pace(trades, speed=paced, variant=variant):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return


def _open_binance_stream(symbol: str):
    fn = live_tape.binance_trades
    params = inspect.signature(fn).parameters
    if "symbol" in params:
        return fn(symbol=symbol)
    return fn()


async def _live(websocket: WebSocket, variant: StreamVariant, symbol: str) -> None:
    await websocket.send_json(hello(variant=variant, source="live", symbol=symbol))
    try:
        async for event in live_tape.follow(_open_binance_stream(symbol), variant=variant):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
