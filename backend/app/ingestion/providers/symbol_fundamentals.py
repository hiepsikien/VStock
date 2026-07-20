from __future__ import annotations

from datetime import date, timedelta

import httpx

from app.ingestion.providers.market_symbols import normalize_exchange
from app.services.http_utils import BROWSER_HEADERS, format_market_cap, safe_float, safe_int

VNDIRECT_STOCKS = "https://api-finfo.vndirect.com.vn/v4/stocks"
SSI_STOCK = "https://iboard-query.ssi.com.vn/stock"
SIMPLIZE_SUMMARY = "https://api.simplize.vn/api/company/summary"
KBS_BASE = "https://kbbuddywts.kbsec.com.vn/sas/kbsv-stock-data-store/stock"


async def fetch_symbol_fundamentals(symbol: str) -> dict:
    sym = symbol.upper()
    profile = {
        "symbol": sym,
        "name": sym,
        "exchange": "HOSE",
        "listed_shares": 0,
        "market_cap": "—",
        "pe": None,
    }

    async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
        # 1) Name / exchange — VNDirect
        try:
            resp = await client.get(
                VNDIRECT_STOCKS,
                params={"q": f"code:{sym}", "size": 1},
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
                        or sym
                    )
                    profile["exchange"] = normalize_exchange(str(row.get("floor") or "HOSE"))
        except Exception:
            pass

        # 2) Market cap / shares / PE — Simplize (authoritative VND units)
        try:
            resp = await client.get(f"{SIMPLIZE_SUMMARY}/{sym}")
            if resp.status_code == 200:
                data = (resp.json() or {}).get("data") or {}
                if isinstance(data, dict) and data:
                    if profile["name"] == sym:
                        profile["name"] = data.get("nameEn") or data.get("name") or data.get("nameVi") or sym
                    shares = safe_int(
                        data.get("outstandingSharesValue") or data.get("outstandingShare"),
                    )
                    if shares > 0:
                        profile["listed_shares"] = shares
                    mcap = safe_float(data.get("marketCap"))
                    if mcap > 0:
                        profile["market_cap"] = format_market_cap(mcap)
                    pe = safe_float(data.get("peRatio"), default=-1)
                    if pe >= 0:
                        profile["pe"] = pe
        except Exception:
            pass

        # 3) SSI — name/exchange + listed*price fallback when Simplize missing
        try:
            resp = await client.get(f"{SSI_STOCK}/{sym}")
            if resp.status_code == 200:
                data = (resp.json() or {}).get("data") or {}
                if profile["name"] == sym:
                    if data.get("companyNameEn"):
                        profile["name"] = data["companyNameEn"]
                    elif data.get("companyNameVi"):
                        profile["name"] = data["companyNameVi"]
                exch = str(data.get("exchange") or profile["exchange"]).upper()
                profile["exchange"] = normalize_exchange(exch)
                listed = safe_int(data.get("listedShare"))
                if listed > 0 and profile["listed_shares"] <= 0:
                    profile["listed_shares"] = listed
                price_vnd = safe_float(
                    data.get("matchedPrice") or data.get("refPrice") or data.get("priorClosePrice"),
                )
                if profile["market_cap"] == "—" and listed > 0 and price_vnd > 0:
                    profile["market_cap"] = format_market_cap(listed * price_vnd)
        except Exception:
            pass

        # 4) KBS — PE only (MarketCapital units are unreliable / endpoint often 404)
        if profile["pe"] is None:
            try:
                to_date = date.today().isoformat()
                from_date = (date.today() - timedelta(days=10)).isoformat()
                resp = await client.get(
                    f"{KBS_BASE}/{sym}/historical-quotes",
                    params={"from": from_date, "to": to_date},
                )
                if resp.status_code == 200:
                    quotes = resp.json()
                    if isinstance(quotes, list) and quotes:
                        pe = safe_float(quotes[0].get("PE"), default=-1)
                        profile["pe"] = pe if pe >= 0 else None
            except Exception:
                pass

    return profile
