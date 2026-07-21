from __future__ import annotations

from datetime import datetime, timezone

from app.domain.news import NewsArticle
from app.ingestion.normalizers.commodity_news import COMMODITY_TITLE_HINTS
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
    MARKET_CATEGORIES = (
        "stock_news",
        "macro_news",
        "company_news",
        "commodity_news",
        "real_estate_news",
        "disclosure",
    )

    async def get_market_news(self, limit: int, category: str | None = None) -> list[dict]:
        db = await get_db()
        if category == "commodity_news":
            # Include gold/oil/agri headlines that may still sit in other groups in DB.
            clauses = ["category = ?"]
            params: list[object] = ["commodity_news"]
            for hint in COMMODITY_TITLE_HINTS:
                clauses.append("LOWER(title) LIKE ?")
                params.append(f"%{hint}%")
            params.append(limit)
            cursor = await db.execute(
                f"""
                SELECT id, title, summary, source, published_at, url, image_url, symbols, category
                FROM news
                WHERE {" OR ".join(clauses)}
                ORDER BY published_at DESC
                LIMIT ?
                """,
                params,
            )
            rows = await cursor.fetchall()
            items = [_row_to_dict(row) for row in rows]
            for item in items:
                item["category"] = "commodity_news"
            # Dedupe by id while preserving order
            seen: set[str] = set()
            deduped: list[dict] = []
            for item in items:
                if item["id"] in seen:
                    continue
                seen.add(item["id"])
                deduped.append(item)
            return deduped

        if category:
            cursor = await db.execute(
                """
                SELECT id, title, summary, source, published_at, url, image_url, symbols, category
                FROM news
                WHERE category = ?
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (category, limit),
            )
            rows = await cursor.fetchall()
            return [_row_to_dict(row) for row in rows]

        # Stratify so quieter categories (BĐS, hàng hóa) still appear in "all".
        per_cat = max(limit // len(self.MARKET_CATEGORIES), 2)
        selected: list[dict] = []
        seen_ids: set[str] = set()
        for cat in self.MARKET_CATEGORIES:
            cat_items = await self.get_market_news(per_cat, category=cat)
            for item in cat_items:
                if item["id"] in seen_ids:
                    continue
                selected.append(item)
                seen_ids.add(item["id"])

        if len(selected) < limit:
            cursor = await db.execute(
                """
                SELECT id, title, summary, source, published_at, url, image_url, symbols, category
                FROM news
                ORDER BY published_at DESC
                LIMIT ?
                """,
                (limit * 2,),
            )
            for row in await cursor.fetchall():
                item = _row_to_dict(row)
                if item["id"] in seen_ids:
                    continue
                selected.append(item)
                seen_ids.add(item["id"])
                if len(selected) >= limit:
                    break

        selected.sort(key=lambda item: item["publishedAt"], reverse=True)
        return selected[:limit]

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
