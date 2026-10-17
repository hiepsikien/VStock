"""Map a fixed-length recap onto the 1-minute candles it was built from."""

from __future__ import annotations


def piece_seconds(musical_bars: int, bpm: float, beats_per_bar: int = 4) -> float:
    if musical_bars < 1 or bpm <= 0 or beats_per_bar < 1:
        return 0.0
    return musical_bars * beats_per_bar * 60.0 / bpm


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
