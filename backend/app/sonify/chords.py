"""Triads and seventh chords in C major / A minor, Markov transitions, and regime priors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Regime = Literal["uptrend", "downtrend", "sideway"]

# MusicXML 4.0 harmony/kind values. kind_text is only the printed suffix;
# the root step is stored separately and the symbol reads as C, Am, Cmaj7, G7, Am7.
KIND_MAJOR = "major"
KIND_MINOR = "minor"
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


C = Chord("C", "C", KIND_MAJOR, "", (60, 64, 67))
F = Chord("F", "F", KIND_MAJOR, "", (65, 69, 72))
G = Chord("G", "G", KIND_MAJOR, "", (67, 71, 74))
AM = Chord("Am", "A", KIND_MINOR, "m", (57, 60, 64))
DM = Chord("Dm", "D", KIND_MINOR, "m", (62, 65, 69))
EM = Chord("Em", "E", KIND_MINOR, "m", (64, 67, 71))

CMAJ7 = Chord("Cmaj7", "C", KIND_MAJOR_SEVENTH, "maj7", (60, 64, 67, 71))
FMAJ7 = Chord("Fmaj7", "F", KIND_MAJOR_SEVENTH, "maj7", (65, 69, 72, 76))
G7 = Chord("G7", "G", KIND_DOMINANT, "7", (67, 71, 74, 77))
AM7 = Chord("Am7", "A", KIND_MINOR_SEVENTH, "m7", (57, 60, 64, 67))
DM7 = Chord("Dm7", "D", KIND_MINOR_SEVENTH, "m7", (62, 65, 69, 72))
EM7 = Chord("Em7", "E", KIND_MINOR_SEVENTH, "m7", (64, 67, 71, 74))

TRIADS: tuple[Chord, ...] = (C, F, DM, G, AM, EM)
SEVENTHS: tuple[Chord, ...] = (CMAJ7, FMAJ7, DM7, G7, AM7, EM7)
CHORDS: tuple[Chord, ...] = (*TRIADS, *SEVENTHS)

# Root-to-root functional transition probabilities P(next_root | prev_root).
# Every row sums to 1.0 and includes staying on the same harmonic root.
# Ungrammatical retrogressions (such as G -> F/Dm/Em or Dm -> F) are omitted.
_ROOT_TRANSITIONS: dict[str, dict[str, float]] = {
    "C": {"F": 0.26, "A": 0.24, "C": 0.18, "D": 0.14, "G": 0.10, "E": 0.08},
    "A": {"F": 0.26, "C": 0.22, "A": 0.18, "D": 0.18, "E": 0.10, "G": 0.06},
    "F": {"D": 0.26, "G": 0.22, "C": 0.22, "F": 0.16, "A": 0.14},
    "D": {"G": 0.34, "E": 0.20, "C": 0.16, "D": 0.16, "A": 0.14},
    "E": {"A": 0.34, "F": 0.22, "E": 0.18, "D": 0.10, "C": 0.08, "G": 0.08},
    "G": {"C": 0.50, "A": 0.32, "G": 0.18},
}

# Full 12-chord Markov transition matrix P(next_chord | prev_chord).
# Each allowed target root splits its probability mass equally between its triad and seventh chord,
# so every row across CHORDS sums to 1.0.
TRANSITIONS: dict[Chord, dict[Chord, float]] = {
    src: {
        dst: _ROOT_TRANSITIONS[src.root_step][dst.root_step] * 0.5
        for dst in CHORDS
        if dst.root_step in _ROOT_TRANSITIONS[src.root_step]
    }
    for src in CHORDS
}

_ROOT_REGIME_BIAS: dict[Regime, dict[str, float]] = {
    "uptrend": {"C": 0.0, "F": 0.04, "D": 0.06, "G": 0.04, "A": 0.35, "E": 0.45},
    "downtrend": {"A": 0.0, "F": 0.04, "D": 0.06, "E": 0.06, "C": 0.35, "G": 0.35},
    "sideway": {"C": 0.0, "A": 0.02, "F": 0.20, "D": 0.30, "E": 0.35, "G": 0.40},
}

# A seventh chord adds a fourth pitch class; when the melody does not need that 7th degree
# to reduce quantization loss, a small tension cost lets the cleaner triad win on ties.
SEVENTH_TENSION_COST = 0.05

REGIME_BIAS: dict[Regime, dict[Chord, float]] = {
    regime: {
        chord: _ROOT_REGIME_BIAS[regime][chord.root_step]
        + (SEVENTH_TENSION_COST if len(chord.pitches) == 4 else 0.0)
        for chord in CHORDS
    }
    for regime in ("uptrend", "downtrend", "sideway")
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


def tonic_chords(regime: Regime) -> tuple[Chord, Chord]:
    """The tonic triad and tonic seventh chord for `regime`."""
    seventh = tonic(regime)
    triad = C if seventh == CMAJ7 else AM
    return (triad, seventh)


def transition_probability(previous: Chord, current: Chord) -> float:
    """Markov transition probability P(current | previous), or 0.0 if disallowed."""
    return TRANSITIONS.get(previous, {}).get(current, 0.0)


