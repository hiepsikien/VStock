from __future__ import annotations

from app.ingestion.providers.news_registry import get_news_registry
from app.repositories.news_repo import NewsRepository
from app.services.cache import cache

NEWS_TTL = 900  # 15 minutes

_repo = NewsRepository()


async def fetch_market_news(limit: int = 30) -> list[dict]:
    key = f"news:market:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    items = await _repo.get_market_news(limit)
    if len(items) < min(limit, 5):
        articles = await get_news_registry().fetch_market_news(limit=limit)
        if articles:
            await _repo.upsert_many(articles)
            items = await _repo.get_market_news(limit)

    cache.set(key, items, NEWS_TTL)
    return items


async def fetch_symbol_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    key = f"news:symbol:{sym}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    items = await _repo.get_symbol_news(sym, limit)
    if len(items) < min(limit, 3):
        articles = await get_news_registry().fetch_symbol_news(sym, limit=limit)
        if articles:
            await _repo.upsert_many(articles)
            items = await _repo.get_symbol_news(sym, limit)

    cache.set(key, items, NEWS_TTL)
    return items
