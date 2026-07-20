from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.ingestion.config import load_ingestion_settings
from app.ingestion.jobs.quotes import ingest_quotes

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = load_ingestion_settings()
    _scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
    _scheduler.add_job(
        ingest_quotes,
        trigger="interval",
        seconds=settings.quote_interval_open_seconds,
        id="ingest_quotes",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "Quote ingestion scheduler started (interval=%ss, symbols=%d)",
        settings.quote_interval_open_seconds,
        len(settings.quote_symbols),
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Quote ingestion scheduler stopped")
