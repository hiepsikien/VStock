from __future__ import annotations

from app.domain.history import ChartRange, INTRADAY_RANGE
from app.ingestion.providers.entrade_history import fetch_history_prices
from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS, fetch_index_history_prices
from app.repositories.history_repo import HistoryRepository
from app.services.cache import HISTORY_TTL, cache

_repo = HistoryRepository()


async def fetch_history(symbol: str, chart_range: ChartRange) -> list[float]:
    sym = symbol.upper()
    key = f"hist:{sym}:{chart_range}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    prices = await _repo.get(sym, chart_range)
    if not prices:
        if sym in INDEX_SYMBOLS:
            prices = await fetch_index_history_prices(sym, chart_range)
        else:
            prices = await fetch_history_prices(sym, chart_range)
        if prices:
            await _repo.upsert(sym, chart_range, prices)

    cache.set(key, prices, HISTORY_TTL)
    return prices


async def fetch_sparkline(symbol: str) -> list[float]:
    sym = symbol.upper()
    prices = await _repo.get(sym, INTRADAY_RANGE)
    if len(prices) >= 8:
        cache.set(f"hist:{sym}:1D", prices, HISTORY_TTL)
        return prices

    prices = await fetch_history(sym, INTRADAY_RANGE)
    if len(prices) >= 8:
        return prices

    week_prices = await _repo.get(sym, "1W")
    if week_prices:
        cache.set(f"hist:{sym}:1W", week_prices, HISTORY_TTL)
        return week_prices

    return await fetch_history(sym, "1W")
