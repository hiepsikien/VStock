from __future__ import annotations

import time

import httpx

from app.domain.history import ChartRange, RANGE_CONFIG, downsample_prices
from app.services.http_utils import ENTRADE_HEADERS, safe_float

ENTRADE_OHLC = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"


async def fetch_history_prices(symbol: str, chart_range: ChartRange) -> list[float]:
    sym = symbol.upper()
    lookback, resolution = RANGE_CONFIG[chart_range]
    now = int(time.time())
    params = {
        "from": now - lookback,
        "to": now,
        "symbol": sym,
        "resolution": resolution,
    }

    async with httpx.AsyncClient(timeout=20.0, headers=ENTRADE_HEADERS) as client:
        resp = await client.get(ENTRADE_OHLC, params=params)
        resp.raise_for_status()
        payload = resp.json()

    closes = payload.get("c") or []
    prices = [round(safe_float(c), 2) for c in closes if safe_float(c) > 0]
    return downsample_prices(prices)
