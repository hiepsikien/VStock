from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from app import db, notify, paper
from app.evaluate import compose
from app.flow import flow_gate
from app.ingest import (
    fetch_bars,
    fetch_foreign_flow,
    fetch_macro,
    fetch_market,
    fetch_ratios,
    fetch_symbol_news,
    load_exchanges,
    load_market_articles,
    load_valuation,
)
from app.macro import macro_state
from app.money import money_state
from app.pattern import assess_pattern, market_regime

logger = logging.getLogger(__name__)
_lock = asyncio.Lock()


def busy() -> bool:
    return _lock.locked()


async def run_session() -> str:
    if _lock.locked():
        return "Đang chạy một phiên khác."
    async with _lock:
        run_id = await db.start_run()
        try:
            message = await _run()
        except Exception as exc:
            logger.exception("Research run failed")
            await db.finish_run(run_id, "error", str(exc))
            return f"Phiên lỗi: {exc}"
        await db.finish_run(run_id, "ok", message)
        return message


async def _run() -> str:
    symbols = await universe_symbols()
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        index_bars = await fetch_bars(client, "VNINDEX", index=True)
        await db.replace_bars("VNINDEX", index_bars)
        try:
            macro_series = await fetch_macro(client)
        except Exception as exc:
            logger.warning("Macro fetch failed: %s", exc)
            macro_series = {}
        # The money gate is stored one point per session, so it is fetched under the date of
        # the session being scored. A feed that is down stores nothing; the gate then reads
        # "Chưa chấm" instead of letting an old number stand in for today's.
        session_day = index_bars[-1]["trade_date"] if index_bars else None
        try:
            market_series = await fetch_market(client, session_day)
        except Exception as exc:
            logger.warning("Market fetch failed: %s", exc)
            market_series = {}
        for code, market_rows in market_series.items():
            await db.upsert_market_points(code, market_rows)
        semaphore = asyncio.Semaphore(4)

        async def _one(symbol: str) -> str | None:
            async with semaphore:
                try:
                    bars = await fetch_bars(client, symbol)
                    ratios = await fetch_ratios(client, symbol)
                    articles = await fetch_symbol_news(client, symbol)
                except Exception as exc:
                    logger.warning("Ingest failed for %s: %s", symbol, exc)
                    return symbol
                # The foreign tape is a separate resource, so a failure there must not
                # cost the symbol its bars, ratios and filings.
                try:
                    flow = await fetch_foreign_flow(client, symbol)
                except Exception as exc:
                    logger.warning("Foreign flow failed for %s: %s", symbol, exc)
                    flow = {}
            await db.replace_bars(symbol, bars)
            await db.replace_ratios(symbol, ratios)
            await db.upsert_articles(articles)
            if flow:
                await db.replace_flow(symbol, flow)
            return None

        failed = [symbol for symbol in await asyncio.gather(*[_one(symbol) for symbol in symbols]) if symbol]

    market_articles = load_market_articles()
    await db.upsert_articles(market_articles)
    removed = await db.prune_articles()
    if removed:
        logger.info("Dropped %d research filings older than the retention window", removed)
    exchanges = load_exchanges()

    index_bars = await db.bars("VNINDEX")
    if not index_bars:
        raise RuntimeError("Không tải được nến VN-Index")
    as_of = date.fromisoformat(index_bars[-1]["trade_date"])
    regime = market_regime(index_bars)
    macro = macro_state(macro_series)
    # Read the series back from the store rather than from the fetch, so live and backtest
    # scoring both see exactly the points that were kept for that day.
    money = money_state(await db.market_points(), as_of=as_of.isoformat())
    valuation_by_symbol = load_valuation()
    verdicts: list[dict] = []
    for symbol in symbols:
        stock_bars = await db.bars(symbol)
        points = await db.ratios(symbol)
        articles = await db.articles_for(symbol)
        verdict = compose(
            symbol,
            as_of,
            points,
            articles,
            regime,
            assess_pattern(stock_bars, index_bars, exchanges.get(symbol)),
            require_clock=True,
            valuation=valuation_by_symbol.get(symbol),
            flow=flow_gate(await db.flow(symbol), stock_bars),
            macro=macro,
            market=money,
        )
        verdicts.append(verdict.row())

    # Read the session that is in the store right now, before this run overwrites it.
    # Comparing against the one before that would stay silent when a status changed
    # yesterday and simply held today.
    previous = await db.latest_verdicts()
    await db.save_verdicts(verdicts)
    paper_messages = await paper.mark_positions(as_of.isoformat())

    counts: dict[str, int] = {}
    for item in verdicts:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    summary = ", ".join(f"{status} {count}" for status, count in counts.items())
    if failed:
        summary += ". Không tải được: " + ", ".join(failed)
    if paper_messages:
        summary += f". Vị thế giấy: {len(paper_messages)} lệnh đóng"

    body = notify.session_message(verdicts, previous, as_of.isoformat())
    if paper_messages:
        body = (body + "\n" if body else f"VStock research {as_of.isoformat()}\n") + "\n".join(
            paper_messages
        )
    if body:
        await notify.send(body)
    return f"Phiên {as_of.isoformat()}: {summary}"


async def universe_symbols() -> list[str]:
    return await db.universe()
