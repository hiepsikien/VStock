from __future__ import annotations

from datetime import datetime, timezone

from app.store.db import get_db


class FundamentalsRepository:
    async def get(self, symbol: str) -> dict | None:
        sym = symbol.upper()
        db = await get_db()
        cursor = await db.execute(
            """
            SELECT symbol, name, exchange, market_cap, pe, eps, pb, roe, roa,
                   dividend_yield, listed_shares, updated_at
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
            "eps": row["eps"],
            "pb": row["pb"],
            "roe": row["roe"],
            "roa": row["roa"],
            "dividendYield": row["dividend_yield"],
            "listedShares": row["listed_shares"],
            "updatedAt": row["updated_at"],
        }

    async def upsert(self, profile: dict) -> None:
        sym = str(profile["symbol"]).upper()
        now = datetime.now(timezone.utc).isoformat()
        db = await get_db()
        await db.execute(
            """
            INSERT INTO fundamentals (
                symbol, name, exchange, market_cap, pe, eps, pb, roe, roa,
                dividend_yield, listed_shares, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                name = excluded.name,
                exchange = excluded.exchange,
                market_cap = excluded.market_cap,
                pe = excluded.pe,
                eps = excluded.eps,
                pb = excluded.pb,
                roe = excluded.roe,
                roa = excluded.roa,
                dividend_yield = excluded.dividend_yield,
                listed_shares = excluded.listed_shares,
                updated_at = excluded.updated_at
            """,
            (
                sym,
                profile["name"],
                profile["exchange"],
                profile.get("market_cap") or profile.get("marketCap") or "—",
                profile.get("pe"),
                profile.get("eps"),
                profile.get("pb"),
                profile.get("roe"),
                profile.get("roa"),
                profile.get("dividend_yield")
                if "dividend_yield" in profile
                else profile.get("dividendYield"),
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
