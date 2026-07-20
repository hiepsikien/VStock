from __future__ import annotations

from datetime import datetime, timezone

from app.store.db import get_db


class FundamentalsRepository:
    async def get(self, symbol: str) -> dict | None:
        sym = symbol.upper()
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT symbol, name, exchange, market_cap, pe, listed_shares
            FROM fundamentals
            WHERE symbol = ?
            """,
            (sym,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return {
            "name": row["name"],
            "exchange": row["exchange"],
            "marketCap": row["market_cap"],
            "pe": row["pe"],
            "listedShares": row["listed_shares"],
        }

    async def upsert(self, profile: dict) -> None:
        sym = str(profile["symbol"]).upper()
        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.execute(
            """
            INSERT INTO fundamentals (
                symbol, name, exchange, market_cap, pe, listed_shares, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                exchange = excluded.exchange,
                market_cap = excluded.market_cap,
                pe = excluded.pe,
                listed_shares = excluded.listed_shares,
                updated_at = excluded.updated_at
            """,
            (
                sym,
                profile["name"],
                profile["exchange"],
                profile.get("market_cap") or profile.get("marketCap") or "—",
                profile.get("pe"),
                int(profile.get("listed_shares") or profile.get("listedShares") or 0),
                now,
            ),
        )
        await db.commit()

    async def stats(self) -> dict:
        db = await get_db()
        cursor = await db.execute("SELECT COUNT(*), MAX(updated_at) FROM fundamentals")
        row = await cursor.fetchone()
        return {
            "count": int(row[0]) if row and row[0] is not None else 0,
            "latestUpdatedAt": row[1] if row else None,
        }
