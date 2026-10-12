from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from app import db, notify, paper
from app.breadth import BreadthGate, basket_on, breadth_by_day, breadth_states, gate_on
from app.config import BANKS, BREADTH_SERIES, BREADTH_STATE_SERIES, DEFAULT_UNIVERSE
from app.evaluate import compose
from app.flow import flow_gate
from app.industries import industry_of, load_industry_map
from app.industry_screen import build_open_map, credit_by_day, lead_bars_from
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
    supplement_historical_shares,
)
from app.macro import macro_state
from app.money import money_state
from app.pattern import assess_pattern, market_regime, session_bar
from app.pit_universe import baskets_from_bars

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
    # Bảng ngành là trạng thái toàn cục: phiên này có thể chạy ở tiến trình khác với web, nên
    # nó phải tự gắn bảng đã lưu trước khi chấm, không thì cùng một mã được ghi nhãn ngành khác.
    await load_industry_map()
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
        for code, bars in macro_series.items():
            series_name = "USDVND_MACRO" if code == "USDVND" else code
            await db.upsert_market_points(
                series_name, [(str(bar["trade_date"]), float(bar["close"])) for bar in bars]
            )
        for code, market_rows in market_series.items():
            await db.upsert_market_points(code, market_rows)
        semaphore = asyncio.Semaphore(4)
        backfilled = await db.shares_backfilled()
        newly_backfilled: list[str] = []

        async def _one(symbol: str) -> str | None:
            async with semaphore:
                try:
                    bars = await fetch_bars(client, symbol)
                    ratios = await fetch_ratios(client, symbol)
                    if symbol not in backfilled and await supplement_historical_shares(
                        client, symbol, ratios
                    ):
                        newly_backfilled.append(symbol)
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
                await db.upsert_flow(symbol, flow)
            return None

        failed = [symbol for symbol in await asyncio.gather(*[_one(symbol) for symbol in symbols]) if symbol]
        if newly_backfilled:
            await db.mark_shares_backfilled([s for s in newly_backfilled if s not in failed])
        try:
            breadth = await _breadth(client, set(symbols))
        except Exception as exc:
            logger.exception("Breadth failed")
            breadth = BreadthGate(None, f"Độ rộng chưa chấm: {exc}")

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
    # Only a name that has the bar of this session is scored. The backtest drops the names it
    # has no bar for (`session_bar`) and the paper ledger only ever steps a real bar, so a run
    # that scored a name on the bars and flow already in the store would put this session's date
    # on an older close — showing a base break of a session already gone as if it were today's.
    # A name whose bar for this session was stored by an earlier run today is scored as usual.
    day = as_of.isoformat()
    skipped: list[str] = []
    bars_by_symbol = {symbol: await db.bars(symbol) for symbol in DEFAULT_UNIVERSE}
    # Chạy cả khi cờ ngành tắt: verdict vẫn ghi trạng thái ngành để quan sát trước khi cho chặn.
    open_map = build_open_map(
        index_bars,
        bars_by_symbol,
        list(DEFAULT_UNIVERSE),
        lead_bars=lead_bars_from(await db.market_points()),
        credit_by_day=credit_by_day(
            {bank: await db.ratios(bank) for bank in BANKS},
            [str(bar["trade_date"]) for bar in index_bars],
        ),
    )
    for symbol in symbols:
        stock_slice = [bar for bar in (bars_by_symbol.get(symbol) or await db.bars(symbol)) if str(bar["trade_date"]) <= day]
        if session_bar(stock_slice, day) is None:
            skipped.append(symbol)
            continue
        points = await db.ratios(symbol)
        articles = await db.articles_for(symbol)
        industry = industry_of(symbol)
        industry_open = None if open_map is None else open_map.get((symbol, day))
        verdict = compose(
            symbol,
            as_of,
            points,
            articles,
            regime,
            assess_pattern(stock_slice, index_bars, exchanges.get(symbol)),
            require_clock=True,
            valuation=valuation_by_symbol.get(symbol),
            flow=flow_gate(await db.flow(symbol), stock_slice),
            macro=macro,
            market=money,
            industry_name=industry,
            industry_open=industry_open,
            breadth=breadth,
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
    summary = ", ".join(f"{status} {count}" for status, count in counts.items()) or (
        "không chấm được mã nào"
    )
    if failed:
        summary += ". Không tải được: " + ", ".join(failed)
    # A name that loaded fine but has no bar of this session is named apart from a dead feed, so
    # the operator can tell a broken fetch from a name that simply did not trade this session.
    # "Không tải được" above is about that fetch alone: a name whose bar for the session was
    # already stored by an earlier run today is still scored and still on the table.
    no_bar = [symbol for symbol in skipped if symbol not in set(failed)]
    if no_bar:
        summary += ". Chưa có nến phiên này: " + ", ".join(no_bar)
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


async def _breadth(client: httpx.AsyncClient, watched: set[str]) -> BreadthGate:
    """Độ rộng của phiên, dựng trên rổ 200 của năm đúng như báo cáo cổng độ rộng.

    Phần nạp chính chỉ đi qua danh sách theo dõi, nên mã của rổ ngoài danh sách được nạp nến ở
    đây. Mã nạp lỗi giữ nến cũ và tự rơi khỏi phép đếm khi nến cuối đã quá cũ. Trạng thái có độ
    trễ nên phụ thuộc cả chuỗi trước nó: chuỗi VN-Index đọc từ kho, đủ từ 2014 như báo cáo,
    chứ không phải phần vừa nạp từ 2021.
    """
    index_days = [str(bar["trade_date"]) for bar in await db.bars("VNINDEX")]
    if not index_days:
        return BreadthGate(None, "Độ rộng chưa chấm: chưa có nến VN-Index")
    day = index_days[-1]
    listings = await db.symbol_meta()
    bars = await db.all_bars()
    baskets = baskets_from_bars(index_days, bars, await db.ratio_series("OUTSTANDING_SHARES"), listings)
    current = basket_on(baskets, day)
    extra = [symbol for symbol in (current.universe if current else []) if symbol not in watched]
    semaphore = asyncio.Semaphore(4)

    async def _fetch(symbol: str) -> None:
        async with semaphore:
            try:
                fetched = await fetch_bars(client, symbol)
            except Exception as exc:
                logger.warning("Breadth bars failed for %s: %s", symbol, exc)
                return
        await db.replace_bars(symbol, fetched)

    await asyncio.gather(*[_fetch(symbol) for symbol in extra])
    for symbol in extra:
        bars[symbol] = await db.bars(symbol)
    boards = {symbol: str(meta.get("exchange") or "") for symbol, meta in listings.items()}
    points = breadth_by_day(index_days, bars, baskets, boards)
    gate = gate_on(day, points, breadth_states([(d, points[d].share) for d in index_days]))
    if gate.share is not None and gate.open is not None:
        await db.upsert_market_points(BREADTH_SERIES, [(day, gate.share)])
        await db.upsert_market_points(BREADTH_STATE_SERIES, [(day, 1.0 if gate.open else 0.0)])
    return gate
