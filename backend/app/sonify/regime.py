"""Intraday regime from a 20-bar average and a deadband around it."""

from __future__ import annotations

from app.sonify.chords import Regime

# Price has to clear the average by this fraction before the phrase turns.
# A strict greater/less comparison never produces the sideway loop.
BAND = 0.0015
MA_WINDOW = 20


def moving_average(values: list[float], window: int = MA_WINDOW) -> list[float | None]:
    if window < 1:
        raise ValueError("window must be positive")
    averages: list[float | None] = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        if index >= window - 1:
            averages[index] = total / window
    return averages


def classify(close: float, ma: float | None, band: float = BAND) -> Regime:
    """Uptrend above MA20, downtrend below, sideway inside the band.

    Until the average exists the phrase stays on the sideway loop.
    """
    if ma is None or ma <= 0:
        return "sideway"
    if close > ma * (1 + band):
        return "uptrend"
    if close < ma * (1 - band):
        return "downtrend"
    return "sideway"
