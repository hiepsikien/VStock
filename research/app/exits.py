from __future__ import annotations

from dataclasses import dataclass

from app.config import (
    ATR_STOP_MULTIPLIER,
    FAILED_BREAKOUT_ATR_BUFFER,
    FAILED_BREAKOUT_SESSIONS,
    MAX_HOLD_SESSIONS,
    MAX_POSITION_WEIGHT,
    RISK_PER_TRADE,
    ROUND_TRIP_COST,
    TIME_STOP_SESSIONS,
    TP1_FRACTION,
    TP1_R_MULTIPLE,
    TRAIL_ATR_MULTIPLIER,
)
from app.pattern import Pattern

BLOCK_KINDS = frozenset({"suspension", "audit_exception"})
FALLBACK_STOP = 0.93


@dataclass
class OpenPosition:
    """One slot of the book. The backtest and the paper ledger share this state."""

    symbol: str
    entry_date: str
    entry_price: float
    stop: float
    initial_stop: float
    target1: float
    weight: float = 0.0
    atr14: float | None = None
    sessions: int = 0
    tp1_done: bool = False
    booked_fraction: float = 0.0
    realised: float = 0.0
    last_price: float | None = None
    last_date: str | None = None
    exit_date: str | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    # Trần nền lúc vào lệnh. Trong vài phiên đầu, đóng cửa vào hẳn dưới mốc này thì cú phá hỏng.
    base_ceiling: float | None = None

    @property
    def open(self) -> bool:
        return self.exit_reason is None

    def unrealised(self) -> float:
        """Mark-to-market return on the slot, after the part already booked at TP1."""
        reference = self.last_price if self.last_price is not None else self.entry_price
        return self.realised + (1 - self.booked_fraction) * (reference / self.entry_price - 1)

    def realised_return(self) -> float:
        if self.exit_price is None:
            return self.unrealised()
        return self.realised + (1 - self.booked_fraction) * (self.exit_price / self.entry_price - 1)


def plan_exit(
    symbol: str,
    entry_date: str,
    entry_price: float,
    pattern: Pattern | None = None,
    atr_value: float | None = None,
    weight: float = 0.0,
) -> OpenPosition:
    """Stop below the base or two ATR, whichever the data supports. TP1 sits one R away."""
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if pattern is not None and pattern.stop and pattern.stop < entry_price:
        stop = float(pattern.stop)
    elif atr_value and atr_value > 0:
        stop = entry_price - ATR_STOP_MULTIPLIER * atr_value
    else:
        stop = entry_price * FALLBACK_STOP
    risk = entry_price - stop
    return OpenPosition(
        symbol=symbol,
        entry_date=entry_date,
        entry_price=entry_price,
        stop=stop,
        initial_stop=stop,
        target1=entry_price + TP1_R_MULTIPLE * risk,
        weight=weight,
        atr14=atr_value,
        base_ceiling=float(pattern.base_ceiling) if pattern and pattern.base_ceiling else None,
    )


def _close(pos: OpenPosition, bar: dict, reason: str, price: float) -> str:
    pos.exit_date = str(bar.get("trade_date") or pos.last_date or "")
    pos.exit_price = price
    pos.exit_reason = reason
    pos.last_price = price
    if pos.exit_date:
        pos.last_date = pos.exit_date
    return reason


def mark_bar(pos: OpenPosition, bar: dict) -> None:
    """Mark one session on the slot, before any rule reads it.

    Every session the slot is exposed to counts, including the one a close-based exit books
    it on, so the ledger's session count follows the calendar and not the exit rule.
    """
    pos.sessions += 1
    pos.last_price = float(bar["close"])
    pos.last_date = str(bar.get("trade_date") or "")


def step_position(
    pos: OpenPosition,
    bar: dict,
    *,
    ma20: float | None = None,
    atr14: float | None = None,
) -> str | None:
    """Advance one D1 session. Returns the exit reason, or None while the slot stays open.

    The stop is checked before the target, so a bar that touches both is booked as a loss.
    """
    mark_bar(pos, bar)
    return manage_position(pos, bar, ma20=ma20, atr14=atr14)


def manage_position(
    pos: OpenPosition,
    bar: dict,
    *,
    ma20: float | None = None,
    atr14: float | None = None,
) -> str | None:
    """Judge a session that has already been marked: stop, target, trailing stop, clock.

    The callers mark the bar first: the news, flow and base-ceiling exits read the same
    session and have to leave the same session count behind them as the stop does.
    """
    # The level a low has to reach is the one that rested in the book for this whole session.
    session_stop = pos.stop
    if float(bar["low"]) <= session_stop:
        return _close(pos, bar, "Chạm dừng lỗ", min(float(bar["open"]), session_stop))

    if not pos.tp1_done and float(bar["high"]) >= pos.target1:
        pos.tp1_done = True
        pos.booked_fraction = TP1_FRACTION
        pos.realised = TP1_FRACTION * (pos.target1 / pos.entry_price - 1)
        pos.stop = max(pos.stop, pos.entry_price * (1 + ROUND_TRIP_COST))

    # MA20 and ATR of this session are only known once it has closed, so a level drawn from them
    # can only watch the sessions after this one. Raising the stop before reading the low would
    # book an exit at min(open, new stop) on a session whose low never reached the resting stop.
    if pos.tp1_done and ma20 is not None and atr14:
        candidate = ma20 - TRAIL_ATR_MULTIPLIER * atr14
        if candidate > pos.stop:
            pos.stop = candidate

    if pos.sessions >= MAX_HOLD_SESSIONS:
        return _close(pos, bar, f"Đủ {MAX_HOLD_SESSIONS} phiên", float(bar["close"]))
    if not pos.tp1_done and pos.sessions >= TIME_STOP_SESSIONS:
        return _close(pos, bar, f"Tiền chết {TIME_STOP_SESSIONS} phiên", float(bar["close"]))
    return None


def close_at(pos: OpenPosition, bar: dict, reason: str) -> str:
    """Force an exit at the close, used by the news and flow overrides."""
    return _close(pos, bar, reason, float(bar["close"]))


def fell_under_base(pos: OpenPosition, bar: dict, *, atr14: float | None = None) -> bool:
    """A close back inside the base during the first few sessions ends the breakout.

    The ceiling is the base high captured at entry, so a later base cannot lift it. The rule
    only runs for FAILED_BREAKOUT_SESSIONS after entry, and only when the close is at least
    half an ATR under that ceiling. A close that merely tags the level holds. After the
    window, the base-low stop and the trail take over.

    The bar must already be marked, so the session count matches the other exits. The ATR is
    the one known at this close, falling back to the ATR stored at entry. Without one, the
    distance cannot be measured and the rule stays quiet.

    A bar that also takes out the stop is left to the stop: that order rests in the market
    and fills inside the bar, and its fill is never better than the close this rule would
    book, so letting the stop win only ever reads as the more cautious of the two.
    """
    if pos.sessions < 1 or pos.sessions > FAILED_BREAKOUT_SESSIONS:
        return False
    if pos.base_ceiling is None or pos.base_ceiling <= 0:
        return False
    if float(bar["low"]) <= pos.stop:
        return False
    volatility = atr14 if atr14 and atr14 > 0 else pos.atr14
    if volatility is None or volatility <= 0:
        return False
    inside = pos.base_ceiling - FAILED_BREAKOUT_ATR_BUFFER * volatility
    if float(bar["close"]) > inside:
        return False
    close_at(pos, bar, f"Đóng dưới đỉnh nền {pos.base_ceiling:.2f}")
    return True


def blocking_filing(
    articles: list[dict],
    after_date: str,
    until_date: str | None = None,
) -> str | None:
    """A suspension or an audit exception published after entry ends the thesis.

    `until_date` is the session being processed. Without it a walk through history would
    read a filing published years later and close the slot on the very next bar.
    """
    for article in articles:
        published = str(article.get("published_at") or "")[:10]
        if published <= after_date:
            continue
        if until_date is not None and published > until_date:
            continue
        if article.get("kind") in BLOCK_KINDS:
            return str(article.get("title") or "Công bố rủi ro")
    return None


def position_size(
    equity: float,
    entry_price: float,
    stop: float,
    weight_cap: float = MAX_POSITION_WEIGHT,
) -> float:
    """Risk one percent of equity per slot, capped by a maximum weight."""
    if equity <= 0 or entry_price <= 0:
        return 0.0
    distance = entry_price - stop
    if distance <= 0:
        return 0.0
    risk_budget = equity * RISK_PER_TRADE
    notional = risk_budget / distance * entry_price
    return min(notional, equity * weight_cap)
