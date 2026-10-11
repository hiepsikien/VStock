"""Đo cổng ngành với cửa sổ lợi suất 14, 30 và 60 phiên.

Mỗi cửa sổ cho ba nhóm số trên giai đoạn lùi, giai đoạn chọn và giai đoạn xác nhận:

* recall và precision ngành, cùng cách đếm với báo cáo cổng ngành;
* lợi nhuận của một danh mục chia đều cho mọi mã đang ở ngành mở, so với danh mục chia đều cả rổ;
* lợi nhuận của sổ lệnh hiện tại khi chỉ được vào mã ở ngành mở, so với sổ lệnh không có cổng ngành.

Chỉ dùng giá, BCTC, dầu và tín dụng đã lưu trong kho. Không gọi mô hình ngôn ngữ.

Chạy: cd research && PYTHONPATH=. python3 -m app.industry_sweep
Mất khoảng 10–12 phút và gần 2 GB RAM: bốn sổ lệnh chạy song song, mỗi tiến trình nhận
một bản sao đầy đủ của nến, BCTC, tin và dòng ngoại.

Cần bảng sàn từ kho thị trường (backend/data/vstock.db hoặc VSTOCK_MARKET_DB): luật giá chưa
chỉnh chia tách đọc biên độ theo sàn, thiếu bảng thì mọi mã dùng biên độ rộng nhất và sổ lệnh
ra số khác hẳn. Không có bảng thì lệnh dừng thay vì chạy.
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from app import db
from app.backtest import run_backtest
from app.config import CASH_YIELD, ROUND_TRIP_COST
from app.db import market_db_path
from app.industries import INDUSTRY_WINDOW, industry_labels, set_industry_map
from app.industry_report import _load, baskets_for, measure_gate, yearly_open_map
from app.pit_universe import Basket
from app.industry_screen import (
    BACK_END,
    BACK_LEDGER_START,
    BACK_START,
    CONFIRM_END,
    CONFIRM_START,
    MIN_PRECISION_MULTIPLE,
    MIN_RECALL,
    OPERABLE_START,
    SCREEN_END,
)
from app.ingest import load_exchanges
from app.pattern import market_regime

WINDOWS = (14, 30, 60)
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "industry_sweep.md"
PERIODS = (
    ("Lùi", BACK_START, BACK_END),
    ("Chọn", OPERABLE_START, SCREEN_END),
    ("Xác nhận", CONFIRM_START, CONFIRM_END),
)
LEDGER_PERIODS = (("Lùi", BACK_LEDGER_START, BACK_END),) + PERIODS[1:]

Curve = list[tuple[str, float]]

_INPUTS: dict = {}


def _segment(curve: Curve, start: str, end: str) -> dict | None:
    """Return, yearly rate and deepest drawdown of a curve between two dates."""
    before = [value for day, value in curve if day < start]
    inside = [(day, value) for day, value in curve if start <= day <= end]
    if not inside:
        return None
    base = before[-1] if before else inside[0][1]
    values = [base] + [value for _day, value in inside]
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1)
    total = values[-1] / base - 1
    years = (date.fromisoformat(inside[-1][0]) - date.fromisoformat(inside[0][0])).days / 365.25
    yearly = (1 + total) ** (1 / years) - 1 if years > 0.25 else None
    return {
        "start": inside[0][0],
        "end": inside[-1][0],
        "return": total,
        "yearly": yearly,
        "drawdown": worst,
    }


def _rotation(bars: dict[str, list[dict]], index_days: list[str], pick) -> Curve:
    """Equal weight across the names `pick(day)` returns, settled at each close.

    The state of a session only uses data through the session before, so holding from the
    previous close is the earliest the rule could act. Cost is charged on the weight that
    changes hands; a session with nothing open earns the deposit rate.
    """
    side_cost = ROUND_TRIP_COST / 2
    closes = {
        symbol: {bar["trade_date"]: float(bar["close"]) for bar in series}
        for symbol, series in bars.items()
        if symbol != "VNINDEX"
    }
    equity = 1.0
    weights: dict[str, float] = {}
    curve: Curve = []
    for previous, day in zip(index_days, index_days[1:]):
        names = [
            symbol
            for symbol in pick(day)
            if (closes.get(symbol) or {}).get(previous, 0) > 0 and day in closes[symbol]
        ]
        target = {symbol: 1 / len(names) for symbol in names}
        turnover = sum(abs(target.get(s, 0.0) - weights.get(s, 0.0)) for s in set(target) | set(weights))
        equity *= 1 - side_cost * turnover
        if target:
            moves = {symbol: closes[symbol][day] / closes[symbol][previous] - 1 for symbol in target}
            gross = sum(target[symbol] * moves[symbol] for symbol in target)
            equity *= 1 + gross
            weights = {s: target[s] * (1 + moves[s]) / (1 + gross) for s in target}
        else:
            gap = (date.fromisoformat(day) - date.fromisoformat(previous)).days
            equity *= (1 + CASH_YIELD) ** (gap / 365)
            weights = {}
        curve.append((day, equity))
    return curve


def _by_day(allowed: dict[tuple[str, str], bool]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for (symbol, day), flag in allowed.items():
        if flag:
            out[day].append(symbol)
    return out


def _basket_by_day(baskets: dict[int, Basket], index_days: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for day in index_days:
        basket = baskets.get(int(day[:4]))
        out[day] = (
            list(basket.trade) if basket is not None and basket.day is not None and day >= basket.day else []
        )
    return out


def _init_worker(inputs: dict) -> None:
    _INPUTS.update(inputs)
    # Sổ lệnh chấm `industry_of` cho từng mã, nên tiến trình con phải nhận đúng bảng ngành
    # mà tiến trình cha đã gắn từ kho; thiếu thì chỉ danh sách thủ công còn tác dụng.
    set_industry_map(inputs["industries"])


def _backtest(window: int | None, open_map: dict | None) -> tuple[int | None, dict]:
    inputs = _INPUTS
    result = run_backtest(
        inputs["index"],
        inputs["bars"],
        inputs["ratios"],
        inputs["articles"],
        inputs["exchanges"],
        inputs["flow"],
        inputs["market"],
        open_map=open_map,
        enforce_industry=open_map is not None,
    )
    print(f"  sổ lệnh {window or 'không cổng'} xong", file=sys.stderr, flush=True)
    return window, result


def _trades_in(result: dict, start: str, end: str) -> tuple[int, float | None, float | None]:
    trades = [trade for trade in result.get("trades") or [] if start <= trade["entry"] <= end]
    if not trades:
        return 0, None, None
    returns = [trade["return_pct"] or 0.0 for trade in trades]
    wins = sum(1 for value in returns if value > 0)
    return len(trades), wins / len(trades), sum(returns) / len(returns)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:+.1f}%"


def _plain(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


async def _stored(symbols: list[str]) -> tuple[dict, dict]:
    await db.init_db()
    articles = {symbol: await db.articles_for(symbol) for symbol in symbols}
    flow = {symbol: await db.flow(symbol) for symbol in symbols}
    await db.close_db()
    return articles, flow


def run_sweep() -> str:
    bars, ratios, market, listings = _load()
    index = bars["VNINDEX"]
    index_days = [bar["trade_date"] for bar in index]
    regime_by_day = {day: market_regime(index[: i + 1]).open for i, day in enumerate(index_days)}
    print("Dựng rổ theo từng năm", file=sys.stderr, flush=True)
    baskets = baskets_for(bars, ratios, listings, index_days)

    print("Dựng trạng thái ngành", file=sys.stderr, flush=True)
    maps = {}
    measures = {}
    for window in WINDOWS:
        allowed = yearly_open_map(
            bars, ratios, market, baskets, window=window, regime_by_day=regime_by_day
        )
        maps[window] = allowed
        measures[window] = {
            name: measure_gate(bars, allowed, baskets, start, end)
            for name, start, end in PERIODS
        }

    basket = _basket_by_day(baskets, index_days)
    index_curve = [(bar["trade_date"], float(bar["close"])) for bar in index]
    always_curve = _rotation(bars, index_days, lambda day: basket.get(day, []))
    previous = dict(zip(index_days[1:], index_days))
    rotation_curves = {}
    for window in WINDOWS:
        opened = _by_day(maps[window])
        rotation_curves[window] = (
            _rotation(bars, index_days, lambda day, o=opened: o.get(day, [])),
            _rotation(bars, index_days, lambda day, o=opened: o.get(previous.get(day, ""), [])),
        )

    symbols = sorted(
        symbol
        for symbol in {name for basket in baskets.values() for name in basket.universe}
        if bars.get(symbol)
    )
    exchanges = load_exchanges()
    if not exchanges:
        raise SystemExit(
            "Không đọc được bảng sàn từ backend/data/vstock.db hoặc VSTOCK_MARKET_DB. "
            "Sổ lệnh cần nó cho luật giá chưa chỉnh chia tách, nên không chạy."
        )
    print("Nạp tin và dòng ngoại", file=sys.stderr, flush=True)
    articles, flow = asyncio.run(_stored(symbols))
    sources = _sources(bars, symbols, exchanges, articles, flow)
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
    print("Chạy sổ lệnh: không cổng và từng cửa sổ", file=sys.stderr, flush=True)
    jobs = [(None, None)] + [(window, maps[window]) for window in WINDOWS]
    books: dict[int | None, dict] = {}
    with ProcessPoolExecutor(max_workers=len(jobs), initializer=_init_worker, initargs=(inputs,)) as pool:
        futures = [pool.submit(_backtest, window, open_map) for window, open_map in jobs]
        for future in futures:
            window, result = future.result()
            books[window] = result

    text = _render(sources, measures, index_curve, always_curve, rotation_curves, books)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text)
    return text


def _sources(bars, symbols, exchanges, articles, flow) -> list[str]:
    def _first(days):
        days = [day for day in days if day]
        return min(days) if days else "không có"

    unknown = [symbol for symbol in symbols if symbol not in exchanges]
    source = market_db_path()
    try:
        source = source.relative_to(Path(__file__).resolve().parents[2]) if source else source
    except ValueError:
        pass
    return [
        f"Nến từ {_first(bars[symbol][0]['trade_date'] for symbol in symbols if bars[symbol])} "
        f"đến {bars['VNINDEX'][-1]['trade_date']}, {len(symbols)} mã.",
        f"Bảng sàn: {len(exchanges)} mã từ `{source}`, "
        f"{len(symbols) - len(unknown)}/{len(symbols)} mã của rổ có sàn"
        + (f"; {', '.join(unknown)} không có nên dùng biên độ rộng nhất." if unknown else "."),
        "Tin từ "
        + _first(str(article.get("published_at") or "")[:10] for items in articles.values() for article in items)
        + ", dòng ngoại từ "
        + _first(day for points in flow.values() for series in points.values() for day, _value in series)
        + ".",
    ]


def _window_lines(measures) -> list[str]:
    recall_ok = []
    lift_ok = []
    for window in WINDOWS:
        checked = [measures[window][name][0] for name in ("Chọn", "Xác nhận")]
        if all(counts["recall"] >= MIN_RECALL for counts in checked):
            recall_ok.append(str(window))
        if all(
            counts["baseline"] and counts["precision"] >= MIN_PRECISION_MULTIPLE * counts["baseline"]
            for counts in checked
        ):
            lift_ok.append(str(window))
    return [
        f"Cửa sổ đang dùng ở live: {INDUSTRY_WINDOW} phiên. "
        f"Qua ngưỡng recall {MIN_RECALL:.0%} ở cả Chọn và Xác nhận: "
        f"{', '.join(recall_ok) or 'không cửa sổ nào'}. "
        f"Đạt precision gấp {MIN_PRECISION_MULTIPLE:g} lần nền ở cả hai: "
        f"{', '.join(lift_ok) or 'không cửa sổ nào'}.",
        "Ngưỡng được chốt trước lần đo đầu. Số sát ngưỡng không phải lý do để nới ngưỡng, và chọn lại "
        "cửa sổ sau khi đã xem các bảng này là một luật mới: phải đo lại từ đầu, và các giai đoạn đã "
        "xem không còn là phép thử sạch.",
    ]


def _render(sources, measures, index_curve, always_curve, rotation_curves, books) -> str:
    lines = ["# Cổng ngành theo cửa sổ 14, 30, 60 phiên", ""]
    lines.extend(sources)
    lines.append("")
    lines.append(
        "Cửa sổ là số phiên dùng để so lợi suất ngành với VN-Index, và cũng là cửa sổ của chuỗi dầu. "
        "Định nghĩa đợt tăng (66 phiên, +20%, cửa sớm dưới +15%), rổ theo năm, ngưỡng tín dụng và "
        "VN-Index trên MA200 giữ nguyên. Không có bước nào gọi mô hình ngôn ngữ."
    )
    lines.append("")
    lines.append("## Tín hiệu")
    lines.append("")
    lines.append("| Cửa sổ | Giai đoạn | Đợt | Recall | Precision ngành | Tỷ lệ nền | Precision / nền | Ngành mở TB |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for window in WINDOWS:
        for name, _start, _end in PERIODS:
            counts, industry = measures[window][name]
            lift = counts["precision"] / counts["baseline"] if counts["baseline"] else None
            lines.append(
                f"| {window} | {name} | {int(counts['runs'])} | {_plain(counts['recall'])} | "
                f"{_plain(counts['precision'])} | {_plain(counts['baseline'])} | "
                f"{'—' if lift is None else f'{lift:.2f}'} | {industry['open_average']:.2f} |"
            )
    lines.append("")
    lines.extend(_window_lines(measures))
    lines.append("")
    lines.append("## Danh mục chia đều mã ở ngành mở")
    lines.append("")
    lines.append(
        "Mỗi phiên giữ đều mọi mã của rổ năm đang ở ngành mở, trạng thái tính đến hết phiên trước. "
        f"Phí {ROUND_TRIP_COST * 100:.1f}% cả vòng tính trên phần tỷ trọng đổi chủ. Phiên không ngành nào "
        f"mở thì đứng tiền, lãi {CASH_YIELD * 100:.1f}%/năm. \"Cả rổ\" là cùng cách đó nhưng luôn mở. "
        "Cột chính mua ngay giá đóng cửa của phiên vừa cho tín hiệu, là cách lạc quan nhất; "
        "cột \"trễ 1 phiên\" mua ở giá đóng cửa phiên sau, là cách thận trọng. Giá mở cửa nằm giữa hai cột."
    )
    lines.append("")
    lines.append("| Danh mục | Giai đoạn | Từ | Đến | Lợi nhuận | Mỗi năm | Sụt sâu nhất | Lợi nhuận trễ 1 phiên |")
    lines.append("|---|---|---|---|---|---|---|---|")
    rows = [("VN-Index", index_curve, None), ("Cả rổ", always_curve, None)] + [
        (f"Ngành mở {window} phiên", *rotation_curves[window]) for window in WINDOWS
    ]
    for name, start, end in PERIODS:
        for label, curve, late in rows:
            seg = _segment(curve, start, end)
            if seg is None:
                continue
            late_seg = _segment(late, start, end) if late else None
            lines.append(
                f"| {label} | {name} | {seg['start']} | {seg['end']} | {_pct(seg['return'])} | "
                f"{_pct(seg['yearly'])} | {_pct(seg['drawdown'])} | "
                f"{_pct(late_seg['return']) if late_seg else '—'} |"
            )
    lines.append("")
    lines.append("## Sổ lệnh hiện tại")
    lines.append("")
    base = books.get(None) or {}
    lines.append(
        "Cùng luật `Được vào`, dừng lỗ, chốt một phần ba ở +1R, tiền chết 30 phiên và phí như trang "
        "/backtest. Cột cửa sổ chỉ thêm một điều: mã phải thuộc rổ năm và ngành đang mở. "
        "Mỗi lệnh chỉ rủi ro 1% vốn nên sổ đứng tiền phần lớn thời gian; phần lãi từ giao dịch là "
        "chênh lệch so với dòng \"Chỉ gửi tiền\". "
        f"Giai đoạn lùi của sổ bắt đầu {BACK_LEDGER_START}, khi chỉ số tài chính quý 4/2017 "
        "đã công bố đủ 45 ngày; trước đó cổng cơ bản không chấm được mã nào."
    )
    lines.append("")
    lines.append("| Sổ | Giai đoạn | Lợi nhuận | Mỗi năm | Sụt sâu nhất | VN-Index cùng kỳ | Lệnh vào | Thắng | Lãi TB mỗi lệnh |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for name, start, end in LEDGER_PERIODS:
        days = [day for day, _value in base.get("curve") or [] if start <= day <= end]
        if days:
            years = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days / 365.25
            lines.append(
                f"| Chỉ gửi tiền | {name} | {_pct((1 + CASH_YIELD) ** years - 1)} | "
                f"{_pct(CASH_YIELD)} | +0.0% | | | | |"
            )
        for window in (None,) + WINDOWS:
            result = books.get(window) or {}
            if result.get("error"):
                lines.append(f"| {window or 'Không cổng'} | {name} | {result['error']} |||||||")
                continue
            curve = result.get("curve") or []
            seg = _segment(curve, start, end)
            if seg is None:
                continue
            index_seg = _segment(
                [(day, value) for day, value in index_curve if day >= curve[0][0]], start, end
            )
            count, win_rate, average = _trades_in(result, start, end)
            label = "Không cổng" if window is None else f"Ngành mở {window} phiên"
            lines.append(
                f"| {label} | {name} | {_pct(seg['return'])} | {_pct(seg['yearly'])} | "
                f"{_pct(seg['drawdown'])} | {_pct(index_seg['return'] if index_seg else None)} | "
                f"{count} | {_plain(win_rate)} | {_pct(average)} |"
            )
    lines.append("")
    lines.append(
        "Lưu ý: rổ mỗi năm là 200 mã còn niêm yết theo danh sách của nguồn và đủ thanh khoản, "
        "rổ giao dịch là 100 mã đầu theo vốn hóa, nên mã đã hủy niêm yết vẫn có mặt trong năm "
        "mà nó còn giao dịch. Giai đoạn lùi vẫn không nằm trong luật qua cửa. Trong giai đoạn đó "
        "tín dụng ngân hàng chỉ có từ 2018, nên trước đó ngân hàng và chứng khoán luôn đóng; "
        "dòng tiền khối ngoại chỉ có từ 2018-08, phiên thiếu thì cổng dòng ngoại không chặn. "
        "Vốn hóa và thanh khoản của rổ đo bằng giá thật và giá trị khớp thật của phiên, không "
        "bằng giá đã điều chỉnh chia tách. Số cổ phiếu của nhiều mã đã hủy niêm yết chỉ còn lại "
        "ở khoản vốn góp chủ sở hữu trong BCTC quý, nên vốn hóa của chúng là ước lượng, và các ô "
        "của giai đoạn lùi chỉ là đối chiếu."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    print(run_sweep())


if __name__ == "__main__":
    main()
