from __future__ import annotations

import httpx

from app.services.cache import QUOTE_TTL, cache
from app.services.http_utils import BROWSER_HEADERS, safe_float, safe_int

VPS_URL = "https://bgapidatafeed.vps.com.vn/getliststockdata"


def _parse_quote(item: dict) -> dict:
    symbol = str(item.get("sym") or "").upper()
    ref = safe_float(item.get("r"))
    last = safe_float(item.get("lastPrice"))
    if last <= 0 and ref > 0:
        last = ref

    change = last - ref if ref > 0 else 0.0
    # VPS changePc is absolute; sign from price vs ref
    change_pc = abs(safe_float(item.get("changePc")))
    if change < 0:
        change_pc = -change_pc
    elif change == 0:
        change_pc = 0.0

    return {
        "symbol": symbol,
        "price": round(last, 2),
        "change": round(change, 2),
        "changePercent": round(change_pc, 2),
        "open": round(safe_float(item.get("openPrice")), 2),
        "high": round(safe_float(item.get("highPrice")), 2),
        "low": round(safe_float(item.get("lowPrice")), 2),
        "volume": safe_int(item.get("lot")),
        "ref": round(ref, 2),
    }


async def fetch_quotes(symbols: list[str]) -> dict[str, dict]:
    """Batch quotes from VPS. Prices in nghìn đồng (display units)."""
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

    url = f"{VPS_URL}/{','.join(missing)}"
    async with httpx.AsyncClient(timeout=15.0, headers=BROWSER_HEADERS) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, list):
        raise RuntimeError("Unexpected VPS response")

    for item in data:
        quote = _parse_quote(item)
        if not quote["symbol"]:
            continue
        cache.set(f"quote:{quote['symbol']}", quote, QUOTE_TTL)
        result[quote["symbol"]] = quote

    return result


async def fetch_quote(symbol: str) -> dict | None:
    quotes = await fetch_quotes([symbol])
    return quotes.get(symbol.upper())
