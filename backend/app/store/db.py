from __future__ import annotations

import os
from pathlib import Path

import aiosqlite

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS quotes (
    symbol TEXT PRIMARY KEY,
    price REAL NOT NULL,
    change REAL NOT NULL,
    change_percent REAL NOT NULL,
    open REAL NOT NULL DEFAULT 0,
    high REAL NOT NULL DEFAULT 0,
    low REAL NOT NULL DEFAULT 0,
    volume INTEGER NOT NULL DEFAULT 0,
    ref REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'vps',
    stale INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_quotes_updated_at ON quotes(updated_at);

CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    published_at TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    image_url TEXT,
    symbols TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'news',
    provider TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at DESC);

CREATE TABLE IF NOT EXISTS indices (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    price REAL NOT NULL,
    change REAL NOT NULL,
    change_percent REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'entrade',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_indices_updated_at ON indices(updated_at);

CREATE TABLE IF NOT EXISTS history (
    symbol TEXT NOT NULL,
    range_key TEXT NOT NULL,
    prices TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'entrade',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (symbol, range_key)
);

CREATE INDEX IF NOT EXISTS idx_history_updated_at ON history(updated_at);

CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbols_exchange ON symbols(exchange);

CREATE TABLE IF NOT EXISTS fundamentals (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    market_cap TEXT NOT NULL DEFAULT '—',
    pe REAL,
    eps REAL,
    pb REAL,
    roe REAL,
    roa REAL,
    dividend_yield REAL,
    listed_shares INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_updated_at ON fundamentals(updated_at);

CREATE TABLE IF NOT EXISTS income_statements (
    symbol TEXT PRIMARY KEY,
    revenue_label TEXT NOT NULL DEFAULT 'Doanh thu thuần',
    latest_annual TEXT,
    last_quarters TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_income_statements_updated_at ON income_statements(updated_at);
"""


_FUNDAMENTALS_EXTRA_COLUMNS = (
    ("eps", "REAL"),
    ("pb", "REAL"),
    ("roe", "REAL"),
    ("roa", "REAL"),
    ("dividend_yield", "REAL"),
)


async def _ensure_schema_migrations(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(fundamentals)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col, col_type in _FUNDAMENTALS_EXTRA_COLUMNS:
        if col not in existing:
            await db.execute(f"ALTER TABLE fundamentals ADD COLUMN {col} {col_type}")
    await db.commit()


def db_path() -> Path:
    override = os.environ.get("VSTOCK_DB_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "vstock.db"


async def init_db() -> None:
    global _db
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(path)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _ensure_schema_migrations(_db)
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
