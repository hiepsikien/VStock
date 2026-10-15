"""Seventh chords in C major / A minor, Markov transitions, and regime priors."""

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
    def pitch_classes(self) -> frozenset[int]:
        return frozenset(pitch % 12 for pitch in self.pitches)

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

CHORDS: tuple[Chord, ...] = (CMAJ7, FMAJ7, DM7, G7, AM7, EM7)

# Acoustic and functional Markov transition probabilities P(next | previous).
# Every row sums to 1.0 and includes self-transition (staying on the same chord).
# Ungrammatical retrogressions (such as G7 -> Fmaj7/Dm7/Em7 or Dm7 -> Fmaj7) are omitted.
TRANSITIONS: dict[Chord, dict[Chord, float]] = {
    CMAJ7: {FMAJ7: 0.26, AM7: 0.24, CMAJ7: 0.18, DM7: 0.14, G7: 0.10, EM7: 0.08},
    AM7: {FMAJ7: 0.26, CMAJ7: 0.22, AM7: 0.18, DM7: 0.18, EM7: 0.10, G7: 0.06},
    FMAJ7: {DM7: 0.26, G7: 0.22, CMAJ7: 0.22, FMAJ7: 0.16, AM7: 0.14},
    DM7: {G7: 0.34, EM7: 0.20, CMAJ7: 0.16, DM7: 0.16, AM7: 0.14},
    EM7: {AM7: 0.34, FMAJ7: 0.22, EM7: 0.18, DM7: 0.10, CMAJ7: 0.08, G7: 0.08},
    G7: {CMAJ7: 0.50, AM7: 0.32, G7: 0.18},
}

# Gentle cost prior (in scale-step units) nudging ties toward the regime's tonal colour.
REGIME_BIAS: dict[Regime, dict[Chord, float]] = {
    "uptrend": {CMAJ7: 0.0, FMAJ7: 0.04, DM7: 0.06, G7: 0.04, AM7: 0.35, EM7: 0.45},
    "downtrend": {AM7: 0.0, FMAJ7: 0.04, DM7: 0.06, EM7: 0.06, CMAJ7: 0.35, G7: 0.35},
    "sideway": {CMAJ7: 0.0, AM7: 0.02, FMAJ7: 0.20, DM7: 0.30, EM7: 0.35, G7: 0.40},
}

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


def transition_probability(previous: Chord, current: Chord) -> float:
    """Markov transition probability P(current | previous), or 0.0 if disallowed."""
    return TRANSITIONS.get(previous, {}).get(current, 0.0)

