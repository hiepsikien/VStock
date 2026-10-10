from __future__ import annotations

from datetime import date, timedelta

from app.config import CASH_YIELD, HOLD_SESSIONS, MA_WINDOW, ROUND_TRIP_COST, STATEMENT_LAG_DAYS
from app.evaluate import compose
from app.pattern import assess_pattern, market_regime


def _slice(bars: list[dict], as_of: str) -> list[dict]:
    return [bar for bar in bars if bar["trade_date"] <= as_of]


def _lag_ratios(
    points: dict[str, list[tuple[str, float]]],
    as_of: date,
    lag_days: int,
) -> dict[str, list[tuple[str, float]]]:
    visible: dict[str, list[tuple[str, float]]] = {}
    for code, series in points.items():
        kept = []
        for report, value in series:
            try:
                report_day = date.fromisoformat(report)
            except ValueError:
                continue
            if report_day + timedelta(days=lag_days) <= as_of:
                kept.append((report, value))
        if kept:
            visible[code] = kept
    return visible


def run_backtest(
    index_bars: list[dict],
    bars_by_symbol: dict[str, list[dict]],
    ratios_by_symbol: dict[str, dict[str, list[tuple[str, float]]]],
    articles_by_symbol: dict[str, list[dict]],
) -> dict:
    """One slot of capital. Statements are used 45 days after period end. News clock is live-only."""
    if len(index_bars) < MA_WINDOW + 5:
        return {"error": f"Chưa đủ nến VN-Index. Cần hơn {MA_WINDOW} phiên."}

    dates = [bar["trade_date"] for bar in index_bars][MA_WINDOW:]
    side_cost = ROUND_TRIP_COST / 2
    cash = 1.0
    position: dict | None = None
    trades: list[dict] = []
    curve: list[tuple[str, float]] = []
    previous_day: date | None = None

    for trade_date in dates:
        as_of = date.fromisoformat(trade_date)
        index_slice = _slice(index_bars, trade_date)
        regime = market_regime(index_slice)

        if position is not None:
            symbol = position["symbol"]
            stock_slice = _slice(bars_by_symbol.get(symbol, []), trade_date)
            price = stock_slice[-1]["close"] if stock_slice else None
            if price is None:
                curve.append((trade_date, cash))
                previous_day = as_of
                continue
            position["sessions"] += 1
            stop_hit = price < position["stop"]
            time_hit = position["sessions"] >= HOLD_SESSIONS
            last_day = trade_date == dates[-1]
            if stop_hit or time_hit or last_day:
                cash = position["notional"] * (price / position["entry"]) * (1 - side_cost)
                if last_day and not stop_hit and not time_hit:
                    exit_reason = "Hết cửa sổ đo"
                elif stop_hit:
                    exit_reason = "Chạm đáy nền"
                else:
                    exit_reason = "Đủ 60 phiên"
                trades.append(
                    {
                        "symbol": symbol,
                        "entry": position["entry_date"],
                        "exit": trade_date,
                        "entry_price": position["entry"],
                        "exit_price": price,
                        "sessions": position["sessions"],
                        "reason": exit_reason,
                    }
                )
                position = None
            else:
                curve.append((trade_date, position["notional"] * (price / position["entry"])))
                previous_day = as_of
                continue

        if previous_day is not None:
            gap_days = (as_of - previous_day).days
            if gap_days > 0:
                cash *= (1 + CASH_YIELD) ** (gap_days / 365)
        previous_day = as_of
        candidates = []
        if regime.open:
            for symbol, stock_bars in bars_by_symbol.items():
                stock_slice = _slice(stock_bars, trade_date)
                if len(stock_slice) < 61:
                    continue
                verdict = compose(
                    symbol,
                    as_of,
                    _lag_ratios(ratios_by_symbol.get(symbol, {}), as_of, STATEMENT_LAG_DAYS),
                    articles_by_symbol.get(symbol, []),
                    regime,
                    assess_pattern(stock_slice, index_slice),
                    require_clock=False,
                )
                if verdict.status == "Được vào" and verdict.stop_price and verdict.stop_price < stock_slice[-1]["close"]:
                    candidates.append((verdict.priority, symbol, stock_slice[-1]["close"], verdict.stop_price))
        if candidates:
            _priority, symbol, price, stop = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
            notional = cash * (1 - side_cost)
            cash = 0.0
            position = {
                "symbol": symbol,
                "entry": price,
                "entry_date": trade_date,
                "stop": stop,
                "notional": notional,
                "sessions": 0,
            }
            curve.append((trade_date, notional))
            continue

        curve.append((trade_date, cash))

    if not curve:
        return {"error": "Không có phiên nào sau khi MA200 đã đủ dữ liệu."}

    start_index = index_bars[MA_WINDOW]["close"]
    end_index = index_bars[-1]["close"]
    index_return = end_index / start_index - 1 if start_index else 0.0
    strategy_return = curve[-1][1] - 1
    return {
        "error": None,
        "start": dates[0],
        "end": dates[-1],
        "sessions": len(dates),
        "trades": trades,
        "trade_count": len(trades),
        "strategy_return": strategy_return,
        "index_return": index_return,
        "passed": strategy_return >= index_return,
        "assumptions": (
            f"Phí cả vòng {ROUND_TRIP_COST * 100:.2f}%. "
            f"Lãi tiền gửi {CASH_YIELD * 100:.1f}%/năm khi đang đứng ngoài. "
            f"Số liệu quý được dùng {STATEMENT_LAG_DAYS} ngày sau ngày kết thúc kỳ. "
            "Bài công bố chỉ chặn hoặc hoãn khi đã có trong kho; đo này không bắt buộc bài công bố "
            "vì tin cũ không được lưu đủ."
        ),
    }
