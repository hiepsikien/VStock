"""Fill bars, statements, foreign flow and Yahoo macro back to RESEARCH_HISTORY_START.

Mặc định chỉ nạp danh sách trong `DEFAULT_UNIVERSE`. Chế độ `--market` nạp cả sàn HOSE và HNX
theo danh sách niêm yết của VNDirect: mã đã hủy niêm yết vẫn phải có nến, vì rổ theo thời điểm
cần biết chúng từng lớn thế nào chứ không chỉ mã còn sống hôm nay. Entrade không trả nến của mã
đã hủy niêm yết, nên những mã đó lấy từ bảng giá VNDirect.

Chế độ `--raw-tape` chỉ nạp cạnh thật của nến đã có — giá thật và giá trị khớp thật — vì rổ đo
vốn hóa bằng giá nhân số cổ phiếu của chính năm đó, mà giá trong kho đã điều chỉnh chia tách.

A symbol neither source has is skipped. Older sessions already stored are kept.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import httpx

from app import db
from app.config import (
    DEFAULT_UNIVERSE,
    MACRO_SYMBOLS,
    RESEARCH_HISTORY_START,
    UNIVERSE_EXCHANGES,
)
from app.industries import industry_rows
from app.ingest import (
    fetch_bars,
    fetch_foreign_flow,
    fetch_industry_groups,
    fetch_listings,
    fetch_macro,
    fetch_market_bars,
    fetch_ratios,
    fetch_raw_tape,
    listing_rows,
    supplement_historical_shares,
)

logger = logging.getLogger(__name__)


async def pull_listings(client: httpx.AsyncClient) -> tuple[int, int]:
    """Ghi danh sách niêm yết và bảng phân loại ICB của cả sàn vào kho."""
    listings = listing_rows(await fetch_listings(client, UNIVERSE_EXCHANGES))
    await db.replace_symbol_meta(listings)
    industries = industry_rows(await fetch_industry_groups(client))
    await db.replace_symbol_industry(industries)
    return len(listings), len(industries)


async def pull(
    symbols: list[str] | None = None, *, flow: bool = True, listings: bool = False
) -> dict[str, str]:
    await db.init_db()
    if symbols is None:
        symbols = list(DEFAULT_UNIVERSE)
    earliest: dict[str, str] = {}
    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if listings:
            names, groups = await pull_listings(client)
            print(f"niêm yết {names} mã, phân loại ngành {groups} mã", flush=True)
        index_bars = await fetch_bars(client, "VNINDEX", index=True, start=RESEARCH_HISTORY_START)
        await db.replace_bars("VNINDEX", index_bars)
        if index_bars:
            earliest["VNINDEX"] = index_bars[0]["trade_date"]
        macro = await fetch_macro(client, start=RESEARCH_HISTORY_START)
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

        async def _bars(symbol: str) -> list[dict]:
            """Nến của một mã. Entrade trước, vì phiên live cũng đọc nguồn đó."""
            try:
                bars = await fetch_bars(client, symbol, start=RESEARCH_HISTORY_START)
            except Exception as exc:
                logger.info("Entrade không có nến %s: %s", symbol, exc)
                bars = []
            if bars:
                return bars
            return await fetch_market_bars(client, symbol, RESEARCH_HISTORY_START)

        async def _one(symbol: str) -> None:
            async with semaphore:
                try:
                    bars = await _bars(symbol)
                except Exception as exc:
                    logger.warning("Bars failed for %s: %s", symbol, exc)
                    bars = []
                backfilled = False
                try:
                    ratios = await fetch_ratios(client, symbol)
                    backfilled = await supplement_historical_shares(client, symbol, ratios)
                except Exception as exc:
                    logger.warning("Ratios failed for %s: %s", symbol, exc)
                    ratios = {}
                try:
                    flow_points = await fetch_foreign_flow(client, symbol) if flow else {}
                except Exception as exc:
                    logger.warning("Flow failed for %s: %s", symbol, exc)
                    flow_points = {}
            async with write_lock:
                if bars:
                    await db.replace_bars(symbol, bars)
                    earliest[symbol] = bars[0]["trade_date"]
                if ratios:
                    await db.replace_ratios(symbol, ratios)
                    if backfilled:
                        await db.mark_shares_backfilled([symbol])
                if flow_points:
                    await db.upsert_flow(symbol, flow_points)
                print(symbol, earliest.get(symbol, "no bars"), flush=True)

        await asyncio.gather(*(_one(symbol) for symbol in symbols))
    await db.close_db()
    return earliest


async def listed_symbols() -> list[str]:
    """Mã của cả sàn đã lưu trong `symbol_meta`, kể cả mã đã hủy niêm yết."""
    await db.init_db()
    rows = await db.symbol_meta()
    await db.close_db()
    return sorted(rows)


async def refresh_listings() -> tuple[int, int]:
    """Nạp lại danh sách niêm yết và bảng phân loại ngành, không đụng tới nến."""
    await db.init_db()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        counts = await pull_listings(client)
    await db.close_db()
    return counts


async def pull_raw_tape(symbols: list[str] | None = None) -> dict[str, int]:
    """Nạp giá thật và giá trị khớp thật cho nến đã có của cả sàn.

    Rổ theo thời điểm nhân giá với số cổ phiếu của chính năm đó, nên giá đã điều chỉnh chia tách
    không dùng được; giá trị giao dịch cũng phải là giá trị khớp thật của nguồn. Mã nào kho đã có
    đủ giá thật thì lần chạy sau bỏ qua, còn mã còn thiếu phiên nào thì hỏi lại cả lịch sử.
    """
    await db.init_db()
    if symbols is None:
        rows = await db.symbol_meta()
        done = await db.raw_tape_backfilled()
        symbols = [symbol for symbol in sorted(rows) if symbol not in done]
    semaphore = asyncio.Semaphore(4)
    write_lock = asyncio.Lock()
    totals = {"symbols": 0, "sessions": 0, "unmatched": 0}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:

        async def _one(symbol: str) -> None:
            async with semaphore:
                try:
                    points = await fetch_raw_tape(client, symbol, RESEARCH_HISTORY_START)
                except Exception as exc:
                    logger.warning("Giá thật của %s lỗi: %s", symbol, exc)
                    points = []
            async with write_lock:
                if not points:
                    print(symbol, "không có giá thật", flush=True)
                    return
                matched, unmatched = await db.write_raw_tape(symbol, points)
                totals["symbols"] += 1
                totals["sessions"] += matched
                totals["unmatched"] += unmatched
                print(symbol, f"{matched}/{len(points)}", flush=True)

        await asyncio.gather(*(_one(symbol) for symbol in symbols))
    # Đánh dấu theo kho chứ không theo nguồn: nguồn có phiên mà kho không có nến là chuyện
    # thường, còn mã nào kho đã đủ giá thật thì lần sau không cần hỏi lại.
    gaps = await db.raw_tape_missing(RESEARCH_HISTORY_START)
    thin = {symbol for symbol, _sessions, _gap in gaps}
    covered = [symbol for symbol in symbols if symbol not in thin]
    if covered:
        await db.mark_raw_tape_backfilled(covered)
    totals["backfilled"] = len(covered)
    totals["missing_symbols"] = len(gaps)
    totals["missing_sessions"] = sum(gap for _symbol, _sessions, gap in gaps)
    await db.close_db()
    return totals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--listings",
        action="store_true",
        help="Nạp lại danh sách niêm yết và bảng phân loại ngành trước khi chạy.",
    )
    parser.add_argument(
        "--market",
        action="store_true",
        help="Nạp cả sàn HOSE và HNX theo danh sách niêm yết đã lưu, kể cả mã đã hủy niêm yết.",
    )
    parser.add_argument(
        "--raw-tape",
        action="store_true",
        help=(
            "Chỉ nạp giá thật và giá trị khớp thật cho nến đã có của cả sàn, phục vụ đo vốn hóa "
            "và thanh khoản của rổ. Không nạp nến, BCTC hay dòng tiền."
        ),
    )
    parser.add_argument("--symbols", help="Danh sách mã, cách nhau bằng dấu phẩy.")
    parser.add_argument(
        "--no-flow",
        action="store_true",
        help="Bỏ qua dòng tiền khối ngoại, chỉ lấy nến và số cổ phiếu.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    chosen = [item.strip().upper() for item in (args.symbols or "").split(",") if item.strip()]
    if args.raw_tape:
        if args.listings:
            names, groups = asyncio.run(refresh_listings())
            print(f"niêm yết {names} mã, phân loại ngành {groups} mã", flush=True)
        totals = asyncio.run(pull_raw_tape(chosen or None))
        print(
            f"cạnh thật {totals['symbols']} mã, {totals['sessions']} phiên, "
            f"{totals['unmatched']} phiên không có nến, đánh dấu xong {totals['backfilled']} mã; "
            f"còn thiếu {totals['missing_symbols']} mã ({totals['missing_sessions']} phiên)"
        )
        return
    if args.market:
        if chosen:
            symbols = chosen
        else:
            # Danh sách niêm yết phải nằm trong kho trước khi biết cần nạp nến cho mã nào.
            if args.listings:
                names, groups = asyncio.run(refresh_listings())
                print(f"niêm yết {names} mã, phân loại ngành {groups} mã", flush=True)
            symbols = asyncio.run(listed_symbols())
        print(f"Sàn: {len(symbols)} mã", flush=True)
    else:
        symbols = chosen or list(DEFAULT_UNIVERSE)
    earliest = asyncio.run(
        pull(symbols=symbols, flow=not args.no_flow, listings=args.listings and not args.market)
    )
    covered = [day for symbol, day in earliest.items() if symbol in set(symbols)]
    print(f"symbols {len(covered)} earliest {min(covered) if covered else 'none'}")
    for code in ("VNINDEX", "OIL", "USDVND_MACRO", "DXY", "SP500"):
        print(code, earliest.get(code, "missing"))


if __name__ == "__main__":
    main()
