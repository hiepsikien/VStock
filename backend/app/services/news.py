from __future__ import annotations

from app.ingestion.providers.news_registry import get_news_registry
from app.services.cache import cache

NEWS_TTL = 900  # 15 minutes


async def fetch_market_news(limit: int = 30) -> list[dict]:
    key = f"news:market:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    articles = await get_news_registry().fetch_market_news(limit=limit)
    ordered = [article.to_api_dict() for article in articles]
    cache.set(key, ordered, NEWS_TTL)
    return ordered


async def fetch_symbol_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    key = f"news:symbol:{sym}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    articles = await get_news_registry().fetch_symbol_news(symbol=sym, limit=limit)
    items = [article.to_api_dict() for article in articles]
    cache.set(key, items, NEWS_TTL)
    return items
