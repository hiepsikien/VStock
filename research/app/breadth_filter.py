"""Độ rộng làm bộ lọc tín hiệu phá nền: đếm và đo theo luật đã chốt.

Luật nằm ở docs/breadth-signal-filter.md và các hằng số `BREADTH_FILTER_*`, chốt ở tag
`prereg/breadth-filter` và các sửa đổi `prereg/breadth-filter-amend1`, `-amend2`. Mẫu là các tín
hiệu phá nền của rổ 100 (`find_signals`) phát ra từ `BREADTH_FILTER_START`, ở phiên VN-Index trên
MA200. Nhóm giữ là tín hiệu lúc trạng thái độ rộng
đã lưu là mở, nhóm bỏ là lúc đóng. Lợi nhuận đo từ giá đóng cửa phiên sau phiên tín hiệu.

Chạy từ thư mục research:

    PYTHONPATH=. python3 -m app.breadth_filter            # chỉ in số đếm, không có lợi nhuận
    PYTHONPATH=. python3 -m app.breadth_filter --measure  # đo một lần, khi đã đủ điều kiện

Chế độ đếm không in số nào suy ra được kết quả. Chế độ đo chỉ chạy khi đã đủ mẫu và đủ thời gian,
hoặc khi đã quá hạn chót, và không ghi đè một báo cáo đã có. Trước hạn chót, nó dừng mà không ghi
báo cáo khi còn tín hiệu không xác nhận được nến.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import statistics
from bisect import bisect_right
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from app.config import (
    BREADTH_FILTER_HORIZON,
    BREADTH_FILTER_MAX_MONTHS,
    BREADTH_FILTER_MIN_EDGE,
    BREADTH_FILTER_MIN_MONTHS,
    BREADTH_FILTER_MIN_SIGNALS,
    BREADTH_FILTER_START,
    BREADTH_MAX_STALE_SESSIONS,
    BREADTH_STATE_SERIES,
    ROUND_TRIP_COST,
)
from app.pattern import market_regime
from app.pit_universe import Basket

logger = logging.getLogger(__name__)

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "breadth_filter.md"
KEEP = "giữ"
DROP = "bỏ"


@dataclass(frozen=True)
class FilterSignal:
    symbol: str
    day: str
    # KEEP, DROP, hoặc None khi phiên tín hiệu không có trạng thái độ rộng đã lưu.
    group: str | None
    # Đã qua đủ phiên sau phiên tín hiệu cộng `horizon` phiên của VN-Index.
    matured: bool
    forward: float | None


@dataclass(frozen=True)
class Counts:
    start: str
    last_day: str
    months: int
    keep_total: int
    keep_matured: int
    drop_total: int
    drop_matured: int
    missing_state: int
    sessions: int
    sessions_without_state: int

    @property
    def ready(self) -> bool:
        return (
            self.months >= BREADTH_FILTER_MIN_MONTHS
            and self.keep_matured >= BREADTH_FILTER_MIN_SIGNALS
            and self.drop_matured >= BREADTH_FILTER_MIN_SIGNALS
        )

    @property
    def expired(self) -> bool:
        return self.months >= BREADTH_FILTER_MAX_MONTHS


@dataclass(frozen=True)
class Verdict:
    outcome: str
    keep: list[float]
    drop: list[float]
    edge: float | None
    missing_price: int


def months_between(start: str, end: str) -> int:
    """Số tháng tròn từ `start` tới `end`."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    months = (last.year - first.year) * 12 + (last.month - first.month)
    if last.day < first.day:
        months -= 1
    return max(months, 0)


def stored_states(points: list[tuple[str, float]]) -> dict[str, bool]:
    """Trạng thái độ rộng phiên chạy thật đã lưu: 1 là mở, 0 là đóng. Giá trị ghi sau cùng thắng."""
    return {str(day): float(value) >= 0.5 for day, value in points}


def ma200_from(index: list[dict], since: str) -> dict[str, bool | None]:
    """MA200 của VN-Index cho từng phiên từ `since`, đúng như cột MA200 của báo cáo cổng độ rộng."""
    out: dict[str, bool | None] = {}
    for position, bar in enumerate(index):
        day = str(bar["trade_date"])
        if day >= since:
            out[day] = market_regime(index[: position + 1]).open
    return out


def next_session_return(
    series: list[dict], index_days: list[str], position: int, horizon: int
) -> float | None:
    """Lợi nhuận từ giá đóng cửa phiên sau phiên tín hiệu tới `horizon` phiên VN-Index sau đó.

    Giá lấy là giá đóng cửa cuối cùng không muộn hơn mỗi mốc, nên mã ngừng giao dịch giữ giá cuối,
    như `find_signals`.
    """
    if position + 1 + horizon >= len(index_days):
        return None
    days = [str(bar["trade_date"]) for bar in series]
    entry = bisect_right(days, index_days[position + 1]) - 1
    exit_ = bisect_right(days, index_days[position + 1 + horizon]) - 1
    if entry < 0 or exit_ < 0:
        return None
    base = float(series[entry]["close"])
    if base <= 0:
        return None
    return float(series[exit_]["close"]) / base - 1


def classify(
    raw: list[dict],
    index_days: list[str],
    bars: dict[str, list[dict]],
    ma200: dict[str, bool | None],
    states: dict[str, bool],
    *,
    start: str = BREADTH_FILTER_START,
    horizon: int = BREADTH_FILTER_HORIZON,
) -> list[FilterSignal]:
    """Tín hiệu thuộc mẫu đo: từ `start`, phiên MA200 mở, gắn nhóm theo trạng thái đã lưu."""
    position_of = {day: position for position, day in enumerate(index_days)}
    out: list[FilterSignal] = []
    for signal in raw:
        day = str(signal["day"])
        position = position_of.get(day)
        if day < start or position is None or ma200.get(day) is not True:
            continue
        state = states.get(day)
        group = None if state is None else (KEEP if state else DROP)
        matured = position + 1 + horizon < len(index_days)
        forward = (
            next_session_return(bars.get(signal["symbol"]) or [], index_days, position, horizon)
            if matured
            else None
        )
        out.append(FilterSignal(str(signal["symbol"]), day, group, matured, forward))
    return out


def count(
    signals: list[FilterSignal],
    index_days: list[str],
    states: dict[str, bool],
    *,
    start: str = BREADTH_FILTER_START,
) -> Counts:
    sessions = [day for day in index_days if day >= start]
    last_day = index_days[-1] if index_days else start
    return Counts(
        start=start,
        last_day=last_day,
        months=months_between(start, last_day) if last_day >= start else 0,
        keep_total=sum(1 for s in signals if s.group == KEEP),
        keep_matured=sum(1 for s in signals if s.group == KEEP and s.matured),
        drop_total=sum(1 for s in signals if s.group == DROP),
        drop_matured=sum(1 for s in signals if s.group == DROP and s.matured),
        missing_state=sum(1 for s in signals if s.group is None),
        sessions=len(sessions),
        sessions_without_state=sum(1 for day in sessions if day not in states),
    )


def judge(signals: list[FilterSignal], counts: Counts) -> Verdict:
    """Kết luận theo luật đã chốt. Chưa đủ điều kiện mà chưa quá hạn thì không được đo."""
    if not counts.ready:
        if not counts.expired:
            raise ValueError("Chưa đủ điều kiện đo: chưa đủ mẫu hoặc chưa đủ 12 tháng.")
        return Verdict("không đủ mẫu", [], [], None, 0)
    keep = [s.forward for s in signals if s.group == KEEP and s.matured and s.forward is not None]
    drop = [s.forward for s in signals if s.group == DROP and s.matured and s.forward is not None]
    missing_price = sum(
        1 for s in signals if s.group is not None and s.matured and s.forward is None
    )
    if len(keep) < BREADTH_FILTER_MIN_SIGNALS or len(drop) < BREADTH_FILTER_MIN_SIGNALS:
        return Verdict("không đủ mẫu", keep, drop, None, missing_price)
    edge = statistics.mean(keep) - statistics.mean(drop)
    outcome = "qua" if edge >= BREADTH_FILTER_MIN_EDGE else "không qua"
    return Verdict(outcome, keep, drop, edge, missing_price)


def counts_text(counts: Counts) -> str:
    if counts.ready:
        status = "đã đủ điều kiện đo"
    elif counts.expired:
        status = "đã quá hạn chót, đo sẽ cho kết luận \"không đủ mẫu\""
    else:
        status = "chưa đủ điều kiện đo"
    if counts.last_day < counts.start:
        span = f"Từ {counts.start}: chưa có phiên nào, phiên mới nhất trong kho là {counts.last_day}."
    else:
        span = f"Từ {counts.start} tới {counts.last_day}: {counts.months} tháng, {counts.sessions} phiên."
    return "\n".join(
        [
            "Bộ lọc độ rộng — chỉ số đếm, không có lợi nhuận",
            span,
            f"Nhóm giữ (độ rộng mở): {counts.keep_total} tín hiệu, {counts.keep_matured} đã đủ "
            f"{BREADTH_FILTER_HORIZON} phiên.",
            f"Nhóm bỏ (độ rộng đóng): {counts.drop_total} tín hiệu, {counts.drop_matured} đã đủ "
            f"{BREADTH_FILTER_HORIZON} phiên.",
            f"Tín hiệu bị loại vì phiên không có trạng thái độ rộng đã lưu: {counts.missing_state}.",
            f"Phiên không có trạng thái độ rộng đã lưu: {counts.sessions_without_state}/{counts.sessions}.",
            f"Cần {BREADTH_FILTER_MIN_SIGNALS} tín hiệu đã đủ phiên mỗi nhóm và {BREADTH_FILTER_MIN_MONTHS} "
            f"tháng; hạn chót {BREADTH_FILTER_MAX_MONTHS} tháng. Trạng thái: {status}.",
        ]
    )


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:+.1f}%"


def report_text(
    signals: list[FilterSignal],
    counts: Counts,
    verdict: Verdict,
    *,
    code: str = "không rõ",
    unpriced: list[FilterSignal] | None = None,
) -> str:
    lines = [
        "# Bộ lọc độ rộng — kết quả đo",
        "",
        "Luật chốt ở `docs/breadth-signal-filter.md`, tag `prereg/breadth-filter` và các sửa đổi "
        "`prereg/breadth-filter-amend1`, `prereg/breadth-filter-amend2`. Đo một lần.",
        f"Code chạy phép đo: `{code}`.",
        "",
        f"## Kết luận: {verdict.outcome}",
        "",
        counts_text(counts),
        "",
    ]
    if verdict.edge is not None:
        lines.extend(
            [
                "| Nhóm | Tín hiệu đã đủ phiên | TB 40 phiên | Trung vị 40 | Thắng 40 |",
                "|---|---|---|---|---|",
            ]
        )
        for name, values in (("Giữ (độ rộng mở)", verdict.keep), ("Bỏ (độ rộng đóng)", verdict.drop)):
            wins = sum(1 for value in values if value > 0) / len(values)
            lines.append(
                f"| {name} | {len(values)} | {_pct(statistics.mean(values))} | "
                f"{_pct(statistics.median(values))} | {wins * 100:.1f}% |"
            )
        drop_mean = statistics.mean(verdict.drop)
        lines.extend(
            [
                "",
                f"Cách biệt nhóm giữ trừ nhóm bỏ: {_pct(verdict.edge)}, ngưỡng "
                f"{BREADTH_FILTER_MIN_EDGE * 100:.0f} điểm %.",
                f"Số báo cáo, không thuộc luật qua cửa: nhóm bỏ lãi TB {_pct(drop_mean)}, "
                f"{'thấp hơn' if drop_mean < ROUND_TRIP_COST else 'không thấp hơn'} phí cả vòng "
                f"{ROUND_TRIP_COST * 100:.1f}%.",
            ]
        )
    lines.append(f"Tín hiệu đã đủ phiên nhưng thiếu giá trong kho: {verdict.missing_price}.")
    if unpriced:
        lines.append(
            "Trong đó tính là thiếu giá vì đã quá hạn chót mà vẫn không xác nhận được nến: "
            + ", ".join(f"{s.symbol} {s.day}" for s in unpriced)
            + "."
        )
    return "\n".join(lines) + "\n"


def _trade_symbols(baskets: dict[int, Basket], since: str) -> list[str]:
    first_year = int(since[:4])
    return sorted({name for year, basket in baskets.items() if year >= first_year for name in basket.trade})


def unconfirmed(
    signals: list[FilterSignal],
    bars: dict[str, list[dict]],
    index_days: list[str],
    listings: dict[str, dict],
    refreshed: set[str],
    *,
    horizon: int = BREADTH_FILTER_HORIZON,
) -> list[FilterSignal]:
    """Tín hiệu đã đủ phiên trong mẫu mà không xác nhận được nến dùng để tính lợi nhuận.

    Nến của một tín hiệu được coi là đủ khi một trong ba điều đúng: mã vừa nạp lại thành công,
    nến lưu trong kho đã tới phiên bán, hoặc mã đã hủy niêm yết trước phiên bán và nến lưu tới
    sát ngày hủy (cách không quá `BREADTH_MAX_STALE_SESSIONS` phiên). Còn lại là nến có thể đã
    cũ: mã nạp lỗi, hoặc mã vào mẫu mà không nằm trong danh sách nạp lại.
    """
    position_of = {day: position for position, day in enumerate(index_days)}
    out: list[FilterSignal] = []
    for signal in signals:
        if signal.group is None or not signal.matured or signal.symbol in refreshed:
            continue
        exit_day = index_days[position_of[signal.day] + 1 + horizon]
        series = bars.get(signal.symbol) or []
        last = str(series[-1]["trade_date"]) if series else ""
        if last >= exit_day:
            continue
        delisted = (listings.get(signal.symbol) or {}).get("delisted_date")
        if delisted and delisted <= exit_day and last:
            gap = bisect_right(index_days, delisted) - bisect_right(index_days, last)
            if gap <= BREADTH_MAX_STALE_SESSIONS:
                continue
        out.append(signal)
    return out


def settle_unconfirmed(
    signals: list[FilterSignal], unsure: list[FilterSignal], counts: Counts
) -> list[FilterSignal]:
    """Trước hạn chót thì dừng, không ghi báo cáo. Tới hạn chót thì tính các tín hiệu đó là thiếu giá."""
    if not unsure:
        return signals
    if not counts.expired:
        raise SystemExit(
            "Không xác nhận được nến của "
            + ", ".join(sorted({s.symbol for s in unsure}))
            + ", là mã có tín hiệu đã đủ phiên trong mẫu. Chưa ghi báo cáo; chạy lại khi nguồn trả "
            "đủ nến. Tới hạn chót mà vẫn vậy thì các tín hiệu này tính là thiếu giá."
        )
    dropped = set(unsure)
    return [replace(s, forward=None) if s in dropped else s for s in signals]


def _git_commit() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "không rõ"


async def refresh_bars(symbols: list[str]) -> list[str]:
    """Nạp lại nến của VN-Index và mọi mã có thể phát tín hiệu trước khi đo; trả mã nạp lỗi.

    Phiên chạy thật chỉ nạp nến cho rổ 200 của năm hiện tại, nên mã rơi khỏi rổ năm sau sẽ ngừng
    được cập nhật, và lợi nhuận 40 phiên của chúng thành đi ngang giả. Mã đã hủy niêm yết vẫn
    nạp được từ bảng giá VNDirect, nên chỉ mã cả hai nguồn đều không trả mới tính là lỗi.
    """
    import httpx

    from app import db
    from app.config import RESEARCH_HISTORY_START
    from app.ingest import fetch_bars, fetch_market_bars

    await db.init_db()
    semaphore = asyncio.Semaphore(4)
    failed: list[str] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        await db.replace_bars("VNINDEX", await fetch_bars(client, "VNINDEX", index=True))

        async def _one(symbol: str) -> None:
            async with semaphore:
                try:
                    fetched = await fetch_bars(client, symbol)
                except Exception as exc:
                    logger.info("Entrade không có nến %s: %s", symbol, exc)
                    fetched = []
                if not fetched:
                    try:
                        fetched = await fetch_market_bars(client, symbol, RESEARCH_HISTORY_START)
                    except Exception as exc:
                        logger.warning("Không nạp được nến %s: %s", symbol, exc)
                        fetched = []
            if fetched:
                await db.replace_bars(symbol, fetched)
            else:
                failed.append(symbol)

        await asyncio.gather(*(_one(symbol) for symbol in symbols))
    await db.close_db()
    return sorted(failed)


def _sample(start: str) -> tuple[list[FilterSignal], Counts, dict, list[str], dict]:
    from app.breadth_report import find_signals
    from app.industry_report import _load, baskets_for
    from app.ingest import load_exchanges

    bars, ratios, market, listings = _load()
    index = bars["VNINDEX"]
    index_days = [str(bar["trade_date"]) for bar in index]
    baskets = baskets_for(bars, ratios, listings, index_days)
    exchanges = load_exchanges()
    if not exchanges:
        raise SystemExit("Không đọc được bảng sàn từ backend/data/vstock.db hoặc VSTOCK_MARKET_DB.")
    recent = {year: basket for year, basket in baskets.items() if year >= int(start[:4])}
    raw = [signal for signal in find_signals(index, bars, recent, exchanges) if signal["day"] >= start]
    states = stored_states(market.get(BREADTH_STATE_SERIES) or [])
    signals = classify(raw, index_days, bars, ma200_from(index, start), states, start=start)
    return signals, count(signals, index_days, states, start=start), bars, index_days, listings


def _symbols_to_refresh(start: str) -> list[str]:
    from app.industry_report import _load, baskets_for

    bars, ratios, _market, listings = _load()
    index_days = [str(bar["trade_date"]) for bar in bars["VNINDEX"]]
    return _trade_symbols(baskets_for(bars, ratios, listings, index_days), start)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--measure", action="store_true", help="Đo một lần khi đã đủ điều kiện.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if not args.measure:
        _signals, counts, *_rest = _sample(BREADTH_FILTER_START)
        print(counts_text(counts))
        return
    if REPORT_PATH.exists():
        raise SystemExit(f"{REPORT_PATH} đã có: luật chỉ cho đo một lần.")
    _signals, counts, *_rest = _sample(BREADTH_FILTER_START)
    if not counts.ready and not counts.expired:
        print(counts_text(counts))
        raise SystemExit("Chưa đủ điều kiện đo.")
    to_refresh = _symbols_to_refresh(BREADTH_FILTER_START)
    failed = asyncio.run(refresh_bars(to_refresh))
    signals, counts, bars, index_days, listings = _sample(BREADTH_FILTER_START)
    unsure = unconfirmed(signals, bars, index_days, listings, set(to_refresh) - set(failed))
    signals = settle_unconfirmed(signals, unsure, counts)
    text = report_text(
        signals, counts, judge(signals, counts), code=_git_commit(), unpriced=unsure
    )
    REPORT_PATH.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
