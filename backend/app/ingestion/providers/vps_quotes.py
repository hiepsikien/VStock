from __future__ import annotations

import httpx

from app.domain.quote import Quote
from app.ingestion.normalizers.vps import normalize_vps_item
from app.ingestion.providers.base import QuoteProvider
from app.services.http_utils import BROWSER_HEADERS

VPS_URL = "https://bgapidatafeed.vps.com.vn/getliststockdata"


class VpsQuoteProvider(QuoteProvider):
    name = "vps"
    priority = 1
    batch = True
    stale = False

    async def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        cleaned = [s.strip().upper() for s in symbols if s.strip()]
        if not cleaned:
            return {}

        url = f"{VPS_URL}/{','.join(cleaned)}"
        async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list):
            raise RuntimeError("Unexpected VPS response")

        result: dict[str, Quote] = {}
        for item in data:
            quote = normalize_vps_item(item)
            if quote:
                result[quote.symbol] = quote
        return result
