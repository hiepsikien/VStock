from __future__ import annotations

import asyncio
import logging

from app.health import state as health_state
from app.ingestion.providers.market_symbols import fetch_all_market_symbols
from app.repositories.symbols_repo import SymbolsRepository

logger = logging.getLogger(__name__)
_repo = SymbolsRepository()


async def ingest_symbols(*, force: bool = False) -> int:
    del force
    try:
        rows, source = await fetch_all_market_symbols()
        count = await _repo.upsert_many(rows)
        health_state.record_provider_success("symbols", source, count)
        health_state.record_job_success("symbols", count)
        logger.info("Ingested %d symbols from %s", count, source)
        return count
    except Exception as exc:
        health_state.record_provider_failure("symbols", "ssi", str(exc))
        health_state.record_provider_failure("symbols", "vndirect", str(exc))
        health_state.record_job_failure("symbols", str(exc))
        raise
