from __future__ import annotations

import asyncio
import time

import httpx

from app.domain.quote import Quote
from app.ingestion.normalizers.entrade import normalize_entrade_closes
from app.ingestion.providers.base import QuoteProvider
from app.services.http_utils import ENTRADE_HEADERS, safe_float

ENTRADE_OHLC = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"


class EntradeStaleQuoteProvider(QuoteProvider):
    name = "entrade"
    priority = 3
    batch = True
    stale = True

    async def _fetch_one(self, client: httpx.AsyncClient, symbol: str) -> Quote | None:
        now = int(time.time())
        params = {
            "from": now - 5 * 24 * 3600,
            "to": now,
            "symbol": symbol.upper(),
            "resolution": "1D",
        }
        resp = await client.get(ENTRADE_OHLC, params=params)
        resp.raise_for_status()
        payload = resp.json()
        closes = payload.get("c") or []
        prices = [round(safe_float(c), 2) for c in closes if safe_float(c) > 0]
        return normalize_entrade_closes(symbol, prices)

    async def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        cleaned = [s.strip().upper() for s in symbols if s.strip()]
        if not cleaned:
            return {}

        async with httpx.AsyncClient(timeout=20.0, headers=ENTRADE_HEADERS) as client:
            rows = await asyncio.gather(
                *(self._fetch_one(client, sym) for sym in cleaned),
                return_exceptions=True,
            )

        result: dict[str, Quote] = {}
        for sym, row in zip(cleaned, rows):
            if isinstance(row, Quote):
                result[sym] = row
        return result
