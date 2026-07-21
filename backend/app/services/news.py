from __future__ import annotations

from app.ingestion.providers.entrade_indices import INDEX_SYMBOLS
from app.ingestion.providers.news_registry import get_news_registry
from app.ingestion.providers.yahoo_commodities import COMMODITY_SYMBOLS
from app.repositories.news_repo import NewsRepository
from app.services.cache import cache

NEWS_TTL = 900  # 15 minutes

_repo = NewsRepository()

INDEX_NEWS_HINTS: dict[str, tuple[str, ...]] = {
    "VNINDEX": ("vn-index", "vnindex", "vn index", "vn-index", "hose", "vn index"),
    "HNX": ("hnx-index", "hnx index", "sàn hnx", "hnx"),
}

COMMODITY_NEWS_HINTS: dict[str, tuple[str, ...]] = {
    "XAU": (
        "giá vàng",
        "vàng sjc",
        "vàng thế giới",
        "vàng trong nước",
        "spdr gold",
        "giá bạc",
        "bạc thế giới",
    ),
    "WTI": (
        "dầu thô",
        "giá dầu",
        "brent",
        "wti",
        "giá xăng",
        "xăng dầu",
        "crude",
    ),
}


def _news_text(item: dict) -> str:
    return f"{item.get('title', '')} {item.get('summary', '')}".lower()


def _filter_hint_news(
    items: list[dict],
    hints: tuple[str, ...],
    limit: int,
    *,
    fallback_categories: set[str],
) -> list[dict]:
    matched = [item for item in items if any(hint in _news_text(item) for hint in hints)]
    if len(matched) >= limit:
        return matched[:limit]

    seen = {item["id"] for item in matched}
    for item in items:
        if item["id"] in seen:
            continue
        if item.get("category") in fallback_categories:
            matched.append(item)
            seen.add(item["id"])
        if len(matched) >= limit:
            break
    return matched[:limit]


def _filter_index_news(items: list[dict], hints: tuple[str, ...], limit: int) -> list[dict]:
    return _filter_hint_news(
        items,
        hints,
        limit,
        fallback_categories={"macro_news", "stock_news"},
    )


async def fetch_market_news(limit: int = 30, category: str | None = None) -> list[dict]:
    cat = (category or "").strip() or None
    key = f"news:market:{limit}:{cat or 'all'}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    items = await _repo.get_market_news(limit, category=cat)
    need = min(limit, 5) if not cat else min(limit, 3)
    if len(items) < need:
        articles = await get_news_registry().fetch_market_news(limit=max(limit, 40))
        if articles:
            await _repo.upsert_many(articles)
            items = await _repo.get_market_news(limit, category=cat)

    # Category still empty — fetch that VNDirect group directly.
    if cat and len(items) < need:
        try:
            from app.ingestion.providers.vndirect_news import VndirectNewsProvider

            provider = VndirectNewsProvider(groups=(cat,))
            articles = await provider.fetch_market_news(limit=limit)
            if articles:
                await _repo.upsert_many(articles, provider="vndirect")
                items = await _repo.get_market_news(limit, category=cat)
        except Exception:
            pass

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


async def fetch_commodity_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    hints = COMMODITY_NEWS_HINTS.get(sym, ())
    key = f"news:commodity:{sym}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    # Prefer commodity category, then broaden to market pool.
    commodity_pool = await fetch_market_news(max(limit * 3, 30), category="commodity_news")
    items = _filter_hint_news(
        commodity_pool,
        hints,
        limit,
        fallback_categories={"commodity_news"},
    )
    if len(items) < min(limit, 3):
        pool = await fetch_market_news(max(limit * 4, 40))
        items = _filter_hint_news(
            pool,
            hints,
            limit,
            fallback_categories={"commodity_news", "macro_news"},
        )

    cache.set(key, items, NEWS_TTL)
    return items


async def fetch_symbol_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    if sym in INDEX_SYMBOLS:
        return await fetch_index_news(sym, limit=limit)
    if sym in COMMODITY_SYMBOLS:
        return await fetch_commodity_news(sym, limit=limit)

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
