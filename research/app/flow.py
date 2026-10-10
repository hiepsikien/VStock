from __future__ import annotations

from dataclasses import dataclass, field

from app.config import (
    FLOW_FLAT_BAND,
    FLOW_MIN_SESSIONS,
    FLOW_ROOM_LOW,
    FLOW_SCORE,
    FLOW_STRONG_RATIO,
    FLOW_WINDOW,
)

# Daily series keyed by trading date, the same shape the ratio store uses.
FlowMap = dict[str, list[tuple[str, float]]]

OPEN = "Mở"
WAIT = "Chờ"
MISSING = "Chưa có"

ACCUMULATION = "accumulation"
SUPPORT = "support"
NEUTRAL = "neutral"
WEAK = "weak"
BLOCK = "block"


@dataclass(frozen=True)
class FlowState:
    """What the foreign tape says about the last window of sessions."""

    state: str
    level: str
    reason: str
    priority: int = 0
    net_volume: float | None = None
    net_value: float | None = None
    room_ratio: float | None = None
    sessions: int = 0
    metrics: list[tuple[str, str]] = field(default_factory=list)


def missing_flow() -> FlowState:
    return FlowState(MISSING, "missing", "Chưa có dữ liệu giao dịch khối ngoại", metrics=[])


def _by_day(points: FlowMap, code: str) -> dict[str, float]:
    return {day: value for day, value in points.get(code, [])}


def _format_volume(value: float) -> str:
    if abs(value) >= 1e6:
        return f"{value / 1e6:,.1f} triệu cp"
    return f"{value:,.0f} cp"


def _format_value(value: float) -> str:
    return f"{value / 1e9:,.0f} tỷ"


def flow_gate(points: FlowMap, bars: list[dict]) -> FlowState:
    """Compare the last window of price action with the foreign tape.

    Rule 1 blocks a rally that foreigners are selling into, rule 2 marks quiet
    accumulation while the price goes nowhere, rule 3 looks for a divergence
    between a falling price and a buying tape.
    """
    if not points or not bars:
        return missing_flow()

    net_volume = _by_day(points, "FOREIGN_NET_VOL")
    net_value = _by_day(points, "FOREIGN_NET_VAL")
    room = _by_day(points, "FOREIGN_ROOM_RATIO")
    window = bars[-FLOW_WINDOW:]
    if len(window) < FLOW_MIN_SESSIONS:
        return missing_flow()

    matched = [bar for bar in window if bar.get("trade_date") in net_volume]
    if len(matched) < FLOW_MIN_SESSIONS:
        return missing_flow()

    traded = sum(float(bar.get("volume") or 0.0) for bar in matched)
    if traded <= 0:
        return missing_flow()

    foreign_volume = sum(net_volume[bar["trade_date"]] for bar in matched)
    foreign_value = sum(net_value.get(bar["trade_date"], 0.0) for bar in matched)
    ratio = foreign_volume / traded
    first_close = float(matched[0]["close"])
    last_close = float(matched[-1]["close"])
    price_return = last_close / first_close - 1 if first_close > 0 else 0.0
    last_day = matched[-1]["trade_date"]
    room_ratio = room.get(last_day)

    sessions = len(matched)
    read = (
        f"khối ngoại {'mua' if foreign_volume >= 0 else 'bán'} ròng "
        f"{_format_volume(abs(foreign_volume))} ({abs(ratio):.0%} khối lượng khớp) "
        f"trong {sessions} phiên"
    )
    metrics = [
        ("Dòng tiền ngoại", read),
        ("Giá trị ròng", f"{_format_value(foreign_value)}"),
    ]
    if room_ratio is not None:
        metrics.append(("Room ngoại còn", f"{room_ratio * 100:.1f}%"))
    note = ""
    if room_ratio is not None and room_ratio < FLOW_ROOM_LOW:
        note = " Room ngoại gần cạn."

    if ratio >= FLOW_STRONG_RATIO and price_return <= FLOW_FLAT_BAND:
        return FlowState(
            OPEN,
            ACCUMULATION,
            f"Gom hàng: {read}, giá gần như đứng ({price_return:+.1%}).{note}",
            priority=2,
            net_volume=foreign_volume,
            net_value=foreign_value,
            room_ratio=room_ratio,
            sessions=sessions,
            metrics=metrics,
        )
    if ratio >= FLOW_STRONG_RATIO:
        return FlowState(
            OPEN,
            SUPPORT,
            f"Ủng hộ: {read}, giá {price_return:+.1%}.{note}",
            priority=1,
            net_volume=foreign_volume,
            net_value=foreign_value,
            room_ratio=room_ratio,
            sessions=sessions,
            metrics=metrics,
        )
    if ratio <= -FLOW_STRONG_RATIO and price_return > FLOW_FLAT_BAND:
        return FlowState(
            WAIT,
            BLOCK,
            f"Nghi bán vào đà tăng: giá {price_return:+.1%} nhưng {read}.{note}",
            net_volume=foreign_volume,
            net_value=foreign_value,
            room_ratio=room_ratio,
            sessions=sessions,
            metrics=metrics,
        )
    if ratio <= -FLOW_STRONG_RATIO:
        return FlowState(
            WAIT,
            WEAK,
            f"Bán ròng mạnh: {read}, giá {price_return:+.1%}.{note}",
            net_volume=foreign_volume,
            net_value=foreign_value,
            room_ratio=room_ratio,
            sessions=sessions,
            metrics=metrics,
        )
    return FlowState(
        OPEN,
        NEUTRAL,
        f"Trung tính: {read}, giá {price_return:+.1%}.{note}",
        net_volume=foreign_volume,
        net_value=foreign_value,
        room_ratio=room_ratio,
        sessions=sessions,
        metrics=metrics,
    )


def flow_score(level: str) -> int:
    return FLOW_SCORE.get(level, FLOW_SCORE["neutral"])


def flow_flipped(points: FlowMap, bars: list[dict]) -> bool:
    """True when the tape turned hard negative, the exit trigger for an open position."""
    state = flow_gate(points, bars)
    return state.state == WAIT and state.level in {WEAK, BLOCK}
