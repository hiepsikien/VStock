from __future__ import annotations

import json
from datetime import datetime, timezone

from app.store.db import get_db


class IncomeRepository:
    async def get(self, symbol: str) -> dict | None:
        sym = symbol.upper()
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT symbol, revenue_label, latest_annual, last_quarters, updated_at
            FROM income_statements
            WHERE symbol = ?
            """,
            (sym,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        latest = json.loads(row["latest_annual"]) if row["latest_annual"] else None
        quarters = json.loads(row["last_quarters"]) if row["last_quarters"] else []
        return {
            "symbol": row["symbol"],
            "revenueLabel": row["revenue_label"] or "Doanh thu thuần",
            "latestAnnual": latest,
            "lastQuarters": quarters if isinstance(quarters, list) else [],
            "updatedAt": row["updated_at"],
        }

    async def upsert(self, payload: dict) -> None:
        sym = str(payload["symbol"]).upper()
        now = datetime.now(timezone.utc).isoformat()
        latest = payload.get("latestAnnual") or payload.get("latest_annual")
        quarters = payload.get("lastQuarters") or payload.get("last_quarters") or []
        label = payload.get("revenueLabel") or payload.get("revenue_label") or "Doanh thu thuần"
        db = await get_db()
        await db.execute(
            """
            INSERT INTO income_statements (
                symbol, revenue_label, latest_annual, last_quarters, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                revenue_label = excluded.revenue_label,
                latest_annual = excluded.latest_annual,
                last_quarters = excluded.last_quarters,
                updated_at = excluded.updated_at
            """,
            (
                sym,
                label,
                json.dumps(latest, ensure_ascii=False) if latest else None,
                json.dumps(quarters, ensure_ascii=False),
                now,
            ),
        )
        await db.commit()
