"""Fill bars, statements, foreign flow and Yahoo macro back to 2021.

A symbol the source does not have is skipped. Older sessions already stored are kept.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app import db
from app.config import DEFAULT_UNIVERSE, MACRO_SYMBOLS
from app.ingest import fetch_bars, fetch_foreign_flow, fetch_macro, fetch_ratios

logger = logging.getLogger(__name__)


async def pull() -> dict[str, str]:
    await db.init_db()
    earliest: dict[str, str] = {}
    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        index_bars = await fetch_bars(client, "VNINDEX", index=True)
        await db.replace_bars("VNINDEX", index_bars)
        if index_bars:
            earliest["VNINDEX"] = index_bars[0]["trade_date"]
        macro = await fetch_macro(client)
        for code, _symbol, _label in MACRO_SYMBOLS:
            bars = macro.get(code) or []
            series_name = "USDVND_MACRO" if code == "USDVND" else code
            await db.upsert_market_points(
                series_name, [(str(bar["trade_date"]), float(bar["close"])) for bar in bars]
            )
            if bars:
                earliest[series_name] = bars[0]["trade_date"]
        semaphore = asyncio.Semaphore(4)
        write_lock = asyncio.Lock()

        async def _one(symbol: str) -> None:
            async with semaphore:
                try:
                    bars = await fetch_bars(client, symbol)
                except Exception as exc:
                    logger.warning("Bars failed for %s: %s", symbol, exc)
                    bars = []
                try:
                    ratios = await fetch_ratios(client, symbol)
                except Exception as exc:
                    logger.warning("Ratios failed for %s: %s", symbol, exc)
                    ratios = {}
                try:
                    flow = await fetch_foreign_flow(client, symbol)
                except Exception as exc:
                    logger.warning("Flow failed for %s: %s", symbol, exc)
                    flow = {}
            async with write_lock:
                if bars:
                    await db.replace_bars(symbol, bars)
                    earliest[symbol] = bars[0]["trade_date"]
                if ratios:
                    await db.replace_ratios(symbol, ratios)
                if flow:
                    await db.upsert_flow(symbol, flow)
                print(symbol, earliest.get(symbol, "no bars"), flush=True)

        await asyncio.gather(*(_one(symbol) for symbol in DEFAULT_UNIVERSE))
    await db.close_db()
    return earliest


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    earliest = asyncio.run(pull())
    covered = [day for symbol, day in earliest.items() if symbol in DEFAULT_UNIVERSE]
    print(f"symbols {len(covered)} earliest {min(covered) if covered else 'none'}")
    for code in ("VNINDEX", "OIL", "USDVND_MACRO", "DXY", "SP500"):
        print(code, earliest.get(code, "missing"))


if __name__ == "__main__":
    main()
