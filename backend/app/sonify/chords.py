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
KIND_MAJOR_NINTH = "major-ninth"
KIND_MINOR_NINTH = "minor-ninth"
KIND_DOMINANT_NINTH = "dominant-ninth"


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

    alter: int = 0
    # (pitch class, step letter, alter) for tones that are not the C-major spelling.
    tones: tuple[tuple[int, str, int], ...] = ()

    @property
    def bass_midi(self) -> int:
        """Root kept inside C2–B2 so a minor chord does not drop the bass an octave."""
        return 36 + (self.pitches[0] % 12)

    @property
    def quality_group(self) -> str:
        if self.kind in (KIND_MINOR, KIND_MINOR_SEVENTH, KIND_MINOR_NINTH):
            return "minor"
        if self.kind in (KIND_DOMINANT, KIND_DOMINANT_NINTH):
            return "dominant"
        if self.kind == "half-diminished":
            return "half-diminished"
        if "diminished" in self.kind:
            return "diminished"
        return "major"

    def spelling(self, pitch_class: int) -> tuple[str, int] | None:
        """Explicit step and alter for one pitch class, when this chord owns it."""
        for pc, step, alter in self.tones:
            if pc == pitch_class:
                return step, alter
        return None


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

CMAJ9 = Chord("Cmaj9", "C", KIND_MAJOR_NINTH, "maj9", (60, 64, 67, 71, 74))
FMAJ9 = Chord("Fmaj9", "F", KIND_MAJOR_NINTH, "maj9", (65, 69, 72, 76, 79))
G9 = Chord("G9", "G", KIND_DOMINANT_NINTH, "9", (67, 71, 74, 77, 81))
AM9 = Chord("Am9", "A", KIND_MINOR_NINTH, "m9", (57, 60, 64, 67, 71))
DM9 = Chord("Dm9", "D", KIND_MINOR_NINTH, "m9", (62, 65, 69, 72, 76))

KIND_HALF_DIMINISHED = "half-diminished"
KIND_DIMINISHED_SEVENTH = "diminished-seventh"

# Secondary dominants, borrowed chords, and the missing leading-tone seventh.
# Melody stays on C major; these tones are accompaniment spellings.
BM7B5 = Chord("Bm7b5", "B", KIND_HALF_DIMINISHED, "m7♭5", (71, 74, 77, 81))
D7 = Chord("D7", "D", KIND_DOMINANT, "7", (62, 66, 69, 72), tones=((6, "F", 1),))
E7 = Chord("E7", "E", KIND_DOMINANT, "7", (64, 68, 71, 74), tones=((8, "G", 1),))
A7 = Chord("A7", "A", KIND_DOMINANT, "7", (57, 61, 64, 67), tones=((1, "C", 1),))
C7 = Chord("C7", "C", KIND_DOMINANT, "7", (60, 64, 67, 70), tones=((10, "B", -1),))
FM = Chord("Fm", "F", KIND_MINOR, "m", (65, 68, 72), tones=((8, "A", -1),))
GM = Chord("Gm", "G", KIND_MINOR, "m", (67, 70, 74), tones=((10, "B", -1),))
AF = Chord("Ab", "A", KIND_MAJOR, "", (68, 72, 75), alter=-1, tones=((8, "A", -1), (3, "E", -1)))
BF = Chord("Bb", "B", KIND_MAJOR, "", (70, 74, 77), alter=-1, tones=((10, "B", -1),))
BF7 = Chord(
    "Bb7", "B", KIND_DOMINANT, "7", (70, 74, 77, 80),
    alter=-1, tones=((10, "B", -1), (8, "A", -1)),
)
EF = Chord(
    "Eb", "E", KIND_MAJOR, "", (63, 67, 70),
    alter=-1, tones=((3, "E", -1), (10, "B", -1)),
)
FDIM7 = Chord(
    "F#dim7", "F", KIND_DIMINISHED_SEVENTH, "°7", (66, 69, 72, 75),
    alter=1, tones=((6, "F", 1), (3, "E", -1)),
)

BORROWED: tuple[Chord, ...] = (BM7B5, D7, E7, A7, C7, FM, GM, AF, BF, BF7, EF, FDIM7)

D9 = Chord("D9", "D", KIND_DOMINANT_NINTH, "9", (62, 66, 69, 72, 76), tones=((6, "F", 1),))
E9 = Chord("E9", "E", KIND_DOMINANT_NINTH, "9", (64, 68, 71, 74, 78), tones=((8, "G", 1), (6, "F", 1)))
A9 = Chord("A9", "A", KIND_DOMINANT_NINTH, "9", (57, 61, 64, 67, 71), tones=((1, "C", 1),))
C9 = Chord("C9", "C", KIND_DOMINANT_NINTH, "9", (60, 64, 67, 70, 74), tones=((10, "B", -1),))
FM9 = Chord("Fm9", "F", KIND_MINOR_NINTH, "m9", (65, 68, 72, 75, 79), tones=((8, "A", -1), (3, "E", -1)))
GM9 = Chord("Gm9", "G", KIND_MINOR_NINTH, "m9", (67, 70, 74, 77, 81), tones=((10, "B", -1),))
AFMAJ7 = Chord(
    "Abmaj7", "A", KIND_MAJOR_SEVENTH, "maj7", (68, 72, 75, 79),
    alter=-1, tones=((8, "A", -1), (3, "E", -1)),
)
BFMAJ7 = Chord(
    "Bbmaj7", "B", KIND_MAJOR_SEVENTH, "maj7", (70, 74, 77, 81),
    alter=-1, tones=((10, "B", -1),),
)
BF9 = Chord(
    "Bb9", "B", KIND_DOMINANT_NINTH, "9", (70, 74, 77, 80, 84),
    alter=-1, tones=((10, "B", -1), (8, "A", -1)),
)
EFMAJ7 = Chord(
    "Ebmaj7", "E", KIND_MAJOR_SEVENTH, "maj7", (63, 67, 70, 74),
    alter=-1, tones=((3, "E", -1), (10, "B", -1)),
)

JAZZ_VOICING_BY_NAME: dict[str, Chord] = {
    "D7": D9,
    "E7": E9,
    "A7": A9,
    "C7": C9,
    "Fm": FM9,
    "Gm": GM9,
    "Ab": AFMAJ7,
    "Bb": BFMAJ7,
    "Bb7": BF9,
    "Eb": EFMAJ7,
    "Bm7b5": BM7B5,
    "F#dim7": FDIM7,
}

JAZZ_CHORD_BY_ROOT: dict[str, Chord] = {
    "C": CMAJ9,
    "F": FMAJ9,
    "D": DM9,
    "G": G9,
    "A": AM9,
    "E": EM7,
}


def jazz_chord(chord: Chord) -> Chord:
    """Promote a triad or seventh chord to its Lush/Lo-Fi Jazz voicing."""
    named = JAZZ_VOICING_BY_NAME.get(chord.name)
    if named is not None:
        return named
    return JAZZ_CHORD_BY_ROOT.get(chord.root_step, chord)


def fifth_above_bass(chord: Chord) -> int:
    """MIDI of the chord's fifth above the written bass, diminished when the chord says so."""
    root = chord.bass_midi
    root_pc = chord.pitches[0] % 12
    fifth_pc = chord.pitches[2] % 12
    return root + ((fifth_pc - root_pc) % 12)


def same_harmonic_root(previous: Chord, current: Chord) -> bool:
    """Same root letter and accidental. Original G/G7 still count as one root."""
    if previous.root_step != current.root_step or previous.alter != current.alter:
        return False
    if previous.quality_group == current.quality_group:
        return True
    original = {chord.name for chord in CHORDS}
    return (
        {previous.quality_group, current.quality_group} == {"major", "dominant"}
        and previous.name in original
        and current.name in original
    )


def chords_for_spec(borrowed: bool) -> tuple[Chord, ...]:
    if not borrowed:
        return CHORDS
    return (*CHORDS, *BORROWED)


_BORROWED_EDGES: dict[tuple[str, str], float] = {
    ("C", "D7"): 0.12,
    ("Cmaj7", "D7"): 0.12,
    ("Am", "E7"): 0.16,
    ("Am7", "E7"): 0.16,
    ("Dm", "A7"): 0.16,
    ("Dm7", "A7"): 0.16,
    ("F", "C7"): 0.14,
    ("Fmaj7", "C7"): 0.14,
    ("C", "C7"): 0.08,
    ("C", "Fm"): 0.06,
    ("Am", "Fm"): 0.12,
    ("F", "Fm"): 0.10,
    ("Am", "Ab"): 0.10,
    ("C", "Ab"): 0.05,
    ("Am", "Eb"): 0.08,
    ("C", "Eb"): 0.04,
    ("C", "Bb"): 0.08,
    ("F", "Bb"): 0.14,
    ("Bb", "Bb7"): 0.20,
    ("C", "Gm"): 0.05,
    ("G", "Gm"): 0.08,
    ("Am", "Bm7b5"): 0.08,
    ("Dm", "Bm7b5"): 0.10,
    ("C", "F#dim7"): 0.06,
    ("G", "F#dim7"): 0.04,
    ("D7", "G"): 0.46,
    ("D7", "G7"): 0.34,
    ("E7", "Am"): 0.40,
    ("E7", "Am7"): 0.36,
    ("A7", "Dm"): 0.40,
    ("A7", "Dm7"): 0.36,
    ("C7", "F"): 0.42,
    ("C7", "Fmaj7"): 0.34,
    ("Fm", "C"): 0.30,
    ("Fm", "Ab"): 0.22,
    ("Ab", "Eb"): 0.20,
    ("Ab", "Bb"): 0.16,
    ("Eb", "Bb"): 0.22,
    ("Eb", "Ab"): 0.18,
    ("Bb", "F"): 0.24,
    ("Bb", "Eb"): 0.20,
    ("Bb7", "Eb"): 0.40,
    ("Gm", "C"): 0.28,
    ("Gm", "Bb"): 0.16,
    ("Bm7b5", "C"): 0.34,
    ("Bm7b5", "Am"): 0.30,
    ("F#dim7", "G"): 0.55,
    ("F#dim7", "G7"): 0.35,
}


def borrowed_transition(previous: Chord, current: Chord) -> float:
    """Chord-to-chord weight outside the diatonic matrix. Zero when the pair is absent."""
    return _BORROWED_EDGES.get((previous.name, current.name), 0.0)

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


