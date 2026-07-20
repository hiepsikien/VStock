from __future__ import annotations

import asyncio

import httpx

from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS
from app.services.cache import cache
from app.services.http_utils import BROWSER_HEADERS, format_market_cap, safe_float, safe_int

SSI_EXCHANGE = "https://iboard-query.ssi.com.vn/stock/exchange"
SSI_STOCK = "https://iboard-query.ssi.com.vn/stock"

INDEX_EXCHANGE = {
    "VNINDEX": "hose",
    "HNX": "hnx",
}

MCAP_TTL = 3600
_CONCURRENCY = 25


async def _stock_market_cap(client: httpx.AsyncClient, symbol: str) -> float:
    resp = await client.get(f"{SSI_STOCK}/{symbol.upper()}")
    resp.raise_for_status()
    data = (resp.json() or {}).get("data") or {}
    listed = safe_int(data.get("listedShare"))
    price = safe_float(
        data.get("matchedPrice") or data.get("refPrice") or data.get("priorClosePrice"),
    )
    if listed <= 0 or price <= 0:
        return 0.0
    return listed * price


async def _exchange_market_cap_vnd(exchange: str) -> float:
    async with httpx.AsyncClient(timeout=30.0, headers=BROWSER_HEADERS) as client:
        resp = await client.get(f"{SSI_EXCHANGE}/{exchange}")
        resp.raise_for_status()
        rows = [
            row
            for row in (resp.json() or {}).get("data") or []
            if row.get("stockType") == "s" and row.get("stockSymbol")
        ]

        sem = asyncio.Semaphore(_CONCURRENCY)

        async def one(symbol: str) -> float:
            async with sem:
                try:
                    return await _stock_market_cap(client, symbol)
                except Exception:
                    return 0.0

        caps = await asyncio.gather(*(one(str(row["stockSymbol"])) for row in rows))
        return sum(caps)


async def fetch_index_market_cap(symbol: str) -> str:
    sym = symbol.upper()
    exchange = INDEX_EXCHANGE.get(sym)
    if not exchange or sym not in INDEX_SYMBOLS:
        return "—"

    cache_key = f"index:mcap:{exchange}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        total = await _exchange_market_cap_vnd(exchange)
        formatted = format_market_cap(total)
        cache.set(cache_key, formatted, MCAP_TTL)
        return formatted
    except Exception:
        return "—"
