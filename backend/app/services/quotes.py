from __future__ import annotations

from app.ingestion.providers.registry import get_quote_registry
from app.services.cache import QUOTE_TTL, cache


async def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Fetch quotes via provider failover chain. Prices in nghìn đồng."""
    cleaned = [s.strip().upper() for s in symbols if s.strip()]
    if not cleaned:
        return {}

    missing: list[str] = []
    result: dict[str, dict] = {}
    for sym in cleaned:
        cached = cache.get(f"quote:{sym}")
        if cached is not None:
            result[sym] = cached
        else:
            missing.append(sym)

    if not missing:
        return result

    registry = get_quote_registry()
    fetched = await registry.fetch_quotes(missing)

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
