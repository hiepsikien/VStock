from __future__ import annotations

import re
from datetime import datetime, timezone

from app.ingestion.providers.symbol_fundamentals import fetch_symbol_fundamentals
from app.ingestion.providers.vndirect_income import fetch_symbol_income
from app.repositories.fundamentals_repo import FundamentalsRepository
from app.repositories.income_repo import IncomeRepository
from app.services.cache import FUNDAMENTALS_TTL, PROFILE_TTL, cache

_repo = FundamentalsRepository()
_income_repo = IncomeRepository()

# Legacy display like "114.3T" / "850.5B" — ambiguous; refresh once.
_LEGACY_CAP = re.compile(r"^\d+(\.\d+)?[TB]$")
_FUND_TTL_SECONDS = 6 * 60 * 60
_INCOME_TTL_SECONDS = 6 * 60 * 60


def _age_seconds(updated_at: str | None) -> float | None:
    if not updated_at:
        return None
    try:
        ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


def _needs_refresh(row: dict | None) -> bool:
    if not row:
        return True
    cap = row.get("marketCap") or row.get("market_cap") or "—"
    if cap in ("", "—"):
        return True
    if isinstance(cap, str) and _LEGACY_CAP.match(cap.strip()):
        return True
    age = _age_seconds(row.get("updatedAt") or row.get("updated_at"))
    if age is not None and age > _FUND_TTL_SECONDS:
        return True
    return False


def _profile_from_row(sym: str, row: dict) -> dict:
    return {
        "symbol": sym,
        "name": row["name"],
        "exchange": row["exchange"],
        "listed_shares": row.get("listedShares", 0),
        "market_cap": row["marketCap"],
        "pe": row.get("pe"),
        "eps": row.get("eps"),
        "pb": row.get("pb"),
        "roe": row.get("roe"),
        "roa": row.get("roa"),
        "dividend_yield": row.get("dividendYield"),
        "updated_at": row.get("updatedAt"),
    }


def _fundamentals_result(profile: dict) -> dict:
    return {
        "name": profile["name"],
        "exchange": profile["exchange"],
        "marketCap": profile["market_cap"],
        "pe": profile.get("pe"),
        "eps": profile.get("eps"),
        "pb": profile.get("pb"),
        "roe": profile.get("roe"),
        "roa": profile.get("roa"),
        "dividendYield": profile.get("dividend_yield"),
        "listedShares": profile.get("listed_shares", 0),
        "updatedAt": profile.get("updated_at")
        or datetime.now(timezone.utc).isoformat(),
    }


def _income_stale(updated_at: str | None) -> bool:
    age = _age_seconds(updated_at)
    if age is None:
        return True
    return age > _INCOME_TTL_SECONDS


async def fetch_profile(symbol: str) -> dict:
    sym = symbol.upper()
    key = f"profile:{sym}"
    cached = cache.get(key)
    if cached is not None and not _needs_refresh(
        {
            "marketCap": cached.get("market_cap"),
            "updatedAt": cached.get("updated_at"),
        }
    ):
        return cached

    row = await _repo.get(sym)
    if row and not _needs_refresh(row):
        profile = _profile_from_row(sym, row)
        cache.set(key, profile, PROFILE_TTL)
        return profile

    profile = await fetch_symbol_fundamentals(sym)
    await _repo.upsert(profile)
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
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
        result = _fundamentals_result(profile)
    else:
        assert row is not None
        result = row

    cache.set(key, result, FUNDAMENTALS_TTL)
    return result


async def fetch_income(symbol: str) -> dict:
    sym = symbol.upper()
    key = f"income:{sym}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    row = await _income_repo.get(sym)
    if row and not _income_stale(row.get("updatedAt")) and (
        row.get("latestAnnual") or row.get("lastQuarters")
    ):
        result = {
            "revenueLabel": row["revenueLabel"],
            "latestAnnual": row["latestAnnual"],
            "lastQuarters": row["lastQuarters"],
        }
        cache.set(key, result, FUNDAMENTALS_TTL)
        return result

    payload = await fetch_symbol_income(sym)
    await _income_repo.upsert(payload)
    result = {
        "revenueLabel": payload["revenueLabel"],
        "latestAnnual": payload["latestAnnual"],
        "lastQuarters": payload["lastQuarters"],
    }
    cache.set(key, result, FUNDAMENTALS_TTL)
    return result
