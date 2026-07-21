from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    DEFAULT_WATCHLIST,
    ChartRange,
    HistoryResponse,
    IncomePeriod,
    IndicesResponse,
    IndexQuote,
    MarketStatusResponse,
    StockDetail,
    SymbolInfo,
    SymbolsResponse,
    WatchlistItem,
)
from app.services import fundamentals, history, indices, market_session, quotes, symbols as symbols_service

router = APIRouter(prefix="/v1")


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

    items = [SymbolInfo(**r) for r in rows]
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
    return [SymbolInfo(**r) for r in rows]


@router.get("/indices", response_model=IndicesResponse)
async def get_market_indices() -> IndicesResponse:
    try:
        rows = await indices.fetch_market_indices()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Index source unavailable: {exc}") from exc
    return IndicesResponse(items=[IndexQuote(**r) for r in rows])


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
