"""Listen to BTCUSDT as the prints arrive, instead of a finished tape.

Binance aggTrade is the clock. Wall time only closes a quiet bucket after we
have measured how far the local clock sits from the exchange timestamp, so a
test tape from another era cannot be stretched into millions of held notes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from app.sonify.model import Variant
from app.sonify.stream import BUCKET_MS, StreamEngine, Trade

logger = logging.getLogger(__name__)

BINANCE_AGG_TRADE = "wss://data-stream.binance.vision/ws/btcusdt@aggTrade"
_POLL_S = 0.05
_TICK = object()


def now_ms() -> int:
    return int(time.time() * 1000)


def trade_from_agg(payload: object) -> Trade | None:
    """Read one aggTrade, including the combined-stream envelope."""
    if isinstance(payload, dict) and "data" in payload and "e" not in payload:
        payload = payload.get("data")
    if not isinstance(payload, dict) or payload.get("e") != "aggTrade":
        return None
    try:
        trade = Trade(int(payload["T"]), float(payload["p"]), float(payload["q"]))
    except (KeyError, TypeError, ValueError):
        return None
    return trade


def _message_trade(raw: str | bytes) -> Trade | None:
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return trade_from_agg(payload)


async def binance_trades(url: str = BINANCE_AGG_TRADE) -> AsyncIterator[Trade]:
    """Yield aggTrade prints until the upstream socket closes."""
    import websockets

    async with websockets.connect(url, open_timeout=10, ping_interval=20) as socket:
        async for raw in socket:
            trade = _message_trade(raw)
            if trade is not None:
                yield trade


async def follow(
    trades: AsyncIterator[Trade],
    *,
    variant: Variant = "symphony",
    seed: int = 1,
) -> AsyncIterator[dict[str, object]]:
    """Turn an open print stream into notes. The stream has no last bar."""
    engine = StreamEngine(seed=seed, variant=variant)
    queue: asyncio.Queue[Trade | BaseException | None] = asyncio.Queue()
    skew: int | None = None
    count = 0

    async def produce() -> None:
        try:
            async for trade in trades:
                await queue.put(trade)
            await queue.put(None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("BTC live tape ended: %s", exc)
            await queue.put(exc)

    producer = asyncio.create_task(produce())
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=_POLL_S)
            except asyncio.TimeoutError:
                item = _TICK
            if item is _TICK:
                emitted = _close_quiet(engine, skew)
            elif isinstance(item, BaseException):
                if count:
                    yield {"type": "end", "notes": count}
                else:
                    yield {"type": "error", "text": "Không nối được Binance."}
                return
            elif item is None:
                emitted = _close_quiet(engine, skew)
                for note in emitted:
                    count += 1
                    yield note.payload()
                yield {"type": "end", "notes": count}
                return
            else:
                skew = now_ms() - item.t
                emitted = engine.push_trade(item.t, item.price, item.qty)
                emitted.extend(_close_quiet(engine, skew))
            for note in emitted:
                count += 1
                yield note.payload()
    finally:
        producer.cancel()
        try:
            await producer
        except asyncio.CancelledError:
            pass


def _close_quiet(engine: StreamEngine, skew: int | None) -> list:
    """Close buckets the exchange clock has already finished."""
    if skew is None:
        return []
    return engine.advance_to(now_ms() - skew)
