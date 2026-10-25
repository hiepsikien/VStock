"""1-minute HOSE sessions for the last few trading days, and their recap audio."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import replace
from datetime import date

import httpx
from fastapi import Request

from app.services.cache import cache
from app.services.http_utils import ENTRADE_HEADERS
from app.sonify.audio import RecapAsset, RecapCancelled, RecapUnavailable, recap_store
from app.sonify.model import Ensemble, Variant
from app.sonify.session import samples_from_ohlc, session_dates, session_points

logger = logging.getLogger(__name__)

ENTRADE_OHLC = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
# Calendar span that still covers seven sessions across a holiday week.
LOOKBACK_DAYS = 18
MINUTE_TTL = 45


def _cache_key(symbol: str) -> str:
    return f"minute-ohlc:{symbol}"


async def fetch_ohlc(symbol: str, lookback_days: int, resolution: str) -> dict:
    """OHLC for a long-form span. The 1-day recap keeps `fetch_minute_payload`."""
    sym = symbol.upper()
    key = f"ohlc:{resolution}:{lookback_days}:{sym}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    now = int(time.time())
    params = {
        "from": now - lookback_days * 24 * 3600,
        "to": now,
        "symbol": sym,
        "resolution": resolution,
    }
    async with httpx.AsyncClient(timeout=20.0, headers=ENTRADE_HEADERS) as client:
        response = await client.get(ENTRADE_OHLC, params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("history payload is not an object")
    cache.set(key, payload, MINUTE_TTL)
    return payload


def payload_truncated(payload: dict, lookback_days: int, now: int | None = None) -> bool:
    """True when the feed starts well after the requested window."""
    from app.sonify.session import samples_from_ohlc

    samples = samples_from_ohlc(payload)
    if not samples:
        return True
    earliest = min(sample[0] for sample in samples)
    clock = int(time.time()) if now is None else now
    requested = clock - lookback_days * 24 * 3600
    # Friday's close to Monday's open is already longer than two days, and a
    # holiday stretches it further. Five days still catches a feed that started
    # in the middle of the requested window.
    return earliest > requested + 5 * 24 * 3600


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


def session_change_percent(reference: float, last: float) -> float:
    if reference <= 0:
        return 0.0
    return round((last - reference) / reference * 100, 2)


def _session_closes(samples: list[tuple[int, float, float]]) -> dict[date, float]:
    closes: dict[date, float] = {}
    for day in session_dates(samples, limit=10_000):
        points = session_points(samples, day)
        if points:
            closes[day] = points[-1].bar.close
    return closes


def _reference_close(closes: dict[date, float], day: date, first: float) -> float:
    """Board-style change uses the previous session's close, not the day's first print.

    The first recap print includes the opening auction, so a ceiling open looks
    like a flat day if the chip compares the close with that print.
    """
    earlier = [stamp for stamp in closes if stamp < day]
    if not earlier:
        return first
    return closes[max(earlier)]


def summarize_sessions(payload: dict, limit: int = 7) -> list[dict]:
    samples = samples_from_ohlc(payload)
    closes = _session_closes(samples)
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
                "changePercent": session_change_percent(_reference_close(closes, day, first), last),
                "bars": len(points),
            }
        )
    return rows


def minute_series(payload: dict, day: date) -> dict | None:
    samples = samples_from_ohlc(payload)
    points = session_points(samples, day)
    if not points:
        return None
    first = points[0].bar.close
    last = points[-1].bar.close
    closes = _session_closes(samples)
    return {
        "date": day.isoformat(),
        "prices": [round(point.bar.close, 2) for point in points],
        "times": [point.moment.strftime("%H:%M") for point in points],
        "changePercent": session_change_percent(_reference_close(closes, day, first), last),
    }


async def list_sessions(symbol: str, limit: int = 7) -> list[dict]:
    payload = await fetch_minute_payload(symbol)
    return summarize_sessions(payload, limit)


async def load_session(symbol: str, day: date) -> dict | None:
    payload = await fetch_minute_payload(symbol)
    return minute_series(payload, day)


def ready_recap(
    symbol: str,
    day: date,
    variant: Variant,
    bar_count: int,
    ensemble: Ensemble = "classic",
) -> RecapAsset | None:
    """Return a file that was already composed. Never starts MuseScore."""
    return recap_store().get(symbol.upper(), day, variant, bar_count, ensemble)


async def load_recap(
    symbol: str,
    day: date,
    variant: Variant,
    request: Request | None = None,
    ensemble: Ensemble = "classic",
) -> RecapAsset:
    payload = await fetch_minute_payload(symbol)
    points = session_points(samples_from_ohlc(payload), day)
    if not points:
        raise LookupError(day.isoformat())
    from app.sonify.keys import key_label, movement_character, stock_home_key
    from app.sonify.program import guitar_movement_name

    bars = [point.bar for point in points]
    character = movement_character([bar.close for bar in bars], "1D")
    home = stock_home_key(symbol)
    cancel = threading.Event()

    async def watch_disconnect() -> None:
        if request is None:
            return
        while True:
            if await request.is_disconnected():
                cancel.set()
                return
            await asyncio.sleep(0.4)

    watcher = asyncio.create_task(watch_disconnect())
    try:
        asset = await asyncio.to_thread(
            recap_store().ensure,
            symbol.upper(),
            day,
            variant,
            bars,
            cancel,
            ensemble,
        )
        movement_name = ""
        if variant == "guitar":
            try:
                movement_name = await asyncio.to_thread(
                    guitar_movement_name,
                    bars,
                    ensemble=ensemble,
                    key=home,
                    character=character,
                )
            except Exception:
                logger.warning("guitar recap name failed for %s", symbol, exc_info=True)
                movement_name = "Etude"
        return replace(
            asset,
            character=character,
            key_label=key_label(home, "major"),
            movement_name=movement_name,
        )
    except (RecapUnavailable, RecapCancelled):
        raise
    except Exception as exc:
        raise RecapUnavailable(str(exc)) from exc
    finally:
        watcher.cancel()
