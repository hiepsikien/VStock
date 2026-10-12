from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from app.config import ARTICLE_RETENTION_DAYS, DEFAULT_UNIVERSE, RESEARCH_HISTORY_START
from app.evaluate import group_metrics

_db: aiosqlite.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS universe (
    symbol TEXT PRIMARY KEY,
    added_at TEXT NOT NULL
);

-- Danh sách niêm yết của nguồn, gồm cả mã đã hủy niêm yết. Rổ theo thời điểm đọc khoảng
-- niêm yết ở đây để biết mã nào có mặt trong từng năm, thay vì chỉ có những mã còn sống.
CREATE TABLE IF NOT EXISTS symbol_meta (
    symbol TEXT PRIMARY KEY,
    exchange TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    listed_date TEXT,
    delisted_date TEXT
);

-- Ngành theo bảng phân loại ICB. Bảng chứng khoán của nguồn không có mã đã hủy niêm yết,
-- nên ngành của những mã đó chỉ đến từ danh sách mã của từng nhóm ICB.
CREATE TABLE IF NOT EXISTS symbol_industry (
    symbol TEXT PRIMARY KEY,
    icb_level INTEGER NOT NULL DEFAULT 0,
    icb_code TEXT NOT NULL DEFAULT '',
    icb_name TEXT NOT NULL DEFAULT '',
    industry TEXT NOT NULL DEFAULT ''
);

-- Bookmarks for one-time work, e.g. which default symbols were already merged in.
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_bars (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL DEFAULT 0,
    -- Giá thật và giá trị khớp thật của nguồn: `close` là giá đã điều chỉnh chia tách nên
    -- không nhân được với số cổ phiếu của chính năm đó, còn khối lượng thật nhân với giá đã
    -- điều chỉnh thì ra giá trị giao dịch sai. Hai cột này chỉ phục vụ đo vốn hóa và thanh
    -- khoản của rổ, tín hiệu vẫn đọc `close`.
    raw_close REAL,
    trade_value REAL,
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

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);

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
    score INTEGER NOT NULL DEFAULT 0,
    flow_state TEXT NOT NULL DEFAULT '',
    extra_json TEXT NOT NULL DEFAULT '{}',
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

CREATE TABLE IF NOT EXISTS flow_points (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    code TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (symbol, trade_date, code)
);

-- Money gate. One series per row-set, one point per session, and the symbol column is
-- absent because these numbers belong to the market rather than to a ticker.
CREATE TABLE IF NOT EXISTS market_points (
    series TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (series, trade_date)
);

-- Forward test. One row per confirmed signal, marked to market each session.
CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    entry_date TEXT NOT NULL,
    entry_price REAL NOT NULL,
    initial_stop REAL NOT NULL,
    stop_price REAL NOT NULL,
    target1 REAL NOT NULL,
    atr14 REAL,
    sessions INTEGER NOT NULL DEFAULT 0,
    tp1_done INTEGER NOT NULL DEFAULT 0,
    booked_fraction REAL NOT NULL DEFAULT 0,
    realised REAL NOT NULL DEFAULT 0,
    last_price REAL,
    last_date TEXT,
    closed_at TEXT,
    exit_date TEXT,
    exit_price REAL,
    exit_reason TEXT,
    base_ceiling REAL,
    score INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_paper_symbol ON paper_positions(symbol);

CREATE TABLE IF NOT EXISTS valuation_points (
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    market_cap REAL,
    trailing_pe REAL,
    PRIMARY KEY (symbol, trade_date)
);

CREATE TABLE IF NOT EXISTS industry_notes (
    as_of TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    response TEXT NOT NULL,
    industries TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_marks (
    position_id INTEGER NOT NULL,
    mark_date TEXT NOT NULL,
    price REAL NOT NULL,
    return_pct REAL NOT NULL,
    PRIMARY KEY (position_id, mark_date)
);
"""

# Columns added after the first release. Existing databases get them by ALTER TABLE.
_VERDICT_EXTRA_COLUMNS = (
    ("score", "INTEGER NOT NULL DEFAULT 0"),
    ("flow_state", "TEXT NOT NULL DEFAULT ''"),
    ("extra_json", "TEXT NOT NULL DEFAULT '{}'"),
)

# The paper ledger keeps the frozen base high of the entry, so a base that forms higher
# later cannot lift the level that closes the slot.
_PAPER_EXTRA_COLUMNS = (
    ("base_ceiling", "REAL"),
)

# Giá thật và giá trị khớp thật của phiên, nạp cho nến đã có. Cột thêm sau bản đầu tiên nên
# kho cũ nhận bằng ALTER TABLE, và `replace_bars` cố ý không chạm hai cột này để lần nạp nến
# sau không xoá chúng.
_BAR_EXTRA_COLUMNS = (
    ("raw_close", "REAL"),
    ("trade_value", "REAL"),
)

# Lần chạy bắt đầu từ đâu: "web" là nút Chạy phiên, "lịch" là `app.scheduled`. Lần chạy cũ để trống.
_RUN_EXTRA_COLUMNS = (
    ("source", "TEXT NOT NULL DEFAULT ''"),
)


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
    await _ensure_schema_migrations(_db)
    await _split_usdvnd(_db)
    await _merge_default_universe(_db)
    await _db.commit()


async def _split_usdvnd(db: aiosqlite.Connection) -> None:
    """Move the Yahoo FX history out of the money gate's series, once per store.

    Before the split, history_pull and the macro fetch wrote Yahoo `USDVND=X` under `USDVND`,
    the key the money gate reads for TradingView. The whole series is copied to USDVND_MACRO,
    and the weekend rows, which only Yahoo writes, leave USDVND so its 20-row average spans
    20 sessions. Weekday rows stay as the gate's seed until TradingView points replace them.
    """
    cursor = await db.execute("SELECT 1 FROM meta WHERE key = 'usdvnd_split'")
    if await cursor.fetchone():
        return
    await db.execute(
        """
        INSERT INTO market_points (series, trade_date, value)
        SELECT 'USDVND_MACRO', trade_date, value FROM market_points WHERE series = 'USDVND'
        ON CONFLICT(series, trade_date) DO NOTHING
        """
    )
    await db.execute(
        "DELETE FROM market_points WHERE series = 'USDVND' "
        "AND strftime('%w', trade_date) IN ('0', '6')"
    )
    await db.execute("INSERT INTO meta (key, value) VALUES ('usdvnd_split', ?)", (_now(),))


async def _write_universe_seed(db: aiosqlite.Connection, symbols: list[str]) -> None:
    await db.execute(
        "INSERT INTO meta (key, value) VALUES ('universe_seed', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (json.dumps(symbols),),
    )


async def _merge_default_universe(db: aiosqlite.Connection) -> None:
    """Add default symbols the store has not seen, without re-seeding a list already set.

    A store that already holds a list keeps it, so a symbol removed by hand stays
    removed; only members appended to DEFAULT_UNIVERSE since the last merge are added.
    A store with a list but no bookmark predates this merge and its list is the operator's,
    so the defaults are not poured back in there either; recording the bookmark is what makes
    the next boot add only what is new.
    That keeps the research list in step with ingestion.quote_symbols, whose P/E numbers
    feed the valuation gate.
    """
    cursor = await db.execute("SELECT value FROM meta WHERE key = 'universe_seed'")
    row = await cursor.fetchone()
    if row is None:
        cursor = await db.execute("SELECT COUNT(*) FROM universe")
        count_row = await cursor.fetchone()
        if count_row and count_row[0]:
            await _write_universe_seed(db, list(DEFAULT_UNIVERSE))
            return
        merged: list[str] = []
    else:
        merged = json.loads(row["value"])
    missing = [symbol for symbol in DEFAULT_UNIVERSE if symbol not in merged]
    if missing:
        await db.executemany(
            "INSERT INTO universe (symbol, added_at) VALUES (?, ?) "
            "ON CONFLICT(symbol) DO NOTHING",
            [(symbol, _now()) for symbol in missing],
        )
        await _write_universe_seed(db, list(DEFAULT_UNIVERSE))


async def _ensure_schema_migrations(db: aiosqlite.Connection) -> None:
    for table, columns in (
        ("verdicts", _VERDICT_EXTRA_COLUMNS),
        ("paper_positions", _PAPER_EXTRA_COLUMNS),
        ("daily_bars", _BAR_EXTRA_COLUMNS),
        ("runs", _RUN_EXTRA_COLUMNS),
    ):
        cursor = await db.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in await cursor.fetchall()}
        for column, declaration in columns:
            if column not in existing:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
    await db.commit()


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


async def shares_backfilled() -> set[str]:
    """Names whose pre-2023 share counts the statements API has already answered for."""
    db = await get_db()
    cursor = await db.execute("SELECT value FROM meta WHERE key = 'shares_backfilled'")
    row = await cursor.fetchone()
    return set(json.loads(row["value"])) if row else set()


async def mark_shares_backfilled(symbols: list[str]) -> None:
    done = sorted(await shares_backfilled() | set(symbols))
    db = await get_db()
    await db.execute(
        "INSERT INTO meta (key, value) VALUES ('shares_backfilled', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (json.dumps(done),),
    )
    await db.commit()


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


async def replace_symbol_meta(rows: list[tuple[str, str, str, str | None, str | None]]) -> None:
    """Ghi danh sách niêm yết của nguồn: mã, sàn, trạng thái, ngày niêm yết, ngày hủy."""
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO symbol_meta (symbol, exchange, status, listed_date, delisted_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            exchange = excluded.exchange,
            status = excluded.status,
            listed_date = excluded.listed_date,
            delisted_date = excluded.delisted_date
        """,
        rows,
    )
    await db.commit()


async def symbol_meta() -> dict[str, dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT symbol, exchange, status, listed_date, delisted_date FROM symbol_meta"
    )
    return {row["symbol"]: dict(row) for row in await cursor.fetchall()}


async def replace_symbol_industry(rows: list[tuple[str, int, str, str, str]]) -> None:
    """Ghi bảng ngành ICB: mã, cấp, mã nhóm, tên nhóm, nhãn ngành của dự án."""
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO symbol_industry (symbol, icb_level, icb_code, icb_name, industry)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            icb_level = excluded.icb_level,
            icb_code = excluded.icb_code,
            icb_name = excluded.icb_name,
            industry = excluded.industry
        """,
        rows,
    )
    await db.commit()


async def symbol_industry() -> dict[str, dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT symbol, icb_level, icb_code, icb_name, industry FROM symbol_industry"
    )
    return {row["symbol"]: dict(row) for row in await cursor.fetchall()}



async def replace_bars(symbol: str, bars: list[dict]) -> None:
    db = await get_db()
    # `raw_close` và `trade_value` cố ý không có trong danh sách cập nhật: chúng chỉ đến từ
    # `write_raw_tape`, nên nạp lại nến không xoá mất cạnh thật của nguồn.
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


async def write_raw_tape(symbol: str, rows: list[tuple[str, float, float]]) -> tuple[int, int]:
    """Ghi giá thật và giá trị khớp thật của một mã; trả (số phiên khớp, số phiên không có nến).

    Chỉ cập nhật hai cột phụ của nến đã có. Phiên nguồn có mà kho không có thì để nguyên chứ
    không chèn nến mới: nến lấy từ nguồn khác có thể lệch chuỗi giá mà mọi tín hiệu đang đọc.
    """
    db = await get_db()
    batch = [(raw_close, trade_value, symbol, day) for day, raw_close, trade_value in rows]
    cursor = await db.executemany(
        "UPDATE daily_bars SET raw_close = ?, trade_value = ? WHERE symbol = ? AND trade_date = ?",
        batch,
    )
    await db.commit()
    matched = int(cursor.rowcount or 0)
    return matched, len(batch) - matched


async def bars(symbol: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT trade_date, open, high, low, close, volume, raw_close, trade_value
        FROM daily_bars
        WHERE symbol = ?
        ORDER BY trade_date
        """,
        (symbol,),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def all_bars() -> dict[str, list[dict]]:
    """Nến của mọi mã trong một truy vấn, cho phần cần cả kho như rổ theo năm và độ rộng."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT symbol, trade_date, open, high, low, close, volume, raw_close, trade_value
        FROM daily_bars
        ORDER BY trade_date
        """
    )
    out: dict[str, list[dict]] = {}
    for row in await cursor.fetchall():
        bar = dict(row)
        out.setdefault(bar.pop("symbol"), []).append(bar)
    return out


async def ratio_series(code: str) -> dict[str, dict[str, list[tuple[str, float]]]]:
    """Một mã chỉ số của mọi mã, trong hình dạng `pit_universe` đọc."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT symbol, report_date, value FROM ratio_points WHERE code = ? ORDER BY report_date",
        (code,),
    )
    out: dict[str, dict[str, list[tuple[str, float]]]] = {}
    for row in await cursor.fetchall():
        out.setdefault(row["symbol"], {}).setdefault(code, []).append((row["report_date"], row["value"]))
    return out


async def raw_tape_missing(since: str = RESEARCH_HISTORY_START) -> list[tuple[str, int, int, str]]:
    """Mã còn thiếu giá thật kể từ `since`: mã, số phiên, số phiên thiếu, phiên thiếu đầu tiên.

    Chỉ xét mã có trong bảng niêm yết của nguồn: rổ chỉ dựng từ danh sách đó, nên giá thật của
    một mã nguồn chưa xác nhận không dùng vào việc gì. Đây cũng là danh sách việc của
    `history_pull --raw-tape`: đọc từ kho thay vì từ một dấu đã ghi, vì nến lấy về sau chỉ có
    `close`, và phiên mới như thế tự lọt vào lần nạp sau mà không cần ai nhớ xoá dấu.
    """
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT b.symbol AS symbol,
               COUNT(*) AS sessions,
               SUM(b.raw_close IS NULL) AS missing,
               MIN(CASE WHEN b.raw_close IS NULL THEN b.trade_date END) AS first_missing
        FROM daily_bars b
        JOIN symbol_meta m ON m.symbol = b.symbol
        WHERE b.trade_date >= ?
        GROUP BY b.symbol
        HAVING missing > 0
        ORDER BY missing DESC, b.symbol
        """,
        (since,),
    )
    return [
        (row["symbol"], int(row["sessions"]), int(row["missing"]), str(row["first_missing"]))
        for row in await cursor.fetchall()
    ]


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


def article_retention_days() -> int:
    """Env ARTICLE_RETENTION_DAYS overrides the default that matches news_filing_days."""
    raw = os.environ.get("ARTICLE_RETENTION_DAYS", "").strip()
    if not raw:
        return ARTICLE_RETENTION_DAYS
    try:
        return max(30, int(raw))
    except ValueError:
        return ARTICLE_RETENTION_DAYS


async def prune_articles(days: int | None = None) -> int:
    """Drop filings older than the market cache window."""
    window = article_retention_days() if days is None else days
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).date().isoformat()
    db = await get_db()
    cursor = await db.execute(
        "DELETE FROM articles WHERE published_at < ?",
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
            stop_price, summary, metrics_json, score, flow_state, extra_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            metrics_json = excluded.metrics_json,
            score = excluded.score,
            flow_state = excluded.flow_state,
            extra_json = excluded.extra_json
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
                int(item.get("score") or 0),
                item.get("flow_state") or "",
                json.dumps(item.get("extra") or {}, ensure_ascii=False),
            )
            for item in verdicts
        ],
    )
    await db.commit()


_VERDICT_COLUMNS = """
    as_of, symbol, status, regime_open, regime_reason, fa_label, fa_reason,
    news_state, news_reason, pattern_ready, pattern_reason, rs, priority,
    stop_price, summary, metrics_json, score, flow_state, extra_json
"""


def _verdict_row(record) -> dict:
    item = dict(record)
    item["metrics"] = json.loads(item.pop("metrics_json") or "[]")
    extra = json.loads(item.pop("extra_json") or "{}")
    item["regime_open"] = None if item["regime_open"] is None else bool(item["regime_open"])
    item["pattern_ready"] = bool(item["pattern_ready"])
    stored_groups = [
        (str(group[0]), [tuple(metric) for metric in group[1]])
        for group in (extra.get("metric_groups") or [])
    ]
    # A row stored before the page had sections only carries the flat list, and the labels are
    # enough to file those numbers under the layer that produced them.
    groups = stored_groups or group_metrics(item["metrics"])
    item.update(
        {
            "score_parts": [tuple(part) for part in extra.get("score_parts", [])],
            "score_ok": bool(extra.get("score_ok")),
            "flow_reason": extra.get("flow_reason") or "",
            "flow_level": extra.get("flow_level") or "missing",
            "macro_reason": extra.get("macro_reason") or "",
            "macro_block": bool(extra.get("macro_block")),
            "market_reason": extra.get("market_reason") or "",
            "market_open": (
                None if extra.get("market_open") is None else bool(extra.get("market_open"))
            ),
            "valuation_label": extra.get("valuation_label") or "",
            "valuation_reason": extra.get("valuation_reason") or "",
            "patterns": tuple(extra.get("patterns") or ()),
            "pattern_score": int(extra.get("pattern_score") or 0),
            "f_score": extra.get("f_score"),
            "f_score_max": int(extra.get("f_score_max") or 0),
            "warnings": list(extra.get("warnings") or []),
            "base_ceiling": extra.get("base_ceiling"),
            "base_advance": extra.get("base_advance"),
            "base_depth": extra.get("base_depth"),
            "base_sessions": int(extra.get("base_sessions") or 0),
            "breakout_volume_ratio": extra.get("breakout_volume_ratio"),
            "failed_breakout": extra.get("failed_breakout") or None,
            "metric_groups": groups,
        }
    )
    return item


async def latest_verdicts() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT MAX(as_of) FROM verdicts")
    row = await cursor.fetchone()
    as_of = row[0] if row else None
    if not as_of:
        return []
    cursor = await db.execute(
        f"""
        SELECT {_VERDICT_COLUMNS}
        FROM verdicts
        WHERE as_of = ?
        """,
        (as_of,),
    )
    return [_verdict_row(record) for record in await cursor.fetchall()]


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


async def start_run(source: str = "web") -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO runs (started_at, status, message, source) VALUES (?, 'running', '', ?)",
        (_now(), source),
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
    runs = await recent_runs(1)
    return runs[0] if runs else None


async def recent_runs(limit: int = 10) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT id, started_at, finished_at, status, message, source
        FROM runs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in await cursor.fetchall()]


def _flow_rows(symbol: str, points: dict[str, list[tuple[str, float]]]) -> list[tuple]:
    return [
        (symbol, day, code, value)
        for code, series in points.items()
        for day, value in series
    ]


async def replace_flow(symbol: str, points: dict[str, list[tuple[str, float]]]) -> None:
    db = await get_db()
    await db.execute("DELETE FROM flow_points WHERE symbol = ?", (symbol,))
    rows = _flow_rows(symbol, points)
    if rows:
        await db.executemany(
            """
            INSERT INTO flow_points (symbol, trade_date, code, value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol, trade_date, code) DO UPDATE SET value = excluded.value
            """,
            rows,
        )
    await db.commit()


async def upsert_flow(symbol: str, points: dict[str, list[tuple[str, float]]]) -> None:
    """Keep older foreign-flow sessions. A new download only rewrites the days it contains."""
    rows = _flow_rows(symbol, points)
    if not rows:
        return
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO flow_points (symbol, trade_date, code, value)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date, code) DO UPDATE SET value = excluded.value
        """,
        rows,
    )
    await db.commit()


async def upsert_valuation(rows: list[tuple[str, str, float | None, float | None]]) -> None:
    if not rows:
        return
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO valuation_points (symbol, trade_date, market_cap, trailing_pe)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date) DO UPDATE SET
            market_cap = excluded.market_cap,
            trailing_pe = excluded.trailing_pe
        """,
        rows,
    )
    await db.commit()


async def industry_notes() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT as_of, prompt, response, industries FROM industry_notes ORDER BY as_of"
    )
    return [dict(row) for row in await cursor.fetchall()]


async def save_industry_note(as_of: str, prompt: str, response: str, industries: str) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO industry_notes (as_of, prompt, response, industries)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(as_of) DO UPDATE SET
            prompt = excluded.prompt,
            response = excluded.response,
            industries = excluded.industries
        """,
        (as_of, prompt, response, industries),
    )
    await db.commit()


async def flow(symbol: str) -> dict[str, list[tuple[str, float]]]:
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT trade_date, code, value
        FROM flow_points
        WHERE symbol = ?
        ORDER BY trade_date
        """,
        (symbol,),
    )
    points: dict[str, list[tuple[str, float]]] = {}
    for row in await cursor.fetchall():
        points.setdefault(row["code"], []).append((row["trade_date"], row["value"]))
    return points


async def upsert_market_points(series: str, points: list[tuple[str, float]]) -> None:
    """One point per session. Re-running a session rewrites its own point, never the history."""
    rows = [(series, str(day), float(value)) for day, value in points]
    if not rows:
        return
    db = await get_db()
    await db.executemany(
        """
        INSERT INTO market_points (series, trade_date, value)
        VALUES (?, ?, ?)
        ON CONFLICT(series, trade_date) DO UPDATE SET value = excluded.value
        """,
        rows,
    )
    await db.commit()


async def market_points() -> dict[str, list[tuple[str, float]]]:
    """Every stored money series, oldest point first, in the shape money_state reads."""
    db = await get_db()
    cursor = await db.execute(
        """
        SELECT series, trade_date, value
        FROM market_points
        ORDER BY trade_date
        """
    )
    points: dict[str, list[tuple[str, float]]] = {}
    for row in await cursor.fetchall():
        points.setdefault(row["series"], []).append((row["trade_date"], row["value"]))
    return points


async def open_paper_position(position: dict) -> int:
    db = await get_db()
    cursor = await db.execute(
        """
        INSERT INTO paper_positions (
            symbol, opened_at, entry_date, entry_price, initial_stop, stop_price,
            target1, atr14, base_ceiling, sessions, score, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position["symbol"],
            _now(),
            position["entry_date"],
            position["entry_price"],
            position["initial_stop"],
            position["stop_price"],
            position["target1"],
            position.get("atr14"),
            position.get("base_ceiling"),
            0,
            int(position.get("score") or 0),
            position.get("note") or "",
        ),
    )
    await db.commit()
    return int(cursor.lastrowid)


async def save_paper_position(position: dict) -> None:
    db = await get_db()
    await db.execute(
        """
        UPDATE paper_positions SET
            stop_price = ?, sessions = ?, tp1_done = ?, booked_fraction = ?, realised = ?,
            last_price = ?, last_date = ?, closed_at = ?, exit_date = ?, exit_price = ?,
            exit_reason = ?
        WHERE id = ?
        """,
        (
            position["stop_price"],
            int(position["sessions"]),
            int(bool(position["tp1_done"])),
            position["booked_fraction"],
            position["realised"],
            position["last_price"],
            position["last_date"],
            position["closed_at"],
            position["exit_date"],
            position["exit_price"],
            position["exit_reason"],
            position["id"],
        ),
    )
    await db.commit()


_PAPER_COLUMNS = """
    id, symbol, opened_at, entry_date, entry_price, initial_stop, stop_price,
    target1, atr14, base_ceiling, sessions, tp1_done, booked_fraction, realised,
    last_price, last_date, closed_at, exit_date, exit_price, exit_reason, score, note
"""


def _paper_row(record) -> dict:
    item = dict(record)
    item["tp1_done"] = bool(item["tp1_done"])
    return item


async def open_paper_positions() -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        f"""
        SELECT {_PAPER_COLUMNS}
        FROM paper_positions
        WHERE closed_at IS NULL
        ORDER BY id
        """
    )
    return [_paper_row(record) for record in await cursor.fetchall()]


async def paper_for(symbol: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        f"""
        SELECT {_PAPER_COLUMNS}
        FROM paper_positions
        WHERE symbol = ?
        ORDER BY (closed_at IS NOT NULL), id DESC
        LIMIT 20
        """,
        (symbol,),
    )
    return [_paper_row(record) for record in await cursor.fetchall()]


async def recent_paper_positions(limit: int = 50) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        f"""
        SELECT {_PAPER_COLUMNS}
        FROM paper_positions
        ORDER BY (closed_at IS NOT NULL), id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [_paper_row(record) for record in await cursor.fetchall()]


async def mark_paper(position_id: int, mark_date: str, price: float, return_pct: float) -> None:
    db = await get_db()
    await db.execute(
        """
        INSERT INTO paper_marks (position_id, mark_date, price, return_pct)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(position_id, mark_date) DO UPDATE SET
            price = excluded.price,
            return_pct = excluded.return_pct
        """,
        (position_id, mark_date, price, return_pct),
    )
    await db.commit()
