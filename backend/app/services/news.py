from __future__ import annotations

from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS
from app.ingestion.providers.news_registry import get_news_registry
from app.repositories.news_repo import NewsRepository
from app.services.cache import cache

NEWS_TTL = 900  # 15 minutes

_repo = NewsRepository()

INDEX_NEWS_HINTS: dict[str, tuple[str, ...]] = {
    "VNINDEX": ("vn-index", "vnindex", "vn index", "vn-index", "hose", "vn index"),
    "HNX": ("hnx-index", "hnx index", "sàn hnx", "hnx"),
}


def _news_text(item: dict) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')}".lower()


def _filter_index_news(items: list[dict], hints: tuple[str, ...], limit: int) -> list[dict]:
    matched = [item for item in items if any(hint in _news_text(item) for hint in hints)]
    if len(matched) >= limit:
        return matched[:limit]

    seen = {item["id"] for item in matched}
    for item in items:
        if item["id"] in seen:
            continue
        if item.get("category") in {"macro_news", "stock_news"}:
            matched.append(item)
            seen.add(item["id"])
        if len(matched) >= limit:
            break
    return matched[:limit]


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


async def fetch_index_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    hints = INDEX_NEWS_HINTS.get(sym, ())
    key = f"news:index:{sym}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    pool = await fetch_market_news(max(limit * 4, 40))
    items = _filter_index_news(pool, hints, limit)
    cache.set(key, items, NEWS_TTL)
    return items


async def fetch_symbol_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    if sym in INDEX_SYMBOLS:
        return await fetch_index_news(sym, limit=limit)

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
