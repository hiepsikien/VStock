from __future__ import annotations

import asyncio
import re

import httpx

from app.services.cache import cache
from app.services.http_utils import BROWSER_HEADERS

VNDIRECT_NEWS = "https://api-finfo.vndirect.com.vn/v4/news"
NEWS_TTL = 900  # 15 minutes

EDITORIAL_GROUPS = {"stock_news", "macro_news"}


def _parse_item(raw: dict) -> dict:
    tags = str(raw.get("tagCodes") or "").strip()
    symbol_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    abstract = str(raw.get("newsAbstract") or "").strip()
    if not abstract and raw.get("newsContent"):
        text = re.sub(r"<[^>]+>", " ", str(raw.get("newsContent")))
        abstract = re.sub(r"\s+", " ", text).strip()[:220]

    return {
        "id": str(raw.get("newsId") or ""),
        "title": str(raw.get("newsTitle") or "").strip(),
        "summary": abstract,
        "source": str(raw.get("newsSource") or "VNDirect").strip(),
        "publishedAt": f"{raw.get('newsDate', '')}T{raw.get('newsTime', '00:00:00')}",
        "url": str(raw.get("newsUrl") or raw.get("dstockUrl") or "").strip(),
        "imageUrl": str(raw.get("thumbnailUrl") or "").strip() or None,
        "symbols": symbol_list,
        "category": str(raw.get("newsGroup") or "news"),
    }


async def _fetch_query(client: httpx.AsyncClient, query: str, size: int) -> list[dict]:
    # VNDirect defaults to oldest-first without sort — must request newsDate:desc.
    resp = await client.get(
        VNDIRECT_NEWS,
        params={"q": query, "size": size, "sort": "newsDate:desc"},
    )
    resp.raise_for_status()
    rows = (resp.json() or {}).get("data") or []
    return [_parse_item(r) for r in rows if r.get("newsTitle")]


async def fetch_market_news(limit: int = 30) -> list[dict]:
    key = f"news:market:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    per_group = max(limit // 2, 15)
    async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS) as client:
        stock_rows, macro_rows = await asyncio.gather(
            _fetch_query(client, "newsGroup:stock_news", per_group),
            _fetch_query(client, "newsGroup:macro_news", per_group),
        )

    merged: dict[str, dict] = {}
    for item in stock_rows + macro_rows:
        merged[item["id"]] = item

    ordered = sorted(merged.values(), key=lambda x: x["publishedAt"], reverse=True)[:limit]
    cache.set(key, ordered, NEWS_TTL)
    return ordered


async def fetch_symbol_news(symbol: str, limit: int = 20) -> list[dict]:
    sym = symbol.upper()
    key = f"news:symbol:{sym}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    async with httpx.AsyncClient(timeout=20.0, headers=BROWSER_HEADERS) as client:
        items = await _fetch_query(client, f"tagCodes:{sym}", limit)

    cache.set(key, items, NEWS_TTL)
    return items
