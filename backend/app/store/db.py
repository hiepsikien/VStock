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
    listed_shares INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_updated_at ON fundamentals(updated_at);
"""


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
