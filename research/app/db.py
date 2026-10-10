from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from app.config import ARTICLE_RETENTION_DAYS, DEFAULT_UNIVERSE

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS ratio_points (
    symbol TEXT NOT NULL,
    report_date TEXT NOT NULL,
    code TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (symbol, report_date, code)
);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    symbols TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'other',
    effect TEXT NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS verdicts (
    as_of TEXT NOT NULL,
    symbol TEXT NOT NULL,
    status TEXT NOT NULL,
    regime_open INTEGER,
    regime_reason TEXT NOT NULL DEFAULT '',
    fa_label TEXT NOT NULL DEFAULT '',
    fa_reason TEXT NOT NULL DEFAULT '',
    news_state TEXT NOT NULL DEFAULT '',
    news_reason TEXT NOT NULL DEFAULT '',
    pattern_ready INTEGER NOT NULL DEFAULT 0,
    pattern_reason TEXT NOT NULL DEFAULT '',
    rs REAL,
    priority INTEGER NOT NULL DEFAULT 0,
    stop_price REAL,
    summary TEXT NOT NULL DEFAULT '',
    metrics_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (as_of, symbol)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    as_of TEXT NOT NULL,
    symbol TEXT NOT NULL,
    signal_status TEXT NOT NULL,
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT NOT NULL DEFAULT ''
);
"""


def db_path() -> Path:
    override = os.environ.get("RESEARCH_DB_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "data" / "research.db"


def market_db_path() -> Path | None:
    override = os.environ.get("VSTOCK_MARKET_DB")
    if override:
        path = Path(override)
        return path if path.exists() else None
    path = Path(__file__).resolve().parents[2] / "backend" / "data" / "vstock.db"
    return path if path.exists() else None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    global _db
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA busy_timeout=5000")
    await _db.executescript(SCHEMA)
    cursor = await _db.execute("SELECT COUNT(*) FROM universe")
    row = await cursor.fetchone()
    if row and int(row[0]) == 0:
        await _db.executemany(
            "INSERT INTO universe (symbol, added_at) VALUES (?, ?)",
            [(symbol, _now()) for symbol in DEFAULT_UNIVERSE],
        )
    await _db.commit()


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        await init_db()
    assert _db is not None
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def universe() -> list[str]:
    db = await get_db()
    cursor = await db.execute("SELECT symbol FROM universe ORDER BY symbol")
    return [row["symbol"] for row in await cursor.fetchall()]


async def add_symbol(symbol: str) -> None:
    db = await get_db()
    await db.execute(
        "INSERT INTO universe (symbol, added_at) VALUES (?, ?) ON CONFLICT(symbol) DO NOTHING",
        (symbol, _now()),
    )
    await db.commit()


async def remove_symbol(symbol: str) -> None:
    db = await get_db()
    await db.execute("DELETE FROM universe WHERE symbol = ?", (symbol,))
    await db.commit()


async def replace_bars(symbol: str, bars: list[dict]) -> None:
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO daily_bars (symbol, trade_date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date) DO UPDATE SET
            open = excluded.open,
            high = excluded.high,
            low = excluded.low,
            close = excluded.close,
            volume = excluded.volume
        """,
        [
            (
                symbol,
                bar["trade_date"],
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
                bar["volume"],
            )
            for bar in bars
        ],
    )
    await db.commit()


async def bars(symbol: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT trade_date, open, high, low, close, volume
        FROM daily_bars
        WHERE symbol = ?
        ORDER BY trade_date
        """,
        (symbol,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def replace_ratios(symbol: str, points: dict[str, list[tuple[str, float]]]) -> None:
    db = await get_db()
    rows = [
        (symbol, day, code, value)
        for code, series in points.items()
        for day, value in series
    ]
    await db.executemany(
        """
        INSERT INTO ratio_points (symbol, report_date, code, value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(symbol, report_date, code) DO UPDATE SET value = excluded.value
        """,
        rows,
    )
    await db.commit()


async def ratios(symbol: str) -> dict[str, list[tuple[str, float]]]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT report_date, code, value
        FROM ratio_points
        WHERE symbol = ?
        ORDER BY report_date
        """,
        (symbol,),
    )
    points: dict[str, list[tuple[str, float]]] = {}
    for row in await cursor.fetchall():
        points.setdefault(row["code"], []).append((row["report_date"], row["value"]))
    return points


async def upsert_articles(articles: list[dict]) -> None:
    if not articles:
        return
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO articles (
            id, title, summary, source, published_at, url, symbols, category, kind, effect
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            symbols = excluded.symbols,
            category = excluded.category,
            kind = excluded.kind,
            effect = excluded.effect
        """,
        [
            (
                article["id"],
                article["title"],
                article.get("summary") or "",
                article.get("source") or "",
                article["published_at"],
                article.get("url") or "",
                ",".join(article.get("symbols") or []),
                article.get("category") or "",
                article.get("kind") or "other",
                article.get("effect") or "none",
            )
            for article in articles
            if article.get("id") and article.get("published_at")
        ],
    )
    await db.commit()


async def prune_articles(days: int = ARTICLE_RETENTION_DAYS) -> int:
    """Drop filings older than the market cache window."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM articles WHERE substr(published_at, 1, 10) < ?",
        (cutoff,),
    )
    await db.commit()
    return cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0


async def articles_for(symbol: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT id, title, summary, source, published_at, url, symbols, category, kind, effect
        FROM articles
        WHERE (',' || symbols || ',') LIKE ?
        ORDER BY published_at DESC
        """,
        (f"%,{symbol},%",),
    )
    rows = []
    for row in await cursor.fetchall():
        item = dict(row)
        item["symbols"] = [part for part in (item["symbols"] or "").split(",") if part]
        rows.append(item)
    return rows


async def save_verdicts(verdicts: list[dict]) -> None:
    if not verdicts:
        return
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO verdicts (
            as_of, symbol, status, regime_open, regime_reason, fa_label, fa_reason,
            news_state, news_reason, pattern_ready, pattern_reason, rs, priority,
            stop_price, summary, metrics_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(as_of, symbol) DO UPDATE SET
            status = excluded.status,
            regime_open = excluded.regime_open,
            regime_reason = excluded.regime_reason,
            fa_label = excluded.fa_label,
            fa_reason = excluded.fa_reason,
            news_state = excluded.news_state,
            news_reason = excluded.news_reason,
            pattern_ready = excluded.pattern_ready,
            pattern_reason = excluded.pattern_reason,
            rs = excluded.rs,
            priority = excluded.priority,
            stop_price = excluded.stop_price,
            summary = excluded.summary,
            metrics_json = excluded.metrics_json
        """,
        [
            (
                item["as_of"],
                item["symbol"],
                item["status"],
                None if item["regime_open"] is None else int(item["regime_open"]),
                item["regime_reason"],
                item["fa_label"],
                item["fa_reason"],
                item["news_state"],
                item["news_reason"],
                int(item["pattern_ready"]),
                item["pattern_reason"],
                item["rs"],
                item["priority"],
                item["stop_price"],
                item["summary"],
                json.dumps(item["metrics"], ensure_ascii=False),
            )
            for item in verdicts
        ],
    )
    await db.commit()


async def latest_verdicts() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT MAX(as_of) FROM verdicts")
    row = await cursor.fetchone()
    as_of = row[0] if row else None
    if not as_of:
        return []
    cursor = await db.execute(
        """
        SELECT as_of, symbol, status, regime_open, regime_reason, fa_label, fa_reason,
               news_state, news_reason, pattern_ready, pattern_reason, rs, priority,
               stop_price, summary, metrics_json
        FROM verdicts
        WHERE as_of = ?
        """,
        (as_of,),
    )
    items = []
    for record in await cursor.fetchall():
        item = dict(record)
        item["metrics"] = json.loads(item.pop("metrics_json") or "[]")
        item["regime_open"] = None if item["regime_open"] is None else bool(item["regime_open"])
        item["pattern_ready"] = bool(item["pattern_ready"])
        items.append(item)
    return items


async def verdict(symbol: str) -> dict | None:
    items = await latest_verdicts()
    for item in items:
        if item["symbol"] == symbol:
            return item
    return None


async def add_decision(as_of: str, symbol: str, signal_status: str, action: str, note: str) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO decisions (created_at, as_of, symbol, signal_status, action, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (_now(), as_of, symbol, signal_status, action, note),
    )
    await db.commit()


async def recent_decisions(limit: int = 20) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT created_at, as_of, symbol, signal_status, action, note
        FROM decisions
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def decisions_for(symbol: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT created_at, as_of, symbol, signal_status, action, note
        FROM decisions
        WHERE symbol = ?
        ORDER BY id DESC
        LIMIT 20
        """,
        (symbol,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def start_run() -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO runs (started_at, status, message) VALUES (?, 'running', '')",
        (_now(),),
    )
    await db.commit()
    return int(cursor.lastrowid)


async def finish_run(run_id: int, status: str, message: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE runs SET finished_at = ?, status = ?, message = ? WHERE id = ?",
        (_now(), status, message, run_id),
    )
    await db.commit()


async def latest_run() -> dict | None:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT id, started_at, finished_at, status, message
        FROM runs
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = await cursor.fetchone()
    return dict(row) if row else None
