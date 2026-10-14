"""Cut an OHLC series down to one HOSE session and attach MA20.

The average is taken on trading minutes only, lunch included in neither the
average nor the recap, and earlier sessions stay in the window so the open
already has an MA20.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.sonify.model import Bar
from app.sonify.regime import MA_WINDOW, moving_average

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def is_recap_minute(moment: datetime) -> bool:
    """Morning auction through the close, with the lunch break removed.

    14:45 stays in so the closing print is part of the recap. 11:30 does not:
    that stamp is already the lunch gap.
    """
    minutes = moment.hour * 60 + moment.minute
    morning = 9 * 60 <= minutes < 11 * 60 + 30
    afternoon = 13 * 60 <= minutes < 15 * 60
    return morning or afternoon


def session_bars(
    samples: list[tuple[int, float, float]],
    session: date | None = None,
    window: int = MA_WINDOW,
) -> list[Bar]:
    """samples are (unix seconds, close, volume), in any order."""
    trading: list[tuple[datetime, float, float]] = []
    for timestamp, close, volume in samples:
        if close is None or close <= 0:
            continue
        moment = datetime.fromtimestamp(int(timestamp), VN)
        if not is_recap_minute(moment):
            continue
        trading.append((moment, float(close), float(volume)))
    trading.sort(key=lambda row: row[0])
    if not trading:
        return []

    chosen = session if session is not None else trading[-1][0].date()
    averages = moving_average([close for _moment, close, _volume in trading], window)
    return [
        Bar(close, volume, average)
        for (moment, close, volume), average in zip(trading, averages)
        if moment.date() == chosen
    ]


def _number(value: object, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def bars_from_ohlc(payload: dict, session: date | None = None) -> list[Bar]:
    """Read an Entrade-shaped payload with t, c, and optional v."""
    times = payload.get("t") or []
    closes = payload.get("c") or []
    volumes = payload.get("v") or [0.0] * len(closes)
    samples: list[tuple[int, float, float]] = []
    for timestamp, close, volume in zip(times, closes, volumes):
        price = _number(close)
        if price is None or price <= 0:
            continue
        stamped = _number(timestamp)
        if stamped is None:
            continue
        amount = _number(volume, 0.0)
        samples.append((int(stamped), price, 0.0 if amount is None else amount))
    return session_bars(samples, session)
