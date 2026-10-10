from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

from app.classify import classify_article
from app.config import BAR_LOOKBACK_DAYS, RATIO_CODES
from app.db import market_db_path

VN_TZ = timezone(timedelta(hours=7))
ENTRADE_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://www.dnse.com.vn",
    "Referer": "https://www.dnse.com.vn/",
}
BROWSER_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
ENTRADE_STOCK = "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
ENTRADE_INDEX = "https://services.entrade.com.vn/chart-api/v2/ohlcs/index"
VNDIRECT_RATIOS = "https://api-finfo.vndirect.com.vn/v4/ratios"
VNDIRECT_NEWS = "https://api-finfo.vndirect.com.vn/v4/news"


def _bars_from_payload(payload: dict) -> list[dict]:
    stamps = payload.get("t") or []
    opens = payload.get("o") or []
    highs = payload.get("h") or []
    lows = payload.get("l") or []
    closes = payload.get("c") or []
    volumes = payload.get("v") or []
    by_day: dict[str, dict] = {}
    for index, stamp in enumerate(stamps):
        try:
            close = float(closes[index])
            high = float(highs[index])
            low = float(lows[index])
            open_price = float(opens[index])
        except (TypeError, ValueError, IndexError):
            continue
        if close <= 0 or high < low:
            continue
        day = datetime.fromtimestamp(int(stamp), VN_TZ).date().isoformat()
        volume = 0.0
        if index < len(volumes):
            try:
                volume = float(volumes[index] or 0)
            except (TypeError, ValueError):
                volume = 0.0
        by_day[day] = {
            "trade_date": day,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    return [by_day[day] for day in sorted(by_day)]


async def fetch_bars(client: httpx.AsyncClient, symbol: str, *, index: bool = False) -> list[dict]:
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - BAR_LOOKBACK_DAYS * 86400
    url = ENTRADE_INDEX if index else ENTRADE_STOCK
    response = await client.get(
        url,
        params={"symbol": symbol, "resolution": "1D", "from": start, "to": now},
        headers=ENTRADE_HEADERS,
    )
    response.raise_for_status()
    return _bars_from_payload(response.json() or {})


async def fetch_ratios(client: httpx.AsyncClient, symbol: str) -> dict[str, list[tuple[str, float]]]:
    points: dict[str, list[tuple[str, float]]] = {}
    for code in RATIO_CODES:
        response = await client.get(
            VNDIRECT_RATIOS,
            params={
                "q": f"code:{symbol}~ratioCode:{code}",
                "size": 12,
                "sort": "reportDate:desc",
            },
            headers=BROWSER_HEADERS,
        )
        if response.status_code != 200:
            continue
        series: list[tuple[str, float]] = []
        seen: set[str] = set()
        for row in (response.json() or {}).get("data") or []:
            report = str(row.get("reportDate") or "")[:10]
            raw = row.get("value")
            if not report or raw is None or report in seen:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            seen.add(report)
            series.append((report, value))
        series.sort()
        if series:
            points[code] = series
    return points


def _parse_article(row: dict) -> dict | None:
    title = str(row.get("newsTitle") or "").strip()
    news_id = str(row.get("newsId") or "").strip()
    if not title or not news_id:
        return None
    tags = str(row.get("tagCodes") or "")
    symbols = []
    for tag in tags.split(","):
        symbol = tag.strip().upper()
        if symbol.isalnum() and 2 <= len(symbol) <= 8:
            symbols.append(symbol)
    category = str(row.get("newsGroup") or "news")
    summary = str(row.get("newsAbstract") or "").strip()
    label = classify_article(title, summary, category)
    published = f"{row.get('newsDate') or ''}T{row.get('newsTime') or '00:00:00'}"
    return {
        "id": f"vnd:{news_id}",
        "title": title,
        "summary": summary,
        "source": str(row.get("newsSource") or "VNDirect"),
        "published_at": published,
        "url": str(row.get("newsUrl") or row.get("dstockUrl") or ""),
        "symbols": symbols,
        "category": category,
        "kind": label.kind,
        "effect": label.effect,
    }


async def fetch_symbol_news(client: httpx.AsyncClient, symbol: str) -> list[dict]:
    articles: list[dict] = []
    seen: set[str] = set()
    queries = (
        f"tagCodes:{symbol}~newsGroup:disclosure",
        f"tagCodes:{symbol}~newsGroup:company_news",
    )
    for query in queries:
        response = await client.get(
            VNDIRECT_NEWS,
            params={"q": query, "size": 60, "sort": "newsDate:desc"},
            headers=BROWSER_HEADERS,
        )
        if response.status_code != 200:
            continue
        for row in (response.json() or {}).get("data") or []:
            article = _parse_article(row)
            if article is None or article["id"] in seen or symbol not in article["symbols"]:
                continue
            seen.add(article["id"])
            articles.append(article)
    return articles


def load_market_articles() -> list[dict]:
    path = market_db_path()
    if path is None:
        return []
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            """
            SELECT id, title, summary, source, published_at, url, symbols, category
            FROM news
            WHERE category IN ('disclosure', 'company_news')
            """
        )
        articles = []
        for row in cursor:
            symbols = [part.strip().upper() for part in (row["symbols"] or "").split(",") if part.strip()]
            label = classify_article(row["title"], row["summary"] or "", row["category"])
            if label.kind == "ignore":
                continue
            articles.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "summary": row["summary"] or "",
                    "source": row["source"] or "",
                    "published_at": row["published_at"],
                    "url": row["url"] or "",
                    "symbols": symbols,
                    "category": row["category"],
                    "kind": label.kind,
                    "effect": label.effect,
                }
            )
        return articles
    except sqlite3.Error:
        return []
    finally:
        connection.close()
