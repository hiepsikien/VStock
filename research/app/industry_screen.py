"""Whether an industry is open, using only information through the previous session."""

from __future__ import annotations

from datetime import date, timedelta

from app.config import BANKS, STATEMENT_LAG_DAYS
from app.industries import (
    CREDIT_INDUSTRIES,
    INDUSTRY_WINDOW,
    LEAD_SERIES,
    MIN_INDUSTRY_NAMES,
    REGIME_INDUSTRIES,
    gated_industries,
    industry_of,
    members,
)


def compound(returns: list[float]) -> float | None:
    if len(returns) < INDUSTRY_WINDOW:
        return None
    window = returns[-INDUSTRY_WINDOW:]
    value = 1.0
    for item in window:
        value *= 1.0 + item
    return value - 1.0


def member_returns(closes: list[float]) -> list[float]:
    out = []
    for previous, current in zip(closes, closes[1:]):
        if previous <= 0:
            out.append(0.0)
        else:
            out.append(current / previous - 1.0)
    return out


def industry_session_returns(member_closes: list[list[float]]) -> list[float]:
    """Equal-weight daily return. A name with no close that session is left out of the average."""
    series = [member_returns(closes) for closes in member_closes if len(closes) >= 2]
    if not series:
        return []
    length = min(len(item) for item in series)
    trimmed = [item[-length:] for item in series]
    out = []
    for index in range(length):
        values = [item[index] for item in trimmed]
        out.append(sum(values) / len(values))
    return out


def is_open(
    industry: str,
    universe: list[str],
    *,
    excess: float | None,
    lead_return: float | None,
    credit_growth: float | None,
    regime_open: bool | None,
) -> bool | None:
    """True when the industry wave is open. None when the group is too small to be a wave."""
    if len(members(industry, universe)) < MIN_INDUSTRY_NAMES:
        return None
    if excess is None or excess <= 0:
        return False
    if industry in LEAD_SERIES and (lead_return is None or lead_return <= 0):
        return False
    if industry in CREDIT_INDUSTRIES and (credit_growth is None or credit_growth <= 0):
        return False
    if industry in REGIME_INDUSTRIES and regime_open is not True:
        return False
    return True


def name_allowed(symbol: str, universe: list[str], industry_open: bool | None, regime_open: bool | None) -> bool:
    """A gated industry must be open. A thin label only needs the domestic regime."""
    industry = industry_of(symbol)
    if industry is None:
        return regime_open is True
    if len(members(industry, universe)) < MIN_INDUSTRY_NAMES:
        return regime_open is True
    return industry_open is True


SCREEN_START = "2021-01-01"
SCREEN_END = "2024-12-31"
# Số cổ phiếu lưu hành trước 2023 được bổ sung từ vốn góp của chủ sở hữu trong BCTC quý.
# Cửa sổ đo chạy từ phiên đầu tiên vốn hóa đã biết.
OPERABLE_START = "2021-01-04"
CONFIRM_START = "2025-01-01"
CONFIRM_END = "2026-10-09"
MIN_RECALL = 0.60
MIN_PRECISION_MULTIPLE = 2.0
MIN_CLOSED_TRADES = 30
MIN_STOCK_RECALL = 0.50
RUN_WINDOW = 66
RUN_RETURN = 0.20
EARLY_CAP = 0.15


def dated_returns(bars: list[dict]) -> list[tuple[str, float]]:
    out = []
    for previous, current in zip(bars, bars[1:]):
        before = float(previous["close"])
        after = float(current["close"])
        change = 0.0 if before <= 0 else after / before - 1.0
        out.append((str(current["trade_date"]), change))
    return out


def average_by_day(series_list: list[list[tuple[str, float]]]) -> list[tuple[str, float]]:
    buckets: dict[str, list[float]] = {}
    for series in series_list:
        for day, value in series:
            buckets.setdefault(day, []).append(value)
    return [(day, sum(values) / len(values)) for day, values in sorted(buckets.items())]


def rolling_compound(series: list[tuple[str, float]], window: int = INDUSTRY_WINDOW) -> dict[str, float]:
    """Compound return of the last `window` observations, known at that session's close."""
    if window <= 0:
        return {}
    prefix = [1.0]
    days = []
    for day, value in series:
        prefix.append(prefix[-1] * (1.0 + value))
        days.append(day)
    out = {}
    for index in range(window - 1, len(days)):
        out[days[index]] = prefix[index + 1] / prefix[index + 1 - window] - 1.0
    return out


def previous_session(days: list[str], day: str) -> str | None:
    earlier = [item for item in days if item < day]
    return earlier[-1] if earlier else None


def lead_bars_from(market_points: dict[str, list[tuple[str, float]]]) -> dict[str, list[dict]]:
    """The lead series build_open_map reads, in bar shape, from the stored market points."""
    return {
        name: [{"trade_date": day, "close": value} for day, value in market_points.get(name, [])]
        for name in set(LEAD_SERIES.values())
    }


def credit_by_day(
    ratios_by_symbol: dict[str, dict[str, list[tuple[str, float]]]],
    days: list[str],
) -> dict[str, float | None]:
    """Median bank loan growth each session, from statements visible STATEMENT_LAG_DAYS after period end."""
    series = []
    for bank in BANKS:
        points = (ratios_by_symbol.get(bank) or {}).get("CUSTOMER_LOANS_AQ_GRYOY") or []
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


def build_open_map(
    index_bars: list[dict],
    bars_by_symbol: dict[str, list[dict]],
    universe: list[str],
    *,
    lead_bars: dict[str, list[dict]] | None = None,
    credit_by_day: dict[str, float | None] | None = None,
    regime_by_day: dict[str, bool | None] | None = None,
    window: int = INDUSTRY_WINDOW,
) -> dict[tuple[str, str], bool]:
    """Whether each name is allowed on a session, using the window that ended yesterday.

    Without lead_bars and credit_by_day the lead and credit industries can never open, so every
    caller has to pass both, built by lead_bars_from and credit_by_day.
    """
    from app.pattern import market_regime

    index_days = [str(bar["trade_date"]) for bar in index_bars]
    index_roll = rolling_compound(dated_returns(index_bars), window)
    if regime_by_day is None:
        regime_by_day = {}
        for index, day in enumerate(index_days):
            regime_by_day[day] = market_regime(index_bars[: index + 1]).open
    lead_roll = {}
    for industry, series_name in LEAD_SERIES.items():
        bars = (lead_bars or {}).get(series_name) or []
        if bars and "close" in bars[0]:
            lead_roll[industry] = rolling_compound(dated_returns(bars), window)
        elif bars:
            lead_roll[industry] = rolling_compound(
                [(str(day), float(value)) for day, value in bars], window
            )
    industry_roll = {}
    for industry in gated_industries(universe):
        series = [
            dated_returns(bars_by_symbol[symbol])
            for symbol in members(industry, universe)
            if symbol in bars_by_symbol
        ]
        industry_roll[industry] = rolling_compound(average_by_day(series), window)

    allowed: dict[tuple[str, str], bool] = {}
    for day in index_days:
        yesterday = previous_session(index_days, day)
        regime_open = regime_by_day.get(yesterday) if yesterday else None
        credit = (credit_by_day or {}).get(yesterday) if yesterday else None
        index_return = index_roll.get(yesterday) if yesterday else None
        open_by_industry: dict[str, bool | None] = {}
        for industry, rolled in industry_roll.items():
            own = rolled.get(yesterday) if yesterday else None
            excess = None if own is None or index_return is None else own - index_return
            lead_return = None
            if industry in LEAD_SERIES:
                lead_return = lead_roll.get(industry, {}).get(yesterday) if yesterday else None
            open_by_industry[industry] = is_open(
                industry,
                universe,
                excess=excess,
                lead_return=lead_return,
                credit_growth=credit,
                regime_open=regime_open,
            )
        for symbol in universe:
            industry = industry_of(symbol)
            allowed[(symbol, day)] = name_allowed(
                symbol,
                universe,
                open_by_industry.get(industry) if industry else None,
                regime_open,
            )
    return allowed


def find_runs(bars: list[dict], start: str, end: str) -> list[tuple[str, int, float]]:
    """Non-overlapping 66-session runs of at least 20%, greedy by return. Start day must fall in range."""
    closes = [float(bar["close"]) for bar in bars]
    days = [str(bar["trade_date"]) for bar in bars]
    candidates = []
    for index, day in enumerate(days):
        if day < start or day > end or index + RUN_WINDOW >= len(closes):
            continue
        base = closes[index]
        if base <= 0:
            continue
        change = closes[index + RUN_WINDOW] / base - 1.0
        if change >= RUN_RETURN:
            candidates.append((change, index, day))
    candidates.sort(reverse=True)
    used: set[int] = set()
    chosen = []
    for change, index, day in candidates:
        span = set(range(index, index + RUN_WINDOW + 1))
        if span & used:
            continue
        used |= span
        chosen.append((day, index, change))
    chosen.sort()
    return chosen


def early_days(bars: list[dict], start_index: int) -> list[str]:
    closes = [float(bar["close"]) for bar in bars]
    days = [str(bar["trade_date"]) for bar in bars]
    base = closes[start_index]
    found = []
    for offset in range(RUN_WINDOW):
        index = start_index + offset
        if index >= len(closes):
            break
        if base > 0 and closes[index] / base - 1.0 > EARLY_CAP:
            break
        found.append(days[index])
    return found


def layer_counts(
    bars_by_symbol: dict[str, list[dict]],
    open_on,
    start: str,
    end: str,
    active=None,
) -> dict[str, float]:
    """Recall of runs and precision of open symbol-days. `open_on(symbol, day)` is the rule.

    `active(symbol, day)` drops sessions the name was not in that year's list.
    """
    runs = 0
    caught = 0
    open_days = 0
    open_hits = 0
    for symbol, bars in bars_by_symbol.items():
        closes = [float(bar["close"]) for bar in bars]
        days = [str(bar["trade_date"]) for bar in bars]
        for day, index, _change in find_runs(bars, start, end):
            if active is not None and not active(symbol, day):
                continue
            runs += 1
            if any(open_on(symbol, early) for early in early_days(bars, index)):
                caught += 1
        for index, day in enumerate(days):
            if day < start or day > end or not open_on(symbol, day):
                continue
            if index + RUN_WINDOW >= len(closes) or closes[index] <= 0:
                continue
            open_days += 1
            if closes[index + RUN_WINDOW] / closes[index] - 1.0 >= RUN_RETURN:
                open_hits += 1
    always_days = 0
    always_hits = 0
    for symbol, bars in bars_by_symbol.items():
        closes = [float(bar["close"]) for bar in bars]
        days = [str(bar["trade_date"]) for bar in bars]
        for index, day in enumerate(days):
            if day < start or day > end or index + RUN_WINDOW >= len(closes) or closes[index] <= 0:
                continue
            always_days += 1
            if closes[index + RUN_WINDOW] / closes[index] - 1.0 >= RUN_RETURN:
                always_hits += 1
    return {
        "runs": runs,
        "recall": (caught / runs) if runs else 0.0,
        "precision": (open_hits / open_days) if open_days else 0.0,
        "baseline": (always_hits / always_days) if always_days else 0.0,
        "open_days": open_days,
    }


def passes_stock(recall_screen: float, recall_confirm: float, edge_screen: float, edge_confirm: float) -> bool:
    return (
        recall_screen >= MIN_STOCK_RECALL
        and recall_confirm >= MIN_STOCK_RECALL
        and edge_screen > 0
        and edge_confirm > 0
    )


def passes_layer(
    recall_screen: float,
    precision_screen: float,
    baseline_screen: float,
    recall_confirm: float,
    precision_confirm: float,
    baseline_confirm: float,
) -> bool:
    if recall_screen < MIN_RECALL or recall_confirm < MIN_RECALL:
        return False
    if baseline_screen <= 0 or baseline_confirm <= 0:
        return precision_screen > 0 and precision_confirm > 0
    return (
        precision_screen >= MIN_PRECISION_MULTIPLE * baseline_screen
        and precision_confirm >= MIN_PRECISION_MULTIPLE * baseline_confirm
    )
