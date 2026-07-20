from __future__ import annotations

import logging

from app.health import state as health_state
from app.ingestion.config import load_ingestion_settings
from app.ingestion.providers.entrade_indices import fetch_all_indices
from app.repositories.indices_repo import IndicesRepository
from app.services.market_session import is_market_open

logger = logging.getLogger(__name__)
_repo = IndicesRepository()
_PROVIDER = "entrade"


async def ingest_indices(*, force: bool = False) -> int:
    settings = load_ingestion_settings()
    if not force and settings.skip_when_market_closed and not is_market_open():
        return 0

    try:
        rows = await fetch_all_indices()
        if not rows:
            health_state.record_provider_failure("indices", _PROVIDER, "No index data returned")
            health_state.record_job_failure("indices", "No indices ingested")
            logger.warning("Index ingestion returned no data")
            return 0

        count = await _repo.upsert_many(rows)
        health_state.record_provider_success("indices", _PROVIDER, count)
        health_state.record_job_success("indices", count)
        logger.info("Ingested %d indices from %s", count, _PROVIDER)
        return count
    except Exception as exc:
        health_state.record_provider_failure("indices", _PROVIDER, str(exc))
        health_state.record_job_failure("indices", str(exc))
        raise
