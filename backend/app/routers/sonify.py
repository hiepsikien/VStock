"""Browser player for the open-ended BTC tape."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from app.sonify.replay import hello, load_trades, pace
from app.sonify.stream import BUCKET_MS, piece_bounds

router = APIRouter(prefix="/v1/sonify", tags=["sonify"])
_PLAYER = Path(__file__).resolve().parents[1] / "sonify" / "player.html"


@router.get("", response_class=HTMLResponse)
def player() -> str:
    return _PLAYER.read_text()


@router.websocket("/ws")
async def stream(websocket: WebSocket, speed: float = 1.0) -> None:
    await websocket.accept()
    trades = load_trades()
    paced = min(500.0, max(0.25, speed))
    start, end = piece_bounds(trades)
    await websocket.send_json(hello((end - start) // BUCKET_MS))
    try:
        async for event in pace(trades, speed=paced):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
