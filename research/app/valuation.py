"""Market cap and trailing P/E from prices and statements already in the store.

Shares and profit become visible 45 days after the period ends, the same lag the
fundamental score uses. A non-positive trailing profit has no P/E.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.config import STATEMENT_LAG_DAYS


def _visible(series: list[tuple[str, float]], as_of: date, lag_days: int) -> list[tuple[str, float]]:
    kept = []
    for report, value in series:
        try:
            report_day = date.fromisoformat(report)
        except ValueError:
            continue
        if report_day + timedelta(days=lag_days) <= as_of:
            kept.append((report, value))
    kept.sort()
    return kept


def market_cap(
    close: float,
    share_points: list[tuple[str, float]],
    as_of: date,
    *,
    lag_days: int = STATEMENT_LAG_DAYS,
) -> float | None:
    visible = _visible(share_points, as_of, lag_days)
    if not visible or close <= 0:
        return None
    shares = visible[-1][1]
    if shares <= 0:
        return None
    return close * shares


def trailing_profit(
    profit_points: list[tuple[str, float]],
    as_of: date,
    *,
    lag_days: int = STATEMENT_LAG_DAYS,
    quarters: int = 4,
) -> float | None:
    visible = _visible(profit_points, as_of, lag_days)
    if len(visible) < quarters:
        return None
    total = sum(value for _day, value in visible[-quarters:])
    if total <= 0:
        return None
    return total


def trailing_pe(cap: float | None, profit: float | None) -> float | None:
    if cap is None or profit is None or profit <= 0:
        return None
    return cap / profit


def daily_valuation(
    bars: list[dict],
    share_points: list[tuple[str, float]],
    profit_points: list[tuple[str, float]],
) -> list[tuple[str, float | None, float | None]]:
    """One market cap and trailing P/E per session, using statements already public that day."""
    rows = []
    for bar in bars:
        as_of = date.fromisoformat(str(bar["trade_date"]))
        cap = market_cap(float(bar["close"]), share_points, as_of)
        profit = trailing_profit(profit_points, as_of)
        rows.append((str(bar["trade_date"]), cap, trailing_pe(cap, profit)))
    return rows


def cheap_versus(current: float | None, baseline: float | None) -> float | None:
    """Below 1 means cheaper than the baseline. Missing numbers stay missing."""
    if current is None or baseline is None or baseline <= 0 or current <= 0:
        return None
    return current / baseline
