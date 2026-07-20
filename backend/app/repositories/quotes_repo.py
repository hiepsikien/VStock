from __future__ import annotations

from datetime import datetime, timezone

from app.domain.quote import Quote
from app.store.db import get_db


class QuotesRepository:
    async def get_latest(self, symbols: list[str]) -> dict[str, dict]:
        cleaned = [s.strip().upper() for s in symbols if s.strip()]
        if not cleaned:
            return {}

        db = await get_db()
        placeholders = ",".join("?" for _ in cleaned)
        cursor = await db.execute(
            f"""
            SELECT symbol, price, change, change_percent, open, high, low, volume, ref, source, stale
            FROM quotes
            WHERE symbol IN ({placeholders})
            """,
            cleaned,
        )
        rows = await cursor.fetchall()

        result: dict[str, dict] = {}
        for row in rows:
            result[row["symbol"]] = {
                "symbol": row["symbol"],
                "price": row["price"],
                "change": row["change"],
                "changePercent": row["change_percent"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "volume": row["volume"],
                "ref": row["ref"],
            }
        return result

    async def upsert_many(self, quotes: list[Quote]) -> int:
        if not quotes:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.executemany(
            """
            INSERT INTO quotes (
                symbol, price, change, change_percent, open, high, low, volume, ref, source, stale, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                price = excluded.price,
                change = excluded.change,
                change_percent = excluded.change_percent,
                open = excluded.open,
                high = excluded.high,
                low = excluded.low,
                volume = excluded.volume,
                ref = excluded.ref,
                source = excluded.source,
                stale = excluded.stale,
                updated_at = excluded.updated_at
            """,
            [
                (
                    q.symbol,
                    q.price,
                    q.change,
                    q.changePercent,
                    q.open,
                    q.high,
                    q.low,
                    q.volume,
                    q.ref,
                    q.source,
                    1 if q.stale else 0,
                    now,
                )
                for q in quotes
            ],
        )
        await db.commit()
        return len(quotes)

    async def list_symbols(self) -> list[str]:
        db = await get_db()
        cursor = await db.execute("SELECT symbol FROM quotes ORDER BY symbol")
        rows = await cursor.fetchall()
        return [row["symbol"] for row in rows]

    async def stats(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*), MAX(updated_at) FROM quotes")
        row = await cursor.fetchone()
        return {
            "count": int(row[0]) if row and row[0] is not None else 0,
            "latestUpdatedAt": row[1] if row else None,
        }
