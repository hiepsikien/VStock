"""Measure the industry gate on 2021–2024 and confirm it on 2025–2026.

The flags that block an entry stay off unless this report's numbers clear both windows.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from app.config import BANKS, DEFAULT_UNIVERSE, STATEMENT_LAG_DAYS
from app.industries import gated_industries, members, yearly_universe
from app.industry_screen import (
    CONFIRM_END,
    CONFIRM_START,
    SCREEN_END,
    SCREEN_START,
    average_by_day,
    build_open_map,
    dated_returns,
    early_days,
    find_runs,
    layer_counts,
    passes_layer,
    passes_stock,
)
from app.stock_select import balance_sheet_block, cheap_pair, position_rank, revenue_on, shortlist
from app.valuation import daily_valuation, market_cap

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "research.db"
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "industry_gate.md"


def _load() -> tuple[dict[str, list[dict]], dict, dict[str, list[tuple[str, float]]]]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    bars: dict[str, list[dict]] = defaultdict(list)
    for row in connection.execute(
        "SELECT symbol, trade_date, open, high, low, close, volume FROM daily_bars ORDER BY trade_date"
    ):
        bars[row["symbol"]].append(
            {
                "trade_date": row["trade_date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
            }
        )
    ratios: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(lambda: defaultdict(list))
    for row in connection.execute(
        "SELECT symbol, report_date, code, value FROM ratio_points ORDER BY report_date"
    ):
        ratios[row["symbol"]][row["code"]].append((row["report_date"], row["value"]))
    market: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in connection.execute(
        "SELECT series, trade_date, value FROM market_points ORDER BY trade_date"
    ):
        market[row["series"]].append((row["trade_date"], row["value"]))
    connection.close()
    return bars, ratios, market


def _credit(ratios: dict, days: list[str]) -> dict[str, float | None]:
    series = []
    for bank in BANKS:
        points = ratios.get(bank, {}).get("CUSTOMER_LOANS_AQ_GRYOY") or []
        visible = []
        for report, value in points:
            try:
                day = (date.fromisoformat(report) + timedelta(days=STATEMENT_LAG_DAYS)).isoformat()
            except ValueError:
                continue
            visible.append((day, value))
        visible.sort()
        series.append(visible)
    out: dict[str, float | None] = {}
    for day in days:
        values = []
        for visible in series:
            latest = None
            for report_day, value in visible:
                if report_day <= day:
                    latest = value
                else:
                    break
            if latest is not None:
                values.append(latest)
        values.sort()
        out[day] = values[len(values) // 2] if values else None
    return out


def _caps_on(day: str, bars: dict, ratios: dict) -> dict[str, float]:
    as_of = date.fromisoformat(day)
    caps = {}
    for symbol in DEFAULT_UNIVERSE:
        symbol_bars = bars.get(symbol) or []
        close = None
        for bar in symbol_bars:
            if bar["trade_date"] <= day:
                close = float(bar["close"])
            else:
                break
        if close is None:
            continue
        cap = market_cap(close, ratios.get(symbol, {}).get("OUTSTANDING_SHARES") or [], as_of)
        if cap:
            caps[symbol] = cap
    return caps


def _universe_for_year(year: int, bars: dict, ratios: dict, index_days: list[str]) -> tuple[str | None, list[str]]:
    """Top 100 on 1 January, or on the first session that year when a cap is actually knowable."""
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    for day in index_days:
        if day < start or day > end:
            continue
        caps = _caps_on(day, bars, ratios)
        if len(caps) >= 30:
            return day, yearly_universe(caps)
    return None, []


def _industry_forward(index: list[dict], day: str) -> float | None:
    days = [bar["trade_date"] for bar in index]
    if day not in days:
        return None
    start = days.index(day)
    if start + 66 >= len(index):
        return None
    base = float(index[start]["close"])
    if base <= 0:
        return None
    return float(index[start + 66]["close"]) / base - 1.0


def write_report() -> str:
    bars, ratios, market = _load()
    index = bars.get("VNINDEX") or []
    index_days = [bar["trade_date"] for bar in index]
    lines = ["# Cổng ngành", ""]
    if not index or index_days[0] > "2021-06-01":
        lines.append(
            f"Nến VN-Index bắt đầu {index_days[0] if index_days else 'không có'}. "
            "Chưa đủ 2021–2024 nên cổng chưa được phép chặn lệnh."
        )
        text = "\n".join(lines) + "\n"
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(text)
        return text

    stock_starts = [bars[symbol][0]["trade_date"] for symbol in DEFAULT_UNIVERSE if bars.get(symbol)]
    missing = [symbol for symbol in DEFAULT_UNIVERSE if not bars.get(symbol)]
    lines.append(
        f"Nến từ {min(stock_starts)} đến {index_days[-1]}, {len(stock_starts)} mã có nến, "
        f"sớm nhất thực tế {min(stock_starts)}."
    )
    if missing:
        lines.append("Không có nến: " + ", ".join(missing) + ".")
    oil = market.get("OIL") or []
    if oil:
        lines.append(f"Dầu từ {oil[0][0]} đến {oil[-1][0]}.")
    connection = sqlite3.connect(DB_PATH)
    flow_span = connection.execute(
        "SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT symbol) FROM flow_points"
    ).fetchone()
    connection.close()
    if flow_span and flow_span[0]:
        lines.append(
            f"Dòng ngoại từ {flow_span[0]} đến {flow_span[1]}, {flow_span[2]} mã. "
            "Nguồn không có trước ngày sớm nhất này."
        )
    lines.append("")
    credit = _credit(ratios, index_days)
    lead = {
        "OIL": [{"trade_date": day, "close": value} for day, value in market.get("OIL", [])]
    }
    allowed: dict[tuple[str, str], bool] = {}
    year_members: dict[int, tuple[str | None, list[str]]] = {}
    for year in range(2021, 2027):
        anchor, universe = _universe_for_year(year, bars, ratios, index_days)
        year_members[year] = (anchor, universe)
        if anchor is None or len(universe) < 3:
            continue
        opened = build_open_map(
            index,
            bars,
            universe,
            lead_bars=lead,
            credit_by_day=credit,
        )
        for (symbol, day), flag in opened.items():
            if day.startswith(str(year)) and day >= anchor and symbol in universe:
                allowed[(symbol, day)] = flag

    def _active(symbol: str, day: str) -> bool:
        anchor, universe = year_members.get(int(day[:4]), (None, []))
        return anchor is not None and day >= anchor and symbol in universe

    def _open(symbol: str, day: str) -> bool:
        return _active(symbol, day) and allowed.get((symbol, day), False)

    screen_book = {symbol: bars[symbol] for symbol in DEFAULT_UNIVERSE if symbol in bars}
    screen = layer_counts(screen_book, _open, SCREEN_START, SCREEN_END, _active)
    confirm = layer_counts(screen_book, _open, CONFIRM_START, CONFIRM_END, _active)

    # Precision of the industry gate is counted in industry-sessions, not name-sessions.
    industry_precision = _industry_precision(bars, allowed, year_members, SCREEN_START, SCREEN_END)
    industry_confirm = _industry_precision(bars, allowed, year_members, CONFIRM_START, CONFIRM_END)
    screen["precision"] = industry_precision["precision"]
    screen["baseline"] = industry_precision["baseline"]
    confirm["precision"] = industry_confirm["precision"]
    confirm["baseline"] = industry_confirm["baseline"]
    passed = passes_layer(
        screen["recall"],
        screen["precision"],
        screen["baseline"],
        confirm["recall"],
        confirm["precision"],
        confirm["baseline"],
    )
    # Số cổ phiếu trên nguồn chỉ có từ cuối 2022, nên 2021 và 2022 không dựng được rổ.
    # Giai đoạn chọn đã ấn định gồm sóng giảm 2022. Thiếu năm đó thì chưa được chặn lệnh.
    if year_members[2021][0] is None or year_members[2022][0] is None:
        passed = False
    roster = ", ".join(
        f"{year}={len(names)} từ {anchor or 'không có'}"
        for year, (anchor, names) in year_members.items()
    )
    lines.append("Rổ theo vốn hóa: " + roster + ".")
    lines.append(
        "Số cổ phiếu lưu hành trên nguồn bắt đầu 2022-12-31, công bố sau 45 ngày. "
        "Năm 2021 và 2022 không có vốn hóa đã biết vào đầu năm, nên không có rổ."
    )
    lines.append("")
    lines.append(_window_line("Chọn 2021–2024", screen, industry_precision))
    lines.append(_window_line("Xác nhận 2025–2026", confirm, industry_confirm))
    lines.append("")
    if passed:
        lines.append("Cổng ngành qua cả hai giai đoạn và được phép chặn Được vào.")
    else:
        lines.append("Cổng ngành chưa qua cả hai giai đoạn. Được vào chưa đổi.")
    lines.append("")
    lines.extend(_stock_lines(bars, ratios, allowed, year_members))
    lines.append("")
    lines.append("Nhận định LLM không được gọi vì không có khóa API. Cổng số vẫn là cổng được ghi ở trên.")
    lines.append(
        "Cửa thoát theo ngành, trailing stop sau khi chốt một phần ba, và trần 132 phiên "
        "đã có trong sổ. Trần nắm và việc bỏ tiền chết 30 phiên vẫn tắt vì cổng ngành "
        + ("đã qua cửa." if passed else "chưa được phép chặn lệnh.")
    )
    text = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    return text


def _window_line(title: str, counts: dict, industry: dict) -> str:
    return (
        f"{title}: {int(counts['runs'])} đợt, recall {counts['recall']:.1%}, "
        f"precision ngành {counts['precision']:.1%}, tỷ lệ nền {counts['baseline']:.1%}, "
        f"ngành mở trung bình mỗi phiên {industry['open_average']:.2f}."
    )


def _industry_precision(bars, allowed, year_members, start: str, end: str) -> dict:
    open_hits = open_days = base_hits = base_days = 0
    open_count = defaultdict(int)
    sessions = 0
    seen_days = set()
    for year, (anchor, universe) in year_members.items():
        gated = gated_industries(universe)
        indexes = {}
        for industry in gated:
            member_bars = [bars[symbol] for symbol in members(industry, universe) if symbol in bars]
            daily = average_by_day([dated_returns(item) for item in member_bars])
            level = 100.0
            index = []
            for day, change in daily:
                level *= 1.0 + change
                index.append({"trade_date": day, "close": level})
            indexes[industry] = index
        for industry in gated:
            index = indexes[industry]
            for bar in index:
                day = bar["trade_date"]
                if anchor is None or day < anchor or day < start or day > end or not day.startswith(str(year)):
                    continue
                forward = _industry_forward(index, day)
                if forward is None:
                    continue
                base_days += 1
                if forward >= 0.20:
                    base_hits += 1
                names = members(industry, universe)
                is_open_day = any(allowed.get((symbol, day)) for symbol in names)
                if day not in seen_days:
                    seen_days.add(day)
                    sessions += 1
                if is_open_day:
                    open_count[day] += 1
                    open_days += 1
                    if forward >= 0.20:
                        open_hits += 1
    average = (sum(open_count.values()) / sessions) if sessions else 0.0
    return {
        "precision": (open_hits / open_days) if open_days else 0.0,
        "baseline": (base_hits / base_days) if base_days else 0.0,
        "open_average": average,
    }


def _stock_lines(bars, ratios, allowed, year_members) -> list[str]:
    """Recall of runs whose name was on the shortlist, and the median gap versus the names left out."""
    valuations = {}
    for symbol, symbol_bars in bars.items():
        if symbol == "VNINDEX":
            continue
        points = ratios.get(symbol, {})
        valuations[symbol] = {
            day: (cap, pe)
            for day, cap, pe in daily_valuation(
                symbol_bars,
                points.get("OUTSTANDING_SHARES") or [],
                points.get("NET_PROFIT_QR") or [],
            )
        }
    connection = sqlite3.connect(DB_PATH)
    connection.executemany(
        """
        INSERT INTO valuation_points (symbol, trade_date, market_cap, trailing_pe)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(symbol, trade_date) DO UPDATE SET
            market_cap = excluded.market_cap,
            trailing_pe = excluded.trailing_pe
        """,
        [
            (symbol, day, cap, pe)
            for symbol, by_day in valuations.items()
            for day, (cap, pe) in by_day.items()
        ],
    )
    connection.commit()
    connection.close()

    def _measure(start: str, end: str) -> tuple[float, float, int, int, int]:
        runs = caught = 0
        shs_runs = shs_listed = 0
        kept_returns: list[float] = []
        dropped_returns: list[float] = []
        seen = set()
        for year, (anchor, universe) in year_members.items():
            for industry in gated_industries(universe):
                names = [symbol for symbol in members(industry, universe) if symbol in bars]
                for symbol in names:
                    for day, index, _change in find_runs(bars[symbol], start, end):
                        if anchor is None or day < anchor or not day.startswith(str(year)):
                            continue
                        runs += 1
                        early = early_days(bars[symbol], index)
                        listed = False
                        for early_day in early:
                            if not allowed.get((symbol, early_day)):
                                continue
                            chosen = _short(industry, names, early_day, valuations, ratios)
                            if symbol in chosen:
                                listed = True
                                break
                        if listed:
                            caught += 1
                        if symbol == "SHS":
                            shs_runs += 1
                            if listed:
                                shs_listed += 1
                for symbol in names:
                    symbol_bars = bars[symbol]
                    closes = [float(bar["close"]) for bar in symbol_bars]
                    days = [bar["trade_date"] for bar in symbol_bars]
                    for index, day in enumerate(days):
                        if anchor is None or day < anchor or day < start or day > end or not day.startswith(str(year)):
                            continue
                        if not allowed.get((symbol, day)) or index + 66 >= len(closes) or closes[index] <= 0:
                            continue
                        key = (industry, day)
                        if key not in seen:
                            seen.add(key)
                        chosen = _short(industry, names, day, valuations, ratios)
                        forward = closes[index + 66] / closes[index] - 1.0
                        if symbol in chosen:
                            kept_returns.append(forward)
                        else:
                            dropped_returns.append(forward)
        recall = (caught / runs) if runs else 0.0
        kept = statistics.median(kept_returns) if kept_returns else 0.0
        dropped = statistics.median(dropped_returns) if dropped_returns else 0.0
        return recall, kept - dropped, runs, shs_runs, shs_listed

    cache: dict[tuple, list[str]] = {}

    def _visible(points: dict, day: str) -> dict:
        as_of = date.fromisoformat(day)
        out = {}
        for code, series in points.items():
            kept = []
            for report, value in series:
                try:
                    report_day = date.fromisoformat(report)
                except ValueError:
                    continue
                if report_day + timedelta(days=STATEMENT_LAG_DAYS) <= as_of:
                    kept.append((report, value))
            if kept:
                out[code] = kept
        return out

    def _short(industry, names, day, valuations, ratios):
        key = (industry, day, tuple(names))
        if key in cache:
            return cache[key]
        as_of = date.fromisoformat(day)
        caps = {}
        revenues = {}
        rows = []
        pes = []
        for symbol in names:
            cap, pe = valuations.get(symbol, {}).get(day, (None, None))
            caps[symbol] = cap
            revenues[symbol] = revenue_on(symbol, ratios.get(symbol, {}), as_of)
            pes.append(pe)
        history = {}
        for symbol in names:
            own = []
            for past, (_cap, pe) in valuations.get(symbol, {}).items():
                if past < day and past >= f"{as_of.year - 3:04d}-{day[5:]}":
                    if pe:
                        own.append(pe)
            history[symbol] = own
        for symbol in names:
            _cap, pe = valuations.get(symbol, {}).get(day, (None, None))
            cheap_self, cheap_industry = cheap_pair(pe, history[symbol], [item for item in pes if item])
            rows.append(
                {
                    "symbol": symbol,
                    "block": balance_sheet_block(symbol, _visible(ratios.get(symbol, {}), day)),
                    "position": position_rank(symbol, caps, revenues),
                    "cheap_industry": cheap_industry,
                    "cheap_self": cheap_self,
                }
            )
        chosen = shortlist(rows)
        cache[key] = chosen
        return chosen

    screen_recall, screen_edge, screen_runs, screen_shs, screen_shs_listed = _measure(SCREEN_START, SCREEN_END)
    confirm_recall, confirm_edge, confirm_runs, confirm_shs, confirm_shs_listed = _measure(CONFIRM_START, CONFIRM_END)
    passed = passes_stock(screen_recall, confirm_recall, screen_edge, confirm_edge)
    return [
        f"Danh sách khoanh, chọn: recall {screen_recall:.1%} trên {screen_runs} đợt, "
        f"trung vị nhóm được khoanh trừ nhóm bị loại {screen_edge:.1%}.",
        f"Danh sách khoanh, xác nhận: recall {confirm_recall:.1%} trên {confirm_runs} đợt, "
        f"chênh trung vị {confirm_edge:.1%}.",
        "Danh sách khoanh được phép lọc ứng viên."
        if passed
        else "Danh sách khoanh chưa qua cửa, nên chưa lọc ứng viên. Hạng vị thế không được dùng để chặn.",
        f"SHS nằm trong danh sách khoanh ở {screen_shs_listed}/{screen_shs} đợt của giai đoạn chọn "
        f"và {confirm_shs_listed}/{confirm_shs} đợt của giai đoạn xác nhận.",
    ]


def main() -> None:
    print(write_report())


if __name__ == "__main__":
    main()
