from __future__ import annotations

from app.ingestion.providers.entrade_indices import fetch_all_indices
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
