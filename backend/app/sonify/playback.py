"""Map a fixed-length recap onto the 1-minute candles it was built from."""

from __future__ import annotations


def piece_seconds(musical_bars: int, bpm: float, beats_per_bar: int = 4) -> float:
    if musical_bars < 1 or bpm <= 0 or beats_per_bar < 1:
        return 0.0
    return musical_bars * beats_per_bar * 60.0 / bpm


def ambient_daily_candle_index(elapsed: float, count: int, duration: float) -> int:
    """Candle under the playhead for a 1D Ambient recap.

    The piece is 36 bars. Bars 0–1 warm up and bars 32–35 cool down. The chart
    holds the open through the warm-up and the close through the cool-down.
    Every candle is spread across the 30-bar body.
    """
    intro_bars = 2
    body_bars = 30
    musical_bars = intro_bars + body_bars + 4
    if count <= 1:
        return 0
    if duration <= 0 or elapsed <= 0:
        return 0
    intro_end = duration * intro_bars / musical_bars
    outro_start = duration * (intro_bars + body_bars) / musical_bars
    if elapsed < intro_end:
        return 0
    if elapsed >= outro_start:
        return count - 1
    span = outro_start - intro_end
    if span <= 0:
        return 0
    fraction = (elapsed - intro_end) / span
    if fraction >= 1:
        return count - 1
    return min(count - 1, int(fraction * count))


def candle_index_at(elapsed: float, count: int, duration: float) -> int:
    """Source candle sounding at `elapsed` seconds.

    `render` spreads candles evenly across the piece, in order, so playback
    time and candle index share one fraction of the piece.
    """
    if count <= 1:
        return 0
    if duration <= 0 or elapsed <= 0:
        return 0
    if elapsed >= duration:
        return count - 1
    return min(count - 1, int((elapsed / duration) * count))
