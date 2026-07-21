from __future__ import annotations

import asyncio
import logging

import httpx

from app.domain.history import ChartRange, downsample_prices
from app.services.http_utils import safe_float

logger = logging.getLogger(__name__)

# query2 is less aggressive about 429 than query1 for chart polls.
YAHOO_CHART_HOSTS = (
    "https://query2.finance.yahoo.com/v8/finance/chart",
    "https://query1.finance.yahoo.com/v8/finance/chart",
)

YAHOO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VStock/1.0; +https://github.com/vstock)",
    "Accept": "application/json",
}

# Strip symbols — not VN equity indices; used for watchlist header + Detail.
COMMODITY_STRIP = (
    {
        "symbol": "XAU",
        "yahoo": "GC=F",
        "name": "Vàng",
        "exchange": "COMEX",
        "currency": "USD",
    },
    {
        "symbol": "WTI",
        "yahoo": "CL=F",
        "name": "Dầu WTI",
        "exchange": "NYMEX",
        "currency": "USD",
    },
)

COMMODITY_SYMBOLS = frozenset(item["symbol"] for item in COMMODITY_STRIP)

_COMMODITY_BY_SYMBOL = {item["symbol"]: item for item in COMMODITY_STRIP}

# Map app chart ranges → Yahoo (range, interval).
YAHOO_RANGE_PARAMS: dict[ChartRange, tuple[str, str]] = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
}


def _yahoo_symbol(app_symbol: str) -> str | None:
    meta = _COMMODITY_BY_SYMBOL.get(app_symbol.upper())
    return meta["yahoo"] if meta else None


def _parse_quote(payload: dict, meta: dict) -> dict | None:
    result = ((payload or {}).get("chart") or {}).get("result") or []
    if not result:
        return None

    chart = result[0]
    chart_meta = chart.get("meta") or {}
    price = safe_float(chart_meta.get("regularMarketPrice"))
    if price <= 0:
        return None

    ref = safe_float(
        chart_meta.get("chartPreviousClose")
        or chart_meta.get("previousClose")
        or chart_meta.get("regularMarketPreviousClose"),
    )
    if ref <= 0:
        ref = price

    change = round(price - ref, 2)
    change_pct = round((change / ref) * 100, 2) if ref else 0.0

    # Prefer session day high/low from meta; open from first intraday bar.
    high = safe_float(chart_meta.get("regularMarketDayHigh"))
    low = safe_float(chart_meta.get("regularMarketDayLow"))
    open_price = safe_float(chart_meta.get("regularMarketOpen"))

    quote = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    opens = [safe_float(v) for v in (quote.get("open") or []) if safe_float(v) > 0]
    highs = [safe_float(v) for v in (quote.get("high") or []) if safe_float(v) > 0]
    lows = [safe_float(v) for v in (quote.get("low") or []) if safe_float(v) > 0]

    if open_price <= 0 and opens:
        open_price = opens[0]
    if high <= 0 and highs:
        high = max(highs)
    if low <= 0 and lows:
        low = min(lows)

    if open_price <= 0:
        open_price = price
    if high <= 0:
        high = price
    if low <= 0:
        low = price

    return {
        "symbol": meta["symbol"],
        "name": meta["name"],
        "exchange": meta["exchange"],
        "price": round(price, 2),
        "change": change,
        "changePercent": change_pct,
        "priorClose": round(ref, 2),
        "open": round(open_price, 2),
        "high": round(high, 2),
        "low": round(low, 2),
        "currency": meta["currency"],
        "source": "yahoo",
    }


def _closes_from_payload(payload: dict) -> list[float]:
    result = ((payload or {}).get("chart") or {}).get("result") or []
    if not result:
        return []
    quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    return [round(safe_float(c), 2) for c in closes if safe_float(c) > 0]


async def _get_chart(
    client: httpx.AsyncClient,
    yahoo_symbol: str,
    *,
    range_: str,
    interval: str,
) -> dict | None:
    last_error: Exception | None = None
    for base in YAHOO_CHART_HOSTS:
        try:
            resp = await client.get(
                f"{base}/{yahoo_symbol}",
                params={"interval": interval, "range": range_},
            )
            if resp.status_code == 429:
                last_error = httpx.HTTPStatusError(
                    "Yahoo rate limited",
                    request=resp.request,
                    response=resp,
                )
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        logger.warning("Yahoo chart %s failed: %s", yahoo_symbol, last_error)
    return None


async def _fetch_yahoo_quote(client: httpx.AsyncClient, meta: dict) -> dict | None:
    # 1d/5m gives session OHLC bars; fall back to daily if empty.
    for range_, interval in (("1d", "5m"), ("5d", "1d")):
        payload = await _get_chart(
            client,
            meta["yahoo"],
            range_=range_,
            interval=interval,
        )
        if not payload:
            continue
        row = _parse_quote(payload, meta)
        if row:
            return row
    return None


async def fetch_commodity_strip() -> list[dict]:
    async with httpx.AsyncClient(
        timeout=12.0,
        headers=YAHOO_HEADERS,
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *(_fetch_yahoo_quote(client, meta) for meta in COMMODITY_STRIP),
        )

    # Preserve strip order (Vàng → Dầu WTI).
    return [row for row in results if row]


async def fetch_commodity_quote(symbol: str) -> dict | None:
    meta = _COMMODITY_BY_SYMBOL.get(symbol.upper())
    if not meta:
        return None

    async with httpx.AsyncClient(
        timeout=12.0,
        headers=YAHOO_HEADERS,
        follow_redirects=True,
    ) as client:
        return await _fetch_yahoo_quote(client, meta)


async def fetch_commodity_history_prices(symbol: str, chart_range: ChartRange) -> list[float]:
    yahoo = _yahoo_symbol(symbol)
    if not yahoo:
        return []

    range_, interval = YAHOO_RANGE_PARAMS[chart_range]
    async with httpx.AsyncClient(
        timeout=20.0,
        headers=YAHOO_HEADERS,
        follow_redirects=True,
    ) as client:
        payload = await _get_chart(client, yahoo, range_=range_, interval=interval)

    if not payload:
        return []
    return downsample_prices(_closes_from_payload(payload))
