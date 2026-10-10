from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import db


class PruneArticlesTest(unittest.TestCase):
    def test_retention_env_clamps_and_falls_back(self) -> None:
        previous = os.environ.get("ARTICLE_RETENTION_DAYS")
        try:
            os.environ["ARTICLE_RETENTION_DAYS"] = "5"
            self.assertEqual(db.article_retention_days(), 30)
            os.environ["ARTICLE_RETENTION_DAYS"] = "abc"
            self.assertEqual(db.article_retention_days(), 1460)
            os.environ["ARTICLE_RETENTION_DAYS"] = "2000"
            self.assertEqual(db.article_retention_days(), 2000)
        finally:
            if previous is None:
                os.environ.pop("ARTICLE_RETENTION_DAYS", None)
            else:
                os.environ["ARTICLE_RETENTION_DAYS"] = previous

    def test_keeps_cutoff_day_and_drops_the_day_before(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            window = 10
            cutoff = (datetime.now(timezone.utc) - timedelta(days=window)).date()
            rows = [
                ("keep-day", cutoff.isoformat()),
                ("keep-stamp", cutoff.isoformat() + "T08:00:00"),
                ("drop-day", (cutoff - timedelta(days=1)).isoformat()),
                ("drop-stamp", (cutoff - timedelta(days=1)).isoformat() + "T23:00:00"),
            ]
            connection = await db.get_db()
            await connection.executemany(
                """
                INSERT INTO articles (id, title, published_at, symbols)
                VALUES (?, 'Công bố', ?, 'FPT')
                """,
                rows,
            )
            await connection.commit()
            removed = await db.prune_articles(window)
            self.assertEqual(removed, 2)
            cursor = await connection.execute("SELECT id FROM articles ORDER BY id")
            left = [row[0] for row in await cursor.fetchall()]
            self.assertEqual(left, ["keep-day", "keep-stamp"])
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)
