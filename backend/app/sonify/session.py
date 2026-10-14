"""Cut an OHLC series down to one HOSE session and attach MA20.

The average is taken on trading minutes only, lunch included in neither the
average nor the recap, and earlier sessions stay in the window so the open
already has an MA20.
"""

from __future__ import annotations

from datetime import date, datetime
from math import isfinite
from zoneinfo import ZoneInfo

from app.sonify.model import Bar
from app.sonify.regime import MA_WINDOW, moving_average

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def is_recap_minute(moment: datetime) -> bool:
    """Morning through the 14:45 close, with the lunch break removed.

    11:30 is already the lunch gap. After 14:45 the prints are negotiated
    deals, so the recap stops at 14:45.
    """
    minutes = moment.hour * 60 + moment.minute
    morning = 9 * 60 <= minutes < 11 * 60 + 30
    afternoon = 13 * 60 <= minutes <= 14 * 60 + 45
    return morning or afternoon


def is_auction_minute(moment: datetime) -> bool:
    """ATO runs through the 9:15 match; ATC runs from 14:30 through 14:45."""
    minutes = moment.hour * 60 + moment.minute
    opening = 9 * 60 <= minutes <= 9 * 60 + 15
    closing = 14 * 60 + 30 <= minutes <= 14 * 60 + 45
    return opening or closing


def session_bars(
    samples: list[tuple[int, float, float]],
    session: date | None = None,
    window: int = MA_WINDOW,
) -> list[Bar]:
    """samples are (unix seconds, close, volume), in any order."""
    trading: list[tuple[datetime, float, float]] = []
    for timestamp, close, volume in samples:
        if close is None or not isfinite(close) or close <= 0:
            continue
        moment = datetime.fromtimestamp(int(timestamp), VN)
        if not is_recap_minute(moment):
            continue
        traded = float(volume) if isfinite(volume) and volume > 0 else 0.0
        trading.append((moment, float(close), traded))
    trading.sort(key=lambda row: row[0])
    if not trading:
        return []

    chosen = session if session is not None else trading[-1][0].date()
    averages = moving_average([close for _moment, close, _volume in trading], window)
    return [
        Bar(close, volume, average, is_auction_minute(moment))
        for (moment, close, volume), average in zip(trading, averages)
        if moment.date() == chosen
    ]


def _number(value: object, default: float | None = None) -> float | None:
    """NaN and infinity count as missing, so they cannot clamp to a scale edge."""
    try:
        if value is None or value == "":
            return default
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return parsed if isfinite(parsed) else default


def bars_from_ohlc(payload: dict, session: date | None = None) -> list[Bar]:
    """Read an Entrade-shaped payload with t, c, and optional v.

    A missing or short ``v`` does not drop closes. The missing tail is volume 0.
    """
    times = list(payload.get("t") or [])
    closes = list(payload.get("c") or [])
    raw_volume = payload.get("v")
    volumes = [0.0] * len(closes)
    for index, value in enumerate(raw_volume or []):
        if index >= len(volumes):
            break
        parsed = _number(value, 0.0)
        volumes[index] = 0.0 if parsed is None else parsed
    samples: list[tuple[int, float, float]] = []
    for index in range(min(len(times), len(closes))):
        price = _number(closes[index])
        if price is None or price <= 0:
            continue
        stamped = _number(times[index])
        if stamped is None:
            continue
        samples.append((int(stamped), price, volumes[index]))
    return session_bars(samples, session)
