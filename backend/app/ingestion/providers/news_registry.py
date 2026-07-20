from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from app.domain.news import NewsArticle
from app.ingestion.config import load_news_providers
from app.ingestion.providers.news_base import NewsProvider
from app.ingestion.providers.rss_news import RssNewsProvider, build_rss_news_provider
from app.ingestion.providers.vndirect_news import VndirectNewsProvider, build_vndirect_news_provider

logger = logging.getLogger(__name__)

_PROVIDER_BUILDERS: dict[str, Any] = {
    "vndirect": build_vndirect_news_provider,
    "vnexpress_rss": build_rss_news_provider,
    "thanhnien_rss": build_rss_news_provider,
    "rss": build_rss_news_provider,
}


def build_news_providers(config: list[dict[str, Any]] | None = None) -> list[NewsProvider]:
    rows = config or load_news_providers()
    providers: list[NewsProvider] = []

    for row in sorted(rows, key=lambda item: int(item.get("priority", 99))):
        name = str(row.get("name", "")).strip()
        builder = _PROVIDER_BUILDERS.get(name)
        if not builder:
            logger.warning("Unknown news provider in config: %s", name)
            continue

        provider = builder(name, row) if name in {"vnexpress_rss", "thanhnien_rss", "rss"} else builder(row)
        if provider is None:
            continue

        provider.priority = int(row.get("priority", provider.priority))
        providers.append(provider)

    return providers or [VndirectNewsProvider()]


def _normalize_url(url: str) -> str:
    url = url.strip().lower()
    if not url:
        return ""

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc}{path}"


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


class NewsProviderRegistry:
    def __init__(self, providers: list[NewsProvider] | None = None) -> None:
        self.providers = providers or build_news_providers()

    async def fetch_market_news(self, limit: int) -> list[NewsArticle]:
        if not self.providers:
            return []

        per_provider = max(limit // len(self.providers), 8)
        batches = await self._gather_safe("market", per_provider)
        return self._merge_articles(batches, limit)

    async def fetch_symbol_news(self, symbol: str, limit: int) -> list[NewsArticle]:
        if not self.providers:
            return []

        per_provider = max(limit // len(self.providers), 6)
        batches = await self._gather_safe("symbol", per_provider, symbol=symbol.upper())
        return self._merge_articles(batches, limit)

    async def _gather_safe(
        self,
        mode: str,
        per_provider_limit: int,
        *,
        symbol: str | None = None,
    ) -> list[list[NewsArticle]]:
        import asyncio

        async def _fetch(provider: NewsProvider) -> list[NewsArticle]:
            try:
                if mode == "symbol" and symbol:
                    return await provider.fetch_symbol_news(symbol, per_provider_limit)
                return await provider.fetch_market_news(per_provider_limit)
            except Exception as exc:
                logger.warning("News provider %s failed: %s", provider.name, exc)
                return []

        return list(await asyncio.gather(*[_fetch(provider) for provider in self.providers]))

    def _merge_articles(self, batches: list[list[NewsArticle]], limit: int) -> list[NewsArticle]:
        merged: dict[str, NewsArticle] = {}
        title_index: dict[str, str] = {}

        for batch in batches:
            for article in batch:
                url_key = _normalize_url(article.url)
                title_key = _normalize_title(article.title)

                dedupe_key = url_key or f"title:{title_key}"
                if dedupe_key in merged:
                    continue

                if title_key and title_key in title_index:
                    continue

                merged[dedupe_key] = article
                if title_key:
                    title_index[title_key] = dedupe_key

        ordered = sorted(merged.values(), key=lambda item: item.published_at, reverse=True)
        return ordered[:limit]


_default_registry: NewsProviderRegistry | None = None


def get_news_registry() -> NewsProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = NewsProviderRegistry()
    return _default_registry
