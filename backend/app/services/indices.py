from __future__ import annotations

from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS, fetch_all_indices
from app.ingestion.providers.yahoo_commodities import (
    COMMODITY_SYMBOLS,
    fetch_commodity_quote,
    fetch_commodity_strip,
)
from app.repositories.indices_repo import IndicesRepository
from app.services.cache import cache

INDEX_TTL = 30
COMMODITY_TTL = 120
EMPTY_COMMODITY_TTL = 20

_repo = IndicesRepository()


async def _equity_indices() -> list[dict]:
    key = "indices:equity"
    cached = cache.get(key)
    if cached is not None:
        return cached

    rows = await _repo.get_all()
    if len(rows) < 2:
        live = await fetch_all_indices()
        if live:
            await _repo.upsert_many(live)
            rows = await _repo.get_all()

    # Normalize currency for equity indices (points).
    normalized = [{**row, "currency": row.get("currency") or ""} for row in rows]
    cache.set(key, normalized, INDEX_TTL)
    cache.set("indices:market", normalized, INDEX_TTL)
    return normalized


async def _commodity_indices() -> list[dict]:
    key = "indices:commodities"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        rows = await fetch_commodity_strip()
    except Exception:
        rows = []

    # Avoid caching empty Yahoo failures for the full TTL (retry sooner).
    cache.set(key, rows, COMMODITY_TTL if rows else EMPTY_COMMODITY_TTL)
    return rows


async def fetch_market_indices() -> list[dict]:
    equity = await _equity_indices()
    commodities = await _commodity_indices()
    return [*equity, *commodities]


async def fetch_commodity(symbol: str) -> dict | None:
    sym = symbol.upper()
    if sym not in COMMODITY_SYMBOLS:
        return None

    rows = await _commodity_indices()
    match = next((row for row in rows if row["symbol"] == sym), None)

    try:
        live = await fetch_commodity_quote(sym)
        if live:
            # Refresh strip cache entry for this symbol.
            refreshed = [
                live if row["symbol"] == sym else row for row in (rows or [live])
            ]
            if not any(row["symbol"] == sym for row in refreshed):
                refreshed.append(live)
            cache.set("indices:commodities", refreshed, COMMODITY_TTL)
            match = live
    except Exception:
        pass

    return match


async def fetch_index(symbol: str) -> dict | None:
    sym = symbol.upper()

    if sym in COMMODITY_SYMBOLS:
        return await fetch_commodity(sym)

    if sym not in INDEX_SYMBOLS:
        return None

    rows = await _equity_indices()
    match = next((row for row in rows if row["symbol"] == sym), None)

    try:
        live_rows = await fetch_all_indices()
        live = next((row for row in live_rows if row["symbol"] == sym), None)
        if live:
            await _repo.upsert_many([live])
            normalized = [{**row, "currency": ""} for row in live_rows]
            cache.set("indices:equity", normalized, INDEX_TTL)
            live = {**live, "currency": ""}
            if match:
                match = {**match, **live}
            else:
                match = live
    except Exception:
        pass

    return match
