"""Harmony dialects beside the tertian Markov catalog.

`COMMON` is the symphony path. Only `villa` registers today; Sor and Barrios
stay on `COMMON` until a later dialect is added to `DIALECTS`.
"""

from __future__ import annotations

from app.sonify.chords import (
    BF,
    CHORDS,
    EF,
    KIND_OTHER,
    KIND_SUSPENDED_FOURTH,
    KIND_SUSPENDED_SECOND,
    MINOR_CATALOG,
    MINOR_DIATONIC,
    Chord,
    _ROOT_TRANSITIONS,
)
from app.sonify.keys import MovementCharacter

_MAJOR_PCS = frozenset({0, 2, 4, 5, 7, 9, 11})
_MINOR_PCS = frozenset({0, 2, 3, 5, 7, 8, 10})
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_LETTERS = "CDEFGAB"
_COLOR_DEGREES = {
    "sus2": frozenset({1}),
    "sus4": frozenset({3}),
    "add9": frozenset({1}),
    "7sus4": frozenset({3, 6}),
}
_COLOR_CREDIT = 0.70
# Same-root color change. The parent-triad return is checked first.
_COLOR_WEIGHT = 0.30
_PARENT_WEIGHT = 0.40
_PLANING_EDGES = {
    ("Csus2", "Bbsus2"): 0.22,
    ("Fsus2", "Ebsus2"): 0.22,
    ("Bbsus2", "F"): 0.34,
    ("Ebsus2", "F"): 0.34,
}


class HarmonyDialect:
    """Default catalog. Every hook is a no-op so the existing Viterbi is unchanged."""

    name = "common"

    def extra(self, mode: str) -> tuple[Chord, ...]:
        del mode
        return ()

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        del prev, curr, mode
        return None

    def shares_root(self, prev: Chord, curr: Chord) -> bool:
        del prev, curr
        return False

    def allowed(
        self,
        chord: Chord,
        *,
        pedal: bool,
        phrase_downbeat: bool,
        character: MovementCharacter | None,
        mode: str,
    ) -> bool:
        del chord, pedal, phrase_downbeat, character, mode
        return True

    def bias(
        self,
        chord: Chord,
        character: MovementCharacter | None,
        mode: str,
        strong_pitch_classes: frozenset[int] = frozenset(),
    ) -> float:
        del chord, character, mode, strong_pitch_classes
        return 0.0

    def is_parent(self, prev: Chord, curr: Chord, mode: str) -> bool:
        del prev, curr, mode
        return False

    def opening_pitch_classes(self, chord: Chord, mode: str) -> frozenset[int]:
        del mode
        return chord.pitch_classes

    def color_credit(
        self,
        chord: Chord,
        strong_pitch_classes: frozenset[int],
        prev: Chord | None,
    ) -> float:
        del chord, strong_pitch_classes, prev
        return 0.0


def _scale(mode: str) -> frozenset[int]:
    return _MINOR_PCS if mode == "minor" else _MAJOR_PCS


def _pc(step: str, alter: int) -> int:
    return (_NATURAL[step] + alter) % 12


def _display(step: str, alter: int) -> str:
    if alter < 0:
        return step + "b" * -alter
    if alter > 0:
        return step + "#" * alter
    return step


def _tones(root_step: str, root_alter: int, degrees: tuple[int, ...], pitches: tuple[int, ...]) -> tuple[tuple[int, str, int], ...]:
    root_letter = _LETTERS.index(root_step)
    tones: list[tuple[int, str, int]] = []
    for index, pitch in enumerate(pitches):
        step = _LETTERS[(root_letter + degrees[index]) % 7]
        natural = _NATURAL[step]
        alter = (pitch % 12 - natural + 6) % 12 - 6
        if alter != 0:
            tones.append((pitch % 12, step, alter))
    if root_alter != 0 and all(tone[1] != root_step for tone in tones):
        tones.insert(0, (_pc(root_step, root_alter), root_step, root_alter))
    return tuple(tones)


def _build(
    name: str,
    root_step: str,
    root_alter: int,
    kind: str,
    kind_text: str,
    semitones: tuple[int, ...],
    degrees: tuple[int, ...],
) -> Chord:
    root = 60 + _pc(root_step, root_alter)
    pitches = tuple(root + interval for interval in semitones)
    return Chord(
        name,
        root_step,
        kind,
        kind_text,
        pitches,
        alter=root_alter,
        tones=_tones(root_step, root_alter, degrees, pitches),
        degrees=degrees,
    )


def _sus2(step: str, alter: int = 0) -> Chord:
    return _build(
        f"{_display(step, alter)}sus2",
        step,
        alter,
        KIND_SUSPENDED_SECOND,
        "sus2",
        (0, 2, 7),
        (0, 1, 4),
    )


def _sus4(step: str, alter: int = 0) -> Chord:
    return _build(
        f"{_display(step, alter)}sus4",
        step,
        alter,
        KIND_SUSPENDED_FOURTH,
        "sus4",
        (0, 5, 7),
        (0, 3, 4),
    )


def _add9(step: str, alter: int, third: int, name: str) -> Chord:
    return _build(
        name,
        step,
        alter,
        KIND_OTHER,
        "add9",
        (0, third, 7, 14),
        (0, 2, 4, 1),
    )


def _dom_sus(step: str, alter: int = 0) -> Chord:
    return _build(
        f"{_display(step, alter)}7sus4",
        step,
        alter,
        KIND_SUSPENDED_FOURTH,
        "7sus4",
        (0, 5, 7, 10),
        (0, 3, 4, 6),
    )


def _on_scale(root: int, interval: int, mode: str) -> bool:
    return (root + interval) % 12 in _scale(mode)


def _keep_color(root: int, intervals: tuple[int, ...], mode: str) -> bool:
    return all(_on_scale(root, interval, mode) for interval in intervals)


def _triads(catalog: tuple[Chord, ...]) -> dict[tuple[str, int], Chord]:
    return {
        (chord.root_step, chord.alter): chord
        for chord in catalog
        if len(chord.pitches) == 3 and chord.quality_group != "suspended"
    }


def _roots(mode: str) -> tuple[tuple[str, int], ...]:
    catalog = MINOR_DIATONIC if mode == "minor" else CHORDS
    seen: list[tuple[str, int]] = []
    for chord in catalog:
        if chord.name == "F#dim7":
            continue
        key = (chord.root_step, chord.alter)
        if key not in seen:
            seen.append(key)
    return tuple(seen)


def _catalog(mode: str) -> tuple[Chord, ...]:
    scale = _scale(mode)
    chords: list[Chord] = []
    for step, alter in _roots(mode):
        root = _pc(step, alter)
        if _keep_color(root, (2,), mode):
            chords.append(_sus2(step, alter))
        if _keep_color(root, (5,), mode):
            chords.append(_sus4(step, alter))
        if _keep_color(root, (5, 10), mode):
            chords.append(_dom_sus(step, alter))
    if mode == "major":
        for step in ("C", "F", "G"):
            chords.append(_add9(step, 0, 4, f"{step}add9"))
    else:
        for name, step, alter in (("Cmadd9", "C", 0), ("Fmadd9", "F", 0)):
            chords.append(_add9(step, alter, 3, name))
    kept: list[Chord] = []
    for chord in chords:
        if chord.pitch_classes & scale:
            kept.append(chord)
    if mode == "major":
        kept.extend((_sus2("B", -1), _sus2("E", -1)))
    return tuple(kept)


_MAJOR_EXTRA = _catalog("major")
_MINOR_EXTRA = _catalog("minor")
_EXTRA = {"major": _MAJOR_EXTRA, "minor": _MINOR_EXTRA}
_PLANING = frozenset(chord for chord in _MAJOR_EXTRA if chord.name in {"Bbsus2", "Ebsus2"})
_PARENTS = {
    "major": _triads(CHORDS),
    "minor": _triads(MINOR_CATALOG),
}
_DIATONIC = {"major": frozenset(CHORDS), "minor": frozenset(MINOR_CATALOG)}


def _root_probability(prev: Chord, curr: Chord) -> float:
    """Letter-table door. The same letter with a different alter is not that row."""
    if prev.root_step == curr.root_step and prev.alter != curr.alter:
        return 0.0
    return _ROOT_TRANSITIONS.get(prev.root_step, {}).get(curr.root_step, 0.0)


def _parent_triad(chord: Chord, mode: str) -> Chord | None:
    """The 3-note parent. Planing Eb and Bb are borrowed, so they are not in CHORDS."""
    parent = _PARENTS[mode].get((chord.root_step, chord.alter))
    if parent is not None:
        return parent
    if mode == "major" and chord.name == "Bbsus2":
        return BF
    if mode == "major" and chord.name == "Ebsus2":
        return EF
    return None


def color_pitch_classes(chord: Chord) -> frozenset[int]:
    """Pitch classes of the 2nd, 4th, 9th, or b7. Root and fifth are not colors."""
    wanted = _COLOR_DEGREES.get(chord.kind_text, frozenset())
    if not wanted or not chord.degrees:
        return frozenset()
    return frozenset(
        chord.pitches[index] % 12
        for index, degree in enumerate(chord.degrees)
        if degree in wanted
    )


class VillaDialect(HarmonyDialect):
    name = "villa"

    def extra(self, mode: str) -> tuple[Chord, ...]:
        return _EXTRA[mode]

    def _villa(self, chord: Chord, mode: str) -> bool:
        return chord in _EXTRA[mode]

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        if mode == "major" and (prev in _PLANING or curr in _PLANING):
            return _PLANING_EDGES.get((prev.name, curr.name), 0.0)
        if prev != curr:
            parent = _PARENTS[mode].get((curr.root_step, curr.alter))
            same_root = prev.root_step == curr.root_step and prev.alter == curr.alter
            if (
                same_root
                and parent is not None
                and curr == parent
                and self._villa(prev, mode)
            ):
                return _PARENT_WEIGHT
            if same_root and (self._villa(prev, mode) or self._villa(curr, mode)):
                return _COLOR_WEIGHT
            if self._villa(curr, mode):
                prob = _root_probability(prev, curr)
                if prob > 0.0:
                    return prob
            if self._villa(prev, mode) and curr in _DIATONIC[mode]:
                prob = _root_probability(prev, curr)
                if prob > 0.0:
                    return prob
        if self._villa(prev, mode) or self._villa(curr, mode):
            return 0.0
        return None

    def shares_root(self, prev: Chord, curr: Chord) -> bool:
        if prev.root_step != curr.root_step or prev.alter != curr.alter:
            return False
        return prev.quality_group == "suspended" or curr.quality_group == "suspended"

    def allowed(
        self,
        chord: Chord,
        *,
        pedal: bool,
        phrase_downbeat: bool,
        character: MovementCharacter | None,
        mode: str,
    ) -> bool:
        del character
        if not self._villa(chord, mode):
            return True
        if pedal:
            return False
        if mode == "major" and phrase_downbeat and chord in _PLANING:
            return False
        return True

    def is_parent(self, prev: Chord, curr: Chord, mode: str) -> bool:
        parent = _parent_triad(curr, mode)
        return parent is not None and prev == parent

    def opening_pitch_classes(self, chord: Chord, mode: str) -> frozenset[int]:
        """Hear a villa color as its parent triad until that root is held.

        Stripping the color out of the sus chord itself drops the parent's
        other scale tone. Ebsus2 then keeps only Eb and Bb, and the bar cannot
        be priced on C major.
        """
        if not self._villa(chord, mode):
            return chord.pitch_classes
        parent = _parent_triad(chord, mode)
        if parent is not None:
            return parent.pitch_classes
        return chord.pitch_classes - color_pitch_classes(chord)

    def bias(
        self,
        chord: Chord,
        character: MovementCharacter | None,
        mode: str,
        strong_pitch_classes: frozenset[int] = frozenset(),
    ) -> float:
        if not self._villa(chord, mode):
            return 0.0
        # A fifth or a root does not buy the color discount. Calm −0.08 would
        # otherwise cancel the 0.08 floor and undercut F with Fsus2.
        if not (strong_pitch_classes & color_pitch_classes(chord)):
            return 0.0
        text = chord.kind_text
        if character == "calm" and text in ("sus2", "add9"):
            return -0.08
        if character == "volatile" and (
            text == "7sus4" or (mode == "major" and chord.name in {"Bbsus2", "Ebsus2"})
        ):
            return -0.08
        if character == "rally" and text == "sus4":
            return -0.04
        if character == "selloff" and mode == "minor" and (
            chord.quality_group == "suspended" or chord.name == "Absus2"
        ):
            return -0.08
        return 0.0

    def color_credit(
        self,
        chord: Chord,
        strong_pitch_classes: frozenset[int],
        prev: Chord | None,
    ) -> float:
        if prev is None or not chord.degrees:
            return 0.0
        if chord.root_step != prev.root_step or chord.alter != prev.alter:
            return 0.0
        if chord not in _MAJOR_EXTRA and chord not in _MINOR_EXTRA:
            return 0.0
        if strong_pitch_classes & color_pitch_classes(chord):
            return _COLOR_CREDIT
        return 0.0


COMMON = HarmonyDialect()
VILLA = VillaDialect()
DIALECTS: dict[str, HarmonyDialect] = {"villa": VILLA}


def dialect_for(ensemble: str) -> HarmonyDialect:
    return DIALECTS.get(ensemble, COMMON)
