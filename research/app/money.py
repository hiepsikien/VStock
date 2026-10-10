from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.config import (
    MARKET_DRAIN_DAYS,
    MARKET_DRAIN_MIN,
    MARKET_FX_ABOVE_DAYS,
    MARKET_FX_ABOVE_MA_MAX,
    MARKET_GATE_REQUIRED,
    MARKET_MA_WINDOW,
    MARKET_MIN_SESSIONS,
    MARKET_POLICY_LOOKBACK_DAYS,
    MARKET_RATE_RISE_MAX,
    MARKET_SERIES,
    MARKET_SERIES_MAX_AGE_DAYS,
    MARKET_YIELD_RISE_MAX,
    POLICY_RATE_HISTORY,
)

# Daily series keyed by trading date, the same shape the flow store uses.
MarketMap = dict[str, list[tuple[str, float]]]

LABELS = {code: label for code, label, _unit, _symbol in MARKET_SERIES}
# Fetched every session, so an old point means the feed is down. The policy table is a
# record of decisions instead: its last row can be years old and still be the rate today.
DAILY = tuple(code for code, _label, _unit, symbol in MARKET_SERIES if symbol)


@dataclass(frozen=True)
class Money:
    """Tiền đang thừa hay thiếu, và giá của đồng tiền."""

    open: bool | None
    reason: str
    metrics: list[tuple[str, str]] = field(default_factory=list)
    flags: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    ready: tuple[str, ...] = ()


def policy_points(table=POLICY_RATE_HISTORY) -> list[tuple[str, float]]:
    """Chuỗi bậc thang: mỗi ngày có hiệu lực một mốc, và không có mốc nào ở giữa."""
    return sorted((str(day), float(rate)) for day, rate in table)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _upto(points: MarketMap, code: str, as_of: str | None) -> list[tuple[str, float]]:
    rows = sorted((str(day), float(value)) for day, value in (points.get(code) or []))
    if as_of is None:
        return rows
    return [row for row in rows if row[0] <= as_of]


def _minus_days(as_of: str, days: int) -> str:
    try:
        return (date.fromisoformat(as_of[:10]) - timedelta(days=days)).isoformat()
    except ValueError:
        return as_of


def _stale(newest: str, as_of: str) -> bool:
    try:
        age = (date.fromisoformat(as_of[:10]) - date.fromisoformat(newest[:10])).days
    except ValueError:
        return True
    return age > MARKET_SERIES_MAX_AGE_DAYS


def _value(code: str, value: float) -> str:
    if code == "USDVND":
        return f"{value:,.0f} VND"
    if code == "NHNN_NET":
        return f"{value:+,.0f} tỷ"
    return f"{value:,.2f} %/năm"


def _rate_row(
    code: str, rows: list[tuple[str, float]], ceiling: float, word: str
) -> tuple[str, str | None]:
    """Giá của đồng tiền: mức mới nhất so với trung bình các phiên đã lưu."""
    window = rows[-MARKET_MA_WINDOW:]
    average = _mean([value for _day, value in window])
    rise = rows[-1][1] - average
    metric = (
        f"{_value(code, rows[-1][1])} — trung bình {len(window)} phiên {average:,.2f}, {rise:+,.2f}"
    )
    if rise <= ceiling:
        return metric, None
    return metric, f"{word} cao hơn trung bình {len(window)} phiên {rise:+,.2f} điểm"


def _fx_row(rows: list[tuple[str, float]]) -> tuple[str, str | None]:
    """Tỷ giá so với trung bình: số phiên đứng trên mức đó là áp lực ngoại tệ."""
    window = rows[-MARKET_MA_WINDOW:]
    average = _mean([value for _day, value in window])
    ceiling = average * (1 + MARKET_FX_ABOVE_MA_MAX)
    streak = 0
    for _day, value in reversed(rows):
        if value <= ceiling:
            break
        streak += 1
    metric = (
        f"{_value('USDVND', rows[-1][1])} — trung bình {len(window)} phiên {average:,.0f},"
        f" trên mốc {ceiling:,.0f} {streak} phiên"
    )
    if streak < MARKET_FX_ABOVE_DAYS:
        return metric, None
    return metric, f"tỷ giá trên trung bình {len(window)} phiên {streak} phiên liên tiếp"


def _policy_row(rows: list[tuple[str, float]], as_of: str | None) -> tuple[str, str | None]:
    """Lãi suất điều hành: chỉ so mức đang hiệu lực với mức trước đó trong kỳ đã khai báo."""
    latest_day, latest_rate = rows[-1]
    metric = f"{_value('POLICY_RATE', latest_rate)} từ {latest_day}"
    if as_of is None:
        return metric, None
    earlier = [row for row in rows if row[0] <= _minus_days(as_of, MARKET_POLICY_LOOKBACK_DAYS)]
    if earlier and latest_rate > earlier[-1][1]:
        return metric, f"lãi điều hành tăng lên {latest_rate:,.2f}% từ {latest_day}"
    return metric, None


def _drain_row(rows: list[tuple[str, float]]) -> tuple[str, str | None]:
    """Hút ròng liên tiếp qua tín phiếu và thị trường mở: số âm là NHNN hút tiền về."""
    window = rows[-MARKET_DRAIN_DAYS:]
    total = sum(value for _day, value in window)
    metric = f"{total:+,.0f} tỷ trong {len(window)} phiên"
    drained = len(window) == MARKET_DRAIN_DAYS and all(value < 0 for _day, value in window)
    if drained and total <= -MARKET_DRAIN_MIN:
        return metric, f"NHNN hút ròng {total:,.0f} tỷ trong {MARKET_DRAIN_DAYS} phiên"
    return metric, None


def _open_reason(series: MarketMap, ready: list[str]) -> str:
    """Một câu cho bảng: tiền chưa thắt, kèm giá của đồng tiền."""
    parts = [
        f"{LABELS[code]} {_value(code, series[code][-1][1])}"
        for code in ready
        if series.get(code)
    ]
    if not parts:
        return "Tiền chưa thắt"
    return "Tiền chưa thắt: " + ", ".join(parts)


def thresholds() -> list[tuple[str, str]]:
    """Ngưỡng đã khai báo trước, in ra để người đọc biết vì sao cổng khóa."""
    window = MARKET_MA_WINDOW
    rows: list[tuple[str, str]] = [
        (
            LABELS["INTERBANK_ON"],
            f"vượt trung bình {window} phiên quá {MARKET_RATE_RISE_MAX:.2f} điểm %"
            if MARKET_RATE_RISE_MAX is not None
            else "chưa khai báo",
        ),
        (
            LABELS["GOV10Y"],
            f"vượt trung bình {window} phiên quá {MARKET_YIELD_RISE_MAX:.2f} điểm %"
            if MARKET_YIELD_RISE_MAX is not None
            else "chưa khai báo",
        ),
        (
            LABELS["USDVND"],
            f"trên mốc trung bình {window} phiên cộng {MARKET_FX_ABOVE_MA_MAX * 100:.1f}%"
            f" đủ {MARKET_FX_ABOVE_DAYS} phiên"
            if MARKET_FX_ABOVE_MA_MAX is not None
            else "chưa khai báo",
        ),
        (
            LABELS["POLICY_RATE"],
            f"tăng trong {MARKET_POLICY_LOOKBACK_DAYS} ngày gần nhất"
            if MARKET_POLICY_LOOKBACK_DAYS is not None
            else "chưa khai báo",
        ),
        (
            LABELS["NHNN_NET"],
            f"hút ròng {MARKET_DRAIN_DAYS} phiên liên tiếp, tổng từ {MARKET_DRAIN_MIN:,.0f} tỷ"
            if MARKET_DRAIN_MIN is not None
            else "chưa khai báo",
        ),
        ("Số cũ nhất còn dùng", f"{MARKET_SERIES_MAX_AGE_DAYS} ngày, cũ hơn thì tính là thiếu"),
        ("Số phiên tối thiểu", f"{MARKET_MIN_SESSIONS} phiên đã lưu cho mỗi chuỗi giá"),
    ]
    return rows


def money_state(
    points: MarketMap,
    *,
    as_of: str | None = None,
    required: tuple[str, ...] = MARKET_GATE_REQUIRED,
    table=POLICY_RATE_HISTORY,
) -> Money:
    """Chấm cổng tiền tệ cho một phiên.

    Chỉ số đã lưu tới hết ngày as_of được dùng, nên chấm lại một phiên cũ luôn ra cùng
    kết quả và số của hôm nay không bao giờ rơi vào một phiên đã qua. Chuỗi thiếu, chuỗi
    đã cũ, hoặc chuỗi chưa đủ số đã lưu đều đưa cổng về "Chưa chấm".
    """
    if as_of is None:
        stored = [str(day) for rows in points.values() for day, _point in rows]
        as_of = max(stored) if stored else None
    staged = dict(points)
    if not staged.get("POLICY_RATE"):
        staged["POLICY_RATE"] = policy_points(table)
    series = {
        code: _upto(staged, code, as_of) for code, _label, _unit, _symbol in MARKET_SERIES
    }
    needs = {
        "INTERBANK_ON": MARKET_MIN_SESSIONS,
        "GOV10Y": MARKET_MIN_SESSIONS,
        "USDVND": max(MARKET_MIN_SESSIONS, MARKET_FX_ABOVE_DAYS),
        "POLICY_RATE": 2,
        "NHNN_NET": MARKET_DRAIN_DAYS,
    }
    declared = {
        "INTERBANK_ON": MARKET_RATE_RISE_MAX,
        "GOV10Y": MARKET_YIELD_RISE_MAX,
        "USDVND": MARKET_FX_ABOVE_MA_MAX,
        "POLICY_RATE": MARKET_POLICY_LOOKBACK_DAYS,
        "NHNN_NET": MARKET_DRAIN_MIN,
    }

    metrics: list[tuple[str, str]] = []
    flags: list[str] = []
    missing: list[str] = []
    ready: list[str] = []
    for code, label, _unit, _symbol in MARKET_SERIES:
        # Chuỗi chưa được khai báo ngưỡng thì không thể khóa danh sách, nên nó đứng ngoài.
        if declared.get(code) is None:
            continue
        rows = series.get(code) or []
        old = bool(rows) and as_of is not None and code in DAILY and _stale(rows[-1][0], as_of)
        if not rows or old or len(rows) < needs[code]:
            note = (
                "chưa có số"
                if not rows
                else f"{_value(code, rows[-1][1])} ({len(rows)} phiên đã lưu)"
            )
            metrics.append((label, note + (" — số đã cũ" if old else "")))
            if code in required:
                missing.append(code)
            continue
        if code == "INTERBANK_ON":
            metric, flag = _rate_row(code, rows, MARKET_RATE_RISE_MAX, "lãi qua đêm")
        elif code == "GOV10Y":
            metric, flag = _rate_row(code, rows, MARKET_YIELD_RISE_MAX, "lợi suất 10 năm")
        elif code == "USDVND":
            metric, flag = _fx_row(rows)
        elif code == "POLICY_RATE":
            metric, flag = _policy_row(rows, as_of)
        else:
            metric, flag = _drain_row(rows)
        metrics.append((label, metric))
        ready.append(code)
        if flag:
            flags.append(flag)

    if missing:
        where = ", ".join(LABELS.get(code, code) for code in missing)
        return Money(
            None,
            f"Cổng tiền tệ chưa chấm: thiếu chuỗi {where}",
            metrics,
            tuple(flags),
            tuple(missing),
            tuple(ready),
        )
    if flags:
        return Money(
            False, "Tiền thắt: " + "; ".join(flags), metrics, tuple(flags), (), tuple(ready)
        )
    return Money(True, _open_reason(series, ready), metrics, (), (), tuple(ready))
