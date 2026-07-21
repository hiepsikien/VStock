from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

import httpx

from app.domain.news import NewsArticle
from app.ingestion.normalizers.commodity_news import (
    COMMODITY_ENRICH_GROUPS,
    looks_like_commodity,
    looks_like_gold_or_oil,
)
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
        # Keep a floor per group so quieter topics (e.g. real_estate) are not
        # wiped out when sorting the merged feed by date.
        fetch_per_group = max(limit // max(len(self.groups), 1), 8)
        keep_per_group = max(limit // max(len(self.groups), 1), 1)
        want_commodity = "commodity_news" in self.groups or self.groups == ("commodity_news",)

        async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS) as client:
            group_tasks = [
                self._fetch_query(client, f"newsGroup:{group}", fetch_per_group)
                for group in self.groups
            ]
            # Scan related groups for gold/oil headlines (VNDirect rarely tags them
            # as commodity_news — usually stock_news / macro / banking_finance).
            enrich_tasks = []
            if want_commodity:
                enrich_tasks = [
                    self._fetch_query(client, f"newsGroup:{group}", 40)
                    for group in COMMODITY_ENRICH_GROUPS
                ]
            batches = await asyncio.gather(*(group_tasks + enrich_tasks))

        by_category: dict[str, list[NewsArticle]] = {group: [] for group in self.groups}
        if want_commodity and "commodity_news" not in by_category:
            by_category["commodity_news"] = []

        extras: list[NewsArticle] = []
        group_batch_count = len(self.groups)

        for idx, batch in enumerate(batches):
            is_enrich = idx >= group_batch_count
            for article in batch:
                if is_enrich:
                    if not looks_like_commodity(article.title, article.summary):
                        continue
                    article = replace(article, category="commodity_news")
                    by_category.setdefault("commodity_news", []).append(article)
                    continue

                bucket = by_category.get(article.category)
                if bucket is not None:
                    bucket.append(article)
                else:
                    extras.append(article)

        selected: list[NewsArticle] = []
        seen: set[str] = set()
        leftovers: list[NewsArticle] = []

        category_order = list(dict.fromkeys([*self.groups, *by_category.keys()]))
        for group in category_order:
            ranked = sorted(
                by_category.get(group, []),
                key=lambda item: item.published_at,
                reverse=True,
            )
            if group == "commodity_news":
                # Interleave gold/oil with agri so coffee/pepper doesn't crowd out vàng.
                gold_oil = [a for a in ranked if looks_like_gold_or_oil(a.title, a.summary)]
                agri = [a for a in ranked if a.id not in {x.id for x in gold_oil}]
                keep = keep_per_group + 3
                half = max(keep // 2, 1)
                mixed: list[NewsArticle] = []
                for i in range(max(len(gold_oil), len(agri))):
                    if i < half and i < len(gold_oil):
                        mixed.append(gold_oil[i])
                    if len(mixed) >= keep:
                        break
                    if i < half and i < len(agri):
                        mixed.append(agri[i])
                    if len(mixed) >= keep:
                        break
                # Fill remainder preferring gold/oil then agri.
                for pool in (gold_oil[half:], agri[half:]):
                    for article in pool:
                        if len(mixed) >= keep:
                            break
                        if article.id not in {m.id for m in mixed}:
                            mixed.append(article)
                pick = mixed[:keep]
                leftover_ids = {a.id for a in pick}
                leftovers.extend([a for a in ranked if a.id not in leftover_ids])
            else:
                keep = keep_per_group
                pick = ranked[:keep]
                leftovers.extend(ranked[keep:])

            for article in pick:
                if article.id in seen:
                    continue
                selected.append(article)
                seen.add(article.id)

        leftovers.extend(extras)
        if len(selected) < limit:
            for article in sorted(leftovers, key=lambda item: item.published_at, reverse=True):
                if article.id in seen:
                    continue
                selected.append(article)
                seen.add(article.id)
                if len(selected) >= limit:
                    break

        ordered = sorted(selected, key=lambda item: item.published_at, reverse=True)
        if want_commodity and self.groups == ("commodity_news",):
            # Keep vàng/dầu visible near the top of the commodity filter.
            gold_oil = [a for a in ordered if looks_like_gold_or_oil(a.title, a.summary)]
            rest = [a for a in ordered if a.id not in {g.id for g in gold_oil}]
            merged: list[NewsArticle] = []
            while gold_oil or rest:
                if gold_oil:
                    merged.append(gold_oil.pop(0))
                if rest:
                    merged.append(rest.pop(0))
            return merged[:limit]
        return ordered[:limit]

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
