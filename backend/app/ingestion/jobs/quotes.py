from __future__ import annotations

import logging

from app.health import state as health_state
from app.ingestion.config import load_ingestion_settings
from app.ingestion.providers.registry import get_quote_registry
from app.repositories.quotes_repo import QuotesRepository
from app.schemas import DEFAULT_WATCHLIST
from app.services.market_session import is_market_open

logger = logging.getLogger(__name__)
_repo = QuotesRepository()


async def ingest_quotes(*, force: bool = False) -> int:
    settings = load_ingestion_settings()
    if not force and settings.skip_when_market_closed and not is_market_open():
        return 0

    symbols = list(dict.fromkeys([*settings.quote_symbols, *(await _repo.list_symbols())]))
    if not symbols:
        symbols = list(DEFAULT_WATCHLIST)

    registry = get_quote_registry()
    total = 0

    try:
        remaining = list(dict.fromkeys(symbols))
        for provider in registry.providers:
            if not remaining:
                break

            try:
                fetched = await provider.fetch_quotes(remaining)
            except Exception as exc:
                logger.warning("Quote provider %s failed: %s", provider.name, exc)
                health_state.record_provider_failure("quotes", provider.name, str(exc))
                continue

            if fetched:
                count = await _repo.upsert_many(list(fetched.values()))
                total += count
                health_state.record_provider_success("quotes", provider.name, len(fetched))
            else:
                health_state.record_provider_failure("quotes", provider.name, "No quotes returned")

            remaining = [sym for sym in remaining if sym not in fetched]

        if total == 0:
            logger.warning("Quote ingestion returned no data for %d symbols", len(symbols))
            health_state.record_job_failure("quotes", "No quotes ingested")
            return 0

        health_state.record_job_success("quotes", total)
        logger.info("Ingested %d quotes from providers", total)
        return total
    except Exception as exc:
        health_state.record_job_failure("quotes", str(exc))
        raise
