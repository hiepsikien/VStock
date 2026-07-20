from __future__ import annotations

from app.ingestion.providers.registry import get_quote_registry
from app.repositories.quotes_repo import QuotesRepository
from app.services.cache import QUOTE_TTL, cache

_repo = QuotesRepository()


def _is_thin_payload(payload: dict) -> bool:
    return (
        float(payload.get("open") or 0) <= 0
        and float(payload.get("high") or 0) <= 0
        and float(payload.get("low") or 0) <= 0
        and int(payload.get("volume") or 0) <= 0
    )


async def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Serve quotes from SQLite store; bootstrap missing symbols via providers."""
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    if not cleaned:
        return {}

    result: dict[str, dict] = {}
    missing: list[str] = []

    for sym in cleaned:
        cached = cache.get(f"quote:{sym}")
        if cached is not None and not _is_thin_payload(cached):
            result[sym] = cached
            continue
        missing.append(sym)

    if missing:
        from_db = await _repo.get_latest(missing)
        still_missing: list[str] = []
        for sym in missing:
            payload = from_db.get(sym)
            if payload and not _is_thin_payload(payload):
                cache.set(f"quote:{sym}", payload, QUOTE_TTL)
                result[sym] = payload
            else:
                still_missing.append(sym)
        missing = still_missing

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
