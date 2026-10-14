"""Letter dynamics from p to f, as MusicXML 4.0 spells them.

MusicXML prints a dynamic as an empty child of <dynamics>. Only the four
middle names p, mp, mf, f are used: ppp is inaudible under the melody and fff
buries it, so liquidity is ranked into four steps the ear can tell apart.

Playback is a sibling <sound dynamics="N"/> element. N is a percentage of
MusicXML's default forte, which is MIDI velocity 90. The percentages below
are chosen so round(N / 100 * 90) is the velocity in the third column.
"""

from __future__ import annotations

from math import log1p

# marking, sound-dynamics percent, intended MIDI velocity
DYNAMICS: tuple[tuple[str, int, int], ...] = (
    ("p", 54, 49),
    ("mp", 71, 64),
    ("mf", 89, 80),
    ("f", 107, 96),
)

MARKINGS: tuple[str, ...] = tuple(row[0] for row in DYNAMICS)
SOUND: dict[str, int] = {marking: percent for marking, percent, _velocity in DYNAMICS}

# p90 must be at least this many times p10 before the piece leaves mf.
# A 7% gap (150k against 160k) stays put; a real doubling opens the scale.
MIN_SPAN_RATIO = 2.0
# A single print many times a normal minute — the opening and closing
# auctions, or an unlabeled spike — is clipped to this multiple of the
# median before the slot average is taken.
CLIP_MULTIPLE = 4.0


def marking_for_volume(volume: float, low: float, high: float) -> str:
    """Map one slot's average volume onto p–f.

    low and high are the 10th and 90th percentile of those averages. With no
    positive volume to compare, or with a gap smaller than MIN_SPAN_RATIO,
    every traded slot is mf and an untraded one is p.
    """
    if high <= 0:
        return "mf"
    if low > 0 and high / low < MIN_SPAN_RATIO:
        return "mf" if volume > 0 else MARKINGS[0]
    floor = log1p(max(0.0, low))
    ceiling = log1p(high)
    if ceiling <= floor:
        return "mf" if volume > 0 else MARKINGS[0]
    norm = (log1p(max(0.0, volume)) - floor) / (ceiling - floor)
    norm = min(1.0, max(0.0, norm))
    index = min(len(MARKINGS) - 1, int(norm * len(MARKINGS)))
    return MARKINGS[index]


def positive_median(volumes: list[float]) -> float:
    positive = sorted(volume for volume in volumes if volume > 0)
    if not positive:
        return 0.0
    mid = len(positive) // 2
    if len(positive) % 2:
        return positive[mid]
    return (positive[mid - 1] + positive[mid]) / 2


def average_liquidity(groups: list[list[float]]) -> list[float]:
    """Mean volume per candle, after clipping spikes to CLIP_MULTIPLE × median.

    An empty group (a slot whose candles were all auction prints) takes the
    median of the other slots, so it does not become the loudest bar in the piece.
    """
    positive = [volume for group in groups for volume in group if volume > 0]
    ceiling = positive_median(positive) * CLIP_MULTIPLE
    raw: list[float | None] = []
    for group in groups:
        if not group:
            raw.append(None)
            continue
        kept = [min(volume, ceiling) if ceiling > 0 else volume for volume in group]
        raw.append(sum(kept) / len(kept))
    known = [level for level in raw if level is not None]
    fallback = positive_median(known) if known else 0.0
    return [fallback if level is None else level for level in raw]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    low_index = int(rank)
    high_index = min(low_index + 1, len(ordered) - 1)
    weight = rank - low_index
    return ordered[low_index] * (1 - weight) + ordered[high_index] * weight
