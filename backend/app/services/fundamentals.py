from __future__ import annotations

import re

from app.ingestion.providers.symbol_fundamentals import fetch_symbol_fundamentals
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.services.cache import FUNDAMENTALS_TTL, PROFILE_TTL, cache

_repo = FundamentalsRepository()

# Legacy display like "114.3T" / "850.5B" — ambiguous; refresh once.
_LEGACY_CAP = re.compile(r"^\d+(\.\d+)?[TB]$")


def _needs_refresh(row: dict | None) -> bool:
    if not row:
        return True
    cap = row.get("marketCap") or row.get("market_cap") or "—"
    if cap in ("", "—"):
        return True
    if isinstance(cap, str) and _LEGACY_CAP.match(cap.strip()):
        return True
    return False


async def fetch_profile(symbol: str) -> dict:
    sym = symbol.upper()
    key = f"profile:{sym}"
    cached = cache.get(key)
    if cached is not None and not _needs_refresh({"marketCap": cached.get("market_cap")}):
        return cached

    row = await _repo.get(sym)
    if row and not _needs_refresh(row):
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
    if cached is not None and not _needs_refresh(cached):
        return cached

    row = await _repo.get(sym)
    if _needs_refresh(row):
        profile = await fetch_profile(sym)
        result = {
            "name": profile["name"],
            "exchange": profile["exchange"],
            "marketCap": profile["market_cap"],
            "pe": profile["pe"],
            "listedShares": profile["listed_shares"],
        }
    else:
        assert row is not None
        result = row

    cache.set(key, result, FUNDAMENTALS_TTL)
    return result
