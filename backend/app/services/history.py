from __future__ import annotations

from app.domain.history import ChartRange, INTRADAY_RANGE, downsample_prices
from app.ingestion.providers.entrade_history import fetch_history_prices
from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS, fetch_index_history_prices
from app.ingestion.providers.yahoo_commodities import (
    COMMODITY_SYMBOLS,
    fetch_commodity_history_prices,
)
from app.repositories.history_repo import HistoryRepository
from app.services.cache import HISTORY_TTL, cache

_repo = HistoryRepository()

SPARKLINE_RANGE_ORDER: tuple[ChartRange, ...] = ("1D", "1W", "1M", "3M", "1Y", "5Y")


async def fetch_history(symbol: str, chart_range: ChartRange) -> list[float]:
    sym = symbol.upper()
    key = f"hist:{sym}:{chart_range}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    prices = await _repo.get(sym, chart_range)
    if not prices:
        if sym in COMMODITY_SYMBOLS:
            prices = await fetch_commodity_history_prices(sym, chart_range)
        elif sym in INDEX_SYMBOLS:
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


def _fallback_ranges(chart_range: ChartRange) -> list[ChartRange]:
    """Requested range first, then shorter stored ranges, never longer ones."""
    end = SPARKLINE_RANGE_ORDER.index(chart_range)
    shorter = list(reversed(SPARKLINE_RANGE_ORDER[:end]))
    return [chart_range, *shorter]


async def fetch_sparklines(
    symbols: list[str], chart_range: ChartRange
) -> dict[str, dict]:
    """Stored-only sparklines for the rail. Never fetches from a provider."""
    cleaned = [sym.upper() for sym in symbols if sym.strip()]
    if not cleaned:
        return {}

    result: dict[str, dict] = {}
    remaining = set(cleaned)
    for fallback in _fallback_ranges(chart_range):
        if not remaining:
            break
        stored = await _repo.get_many(sorted(remaining), fallback)
        for symbol, prices in stored.items():
            if not prices:
                continue
            change = None
            if len(prices) >= 2 and prices[0] > 0:
                change = round((prices[-1] - prices[0]) / prices[0] * 100, 2)
            result[symbol] = {
                "prices": downsample_prices(prices),
                "range": fallback,
                "changePercent": change,
            }
            remaining.discard(symbol)
    return result
