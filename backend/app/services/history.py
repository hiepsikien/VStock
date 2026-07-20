from __future__ import annotations

import time
from typing import Literal

import httpx

from app.services.cache import HISTORY_TTL, cache
from app.services.http_utils import ENTRADE_HEADERS, safe_float

ChartRange = Literal["1D", "1W", "1M", "3M", "1Y", "5Y"]

ENTRADE_OHLC = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"

# (seconds lookback, resolution)
# Entrade resolutions commonly: 1, 5, 15, 30, 1H, 1D, 1W
RANGE_CONFIG: dict[ChartRange, tuple[int, str]] = {
    "1D": (3 * 24 * 3600, "5"),
    "1W": (12 * 24 * 3600, "30"),
    "1M": (45 * 24 * 3600, "1D"),
    "3M": (110 * 24 * 3600, "1D"),
    "1Y": (400 * 24 * 3600, "1D"),
    "5Y": (5 * 400 * 24 * 3600, "1W"),
}


async def fetch_history(symbol: str, chart_range: ChartRange) -> list[float]:
    symbol = symbol.upper()
    key = f"hist:{symbol}:{chart_range}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    lookback, resolution = RANGE_CONFIG[chart_range]
    now = int(time.time())
    params = {
        "from": now - lookback,
        "to": now,
        "symbol": symbol,
        "resolution": resolution,
    }

    async with httpx.AsyncClient(timeout=20.0, headers=ENTRADE_HEADERS) as client:
        resp = await client.get(ENTRADE_OHLC, params=params)
        resp.raise_for_status()
        payload = resp.json()

    closes = payload.get("c") or []
    prices = [round(safe_float(c), 2) for c in closes if safe_float(c) > 0]

    # Sparkline-friendly downsample if huge
    if len(prices) > 120:
        step = max(1, len(prices) // 90)
        prices = prices[::step]

    cache.set(key, prices, HISTORY_TTL)
    return prices


async def fetch_sparkline(symbol: str) -> list[float]:
    prices = await fetch_history(symbol, "1D")
    if len(prices) >= 8:
        return prices
    # Fallback: use 1W daily closes
    return await fetch_history(symbol, "1W")
