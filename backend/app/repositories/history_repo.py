from __future__ import annotations

import json
from datetime import datetime, timezone

from app.domain.history import ChartRange
from app.store.db import get_db


class HistoryRepository:
    async def get(self, symbol: str, chart_range: ChartRange) -> list[float]:
        sym = symbol.upper()
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT prices FROM history
            WHERE symbol = ? AND range_key = ?
            """,
            (sym, chart_range),
        )
        row = await cursor.fetchone()
        if not row:
            return []

        try:
            parsed = json.loads(row["prices"] or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [float(p) for p in parsed if p]

    async def upsert(self, symbol: str, chart_range: ChartRange, prices: list[float]) -> None:
        if not prices:
            return

        sym = symbol.upper()
        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.execute(
            """
            INSERT INTO history (symbol, range_key, prices, source, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol, range_key) DO UPDATE SET
                prices = excluded.prices,
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (sym, chart_range, json.dumps(prices), "entrade", now),
        )
        await db.commit()

    async def upsert_many(self, rows: list[tuple[str, ChartRange, list[float]]]) -> int:
        count = 0
        for symbol, chart_range, prices in rows:
            if prices:
                await self.upsert(symbol, chart_range, prices)
                count += 1
        return count

    async def stats(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*), MAX(updated_at) FROM history")
        row = await cursor.fetchone()
        return {
            "count": int(row[0]) if row and row[0] is not None else 0,
            "latestUpdatedAt": row[1] if row else None,
        }
