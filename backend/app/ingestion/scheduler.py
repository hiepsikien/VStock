from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.health import state as health_state
from app.ingestion.config import load_ingestion_settings, load_news_providers, load_quote_providers
from app.ingestion.jobs.history import ingest_history_daily, ingest_history_intraday
from app.ingestion.jobs.indices import ingest_indices
from app.ingestion.jobs.news import ingest_news
from app.ingestion.jobs.quotes import ingest_quotes

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _seed_provider_records() -> None:
    for row in load_quote_providers():
        name = str(row.get("name", "")).strip()
        if name:
            health_state.ensure_provider("quotes", name)

    for row in load_news_providers():
        name = str(row.get("name", "")).strip()
        if name:
            health_state.ensure_provider("news", name)

    health_state.ensure_provider("indices", "entrade")
    health_state.ensure_provider("history", "entrade")


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = load_ingestion_settings()
    _seed_provider_records()

    _scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
    _scheduler.add_job(
        ingest_quotes,
        trigger="interval",
        seconds=settings.quote_interval_open_seconds,
        id="ingest_quotes",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        ingest_news,
        trigger="interval",
        seconds=settings.news_interval_seconds,
        id="ingest_news",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        ingest_indices,
        trigger="interval",
        seconds=settings.indices_interval_seconds,
        id="ingest_indices",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        ingest_history_intraday,
        trigger="interval",
        seconds=settings.history_intraday_interval_seconds,
        id="ingest_history_intraday",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        ingest_history_daily,
        trigger="cron",
        hour=settings.history_daily_hour,
        minute=settings.history_daily_minute,
        id="ingest_history_daily",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "Ingestion scheduler started (quotes=%ss, news=%ss, indices=%ss, history_intraday=%ss, quote_symbols=%d)",
        settings.quote_interval_open_seconds,
        settings.news_interval_seconds,
        settings.indices_interval_seconds,
        settings.history_intraday_interval_seconds,
        len(settings.quote_symbols),
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Ingestion scheduler stopped")
