from __future__ import annotations

import logging
from typing import Any

from app.domain.quote import Quote
from app.ingestion.config import load_quote_providers
from app.ingestion.providers.base import QuoteProvider
from app.ingestion.providers.entrade_stale_quotes import EntradeStaleQuoteProvider
from app.ingestion.providers.kbs_stale_quotes import KbsStaleQuoteProvider
from app.ingestion.providers.ssi_iboard_quotes import SsiIboardQuoteProvider
from app.ingestion.providers.vps_quotes import VpsQuoteProvider

logger = logging.getLogger(__name__)


def _is_thin_quote(quote: Quote) -> bool:
    """Missing session OHLC/volume — keep looking for a fuller provider."""
    return quote.open <= 0 and quote.high <= 0 and quote.low <= 0 and quote.volume <= 0


_PROVIDER_CLASSES: dict[str, type[QuoteProvider]] = {
    "vps": VpsQuoteProvider,
    "ssi_iboard": SsiIboardQuoteProvider,
    "entrade_stale": EntradeStaleQuoteProvider,
    "entrade": EntradeStaleQuoteProvider,
    "kbs_stale": KbsStaleQuoteProvider,
    "kbs": KbsStaleQuoteProvider,
}


def build_quote_providers(config: list[dict[str, Any]] | None = None) -> list[QuoteProvider]:
    rows = config or load_quote_providers()
    providers: list[QuoteProvider] = []

    for row in sorted(rows, key=lambda item: int(item.get("priority", 99))):
        name = str(row.get("name", "")).strip()
        cls = _PROVIDER_CLASSES.get(name)
        if not cls:
            logger.warning("Unknown quote provider in config: %s", name)
            continue
        provider = cls()
        provider.priority = int(row.get("priority", provider.priority))
        provider.batch = bool(row.get("batch", provider.batch))
        provider.stale = row.get("type") == "stale" or provider.stale
        providers.append(provider)

    return providers or [VpsQuoteProvider()]


class QuoteProviderRegistry:
    def __init__(self, providers: list[QuoteProvider] | None = None) -> None:
        self.providers = providers or build_quote_providers()

    async def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        cleaned = [s.strip().upper() for s in symbols if s.strip()]
        if not cleaned:
            return {}

        remaining = list(dict.fromkeys(cleaned))
        result: dict[str, Quote] = {}

        for provider in self.providers:
            if not remaining:
                break

            try:
                fetched = await provider.fetch_quotes(remaining)
            except Exception as exc:
                logger.warning("Quote provider %s failed: %s", provider.name, exc)
                continue

            for sym, quote in fetched.items():
                existing = result.get(sym)
                if existing is None or (_is_thin_quote(existing) and not _is_thin_quote(quote)):
                    result[sym] = quote

            remaining = [
                sym
                for sym in remaining
                if sym not in result or _is_thin_quote(result[sym])
            ]

        return result


_default_registry: QuoteProviderRegistry | None = None


def get_quote_registry() -> QuoteProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = QuoteProviderRegistry()
    return _default_registry
