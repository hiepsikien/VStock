from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.config import (
    CASH_YIELD,
    DEFAULT_UNIVERSE,
    INDUSTRY_GATE_ENFORCED,
    INDUSTRY_HOLD_ENABLED,
    MA_FAST,
    MA_WINDOW,
    MAX_SLOTS,
    ROUND_TRIP_COST,
    STATEMENT_LAG_DAYS,
    STOCK_SHORTLIST_ENFORCED,
)
from app.industries import industry_of, set_industry_map
from app.evaluate import compose
from app.exits import (
    OpenPosition,
    blocking_filing,
    close_at,
    fell_under_base,
    manage_position,
    mark_bar,
    plan_exit,
    position_size,
)
from app.flow import flow_flipped, flow_gate
from app.pattern import Pattern, assess_pattern, atr, ma_now, market_regime, session_bar

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


def _settle_slot(slot: Slot, cash: float, side_cost: float) -> float:
    """Return the cash a closed slot hands back, at the price its exit already set."""
    return cash + slot.notional * (1 + slot.position.realised_return()) * (1 - side_cost)


def _close_slot(slot: Slot, bar: dict, reason: str, cash: float, side_cost: float) -> float:
    """Force an exit at the bar close and settle the slot, used when the window ends."""
    close_at(slot.position, bar, reason)
    return _settle_slot(slot, cash, side_cost)


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
    open_map: dict[tuple[str, str], bool] | None = None,
    shortlist: set[tuple[str, str]] | None = None,
    enforce_industry: bool = False,
) -> list[tuple[int, int, str, float, Pattern]]:
    found: list[tuple[int, int, str, float, Pattern]] = []
    for symbol, stock_bars in bars_by_symbol.items():
        if symbol in held:
            continue
        # A name with no state for the session is outside that year's basket, so it stays out too.
        if enforce_industry and open_map is not None and open_map.get((symbol, trade_date)) is not True:
            continue
        stock_slice = _slice(stock_bars, trade_date)
        if len(stock_slice) < 61:
            continue
        # A name with no bar of its own this session is not a candidate: it would be bought at
        # yesterday's close with today's date on the position.
        if session_bar(stock_slice, trade_date) is None:
            continue
        pattern = assess_pattern(stock_slice, index_slice, exchanges.get(symbol))
        flow_points = _slice_flow(flow_by_symbol.get(symbol, {}), trade_date)
        industry_open = None if open_map is None else open_map.get((symbol, trade_date))
        verdict = compose(
            symbol,
            as_of,
            _lag_ratios(ratios_by_symbol.get(symbol, {}), as_of, STATEMENT_LAG_DAYS),
            articles_by_symbol.get(symbol, []),
            regime,
            pattern,
            require_clock=False,
            flow=flow_gate(flow_points, stock_slice),
            industry_name=industry_of(symbol),
            industry_open=industry_open,
        )
        if STOCK_SHORTLIST_ENFORCED and shortlist is not None and (symbol, trade_date) not in shortlist:
            continue
        price = float(stock_slice[-1]["close"])
        if verdict.status != "Được vào" or not verdict.stop_price:
            continue
        if verdict.stop_price >= price:
            continue
        found.append((verdict.score, verdict.priority, symbol, price, pattern))
    return found


def run_backtest_with_industries(industries: dict[str, str], *inputs) -> dict:
    """`run_backtest` in a worker process, which starts without the industry table attached."""
    set_industry_map(industries)
    return run_backtest(*inputs)


def run_backtest(
    index_bars: list[dict],
    bars_by_symbol: dict[str, list[dict]],
    ratios_by_symbol: dict[str, dict[str, list[tuple[str, float]]]],
    articles_by_symbol: dict[str, list[dict]],
    exchanges: dict[str, str] | None = None,
    flow_by_symbol: dict[str, FlowMap] | None = None,
    market_points: dict[str, list[tuple[str, float]]] | None = None,
    open_map: dict[tuple[str, str], bool] | None = None,
    enforce_industry: bool = False,
    breadth_open: dict[str, bool | None] | None = None,
) -> dict:
    """A book of MAX_SLOTS equal-risk slots, each with its own exit plan.

    `breadth_open` adds the breadth gate next to the MA200 gate: a session whose state is not
    True opens nothing, an unscored session included.

    Statements are used 45 days after period end. The news clock is skipped because old
    filings are not kept long enough. Two live gates are deliberately absent:

    * the P/E ceiling, because the market database holds one snapshot, not a history;
    * the macro layer, because Yahoo only serves a few months of cross-market history.
    """
    if len(index_bars) < MA_WINDOW + 5:
        return {"error": f"Chưa đủ nến VN-Index. Cần hơn {MA_WINDOW} phiên."}

    dates = [bar["trade_date"] for bar in index_bars][MA_WINDOW:]
    if open_map is None and (INDUSTRY_GATE_ENFORCED or INDUSTRY_HOLD_ENABLED):
        from app.industry_screen import build_open_map, credit_by_day, lead_bars_from

        open_map = build_open_map(
            index_bars,
            bars_by_symbol,
            list(DEFAULT_UNIVERSE),
            lead_bars=lead_bars_from(market_points or {}),
            credit_by_day=credit_by_day(
                ratios_by_symbol, [str(bar["trade_date"]) for bar in index_bars]
            ),
        )
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

        # 1. Cash earns the deposit rate over the night before this session. The rate is
        #    applied to the balance that was already out of the market, so the proceeds of
        #    a slot that closes today — still in the stock overnight — do not earn it.
        if previous_day is not None:
            gap_days = (as_of - previous_day).days
            if gap_days > 0:
                cash *= (1 + CASH_YIELD) ** (gap_days / 365)
        previous_day = as_of

        # 2. Manage the slots that were opened on an earlier session.
        for slot in list(slots):
            position = slot.position
            stock_slice = _slice(bars_by_symbol.get(position.symbol, []), trade_date)
            bar = session_bar(stock_slice, trade_date)
            if bar is None:
                # The name has no bar of this session, so there is nothing to judge it on.
                continue
            mark_bar(position, bar)
            # Only a filing already published on this session may end the thesis; without
            # the upper bound a future suspension would close the slot on the next bar.
            filing = blocking_filing(
                articles_by_symbol.get(position.symbol, []),
                position.entry_date,
                str(bar["trade_date"]),
            )
            flow_points = _slice_flow((flow_by_symbol or {}).get(position.symbol, {}), trade_date)
            if filing:
                close_at(position, bar, f"Công bố chặn: {filing}")
            elif flow_flipped(flow_points, stock_slice):
                close_at(position, bar, "Dòng tiền ngoại đảo chiều")
            elif (
                INDUSTRY_HOLD_ENABLED
                and open_map is not None
                and open_map.get((position.symbol, trade_date)) is False
            ):
                close_at(position, bar, "Ngành đóng")
            elif fell_under_base(position, bar):
                pass  # Already closed at this bar's close, with the reason on the position.
            else:
                manage_position(
                    position,
                    bar,
                    ma20=ma_now(stock_slice, MA_FAST),
                    atr14=atr(stock_slice),
                )
            if not position.open:
                # The exit already set its own price — a stop fills at min(open, stop) —
                # so settling must not overwrite it with the bar close.
                cash = _settle_slot(slot, cash, side_cost)
                trades.append(_trade(slot, position))
                slots.remove(slot)

        # 3. Fill free slots with the best ranked names.
        breadth_ok = breadth_open is None or breadth_open.get(trade_date) is True
        if regime.open and breadth_ok and len(slots) < MAX_SLOTS:
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
                open_map,
                enforce_industry=enforce_industry,
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
        "curve": curve,
        "slots": MAX_SLOTS,
        "assumptions": (
            f"{MAX_SLOTS} suất vốn, mỗi suất rủi ro 1% vốn chủ khi vào. "
            f"Phí cả vòng {ROUND_TRIP_COST * 100:.2f}%. "
            f"Lãi tiền gửi {CASH_YIELD * 100:.1f}%/năm trên tiền đang đứng ngoài. "
            f"Số liệu quý được dùng {STATEMENT_LAG_DAYS} ngày sau ngày kết thúc kỳ. "
            "Dừng lỗ theo đáy nền, kéo theo MA20 sau khi chốt một phần tại +1R, đóng khi "
            "tiền chết 30 phiên, có công bố chặn, dòng tiền ngoại đảo chiều, hoặc giá "
            "đóng cửa trở lại dưới đỉnh nền đã phá. "
            "Cổng P/E và lớp vĩ mô không dùng ở đây vì dữ liệu chỉ có ảnh chụp hiện tại."
        ),
    }
