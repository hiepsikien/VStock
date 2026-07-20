from __future__ import annotations

from datetime import datetime, timezone

from app.store.db import get_db


class IndicesRepository:
    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT symbol, name, exchange, price, change, change_percent
            FROM indices
            ORDER BY symbol
            """
        )
        rows = await cursor.fetchall()
        return [
            {
                "symbol": row["symbol"],
                "name": row["name"],
                "exchange": row["exchange"],
                "price": row["price"],
                "change": row["change"],
                "changePercent": row["change_percent"],
            }
            for row in rows
        ]

    async def upsert_many(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.executemany(
            """
            INSERT INTO indices (
                symbol, name, exchange, price, change, change_percent, source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                exchange = excluded.exchange,
                price = excluded.price,
                change = excluded.change,
                change_percent = excluded.change_percent,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            [
                (
                    row["symbol"],
                    row["name"],
                    row["exchange"],
                    row["price"],
                    row["change"],
                    row["changePercent"],
                    row.get("source", "entrade"),
                    now,
                )
                for row in rows
            ],
        )
        await db.commit()
        return len(rows)

    async def stats(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*), MAX(updated_at) FROM indices")
        row = await cursor.fetchone()
        return {
            "count": int(row[0]) if row and row[0] is not None else 0,
            "latestUpdatedAt": row[1] if row else None,
        }
