from __future__ import annotations

from dataclasses import dataclass

from app.config import (
    ATR_STOP_MULTIPLIER,
    ATR_WINDOW,
    BREAKOUT_VOLUME_RATIO,
    DOUBLE_BOTTOM_MIN_BARS,
    DOUBLE_BOTTOM_MIN_RISE,
    DOUBLE_BOTTOM_TOLERANCE,
    FAILED_BREAKOUT_SESSIONS,
    FIB_EXTENSION_HIGH,
    FIB_EXTENSION_LOW,
    FIB_RETRACE_HIGH,
    FIB_RETRACE_LOW,
    FLAG_MAX_CONSOLIDATION_BARS,
    FLAG_MAX_RETRACE,
    FLAG_POLE_ATR_MULTIPLE,
    FLAT_BASE_ADVANCE_LOOKBACK,
    FLAT_BASE_MAX_DEPTH,
    FLAT_BASE_MIN_ADVANCE,
    MA_FAST,
    MA_WINDOW,
    PRICE_JUMP_LIMIT_UNKNOWN,
    PRICE_JUMP_LIMITS,
    STRUCTURE_LOOKBACK_SESSIONS,
    VCP_CONTRACTION_RATIO,
)


@dataclass(frozen=True)
class Regime:
    open: bool | None
    reason: str
    close: float | None = None
    ma200: float | None = None


@dataclass(frozen=True)
class Pivot:
    """One confirmed swing point from the ATR ZigZag."""

    kind: str  # "H" for a swing high, "L" for a swing low
    index: int
    price: float
    date: str


@dataclass(frozen=True)
class Shape:
    """Geometry of one structure, in (date, price) so the chart can draw what the text says.

    Points are joined as a line, segments are drawn on their own — the neckline of a double
    bottom or the pole of a flag — and a box marks a range such as the 20-session base.
    """

    kind: str
    points: tuple[tuple[str, float], ...] = ()
    segments: tuple[tuple[tuple[str, float], tuple[str, float]], ...] = ()
    box: tuple[str, str, float, float] | None = None  # start date, end date, low, high


@dataclass(frozen=True)
class Pattern:
    ready: bool
    reason: str
    rs: float | None = None
    stop: float | None = None
    unadjusted: bool = False
    patterns: tuple[str, ...] = ()
    score: int = 0
    atr14: float | None = None
    ma20: float | None = None
    volume_ratio: float | None = None
    base_depth: float | None = None
    base_sessions: int = 0
    # Trần nền tại phiên phá. Vị thế giữ con số này để một nền cao hơn hình thành sau đó
    # không kéo mốc lên theo.
    base_ceiling: float | None = None
    base_advance: float | None = None
    breakout_volume_ratio: float | None = None
    # Lý do phá hỏng, None khi cú phá còn hiệu lực.
    failed_breakout: str | None = None
    geometry: tuple[Shape, ...] = ()


def market_regime(index_bars: list[dict]) -> Regime:
    closes = [bar["close"] for bar in index_bars if bar["close"] > 0]
    if len(closes) < MA_WINDOW:
        return Regime(None, f"Chưa đủ {MA_WINDOW} phiên VN-Index để tính MA200")
    ma = sum(closes[-MA_WINDOW:]) / MA_WINDOW
    close = closes[-1]
    if close > ma:
        return Regime(True, f"VN-Index {close:.2f} trên MA200 {ma:.2f}", close, ma)
    return Regime(False, f"VN-Index {close:.2f} dưới MA200 {ma:.2f}", close, ma)


def session_bar(bars: list[dict], trade_date: str) -> dict | None:
    """The bar of the session being read, or None when the name has no bar of its own.

    A name that is suspended, halted, or simply missing a bar keeps its last close in the store,
    so the last bar of the slice is then yesterday's. Walking it again would count a session the
    slot was never exposed to — bringing the 30-session time stop and the 60-session ceiling
    forward — and would read a low the stop has already seen, letting a trailing stop fill on a
    bottom that happened before it was raised. The paper ledger steps a bar only once, so both
    books have to skip the same sessions to stay comparable. A live run skips them for the same
    reason: scoring a name on an older bar would stamp this session's date on yesterday's close
    and could show a base break that has already happened as if it were this session's.
    """
    if not bars:
        return None
    last = bars[-1]
    if str(last.get("trade_date")) != trade_date:
        return None
    return last


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def sma(values: list[float], window: int) -> float | None:
    if window <= 0 or len(values) < window:
        return None
    return sum(values[-window:]) / window


def true_ranges(bars: list[dict]) -> list[float | None]:
    ranges: list[float | None] = [None]
    for previous, current in zip(bars, bars[1:]):
        previous_close = previous["close"]
        ranges.append(
            max(
                current["high"] - current["low"],
                abs(current["high"] - previous_close),
                abs(current["low"] - previous_close),
            )
        )
    return ranges


def rolling_atr(bars: list[dict], window: int = ATR_WINDOW) -> list[float | None]:
    ranges = true_ranges(bars)
    values: list[float | None] = []
    for index in range(len(bars)):
        if index < window:
            values.append(None)
            continue
        chunk = [item for item in ranges[index - window + 1 : index + 1] if item is not None]
        values.append(sum(chunk) / len(chunk) if chunk else None)
    return values


def atr(bars: list[dict], window: int = ATR_WINDOW) -> float | None:
    values = rolling_atr(bars, window)
    return values[-1] if values else None


def ma_now(bars: list[dict], window: int = MA_FAST) -> float | None:
    return sma([bar["close"] for bar in bars], window)


def average_volume(bars: list[dict]) -> float:
    if not bars:
        return 0.0
    return sum(bar["volume"] for bar in bars) / len(bars)


def zigzag_pivots(
    bars: list[dict],
    window: int = ATR_WINDOW,
    multiplier: float = ATR_STOP_MULTIPLIER,
) -> list[Pivot]:
    """ATR-scaled ZigZag. A swing counts only after the move reverses by one threshold."""
    if len(bars) < window + 3:
        return []
    atr_values = rolling_atr(bars, window)
    start = window
    rising = bars[start]["close"] >= bars[0]["close"]
    extreme_index = start
    extreme = bars[start]["high"] if rising else bars[start]["low"]
    pivots: list[Pivot] = []
    for index in range(start + 1, len(bars)):
        threshold = (atr_values[index] or 0.0) * multiplier
        if threshold <= 0:
            continue
        bar = bars[index]
        if rising:
            if bar["high"] >= extreme:
                extreme_index, extreme = index, bar["high"]
            elif extreme - bar["low"] >= threshold:
                pivots.append(
                    Pivot("H", extreme_index, extreme, bars[extreme_index]["trade_date"])
                )
                rising = False
                extreme_index, extreme = index, bar["low"]
        else:
            if bar["low"] <= extreme:
                extreme_index, extreme = index, bar["low"]
            elif bar["high"] - extreme >= threshold:
                pivots.append(
                    Pivot("L", extreme_index, extreme, bars[extreme_index]["trade_date"])
                )
                rising = True
                extreme_index, extreme = index, bar["high"]
    return pivots


def _recent_pivots(pivots: list[Pivot], bars: list[dict]) -> list[Pivot]:
    cutoff = max(0, len(bars) - STRUCTURE_LOOKBACK_SESSIONS)
    return [pivot for pivot in pivots if pivot.index >= cutoff]


def _pullbacks(pivots: list[Pivot]) -> list[tuple[Pivot, Pivot, float]]:
    return [
        (first, second, (first.price - second.price) / first.price)
        for first, second in zip(pivots, pivots[1:])
        if first.kind == "H" and second.kind == "L" and first.price > 0
    ]


def _match_double_bottom(pivots: list[Pivot], bars: list[dict]) -> tuple[str, Shape] | None:
    if len(pivots) < 3:
        return None
    first, middle, second = pivots[-3:]
    if (first.kind, middle.kind, second.kind) != ("L", "H", "L"):
        return None
    if first.price <= 0 or second.price <= 0:
        return None
    if abs(second.price - first.price) / first.price > DOUBLE_BOTTOM_TOLERANCE:
        return None
    if second.price < first.price * (1 - DOUBLE_BOTTOM_TOLERANCE):
        return None
    if middle.price < first.price * (1 + DOUBLE_BOTTOM_MIN_RISE):
        return None
    if second.index - first.index < DOUBLE_BOTTOM_MIN_BARS:
        return None
    neckline = middle.price
    state = "đã vượt" if bars[-1]["close"] > neckline else "chờ vượt"
    return (
        f"Đáy đôi {state} đỉnh giữa {neckline:.2f}",
        Shape(
            "double_bottom",
            points=(
                (first.date, first.price),
                (middle.date, middle.price),
                (second.date, second.price),
            ),
            segments=(((first.date, neckline), (bars[-1]["trade_date"], neckline)),),
        ),
    )


def _match_vcp(pivots: list[Pivot]) -> tuple[str, Shape] | None:
    pulls = _pullbacks(pivots)[-3:]
    if len(pulls) < 3:
        return None
    first, middle, last = [depth for _high, _low, depth in pulls]
    if not first > middle > last:
        return None
    if middle > first * VCP_CONTRACTION_RATIO or last > middle * VCP_CONTRACTION_RATIO:
        return None
    points = tuple(
        point
        for high, low, _depth in pulls
        for point in ((high.date, high.price), (low.date, low.price))
    )
    return (
        f"VCP ba nhịp co {first:.0%} → {middle:.0%} → {last:.0%}",
        Shape("vcp", points=points),
    )


def _match_flag(
    bars: list[dict], pivots: list[Pivot], atr_value: float | None
) -> tuple[str, Shape] | None:
    highs = [pivot for pivot in pivots if pivot.kind == "H"]
    if not highs:
        return None
    top = highs[-1]
    lows = [pivot for pivot in pivots if pivot.kind == "L" and pivot.index < top.index]
    if not lows:
        return None
    base = lows[-1]
    pole = top.price - base.price
    if pole <= 0 or base.price <= 0:
        return None
    minimum = max(
        (atr_value or 0.0) * FLAG_POLE_ATR_MULTIPLE,
        base.price * 0.10,
    )
    if pole < minimum:
        return None
    consolidation = bars[top.index + 1 :]
    if not 2 <= len(consolidation) <= FLAG_MAX_CONSOLIDATION_BARS:
        return None
    high = max(bar["high"] for bar in consolidation)
    low = min(bar["low"] for bar in consolidation)
    if (high - low) / pole > FLAG_MAX_RETRACE:
        return None
    pole_volume = average_volume(bars[base.index : top.index + 1])
    if pole_volume <= 0 or average_volume(consolidation) >= pole_volume:
        return None
    return (
        f"Cờ: cột tăng {pole / base.price:.0%} rồi nén {len(consolidation)} phiên",
        Shape(
            "flag",
            segments=(((base.date, base.price), (top.date, top.price)),),
            box=(
                consolidation[0]["trade_date"],
                consolidation[-1]["trade_date"],
                low,
                high,
            ),
        ),
    )


def _match_abcd(pivots: list[Pivot]) -> tuple[str, Shape] | None:
    if len(pivots) < 4:
        return None
    first, second, third, fourth = pivots[-4:]
    if (first.kind, second.kind, third.kind, fourth.kind) != ("L", "H", "L", "H"):
        return None
    up_leg = second.price - first.price
    first_pullback = second.price - third.price
    second_leg = fourth.price - third.price
    if up_leg <= 0 or first_pullback <= 0 or second_leg <= 0:
        return None
    retrace = first_pullback / up_leg
    extension = second_leg / first_pullback
    if not FIB_RETRACE_LOW <= retrace <= FIB_RETRACE_HIGH:
        return None
    if not FIB_EXTENSION_LOW <= extension <= FIB_EXTENSION_HIGH:
        return None
    return (
        f"ABCD hồi {retrace:.0%} AB và duỗi {extension:.2f}x BC",
        Shape(
            "abcd",
            points=(
                (first.date, first.price),
                (second.date, second.price),
                (third.date, third.price),
                (fourth.date, fourth.price),
            ),
        ),
    )


def _match_all(
    bars: list[dict],
    pivots: list[Pivot],
    atr_value: float | None = None,
) -> list[tuple[str, str, Shape]]:
    """Named structures inside the lookback window, most specific first."""
    recent = _recent_pivots(pivots, bars)
    found: list[tuple[str, str, Shape]] = []
    for name, match in (
        ("Đáy đôi", _match_double_bottom(recent, bars)),
        ("VCP", _match_vcp(recent)),
        ("Cờ", _match_flag(bars, recent, atr_value)),
        ("ABCD", _match_abcd(recent)),
    ):
        if match is not None:
            found.append((name, match[0], match[1]))
    return found


def recognise_patterns(
    bars: list[dict],
    pivots: list[Pivot],
    atr_value: float | None = None,
) -> tuple[tuple[str, ...], list[str]]:
    """Names and the matching sentence, the narrow view of _match_all."""
    matches = _match_all(bars, pivots, atr_value)
    return (
        tuple(name for name, _note, _shape in matches),
        [note for _name, note, _shape in matches],
    )


def recognise_structures(
    bars: list[dict],
    pivots: list[Pivot],
    atr_value: float | None = None,
) -> tuple[tuple[str, ...], list[str], tuple[Shape, ...]]:
    """The same names and notes, plus the geometry the detail chart draws."""
    matches = _match_all(bars, pivots, atr_value)
    return (
        tuple(name for name, _note, _shape in matches),
        [note for _name, note, _shape in matches],
        tuple(shape for _name, _note, shape in matches),
    )


def pattern_score(
    *,
    contraction: bool,
    dry: bool,
    breakout: bool,
    higher_low: bool,
    names: tuple[str, ...],
) -> int:
    score = 0
    if contraction:
        score += 20
    if dry:
        score += 15
    if breakout:
        score += 30
    if higher_low:
        score += 5
    score += min(30, 15 * len(names))
    return min(100, score)


def jump_limit(exchange: str | None) -> tuple[float, str]:
    board = (exchange or "").strip().upper()
    if board in PRICE_JUMP_LIMITS:
        return PRICE_JUMP_LIMITS[board], board
    percent = int(PRICE_JUMP_LIMIT_UNKNOWN * 100)
    return PRICE_JUMP_LIMIT_UNKNOWN, f"sàn chưa rõ (dùng {percent}%)"


# The structure lookback plus the ATR that scales its pivots. The base, the RS reference and the
# named structures all sit inside it. The ZigZag itself walks the whole series, so an older gap
# can still shift where its first pivots fall, but that settles within a swing or two, while a
# board move or a listing day years ago would otherwise block the name for good.
SPLIT_CHECK_SESSIONS = STRUCTURE_LOOKBACK_SESSIONS + ATR_WINDOW


def unadjusted_split_gap(
    bars: list[dict], exchange: str | None = None, sessions: int | None = SPLIT_CHECK_SESSIONS
) -> str | None:
    """A gap past the daily band inside the last `sessions` sessions (None: all) is a raw split."""
    limit, board = jump_limit(exchange)
    recent = bars if sessions is None else bars[-(sessions + 1) :]
    for previous, current in zip(recent, recent[1:]):
        if previous["close"] <= 0:
            continue
        change = current["close"] / previous["close"] - 1
        if abs(change) > limit:
            return (
                f"Giá chưa chỉnh chia tách: phiên {current['trade_date']} lệch "
                f"{change * 100:.0f}% so với phiên trước, quá biên độ {board}"
            )
    return None


def index_close_on(index_bars: list[dict], day: str) -> float | None:
    """The index close on `day`, or the last session before it, or None without one.

    A halted name prints no bar while the index still does, so two 60-session windows
    only line up on dates, never on positions in the array.
    """
    close = None
    for bar in index_bars:
        if bar["trade_date"] <= day:
            close = bar["close"]
        else:
            break
    return close


def _base_advance(base: list[dict], window: list[dict]) -> float | None:
    """Rise from the lowest low right before the base up to the base ceiling.

    The lookback sits immediately before the fixed 20-session window, so this only asks
    whether the name climbed into the base — the defence against a sideways drift down.
    """
    if not window:
        return None
    before = base[: len(base) - len(window)][-FLAT_BASE_ADVANCE_LOOKBACK:]
    if not before:
        return None
    low = min(bar["low"] for bar in before)
    ceiling = max(bar["high"] for bar in window)
    if low <= 0:
        return None
    return (ceiling - low) / low


def failed_breakout(stock_bars: list[dict]) -> str | None:
    """A close through a base ceiling that later closed back under that same level.

    The level is frozen on the breakout session: the sessions that follow do not raise it.
    Only the most recent breakout counts, because a close above a fresh ceiling means the
    earlier failure is behind the name — so the session being scored is a candidate breakout
    too, and a close through a new ceiling today clears a failure seen three sessions ago.
    A session that closes exactly on the level holds.
    """
    for offset in range(0, FAILED_BREAKOUT_SESSIONS + 1):
        index = len(stock_bars) - 1 - offset
        if index < MA_FAST:
            return None
        ceiling = max(bar["high"] for bar in stock_bars[:index][-MA_FAST:])
        if stock_bars[index]["close"] <= ceiling:
            continue
        for bar in stock_bars[index + 1 :]:
            if bar["close"] < ceiling:
                return (
                    f"phá nền thất bại: đóng {bar['close']:.2f} dưới mốc {ceiling:.2f} "
                    f"({bar['trade_date']})"
                )
        return None
    return None


def assess_pattern(
    stock_bars: list[dict],
    index_bars: list[dict],
    exchange: str | None = None,
    split_sessions: int | None = SPLIT_CHECK_SESSIONS,
) -> Pattern:
    """Daily base: tighter range, drier volume, then a close through the base high, with RS > 0.

    `split_sessions=None` checks the whole series for unadjusted gaps, the rule as it stood at
    the pre-registration tags.
    """
    gap = unadjusted_split_gap(stock_bars, exchange, split_sessions)
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
    window = base[-20:]
    ceiling = max(bar["high"] for bar in window)
    floor = min(bar["low"] for bar in window)
    close = stock_bars[-1]["close"]
    breakout = close > ceiling
    stop = floor
    # The 20-session window is fixed, so its own high and low stay the breakout level and
    # the stop. The flat-base gate adds the shape of that window and of the leg into it.
    base_depth = (ceiling - floor) / ceiling if ceiling > 0 else None
    base_advance = _base_advance(base, window)
    base_volume = _mean([bar["volume"] for bar in window])
    breakout_volume_ratio = stock_bars[-1]["volume"] / base_volume if base_volume > 0 else None
    volume_confirmed = (
        breakout_volume_ratio is not None and breakout_volume_ratio >= BREAKOUT_VOLUME_RATIO
    )

    reference = stock_bars[-61]
    index_start = index_close_on(index_bars, reference["trade_date"])
    index_end = index_close_on(index_bars, stock_bars[-1]["trade_date"])
    rs: float | None = None
    if reference["close"] > 0 and index_start and index_end is not None:
        rs = (close / reference["close"] - 1) - (index_end / index_start - 1)

    atr_value = atr(stock_bars)
    ma20 = ma_now(stock_bars)
    volume_ratio = recent_volume / previous_volume if previous_volume > 0 else None
    pivots = zigzag_pivots(stock_bars)
    names, notes, shapes = recognise_structures(stock_bars, pivots, atr_value)
    recent_lows = [pivot for pivot in _recent_pivots(pivots, stock_bars) if pivot.kind == "L"]
    higher_low = len(recent_lows) >= 2 and recent_lows[-1].price > recent_lows[-2].price
    score = pattern_score(
        contraction=contraction,
        dry=dry,
        breakout=breakout,
        higher_low=higher_low,
        names=names,
    )

    reasons: list[str] = []
    if not contraction:
        reasons.append("biên độ chưa siết")
    if not dry:
        reasons.append("khối lượng chưa cạn")
    if not breakout:
        reasons.append("chưa phá đỉnh nền")
    if rs is None or rs <= 0:
        reasons.append("sức mạnh tương đối không cao hơn VN-Index")
    if base_depth is None or base_depth > FLAT_BASE_MAX_DEPTH:
        shown = f"{base_depth:.0%}" if base_depth is not None else "chưa đo được"
        reasons.append(f"nền sâu {shown} quá trần {FLAT_BASE_MAX_DEPTH:.0%}")
    if base_advance is None or base_advance < FLAT_BASE_MIN_ADVANCE:
        shown = f"{base_advance:.0%}" if base_advance is not None else "chưa đo được"
        reasons.append(f"chưa có nhịp tăng {FLAT_BASE_MIN_ADVANCE:.0%} trước nền ({shown})")
    if breakout and not volume_confirmed:
        shown = f"{breakout_volume_ratio:.1f}x" if breakout_volume_ratio is not None else "chưa đo được"
        reasons.append(f"phá nền thiếu khối lượng ({shown} nền, cần {BREAKOUT_VOLUME_RATIO:.1f}x)")

    detail = ". ".join(notes)
    geometry = (
        Shape("base", box=(window[0]["trade_date"], base[-1]["trade_date"], floor, ceiling)),
        *shapes,
    )
    extra = {
        "patterns": names,
        "score": score,
        "atr14": atr_value,
        "ma20": ma20,
        "volume_ratio": volume_ratio,
        "base_depth": base_depth,
        "base_sessions": len(window),
        "base_ceiling": ceiling,
        "base_advance": base_advance,
        "breakout_volume_ratio": breakout_volume_ratio,
        "failed_breakout": failed_breakout(stock_bars),
        "geometry": geometry,
    }

    if extra["failed_breakout"]:
        # A close back inside the base cancels the breakout itself, so the flat-base and
        # volume gates are not worth listing on top of it.
        reason = f"Nền giá: {extra['failed_breakout']}"
        if detail:
            reason = f"{reason}. {detail}"
        return Pattern(False, reason, rs, stop, **extra)
    if reasons:
        reason = "Nền giá: " + ", ".join(reasons)
        if detail:
            reason = f"{reason}. {detail}"
        return Pattern(False, reason, rs, stop, **extra)
    reason = (
        f"Nền phẳng {len(window)} phiên sâu {base_depth:.0%}, nhịp tăng trước nền "
        f"{base_advance:.0%}, đóng cửa phá đỉnh {ceiling:.2f} với "
        f"{breakout_volume_ratio:.1f}x khối lượng nền"
    )
    if detail:
        reason = f"{reason}. {detail}"
    return Pattern(True, reason, rs, stop, **extra)
