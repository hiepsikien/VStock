from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import NewsItem, NewsResponse
from app.services import news as news_service

router = APIRouter(prefix="/v1/news")


@router.get("/market", response_model=NewsResponse)
async def get_market_news(
    limit: int = Query(default=30, ge=1, le=50),
    category: str | None = Query(default=None),
) -> NewsResponse:
    try:
        items = await news_service.fetch_market_news(limit=limit, category=category)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"News source unavailable: {exc}") from exc
    return NewsResponse(items=[NewsItem(**i) for i in items])


@router.get("/symbols/{symbol}", response_model=NewsResponse)
async def get_symbol_news(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=50),
) -> NewsResponse:
    try:
        items = await news_service.fetch_symbol_news(symbol, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"News source unavailable: {exc}") from exc
    return NewsResponse(items=[NewsItem(**i) for i in items])
