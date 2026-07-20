from __future__ import annotations

import time

import httpx

from app.domain.history import ChartRange, RANGE_CONFIG, downsample_prices
from app.services.http_utils import ENTRADE_HEADERS, safe_float

ENTRADE_INDEX = "https://services.entrade.com.vn/chart-api/v2/ohlcs/index"

MARKET_INDICES = (
    {"symbol": "VNINDEX", "name": "VN-Index", "exchange": "HOSE"},
    {"symbol": "HNX", "name": "HNX-Index", "exchange": "HNX"},
)

INDEX_SYMBOLS = frozenset(meta["symbol"] for meta in MARKET_INDICES)


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


async def fetch_index_quote(client: httpx.AsyncClient, meta: dict) -> dict | None:
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

    opens = intraday.get("o") or []
    highs = intraday.get("h") or []
    lows = intraday.get("l") or []
    if highs:
        open_price = round(safe_float(opens[0] if opens else price), 2)
        high = round(max(safe_float(h) for h in highs), 2)
        low_vals = [safe_float(l) for l in lows if safe_float(l) > 0]
        low = round(min(low_vals) if low_vals else price, 2)
    else:
        open_price = round(price, 2)
        high = round(price, 2)
        low = round(price, 2)

    return {
        "symbol": sym,
        "name": meta["name"],
        "exchange": meta["exchange"],
        "price": round(price, 2),
        "change": change,
        "changePercent": change_pct,
        "priorClose": round(ref, 2),
        "open": open_price,
        "high": high,
        "low": low,
        "source": "entrade",
    }


async def fetch_all_indices() -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0, headers=ENTRADE_HEADERS) as client:
        rows: list[dict] = []
        for meta in MARKET_INDICES:
            try:
                row = await fetch_index_quote(client, meta)
                if row:
                    rows.append(row)
            except Exception:
                continue
        return rows


async def fetch_index_history_prices(symbol: str, chart_range: ChartRange) -> list[float]:
    sym = symbol.upper()
    if sym not in INDEX_SYMBOLS:
        return []

    lookback, resolution = RANGE_CONFIG[chart_range]
    now = int(time.time())
    async with httpx.AsyncClient(timeout=20.0, headers=ENTRADE_HEADERS) as client:
        resp = await client.get(
            ENTRADE_INDEX,
            params={
                "symbol": sym,
                "resolution": resolution,
                "from": now - lookback,
                "to": now,
            },
        )
        resp.raise_for_status()
        payload = resp.json() or {}

    closes = payload.get("c") or []
    prices = [round(safe_float(c), 2) for c in closes if safe_float(c) > 0]
    return downsample_prices(prices)
