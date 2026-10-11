from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

from urllib.parse import quote

from app.classify import classify_article
from app.config import (
    BANKS,
    FLOW_PAGE_SIZE,
    HISTORY_START,
    INSURERS,
    MACRO_SYMBOLS,
    MARKET_SERIES,
    PRICE_JUMP_LIMIT_UNKNOWN,
    RATIO_CODES,
    SECURITIES,
    TRADINGVIEW_SCANNER,
)
from app.db import market_db_path
from app.money import policy_points

logger = logging.getLogger(__name__)
_exchange_cache: tuple[str, dict[str, str]] | None = None
_exchange_warned: str | None = None

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
VNDIRECT_STATEMENTS = "https://api-finfo.vndirect.com.vn/v4/financial_statements"
# Statement line items: charter capital, and operating profit of the corporate income statement.
CHARTER_CAPITAL_ITEM = "14110"
OPERATING_PROFIT_ITEM = "23110"
VNDIRECT_NEWS = "https://api-finfo.vndirect.com.vn/v4/news"
VNDIRECT_FOREIGN = "https://api-finfo.vndirect.com.vn/v4/foreigns"
YAHOO_CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
# The ratios endpoint pages per symbol, so one call can carry every ratioCode.
RATIOS_PAGE_SIZE = 900
VIETSTOCK_NEWS = "https://finance.vietstock.vn/{symbol}/tin-tuc-su-kien.htm"
VIETSTOCK_ARTICLE = "https://vietstock.vn{path}"
_FILING_KINDS = frozenset(
    {
        "earnings_release",
        "bonus_shares",
        "dilution",
        "insider_sell",
        "insider_buy",
        "suspension",
        "audit_exception",
        "dividend",
    }
)


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


async def fetch_bars(
    client: httpx.AsyncClient, symbol: str, *, index: bool = False, start: str = HISTORY_START
) -> list[dict]:
    now = int(datetime.now(timezone.utc).timestamp())
    since = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    url = ENTRADE_INDEX if index else ENTRADE_STOCK
    response = await client.get(
        url,
        params={"symbol": symbol, "resolution": "1D", "from": since, "to": now},
        headers=ENTRADE_HEADERS,
    )
    response.raise_for_status()
    return _bars_from_payload(response.json() or {})


def _series_from_rows(rows: list[dict]) -> dict[str, list[tuple[str, float]]]:
    """Group ratio rows by code, keeping the first row per report date."""
    points: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        code = str(row.get("ratioCode") or "")
        report = str(row.get("reportDate") or "")[:10]
        raw = row.get("value")
        if not code or not report or raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        series = points.setdefault(code, [])
        if any(day == report for day, _value in series):
            continue
        series.append((report, value))
    for series in points.values():
        series.sort()
    return points


async def _statement_item(
    client: httpx.AsyncClient, symbol: str, item_code: str, size: int, sort: str
) -> list[tuple[str, float]] | None:
    """One line of the quarterly statements. None means the source did not answer."""
    try:
        response = await client.get(
            VNDIRECT_STATEMENTS,
            params={
                "q": f"code:{symbol}~itemCode:{item_code}~reportType:QUARTER",
                "size": size,
                "sort": sort,
            },
            headers=BROWSER_HEADERS,
        )
        if response.status_code != 200:
            return None
        out: dict[str, float] = {}
        for row in (response.json() or {}).get("data") or []:
            fiscal = str(row.get("fiscalDate") or "")[:10]
            raw = row.get("numericValue")
            if not fiscal or raw is None:
                continue
            try:
                out.setdefault(fiscal, float(raw))
            except (TypeError, ValueError):
                continue
        return sorted(out.items())
    except Exception as exc:
        logger.warning("Statement item %s failed for %s: %s", item_code, symbol, exc)
        return None


async def fetch_historical_shares(
    client: httpx.AsyncClient, symbol: str
) -> list[tuple[str, float]] | None:
    """Charter capital itemCode 14110 divided by par value (10,000 VND) gives share counts before 2023.

    None means the source did not answer; an empty list means it has no quarter for the name.
    """
    rows = await _statement_item(client, symbol, CHARTER_CAPITAL_ITEM, 100, "fiscalDate:asc")
    if rows is None:
        return None
    return [(day, value / 10000.0) for day, value in rows if value > 0]


async def fetch_operating_profit(
    client: httpx.AsyncClient, symbol: str
) -> list[tuple[str, float]] | None:
    """Quarterly operating profit, the absolute number behind OPERATING_PROFIT_QR_GRYOY.

    The ratio API only carries the growth, and leaves it blank when the base quarter was a loss.
    """
    return await _statement_item(client, symbol, OPERATING_PROFIT_ITEM, 40, "fiscalDate:desc")


async def supplement_historical_shares(
    client: httpx.AsyncClient,
    symbol: str,
    points: dict[str, list[tuple[str, float]]],
) -> bool:
    """Merge the older share counts under the ratio series. True once the source has answered.

    The ratio API starts its share series at 2022-12-31 for every name, so the caller has to
    remember who is done: the merged quarters stay in the store, and asking again only repeats
    a request per name per session.
    """
    historical = await fetch_historical_shares(client, symbol)
    if historical is None:
        return False
    existing = dict(points.get("OUTSTANDING_SHARES") or [])
    for day, val in historical:
        existing.setdefault(day, val)
    if existing:
        points["OUTSTANDING_SHARES"] = sorted(existing.items())
    return True


async def fetch_ratios(client: httpx.AsyncClient, symbol: str) -> dict[str, list[tuple[str, float]]]:
    """One request per symbol: the API pages per symbol, so every ratioCode fits in one call."""
    query = f"code:{symbol}~ratioCode:in({','.join(RATIO_CODES)})"
    response = await client.get(
        VNDIRECT_RATIOS,
        params={"q": query, "size": RATIOS_PAGE_SIZE, "sort": "reportDate:desc"},
        headers=BROWSER_HEADERS,
    )
    points: dict[str, list[tuple[str, float]]] = {}
    if response.status_code == 200:
        points = _series_from_rows((response.json() or {}).get("data") or [])
    if not points:
        logger.warning("Batched ratio fetch failed for %s, falling back to per code calls", symbol)
        points = await fetch_ratios_per_code(client, symbol)
    # Banks, brokers and insurers file other statement models; only corporates read this line.
    if symbol not in BANKS and symbol not in SECURITIES and symbol not in INSURERS:
        operating = await fetch_operating_profit(client, symbol)
        if operating:
            points["OPERATING_PROFIT_QR"] = operating
    return points


async def fetch_ratios_per_code(
    client: httpx.AsyncClient,
    symbol: str,
) -> dict[str, list[tuple[str, float]]]:
    """Fallback path: one request per ratioCode, the shape this module used before."""
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


def _json_array_after(html: str, marker: str) -> list[dict]:
    start = html.find(marker)
    if start < 0:
        return []
    start = html.find("[", start)
    if start < 0:
        return []
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(html)):
        char = html[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(html[start : index + 1])
                except json.JSONDecodeError:
                    return []
                return payload if isinstance(payload, list) else []
    return []


def _vietstock_day(raw: object) -> str | None:
    text = str(raw or "")
    digits = ""
    if text.startswith("/Date("):
        digits = "".join(char for char in text if char.isdigit())
    if not digits:
        return None
    try:
        moment = datetime.fromtimestamp(int(digits) / 1000, VN_TZ)
    except (OverflowError, OSError, ValueError):
        return None
    return moment.date().isoformat()


def parse_vietstock_filings(html: str, symbol: str) -> list[dict]:
    """Keep company filings from a Vietstock symbol page. Sector headlines are left out."""
    symbol = symbol.upper()
    articles: list[dict] = []
    seen: set[str] = set()
    for row in _json_array_after(html, "_NewsData="):
        if not isinstance(row, dict):
            continue
        title = str(row.get("Title") or "").strip()
        article_id = str(row.get("ArticleID") or "").strip()
        published = _vietstock_day(row.get("PublishTime"))
        if not title or not article_id or not published or article_id in seen:
            continue
        channel = row.get("ChannelID")
        owned = title.upper().startswith(f"{symbol}:")
        statement = channel == 3118 and "báo cáo tài chính" in title.lower()
        if not owned and not statement:
            continue
        label = classify_article(title, "", "disclosure")
        if label.kind not in _FILING_KINDS:
            continue
        path = str(row.get("URL") or "")
        url = path if path.startswith("http") else VIETSTOCK_ARTICLE.format(path=path)
        seen.add(article_id)
        articles.append(
            {
                "id": f"vst:{article_id}",
                "title": title,
                "summary": "",
                "source": "Vietstock",
                "published_at": published,
                "url": url,
                "symbols": [symbol],
                "category": "disclosure",
                "kind": label.kind,
                "effect": label.effect,
            }
        )
    return articles


async def fetch_vietstock_filings(client: httpx.AsyncClient, symbol: str) -> list[dict]:
    response = await client.get(
        VIETSTOCK_NEWS.format(symbol=symbol),
        headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"},
    )
    if response.status_code != 200:
        return []
    return parse_vietstock_filings(response.text, symbol)


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
    try:
        for article in await fetch_vietstock_filings(client, symbol):
            if article["id"] in seen:
                continue
            seen.add(article["id"])
            articles.append(article)
    except httpx.HTTPError as exc:
        logger.warning("Vietstock filings failed for %s: %s", symbol, exc)
    return articles


async def fetch_foreign_flow(
    client: httpx.AsyncClient,
    symbol: str,
) -> dict[str, list[tuple[str, float]]]:
    """Daily foreign trading from VNDirect Finfo, walking every page it still has."""
    points: dict[str, list[tuple[str, float]]] = {}
    seen: set[tuple[str, str]] = set()

    def _add(code: str, day: str, value: object) -> None:
        if value is None or (code, day) in seen:
            return
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        seen.add((code, day))
        points.setdefault(code, []).append((day, number))

    page = 1
    total_pages = 1
    while page <= total_pages and page <= 30:
        response = await client.get(
            VNDIRECT_FOREIGN,
            params={
                "q": f"code:{symbol}",
                "size": FLOW_PAGE_SIZE,
                "page": page,
                "sort": "tradingDate:desc",
            },
            headers=BROWSER_HEADERS,
        )
        response.raise_for_status()
        payload = response.json() or {}
        rows = payload.get("data") or []
        if not rows:
            break
        before = len(seen)
        for row in rows:
            day = str(row.get("tradingDate") or "")[:10]
            if not day:
                continue
            _add("FOREIGN_NET_VOL", day, row.get("netVol"))
            _add("FOREIGN_NET_VAL", day, row.get("netVal"))
            total = row.get("totalRoom")
            current = row.get("currentRoom")
            if total and current is not None:
                try:
                    room = float(current) / float(total)
                except (TypeError, ValueError, ZeroDivisionError):
                    room = None
                if room is not None:
                    _add("FOREIGN_ROOM_RATIO", day, room)
        if len(seen) == before:
            break
        # The first page reports totalPages. Later pages omit it, so a missing count
        # must not shrink the walk back to the page just read.
        reported = payload.get("totalPages")
        if reported:
            total_pages = int(reported)
        elif page >= total_pages and len(rows) < FLOW_PAGE_SIZE:
            break
        elif page >= total_pages:
            total_pages = page + 1
        page += 1
    for series in points.values():
        series.sort()
    return points


async def fetch_macro(client: httpx.AsyncClient, start: str = HISTORY_START) -> dict[str, list[dict]]:
    """Cross-market closes for the macro layer. Yahoo serves all four symbols."""
    series: dict[str, list[dict]] = {}
    for code, symbol, _label in MACRO_SYMBOLS:
        response = await client.get(
            YAHOO_CHART.format(symbol=quote(symbol, safe="")),
            params={
                "period1": int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp()),
                "period2": int(datetime.now(timezone.utc).timestamp()),
                "interval": "1d",
            },
            headers=BROWSER_HEADERS,
        )
        if response.status_code != 200:
            logger.warning("Macro fetch failed for %s: HTTP %s", code, response.status_code)
            continue
        results = ((response.json() or {}).get("chart") or {}).get("result") or []
        if not results:
            continue
        payload = results[0]
        stamps = payload.get("timestamp") or []
        quotes = ((payload.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        bars: list[dict] = []
        for stamp, close in zip(stamps, closes):
            if close is None:
                continue
            day = datetime.fromtimestamp(int(stamp), timezone.utc).date().isoformat()
            bars.append({"trade_date": day, "close": float(close)})
        bars.sort(key=lambda bar: bar["trade_date"])
        if bars:
            series[code] = bars
    return series


async def _scanner_close(client: httpx.AsyncClient, symbol: str) -> float | None:
    """Last value of one public quote. TradingView serves rates and yields without a key."""
    response = await client.get(
        TRADINGVIEW_SCANNER,
        params={"symbol": symbol, "fields": "close"},
        headers=BROWSER_HEADERS,
    )
    if response.status_code != 200:
        logger.warning("Market fetch failed for %s: HTTP %s", symbol, response.status_code)
        return None
    payload = response.json() or {}
    close = payload.get("close")
    if close is None:
        logger.warning("Market fetch failed for %s: %s", symbol, payload.get("code") or "no close")
        return None
    try:
        return float(close)
    except (TypeError, ValueError):
        return None


async def _yahoo_close(client: httpx.AsyncClient, symbol: str) -> float | None:
    """A second quote for one series, used when the first one is unavailable."""
    response = await client.get(
        YAHOO_CHART.format(symbol=quote(symbol, safe="")),
        params={"range": "5d", "interval": "1d"},
        headers=BROWSER_HEADERS,
    )
    if response.status_code != 200:
        return None
    results = ((response.json() or {}).get("chart") or {}).get("result") or []
    if not results:
        return None
    closes = ((results[0].get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    for close in reversed(closes):
        if close is None:
            continue
        try:
            return float(close)
        except (TypeError, ValueError):
            return None
    return None


async def fetch_market(
    client: httpx.AsyncClient, day: str | None = None
) -> dict[str, list[tuple[str, float]]]:
    """One point per series for the session being scored.

    A series that fails is left out instead of reusing an older number, so a broken feed shows
    up as "Chưa chấm" rather than as a stale reading. The policy rate is a record of decisions,
    so it arrives as its own step series.
    """
    stamp = day or datetime.now(VN_TZ).date().isoformat()
    points: dict[str, list[tuple[str, float]]] = {"POLICY_RATE": policy_points()}
    for code, _label, _unit, symbol in MARKET_SERIES:
        if not symbol:
            continue
        value = await _scanner_close(client, symbol)
        if value is None and code == "USDVND":
            value = await _yahoo_close(client, "USDVND=X")
        if value is not None:
            points[code] = [(stamp, value)]
    return points


def load_valuation() -> dict[str, dict]:
    """P/E, P/B and ROE per symbol from the market database. A snapshot, not a history."""
    connection = _open_market_db()
    if connection is None:
        return {}
    try:
        cursor = connection.execute(
            "SELECT symbol, pe, pb, roe, roa, updated_at FROM fundamentals"
        )
        return {
            str(row["symbol"]).upper(): {
                "pe": row["pe"],
                "pb": row["pb"],
                "roe": row["roe"],
                "roa": row["roa"],
                "updated_at": row["updated_at"],
            }
            for row in cursor
            if row["symbol"]
        }
    except sqlite3.Error as exc:
        logger.warning("Market fundamentals unreadable: %s", exc)
        return {}
    finally:
        connection.close()


def _open_market_db() -> sqlite3.Connection | None:
    path = market_db_path()
    if path is None:
        return None
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error as exc:
        logger.warning("Market database unreadable at %s: %s", path, exc)
        return None
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def load_exchanges() -> dict[str, str]:
    """Return symbol → board. A successful read is reused until the next calendar day."""
    global _exchange_cache
    today = datetime.now(VN_TZ).date().isoformat()
    if _exchange_cache is not None and _exchange_cache[0] == today:
        return _exchange_cache[1]
    connection = _open_market_db()
    if connection is None:
        _warn_no_exchanges(today, "không tìm thấy kho thị trường (backend/data/vstock.db hoặc VSTOCK_MARKET_DB)")
        return {}
    try:
        rows = connection.execute("SELECT symbol, exchange FROM symbols")
        found = {
            str(row["symbol"]).upper(): str(row["exchange"]).upper()
            for row in rows
            if row["symbol"] and row["exchange"]
        }
    except sqlite3.Error as exc:
        _warn_no_exchanges(today, f"đọc lỗi: {exc}")
        return {}
    finally:
        connection.close()
    if not found:
        _warn_no_exchanges(today, "bảng symbols rỗng")
        return {}
    _exchange_cache = (today, found)
    return found


def _warn_no_exchanges(today: str, why: str) -> None:
    """Without boards every name falls back to the widest jump limit, so say it once a day."""
    global _exchange_warned
    if _exchange_warned == today:
        return
    _exchange_warned = today
    logger.warning(
        "Không có bảng sàn (%s). Luật giá chưa chỉnh chia tách đang dùng biên độ %.0f%% cho mọi mã.",
        why,
        PRICE_JUMP_LIMIT_UNKNOWN * 100,
    )


def load_market_articles() -> list[dict]:
    connection = _open_market_db()
    if connection is None:
        return []
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
    except sqlite3.Error as exc:
        logger.warning("Market filings unreadable: %s", exc)
        return []
    finally:
        connection.close()
