from __future__ import annotations

from datetime import datetime, timezone

from app.domain.news import NewsArticle
from app.store.db import get_db


def _row_to_dict(row) -> dict:
    symbols_raw = row["symbols"] or ""
    symbols = [s for s in symbols_raw.split(",") if s]
    return {
        "id": row["id"],
        "title": row["title"],
        "summary": row["summary"],
        "source": row["source"],
        "publishedAt": row["published_at"],
        "url": row["url"],
        "imageUrl": row["image_url"],
        "symbols": symbols,
        "category": row["category"],
    }


class NewsRepository:
    async def get_market_news(self, limit: int) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT id, title, summary, source, published_at, url, image_url, symbols, category
            FROM news
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]

    async def get_symbol_news(self, symbol: str, limit: int) -> list[dict]:
        sym = symbol.upper()
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT id, title, summary, source, published_at, url, image_url, symbols, category
            FROM news
            WHERE (',' || symbols || ',') LIKE ?
               OR UPPER(title) LIKE ?
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (f"%,{sym},%", f"%{sym}%", limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(row) for row in rows]

    async def upsert_many(self, articles: list[NewsArticle], *, provider: str = "") -> int:
        if not articles:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.executemany(
            """
            INSERT INTO news (
                id, title, summary, source, published_at, url, image_url,
                symbols, category, provider, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                summary = excluded.summary,
                source = excluded.source,
                published_at = excluded.published_at,
                url = excluded.url,
                image_url = excluded.image_url,
                symbols = excluded.symbols,
                category = excluded.category,
                provider = excluded.provider,
                updated_at = excluded.updated_at
            """,
            [
                (
                    article.id,
                    article.title,
                    article.summary,
                    article.source,
                    article.published_at,
                    article.url,
                    article.image_url,
                    ",".join(article.symbols),
                    article.category,
                    provider or article.source,
                    now,
                )
                for article in articles
            ],
        )
        await db.commit()
        return len(articles)

    async def prune(self, max_rows: int = 1000) -> int:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*) FROM news")
        row = await cursor.fetchone()
        total = int(row[0]) if row else 0
        if total <= max_rows:
            return 0

        excess = total - max_rows
        await db.execute(
            """
            DELETE FROM news
            WHERE id IN (
                SELECT id FROM news ORDER BY published_at ASC LIMIT ?
            )
            """,
            (excess,),
        )
        await db.commit()
        return excess

    async def stats(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*), MAX(updated_at), MAX(published_at) FROM news")
        row = await cursor.fetchone()
        return {
            "count": int(row[0]) if row and row[0] is not None else 0,
            "latestUpdatedAt": row[1] if row else None,
            "latestPublishedAt": row[2] if row else None,
        }

    async def count(self) -> int:
        stats = await self.stats()
        return int(stats["count"])
