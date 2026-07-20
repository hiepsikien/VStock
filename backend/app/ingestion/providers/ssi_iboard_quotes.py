from __future__ import annotations

import asyncio

import httpx

from app.domain.quote import Quote
from app.ingestion.normalizers.ssi import normalize_ssi_stock
from app.ingestion.providers.base import QuoteProvider
from app.services.http_utils import BROWSER_HEADERS

SSI_STOCK = "https://iboard-query.ssi.com.vn/stock"


class SsiIboardQuoteProvider(QuoteProvider):
    name = "ssi_iboard"
    priority = 2
    batch = False
    stale = False

    async def _fetch_one(self, client: httpx.AsyncClient, symbol: str) -> Quote | None:
        resp = await client.get(f"{SSI_STOCK}/{symbol.upper()}")
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or {}
        return normalize_ssi_stock(data, symbol)

    async def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        cleaned = [s.strip().upper() for s in symbols if s.strip()]
        if not cleaned:
            return {}

        async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
            rows = await asyncio.gather(
                *(self._fetch_one(client, sym) for sym in cleaned),
                return_exceptions=True,
            )

        result: dict[str, Quote] = {}
        for sym, row in zip(cleaned, rows):
            if isinstance(row, Quote):
                result[sym] = row
        return result
