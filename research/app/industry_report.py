"""Measure the industry gate on 2021–2024, confirm it on 2025–2026, and look back at 2015–2020.

The flags that block an entry stay off unless this report's numbers clear both windows.
"""

from __future__ import annotations

import sqlite3
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from app.config import STATEMENT_LAG_DAYS
from app.industries import (
    INDUSTRY_WINDOW,
    MIN_INDUSTRY_NAMES,
    gated_industries,
    members,
    set_industry_map,
)
from app.pit_universe import Basket, baskets_from_bars, trade_member_of
from app.industry_screen import (
    BACK_END,
    BACK_START,
    CONFIRM_END,
    CONFIRM_START,
    MIN_PRECISION_MULTIPLE,
    MIN_RECALL,
    SCREEN_END,
    OPERABLE_START,
    average_by_day,
    build_open_map,
    credit_by_day,
    dated_returns,
    early_days,
    find_runs,
    layer_counts,
    lead_bars_from,
    passes_layer,
    passes_stock,
)
from app.stock_select import balance_sheet_block, cheap_pair, position_rank, revenue_on, shortlist
from app.valuation import daily_valuation

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "research.db"
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "industry_gate.md"


def _load() -> tuple[dict[str, list[dict]], dict, dict[str, list[tuple[str, float]]], dict[str, dict]]:
    """Nến, BCTC, chuỗi thị trường và bảng niêm yết đã lưu; đồng thời gắn bảng ngành ICB.

    Bảng ngành được gắn ngay ở đây vì `industry_of` là chỗ duy nhất quyết định mã thuộc ngành
    nào, và cả báo cáo lẫn bảng dò đều đọc qua nó.
    """
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    bars: dict[str, list[dict]] = defaultdict(list)
    for row in connection.execute(
        "SELECT symbol, trade_date, open, high, low, close, volume, raw_close, trade_value "
        "FROM daily_bars ORDER BY trade_date"
    ):
        bars[row["symbol"]].append(
            {
                "trade_date": row["trade_date"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                # Giá thật và giá trị khớp thật của phiên: rổ đọc hai cột này để đo vốn hóa và
                # thanh khoản, còn tín hiệu vẫn đọc `close` đã điều chỉnh.
                "raw_close": row["raw_close"],
                "trade_value": row["trade_value"],
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
    listings: dict[str, dict] = defaultdict(dict)
    for row in connection.execute(
        "SELECT symbol, exchange, status, listed_date, delisted_date FROM symbol_meta"
    ):
        listings[row["symbol"]] = dict(row)
    industries: dict[str, str] = {}
    for row in connection.execute("SELECT symbol, industry FROM symbol_industry"):
        if row["industry"]:
            industries[row["symbol"]] = row["industry"]
    connection.close()
    set_industry_map(industries)
    return bars, ratios, market, dict(listings)


def baskets_for(
    bars: dict[str, list[dict]],
    ratios: dict,
    listings: dict[str, dict],
    index_days: list[str],
) -> dict[int, Basket]:
    """Rổ 200 mã và rổ giao dịch 100 mã của từng năm, dựng từ nến và số cổ phiếu đã lưu."""
    return baskets_from_bars(index_days, bars, ratios, listings)



def yearly_open_map(
    bars: dict[str, list[dict]],
    ratios: dict,
    market: dict[str, list[tuple[str, float]]],
    baskets: dict[int, Basket],
    window: int = INDUSTRY_WINDOW,
    regime_by_day: dict[str, bool | None] | None = None,
) -> dict[tuple[str, str], bool]:
    """Trạng thái mở của từng phiên, chỉ sinh cho mã nằm trong rổ giao dịch của năm đó.

    Sức mạnh ngành đo trên rổ 200 mã của năm, đúng bằng chỉ số ngành mà phép đo precision đọc:
    một ngành đủ ba mã trong rổ 200 thì mã vào lệnh bị xét theo chỉ số ngành đó, kể cả khi ngành
    ấy chỉ có một mã trong rổ giao dịch. Rổ giao dịch chỉ quyết định mã nào có cờ, vì mã ngoài
    rổ giao dịch không có lệnh nào để mở.
    """
    index = bars.get("VNINDEX") or []
    index_days = [bar["trade_date"] for bar in index]
    credit = credit_by_day(ratios, index_days)
    lead = lead_bars_from(market)
    allowed: dict[tuple[str, str], bool] = {}
    for year, basket in baskets.items():
        # Năm nào rổ 200 mã cũng chưa đủ ba mã cho một ngành thì không có cổng ngành nào để mở.
        if basket.day is None or len(basket.universe) < MIN_INDUSTRY_NAMES:
            continue
        opened = build_open_map(
            index,
            bars,
            list(basket.universe),
            lead_bars=lead,
            credit_by_day=credit,
            regime_by_day=regime_by_day,
            window=window,
        )
        in_book = set(basket.trade)
        for (symbol, day), flag in opened.items():
            if symbol in in_book and day.startswith(str(year)) and day >= basket.day:
                allowed[(symbol, day)] = flag
    return allowed


def measure_gate(bars, allowed, baskets: dict[int, Basket], start: str, end: str) -> tuple[dict, dict]:
    """Recall over name runs, and precision over industry-sessions, for one window."""

    def _active(symbol: str, day: str) -> bool:
        basket = baskets.get(int(day[:4]))
        return bool(
            basket
            and basket.day is not None
            and day >= basket.day
            and trade_member_of(baskets, symbol, day)
        )

    def _open(symbol: str, day: str) -> bool:
        return _active(symbol, day) and allowed.get((symbol, day), False)

    book = {
        symbol: series
        for symbol, series in bars.items()
        if symbol != "VNINDEX" and any(symbol in basket.trade for basket in baskets.values())
    }
    counts = layer_counts(book, _open, start, end, _active)
    # Precision of the industry gate is counted in industry-sessions, not name-sessions.
    industry = _industry_precision(bars, allowed, baskets, start, end)
    counts["precision"] = industry["precision"]
    counts["baseline"] = industry["baseline"]
    return counts, industry


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
    bars, ratios, market, listings = _load()
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

    with_bars = [symbol for symbol in listings if bars.get(symbol)]
    delisted = [symbol for symbol, meta in listings.items() if meta.get("delisted_date")]
    missing = [symbol for symbol in listings if not bars.get(symbol)]
    early = {
        symbol
        for symbol in missing
        if (listings[symbol].get("delisted_date") or "9999-99-99") < index_days[0]
    }
    stock_starts = [bars[symbol][0]["trade_date"] for symbol in with_bars]
    lines.append(
        f"Nến từ {min(stock_starts)} đến {index_days[-1]}, {len(with_bars)}/{len(listings)} mã "
        f"trong danh sách niêm yết đã có nến, trong đó {len(delisted)} mã đã hủy niêm yết."
    )
    if missing:
        gap = sorted(set(missing) - early)
        lines.append(
            f"Chưa có nến: {len(missing)} mã, trong đó {len(early)} mã đã hủy niêm yết trước "
            f"{index_days[0]} nên nguồn không còn giá"
            + (f", còn lại {', '.join(gap[:12])}." if gap else ".")
        )
    lines.append(
        "Rổ của mỗi năm đọc danh sách niêm yết của nguồn nên giữ cả mã đã hủy niêm yết: "
        "mã rời sàn vì phá sản hay bị thâu tóm vẫn nằm trong rổ của năm nó còn giao dịch, "
        "và chỉ bị loại khi số cổ phiếu đã công bố hoặc thanh khoản không đủ."
    )
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
    baskets = baskets_for(bars, ratios, listings, index_days)
    allowed = yearly_open_map(bars, ratios, market, baskets)
    screen, industry_precision = measure_gate(bars, allowed, baskets, OPERABLE_START, SCREEN_END)
    confirm, industry_confirm = measure_gate(bars, allowed, baskets, CONFIRM_START, CONFIRM_END)
    back, industry_back = measure_gate(bars, allowed, baskets, BACK_START, BACK_END)
    passed = passes_layer(
        screen["recall"],
        screen["precision"],
        screen["baseline"],
        confirm["recall"],
        confirm["precision"],
        confirm["baseline"],
    )
    roster = ", ".join(
        f"{year}={len(basket.universe)}/{len(basket.trade)} từ {basket.day}"
        for year, basket in sorted(baskets.items())
    )
    lines.append("Rổ 200 mã và rổ giao dịch 100 mã theo vốn hóa: " + roster + ".")
    lines.append(
        "Chỉ số ngành và cổng ba mã dựng trên rổ 200 mã của năm, nên ngành nào đủ ba mã trong "
        "rổ 200 thì mã vào lệnh bị xét theo chỉ số ngành đó kể cả khi rổ giao dịch chỉ có một "
        "mã của ngành ấy; cờ mở chỉ sinh cho mã thuộc rổ giao dịch 100 mã."
    )
    lines.append(
        "Mã bị loại khi số cổ phiếu đã công bố chưa đủ 45 ngày tính tới phiên chốt, hoặc khi "
        "trung vị giá trị khớp thật 20 phiên trước đó dưới 3 tỷ đồng; mã đã hủy niêm yết "
        "không được xếp hạng sau ngày hủy. Vốn hóa và thanh khoản đều đo bằng giá thật và giá "
        "trị khớp thật của phiên, không bằng giá đã điều chỉnh chia tách, nên mã chia tách nhiều "
        "không còn bị đo thấp mà rơi khỏi rổ."
    )
    lines.append(
        "Ba giới hạn đã biết của cách đo này, chưa đưa vào luật. Một: một phiên mã không khớp "
        "lệnh vẫn vào cửa sổ 20 phiên với giá trị 0 nên trung vị bị kéo xuống — trên cả kho, nến "
        "volume bằng 0 chiếm 17–25% mỗi năm trong 2014–2020, 7% năm 2021, rồi khoảng 1% từ 2022; "
        "nhưng đo đúng 20 phiên cuối của rổ thì không năm nào có phiên giá trị 0, vì mã không "
        "khớp lệnh nằm ngoài rổ. Hai: cửa sổ là 20 phiên cuối của chính mã chứ không theo lịch "
        "sàn, nên mã bị tạm ngừng giao dịch dài vẫn xếp hạng bằng thanh khoản cũ (HPX trong rổ "
        "2024 xếp hạng 144/200 dù phiên cuối 2023-09-15 cách phiên chốt 109 ngày); bắt nến cuối "
        "phải mới hơn một số ngày so với phiên chốt là một tham số mới, chưa đưa vào. Ba: số cổ "
        "phiếu phải đủ 45 ngày mới tính trong khi giá thật đã giảm từ ngày giao dịch không hưởng "
        "quyền, nên vốn hóa của mã vừa chia tách hay phát hành thêm bị đo lệch trong cửa sổ đó."
    )
    lines.append(
        "Số cổ phiếu lưu hành trước 2023 được bổ sung từ vốn góp của chủ sở hữu trong BCTC quý. "
        f"Cửa sổ đo chạy từ {OPERABLE_START}, phiên đầu tiên vốn hóa đã biết."
    )
    lines.append("")
    lines.append(_window_line(f"Chọn {OPERABLE_START}–2024", screen, industry_precision))
    lines.append(_window_line("Xác nhận 2025–2026", confirm, industry_confirm))
    lines.append(_window_line("Lùi 2015–2020, chỉ để đối chiếu", back, industry_back))
    lines.append(
        "Giai đoạn lùi không nằm trong luật qua cửa. Tín dụng ngân hàng chỉ có từ 2018, "
        "nên trước đó ngân hàng và chứng khoán luôn đóng."
    )
    lines.append("")
    if passed:
        lines.append("Cổng ngành qua cả hai giai đoạn và được phép chặn Được vào.")
    else:
        lines.append("Cổng ngành chưa qua cả hai giai đoạn. Được vào chưa đổi.")
        misses = _misses("Chọn", screen) + _misses("Xác nhận", confirm)
        lines.append(
            "Chỗ trượt: " + "; ".join(misses) + ". Ngưỡng được chốt trước lần đo đầu; "
            "số sát ngưỡng không phải lý do để nới ngưỡng."
        )
    lines.append("")
    lines.extend(_stock_lines(bars, ratios, allowed, baskets))
    lines.append("")
    lines.append(
        "Nhận định tháng chạy bằng `python -m app.llm_notes` từ thư mục research, "
        f"mỗi tháng một lần từ {OPERABLE_START}. "
        "Câu hỏi thêm về công bố, chỗ lệch hạng, và rà bảng ngành nằm ở docs/industry-first-backlog.md."
    )
    lines.append(
        "Cửa thoát theo ngành, trailing stop sau khi chốt một phần ba, và trần 132 phiên "
        "đã có trong sổ. Trần nắm và việc bỏ tiền chết 30 phiên vẫn tắt vì cổng ngành "
        + ("đã qua cửa." if passed else "chưa được phép chặn lệnh.")
    )
    text = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    return text


def _misses(name: str, counts: dict) -> list[str]:
    out = []
    if counts["recall"] < MIN_RECALL:
        out.append(
            f"{name} recall {counts['recall']:.1%}, dưới ngưỡng {MIN_RECALL:.0%} "
            f"{(MIN_RECALL - counts['recall']) * 100:.1f} điểm"
        )
    if counts["baseline"] and counts["precision"] < MIN_PRECISION_MULTIPLE * counts["baseline"]:
        out.append(
            f"{name} precision gấp {counts['precision'] / counts['baseline']:.2f} lần nền, "
            f"cần {MIN_PRECISION_MULTIPLE:g} lần"
        )
    return out


def _window_line(title: str, counts: dict, industry: dict) -> str:
    return (
        f"{title}: {int(counts['runs'])} đợt, recall {counts['recall']:.1%}, "
        f"precision ngành {counts['precision']:.1%}, tỷ lệ nền {counts['baseline']:.1%}, "
        f"ngành mở trung bình mỗi phiên {industry['open_average']:.2f}."
    )


def _industry_precision(bars, allowed, baskets: dict[int, Basket], start: str, end: str) -> dict:
    """Tỷ lệ phiên-ngành mở mà ngành đó tăng 20% trong 66 phiên, so với tỷ lệ nền của chính nó.

    Chỉ số ngành lấy cả rổ 200 mã để không phụ thuộc vào việc mã nào lọt vào rổ giao dịch,
    còn "ngành mở" chỉ tính trên rổ giao dịch — đúng những mã sổ lệnh được phép vào.
    """
    open_hits = open_days = base_hits = base_days = 0
    open_count = defaultdict(int)
    sessions = 0
    seen_days = set()
    for year, basket in baskets.items():
        anchor = basket.day
        universe = basket.universe
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
            tradable = [symbol for symbol in members(industry, universe) if symbol in basket.trade]
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
                is_open_day = any(allowed.get((symbol, day)) for symbol in tradable)
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


def _stock_lines(bars, ratios, allowed, baskets: dict[int, Basket]) -> list[str]:
    """Recall of runs whose name was on the shortlist, and the median gap versus the names left out.

    Danh sách chọn chỉ đọc rổ giao dịch của năm: đó là những mã sổ lệnh thật sự được phép vào,
    nên recall ở đây không bị thổi lên bởi mã chỉ nằm trong rổ 200 mã.
    """
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
        for year, basket in sorted(baskets.items()):
            anchor = basket.day
            for industry in gated_industries(basket.trade):
                names = [symbol for symbol in members(industry, basket.trade) if symbol in bars]
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

    screen_recall, screen_edge, screen_runs, screen_shs, screen_shs_listed = _measure(OPERABLE_START, SCREEN_END)
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
        f"SHS trong rổ giao dịch {screen_shs} đợt ở giai đoạn chọn và {confirm_shs} đợt ở giai đoạn "
        f"xác nhận, trong đó nằm ở danh sách khoanh {screen_shs_listed} và {confirm_shs_listed} đợt.",
    ]


def main() -> None:
    print(write_report())


if __name__ == "__main__":
    main()
