"""Đo cổng độ rộng trên 2021–2024, xác nhận trên 2025–2026, và nhìn lại 2015–2020.

Luật và ngưỡng nằm trong config (`BREADTH_*`), chốt trước lần chạy đầu. Ba tầng đo:

* thị trường: danh mục chia đều rổ 100 mã của năm, chỉ cầm khi cổng mở — MA200 đơn thuần,
  độ rộng đơn thuần, và MA200 cùng độ rộng;
* tín hiệu: mọi phiên một mã của rổ 100 đạt `assess_pattern`, lợi nhuận 20/40/60 phiên sau đó,
  tách theo trạng thái độ rộng của chính phiên tín hiệu, và theo bốn ô MA200 × độ rộng;
* sổ lệnh: `run_backtest` có và không có cổng độ rộng, chỉ để tham khảo vì quá ít lệnh.

Chạy: cd research && PYTHONPATH=. python3 -m app.breadth_report
Cần bảng sàn từ kho thị trường như `industry_sweep`, vì sổ lệnh đọc biên độ theo sàn.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
from bisect import bisect_right
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from app.backtest import run_backtest
from app.breadth import adjustment_breaks, breadth_by_day, breadth_states
from app.config import (
    BREADTH_CLOSE,
    BREADTH_MA_WINDOW,
    BREADTH_MAX_STALE_SESSIONS,
    BREADTH_MAX_YEARLY_GIVEUP,
    BREADTH_MIN_DRAWDOWN_CUT,
    BREADTH_MIN_NAMES,
    BREADTH_MIN_SIGNAL_EDGE,
    BREADTH_MIN_SIGNALS,
    BREADTH_OPEN,
    BREADTH_SIGNAL_HORIZON,
    BREADTH_START,
    BREAKOUT_VOLUME_RATIO,
    CASH_YIELD,
    ROUND_TRIP_COST,
)
from app.industries import industry_labels, set_industry_map
from app.industry_report import _load, baskets_for
from app.industry_screen import BACK_END, BACK_LEDGER_START, BACK_START, CONFIRM_END, CONFIRM_START, OPERABLE_START, SCREEN_END
from app.industry_sweep import _basket_by_day, _rotation, _segment, _stored
from app.ingest import load_exchanges
from app.pattern import assess_pattern, market_regime
from app.pit_universe import Basket

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "breadth_gate.md"
PERIODS = (
    ("Lùi", BACK_START, BACK_END),
    ("Chọn", OPERABLE_START, SCREEN_END),
    ("Xác nhận", CONFIRM_START, CONFIRM_END),
)
CHECKED = ("Chọn", "Xác nhận")
LEDGER_PERIODS = (("Lùi", BACK_LEDGER_START, BACK_END),) + PERIODS[1:]
HORIZONS = (20, BREADTH_SIGNAL_HORIZON, 60)
ADX_WINDOW = 14
# Đợt giảm từ đỉnh sâu tới mức này thì báo cáo ghi cổng mở lại sau bao lâu.
DEEP_DRAWDOWN = -0.20

_INPUTS: dict = {}


def adx_by_day(bars: list[dict], window: int = ADX_WINDOW) -> dict[str, float]:
    """ADX của Wilder. Chỉ là cột mô tả trong báo cáo, không phải cổng."""
    out: dict[str, float] = {}
    if len(bars) <= 2 * window:
        return out
    trs, plus, minus = [], [], []
    for previous, current in zip(bars, bars[1:]):
        up = current["high"] - previous["high"]
        down = previous["low"] - current["low"]
        plus.append(up if up > down and up > 0 else 0.0)
        minus.append(down if down > up and down > 0 else 0.0)
        trs.append(
            max(
                current["high"] - current["low"],
                abs(current["high"] - previous["close"]),
                abs(current["low"] - previous["close"]),
            )
        )
    tr_s, plus_s, minus_s = sum(trs[:window]), sum(plus[:window]), sum(minus[:window])
    dxs: list[float] = []
    adx: float | None = None
    for index in range(window, len(trs) + 1):
        if index > window:
            tr_s += trs[index - 1] - tr_s / window
            plus_s += plus[index - 1] - plus_s / window
            minus_s += minus[index - 1] - minus_s / window
        plus_di = 100 * plus_s / tr_s if tr_s else 0.0
        minus_di = 100 * minus_s / tr_s if tr_s else 0.0
        total = plus_di + minus_di
        dx = 100 * abs(plus_di - minus_di) / total if total else 0.0
        if adx is None:
            dxs.append(dx)
            if len(dxs) == window:
                adx = sum(dxs) / window
        else:
            adx = (adx * (window - 1) + dx) / window
        if adx is not None:
            out[bars[index]["trade_date"]] = adx
    return out


def _trade_basket(baskets: dict[int, Basket], day: str) -> list[str]:
    basket = baskets.get(int(day[:4]))
    if basket is None or basket.day is None or day < basket.day:
        return []
    return list(basket.trade)


def find_signals(
    index: list[dict],
    bars: dict[str, list[dict]],
    baskets: dict[int, Basket],
    exchanges: dict[str, str],
) -> list[dict]:
    """Mọi phiên một mã của rổ 100 đạt `assess_pattern`, với lợi nhuận các phiên sau đó.

    Lợi nhuận đo từ giá đóng cửa phiên tín hiệu tới giá đóng cửa cuối cùng không muộn hơn phiên
    thứ N của VN-Index, nên mã bị tạm ngừng hay hủy niêm yết giữa chừng giữ giá cuối của nó
    thay vì bị bỏ khỏi mẫu. Tín hiệu chưa đủ N phiên tới cuối kho thì không có số cho N đó.
    """
    index_days = [bar["trade_date"] for bar in index]
    position_of = {day: position for position, day in enumerate(index_days)}
    by_symbol: dict[str, list[str]] = {}
    for day in index_days:
        for symbol in _trade_basket(baskets, day):
            by_symbol.setdefault(symbol, []).append(day)
    signals: list[dict] = []
    for symbol, member_days in sorted(by_symbol.items()):
        series = bars.get(symbol) or []
        days = [bar["trade_date"] for bar in series]
        at = {day: i for i, day in enumerate(days)}
        for day in member_days:
            i = at.get(day)
            if i is None or i < 60:
                continue
            window = series[i - 20 : i]
            ceiling = max(bar["high"] for bar in window)
            volume = sum(bar["volume"] for bar in window) / len(window)
            # Hai điều kiện cần của `assess_pattern`, lọc trước để không gọi nó cho mọi phiên.
            if series[i]["close"] <= ceiling or volume <= 0:
                continue
            if series[i]["volume"] / volume < BREAKOUT_VOLUME_RATIO:
                continue
            position = position_of[day]
            # Both pre-registered measurements read their signals here, so the split guard keeps
            # the whole-history scan it had at the tags; the live screen uses the recent window.
            pattern = assess_pattern(
                series[: i + 1], index[: position + 1], exchanges.get(symbol), split_sessions=None
            )
            if not pattern.ready:
                continue
            entry = float(series[i]["close"])
            forward: dict[int, float | None] = {}
            for horizon in HORIZONS:
                if position + horizon >= len(index_days):
                    forward[horizon] = None
                    continue
                last = bisect_right(days, index_days[position + horizon]) - 1
                forward[horizon] = float(series[last]["close"]) / entry - 1
            signals.append({"symbol": symbol, "day": day, "forward": forward})
    return signals


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _summary(signals: list[dict]) -> dict:
    out: dict = {"count": len(signals)}
    for horizon in HORIZONS:
        values = [s["forward"][horizon] for s in signals if s["forward"][horizon] is not None]
        out[horizon] = _mean(values)
        out[f"n{horizon}"] = len(values)
        out[f"median{horizon}"] = statistics.median(values) if values else None
        out[f"hit{horizon}"] = (sum(1 for v in values if v > 0) / len(values)) if values else None
    return out


def _in(day: str, start: str, end: str) -> bool:
    return start <= day <= end


def _flips(states: dict[str, bool | None], days: list[str]) -> int:
    seen = [states.get(day) for day in days if states.get(day) is not None]
    return sum(1 for a, b in zip(seen, seen[1:]) if a != b)


def _open_share(states: dict[str, bool | None], days: list[str]) -> float | None:
    seen = [states.get(day) for day in days if states.get(day) is not None]
    return sum(1 for value in seen if value) / len(seen) if seen else None


def _recoveries(index: list[dict], gates: dict[str, dict[str, bool | None]]) -> list[dict]:
    """Đợt giảm từ đỉnh tới `DEEP_DRAWDOWN`, và mỗi cổng mở lại sau đáy bao lâu."""
    closes = [float(bar["close"]) for bar in index]
    days = [bar["trade_date"] for bar in index]
    out = []
    peak, peak_at, i = closes[0], 0, 0
    while i < len(closes):
        if closes[i] >= peak:
            peak, peak_at = closes[i], i
            i += 1
            continue
        j, low = i, i
        while j < len(closes) and closes[j] < peak:
            if closes[j] < closes[low]:
                low = j
            j += 1
        if closes[low] / peak - 1 <= DEEP_DRAWDOWN:
            row = {"peak": days[peak_at], "trough": days[low], "fall": closes[low] / peak - 1, "gates": {}}
            for name, states in gates.items():
                back = next((k for k in range(low, len(days)) if states.get(days[k]) is True), None)
                row["gates"][name] = None if back is None else (days[back], back - low, closes[back] / closes[low] - 1)
            out.append(row)
        i = j
    return out


def _init_worker(inputs: dict) -> None:
    _INPUTS.update(inputs)
    set_industry_map(inputs["industries"])


def _ledger(label: str, breadth_open: dict | None) -> tuple[str, dict]:
    inputs = _INPUTS
    result = run_backtest(
        inputs["index"],
        inputs["bars"],
        inputs["ratios"],
        inputs["articles"],
        inputs["exchanges"],
        inputs["flow"],
        inputs["market"],
        breadth_open=breadth_open,
    )
    print(f"  sổ lệnh {label} xong", file=sys.stderr, flush=True)
    return label, result


def run_report() -> str:
    bars, ratios, market, listings = _load()
    index = bars["VNINDEX"]
    index_days = [bar["trade_date"] for bar in index]
    print("Dựng rổ theo từng năm", file=sys.stderr, flush=True)
    baskets = baskets_for(bars, ratios, listings, index_days)
    boards = {symbol: str(meta.get("exchange") or "") for symbol, meta in listings.items()}

    print("Tính độ rộng", file=sys.stderr, flush=True)
    points = breadth_by_day(index_days, bars, baskets, boards)
    breadth = breadth_states([(day, points[day].share) for day in index_days])
    ma200 = {day: market_regime(index[: i + 1]).open for i, day in enumerate(index_days)}
    both = {
        day: (None if ma200[day] is None or breadth[day] is None else bool(ma200[day] and breadth[day]))
        for day in index_days
    }
    gates = {"MA200": ma200, "Độ rộng": breadth, "MA200 và độ rộng": both}

    print("Tầng thị trường", file=sys.stderr, flush=True)
    basket = _basket_by_day(baskets, index_days)
    previous = dict(zip(index_days[1:], index_days))
    curves = {"VN-Index": ([(bar["trade_date"], float(bar["close"])) for bar in index], None)}
    curves["Cả rổ"] = (_rotation(bars, index_days, lambda day: basket.get(day, [])), None)
    for name, states in gates.items():
        # Cầm từ giá đóng cửa phiên trước, nên phiên trước phải đã mở: mua ngay giá đóng cửa
        # của phiên vừa cho tín hiệu. Cột trễ mua ở giá đóng cửa phiên sau đó.
        main = _rotation(
            bars, index_days, lambda day, s=states: basket.get(day, []) if s.get(previous.get(day, "")) else []
        )
        late = _rotation(
            bars,
            index_days,
            lambda day, s=states: basket.get(day, []) if s.get(previous.get(previous.get(day, ""), "")) else [],
        )
        curves[name] = (main, late)

    print("Tầng tín hiệu", file=sys.stderr, flush=True)
    exchanges = load_exchanges()
    if not exchanges:
        raise SystemExit(
            "Không đọc được bảng sàn từ backend/data/vstock.db hoặc VSTOCK_MARKET_DB. "
            "Bộ quét và sổ lệnh cần nó cho luật giá chưa chỉnh chia tách, nên không chạy."
        )
    signals = find_signals(index, bars, baskets, exchanges)
    adx = adx_by_day(index)

    symbols = sorted(
        symbol for symbol in {name for b in baskets.values() for name in b.universe} if bars.get(symbol)
    )
    print("Nạp tin và dòng ngoại", file=sys.stderr, flush=True)
    articles, flow = asyncio.run(_stored(symbols))
    inputs = {
        "index": index,
        "bars": {symbol: bars[symbol] for symbol in symbols},
        "ratios": {symbol: dict(ratios.get(symbol, {})) for symbol in symbols},
        "articles": articles,
        "flow": flow,
        "exchanges": exchanges,
        "market": dict(market),
        "industries": industry_labels(),
    }
    print("Chạy sổ lệnh: MA200 và MA200 cùng độ rộng", file=sys.stderr, flush=True)
    books: dict[str, dict] = {}
    jobs = [("MA200", None), ("MA200 và độ rộng", breadth)]
    with ProcessPoolExecutor(max_workers=len(jobs), initializer=_init_worker, initargs=(inputs,)) as pool:
        for label, result in [f.result() for f in [pool.submit(_ledger, *job) for job in jobs]]:
            books[label] = result

    text = _render(
        index_days, baskets, bars, boards, points, gates, curves, signals, adx, books, index
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    return text


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:+.1f}%"


def _plain(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _verdict(curves: dict, signals: list[dict], breadth: dict) -> tuple[bool, list[str], dict]:
    misses: list[str] = []
    rows: dict = {}
    for name, start, end in PERIODS:
        if name not in CHECKED:
            continue
        base = _segment(curves["MA200"][0], start, end)
        gated = _segment(curves["MA200 và độ rộng"][0], start, end)
        cut = None
        if base and gated and base["drawdown"] < 0:
            cut = 1 - gated["drawdown"] / base["drawdown"]
        giveup = None
        if base and gated and base["yearly"] is not None and gated["yearly"] is not None:
            giveup = base["yearly"] - gated["yearly"]
        inside = [s for s in signals if _in(s["day"], start, end) and breadth.get(s["day"]) is not None]
        opened = [s["forward"][BREADTH_SIGNAL_HORIZON] for s in inside if breadth[s["day"]]]
        closed = [s["forward"][BREADTH_SIGNAL_HORIZON] for s in inside if not breadth[s["day"]]]
        opened = [v for v in opened if v is not None]
        closed = [v for v in closed if v is not None]
        edge = None
        if opened and closed:
            edge = _mean(opened) - _mean(closed)
        rows[name] = {"cut": cut, "giveup": giveup, "edge": edge, "n_open": len(opened), "n_closed": len(closed)}
        if cut is None or cut < BREADTH_MIN_DRAWDOWN_CUT:
            misses.append(
                f"{name}: sụt sâu nhất chỉ nông hơn {_plain(cut)}, cần {BREADTH_MIN_DRAWDOWN_CUT:.0%}"
            )
        if giveup is None or giveup > BREADTH_MAX_YEARLY_GIVEUP:
            misses.append(
                f"{name}: lợi nhuận mỗi năm kém {_pct(giveup)}, trần {BREADTH_MAX_YEARLY_GIVEUP * 100:.0f} điểm %"
            )
        if len(opened) < BREADTH_MIN_SIGNALS or len(closed) < BREADTH_MIN_SIGNALS:
            misses.append(
                f"{name}: chưa đủ mẫu tín hiệu ({len(opened)} lúc mở, {len(closed)} lúc đóng, "
                f"cần {BREADTH_MIN_SIGNALS} mỗi phía)"
            )
        elif edge is None or edge < BREADTH_MIN_SIGNAL_EDGE:
            misses.append(
                f"{name}: tín hiệu lúc mở chỉ hơn lúc đóng {_pct(edge)} sau {BREADTH_SIGNAL_HORIZON} phiên, "
                f"cần {BREADTH_MIN_SIGNAL_EDGE * 100:+.0f} điểm"
            )
    return not misses, misses, rows


def _render(index_days, baskets, bars, boards, points, gates, curves, signals, adx, books, index) -> str:
    breadth = gates["Độ rộng"]
    ma200 = gates["MA200"]
    passed, misses, rows = _verdict(curves, signals, breadth)
    lines = ["# Cổng độ rộng", ""]
    lines.append(
        f"Độ rộng là tỷ lệ mã của rổ 200 trong năm có giá đóng cửa đã điều chỉnh trên MA{BREADTH_MA_WINDOW} "
        f"của chính nó. Mã chỉ được đếm khi nến cuối cách phiên đang chấm không quá "
        f"{BREADTH_MAX_STALE_SESSIONS} phiên, có đủ {BREADTH_MA_WINDOW} nến, và cửa sổ đó không chứa bước giá "
        f"quá biên độ sàn (HOSE 9%, HNX 12%, cùng mốc với luật giá chưa chỉnh chia tách). Dưới "
        f"{BREADTH_MIN_NAMES} mã hợp lệ thì phiên đó chưa chấm. Cổng mở khi tỷ lệ từ {BREADTH_OPEN:.0%}, đóng "
        f"khi từ {BREADTH_CLOSE:.0%} trở xuống, ở giữa giữ trạng thái trước; phiên đầu lấy mốc {BREADTH_START:.0%}. "
        "Luật và ngưỡng chốt ngày 2026-10-12, trước lần đo đầu."
    )
    lines.append("")
    lines.append("## Kết luận")
    lines.append("")
    if passed:
        lines.append("Cổng độ rộng qua cả giai đoạn chọn và xác nhận. `BREADTH_GATE_ENFORCED` được phép bật.")
    else:
        lines.append("Cổng độ rộng chưa qua. `BREADTH_GATE_ENFORCED` giữ tắt.")
        lines.append("")
        lines.append("Chỗ trượt: " + "; ".join(misses) + ".")
    lines.append("")
    lines.append(
        f"Luật qua cửa, phải đạt ở cả hai giai đoạn: (1) danh mục \"MA200 và độ rộng\" có sụt sâu nhất nông hơn "
        f"\"MA200\" ít nhất {BREADTH_MIN_DRAWDOWN_CUT:.0%} (tương đối) và lợi nhuận mỗi năm không kém quá "
        f"{BREADTH_MAX_YEARLY_GIVEUP * 100:.0f} điểm %; (2) lợi nhuận trung bình {BREADTH_SIGNAL_HORIZON} phiên của "
        f"tín hiệu phá nền lúc độ rộng mở cao hơn lúc đóng ít nhất {BREADTH_MIN_SIGNAL_EDGE * 100:.0f} điểm %, "
        f"mỗi phía ít nhất {BREADTH_MIN_SIGNALS} tín hiệu. Số sát ngưỡng không phải lý do để nới ngưỡng."
    )
    lines.append("")
    lines.append("| Giai đoạn | Sụt sâu nhất nông hơn | Lợi nhuận mỗi năm kém | Tín hiệu mở − đóng (40 phiên) | Tín hiệu mở / đóng |")
    lines.append("|---|---|---|---|---|")
    for name in CHECKED:
        row = rows.get(name) or {}
        lines.append(
            f"| {name} | {_plain(row.get('cut'))} | {_pct(row.get('giveup'))} | {_pct(row.get('edge'))} | "
            f"{row.get('n_open', 0)} / {row.get('n_closed', 0)} |"
        )
    lines.append("")

    lines.append("## Dữ liệu")
    lines.append("")
    lines.append("| Năm | Rổ | Mã đếm TB | Nến cũ TB | Thiếu nến TB | Có bước gãy TB | Phiên chưa chấm |")
    lines.append("|---|---|---|---|---|---|---|")
    for year in sorted(baskets):
        days = [day for day in index_days if day[:4] == str(year)]
        pts = [points[day] for day in days]
        if not pts:
            continue
        lines.append(
            f"| {year} | {len(baskets[year].universe)} | {_mean([p.names for p in pts]):.0f} | "
            f"{_mean([p.stale for p in pts]):.1f} | {_mean([p.short for p in pts]):.1f} | "
            f"{_mean([p.broken for p in pts]):.1f} | {sum(1 for p in pts if p.share is None)} |"
        )
    lines.append("")
    broken = []
    for year, basket in sorted(baskets.items()):
        for symbol in basket.universe:
            for day in adjustment_breaks(bars.get(symbol) or [], boards.get(symbol)):
                if day[:4] == str(year):
                    broken.append(f"{symbol} {day}")
    lines.append(
        f"Bước giá quá biên độ sàn của mã trong rổ đúng năm đó: {len(broken)}. "
        + (", ".join(broken) + "." if broken else "")
        + " Mã có bước như vậy không được đếm trong 50 nến kể từ bước đó; sàn lấy theo bảng niêm yết hiện tại, "
        "nên mã từng ở HNX rồi chuyển HOSE bị xét theo biên độ HOSE."
    )
    lines.append("")

    lines.append("## Trạng thái cổng")
    lines.append("")
    lines.append("| Giai đoạn | Cổng | Tỷ lệ phiên mở | Số lần đổi trạng thái | Độ rộng TB |")
    lines.append("|---|---|---|---|---|")
    for name, start, end in PERIODS:
        days = [day for day in index_days if _in(day, start, end)]
        shares = [points[day].share for day in days if points[day].share is not None]
        for gate, states in gates.items():
            lines.append(
                f"| {name} | {gate} | {_plain(_open_share(states, days))} | {_flips(states, days)} | "
                + (_plain(_mean(shares)) if gate == "Độ rộng" else "")
                + " |"
            )
    lines.append("")

    lines.append("## Tầng thị trường")
    lines.append("")
    lines.append(
        "Mỗi phiên giữ đều mọi mã của rổ 100 của năm khi cổng đang mở, đứng tiền khi cổng đóng. "
        f"Phí {ROUND_TRIP_COST * 100:.1f}% cả vòng trên phần tỷ trọng đổi chủ, tiền đứng ngoài lãi "
        f"{CASH_YIELD * 100:.1f}%/năm. Cột chính mua ở giá đóng cửa của phiên vừa cho tín hiệu (trạng thái chỉ dùng "
        "giá tới hết phiên đó); cột trễ mua ở giá đóng cửa phiên sau. Tiêu chí qua cửa đọc cột chính."
    )
    lines.append("")
    lines.append("| Danh mục | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lợi nhuận trễ 1 phiên | Sụt sâu nhất trễ 1 phiên |")
    lines.append("|---|---|---|---|---|---|---|")
    for name, start, end in PERIODS:
        for label, (curve, late) in curves.items():
            seg = _segment(curve, start, end)
            if seg is None:
                continue
            late_seg = _segment(late, start, end) if late else None
            lines.append(
                f"| {label} | {name} | {_pct(seg['return'])} | {_pct(seg['yearly'])} | {_pct(seg['drawdown'])} | "
                f"{_pct(late_seg['return']) if late_seg else '—'} | {_pct(late_seg['drawdown']) if late_seg else '—'} |"
            )
    lines.append("")

    lines.append("## Tầng tín hiệu")
    lines.append("")
    lines.append(
        "Tín hiệu là một phiên mã thuộc rổ 100 của năm đạt `assess_pattern`: nền 20 phiên siết biên độ và cạn "
        "khối lượng, đóng cửa phá đỉnh nền với khối lượng từ 1.5 lần, nền không sâu quá 15%, có nhịp tăng trước "
        "nền, sức mạnh tương đối dương. Không xét cổng cơ bản, tin hay dòng ngoại. Lợi nhuận đo từ giá đóng cửa "
        "phiên tín hiệu, không trừ phí; mã ngừng giao dịch giữ giá cuối. Trạng thái là của chính phiên tín hiệu."
    )
    lines.append("")
    lines.append("| Giai đoạn | Nhóm | Tín hiệu | TB 20 phiên | TB 40 phiên | Trung vị 40 | Thắng 40 | TB 60 phiên |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name, start, end in PERIODS:
        inside = [s for s in signals if _in(s["day"], start, end)]
        groups = [
            ("Tất cả", inside),
            ("Độ rộng mở", [s for s in inside if breadth.get(s["day"]) is True]),
            ("Độ rộng đóng", [s for s in inside if breadth.get(s["day"]) is False]),
            ("MA200 mở, độ rộng mở", [s for s in inside if ma200.get(s["day"]) and breadth.get(s["day"]) is True]),
            ("MA200 mở, độ rộng đóng", [s for s in inside if ma200.get(s["day"]) and breadth.get(s["day"]) is False]),
        ]
        for label, group in groups:
            summary = _summary(group)
            lines.append(
                f"| {name} | {label} | {summary['count']} | {_pct(summary[20])} | {_pct(summary[40])} | "
                f"{_pct(summary['median40'])} | {_plain(summary['hit40'])} | {_pct(summary[60])} |"
            )
    lines.append("")
    lines.append(
        "Hai dòng \"MA200 mở\" chỉ để tham khảo: luật qua cửa so mọi tín hiệu theo độ rộng, như đã chốt."
    )
    lines.append("")

    lines.append("## Bốn ô MA200 × độ rộng")
    lines.append("")
    lines.append(
        "Bảng chẩn đoán, không phải luật. Ô nào dưới "
        f"{BREADTH_MIN_SIGNALS} tín hiệu thì số của nó chưa đủ mẫu. ADX 14 phiên của VN-Index chỉ là cột mô tả."
    )
    lines.append("")
    lines.append("| Giai đoạn | Ô | Tỷ lệ phiên | ADX TB | Phiên ADX < 20 | Tín hiệu | TB 40 phiên | Thắng 40 | Ghi chú |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    cells = (
        ("Trên MA200, độ rộng mở", True, True),
        ("Trên MA200, độ rộng đóng", True, False),
        ("Dưới MA200, độ rộng mở", False, True),
        ("Dưới MA200, độ rộng đóng", False, False),
    )
    for name, start, end in PERIODS:
        days = [d for d in index_days if _in(d, start, end) and ma200[d] is not None and breadth[d] is not None]
        for label, above, wide in cells:
            cell_days = [d for d in days if ma200[d] == above and breadth[d] == wide]
            values = [adx[d] for d in cell_days if d in adx]
            in_cell = set(cell_days)
            group = [s for s in signals if s["day"] in in_cell]
            summary = _summary(group)
            note = "chưa đủ mẫu" if summary["n40"] < BREADTH_MIN_SIGNALS else ""
            lines.append(
                f"| {name} | {label} | {_plain(len(cell_days) / len(days) if days else None)} | "
                f"{'—' if not values else f'{_mean(values):.0f}'} | "
                f"{_plain(sum(1 for v in values if v < 20) / len(values) if values else None)} | "
                f"{summary['count']} | {_pct(summary[40])} | {_plain(summary['hit40'])} | {note} |"
            )
    lines.append("")

    lines.append("## Sổ lệnh")
    lines.append("")
    lines.append(
        "Cùng luật `Được vào` và cách thoát như trang /backtest, trên mọi mã từng vào rổ 200. Dòng \"MA200 và "
        "độ rộng\" chỉ thêm một điều: phiên độ rộng không mở thì không vào lệnh mới; lệnh đang giữ không bị đóng. "
        "Chỉ để tham khảo, vì số lệnh quá ít để làm tiêu chí."
    )
    lines.append("")
    lines.append("| Sổ | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lệnh vào | Thắng | Lãi TB mỗi lệnh |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for name, start, end in LEDGER_PERIODS:
        for label, result in books.items():
            if result.get("error"):
                lines.append(f"| {label} | {name} | {result['error']} ||||||")
                continue
            seg = _segment(result.get("curve") or [], start, end)
            if seg is None:
                continue
            trades = [t for t in result.get("trades") or [] if _in(t["entry"], start, end)]
            returns = [t["return_pct"] or 0.0 for t in trades]
            lines.append(
                f"| {label} | {name} | {_pct(seg['return'])} | {_pct(seg['yearly'])} | {_pct(seg['drawdown'])} | "
                f"{len(trades)} | {_plain(sum(1 for r in returns if r > 0) / len(returns) if returns else None)} | "
                f"{_pct(_mean(returns))} |"
            )
    lines.append("")

    lines.append("## Độ trễ sau đáy")
    lines.append("")
    lines.append(
        f"Đợt VN-Index giảm từ đỉnh {DEEP_DRAWDOWN:.0%} trở xuống, và mỗi cổng mở lại sau đáy bao lâu. Giới hạn "
        "đã biết của mọi cổng theo xu hướng; chỉ có hai đợt như vậy từ 2014 nên không đủ để dựng luật bắt đáy."
    )
    lines.append("")
    lines.append("| Đỉnh | Đáy | Giảm | Cổng | Mở lại | Sau | VN-Index đã tăng từ đáy |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in _recoveries(index, gates):
        for gate, back in row["gates"].items():
            if back is None:
                lines.append(f"| {row['peak']} | {row['trough']} | {_pct(row['fall'])} | {gate} | chưa mở lại | | |")
            else:
                lines.append(
                    f"| {row['peak']} | {row['trough']} | {_pct(row['fall'])} | {gate} | {back[0]} | "
                    f"{back[1]} phiên | {_pct(back[2])} |"
                )
    lines.append("")
    lines.append(
        "Giai đoạn lùi 2015–2020 không nằm trong luật qua cửa: rổ của những năm đó chỉ có 62–118 mã nên mỗi mã "
        "nặng hơn trong tỷ lệ, và cổng cơ bản của sổ lệnh chỉ chấm được từ 2018-02-15."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    print(run_report())


if __name__ == "__main__":
    main()
