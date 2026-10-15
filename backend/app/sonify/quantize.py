"""Map a close onto the C major scale, and snap strong beats to the active chord."""

from __future__ import annotations

from app.sonify.chords import Chord

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


def quantize_chord_tone(
    target: int,
    chord: Chord | frozenset[int],
    scale: tuple[int, ...],
    previous: int | None = None,
) -> int:
    """Keep a chord tone; otherwise snap to the nearest chord tone on the scale.

    A tie in scale steps prefers moving rather than repeating `previous`, then
    the closer note in semitones, and finally the lower note.
    """
    pcs = chord.pitch_classes if isinstance(chord, Chord) else chord
    if target % 12 in pcs:
        return target
    candidates = [(index, note) for index, note in enumerate(scale) if note % 12 in pcs]
    if not candidates:
        raise ValueError("no chord tone in the melody register")
    target_index = scale.index(target)

    def key(item: tuple[int, int]) -> tuple[int, int, int, int]:
        index, note = item
        repeats_previous = 1 if (previous is not None and note == previous) else 0
        return (abs(index - target_index), repeats_previous, abs(note - target), note)

    return min(candidates, key=key)[1]


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
