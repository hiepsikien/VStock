from __future__ import annotations

import asyncio

import httpx

from app.services.http_utils import BROWSER_HEADERS

SSI_EXCHANGE = "https://iboard-query.ssi.com.vn/stock/exchange"
VNDIRECT_STOCKS = "https://api-finfo.vndirect.com.vn/v4/stocks"


def normalize_exchange(value: str) -> str:
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
                "exchange": normalize_exchange(row.get("exchange") or exchange),
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
                "exchange": normalize_exchange(row.get("floor") or floor),
            }
        )
    return results


def dedupe_symbols(symbols: list[dict]) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for item in symbols:
        sym = item["symbol"]
        existing = by_symbol.get(sym)
        if existing is None or (
            existing["exchange"] != "HOSE" and item["exchange"] == "HOSE"
        ):
            by_symbol[sym] = item
    return sorted(by_symbol.values(), key=lambda x: x["symbol"])


async def fetch_all_market_symbols() -> tuple[list[dict], str]:
    """Return (symbols, source_name)."""
    async with httpx.AsyncClient(timeout=30.0, headers=BROWSER_HEADERS) as client:
        source = "ssi"
        try:
            hose, hnx = await asyncio.gather(
                _fetch_ssi_exchange(client, "hose"),
                _fetch_ssi_exchange(client, "hnx"),
            )
            symbols = hose + hnx
        except Exception:
            source = "vndirect"
            hose, hnx = await asyncio.gather(
                _fetch_vndirect_floor(client, "HOSE"),
                _fetch_vndirect_floor(client, "HNX"),
            )
            symbols = hose + hnx

        if source == "ssi":
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

    return dedupe_symbols(symbols), source
