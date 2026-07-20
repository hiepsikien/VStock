from __future__ import annotations

import re

from app.domain.news import NewsArticle

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_vndirect_news(raw: dict) -> NewsArticle | None:
    title = str(raw.get("newsTitle") or "").strip()
    if not title:
        return None

    tags = str(raw.get("tagCodes") or "").strip()
    symbol_list = tuple(t.strip().upper() for t in tags.split(",") if t.strip()) if tags else ()

    abstract = str(raw.get("newsAbstract") or "").strip()
    if not abstract and raw.get("newsContent"):
        text = _HTML_TAG_RE.sub(" ", str(raw.get("newsContent")))
        abstract = re.sub(r"\s+", " ", text).strip()[:220]

    news_id = str(raw.get("newsId") or "").strip()
    url = str(raw.get("newsUrl") or raw.get("dstockUrl") or "").strip()
    image = str(raw.get("thumbnailUrl") or "").strip() or None

    return NewsArticle(
        id=f"vnd:{news_id}" if news_id else f"vnd:{hash(title)}",
        title=title,
        summary=abstract,
        source=str(raw.get("newsSource") or "VNDirect").strip(),
        published_at=f"{raw.get('newsDate', '')}T{raw.get('newsTime', '00:00:00')}",
        url=url,
        image_url=image,
        symbols=symbol_list,
        category=str(raw.get("newsGroup") or "news"),
    )
