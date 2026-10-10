from __future__ import annotations

from dataclasses import dataclass

from app.config import MA_WINDOW, PRICE_JUMP_LIMIT_UNKNOWN, PRICE_JUMP_LIMITS


@dataclass(frozen=True)
class Regime:
    open: bool | None
    reason: str
    close: float | None = None
    ma200: float | None = None


@dataclass(frozen=True)
class Pattern:
    ready: bool
    reason: str
    rs: float | None = None
    stop: float | None = None
    unadjusted: bool = False


def market_regime(index_bars: list[dict]) -> Regime:
    closes = [bar["close"] for bar in index_bars if bar["close"] > 0]
    if len(closes) < MA_WINDOW:
        return Regime(None, f"Chưa đủ {MA_WINDOW} phiên VN-Index để tính MA200")
    ma = sum(closes[-MA_WINDOW:]) / MA_WINDOW
    close = closes[-1]
    if close > ma:
        return Regime(True, f"VN-Index {close:.2f} trên MA200 {ma:.2f}", close, ma)
    return Regime(False, f"VN-Index {close:.2f} dưới MA200 {ma:.2f}", close, ma)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def jump_limit(exchange: str | None) -> tuple[float, str]:
    board = (exchange or "").strip().upper()
    if board in PRICE_JUMP_LIMITS:
        return PRICE_JUMP_LIMITS[board], board
    percent = int(PRICE_JUMP_LIMIT_UNKNOWN * 100)
    return PRICE_JUMP_LIMIT_UNKNOWN, f"sàn chưa rõ (dùng {percent}%)"


def unadjusted_split_gap(bars: list[dict], exchange: str | None = None) -> str | None:
    """A gap past the daily band means the series still contains a raw split."""
    limit, board = jump_limit(exchange)
    for previous, current in zip(bars, bars[1:]):
        if previous["close"] <= 0:
            continue
        change = current["close"] / previous["close"] - 1
        if abs(change) > limit:
            return (
                f"Giá chưa chỉnh chia tách: phiên {current['trade_date']} lệch "
                f"{change * 100:.0f}% so với phiên trước, quá biên độ {board}"
            )
    return None


def assess_pattern(
    stock_bars: list[dict],
    index_bars: list[dict],
    exchange: str | None = None,
) -> Pattern:
    """Daily base: tighter range, drier volume, then a close through the base high, with RS > 0."""
    gap = unadjusted_split_gap(stock_bars, exchange)
    if gap:
        return Pattern(False, gap, unadjusted=True)
    if len(stock_bars) < 61 or len(index_bars) < 61:
        return Pattern(False, "Chưa đủ nến ngày để xét nền giá")

    base = stock_bars[:-1]
    recent = base[-10:]
    previous = base[-20:-10]
    if len(recent) < 10 or len(previous) < 10:
        return Pattern(False, "Chưa đủ nến ngày để xét nền giá")

    def _range(bar: dict) -> float:
        close = bar["close"] or 1
        return (bar["high"] - bar["low"]) / close

    recent_range = _mean([_range(bar) for bar in recent])
    previous_range = _mean([_range(bar) for bar in previous])
    recent_volume = _mean([bar["volume"] for bar in recent])
    previous_volume = _mean([bar["volume"] for bar in previous])
    contraction = recent_range < previous_range
    dry = previous_volume > 0 and recent_volume < previous_volume
    ceiling = max(bar["high"] for bar in base[-20:])
    breakout = stock_bars[-1]["close"] > ceiling
    stop = min(bar["low"] for bar in base[-20:])

    stock_return = stock_bars[-1]["close"] / stock_bars[-61]["close"] - 1
    index_return = index_bars[-1]["close"] / index_bars[-61]["close"] - 1
    rs = stock_return - index_return

    reasons: list[str] = []
    if not contraction:
        reasons.append("biên độ chưa siết")
    if not dry:
        reasons.append("khối lượng chưa cạn")
    if not breakout:
        reasons.append("chưa phá đỉnh nền")
    if rs <= 0:
        reasons.append("sức mạnh tương đối không cao hơn VN-Index")

    if reasons:
        return Pattern(False, "Nền giá: " + ", ".join(reasons), rs, stop)
    return Pattern(
        True,
        "Nền đã siết, khối lượng cạn, và giá đóng cửa phá đỉnh 20 phiên",
        rs,
        stop,
    )
