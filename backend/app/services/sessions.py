"""1-minute HOSE sessions for the last few trading days, and their recap audio."""

from __future__ import annotations

import asyncio
import time
from datetime import date

import httpx

from app.services.cache import cache
from app.services.http_utils import ENTRADE_HEADERS
from app.sonify.audio import RecapAsset, RecapUnavailable, recap_store
from app.sonify.model import Variant
from app.sonify.session import samples_from_ohlc, session_dates, session_points

ENTRADE_OHLC = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
# Calendar span that still covers seven sessions across a holiday week.
LOOKBACK_DAYS = 18
MINUTE_TTL = 45


def _cache_key(symbol: str) -> str:
    return f"minute-ohlc:{symbol}"


async def fetch_minute_payload(symbol: str) -> dict:
    sym = symbol.upper()
    key = _cache_key(sym)
    cached = cache.get(key)
    if cached is not None:
        return cached

    now = int(time.time())
    params = {
        "from": now - LOOKBACK_DAYS * 24 * 3600,
        "to": now,
        "symbol": sym,
        "resolution": "1",
    }
    async with httpx.AsyncClient(timeout=20.0, headers=ENTRADE_HEADERS) as client:
        response = await client.get(ENTRADE_OHLC, params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("minute history payload is not an object")
    cache.set(key, payload, MINUTE_TTL)
    return payload


def session_change_percent(first: float, last: float) -> float:
    if first <= 0:
        return 0.0
    return round((last - first) / first * 100, 2)


def summarize_sessions(payload: dict, limit: int = 7) -> list[dict]:
    samples = samples_from_ohlc(payload)
    rows: list[dict] = []
    for day in session_dates(samples, limit):
        points = session_points(samples, day)
        if not points:
            continue
        first = points[0].bar.close
        last = points[-1].bar.close
        rows.append(
            {
                "date": day.isoformat(),
                "close": round(last, 2),
                "changePercent": session_change_percent(first, last),
                "bars": len(points),
            }
        )
    return rows


def minute_series(payload: dict, day: date) -> dict | None:
    points = session_points(samples_from_ohlc(payload), day)
    if not points:
        return None
    first = points[0].bar.close
    last = points[-1].bar.close
    return {
        "date": day.isoformat(),
        "prices": [round(point.bar.close, 2) for point in points],
        "times": [point.moment.strftime("%H:%M") for point in points],
        "changePercent": session_change_percent(first, last),
    }


async def list_sessions(symbol: str, limit: int = 7) -> list[dict]:
    payload = await fetch_minute_payload(symbol)
    return summarize_sessions(payload, limit)


async def load_session(symbol: str, day: date) -> dict | None:
    payload = await fetch_minute_payload(symbol)
    return minute_series(payload, day)


async def load_recap(symbol: str, day: date, variant: Variant) -> RecapAsset:
    payload = await fetch_minute_payload(symbol)
    points = session_points(samples_from_ohlc(payload), day)
    if not points:
        raise LookupError(day.isoformat())
    bars = [point.bar for point in points]
    try:
        return await asyncio.to_thread(recap_store().ensure, symbol.upper(), day, variant, bars)
    except RecapUnavailable:
        raise
    except Exception as exc:
        raise RecapUnavailable(str(exc)) from exc
