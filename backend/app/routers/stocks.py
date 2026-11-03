from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS
from app.schemas import (
    DEFAULT_WATCHLIST,
    ChartRange,
    HistoryResponse,
    DfiPiecesResponse,
    DfiBreakdown,
    DfiSignature,
    RecapResponse,
    SpanMovementResponse,
    SpanPeaksMovement,
    SpanPeaksResponse,
    SpanResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
    IncomePeriod,
    IndicesResponse,
    IndexQuote,
    MarketStatusResponse,
    StockDetail,
    SymbolInfo,
    SymbolsResponse,
    WatchlistItem,
    WatchlistSparkline,
)
from app.services import fundamentals, history, indices, market_session, quotes, symbols as symbols_service
from app.services import dfi as dfi_service
from app.services.sessions import list_sessions, load_recap, load_session, ready_recap
from app.services.spans import (
    SPAN_RANGES,
    load_movement_audio,
    movement_audio_path,
    movement_duration,
    movement_frame,
    plan_span,
    plan_span_cached,
    ready_movement,
)
from app.sonify.audio import RecapCancelled, RecapUnavailable, recap_store
from app.sonify.ensemble import Ensemble, ensemble_for
from app.sonify.keys import CHARACTER_LABEL, key_label, work_key_label
from app.sonify.params import (
    SCHEMA_VERSION,
    normalize_with_warnings,
    params_from_query,
    params_hash,
    params_layers,
    presets_payload,
    schema_payload,
)
from app.sonify.program import span_movement_name
from app.sonify.model import Variant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


def _ensemble(variant: Variant, name: str) -> Ensemble:
    try:
        return ensemble_for(variant, name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _params(p: str | None, humanize: bool, color: bool):
    text = p if isinstance(p, str) and p else None
    try:
        return params_from_query(text, humanize=humanize, color=color)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid p: {exc}") from exc


def _layers(params) -> tuple[bool, bool]:
    return params_layers(params)


async def _symbol_coverage() -> dict[str, dict]:
    try:
        return await symbols_service.fetch_coverage()
    except Exception as exc:
        logger.warning("Symbol coverage unavailable: %s", exc)
        return {}


def _empty_fund() -> dict:
    return {
        "name": None,
        "exchange": "HOSE",
        "marketCap": "—",
        "pe": None,
        "eps": None,
        "pb": None,
        "roe": None,
        "roa": None,
        "dividendYield": None,
    }


def _empty_income() -> dict:
    return {
        "revenueLabel": None,
        "latestAnnual": None,
        "lastQuarters": [],
    }


def _fallback_fund(name: str = "—", exchange: str = "HOSE") -> dict:
    return {
        **_empty_fund(),
        "name": name,
        "exchange": exchange,
    }


async def _load_fund_income(sym: str) -> tuple[dict, dict]:
    fund_task = asyncio.create_task(fundamentals.fetch_fundamentals(sym))
    income_task = asyncio.create_task(fundamentals.fetch_income(sym))
    try:
        fund = await fund_task
    except Exception:
        fund = _fallback_fund(name=sym)
    try:
        income = await income_task
    except Exception:
        income = _empty_income()
    return fund, income


def _income_period(raw: dict | None) -> IncomePeriod | None:
    if not raw or not isinstance(raw, dict):
        return None
    fiscal = str(raw.get("fiscalDate") or "")
    year = int(raw.get("year") or 0)
    if not fiscal or year <= 0:
        return None
    try:
        return IncomePeriod(
            periodType=raw.get("periodType") or "annual",
            fiscalDate=fiscal,
            year=year,
            quarter=raw.get("quarter"),
            netRevenue=raw.get("netRevenue"),
            netIncome=raw.get("netIncome"),
        )
    except Exception:
        return None


def _stock_detail_extras(fund: dict, income: dict) -> dict:
    quarters_raw = income.get("lastQuarters") or []
    quarters = [p for p in (_income_period(q) for q in quarters_raw) if p is not None]
    return {
        "eps": fund.get("eps"),
        "pb": fund.get("pb"),
        "roe": fund.get("roe"),
        "roa": fund.get("roa"),
        "dividendYield": fund.get("dividendYield"),
        "revenueLabel": income.get("revenueLabel"),
        "incomeLatestAnnual": _income_period(income.get("latestAnnual")),
        "incomeLastQuarters": quarters,
    }


@router.get("/market/status", response_model=MarketStatusResponse)
async def market_status() -> MarketStatusResponse:
    from app.services.cache import QUOTE_TTL

    open_now = market_session.is_market_open()
    return MarketStatusResponse(
        open=open_now,
        session=market_session.session_label(),
        quoteCacheTtlSeconds=QUOTE_TTL,
    )


@router.get("/symbols", response_model=SymbolsResponse)
async def list_symbols(
    exchange: str | None = Query(
        default=None,
        description="Optional filter: HOSE or HNX",
    ),
) -> SymbolsResponse:
    try:
        rows = await symbols_service.fetch_all_symbols()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Symbol source unavailable: {exc}") from exc

    if exchange:
        ex = exchange.upper()
        rows = [r for r in rows if r["exchange"] == ex]

    coverage = await _symbol_coverage()
    items = [
        SymbolInfo(
            **r,
            ranges=coverage.get(r["symbol"], {}).get("ranges", []),
        )
        for r in rows
    ]
    return SymbolsResponse(count=len(items), symbols=items)


@router.get("/symbols/search", response_model=list[SymbolInfo])
async def search_symbols(
    q: str = Query(..., min_length=1, description="Symbol or company name"),
    limit: int = Query(default=30, ge=1, le=100),
) -> list[SymbolInfo]:
    try:
        rows = await symbols_service.search_symbols(q, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Symbol source unavailable: {exc}") from exc
    coverage = await _symbol_coverage()
    return [
        SymbolInfo(
            **row,
            ranges=coverage.get(row["symbol"], {}).get("ranges", []),
        )
        for row in rows
    ]


@router.get("/indices", response_model=IndicesResponse)
async def get_market_indices() -> IndicesResponse:
    try:
        rows = await indices.fetch_market_indices()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Index source unavailable: {exc}") from exc
    return IndicesResponse(items=[IndexQuote(**r) for r in rows])


@router.get("/watchlist/sparklines", response_model=list[WatchlistSparkline])
async def get_watchlist_sparklines(
    symbols: str | None = Query(
        default=None,
        description="Comma-separated symbols. Defaults to VN blue chips.",
    ),
    range: ChartRange = Query(default="1D"),
) -> list[WatchlistSparkline]:
    """Light rail payload: stored candles only, plus the day quote for 1D."""
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols is not None
        else list(DEFAULT_WATCHLIST)
    )
    if not symbol_list:
        return []
    # The rail asks for at most 16; cap defensively without changing the
    # existing /watchlist contract.
    symbol_list = symbol_list[:32]

    stored = await history.fetch_sparklines(symbol_list, range)
    quote_map: dict[str, dict] = {}
    index_map: dict[str, dict] = {}
    if range == "1D":
        equity_symbols = [sym for sym in symbol_list if sym not in INDEX_SYMBOLS]
        try:
            quote_map = await quotes.fetch_quotes(equity_symbols) if equity_symbols else {}
        except Exception:
            # The stored candle is still useful; a missing quote only costs the %
            quote_map = {}
        if any(sym in INDEX_SYMBOLS for sym in symbol_list):
            try:
                index_map = {
                    row["symbol"]: row for row in await indices.fetch_market_indices()
                }
            except Exception:
                index_map = {}

    rows: list[WatchlistSparkline] = []
    for sym in symbol_list:
        item = stored.get(sym)
        if not item:
            continue
        prices = item["prices"]
        change: float | None = item.get("changePercent")
        if range == "1D":
            quote = quote_map.get(sym) or index_map.get(sym)
            if quote is not None:
                change = round(float(quote.get("changePercent") or 0), 2)
        rows.append(
            WatchlistSparkline(
                symbol=sym,
                changePercent=change,
                sparkline=prices,
                rangeUsed=item["range"],
            )
        )
    return rows


@router.get("/watchlist", response_model=list[WatchlistItem])
async def get_watchlist(
    symbols: str | None = Query(
        default=None,
        description="Comma-separated symbols. Defaults to VN blue chips.",
    ),
) -> list[WatchlistItem]:
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols is not None
        else list(DEFAULT_WATCHLIST)
    )
    if not symbol_list:
        return []

    try:
        quote_map = await quotes.fetch_quotes(symbol_list)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quote source unavailable: {exc}") from exc

    async def build_item(sym: str) -> WatchlistItem | None:
        q = quote_map.get(sym)
        if q:
            try:
                fund, spark = await asyncio.gather(
                    fundamentals.fetch_fundamentals(sym),
                    history.fetch_sparkline(sym),
                )
            except Exception:
                fund = {
                    "name": sym,
                    "exchange": "HOSE",
                    "marketCap": "—",
                    "pe": None,
                }
                spark = []
            return WatchlistItem(
                symbol=sym,
                name=fund["name"],
                exchange=fund["exchange"],
                price=q["price"],
                change=q["change"],
                changePercent=q["changePercent"],
                volume=q["volume"],
                sparkline=spark,
            )

        meta = await symbols_service.lookup_symbol(sym)
        if not meta:
            return None
        return WatchlistItem(
            symbol=sym,
            name=str(meta.get("name") or sym),
            exchange=str(meta.get("exchange") or "HOSE"),
            price=0,
            change=0,
            changePercent=0,
            volume=0,
            sparkline=[],
            unavailable=True,
        )

    items = await asyncio.gather(*(build_item(s) for s in symbol_list))
    return [item for item in items if item is not None]


@router.get("/stocks/{symbol}", response_model=StockDetail)
async def get_stock(symbol: str) -> StockDetail:
    sym = symbol.upper()

    index_row = await indices.fetch_index(sym)
    if index_row:
        try:
            spark = await history.fetch_sparkline(sym)
        except Exception:
            spark = []
        price = index_row["price"]
        change = index_row["change"]
        prior_close = index_row.get("priorClose")
        if prior_close is None:
            prior_close = round(price - change, 2)
        currency = index_row.get("currency") or ""
        return StockDetail(
            symbol=sym,
            name=index_row["name"],
            exchange=index_row["exchange"],
            price=price,
            change=change,
            changePercent=index_row["changePercent"],
            open=index_row.get("open", price),
            high=index_row.get("high", price),
            low=index_row.get("low", price),
            priorClose=prior_close,
            volume=0,
            marketCap="—",
            pe=None,
            currency=currency,
            sparkline=spark,
        )

    try:
        q = await quotes.fetch_quote(sym)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quote source unavailable: {exc}") from exc

    if not q:
        meta = await symbols_service.lookup_symbol(sym)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Symbol not found: {sym}")
        fund, income = await _load_fund_income(sym)
        return StockDetail(
            symbol=sym,
            name=str(fund.get("name") or meta.get("name") or sym),
            exchange=str(fund.get("exchange") or meta.get("exchange") or "HOSE"),
            price=0,
            change=0,
            changePercent=0,
            open=0,
            high=0,
            low=0,
            volume=0,
            marketCap=str(fund.get("marketCap") or "—"),
            pe=fund.get("pe"),
            sparkline=[],
            unavailable=True,
            **_stock_detail_extras(fund, income),
        )

    try:
        fund, spark = await asyncio.gather(
            fundamentals.fetch_fundamentals(sym),
            history.fetch_sparkline(sym),
        )
    except Exception:
        fund = _fallback_fund(name=sym)
        spark = []
    try:
        income = await fundamentals.fetch_income(sym)
    except Exception:
        income = _empty_income()

    return StockDetail(
        symbol=sym,
        name=fund["name"],
        exchange=fund["exchange"],
        price=q["price"],
        change=q["change"],
        changePercent=q["changePercent"],
        open=q["open"],
        high=q["high"],
        low=q["low"],
        volume=q["volume"],
        marketCap=fund["marketCap"],
        pe=fund["pe"],
        sparkline=spark,
        **_stock_detail_extras(fund, income),
    )


@router.get("/stocks/{symbol}/history", response_model=HistoryResponse)
async def get_history(
    symbol: str,
    range: ChartRange = Query(default="1D", alias="range"),
) -> HistoryResponse:
    sym = symbol.upper()
    try:
        prices = await history.fetch_history(sym, range)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"History source unavailable: {exc}") from exc

    if not prices:
        raise HTTPException(status_code=404, detail=f"No history for {sym}")

    return HistoryResponse(symbol=sym, range=range, prices=prices)


@router.get("/stocks/{symbol}/sessions", response_model=SessionListResponse)
async def get_sessions(
    symbol: str,
    limit: int = Query(default=7, ge=1, le=7),
) -> SessionListResponse:
    sym = symbol.upper()
    try:
        rows = await list_sessions(sym, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Minute history unavailable: {exc}") from exc
    return SessionListResponse(
        symbol=sym,
        sessions=[SessionSummary(**row) for row in rows],
    )


@router.get("/stocks/{symbol}/sessions/{session_date}", response_model=SessionDetailResponse)
async def get_session_minutes(symbol: str, session_date: date) -> SessionDetailResponse:
    sym = symbol.upper()
    try:
        detail = await load_session(sym, session_date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Minute history unavailable: {exc}") from exc
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No 1-minute session for {sym} on {session_date}")
    return SessionDetailResponse(symbol=sym, **detail)


@router.get("/stocks/{symbol}/sessions/{session_date}/recap", response_model=RecapResponse)
async def get_recap(
    response: Response,
    symbol: str,
    session_date: date,
    request: Request,
    variant: Variant = Query(default="symphony"),
    ensemble: str = Query(default="classic"),
    humanize: bool = Query(default=True),
    color: bool = Query(default=True),
    p: str | None = Query(default=None),
) -> RecapResponse:
    sym = symbol.upper()
    # The movement name and DFI are written with the audio. A cached recap from
    # before that write would show an empty name and a missing DFI.
    response.headers["Cache-Control"] = "no-store"
    chosen = _ensemble(variant, ensemble)
    valid = _params(p, humanize, color)
    try:
        asset = await load_recap(sym, session_date, variant, request, chosen, valid)
    except LookupError:
        raise HTTPException(
            status_code=404,
            detail=f"No 1-minute session for {sym} on {session_date}",
        ) from None
    except RecapCancelled:
        raise HTTPException(status_code=499, detail="Recap cancelled") from None
    except RecapUnavailable as exc:
        logger.warning("Recap export failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Minute history unavailable: {exc}") from exc
    return RecapResponse(
        symbol=asset.symbol,
        date=asset.day.isoformat(),
        variant=asset.variant,
        ensemble=asset.ensemble,
        durationSec=asset.duration_sec,
        mapDurationSec=asset.map_duration_sec,
        barCount=asset.bar_count,
        peaks=asset.peaks,
        audioUrl=asset.audio_url,
        character=asset.character,
        characterLabel=CHARACTER_LABEL.get(asset.character or "", ""),
        keyLabel=asset.key_label,
        movementName=asset.movement_name,
        humanize=_layers(valid)[0],
        color=_layers(valid)[1],
        paramsHash=params_hash(valid),
        dfi=asset.dfi,
    )


@router.get("/stocks/{symbol}/span", response_model=SpanResponse)
async def get_span(
    response: Response,
    symbol: str,
    range: str = Query(default="1W"),
    variant: Variant = Query(default="symphony"),
    ensemble: str = Query(default="classic"),
    humanize: bool = Query(default=True),
    color: bool = Query(default=True),
    p: str | None = Query(default=None),
) -> SpanResponse:
    sym = symbol.upper()
    # A movement name and its DFI appear after the audio is written. Never let
    # a browser or proxy replay a plan from before that write.
    response.headers["Cache-Control"] = "no-store"
    chosen = _ensemble(variant, ensemble)
    valid = _params(p, humanize, color)
    if range not in SPAN_RANGES:
        raise HTTPException(status_code=404, detail=f"No sonification for {range}")
    try:
        plan = await plan_span(sym, range, variant, ensemble=chosen)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Span history unavailable: {exc}") from exc
    rows = []
    work_dfi = None
    for index, movement in enumerate(plan.movements):
        cached = ready_movement(sym, range, index, variant, movement, chosen, valid)
        if range == "1W" and cached is not None:
            # A week is one movement, so the work score is that movement.
            work_dfi = getattr(cached, "dfi", None)
        written = round(movement_duration(movement), 3)
        mapped = written
        heard = written
        if cached is not None:
            if cached.map_duration_sec > 0:
                mapped = round(cached.map_duration_sec, 3)
            if cached.duration_sec > 0:
                heard = round(cached.duration_sec, 3)
        rows.append(
            SpanMovementResponse(
                index=index,
                label=movement.label,
                keyLabel=key_label(movement.key, movement.mode),
                candleCount=movement.candle_count,
                durationSec=heard,
                mapDurationSec=mapped,
                ready=cached is not None,
                audioUrl=movement_audio_path(
                    sym, range, index, variant, movement, chosen, valid
                ),
                restAfterSec=movement.rest_after,
                warmupSec=round(movement_frame(movement)[0], 3),
                cooldownSec=round(movement_frame(movement)[1], 3),
                prices=[round(bar.close, 2) for bar in movement.bars],
                volumes=[round(float(bar.volume), 4) for bar in movement.bars],
                peaks=list(getattr(cached, "peaks", None) or []) if cached is not None else [],
                peakLevel=float(getattr(cached, "peak_level", 0.0) or 0.0) if cached is not None else 0.0,
                renderSec=float(getattr(cached, "render_sec", 0.0) or 0.0) if cached is not None else 0.0,
                renderRatio=float(getattr(cached, "render_ratio", 0.0) or 0.0) if cached is not None else 0.0,
                character=movement.character,
                characterLabel=CHARACTER_LABEL.get(movement.character or "", ""),
                sessionCharacters=[
                    CHARACTER_LABEL[item] for item in movement.session_characters
                ],
                bpm=movement.spec.bpm,
                beats=movement.spec.meter.beats,
                beatType=movement.spec.meter.beat_type,
                name=span_movement_name(
                    movement,
                    variant=variant,
                    span=range,
                    index=index,
                    stored=cached.movement_name if cached is not None else "",
                ),
                paramsHash=params_hash(valid),
                dfi=getattr(cached, "dfi", None) if cached is not None else None,
            )
        )
    return SpanResponse(
        symbol=sym,
        range=range,
        variant=variant,
        ensemble=chosen,
        movements=rows,
        asOf=plan.as_of.isoformat(),
        keyLabel=work_key_label(sym, [movement.mode for movement in plan.movements]),
        humanize=_layers(valid)[0],
        color=_layers(valid)[1],
        paramsHash=params_hash(valid),
        dfi=work_dfi,
    )


@router.get("/stocks/{symbol}/span/peaks", response_model=SpanPeaksResponse)
async def get_span_peaks(
    response: Response,
    symbol: str,
    range: str = Query(default="1W"),
    variant: Variant = Query(default="symphony"),
    ensemble: str = Query(default="classic"),
    humanize: bool = Query(default=True),
    color: bool = Query(default=True),
    p: str | None = Query(default=None),
) -> SpanPeaksResponse:
    """Only the per-movement envelopes. Avoids resending prices/volumes on refresh."""
    sym = symbol.upper()
    response.headers["Cache-Control"] = "no-store"
    chosen = _ensemble(variant, ensemble)
    valid = _params(p, humanize, color)
    if range not in SPAN_RANGES:
        raise HTTPException(status_code=404, detail=f"No sonification for {range}")
    try:
        # Peaks can use the same plan the audio route is rendering from. The
        # cache is short for a live session and invalidated at the opening bell,
        # so this still sees a new candle within the documented window.
        plan = await plan_span_cached(sym, range, variant, chosen)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Span history unavailable: {exc}") from exc

    peaks: list[SpanPeaksMovement] = []
    for index, movement in enumerate(plan.movements):
        cached = ready_movement(sym, range, index, variant, movement, chosen, valid)
        peaks.append(
            SpanPeaksMovement(
                index=index,
                peaks=list(getattr(cached, "peaks", None) or []) if cached is not None else [],
                peakLevel=float(getattr(cached, "peak_level", 0.0) or 0.0)
                if cached is not None
                else 0.0,
                audioUrl=movement_audio_path(
                    sym, range, index, variant, movement, chosen, valid
                ),
                ready=cached is not None,
                durationSec=float(getattr(cached, "duration_sec", 0.0) or 0.0)
                if cached is not None
                else 0.0,
                renderSec=float(getattr(cached, "render_sec", 0.0) or 0.0)
                if cached is not None
                else 0.0,
                renderRatio=float(getattr(cached, "render_ratio", 0.0) or 0.0)
                if cached is not None
                else 0.0,
            )
        )
    return SpanPeaksResponse(
        symbol=sym,
        range=range,
        variant=variant,
        ensemble=chosen,
        humanize=_layers(valid)[0],
        color=_layers(valid)[1],
        asOf=plan.as_of.isoformat(),
        movements=peaks,
    )


@router.get("/sonify/params/schema")
async def get_params_schema(response: Response) -> dict:
    """The single schema the client renders. Also carries the kill switch."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return schema_payload()


@router.post("/sonify/params/validate")
async def validate_params(payload: dict) -> dict:
    """Normalize knobs without rendering anything."""
    schema = payload.get("schema", SCHEMA_VERSION)
    if schema not in (2, SCHEMA_VERSION):
        raise HTTPException(status_code=400, detail="Unsupported params schema")
    raw = payload.get("params", {})
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="params must be an object")
    try:
        values, warnings = normalize_with_warnings(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "schema": SCHEMA_VERSION,
        "params": values,
        "hash": params_hash(values),
        "warnings": warnings,
    }


@router.get("/sonify/params/presets")
async def get_params_presets(response: Response) -> list[dict]:
    response.headers["Cache-Control"] = "public, max-age=300"
    return presets_payload()


_EVENT_NAMES = {
    "ab_toggle",
    "profile_save",
    "knob_change",
    "prefetch_fail",
    "play",
}


def _event_log_path() -> Path:
    configured = os.environ.get("VSTOCK_SONIFY_EVENT_LOG")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "data" / "sonify-events.jsonl"


@router.post("/sonify/params/pin")
async def pin_params(payload: dict) -> dict:
    """Keep the two A/B cache marks alive while the listener toggles."""
    hashes = payload.get("hashes")
    if not isinstance(hashes, list):
        raise HTTPException(status_code=400, detail="hashes must be a list")
    if len(hashes) > 8:
        raise HTTPException(status_code=400, detail="too many hashes")
    ttl = payload.get("ttlSec", 600)
    try:
        ttl_sec = max(1.0, min(3600.0, float(ttl)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="ttlSec must be a number") from None
    recap_store().pin_hashes([str(item) for item in hashes], ttl_sec)
    return {"pinned": len(hashes), "ttlSec": ttl_sec}


@router.post("/sonify/events")
async def post_sonify_events(payload: dict) -> dict:
    """Small batch sink for the client's listening telemetry.

    One JSON object per line. No account ids, no free text. The endpoint is
    intentionally boring: the gate only needs counts by event name and day.
    """
    events = payload.get("events")
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="events must be a list")
    if len(events) > 100:
        raise HTTPException(status_code=400, detail="too many events")
    if len(json.dumps(payload, separators=(",", ":"))) > 64_000:
        raise HTTPException(status_code=413, detail="payload too large")
    accepted = 0
    rows: list[dict] = []
    for item in events:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name not in _EVENT_NAMES:
            continue
        body = item.get("payload", {})
        if body is not None and not isinstance(body, dict):
            body = {}
        rows.append(
            {
                "name": name,
                "eventId": str(item.get("eventId") or ""),
                "at": item.get("at") or time.time(),
                "payload": body or {},
            }
        )
        accepted += 1
    if not rows:
        raise HTTPException(status_code=400, detail="no known events")
    path = _event_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")
    return {"accepted": accepted}


@router.get("/sonify/dfi/signatures", response_model=list[DfiSignature])
async def get_dfi_signatures(
    response: Response,
    variant: Variant | None = Query(default=None),
    bucket: Literal["day", "span"] = Query(default="day"),
) -> list[DfiSignature]:
    """Return the offline corpus medians, when the artifact exists.

    The corpus is generated by the Phase 7 script. Until then the endpoint is
    empty, and the UI hides the genre marker instead of inventing a median.
    """
    response.headers["Cache-Control"] = "public, max-age=3600"
    path = Path(__file__).resolve().parents[1] / "sonify" / "fixtures" / "dfi_signatures.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("signatures") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    found: list[DfiSignature] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("bucket") != bucket:
            continue
        if variant is not None and row.get("variant") != variant:
            continue
        try:
            found.append(DfiSignature(**row))
        except Exception:
            continue
    return found


@router.get("/sonify/dfi/pieces", response_model=DfiPiecesResponse)
async def get_dfi_pieces(
    response: Response,
    request: Request,
    symbol: str,
    bucket: Literal["day", "span"] = Query(default="day"),
    date: date | None = Query(default=None),
    range: str | None = Query(default=None),
    asOf: str | None = Query(default=None),
    movement: int = Query(default=0, ge=0),
    variant: Variant | None = Query(default=None),
    ensemble: str | None = Query(default=None),
    humanize: bool = Query(default=True),
    color: bool = Query(default=True),
    p: str | None = Query(default=None),
) -> DfiPiecesResponse:
    """Compose other rows of the same session or movement, without exporting audio."""
    response.headers["Cache-Control"] = "no-store"
    sym = symbol.upper()
    valid = _params(p, humanize, color)
    try:
        rows = dfi_service.requested_rows(variant, ensemble)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if bucket == "day":
        if date is None:
            raise HTTPException(status_code=422, detail="date is required for bucket=day")
        try:
            results = await dfi_service.pieces_for_day(
                sym, date, rows, valid, request
            )
        except LookupError:
            raise HTTPException(
                status_code=404,
                detail=f"No 1-minute session for {sym} on {date}",
            ) from None
        except RecapCancelled:
            raise HTTPException(status_code=499, detail="DFI cancelled") from None
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"DFI compose failed: {exc}") from exc
        as_of = date.isoformat()
    else:
        if range is None:
            raise HTTPException(status_code=422, detail="range is required for bucket=span")
        if range not in SPAN_RANGES:
            raise HTTPException(status_code=404, detail=f"No sonification for {range}")
        try:
            results, stamped = await dfi_service.pieces_for_span(
                sym, range, movement, rows, valid, request
            )
        except LookupError:
            raise HTTPException(status_code=404, detail="That movement is not in this span") from None
        except RecapCancelled:
            raise HTTPException(status_code=499, detail="DFI cancelled") from None
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"DFI compose failed: {exc}") from exc
        as_of = stamped.isoformat()
    return DfiPiecesResponse(
        symbol=sym,
        bucket=bucket,
        asOf=as_of,
        pieces=[
            {
                "variant": result.variant,
                "ensemble": result.ensemble,
                "movement": result.movement,
                "dfi": None
                if result.dfi is None
                else DfiBreakdown(**result.dfi.to_dict()),
                "cached": result.cached,
                "computedAt": result.computedAt,
            }
            for result in results
        ],
    )


@router.get("/stocks/{symbol}/span/audio.m4a")
async def get_span_audio(
    symbol: str,
    request: Request,
    range: str = Query(default="1W"),
    movement: int = Query(default=0, ge=0),
    variant: Variant = Query(default="symphony"),
    ensemble: str = Query(default="classic"),
    humanize: bool = Query(default=True),
    color: bool = Query(default=True),
    p: str | None = Query(default=None),
) -> FileResponse:
    sym = symbol.upper()
    chosen = _ensemble(variant, ensemble)
    valid = _params(p, humanize, color)
    if range not in SPAN_RANGES:
        raise HTTPException(status_code=404, detail=f"No sonification for {range}")
    try:
        asset = await load_movement_audio(
            sym, range, movement, variant, request, chosen, valid
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="That movement is not in this span") from None
    except RecapCancelled:
        raise HTTPException(status_code=499, detail="Span cancelled") from None
    except RecapUnavailable as exc:
        logger.warning("Span export failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Span history unavailable: {exc}") from exc
    return FileResponse(
        asset.audio_path,
        media_type=asset.media_type,
        filename=asset.audio_path.name,
    )


@router.get("/stocks/{symbol}/sessions/{session_date}/recap/audio.m4a")
async def get_recap_audio(
    symbol: str,
    session_date: date,
    variant: Variant = Query(default="symphony"),
    ensemble: str = Query(default="classic"),
    humanize: bool = Query(default=True),
    color: bool = Query(default=True),
    p: str | None = Query(default=None),
    v: int = Query(..., ge=1),
) -> FileResponse:
    sym = symbol.upper()
    valid = _params(p, humanize, color)
    asset = ready_recap(
        sym, session_date, variant, v, _ensemble(variant, ensemble), valid
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="Recap audio is not ready")
    return FileResponse(
        asset.audio_path,
        media_type=asset.media_type,
        filename=asset.audio_path.name,
    )
