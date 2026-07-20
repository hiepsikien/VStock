from __future__ import annotations

from app.ingestion.providers.registry import get_quote_registry
from app.repositories.quotes_repo import QuotesRepository
from app.services.cache import QUOTE_TTL, cache

_repo = QuotesRepository()


async def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Serve quotes from SQLite store; bootstrap missing symbols via providers."""
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    if not cleaned:
        return {}

    result: dict[str, dict] = {}
    missing: list[str] = []

    for sym in cleaned:
        cached = cache.get(f"quote:{sym}")
        if cached is not None:
            result[sym] = cached
            continue
        missing.append(sym)

    if missing:
        from_db = await _repo.get_latest(missing)
        for sym, payload in from_db.items():
            cache.set(f"quote:{sym}", payload, QUOTE_TTL)
            result[sym] = payload
        missing = [sym for sym in missing if sym not in result]

    if missing:
        registry = get_quote_registry()
        fetched = await registry.fetch_quotes(missing)
        if fetched:
            await _repo.upsert_many(list(fetched.values()))
        for sym in missing:
            quote = fetched.get(sym)
            if not quote:
                continue
            payload = quote.to_dict()
            cache.set(f"quote:{sym}", payload, QUOTE_TTL)
            result[sym] = payload

    return result


async def fetch_quote(symbol: str) -> dict | None:
    quotes = await fetch_quotes([symbol])
    return quotes.get(symbol.upper())
