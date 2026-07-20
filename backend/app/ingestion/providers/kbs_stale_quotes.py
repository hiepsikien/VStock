from __future__ import annotations

import asyncio
from datetime import date, timedelta

import httpx

from app.domain.quote import Quote
from app.ingestion.normalizers.kbs import normalize_kbs_row
from app.ingestion.providers.base import QuoteProvider
from app.services.http_utils import BROWSER_HEADERS

KBS_BASE = "https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock"


class KbsStaleQuoteProvider(QuoteProvider):
    name = "kbs"
    priority = 4
    batch = False
    stale = True

    async def _fetch_one(self, client: httpx.AsyncClient, symbol: str) -> Quote | None:
        to_date = date.today().isoformat()
        from_date = (date.today() - timedelta(days=10)).isoformat()
        resp = await client.get(
            f"{KBS_BASE}/{symbol.upper()}/historical-quotes",
            params={"from": from_date, "to": to_date},
        )
        resp.raise_for_status()
        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            return None
        return normalize_kbs_row(rows[0], symbol)

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
