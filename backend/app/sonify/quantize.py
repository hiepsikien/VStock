"""Map a close onto the C major scale."""

from __future__ import annotations

SCALE_LOW = 48  # C3
SCALE_HIGH = 96  # C7
C_MAJOR_PCS = frozenset({0, 2, 4, 5, 7, 9, 11})


def c_major_scale(low: int = SCALE_LOW, high: int = SCALE_HIGH) -> tuple[int, ...]:
    return tuple(note for note in range(low, high + 1) if note % 12 in C_MAJOR_PCS)


def price_to_scale_index(close: float, low: float, high: float, size: int) -> int:
    if size < 1:
        raise ValueError("scale is empty")
    if high <= low:
        return size // 2
    fraction = (close - low) / (high - low)
    fraction = min(1.0, max(0.0, fraction))
    return round(fraction * (size - 1))


def resample(values: list[float], count: int) -> list[float]:
    """Pick `count` evenly spaced values, including both endpoints."""
    if count < 1:
        raise ValueError("count must be positive")
    if not values:
        raise ValueError("no values to resample")
    if len(values) == 1:
        return [values[0]] * count
    if count == 1:
        return [values[(len(values) - 1) // 2]]
    last = len(values) - 1
    return [values[round(index * last / (count - 1))] for index in range(count)]
