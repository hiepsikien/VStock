"""Compose a score just to read its PAFI. No audio, no MuseScore.

`GET /v1/sonify/pafi/pieces` needs the same price-action number for several
variant/ensemble rows of one session or one span movement.  The audio store
only knows the row the listener selected, so this module composes the other
rows from the same bars and caches the result in memory.

The cache key carries a digest of the inputs that decided the score.  A new
minute, a new close, or a different ensemble therefore misses the cache instead
of serving a stale number.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Iterable

from app.sonify.audio import (
    RECAP_REVISION,
    SPAN_REVISION,
    _compose,
    humanize_score,
    recap_store,
)
from app.sonify.ensemble import ensembles_for
from app.sonify.keys import movement_character, stock_home_key
from app.sonify.model import Bar, Ensemble, VARIANTS, Variant
from app.sonify.pafi import PAFI_VERSION, PafiBreakdown, compute as compute_pafi

ComposeKey = tuple[str, str, str, str, bool, str, str]
_CACHE: dict[ComposeKey, tuple[PafiBreakdown | None, str]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_LIMIT = 256

_PLANS: dict[tuple[str, str, Variant, str], tuple[float, object]] = {}
_PLAN_LOCK = threading.Lock()
_PLAN_TTL_SEC = 120.0


def _digest(values: Iterable[float]) -> str:
    payload = json.dumps(list(values), separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]


def bars_digest(bars: Iterable[Bar]) -> str:
    return _digest(
        value
        for bar in bars
        for value in (round(bar.close, 8), round(float(bar.volume), 8))
    )


def _store(key: ComposeKey, value: PafiBreakdown | None) -> PafiBreakdown | None:
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_LIMIT:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (value, stamp)
    _write_sidecar(key, value, stamp)
    return value


def _load(key: ComposeKey) -> tuple[PafiBreakdown | None, str | None, bool] | None:
    with _CACHE_LOCK:
        item = _CACHE.get(key)
    if item is not None:
        return item[0], item[1], True
    sidecar = _read_sidecar(key)
    if sidecar is None:
        return None
    with _CACHE_LOCK:
        _CACHE[key] = sidecar
    return sidecar[0], sidecar[1], True


def _sidecar_path(key: ComposeKey):
    name = hashlib.sha1(json.dumps(key, separators=(",", ":")).encode("utf-8")).hexdigest()
    return recap_store().root / "pafi" / f"{name}.json"


def _read_sidecar(key: ComposeKey) -> tuple[PafiBreakdown | None, str] | None:
    path = _sidecar_path(key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != PAFI_VERSION:
        return None
    stamp = str(payload.get("computedAt") or "")
    raw = payload.get("pafi")
    if raw is None:
        return None, stamp
    value = PafiBreakdown.from_dict(raw)
    if value is None:
        return None
    return value, stamp


def _write_sidecar(key: ComposeKey, value: PafiBreakdown | None, stamp: str) -> None:
    path = _sidecar_path(key)
    payload = {
        "version": PAFI_VERSION,
        "computedAt": stamp,
        "pafi": None if value is None else value.to_dict(),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        # A read-only store still serves the in-memory value.
        return


def _recap_key(
    symbol: str,
    day: date,
    variant: Variant,
    ensemble: Ensemble,
    humanize: bool,
    color: bool,
    digest: str,
) -> ComposeKey:
    return (
        f"day:{symbol}:{day.isoformat()}:{RECAP_REVISION}:{PAFI_VERSION}:{digest}",
        variant,
        ensemble,
        "day",
        humanize,
        "color" if color else "plain",
        digest,
    )


def _movement_key(
    symbol: str,
    span: str,
    index: int,
    variant: Variant,
    ensemble: Ensemble,
    humanize: bool,
    color: bool,
    digest: str,
) -> ComposeKey:
    return (
        f"span:{symbol}:{span}:{index}:{SPAN_REVISION}:{PAFI_VERSION}:{digest}",
        variant,
        ensemble,
        "span",
        humanize,
        "color" if color else "plain",
        digest,
    )


def _recap_score(
    symbol: str,
    bars: list[Bar],
    variant: Variant,
    ensemble: Ensemble,
    humanize: bool,
):
    score, _dance = _compose(
        variant,
        ensemble,
        bars,
        title=f"{symbol} pafi",
        key=stock_home_key(symbol),
        character=movement_character([bar.close for bar in bars], "1D"),
        movement_index=0,
    )
    if humanize:
        score = humanize_score(score)
    return score


def _movement_score(
    symbol: str,
    span: str,
    index: int,
    movement,
    variant: Variant,
    ensemble: Ensemble,
    humanize: bool,
):
    score, _dance = _compose(
        variant,
        ensemble,
        movement.bars,
        title=f"{symbol} {span} pafi",
        form=movement.spec,
        source_groups=movement.groups,
        key=movement.key,
        character=movement.character,
        outro_override=movement.outro_override,
        framed=False,
        mode=movement.mode,
        home_pedal=movement.home_pedal,
        character_at=movement.bar_characters,
        gap_leads=movement.gap_leads,
        movement_index=0 if span == "1W" else index,
    )
    if humanize:
        score = humanize_score(score)
    return score


@dataclass(frozen=True)
class PafiPieceResult:
    variant: Variant
    ensemble: Ensemble
    movement: int | None
    pafi: PafiBreakdown | None
    cached: bool
    computedAt: str | None


def recap_pafi(
    symbol: str,
    day: date,
    bars: list[Bar],
    variant: Variant,
    ensemble: Ensemble = "classic",
    humanize: bool = True,
    color: bool = True,
) -> PafiPieceResult:
    """Compose the recap score (no export) and read its PAFI."""
    digest = bars_digest(bars)
    key = _recap_key(symbol, day, variant, ensemble, humanize, color, digest)
    hit = _load(key)
    if hit is not None:
        value, stamp, cached = hit
        return PafiPieceResult(variant, ensemble, None, value, cached, stamp)
    score = _recap_score(symbol, bars, variant, ensemble, humanize)
    value = compute_pafi(score, variant=variant, ensemble=ensemble)
    stamp = _store(key, value)
    return PafiPieceResult(
        variant,
        ensemble,
        None,
        value,
        False,
        _stamp(key),
    )


def movement_pafi(
    symbol: str,
    span: str,
    index: int,
    movement,
    variant: Variant,
    ensemble: Ensemble = "classic",
    humanize: bool = True,
    color: bool = True,
) -> PafiPieceResult:
    digest = bars_digest(movement.bars)
    key = _movement_key(symbol, span, index, variant, ensemble, humanize, color, digest)
    hit = _load(key)
    if hit is not None:
        value, stamp, cached = hit
        return PafiPieceResult(variant, ensemble, index, value, cached, stamp)
    score = _movement_score(symbol, span, index, movement, variant, ensemble, humanize)
    value = compute_pafi(score, variant=variant, ensemble=ensemble)
    _store(key, value)
    return PafiPieceResult(
        variant,
        ensemble,
        index,
        value,
        False,
        _stamp(key),
    )


def _stamp(key: ComposeKey) -> str | None:
    with _CACHE_LOCK:
        item = _CACHE.get(key)
    return None if item is None else item[1]


def requested_rows(
    variant: Variant | None,
    ensemble: str | None,
) -> list[tuple[Variant, Ensemble]]:
    """Expand the filter into the rows the sheet asks for."""
    if variant is None:
        if ensemble:
            raise ValueError("ensemble needs a variant")
        return [(row, "classic") for row in VARIANTS]
    from app.sonify.ensemble import ensemble_for

    if ensemble:
        return [(variant, ensemble_for(variant, ensemble))]
    return [(variant, row) for row in ensembles_for(variant)]


def cached_plan(symbol: str, span: str, variant: Variant, ensemble: Ensemble):
    with _PLAN_LOCK:
        item = _PLANS.get((symbol, span, variant, ensemble))
    if item is None:
        return None
    stamp, plan = item
    if time.monotonic() - stamp > _PLAN_TTL_SEC:
        return None
    return plan


def store_plan(
    symbol: str,
    span: str,
    variant: Variant,
    ensemble: Ensemble,
    plan,
) -> None:
    with _PLAN_LOCK:
        if len(_PLANS) >= 32:
            _PLANS.pop(next(iter(_PLANS)))
        _PLANS[(symbol, span, variant, ensemble)] = (time.monotonic(), plan)


async def span_plan(symbol: str, span: str, variant: Variant, ensemble: Ensemble):
    cached = cached_plan(symbol, span, variant, ensemble)
    if cached is not None:
        return cached
    from app.services.spans import plan_span

    plan = await plan_span(symbol, span, variant, ensemble)
    store_plan(symbol, span, variant, ensemble, plan)
    return plan


async def recap_bars(symbol: str, day: date) -> list[Bar]:
    from app.services.sessions import fetch_minute_payload
    from app.sonify.session import samples_from_ohlc, session_points

    payload = await fetch_minute_payload(symbol)
    points = session_points(samples_from_ohlc(payload), day)
    return [point.bar for point in points]


async def pieces_for_day(
    symbol: str,
    day: date,
    rows: list[tuple[Variant, Ensemble]],
    humanize: bool = True,
    color: bool = True,
) -> list[PafiPieceResult]:
    bars = await recap_bars(symbol, day)
    if not bars:
        raise LookupError(day.isoformat())
    results: list[PafiPieceResult] = []
    for variant, ensemble in rows:
        results.append(
            await asyncio.to_thread(
                recap_pafi, symbol, day, bars, variant, ensemble, humanize, color
            )
        )
    return results


async def pieces_for_span(
    symbol: str,
    span: str,
    index: int,
    rows: list[tuple[Variant, Ensemble]],
    humanize: bool = True,
    color: bool = True,
) -> tuple[list[PafiPieceResult], date]:
    results: list[PafiPieceResult] = []
    as_of: date | None = None
    for variant, ensemble in rows:
        plan = await span_plan(symbol, span, variant, ensemble)
        if index < 0 or index >= len(plan.movements):
            raise LookupError(str(index))
        movement = plan.movements[index]
        as_of = plan.as_of
        results.append(
            await asyncio.to_thread(
                movement_pafi,
                symbol,
                span,
                index,
                movement,
                variant,
                ensemble,
                humanize,
                color,
            )
        )
    if as_of is None:
        raise LookupError(span)
    return results, as_of


def apply_to_asset(asset, piece: PafiPieceResult):
    """Attach a composed PAFI to a recap or movement asset."""
    return replace(asset, pafi=None if piece.pafi is None else piece.pafi.to_dict())
