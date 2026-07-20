from __future__ import annotations

import httpx

from app.services.cache import PROFILE_TTL, cache
from app.services.http_utils import BROWSER_HEADERS, format_market_cap, safe_float, safe_int

VNDIRECT_STOCKS = "https://api-finfo.vndirect.com.vn/v4/stocks"
SSI_STOCK = "https://iboard-query.ssi.com.vn/stock"
KBS_BASE = "https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock"


async def fetch_profile(symbol: str) -> dict:
    key = f"profile:{symbol}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    symbol = symbol.upper()
    profile = {
        "symbol": symbol,
        "name": symbol,
        "exchange": "HOSE",
        "listed_shares": 0,
        "market_cap": "—",
        "pe": None,
    }

    async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
        # Company name + floor from VNDirect (prefer short English name)
        try:
            resp = await client.get(
                VNDIRECT_STOCKS,
                params={"q": f"code:{symbol}", "size": 1},
            )
            if resp.status_code == 200:
                rows = resp.json().get("data") or []
                if rows:
                    row = rows[0]
                    profile["name"] = (
                        row.get("shortNameEng")
                        or row.get("shortName")
                        or row.get("companyNameEng")
                        or row.get("companyName")
                        or symbol
                    )
                    floor = str(row.get("floor") or "HOSE").upper()
                    profile["exchange"] = floor
        except Exception:
            pass

        # Listed shares / market cap from SSI (keep VNDirect short name when present)
        try:
            resp = await client.get(f"{SSI_STOCK}/{symbol}")
            if resp.status_code == 200:
                data = (resp.json() or {}).get("data") or {}
                if profile["name"] == symbol:
                    if data.get("companyNameEn"):
                        profile["name"] = data["companyNameEn"]
                    elif data.get("companyNameVi"):
                        profile["name"] = data["companyNameVi"]
                exch = str(data.get("exchange") or profile["exchange"]).upper()
                profile["exchange"] = "HOSE" if exch in {"HOSE", "HSX"} else exch
                listed = safe_int(data.get("listedShare"))
                profile["listed_shares"] = listed
                price_vnd = safe_float(data.get("matchedPrice"))
                if listed and price_vnd:
                    profile["market_cap"] = format_market_cap(listed * price_vnd)
        except Exception:
            pass

        try:
            from datetime import date, timedelta

            to_date = date.today().isoformat()
            from_date = (date.today() - timedelta(days=10)).isoformat()
            resp = await client.get(
                f"{KBS_BASE}/{symbol}/historical-quotes",
                params={"from": from_date, "to": to_date},
            )
            if resp.status_code == 200:
                quotes = resp.json()
                if isinstance(quotes, list) and quotes:
                    q = quotes[0]
                    pe = safe_float(q.get("PE"), default=-1)
                    profile["pe"] = pe if pe >= 0 else None
                    mcap = safe_float(q.get("MarketCapital"))
                    if mcap > 0:
                        # KBS MarketCapital is often already in VND
                        profile["market_cap"] = format_market_cap(mcap)
        except Exception:
            pass

    cache.set(key, profile, PROFILE_TTL)
    return profile


async def fetch_fundamentals(symbol: str) -> dict:
    key = f"fund:{symbol.upper()}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    profile = await fetch_profile(symbol)
    result = {
        "name": profile["name"],
        "exchange": profile["exchange"],
        "marketCap": profile["market_cap"],
        "pe": profile["pe"],
        "listedShares": profile["listed_shares"],
    }
    from app.services.cache import FUNDAMENTALS_TTL

    cache.set(key, result, FUNDAMENTALS_TTL)
    return result
