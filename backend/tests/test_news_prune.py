from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_filing_prune_keeps_cutoff_day() -> None:
    asyncio.run(_run())


async def _run() -> None:
    from app.repositories.news_repo import NewsRepository
    from app.store import db as store

    await store.close_db()
    previous = os.environ.get("VSTOCK_DB_PATH")
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    path = handle.name
    os.environ["VSTOCK_DB_PATH"] = path
    try:
        await store.init_db()
        window = 10
        cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).date()
        rows = [
            ("keep-day", cutoff.isoformat(), "disclosure"),
            ("keep-stamp", cutoff.isoformat() + "T08:00:00", "company_news"),
            ("drop-day", (cutoff - timedelta(days=1)).isoformat(), "disclosure"),
            ("drop-stamp", (cutoff - timedelta(days=1)).isoformat() + "T23:00:00", "company_news"),
            ("commentary", (cutoff - timedelta(days=30)).isoformat(), "stock_news"),
        ]
        connection = await store.get_db()
        await connection.executemany(
            """
            INSERT INTO news (
                id, title, source, published_at, category, updated_at
            ) VALUES (?, 'Tin', 'test', ?, ?, '2026-10-10T00:00:00')
            """,
            rows,
        )
        await connection.commit()
        removed = await NewsRepository().prune(max_rows=1000, filing_days=window)
        assert removed == 2
        cursor = await connection.execute("SELECT id FROM news ORDER BY id")
        left = [row[0] for row in await cursor.fetchall()]
        assert left == ["commentary", "keep-day", "keep-stamp"]
    finally:
        await store.close_db()
        if previous is None:
            os.environ.pop("VSTOCK_DB_PATH", None)
        else:
            os.environ["VSTOCK_DB_PATH"] = previous
        for suffix in ("", "-wal", "-shm"):
            Path(path + suffix).unlink(missing_ok=True)
