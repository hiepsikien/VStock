from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.config import (
    CASH_YIELD,
    MA_FAST,
    MA_WINDOW,
    MAX_SLOTS,
    ROUND_TRIP_COST,
    STATEMENT_LAG_DAYS,
)
from app.evaluate import compose
from app.exits import OpenPosition, blocking_filing, close_at, plan_exit, position_size, step_position
from app.flow import flow_flipped, flow_gate
from app.pattern import Pattern, assess_pattern, atr, ma_now, market_regime

FlowMap = dict[str, list[tuple[str, float]]]


@dataclass
class Slot:
    """An open slot of the backtest book: the plan plus how much cash it holds."""

    position: OpenPosition
    notional: float
    score: int = 0

    def value(self) -> float:
        return self.notional * (1 + self.position.unrealised())


def _slice(bars: list[dict], as_of: str) -> list[dict]:
    return [bar for bar in bars if bar["trade_date"] <= as_of]


def _slice_flow(points: FlowMap, as_of: str) -> FlowMap:
    return {
        code: [(day, value) for day, value in series if day <= as_of]
        for code, series in points.items()
    }


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


def _drawdown(curve: list[tuple[str, float]]) -> float:
    peak = 0.0
    worst = 0.0
    for _day, value in curve:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return worst


def _trade(slot: Slot, position: OpenPosition) -> dict:
    return {
        "symbol": position.symbol,
        "entry": position.entry_date,
        "exit": position.exit_date,
        "entry_price": position.entry_price,
        "exit_price": position.exit_price,
        "sessions": position.sessions,
        "reason": position.exit_reason,
        "return_pct": position.realised_return(),
        "score": slot.score,
    }


def _close_slot(slot: Slot, bar: dict, reason: str, cash: float, side_cost: float) -> float:
    """Close at the bar close and return the cash the slot hands back."""
    close_at(slot.position, bar, reason)
    return cash + slot.notional * (1 + slot.position.realised_return()) * (1 - side_cost)


def _candidates(
    trade_date: str,
    as_of: date,
    index_slice: list[dict],
    regime,
    bars_by_symbol: dict[str, list[dict]],
    ratios_by_symbol: dict[str, dict[str, list[tuple[str, float]]]],
    articles_by_symbol: dict[str, list[dict]],
    flow_by_symbol: dict[str, FlowMap],
    exchanges: dict[str, str],
    held: set[str],
) -> list[tuple[int, int, str, float, Pattern]]:
    found: list[tuple[int, int, str, float, Pattern]] = []
    for symbol, stock_bars in bars_by_symbol.items():
        if symbol in held:
            continue
        stock_slice = _slice(stock_bars, trade_date)
        if len(stock_slice) < 61:
            continue
        pattern = assess_pattern(stock_slice, index_slice, exchanges.get(symbol))
        flow_points = _slice_flow(flow_by_symbol.get(symbol, {}), trade_date)
        verdict = compose(
            symbol,
            as_of,
            _lag_ratios(ratios_by_symbol.get(symbol, {}), as_of, STATEMENT_LAG_DAYS),
            articles_by_symbol.get(symbol, []),
            regime,
            pattern,
            require_clock=False,
            flow=flow_gate(flow_points, stock_slice),
        )
        price = float(stock_slice[-1]["close"])
        if verdict.status != "Được vào" or not verdict.stop_price:
            continue
        if verdict.stop_price >= price:
            continue
        found.append((verdict.score, verdict.priority, symbol, price, pattern))
    return found


def run_backtest(
    index_bars: list[dict],
    bars_by_symbol: dict[str, list[dict]],
    ratios_by_symbol: dict[str, dict[str, list[tuple[str, float]]]],
    articles_by_symbol: dict[str, list[dict]],
    exchanges: dict[str, str] | None = None,
    flow_by_symbol: dict[str, FlowMap] | None = None,
) -> dict:
    """A book of MAX_SLOTS equal-risk slots, each with its own exit plan.

    Statements are used 45 days after period end. The news clock is skipped because old
    filings are not kept long enough. Two live gates are deliberately absent:

    * the P/E ceiling, because the market database holds one snapshot, not a history;
    * the macro layer, because Yahoo only serves a few months of cross-market history.
    """
    if len(index_bars) < MA_WINDOW + 5:
        return {"error": f"Chưa đủ nến VN-Index. Cần hơn {MA_WINDOW} phiên."}

    dates = [bar["trade_date"] for bar in index_bars][MA_WINDOW:]
    side_cost = ROUND_TRIP_COST / 2
    cash = 1.0
    slots: list[Slot] = []
    trades: list[dict] = []
    curve: list[tuple[str, float]] = []
    previous_day: date | None = None

    for trade_date in dates:
        as_of = date.fromisoformat(trade_date)
        index_slice = _slice(index_bars, trade_date)
        regime = market_regime(index_slice)

        # 1. Manage the slots that were opened on an earlier session.
        for slot in list(slots):
            position = slot.position
            stock_slice = _slice(bars_by_symbol.get(position.symbol, []), trade_date)
            if not stock_slice:
                continue
            bar = stock_slice[-1]
            filing = blocking_filing(
                articles_by_symbol.get(position.symbol, []), position.entry_date
            )
            flow_points = _slice_flow((flow_by_symbol or {}).get(position.symbol, {}), trade_date)
            if filing:
                close_at(position, bar, f"Công bố chặn: {filing}")
            elif flow_flipped(flow_points, stock_slice):
                close_at(position, bar, "Dòng tiền ngoại đảo chiều")
            else:
                step_position(
                    position,
                    bar,
                    ma20=ma_now(stock_slice, MA_FAST),
                    atr14=atr(stock_slice),
                )
            if not position.open:
                cash = _close_slot(slot, bar, position.exit_reason or "Đóng", cash, side_cost)
                trades.append(_trade(slot, position))
                slots.remove(slot)

        # 2. Cash earns the deposit rate between sessions.
        if previous_day is not None:
            gap_days = (as_of - previous_day).days
            if gap_days > 0:
                cash *= (1 + CASH_YIELD) ** (gap_days / 365)
        previous_day = as_of

        # 3. Fill free slots with the best ranked names.
        if regime.open and len(slots) < MAX_SLOTS:
            held = {slot.position.symbol for slot in slots}
            found = _candidates(
                trade_date,
                as_of,
                index_slice,
                regime,
                bars_by_symbol,
                ratios_by_symbol,
                articles_by_symbol,
                flow_by_symbol or {},
                exchanges or {},
                held,
            )
            ranked = sorted(found, key=lambda item: (-item[0], -item[1], item[2]))
            for score, _priority, symbol, price, pattern in ranked[: MAX_SLOTS - len(slots)]:
                equity = cash + sum(slot.value() for slot in slots)
                wanted = position_size(equity, price, pattern.stop or 0.0)
                spend = min(wanted, cash)
                if spend <= 0:
                    continue
                stock_slice = _slice(bars_by_symbol.get(symbol, []), trade_date)
                position = plan_exit(symbol, trade_date, price, pattern, atr(stock_slice))
                slots.append(Slot(position=position, notional=spend * (1 - side_cost), score=score))
                cash -= spend

        curve.append((trade_date, cash + sum(slot.value() for slot in slots)))

    # 4. Close whatever is still open so the measurement covers the whole window.
    for slot in list(slots):
        stock_slice = _slice(bars_by_symbol.get(slot.position.symbol, []), dates[-1])
        if not stock_slice:
            continue
        bar = stock_slice[-1]
        cash = _close_slot(slot, bar, "Hết cửa sổ đo", cash, side_cost)
        trades.append(_trade(slot, slot.position))
        slots.remove(slot)
    if curve:
        curve[-1] = (curve[-1][0], cash)

    if not curve:
        return {"error": "Không có phiên nào sau khi MA200 đã đủ dữ liệu."}

    start_index = index_bars[MA_WINDOW]["close"]
    end_index = index_bars[-1]["close"]
    index_return = end_index / start_index - 1 if start_index else 0.0
    strategy_return = cash - 1
    wins = [trade for trade in trades if (trade["return_pct"] or 0) > 0]
    exits: dict[str, int] = {}
    for trade in trades:
        key = trade["reason"] or "Khác"
        exits[key] = exits.get(key, 0) + 1
    average_sessions = sum(trade["sessions"] for trade in trades) / len(trades) if trades else None
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
        "win_rate": (len(wins) / len(trades)) if trades else None,
        "average_sessions": average_sessions,
        "max_drawdown": _drawdown(curve),
        "exit_counts": sorted(exits.items(), key=lambda item: -item[1]),
        "slots": MAX_SLOTS,
        "assumptions": (
            f"{MAX_SLOTS} suất vốn, mỗi suất rủi ro 1% vốn chủ khi vào. "
            f"Phí cả vòng {ROUND_TRIP_COST * 100:.2f}%. "
            f"Lãi tiền gửi {CASH_YIELD * 100:.1f}%/năm trên tiền đang đứng ngoài. "
            f"Số liệu quý được dùng {STATEMENT_LAG_DAYS} ngày sau ngày kết thúc kỳ. "
            "Dừng lỗ theo đáy nền, kéo theo MA20 sau khi chốt một phần tại +1R, đóng khi "
            "tiền chết 30 phiên, có công bố chặn, hoặc dòng tiền ngoại đảo chiều. "
            "Cổng P/E và lớp vĩ mô không dùng ở đây vì dữ liệu chỉ có ảnh chụp hiện tại."
        ),
    }
