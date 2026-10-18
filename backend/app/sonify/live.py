"""Listen to live crypto prints as they arrive, instead of a finished tape.

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

import httpx

from app.sonify.model import StreamVariant
from app.sonify.stream import BUCKET_MS, StreamEngine, Trade

logger = logging.getLogger(__name__)

BINANCE_AGG_TRADE = "wss://data-stream.binance.vision/ws/btcusdt@aggTrade"
BINANCE_TICKER_24H = "https://data-api.binance.vision/api/v3/ticker/24hr"
_POLL_S = 0.05
_TICK = object()
_SYMBOL_TTL_S = 60.0

EXCLUDED_BASES = frozenset(
    {
        "USDC",
        "FDUSD",
        "USD1",
        "USDP",
        "TUSD",
        "DAI",
        "BUSD",
        "USDE",
        "PYUSD",
        "EUR",
        "AEUR",
        "EURI",
        "GBP",
        "TRY",
        "BRL",
        "ARS",
        "JPY",
        "AUD",
        "PAXG",
        "XUSD",
        "RLUSD",
        "USDX",
        "USDT",
    }
)

DEFAULT_TOP_SYMBOLS: tuple[dict[str, object], ...] = (
    {"symbol": "BTCUSDT", "base": "BTC", "quote_volume": 600_000_000.0, "last_price": 81_700.0},
    {"symbol": "ETHUSDT", "base": "ETH", "quote_volume": 320_000_000.0, "last_price": 2_410.0},
    {"symbol": "SOLUSDT", "base": "SOL", "quote_volume": 110_000_000.0, "last_price": 103.6},
    {"symbol": "XRPUSDT", "base": "XRP", "quote_volume": 60_000_000.0, "last_price": 1.30},
    {"symbol": "BNBUSDT", "base": "BNB", "quote_volume": 52_000_000.0, "last_price": 720.0},
    {"symbol": "DOGEUSDT", "base": "DOGE", "quote_volume": 31_000_000.0, "last_price": 0.08},
    {"symbol": "SUIUSDT", "base": "SUI", "quote_volume": 30_000_000.0, "last_price": 0.98},
    {"symbol": "NEARUSDT", "base": "NEAR", "quote_volume": 28_000_000.0, "last_price": 4.98},
    {"symbol": "ADAUSDT", "base": "ADA", "quote_volume": 24_000_000.0, "last_price": 0.42},
    {"symbol": "AVAXUSDT", "base": "AVAX", "quote_volume": 20_000_000.0, "last_price": 18.5},
)

_symbol_cache: tuple[float, list[dict[str, object]]] | None = None


def now_ms() -> int:
    return int(time.time() * 1000)


def valid_symbol(symbol: str) -> str | None:
    cleaned = symbol.strip().upper()
    if not cleaned.isalnum() or not cleaned.endswith("USDT"):
        return None
    if len(cleaned) < 5 or len(cleaned) > 16:
        return None
    base = cleaned[:-4]
    if not base or base in EXCLUDED_BASES:
        return None
    if base.endswith(("UP", "DOWN", "BULL", "BEAR")):
        return None
    return cleaned


def agg_trade_url(symbol: str = "BTCUSDT") -> str:
    checked = valid_symbol(symbol) or "BTCUSDT"
    return f"wss://data-stream.binance.vision/ws/{checked.lower()}@aggTrade"


def rank_top_symbols(rows: list[dict[str, object]], limit: int = 10) -> list[dict[str, object]]:
    """Pick the top non-stablecoin USDT pairs sorted by 24h quote volume."""
    candidates: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_sym = row.get("symbol")
        if not isinstance(raw_sym, str):
            continue
        symbol = valid_symbol(raw_sym)
        if symbol is None:
            continue
        try:
            quote_volume = float(row.get("quoteVolume", 0.0))  # type: ignore[arg-type]
            last_price = float(row.get("lastPrice", 0.0))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if quote_volume <= 0 or last_price <= 0:
            continue
        candidates.append(
            {
                "symbol": symbol,
                "base": symbol[:-4],
                "quote_volume": quote_volume,
                "last_price": last_price,
            }
        )
    candidates.sort(key=lambda item: float(item["quote_volume"]), reverse=True)  # type: ignore[arg-type]
    picked = candidates[: max(1, limit)]
    if picked and not any(item["symbol"] == "BTCUSDT" for item in picked):
        btc = next((item for item in candidates if item["symbol"] == "BTCUSDT"), None)
        if btc is not None:
            picked = [btc, *picked[: max(0, limit - 1)]]
    return picked


async def top_volume_symbols(limit: int = 10) -> list[dict[str, object]]:
    """Fetch and cache the top 10 USDT crypto pairs by 24h volume on Binance."""
    global _symbol_cache
    now = time.monotonic()
    if _symbol_cache is not None and now - _symbol_cache[0] < _SYMBOL_TTL_S:
        return _symbol_cache[1][:limit]
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(BINANCE_TICKER_24H)
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, list):
            ranked = rank_top_symbols(payload, limit=limit)
            if ranked:
                _symbol_cache = (now, ranked)
                return ranked
    except Exception as exc:
        logger.warning("Could not refresh Binance top symbols: %s", exc)
    return [dict(item) for item in DEFAULT_TOP_SYMBOLS[:limit]]


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


async def binance_trades(
    url: str | None = None,
    *,
    symbol: str = "BTCUSDT",
) -> AsyncIterator[Trade]:
    """Yield aggTrade prints until the upstream socket closes."""
    import websockets

    target = url or agg_trade_url(symbol)
    async with websockets.connect(target, open_timeout=10, ping_interval=20) as socket:
        async for raw in socket:
            trade = _message_trade(raw)
            if trade is not None:
                yield trade


async def follow(
    trades: AsyncIterator[Trade],
    *,
    variant: StreamVariant = "symphony",
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
            logger.warning("Live crypto tape ended: %s", exc)
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
