"""Seventh chords in C major / A minor, and the three market progressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Regime = Literal["uptrend", "downtrend", "sideway"]

# MusicXML 4.0 harmony/kind values. kind_text is only the printed suffix;
# the root step is stored separately and the symbol reads as Cmaj7, G7, Am7.
KIND_MAJOR_SEVENTH = "major-seventh"
KIND_DOMINANT = "dominant"
KIND_MINOR_SEVENTH = "minor-seventh"


@dataclass(frozen=True)
class Chord:
    name: str
    root_step: str
    kind: str
    kind_text: str
    pitches: tuple[int, ...]

    @property
    def bass_midi(self) -> int:
        """Root kept inside C2–B2 so a minor chord does not drop the bass an octave."""
        return 36 + (self.pitches[0] % 12)


CMAJ7 = Chord("Cmaj7", "C", KIND_MAJOR_SEVENTH, "maj7", (60, 64, 67, 71))
FMAJ7 = Chord("Fmaj7", "F", KIND_MAJOR_SEVENTH, "maj7", (65, 69, 72, 76))
G7 = Chord("G7", "G", KIND_DOMINANT, "7", (67, 71, 74, 77))
AM7 = Chord("Am7", "A", KIND_MINOR_SEVENTH, "m7", (57, 60, 64, 67))
DM7 = Chord("Dm7", "D", KIND_MINOR_SEVENTH, "m7", (62, 65, 69, 72))
EM7 = Chord("Em7", "E", KIND_MINOR_SEVENTH, "m7", (64, 67, 71, 74))

PROGRESSIONS: dict[Regime, tuple[Chord, Chord, Chord, Chord]] = {
    "uptrend": (CMAJ7, FMAJ7, DM7, G7),
    "downtrend": (AM7, FMAJ7, DM7, EM7),
    "sideway": (CMAJ7, AM7, CMAJ7, AM7),
}


def progression(regime: Regime) -> tuple[Chord, Chord, Chord, Chord]:
    try:
        return PROGRESSIONS[regime]
    except KeyError as exc:
        raise ValueError(f"unknown regime: {regime}") from exc


def tonic(regime: Regime) -> Chord:
    return progression(regime)[0]
