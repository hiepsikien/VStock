from __future__ import annotations

from datetime import datetime, timezone

from app.store.db import get_db


class SymbolsRepository:
    async def get_all(self) -> list[dict]:
        db = await get_db()
        cursor = await db.execute(
            "SELECT symbol, name, exchange FROM symbols ORDER BY symbol"
        )
        rows = await cursor.fetchall()
        return [
            {"symbol": row["symbol"], "name": row["name"], "exchange": row["exchange"]}
            for row in rows
        ]

    async def upsert_many(self, symbols: list[dict]) -> int:
        if not symbols:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.executemany(
            """
            INSERT INTO symbols (symbol, name, exchange, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                exchange = excluded.exchange,
                updated_at = excluded.updated_at
            """,
            [
                (item["symbol"], item["name"], item["exchange"], now)
                for item in symbols
            ],
        )
        await db.commit()
        return len(symbols)

    async def search(self, query: str, limit: int = 30) -> list[dict]:
        q = query.strip().upper()
        if not q:
            return []

        db = await get_db()
        cursor = await db.execute(
            """
            SELECT symbol, name, exchange FROM symbols
            WHERE symbol LIKE ? OR UPPER(name) LIKE ?
            ORDER BY
              CASE WHEN symbol LIKE ? THEN 0 ELSE 1 END,
              symbol
            LIMIT ?
            """,
            (f"{q}%", f"%{q}%", f"{q}%", limit),
        )
        rows = await cursor.fetchall()
        return [
            {"symbol": row["symbol"], "name": row["name"], "exchange": row["exchange"]}
            for row in rows
        ]

    async def get(self, symbol: str) -> dict | None:
        sym = symbol.upper()
        db = await get_db()
        cursor = await db.execute(
            "SELECT symbol, name, exchange FROM symbols WHERE symbol = ?",
            (sym,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {"symbol": row["symbol"], "name": row["name"], "exchange": row["exchange"]}

    async def stats(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*), MAX(updated_at) FROM symbols")
        row = await cursor.fetchone()
        return {
            "count": int(row[0]) if row and row[0] is not None else 0,
            "latestUpdatedAt": row[1] if row else None,
        }
