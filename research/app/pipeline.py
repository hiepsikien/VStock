from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from app import db
from app.evaluate import compose
from app.ingest import fetch_bars, fetch_ratios, fetch_symbol_news, load_market_articles
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
            await db.replace_bars(symbol, bars)
            await db.replace_ratios(symbol, ratios)
            await db.upsert_articles(articles)
            return None

        failed = [symbol for symbol in await asyncio.gather(*[_one(symbol) for symbol in symbols]) if symbol]

    market_articles = load_market_articles()
    await db.upsert_articles(market_articles)

    index_bars = await db.bars("VNINDEX")
    if not index_bars:
        raise RuntimeError("Không tải được nến VN-Index")
    as_of = date.fromisoformat(index_bars[-1]["trade_date"])
    regime = market_regime(index_bars)
    verdicts = []
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
            assess_pattern(stock_bars, index_bars),
            require_clock=True,
        )
        verdicts.append(
            {
                "as_of": verdict.as_of,
                "symbol": verdict.symbol,
                "status": verdict.status,
                "regime_open": verdict.regime_open,
                "regime_reason": verdict.regime_reason,
                "fa_label": verdict.fa_label,
                "fa_reason": verdict.fa_reason,
                "news_state": verdict.news_state,
                "news_reason": verdict.news_reason,
                "pattern_ready": verdict.pattern_ready,
                "pattern_reason": verdict.pattern_reason,
                "rs": verdict.rs,
                "priority": verdict.priority,
                "stop_price": verdict.stop_price,
                "summary": verdict.summary,
                "metrics": verdict.metrics,
            }
        )
    await db.save_verdicts(verdicts)
    counts: dict[str, int] = {}
    for item in verdicts:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    summary = ", ".join(f"{status} {count}" for status, count in counts.items())
    if failed:
        summary += ". Không tải được: " + ", ".join(failed)
    return f"Phiên {as_of.isoformat()}: {summary}"


async def universe_symbols() -> list[str]:
    return await db.universe()
