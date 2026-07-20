from __future__ import annotations

import asyncio
import logging

from app.domain.history import ChartRange, DAILY_RANGES, INTRADAY_RANGE
from app.health import state as health_state
from app.ingestion.config import load_ingestion_settings
from app.ingestion.providers.entrade_history import fetch_history_prices
from app.repositories.history_repo import HistoryRepository
from app.repositories.quotes_repo import QuotesRepository
from app.schemas import DEFAULT_WATCHLIST
from app.services.market_session import is_market_open

logger = logging.getLogger(__name__)
_history_repo = HistoryRepository()
_quotes_repo = QuotesRepository()
_PROVIDER = "entrade"
_FETCH_DELAY_SECONDS = 0.15


async def _ingest_symbols() -> list[str]:
    settings = load_ingestion_settings()
    symbols = list(dict.fromkeys([*settings.quote_symbols, *(await _quotes_repo.list_symbols())]))
    return symbols or list(DEFAULT_WATCHLIST)


async def _ingest_ranges(
    ranges: list[ChartRange],
    *,
    job_name: str,
    force: bool = False,
    require_market_open: bool = True,
) -> int:
    settings = load_ingestion_settings()
    if require_market_open and not force and settings.skip_when_market_closed and not is_market_open():
        return 0

    symbols = await _ingest_symbols()
    total = 0
    failures = 0

    try:
        for sym in symbols:
            for chart_range in ranges:
                try:
                    prices = await fetch_history_prices(sym, chart_range)
                    if prices:
                        await _history_repo.upsert(sym, chart_range, prices)
                        total += 1
                    else:
                        failures += 1
                except Exception as exc:
                    failures += 1
                    logger.warning(
                        "History fetch failed for %s %s: %s",
                        sym,
                        chart_range,
                        exc,
                    )
                await asyncio.sleep(_FETCH_DELAY_SECONDS)

        if total == 0:
            health_state.record_provider_failure("history", _PROVIDER, "No history rows ingested")
            health_state.record_job_failure(job_name, "No history ingested")
            logger.warning("History job %s returned no data", job_name)
            return 0

        health_state.record_provider_success("history", _PROVIDER, total)
        health_state.record_job_success(job_name, total)
        logger.info(
            "History job %s ingested %d rows (%d failures) for %d symbols",
            job_name,
            total,
            failures,
            len(symbols),
        )
        return total
    except Exception as exc:
        health_state.record_provider_failure("history", _PROVIDER, str(exc))
        health_state.record_job_failure(job_name, str(exc))
        raise


async def ingest_history_intraday(*, force: bool = False) -> int:
    return await _ingest_ranges(
        [INTRADAY_RANGE],
        job_name="history_intraday",
        force=force,
        require_market_open=True,
    )


async def ingest_history_daily(*, force: bool = False) -> int:
    return await _ingest_ranges(
        list(DAILY_RANGES),
        job_name="history_daily",
        force=force,
        require_market_open=False,
    )
