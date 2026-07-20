from __future__ import annotations

from typing import Any

import httpx

from app.domain.news import NewsArticle
from app.ingestion.normalizers.rss import parse_rss_feed
from app.ingestion.providers.news_base import NewsProvider
from app.services.http_utils import BROWSER_HEADERS


class RssNewsProvider(NewsProvider):
    name = "rss"

    def __init__(
        self,
        *,
        provider_name: str,
        feed_url: str,
        source_label: str,
        default_category: str,
        priority: int = 99,
    ) -> None:
        self.name = provider_name
        self.priority = priority
        self.feed_url = feed_url
        self.source_label = source_label
        self.default_category = default_category

    async def _fetch_feed(self) -> list[NewsArticle]:
        async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS, follow_redirects=True) as client:
            resp = await client.get(self.feed_url)
            resp.raise_for_status()
            return parse_rss_feed(
                resp.text,
                source=self.source_label,
                default_category=self.default_category,
                provider_prefix=self.name,
            )

    async def fetch_market_news(self, limit: int) -> list[NewsArticle]:
        articles = await self._fetch_feed()
        return sorted(articles, key=lambda item: item.published_at, reverse=True)[:limit]

    async def fetch_symbol_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        sym = symbol.upper()
        articles = await self._fetch_feed()
        matched = [
            article
            for article in articles
            if sym in article.symbols or sym in article.title.upper()
        ]
        return sorted(matched, key=lambda item: item.published_at, reverse=True)[:limit]


def build_rss_news_provider(name: str, config: dict[str, Any]) -> RssNewsProvider | None:
    feed_url = str(config.get("url") or "").strip()
    if not feed_url:
        return None

    return RssNewsProvider(
        provider_name=name,
        feed_url=feed_url,
        source_label=str(config.get("source") or name).strip(),
        default_category=str(config.get("category") or "news").strip(),
        priority=int(config.get("priority", 99)),
    )
