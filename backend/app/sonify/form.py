"""30-bar daily recap: intro, three 8-bar phrases, outro.

Tempo is 90. A bar is 4 beats, a chord is held for 2 bars (8 beats), and a
phrase is 4 chords (8 bars, 32 beats). Regime changes land on the phrase
downbeats — musical bars 3, 11 and 19 when counted from 1 — which already
includes the 2-bar intro. Intro and outro pedal the tonic of the neighbouring
phrase instead of running a progression of their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.sonify.chords import Chord, Regime, progression, tonic

MUSICAL_BARS = 30
BEATS_PER_BAR = 4
BPM = 90
PHRASE_STARTS = (2, 10, 18)
PHRASE_BARS = 8
OUTRO_START = 26
SECTION_STARTS = (0, *PHRASE_STARTS, OUTRO_START)

Section = Literal["intro", "phrase", "outro"]


@dataclass(frozen=True)
class ChordSlot:
    start: int
    length: int
    chord: Chord
    regime: Regime
    section: Section

    def bars(self) -> range:
        return range(self.start, self.start + self.length)


def plan_slots(regimes: tuple[Regime, Regime, Regime]) -> tuple[ChordSlot, ...]:
    if len(regimes) != 3:
        raise ValueError("expected one regime per phrase")
    slots = [ChordSlot(0, 2, tonic(regimes[0]), regimes[0], "intro")]
    for phrase, start in enumerate(PHRASE_STARTS):
        for index, chord in enumerate(progression(regimes[phrase])):
            slots.append(
                ChordSlot(start + index * 2, 2, chord, regimes[phrase], "phrase")
            )
    slots.append(
        ChordSlot(OUTRO_START, MUSICAL_BARS - OUTRO_START, tonic(regimes[2]), regimes[2], "outro")
    )
    covered = [bar for slot in slots for bar in slot.bars()]
    if covered != list(range(MUSICAL_BARS)):
        raise RuntimeError("chord slots do not cover the 30-bar form")
    return tuple(slots)
