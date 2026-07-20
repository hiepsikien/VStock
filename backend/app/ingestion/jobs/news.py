from __future__ import annotations

import logging

from app.health import state as health_state
from app.ingestion.config import load_ingestion_settings
from app.ingestion.providers.news_registry import get_news_registry
from app.repositories.news_repo import NewsRepository

logger = logging.getLogger(__name__)
_repo = NewsRepository()


async def ingest_news(*, force: bool = False) -> int:
    settings = load_ingestion_settings()
    limit = settings.news_market_limit
    registry = get_news_registry()
    total = 0

    try:
        for provider in registry.providers:
            per_provider = max(limit // max(len(registry.providers), 1), 10)
            try:
                articles = await provider.fetch_market_news(per_provider)
                if articles:
                    count = await _repo.upsert_many(articles, provider=provider.name)
                    total += count
                    health_state.record_provider_success("news", provider.name, len(articles))
                else:
                    health_state.record_provider_failure("news", provider.name, "No articles returned")
            except Exception as exc:
                logger.warning("News provider %s failed during ingestion: %s", provider.name, exc)
                health_state.record_provider_failure("news", provider.name, str(exc))

        pruned = await _repo.prune(settings.news_max_rows)
        if pruned:
            logger.info("Pruned %d old news rows", pruned)

        health_state.record_job_success("news", total)
        logger.info("Ingested %d news articles from providers", total)
        return total
    except Exception as exc:
        health_state.record_job_failure("news", str(exc))
        raise
