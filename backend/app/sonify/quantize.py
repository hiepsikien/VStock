"""Map a close onto the C major scale, and snap strong beats to the active chord."""

from __future__ import annotations

from collections.abc import Sequence

SCALE_LOW = 48  # C3
SCALE_HIGH = 96  # C7
C_MAJOR_PCS = frozenset({0, 2, 4, 5, 7, 9, 11})
STRONG_BEAT_EIGHTHS = (0, 4)  # beats 1 and 3 inside an 8-eighth bar
STRONG_BEAT_WEIGHT = 2.5
HELD_STRONG_WEIGHT = 1.0
WEAK_BEAT_WEIGHT = 0.02


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
    pitch_classes: frozenset[int],
    scale: tuple[int, ...],
    previous: int | None = None,
    step: int = 0,
) -> int:
    """Keep a chord tone; otherwise snap to the nearest chord tone on the scale.

    A tie in scale steps prefers moving rather than repeating `previous`, then
    moving in the direction of `step`, then the closer note in semitones, and
    finally the lower note.
    """
    if target % 12 in pitch_classes:
        return target
    candidates = [
        (index, note) for index, note in enumerate(scale) if note % 12 in pitch_classes
    ]
    if not candidates:
        raise ValueError("no chord tone in the melody register")
    target_index = scale.index(target)

    def key(item: tuple[int, int]) -> tuple[int, int, int, int, int]:
        index, note = item
        repeats_previous = 1 if (previous is not None and note == previous) else 0
        wrong_way = (
            1
            if (step > 0 and note < target) or (step < 0 and note > target)
            else 0
        )
        return (abs(index - target_index), repeats_previous, wrong_way, abs(note - target), note)

    return min(candidates, key=key)[1]


def bar_quantization_loss(
    bar_pitches: Sequence[int],
    pitch_classes: frozenset[int],
    scale: tuple[int, ...],
) -> float:
    """Weighted scale-step quantization loss for one 8-eighth bar under a candidate chord.

    Strong beats (eighths 0 and 4, beats 1 and 3) and eighths held in the same
    run as a strong beat carry primary weight because _quantize_strong_beats
    snaps strong-beat runs to chord tones; weak-beat passing notes keep their
    scale tone and carry only a small tie-breaker weight.
    """
    index_of = {note: index for index, note in enumerate(scale)}
    strong_run_eighths = set(STRONG_BEAT_EIGHTHS)
    for beat in STRONG_BEAT_EIGHTHS:
        if beat >= len(bar_pitches):
            continue
        pitch = bar_pitches[beat]
        cursor = beat - 1
        while cursor >= 0 and bar_pitches[cursor] == pitch:
            strong_run_eighths.add(cursor)
            cursor -= 1
        cursor = beat + 1
        while cursor < len(bar_pitches) and bar_pitches[cursor] == pitch:
            strong_run_eighths.add(cursor)
            cursor += 1

    loss = 0.0
    for eighth, note in enumerate(bar_pitches):
        snapped = quantize_chord_tone(note, pitch_classes, scale)
        steps = abs(index_of[snapped] - index_of[note])
        if steps == 0:
            continue
        if eighth in STRONG_BEAT_EIGHTHS:
            weight = STRONG_BEAT_WEIGHT
        elif eighth in strong_run_eighths:
            weight = HELD_STRONG_WEIGHT
        else:
            weight = WEAK_BEAT_WEIGHT
        loss += weight * steps
    return loss


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
