"""Harmony dialects beside the tertian Markov catalog.

`COMMON` is the symphony path. `bach`, `villa`, `barrios`, `brouwer`, and `sor`
register in `DIALECTS`. Guitar `classic` resolves to `sor`. An unknown ensemble
stays on `COMMON`.
"""

from __future__ import annotations

from app.sonify.chords import (
    AB_AUG6,
    BF,
    BF7,
    CHORDS,
    D7,
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
    "madd9": frozenset({1}),
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
    # Minor keeps the parent's third. The printed suffix has to carry the "m",
    # because MusicXML joins root-step with kind_text and would otherwise read Cadd9.
    return _build(
        name,
        step,
        alter,
        KIND_OTHER,
        "madd9" if third == 3 else "add9",
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
        if character == "calm" and text in ("sus2", "add9", "madd9"):
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


# Minor circle of fifths, the V/V close, and the German sixth. A pair that
# touches an extra chord and is missing here is illegal (0), because Bb has no
# row in `_ROOT_TRANSITIONS` and minor D7 shares a letter with ii.
_BARRIOS_MINOR: dict[tuple[str, str], float] = {
    ("Fm", "Bb"): 0.42,
    ("Fm7", "Bb"): 0.42,
    ("Fm", "Bb7"): 0.34,
    ("Fm7", "Bb7"): 0.34,
    ("Cm", "Bb"): 0.12,
    ("Cm7", "Bb"): 0.12,
    ("Bb", "Eb"): 0.42,
    ("Bb", "Ebmaj7"): 0.26,
    ("Bb7", "Eb"): 0.50,
    ("Bb7", "Ebmaj7"): 0.34,
    ("Bb", "G"): 0.22,
    ("Bb", "G7"): 0.26,
    ("Bb", "Bb"): 0.18,
    ("Bb", "Bb7"): 0.24,
    ("Bb7", "Bb"): 0.24,
    ("Bb7", "Bb7"): 0.14,
    ("Ab", "D7"): 0.48,
    ("Abmaj7", "D7"): 0.40,
    ("Dm7b5", "D7"): 0.40,
    ("D7", "G"): 0.46,
    ("D7", "G7"): 0.55,
    ("D7", "D7"): 0.12,
    ("Fm", "Ab+6"): 0.24,
    ("Fm7", "Ab+6"): 0.20,
    ("Cm", "Ab+6"): 0.06,
    ("Cm7", "Ab+6"): 0.06,
    ("Ab+6", "G"): 0.62,
    ("Ab+6", "G7"): 0.55,
}
# Major borrows the existing secondary dominants and only adds the choro chain.
_BARRIOS_MAJOR: dict[tuple[str, str], float] = {
    ("E7", "A7"): 0.55,
    ("A7", "D7"): 0.55,
    ("D7", "G7"): 0.55,
}
_BARRIOS_MINOR_EXTRA: tuple[Chord, ...] = (BF, BF7, D7, AB_AUG6)


class BarriosDialect(HarmonyDialect):
    """Functional minor circle and a major secondary-dominant chain. No color tones."""

    name = "barrios"

    def extra(self, mode: str) -> tuple[Chord, ...]:
        if mode == "minor":
            return _BARRIOS_MINOR_EXTRA
        return ()

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        if mode == "major":
            return _BARRIOS_MAJOR.get((prev.name, curr.name))
        if prev in _BARRIOS_MINOR_EXTRA or curr in _BARRIOS_MINOR_EXTRA:
            return _BARRIOS_MINOR.get((prev.name, curr.name), 0.0)
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
        del character
        if chord not in self.extra(mode):
            return True
        if pedal or phrase_downbeat:
            return False
        return True

    def bias(
        self,
        chord: Chord,
        character: MovementCharacter | None,
        mode: str,
        strong_pitch_classes: frozenset[int] = frozenset(),
    ) -> float:
        del strong_pitch_classes
        if mode != "minor":
            return 0.0
        if character == "volatile" and chord.name in {"Bb", "Bb7", "D7"}:
            return -0.06
        if character == "rally" and chord.name in {"D7", "Bb7"}:
            return -0.04
        return 0.0

    def color_credit(
        self,
        chord: Chord,
        strong_pitch_classes: frozenset[int],
        prev: Chord | None,
    ) -> float:
        del chord, strong_pitch_classes, prev
        return 0.0


def _pick(catalog: tuple[Chord, ...], names: tuple[str, ...]) -> tuple[Chord, ...]:
    found = {chord.name: chord for chord in catalog}
    return tuple(found[name] for name in names)


# Estudios Sencillos suspensions plus the open-string planing of Estudio No. 6.
_BROUWER_MAJOR_COLOR = _pick(
    _MAJOR_EXTRA,
    ("Csus2", "Dsus2", "Esus4", "Fsus2", "G7sus4", "Bbsus2", "Ebsus2"),
)
# Un Día de Noviembre keeps the minor add9/sus colors and the bVII door.
_BROUWER_MINOR_COLOR = _pick(
    _MINOR_EXTRA,
    ("Csus2", "Dsus4", "Ebsus2", "Fsus2", "G7sus4", "Cmadd9", "Fmadd9"),
)
_BROUWER_MAJOR = _BROUWER_MAJOR_COLOR
_BROUWER_MINOR = _BROUWER_MINOR_COLOR + (BF, BF7, D7)
_BROUWER_COLOR = frozenset(_BROUWER_MAJOR_COLOR + _BROUWER_MINOR_COLOR)
_BROUWER_CREDIT = 0.65
_BROUWER_COLOR_WEIGHT = 0.30
_BROUWER_PARENT_WEIGHT = 0.40
_BROUWER_PLANING: dict[tuple[str, str], float] = {}
for _left, _right in zip(
    ("Csus2", "Bbsus2", "Fsus2"),
    ("Bbsus2", "Fsus2", "Ebsus2"),
):
    _BROUWER_PLANING[(_left, _right)] = 0.32
    _BROUWER_PLANING[(_right, _left)] = 0.32
# Fm/Fmadd9 -> Bb/Bb7 -> Eb/Ebmaj7 -> G7sus4 -> Cm.
_BROUWER_MODAL: dict[tuple[str, str], float] = {
    pair: 0.42
    for pair in (
        ("Fm", "Bb"),
        ("Fm", "Bb7"),
        ("Fmadd9", "Bb"),
        ("Fmadd9", "Bb7"),
        ("Bb", "Eb"),
        ("Bb", "Ebmaj7"),
        ("Bb7", "Eb"),
        ("Bb7", "Ebmaj7"),
        ("Eb", "G7sus4"),
        ("Ebmaj7", "G7sus4"),
        ("G7sus4", "Cm"),
    )
}
_BROUWER_CALM = frozenset({"maj7", "m7", "add9", "madd9", "sus2"})
_BROUWER_EDGE_TEXT = frozenset({"sus4", "7sus4"})
_BROUWER_EDGE_NAMES = frozenset({"Bb7", "Bm7b5", "Dm7b5", "E7"})
_BROUWER_DOWNBEAT = frozenset({"Bbsus2", "Ebsus2", "Bb", "Bb7", "D7"})


class BrouwerDialect(HarmonyDialect):
    """Afro-Cuban modal harmony with suspended planing.

    Villa's sus2/add9 colors and Barrios's bVII / secondary dominant sit in
    one catalog. Parallel sus2 planing and the minor bVII chain are explicit.
    """

    name = "brouwer"

    def extra(self, mode: str) -> tuple[Chord, ...]:
        if mode == "minor":
            return _BROUWER_MINOR
        return _BROUWER_MAJOR

    def _owns(self, chord: Chord, mode: str) -> bool:
        return chord in self.extra(mode)

    def _color(self, chord: Chord, mode: str) -> bool:
        return self._owns(chord, mode) and chord in _BROUWER_COLOR

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        planned = _BROUWER_PLANING.get((prev.name, curr.name))
        if planned is not None and (mode == "major" or "Bbsus2" not in {prev.name, curr.name}):
            return planned
        if mode == "minor":
            modal = _BROUWER_MODAL.get((prev.name, curr.name))
            if modal is not None:
                return modal
        owns = self._owns(prev, mode) or self._owns(curr, mode)
        if not owns:
            return None
        if prev != curr and prev.root_step == curr.root_step and prev.alter == curr.alter:
            parent = _parent_triad(curr, mode)
            if parent is not None and curr == parent and self._color(prev, mode):
                return _BROUWER_PARENT_WEIGHT
            return _BROUWER_COLOR_WEIGHT
        return 0.0

    def shares_root(self, prev: Chord, curr: Chord) -> bool:
        if prev.root_step != curr.root_step or prev.alter != curr.alter:
            return False
        kinds = {prev.kind_text, curr.kind_text}
        return (
            prev.quality_group == "suspended"
            or curr.quality_group == "suspended"
            or bool(kinds & {"add9", "madd9"})
        )

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
        if not self._owns(chord, mode):
            return True
        if pedal:
            return False
        if phrase_downbeat and chord.name in _BROUWER_DOWNBEAT:
            return False
        return True

    def is_parent(self, prev: Chord, curr: Chord, mode: str) -> bool:
        if not self._color(curr, mode):
            return False
        parent = _parent_triad(curr, mode)
        return parent is not None and prev == parent

    def opening_pitch_classes(self, chord: Chord, mode: str) -> frozenset[int]:
        if not self._color(chord, mode):
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
        del mode, strong_pitch_classes
        if character in {"calm", "rally"} and chord.kind_text in _BROUWER_CALM:
            return -0.06
        if character in {"volatile", "selloff"} and (
            chord.kind_text in _BROUWER_EDGE_TEXT or chord.name in _BROUWER_EDGE_NAMES
        ):
            return -0.07
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
        if chord not in _BROUWER_COLOR:
            return 0.0
        if strong_pitch_classes & color_pitch_classes(chord):
            return _BROUWER_CREDIT
        return 0.0


# Classical functional weights. A missing pair keeps the shared Markov row.
# G/G7 back to IV or ii is a retrogression and stays illegal.
_SOR_MAJOR: dict[tuple[str, str], float] = {
    ("C", "G"): 0.28,
    ("C", "G7"): 0.26,
    ("C", "F"): 0.28,
    ("C", "Dm"): 0.18,
    ("C", "Am"): 0.18,
    ("F", "G"): 0.36,
    ("F", "G7"): 0.40,
    ("F", "C"): 0.24,
    ("F", "Dm"): 0.22,
    ("F", "Dm7"): 0.18,
    ("F", "D7"): 0.18,
    ("Dm", "G"): 0.40,
    ("Dm", "G7"): 0.44,
    ("Dm7", "G"): 0.40,
    ("Dm7", "G7"): 0.46,
    ("G", "C"): 0.62,
    ("G7", "C"): 0.68,
    ("G", "Am"): 0.20,
    ("G7", "Am"): 0.18,
    ("C", "D7"): 0.14,
    ("Am", "D7"): 0.20,
    ("D7", "G"): 0.52,
    ("D7", "G7"): 0.48,
    ("C", "E7"): 0.10,
    ("Am", "E7"): 0.18,
    ("E7", "Am"): 0.58,
    ("Dm", "A7"): 0.16,
    ("A7", "Dm"): 0.55,
    ("C", "C7"): 0.12,
    ("C7", "F"): 0.58,
    ("F", "F#dim7"): 0.12,
    ("F#dim7", "G"): 0.60,
    ("F#dim7", "G7"): 0.40,
    ("G", "F"): 0.0,
    ("G7", "F"): 0.0,
    ("G", "Dm"): 0.0,
    ("G7", "Dm"): 0.0,
    ("G", "Dm7"): 0.0,
    ("G7", "Dm7"): 0.0,
}
_SOR_MINOR: dict[tuple[str, str], float] = {
    ("Cm", "Fm"): 0.34,
    ("Cm", "G"): 0.26,
    ("Cm", "G7"): 0.28,
    ("Cm", "Dm7b5"): 0.22,
    ("Cm", "Eb"): 0.18,
    ("Cm", "Ab"): 0.14,
    ("Fm", "G"): 0.40,
    ("Fm", "G7"): 0.44,
    ("Fm", "Dm7b5"): 0.24,
    ("Fm", "D7"): 0.20,
    ("Fm", "Cm"): 0.22,
    ("Dm7b5", "G"): 0.44,
    ("Dm7b5", "G7"): 0.48,
    ("Dm7b5", "D7"): 0.24,
    ("Eb", "Ab"): 0.38,
    ("Eb", "Fm"): 0.26,
    ("Eb", "G"): 0.22,
    ("Eb", "G7"): 0.24,
    ("Ab", "Dm7b5"): 0.36,
    ("Ab", "Fm"): 0.28,
    ("Ab", "G"): 0.32,
    ("Ab", "G7"): 0.34,
    ("Ab", "D7"): 0.26,
    ("D7", "G"): 0.52,
    ("D7", "G7"): 0.56,
    ("D7", "D7"): 0.12,
    ("G", "Cm"): 0.60,
    ("G7", "Cm"): 0.66,
    ("G", "Ab"): 0.20,
    ("G7", "Ab"): 0.18,
}
_SOR_MAJOR_BANNED = frozenset({
    "Cmaj7", "Fmaj7", "Am7", "Em7",
    "Ab", "Eb", "Bb", "Bb7", "Gm", "Fm", "Bm7b5",
})
_SOR_MAJOR_SECONDARY = frozenset({"D7", "E7", "A7", "C7", "F#dim7"})
_SOR_MINOR_BANNED = frozenset({"Cm7", "Fm7", "Ebmaj7", "Abmaj7"})
_SOR_MINOR_PASSING = frozenset({"D7", "F#dim7"})
_SOR_PREFERENCE = -0.06
# F is the chordal seventh of G7. D is scale degree 2, the fifth of that dominant.
_G7_COLOR = frozenset({2, 5})


class SorDialect(HarmonyDialect):
    """Triads, V7, and secondary dominants. No pop or jazz sevenths."""

    name = "sor"

    def extra(self, mode: str) -> tuple[Chord, ...]:
        if mode == "minor":
            return (D7,)
        return ()

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        table = _SOR_MAJOR if mode == "major" else _SOR_MINOR
        key = (prev.name, curr.name)
        if key in table:
            return table[key]
        # D7 is not in the minor letter table. An unlisted edge would read ii.
        if mode == "minor" and (prev.name == "D7" or curr.name == "D7"):
            return 0.0
        return None

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
        if pedal:
            return chord.name == ("Cm" if mode == "minor" else "C")
        if mode == "minor":
            if chord.name in _SOR_MINOR_BANNED:
                return False
            if phrase_downbeat and chord.name in _SOR_MINOR_PASSING:
                return False
            return True
        if chord.name in _SOR_MAJOR_BANNED:
            return False
        if phrase_downbeat and chord.name in _SOR_MAJOR_SECONDARY:
            return False
        return True

    def bias(
        self,
        chord: Chord,
        character: MovementCharacter | None,
        mode: str,
        strong_pitch_classes: frozenset[int] = frozenset(),
    ) -> float:
        primary = {"C", "F", "G"} if mode == "major" else {"Cm", "Fm", "G"}
        if chord.name in primary:
            return _SOR_PREFERENCE
        if chord.name == "G7" and (strong_pitch_classes & _G7_COLOR):
            return _SOR_PREFERENCE
        if character == "rally" and chord.name in {"C", "F", "G", "G7", "D7"}:
            return _SOR_PREFERENCE
        if character == "selloff" and chord.name in {
            "Cm", "Fm", "Dm7b5", "G", "G7", "Ab", "F#dim7",
        }:
            return _SOR_PREFERENCE
        return 0.0


# Circle of fifths, secondary dominants, and the leading-tone diminished seventh.
# Every positive weight sits in the Baroque band. G/G7 back to IV or ii is blocked.
_BACH_MAJOR: dict[tuple[str, str], float] = {
    ("C", "F"): 0.46,
    ("C", "Fmaj7"): 0.44,
    ("F", "Bm7b5"): 0.46,
    ("Fmaj7", "Bm7b5"): 0.48,
    ("Bm7b5", "Em"): 0.48,
    ("Bm7b5", "E7"): 0.52,
    ("Em", "Am"): 0.50,
    ("Em", "Am7"): 0.44,
    ("E7", "Am"): 0.58,
    ("E7", "Am7"): 0.46,
    ("Am", "Dm"): 0.48,
    ("Am", "Dm7"): 0.46,
    ("Am7", "Dm"): 0.48,
    ("Am7", "Dm7"): 0.50,
    ("Am", "D7"): 0.44,
    ("Dm", "G"): 0.50,
    ("Dm", "G7"): 0.54,
    ("Dm7", "G"): 0.50,
    ("Dm7", "G7"): 0.56,
    ("G", "C"): 0.58,
    ("G7", "C"): 0.62,
    ("G", "Am"): 0.42,
    ("G7", "Am"): 0.42,
    ("C", "C7"): 0.42,
    ("C7", "F"): 0.58,
    ("C", "A7"): 0.42,
    ("Em", "A7"): 0.44,
    ("A7", "Dm"): 0.56,
    ("A7", "Dm7"): 0.48,
    ("A7", "D7"): 0.44,
    ("F", "D7"): 0.44,
    ("Dm", "D7"): 0.44,
    ("D7", "G"): 0.56,
    ("D7", "G7"): 0.58,
    ("F", "F#dim7"): 0.42,
    ("Dm", "F#dim7"): 0.42,
    ("F#dim7", "G"): 0.60,
    ("F#dim7", "G7"): 0.56,
    ("C", "E7"): 0.42,
    ("G", "F"): 0.0,
    ("G7", "F"): 0.0,
    ("G", "Dm"): 0.0,
    ("G7", "Dm"): 0.0,
}
# Minor circle through bVII and III, plus the full Chaconne descent back to i.
# Positive sequence weights stay inside the Baroque band. An unlisted pair that
# touches Bb, Bb7, or D7 is illegal rather than letter-row ii.
_BACH_MINOR: dict[tuple[str, str], float] = {
    ("Cm", "Fm"): 0.48,
    ("Cm", "Fm7"): 0.44,
    ("Fm", "Bb"): 0.48,
    ("Fm", "Bb7"): 0.52,
    ("Fm7", "Bb"): 0.48,
    ("Fm7", "Bb7"): 0.54,
    ("Cm", "Bb"): 0.42,
    ("Cm", "Bb7"): 0.42,
    ("Bb", "Eb"): 0.54,
    ("Bb7", "Eb"): 0.60,
    ("Bb", "G"): 0.42,
    ("Bb", "G7"): 0.44,
    ("Bb", "Bb"): 0.42,
    ("Bb7", "Bb7"): 0.42,
    ("Bb", "Bb7"): 0.44,
    ("Bb7", "Bb"): 0.42,
    ("Eb", "Ab"): 0.50,
    ("Eb", "Fm"): 0.44,
    ("Eb", "Dm7b5"): 0.42,
    ("Eb", "G7"): 0.42,
    ("Ab", "Fm"): 0.48,
    ("Ab", "Fm7"): 0.44,
    ("Ab", "Dm7b5"): 0.50,
    ("Ab", "F#dim7"): 0.46,
    ("Ab", "D7"): 0.46,
    ("Ab", "G"): 0.46,
    ("Ab", "G7"): 0.48,
    ("Fm", "Dm7b5"): 0.48,
    ("Fm7", "Dm7b5"): 0.46,
    ("Fm", "G"): 0.48,
    ("Fm", "G7"): 0.52,
    ("Fm7", "G"): 0.46,
    ("Fm7", "G7"): 0.50,
    ("Dm7b5", "G"): 0.52,
    ("Dm7b5", "G7"): 0.56,
    ("Dm7b5", "D7"): 0.46,
    ("Fm", "D7"): 0.44,
    ("Fm7", "D7"): 0.44,
    ("Fm", "F#dim7"): 0.46,
    ("Fm7", "F#dim7"): 0.44,
    ("F#dim7", "G"): 0.60,
    ("F#dim7", "G7"): 0.58,
    ("D7", "G"): 0.54,
    ("D7", "G7"): 0.58,
    ("D7", "D7"): 0.42,
    ("G", "Cm"): 0.58,
    ("G7", "Cm"): 0.62,
    ("G", "Ab"): 0.46,
    ("G7", "Ab"): 0.46,
    ("Cm", "G"): 0.46,
    ("Cm", "G7"): 0.48,
    ("Cm", "Ab"): 0.42,
    ("Cm", "Dm7b5"): 0.44,
}
_BACH_MINOR_EXTRA_NAMES = frozenset({"Bb", "Bb7", "D7"})
_BACH_SUSPENDED_TEXT = frozenset({"sus2", "sus4", "7sus4", "add9", "madd9"})
_BACH_MAJOR_BANNED = frozenset({"Cmaj7", "Em7", "Ab", "Eb", "Bb", "Bb7", "Gm", "Fm"})
_BACH_MAJOR_PASSING = frozenset({"D7", "E7", "A7", "C7", "F#dim7", "Bm7b5"})
_BACH_MINOR_BANNED = frozenset({"Cm7", "Ebmaj7", "Abmaj7"})
_BACH_MINOR_PASSING = frozenset({"Bb", "Bb7", "D7", "F#dim7", "Dm7b5"})
_BACH_MAJOR_DRIVERS = frozenset({"C", "F", "Fmaj7", "Dm", "Dm7", "G", "G7", "Am", "Am7", "Bm7b5", "D7", "E7", "A7", "F#dim7"})
_BACH_MINOR_DRIVERS = frozenset({
    "Cm", "Fm", "Fm7", "Bb", "Bb7", "Eb", "Ab", "Dm7b5", "D7", "F#dim7", "G", "G7",
})
_BACH_PREFERENCE = -0.06


class BachDialect(HarmonyDialect):
    """Circle-of-fifths sequences, secondary dominants, and the minor bVII door.

    Lute-suite and Chaconne harmony. No modern suspensions, and no seventh
    chord on a pedal bar.
    """

    name = "bach"

    def extra(self, mode: str) -> tuple[Chord, ...]:
        if mode == "minor":
            return (BF, BF7, D7)
        return ()

    def transition(self, prev: Chord, curr: Chord, mode: str) -> float | None:
        if mode == "minor":
            key = (prev.name, curr.name)
            if key in _BACH_MINOR:
                return _BACH_MINOR[key]
            if prev.name in _BACH_MINOR_EXTRA_NAMES or curr.name in _BACH_MINOR_EXTRA_NAMES:
                return 0.0
            return None
        return _BACH_MAJOR.get((prev.name, curr.name))

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
        if pedal:
            return chord.name == ("Cm" if mode == "minor" else "C")
        if chord.quality_group == "suspended" or chord.kind_text in _BACH_SUSPENDED_TEXT:
            return False
        if mode == "minor":
            if chord.name in _BACH_MINOR_BANNED:
                return False
            if phrase_downbeat and chord.name in _BACH_MINOR_PASSING:
                return False
            return True
        if chord.name in _BACH_MAJOR_BANNED:
            return False
        if phrase_downbeat and chord.name in _BACH_MAJOR_PASSING:
            return False
        return True

    def bias(
        self,
        chord: Chord,
        character: MovementCharacter | None,
        mode: str,
        strong_pitch_classes: frozenset[int] = frozenset(),
    ) -> float:
        del character, strong_pitch_classes
        drivers = _BACH_MINOR_DRIVERS if mode == "minor" else _BACH_MAJOR_DRIVERS
        if chord.name in drivers:
            return _BACH_PREFERENCE
        return 0.0


COMMON = HarmonyDialect()
VILLA = VillaDialect()
BARRIOS = BarriosDialect()
BROUWER = BrouwerDialect()
SOR = SorDialect()
BACH = BachDialect()
DIALECTS: dict[str, HarmonyDialect] = {
    "bach": BACH,
    "villa": VILLA,
    "barrios": BARRIOS,
    "brouwer": BROUWER,
    "sor": SOR,
}


def dialect_for(ensemble: str, variant: str | None = None) -> HarmonyDialect:
    """Resolve a dialect. Symphony `classic` stays on `COMMON`.

    Guitar `classic` is Fernando Sor. `ensemble="sor"` selects the same dialect
    for either variant.
    """
    if variant == "guitar" and ensemble == "classic":
        return SOR
    return DIALECTS.get(ensemble, COMMON)
