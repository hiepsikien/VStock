"""Letter dynamics from ppp to fff, as MusicXML 4.0 spells them.

MusicXML prints a dynamic as an empty child of <dynamics>. The eight names
ppp, pp, p, mp, mf, f, ff, fff are all in that content model. pppp and ffff
exist too, and they sit outside the range used here.

Playback is a sibling <sound dynamics="N"/> element. N is a percentage of
MusicXML's default forte, which is MIDI velocity 90. The percentages below
are chosen so round(N / 100 * 90) is the velocity in the third column.
"""

from __future__ import annotations

from math import log1p

# marking, sound-dynamics percent, intended MIDI velocity
DYNAMICS: tuple[tuple[str, int, int], ...] = (
    ("ppp", 18, 16),
    ("pp", 37, 33),
    ("p", 54, 49),
    ("mp", 71, 64),
    ("mf", 89, 80),
    ("f", 107, 96),
    ("ff", 124, 112),
    ("fff", 141, 127),
)

MARKINGS: tuple[str, ...] = tuple(row[0] for row in DYNAMICS)
SOUND: dict[str, int] = {marking: percent for marking, percent, _velocity in DYNAMICS}


def marking_for_volume(volume: float, low: float, high: float) -> str:
    """Map one slot volume onto ppp–fff using log1p between low and high.

    low and high are the reference ends (the 10th and 90th percentile of the
    piece). With no positive volume to compare, every slot is mf: a neutral
    mark, rather than a claim that the session was silent.
    """
    if high <= 0:
        return "mf"
    if high <= low:
        return "mf" if volume > 0 else "ppp"
    floor = log1p(max(0.0, low))
    ceiling = log1p(high)
    if ceiling <= floor:
        return "mf" if volume > 0 else "ppp"
    norm = (log1p(max(0.0, volume)) - floor) / (ceiling - floor)
    norm = min(1.0, max(0.0, norm))
    index = min(len(MARKINGS) - 1, int(norm * len(MARKINGS)))
    if norm >= 1:
        index = len(MARKINGS) - 1
    return MARKINGS[index]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * fraction
    low_index = int(rank)
    high_index = min(low_index + 1, len(ordered) - 1)
    weight = rank - low_index
    return ordered[low_index] * (1 - weight) + ordered[high_index] * weight
