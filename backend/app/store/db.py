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
CREATE INDEX IF NOT EXISTS idx_news_category_published ON news(category, published_at);

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
CREATE INDEX IF NOT EXISTS idx_history_range_symbol ON history(range_key, symbol);

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

CREATE TABLE IF NOT EXISTS studio_sentence_specs (
    id TEXT PRIMARY KEY,
    pattern TEXT NOT NULL,
    meter TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL,
    rollback_of TEXT,
    UNIQUE(pattern, meter, version)
);

CREATE INDEX IF NOT EXISTS idx_studio_sentence_specs_key
    ON studio_sentence_specs(pattern, meter, version DESC);

CREATE TABLE IF NOT EXISTS studio_blobs (
    sha256 TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    refcount INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS studio_uploads (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    blob_sha256 TEXT NOT NULL REFERENCES studio_blobs(sha256),
    filename TEXT NOT NULL DEFAULT '',
    mime TEXT NOT NULL DEFAULT '',
    width INTEGER,
    height INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_studio_uploads_owner
    ON studio_uploads(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS studio_quota (
    owner_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    day TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (owner_id, kind, day)
);
"""


_FUNDAMENTALS_EXTRA_COLUMNS = (
    ("eps", "REAL"),
    ("pb", "REAL"),
    ("roe", "REAL"),
    ("roa", "REAL"),
    ("dividend_yield", "REAL"),
)

# Nullable lineage column: old rows read as "not a rollback" and new writes stay
# additive, so `ALTER TABLE ... ADD COLUMN` is enough on an existing database.
_STUDIO_SENTENCE_SPEC_EXTRA_COLUMNS = (("rollback_of", "TEXT"),)

# A Phase-1 database may already have a partial `studio_uploads` table (id,
# owner, blob, created_at) from an earlier draft. Filename/MIME are additive
# with defaults so old rows stay readable; width/height are nullable.
_STUDIO_UPLOAD_EXTRA_COLUMNS = (
    ("filename", "TEXT NOT NULL DEFAULT ''"),
    ("mime", "TEXT NOT NULL DEFAULT ''"),
    ("width", "INTEGER"),
    ("height", "INTEGER"),
)


async def _ensure_schema_migrations(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(fundamentals)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col, col_type in _FUNDAMENTALS_EXTRA_COLUMNS:
        if col not in existing:
            await db.execute(f"ALTER TABLE fundamentals ADD COLUMN {col} {col_type}")

    cursor = await db.execute("PRAGMA table_info(studio_sentence_specs)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col, col_type in _STUDIO_SENTENCE_SPEC_EXTRA_COLUMNS:
        if col not in existing:
            await db.execute(
                f"ALTER TABLE studio_sentence_specs ADD COLUMN {col} {col_type}"
            )

    # SCHEMA already creates the Studio upload/blob/quota tables when missing.
    # This only backfills columns on a table that predates them.
    cursor = await db.execute("PRAGMA table_info(studio_uploads)")
    existing = {row[1] for row in await cursor.fetchall()}
    for col, col_type in _STUDIO_UPLOAD_EXTRA_COLUMNS:
        if col not in existing:
            await db.execute(
                f"ALTER TABLE studio_uploads ADD COLUMN {col} {col_type}"
            )
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
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA busy_timeout=5000")
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
