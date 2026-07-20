from __future__ import annotations

import asyncio
import logging

from app.health import state as health_state
from app.ingestion.config import load_ingestion_settings
from app.ingestion.providers.symbol_fundamentals import fetch_symbol_fundamentals
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.repositories.quotes_repo import QuotesRepository
from app.schemas import DEFAULT_WATCHLIST

logger = logging.getLogger(__name__)
_repo = FundamentalsRepository()
_quotes_repo = QuotesRepository()
_FETCH_DELAY_SECONDS = 0.2
_PROVIDER = "merge"


async def _fundamental_symbols() -> list[str]:
    settings = load_ingestion_settings()
    symbols = list(dict.fromkeys([*settings.quote_symbols, *(await _quotes_repo.list_symbols())]))
    return symbols or list(DEFAULT_WATCHLIST)


async def ingest_fundamentals(*, force: bool = False) -> int:
    del force
    symbols = await _fundamental_symbols()
    total = 0
    failures = 0

    try:
        for sym in symbols:
            try:
                profile = await fetch_symbol_fundamentals(sym)
                await _repo.upsert(profile)
                total += 1
            except Exception as exc:
                failures += 1
                logger.warning("Fundamentals fetch failed for %s: %s", sym, exc)
            await asyncio.sleep(_FETCH_DELAY_SECONDS)

        if total == 0:
            health_state.record_provider_failure("fundamentals", _PROVIDER, "No fundamentals ingested")
            health_state.record_job_failure("fundamentals", "No fundamentals ingested")
            return 0

        health_state.record_provider_success("fundamentals", _PROVIDER, total)
        health_state.record_job_success("fundamentals", total)
        logger.info(
            "Ingested fundamentals for %d symbols (%d failures)",
            total,
            failures,
        )
        return total
    except Exception as exc:
        health_state.record_provider_failure("fundamentals", _PROVIDER, str(exc))
        health_state.record_job_failure("fundamentals", str(exc))
        raise
