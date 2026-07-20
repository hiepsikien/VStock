from __future__ import annotations

import time

import httpx

from app.services.cache import cache
from app.services.http_utils import ENTRADE_HEADERS, safe_float

ENTRADE_INDEX = "https://services.entrade.com.vn/chart-api/v2/ohlcs/index"
INDEX_TTL = 30

MARKET_INDICES = (
    {"symbol": "VNINDEX", "name": "VN-Index", "exchange": "HOSE"},
    {"symbol": "HNX", "name": "HNX-Index", "exchange": "HNX"},
)


async def _fetch_bars(
    client: httpx.AsyncClient,
    symbol: str,
    resolution: str,
    days: int,
) -> dict:
    now = int(time.time())
    start = now - days * 86400
    resp = await client.get(
        ENTRADE_INDEX,
        params={"symbol": symbol, "resolution": resolution, "from": start, "to": now},
    )
    resp.raise_for_status()
    return resp.json() or {}


async def _fetch_index_quote(client: httpx.AsyncClient, meta: dict) -> dict | None:
    sym = meta["symbol"]
    daily = await _fetch_bars(client, sym, "1D", 14)
    closes = daily.get("c") or []
    if len(closes) < 1:
        return None

    intraday = await _fetch_bars(client, sym, "5", 3)
    intra_closes = intraday.get("c") or []
    price = safe_float(intra_closes[-1] if intra_closes else closes[-1])
    ref = safe_float(closes[-2] if len(closes) >= 2 else closes[-1])
    if ref <= 0:
        ref = price

    change = round(price - ref, 2)
    change_pct = round((change / ref) * 100, 2) if ref else 0.0

    return {
        "symbol": sym,
        "name": meta["name"],
        "exchange": meta["exchange"],
        "price": round(price, 2),
        "change": change,
        "changePercent": change_pct,
    }


async def fetch_market_indices() -> list[dict]:
    key = "indices:market"
    cached = cache.get(key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=15.0, headers=ENTRADE_HEADERS) as client:
        rows: list[dict] = []
        for meta in MARKET_INDICES:
            try:
                row = await _fetch_index_quote(client, meta)
                if row:
                    rows.append(row)
            except Exception:
                continue

    cache.set(key, rows, INDEX_TTL)
    return rows
