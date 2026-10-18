"""Play a recorded trade tape as if the prints were arriving now."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from pathlib import Path

from app.sonify.model import StreamVariant
from app.sonify.stream import (
    BUCKET_MS,
    Trade,
    StreamEngine,
    piece_bounds,
    pump,
)

FIXTURE = Path(__file__).with_name("fixtures") / "btcusdt_90s.json"
BUFFER_MS = 1000


def load_trades(path: Path | None = None) -> list[Trade]:
    payload = json.loads((path or FIXTURE).read_text())
    trades = [
        Trade(int(row["t"]), float(row["p"]), float(row["q"]))
        for row in payload["trades"]
    ]
    trades.sort(key=lambda trade: trade.t)
    return trades


async def pace(
    trades: list[Trade],
    *,
    seed: int = 1,
    buffer_ms: int = BUFFER_MS,
    speed: float = 1.0,
    variant: StreamVariant = "symphony",
) -> AsyncIterator[dict[str, object]]:
    """Yield note payloads about `buffer_ms` before they should be heard.

    `speed` compresses the wait between buckets. The notes themselves stay on
    the 250 ms grid, so a faster pace only shortens the silence in tests.
    """
    if not trades:
        yield {"type": "end", "notes": 0}
        return
    if speed <= 0:
        raise ValueError("speed must be positive")
    origin, piece_end = piece_bounds(trades)
    engine = StreamEngine(seed=seed, variant=variant)
    index = 0
    count = 0
    wall0 = time.monotonic()
    while True:
        elapsed_ms = (time.monotonic() - wall0) * 1000 * speed
        horizon = min(piece_end, origin + elapsed_ms + buffer_ms)
        index, notes = pump(engine, trades, index, int(horizon), piece_end)
        for note in notes:
            count += 1
            yield note.payload()
        if horizon >= piece_end and index >= len(trades):
            yield {"type": "end", "notes": count}
            return
        await asyncio.sleep(0.02)


def hello(
    note_count: int | None = None,
    variant: StreamVariant = "symphony",
    source: str = "history",
    symbol: str = "BTCUSDT",
) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "hello",
        "symbol": symbol,
        "bucket_ms": BUCKET_MS,
        "bpm": 60,
        "buffer_ms": BUFFER_MS,
        "variant": variant,
        "source": source,
    }
    if note_count is not None:
        payload["notes"] = note_count
    return payload
