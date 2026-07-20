from __future__ import annotations

from app.ingestion.providers.symbol_fundamentals import fetch_symbol_fundamentals
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.services.cache import FUNDAMENTALS_TTL, PROFILE_TTL, cache

_repo = FundamentalsRepository()


async def fetch_profile(symbol: str) -> dict:
    sym = symbol.upper()
    key = f"profile:{sym}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    row = await _repo.get(sym)
    if row:
        profile = {
            "symbol": sym,
            "name": row["name"],
            "exchange": row["exchange"],
            "listed_shares": row.get("listedShares", 0),
            "market_cap": row["marketCap"],
            "pe": row["pe"],
        }
        cache.set(key, profile, PROFILE_TTL)
        return profile

    profile = await fetch_symbol_fundamentals(sym)
    await _repo.upsert(profile)
    cache.set(key, profile, PROFILE_TTL)
    return profile


async def fetch_fundamentals(symbol: str) -> dict:
    sym = symbol.upper()
    key = f"fund:{sym}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    row = await _repo.get(sym)
    if not row:
        profile = await fetch_profile(sym)
        result = {
            "name": profile["name"],
            "exchange": profile["exchange"],
            "marketCap": profile["market_cap"],
            "pe": profile["pe"],
            "listedShares": profile["listed_shares"],
        }
    else:
        result = row

    cache.set(key, result, FUNDAMENTALS_TTL)
    return result
