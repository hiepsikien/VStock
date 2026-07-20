from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    DEFAULT_WATCHLIST,
    ChartRange,
    HistoryResponse,
    StockDetail,
    WatchlistItem,
)
from app.services import fundamentals, history, quotes

router = APIRouter(prefix="/v1")


@router.get("/watchlist", response_model=list[WatchlistItem])
async def get_watchlist(
    symbols: str | None = Query(
        default=None,
        description="Comma-separated symbols. Defaults to VN blue chips.",
    ),
) -> list[WatchlistItem]:
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else list(DEFAULT_WATCHLIST)
    )
    if not symbol_list:
        symbol_list = list(DEFAULT_WATCHLIST)

    try:
        quote_map = await quotes.fetch_quotes(symbol_list)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quote source unavailable: {exc}") from exc

    async def build_item(sym: str) -> WatchlistItem | None:
        q = quote_map.get(sym)
        if not q:
            return None
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

    items = await asyncio.gather(*(build_item(s) for s in symbol_list))
    return [item for item in items if item is not None]


@router.get("/stocks/{symbol}", response_model=StockDetail)
async def get_stock(symbol: str) -> StockDetail:
    sym = symbol.upper()
    try:
        q = await quotes.fetch_quote(sym)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Quote source unavailable: {exc}") from exc

    if not q:
        raise HTTPException(status_code=404, detail=f"Symbol not found: {sym}")

    try:
        fund, spark = await asyncio.gather(
            fundamentals.fetch_fundamentals(sym),
            history.fetch_sparkline(sym),
        )
    except Exception:
        fund = {"name": sym, "exchange": "HOSE", "marketCap": "—", "pe": None}
        spark = []

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
