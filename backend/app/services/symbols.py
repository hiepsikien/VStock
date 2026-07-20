from __future__ import annotations

import asyncio

import httpx

from app.services.cache import cache
from app.services.http_utils import BROWSER_HEADERS

SSI_EXCHANGE = "https://iboard-query.ssi.com.vn/stock/exchange"
VNDIRECT_STOCKS = "https://api-finfo.vndirect.com.vn/v4/stocks"

SYMBOLS_TTL = 6 * 3600


def _normalize_exchange(value: str) -> str:
    v = (value or "").upper()
    if v in {"HOSE", "HSX", "STO"}:
        return "HOSE"
    if v in {"HNX", "STX"}:
        return "HNX"
    return v or "HOSE"


async def _fetch_ssi_exchange(client: httpx.AsyncClient, exchange: str) -> list[dict]:
    resp = await client.get(f"{SSI_EXCHANGE}/{exchange}")
    resp.raise_for_status()
    rows = (resp.json() or {}).get("data") or []
    results: list[dict] = []
    for row in rows:
        symbol = str(row.get("stockSymbol") or "").upper().strip()
        if not symbol:
            continue
        name = (
            row.get("companyNameEn")
            or row.get("clientNameEn")
            or row.get("companyNameVi")
            or row.get("clientName")
            or symbol
        )
        results.append(
            {
                "symbol": symbol,
                "name": name,
                "exchange": _normalize_exchange(row.get("exchange") or exchange),
            }
        )
    return results


async def _fetch_vndirect_floor(client: httpx.AsyncClient, floor: str) -> list[dict]:
    resp = await client.get(
        VNDIRECT_STOCKS,
        params={"q": f"type:STOCK~floor:{floor}~status:listed", "size": 2000},
    )
    resp.raise_for_status()
    rows = (resp.json() or {}).get("data") or []
    results: list[dict] = []
    for row in rows:
        symbol = str(row.get("code") or "").upper().strip()
        if not symbol:
            continue
        name = (
            row.get("shortNameEng")
            or row.get("shortName")
            or row.get("companyNameEng")
            or row.get("companyName")
            or symbol
        )
        results.append(
            {
                "symbol": symbol,
                "name": name,
                "exchange": _normalize_exchange(row.get("floor") or floor),
            }
        )
    return results


def _dedupe(symbols: list[dict]) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for item in symbols:
        sym = item["symbol"]
        existing = by_symbol.get(sym)
        if existing is None or (
            existing["exchange"] != "HOSE" and item["exchange"] == "HOSE"
        ):
            by_symbol[sym] = item
    return sorted(by_symbol.values(), key=lambda x: x["symbol"])


async def fetch_all_symbols() -> list[dict]:
    cached = cache.get("symbols:all")
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=30.0, headers=BROWSER_HEADERS) as client:
        try:
            hose, hnx = await asyncio.gather(
                _fetch_ssi_exchange(client, "hose"),
                _fetch_ssi_exchange(client, "hnx"),
            )
            symbols = hose + hnx
        except Exception:
            hose, hnx = await asyncio.gather(
                _fetch_vndirect_floor(client, "HOSE"),
                _fetch_vndirect_floor(client, "HNX"),
            )
            symbols = hose + hnx

        # Overlay shorter VNDirect names for better search UX
        try:
            vd_hose, vd_hnx = await asyncio.gather(
                _fetch_vndirect_floor(client, "HOSE"),
                _fetch_vndirect_floor(client, "HNX"),
            )
            short_names = {r["symbol"]: r["name"] for r in vd_hose + vd_hnx}
            for item in symbols:
                short = short_names.get(item["symbol"])
                if short and len(short) < len(item["name"]):
                    item["name"] = short
        except Exception:
            pass

    if not symbols:
        raise RuntimeError("Unable to load market symbols")

    ordered = _dedupe(symbols)
    cache.set("symbols:all", ordered, SYMBOLS_TTL)
    return ordered

async def search_symbols(query: str, limit: int = 30) -> list[dict]:
    q = query.strip().upper()
    if not q:
        return []

    all_symbols = await fetch_all_symbols()
    starts: list[dict] = []
    contains: list[dict] = []
    for item in all_symbols:
        sym = item["symbol"]
        name = str(item["name"]).upper()
        if sym.startswith(q):
            starts.append(item)
        elif q in sym or q in name:
            contains.append(item)

    return (starts + contains)[:limit]
