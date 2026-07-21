from __future__ import annotations

from app.ingestion.providers.market_symbols import fetch_all_market_symbols
from app.repositories.symbols_repo import SymbolsRepository
from app.services.cache import cache

SYMBOLS_TTL = 6 * 3600

_repo = SymbolsRepository()


async def fetch_all_symbols() -> list[dict]:
    cached = cache.get("symbols:all")
    if cached is not None:
        return cached

    rows = await _repo.get_all()
    if len(rows) < 50:
        live, _source = await fetch_all_market_symbols()
        if live:
            await _repo.upsert_many(live)
            rows = await _repo.get_all()

    if not rows:
        raise RuntimeError("Unable to load market symbols")

    cache.set("symbols:all", rows, SYMBOLS_TTL)
    return rows


async def search_symbols(query: str, limit: int = 30) -> list[dict]:
    q = query.strip()
    if not q:
        return []

    rows = await _repo.search(q, limit)
    if rows:
        return rows

    all_symbols = await fetch_all_symbols()
    q_upper = q.upper()
    starts: list[dict] = []
    contains: list[dict] = []
    for item in all_symbols:
        sym = item["symbol"]
        name = str(item["name"]).upper()
        if sym.startswith(q_upper):
            starts.append(item)
        elif q_upper in sym or q_upper in name:
            contains.append(item)

    return (starts + contains)[:limit]


async def lookup_symbol(symbol: str) -> dict | None:
    """Metadata for a symbol (name, exchange) even when quotes are missing."""
    sym = symbol.strip().upper()
    if not sym:
        return None
    row = await _repo.get(sym)
    if row:
        return row
    try:
        all_symbols = await fetch_all_symbols()
    except RuntimeError:
        return None
    for item in all_symbols:
        if item.get("symbol") == sym:
            return item
    return None
