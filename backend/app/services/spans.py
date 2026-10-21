"""Plan a 1W, 1M, 3M, or 1Y sonification and compose one movement at a time.

The manifest only describes movements. MuseScore runs when a movement's audio
is requested, so the chart can show the form before the first file exists.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import date

from fastapi import Request

from app.services.sessions import (
    fetch_minute_payload,
    fetch_ohlc,
    payload_truncated,
)
from app.sonify.audio import SpanAsset, RecapCancelled, RecapUnavailable, recap_store
from app.sonify.model import Variant
from app.sonify.playback import piece_seconds
from app.sonify.session import coarse_bars, samples_from_ohlc, session_bars, session_dates
from app.sonify.span import PreparedMovement, prepare_month, prepare_quarter, prepare_week, prepare_year

SPAN_RANGES = ("1W", "1M", "3M", "1Y")
MONTH_LOOKBACK_DAYS = 40
QUARTER_LOOKBACK_DAYS = 110
YEAR_LOOKBACK_DAYS = 400


def movement_duration(movement: PreparedMovement) -> float:
    return piece_seconds(movement.spec.bars, movement.spec.bpm)


def movement_audio_path(
    symbol: str,
    span: str,
    index: int,
    variant: Variant,
    movement: PreparedMovement,
) -> str:
    fingerprint = movement.scale_fingerprint
    return (
        f"/v1/stocks/{symbol}/span/audio.m4a"
        f"?range={span}&movement={index}&variant={variant}"
        f"&candles={movement.candle_count}&scale={fingerprint}"
    )


async def plan_span(symbol: str, span: str) -> tuple[PreparedMovement, ...]:
    if span == "1W":
        payload = await fetch_minute_payload(symbol)
        samples = samples_from_ohlc(payload)
        days = session_dates(samples, 5)
        return prepare_week([session_bars(samples, day) for day in days], symbol)
    if span == "1M":
        payload = await fetch_ohlc(symbol, MONTH_LOOKBACK_DAYS, "1")
        if payload_truncated(payload, MONTH_LOOKBACK_DAYS):
            payload = await fetch_ohlc(symbol, MONTH_LOOKBACK_DAYS, "5")
            return prepare_month(_days(coarse_bars(samples_from_ohlc(payload))), symbol)
        samples = samples_from_ohlc(payload)
        days = session_dates(samples, 10_000)
        return prepare_month([(day, session_bars(samples, day)) for day in days], symbol)
    if span == "3M":
        payload = await fetch_ohlc(symbol, QUARTER_LOOKBACK_DAYS, "5")
        return prepare_quarter(coarse_bars(samples_from_ohlc(payload)), symbol)
    if span == "1Y":
        payload = await fetch_ohlc(symbol, YEAR_LOOKBACK_DAYS, "30")
        return prepare_year(coarse_bars(samples_from_ohlc(payload)), symbol)
    raise ValueError(f"unsupported span: {span}")


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
) -> SpanAsset | None:
    return recap_store().get_movement(
        symbol.upper(),
        span,
        index,
        variant,
        movement.candle_count,
        movement.scale_fingerprint,
    )


async def load_movement_audio(
    symbol: str,
    span: str,
    index: int,
    variant: Variant,
    request: Request | None = None,
) -> SpanAsset:
    movements = await plan_span(symbol, span)
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
        return await asyncio.to_thread(
            recap_store().ensure_movement,
            symbol.upper(),
            span,
            index,
            variant,
            movement,
            cancel,
        )
    except (RecapUnavailable, RecapCancelled):
        raise
    except Exception as exc:
        raise RecapUnavailable(str(exc)) from exc
    finally:
        watcher.cancel()
