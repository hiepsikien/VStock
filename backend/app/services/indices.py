from __future__ import annotations

from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS, fetch_all_indices
from app.repositories.indices_repo import IndicesRepository
from app.services.cache import cache

INDEX_TTL = 30

_repo = IndicesRepository()


async def fetch_market_indices() -> list[dict]:
    key = "indices:market"
    cached = cache.get(key)
    if cached is not None:
        return cached

    rows = await _repo.get_all()
    if len(rows) < 2:
        live = await fetch_all_indices()
        if live:
            await _repo.upsert_many(live)
            rows = await _repo.get_all()

    cache.set(key, rows, INDEX_TTL)
    return rows


async def fetch_index(symbol: str) -> dict | None:
    sym = symbol.upper()
    if sym not in INDEX_SYMBOLS:
        return None

    rows = await fetch_market_indices()
    match = next((row for row in rows if row["symbol"] == sym), None)

    try:
        live_rows = await fetch_all_indices()
        live = next((row for row in live_rows if row["symbol"] == sym), None)
        if live:
            await _repo.upsert_many([live])
            cache.set("indices:market", live_rows, INDEX_TTL)
            if match:
                match = {**match, **live}
            else:
                match = live
    except Exception:
        pass

    return match
