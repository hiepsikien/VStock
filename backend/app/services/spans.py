"""Plan a 1W, 1M, 3M, or 1Y sonification and compose one movement at a time.

The manifest only describes movements. MuseScore runs when a movement's audio
is requested, so the chart can show the form before the first file exists.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, replace
from datetime import date, datetime

from fastapi import Request

from app.services.market_session import is_market_open
from app.services.sessions import (
    fetch_minute_payload,
    fetch_ohlc,
    payload_truncated,
)
from app.sonify.audio import (
    SPAN_REVISION,
    SpanAsset,
    RecapCancelled,
    RecapUnavailable,
    layer_query,
    recap_store,
)
from app.sonify.dfi import DFI_VERSION, data_digest
from app.sonify.model import Ensemble, Variant
from app.sonify.session import (
    VN,
    coarse_bars,
    samples_from_ohlc,
    session_bars,
    session_dates,
)
from app.sonify.span import (
    PreparedMovement,
    frame_seconds,
    prepare_month,
    prepare_quarter,
    prepare_week,
    prepare_year,
    year_as_of,
)

logger = logging.getLogger(__name__)

SPAN_RANGES = ("1W", "1M", "3M", "1Y")


@dataclass(frozen=True)
class SpanPlan:
    movements: tuple[PreparedMovement, ...]
    as_of: date


MONTH_LOOKBACK_DAYS = 40
QUARTER_LOOKBACK_DAYS = 110
YEAR_LOOKBACK_DAYS = 400


def movement_duration(movement: PreparedMovement) -> float:
    return movement.spec.eighths * 30.0 / movement.spec.bpm


def movement_frame(movement: PreparedMovement) -> tuple[float, float]:
    return frame_seconds(movement.spec)


def movement_audio_path(
    symbol: str,
    span: str,
    index: int,
    variant: Variant,
    movement: PreparedMovement,
    ensemble: Ensemble = "classic",
    humanize: bool = True,
    color: bool = True,
) -> str:
    fingerprint = movement.scale_fingerprint
    extra = "" if ensemble == "classic" else f"&ensemble={ensemble}"
    extra += layer_query(humanize, color)
    return (
        f"/v1/stocks/{symbol}/span/audio.m4a"
        f"?range={span}&movement={index}&variant={variant}"
        f"&candles={movement.candle_count}&scale={fingerprint}&r={SPAN_REVISION}{extra}"
    )


async def plan_span(
    symbol: str,
    span: str,
    variant: Variant = "symphony",
    ensemble: Ensemble = "classic",
) -> SpanPlan:
    if span == "1W":
        payload = await fetch_minute_payload(symbol)
        samples = samples_from_ohlc(payload)
        from app.sonify.groove import opening_median
        from app.sonify.session import session_points

        days = session_dates(samples, 5)
        day_points = [session_points(samples, day) for day in days]
        openings = [
            opening_median(
                [
                    point.bar.close
                    for point in points
                    if 9 * 60 + 16 <= point.moment.hour * 60 + point.moment.minute <= 9 * 60 + 30
                ]
            )
            for points in day_points
        ]
        return SpanPlan(
            prepare_week(
                [[point.bar for point in points] for points in day_points],
                symbol,
                openings,
                variant=variant,
                ensemble=ensemble,
            ),
            days[-1],
        )
    if span == "1M":
        payload = await fetch_ohlc(symbol, MONTH_LOOKBACK_DAYS, "1")
        if payload_truncated(payload, MONTH_LOOKBACK_DAYS):
            payload = await fetch_ohlc(symbol, MONTH_LOOKBACK_DAYS, "5")
            stamped = coarse_bars(samples_from_ohlc(payload))
            return SpanPlan(
                prepare_month(_days(stamped), symbol, variant=variant, ensemble=ensemble),
                stamped[-1][0],
            )
        samples = samples_from_ohlc(payload)
        days = session_dates(samples, 10_000)
        return SpanPlan(
            prepare_month(
                [(day, session_bars(samples, day)) for day in days],
                symbol,
                variant=variant,
                ensemble=ensemble,
            ),
            days[-1],
        )
    if span == "3M":
        payload = await fetch_ohlc(symbol, QUARTER_LOOKBACK_DAYS, "5")
        stamped = coarse_bars(samples_from_ohlc(payload))
        return SpanPlan(
            prepare_quarter(stamped, symbol, variant=variant, ensemble=ensemble),
            stamped[-1][0],
        )
    if span == "1Y":
        payload = await fetch_ohlc(symbol, YEAR_LOOKBACK_DAYS, "30")
        stamped = coarse_bars(samples_from_ohlc(payload))
        return SpanPlan(
            prepare_year(stamped, symbol, variant=variant, ensemble=ensemble),
            year_as_of(stamped),
        )
    raise ValueError(f"unsupported span: {span}")


# One audio request re-plans the whole work, and a long-form work is expensive
# to plan. Reuse the plan across the renders of the same listening session.
PLAN_TTL_CLOSED = 600.0
PLAN_TTL_OPEN = 60.0
_PLAN_CACHE_MAX = 64
_PLAN_CACHE: dict[tuple[str, str, str, str], tuple[float, SpanPlan, bool]] = {}
_PLAN_LOCKS: dict[
    tuple[str, str, str, str], tuple[asyncio.AbstractEventLoop, asyncio.Lock]
] = {}


def plan_ttl(market_open: bool | None = None) -> float:
    """A live session's plan goes stale with the next candle; closed data does not."""
    live = is_market_open() if market_open is None else market_open
    return PLAN_TTL_OPEN if live else PLAN_TTL_CLOSED


def _plan_cache_valid(entry: tuple[float, SpanPlan, bool], now: float) -> bool:
    until, plan, was_open = entry
    if until <= now:
        return False
    open_now = is_market_open()
    # A plan cached while the market was closed must not survive any opening
    # bell, including the 13:00 restart after lunch. Its `as_of` can already be
    # today from the morning, so `as_of` alone cannot catch this.
    if open_now and not was_open:
        return False
    if open_now and plan.as_of < datetime.now(VN).date():
        return False
    return True


def clear_plan_cache() -> None:
    _PLAN_CACHE.clear()
    _PLAN_LOCKS.clear()


def _plan_lock(key: tuple[str, str, str, str]) -> asyncio.Lock:
    # Tests and workers can call this from a new event loop. A lock bound to a
    # dead loop would raise, so replace it instead of reusing it.
    loop = asyncio.get_running_loop()
    entry = _PLAN_LOCKS.get(key)
    if entry is None or entry[0] is not loop:
        entry = (loop, asyncio.Lock())
        _PLAN_LOCKS[key] = entry
    return entry[1]


async def plan_span_cached(
    symbol: str,
    span: str,
    variant: Variant = "symphony",
    ensemble: Ensemble = "classic",
) -> SpanPlan:
    """Plan once per listening session, not once per chapter render.

    Concurrent requests share one lock and one plan. `/span` stays uncached
    because it must show a new candle immediately.
    """
    key = (symbol.upper(), span, variant, ensemble)
    now = time.monotonic()
    cached = _PLAN_CACHE.get(key)
    if cached is not None and _plan_cache_valid(cached, now):
        return cached[1]
    async with _plan_lock(key):
        now = time.monotonic()
        cached = _PLAN_CACHE.get(key)
        if cached is not None and _plan_cache_valid(cached, now):
            return cached[1]
        plan = await plan_span(symbol, span, variant, ensemble)
        was_open = is_market_open()
        _PLAN_CACHE[key] = (time.monotonic() + plan_ttl(was_open), plan, was_open)
        if len(_PLAN_CACHE) > _PLAN_CACHE_MAX:
            cutoff = time.monotonic()
            for stale_key in [
                k for k, (until, _, _) in _PLAN_CACHE.items() if until <= cutoff
            ]:
                _PLAN_CACHE.pop(stale_key, None)
            while len(_PLAN_CACHE) > _PLAN_CACHE_MAX:
                _PLAN_CACHE.pop(next(iter(_PLAN_CACHE)), None)
        return plan


def _days(stamped: list[tuple[date, object]]) -> list[tuple[date, list]]:
    groups: list[tuple[date, list]] = []
    for day, bar in stamped:
        if not groups or groups[-1][0] != day:
            groups.append((day, []))
        groups[-1][1].append(bar)
    return groups


def ready_movement(
    symbol: str,
    span: str,
    index: int,
    variant: Variant,
    movement: PreparedMovement,
    ensemble: Ensemble = "classic",
    humanize: bool = True,
    color: bool = True,
) -> SpanAsset | None:
    asset = recap_store().get_movement(
        symbol.upper(),
        span,
        index,
        variant,
        movement.candle_count,
        movement.scale_fingerprint,
        ensemble,
        humanize,
        color,
    )
    if asset is not None and asset.dfi is not None:
        if (
            asset.dfi_inputs != data_digest(movement.bars)
            or asset.dfi_checked != DFI_VERSION
        ):
            # The last close moved after this file was scored. Treat it as
            # missing so the plan does not stop the client's refresh poll.
            asset = replace(asset, dfi=None)
    return asset


async def load_movement_audio(
    symbol: str,
    span: str,
    index: int,
    variant: Variant,
    request: Request | None = None,
    ensemble: Ensemble = "classic",
    humanize: bool = True,
    color: bool = True,
) -> SpanAsset:
    movements = (await plan_span_cached(symbol, span, variant, ensemble)).movements
    if index < 0 or index >= len(movements):
        raise LookupError(str(index))
    movement = movements[index]
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
            recap_store().ensure_movement,
            symbol.upper(),
            span,
            index,
            variant,
            movement,
            cancel,
            ensemble,
            humanize,
            color,
        )
        digest = data_digest(movement.bars)
        if (
            getattr(asset, "dfi_inputs", "") != digest
            or getattr(asset, "dfi_checked", "") != DFI_VERSION
        ):
            # Never let a DFI recompose failure turn cached audio into a 503.
            asset = replace(asset, dfi=None)
            try:
                from app.services import dfi as dfi_service

                piece = await asyncio.to_thread(
                    dfi_service.movement_dfi,
                    symbol.upper(),
                    span,
                    index,
                    movement,
                    variant,
                    ensemble,
                    humanize,
                    color,
                )
                asset = dfi_service.apply_to_asset(asset, piece)
                asset = replace(asset, dfi_inputs=digest, dfi_checked=DFI_VERSION)
                remember = getattr(recap_store(), "remember_movement_dfi", None)
                if callable(remember):
                    remember(
                        symbol.upper(),
                        span,
                        index,
                        variant,
                        movement.candle_count,
                        movement.scale_fingerprint,
                        ensemble,
                        humanize,
                        color,
                        getattr(asset, "dfi", None),
                        digest,
                    )
            except Exception as exc:
                logger.warning(
                    "DFI recompose failed for %s %s movement %s: %s",
                    symbol,
                    span,
                    index,
                    exc,
                )
        return asset
    except (RecapUnavailable, RecapCancelled):
        raise
    except Exception as exc:
        raise RecapUnavailable(str(exc)) from exc
    finally:
        watcher.cancel()
