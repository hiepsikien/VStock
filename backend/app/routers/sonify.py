"""Browser player for the open-ended BTC tape."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.sonify import live as live_tape
from app.sonify.model import VARIANTS, Variant
from app.sonify.replay import hello, load_trades, pace
from app.sonify.stream import BUCKET_MS, piece_bounds

router = APIRouter(prefix="/v1/sonify", tags=["sonify"])
_PLAYER = Path(__file__).resolve().parents[1] / "sonify" / "player.html"
_SOURCES = {"history", "live"}


@router.get("", response_class=HTMLResponse)
def player() -> str:
    return _PLAYER.read_text()


@router.websocket("/ws")
async def stream(
    websocket: WebSocket,
    speed: float = 1.0,
    variant: Variant = "symphony",
    source: str = "history",
) -> None:
    await websocket.accept()
    if variant not in VARIANTS or source not in _SOURCES:
        await websocket.close(code=1008)
        return
    if source == "live":
        await _live(websocket, variant)
        return
    trades = load_trades()
    paced = min(500.0, max(0.25, speed))
    start, end = piece_bounds(trades)
    await websocket.send_json(hello((end - start) // BUCKET_MS, variant, source="history"))
    try:
        async for event in pace(trades, speed=paced, variant=variant):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return


async def _live(websocket: WebSocket, variant: Variant) -> None:
    await websocket.send_json(hello(variant=variant, source="live"))
    try:
        async for event in live_tape.follow(live_tape.binance_trades(), variant=variant):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
