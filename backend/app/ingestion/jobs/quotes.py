from __future__ import annotations

import logging

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
    fetched = await registry.fetch_quotes(symbols)
    if not fetched:
        logger.warning("Quote ingestion returned no data for %d symbols", len(symbols))
        return 0

    count = await _repo.upsert_many(list(fetched.values()))
    logger.info("Ingested %d quotes from providers", count)
    return count
