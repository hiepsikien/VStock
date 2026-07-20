from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.domain.news import NewsArticle
from app.ingestion.normalizers.vndirect import parse_vndirect_news
from app.ingestion.providers.news_base import NewsProvider
from app.services.http_utils import BROWSER_HEADERS

VNDIRECT_NEWS = "https://api-finfo.vndirect.com.vn/v4/news"

DEFAULT_GROUPS = (
    "stock_news",
    "macro_news",
    "company_news",
    "disclosure",
    "commodity_news",
    "real_estate_news",
)


class VndirectNewsProvider(NewsProvider):
    name = "vndirect"
    priority = 1

    def __init__(self, groups: tuple[str, ...] | None = None) -> None:
        self.groups = groups or DEFAULT_GROUPS

    async def _fetch_query(
        self,
        client: httpx.AsyncClient,
        query: str,
        size: int,
    ) -> list[NewsArticle]:
        resp = await client.get(
            VNDIRECT_NEWS,
            params={"q": query, "size": size, "sort": "newsDate:desc"},
        )
        resp.raise_for_status()
        rows = (resp.json() or {}).get("data") or []
        articles: list[NewsArticle] = []
        for row in rows:
            article = parse_vndirect_news(row)
            if article:
                articles.append(article)
        return articles

    async def fetch_market_news(self, limit: int) -> list[NewsArticle]:
        per_group = max(limit // max(len(self.groups), 1), 6)
        async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS) as client:
            batches = await asyncio.gather(
                *[
                    self._fetch_query(client, f"newsGroup:{group}", per_group)
                    for group in self.groups
                ]
            )

        merged: dict[str, NewsArticle] = {}
        for batch in batches:
            for article in batch:
                merged[article.id] = article

        return sorted(merged.values(), key=lambda item: item.published_at, reverse=True)[:limit]

    async def fetch_symbol_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        sym = symbol.upper()
        async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS) as client:
            return await self._fetch_query(client, f"tagCodes:{sym}", limit)


def build_vndirect_news_provider(config: dict[str, Any] | None = None) -> VndirectNewsProvider:
    config = config or {}
    groups_raw = config.get("groups")
    if isinstance(groups_raw, list) and groups_raw:
        groups = tuple(str(g).strip() for g in groups_raw if str(g).strip())
        return VndirectNewsProvider(groups=groups)
    return VndirectNewsProvider()
