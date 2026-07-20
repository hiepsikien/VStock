from __future__ import annotations

from typing import Literal

ChartRange = Literal["1D", "1W", "1M", "3M", "1Y", "5Y"]

INTRADAY_RANGE: ChartRange = "1D"
DAILY_RANGES: tuple[ChartRange, ...] = ("1W", "1M", "3M", "1Y", "5Y")

# (seconds lookback, resolution)
RANGE_CONFIG: dict[ChartRange, tuple[int, str]] = {
    "1D": (3 * 24 * 3600, "5"),
    "1W": (12 * 24 * 3600, "30"),
    "1M": (45 * 24 * 3600, "1D"),
    "3M": (110 * 24 * 3600, "1D"),
    "1Y": (400 * 24 * 3600, "1D"),
    "5Y": (5 * 400 * 24 * 3600, "1W"),
}


def downsample_prices(prices: list[float]) -> list[float]:
    if len(prices) <= 120:
        return prices
    step = max(1, len(prices) // 90)
    return prices[::step]
