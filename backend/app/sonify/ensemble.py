"""Alternate instrument rows for one variant.

The five parts stay P5, P1, P2, P3, P4. `classic` is the row already written
into `musicxml.py`. The other rows only change which MuseSounds voice plays
each part, plus the few pitch edges that voice cannot cover.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

from app.sonify.model import ENSEMBLES, Ensemble, NoteEvent, Score, Variant

# part id, part name (MuseSounds voice), MusicXML instrument, channel, program
PartSpec = tuple[str, str, str, str, str]

_ROWS: dict[tuple[Variant, Ensemble], tuple[PartSpec, ...]] = {
    ("symphony", "wood"): (
        ("P5", "Piccolo", "Piccolo", "5", "73"),
        ("P1", "Oboe", "Oboe", "1", "69"),
        ("P2", "Clarinet in Bb", "Clarinet", "2", "72"),
        ("P3", "Harp", "Harp", "3", "47"),
        ("P4", "Contrabassoon", "Contrabassoon", "4", "71"),
    ),
    ("symphony", "brass"): (
        ("P5", "Glockenspiel", "Glockenspiel", "5", "10"),
        ("P1", "Trumpet", "Trumpet", "1", "57"),
        ("P2", "Trombone", "Trombone", "2", "58"),
        ("P3", "French Horns a6", "Horn in F", "3", "61"),
        ("P4", "Tuba", "Tuba", "4", "59"),
    ),
    ("jazz", "soul"): (
        ("P5", "Electric LP - Clean", "Electric Guitar", "5", "28"),
        ("P1", "Trumpet", "Trumpet", "1", "57"),
        ("P2", "Trombone", "Trombone", "2", "58"),
        ("P3", "Wurly 200A", "Electric Piano", "3", "5"),
        ("P4", "Electric Bass", "Electric Bass (finger)", "4", "34"),
    ),
    ("jazz", "organ"): (
        ("P5", "Electric SC - Clean", "Electric Guitar", "5", "28"),
        ("P1", "Soprano Saxophone", "Soprano Saxophone", "1", "65"),
        ("P2", "Baritone Saxophone", "Baritone Saxophone", "2", "68"),
        ("P3", "Hammond Organ", "Hammond Organ", "3", "17"),
        ("P4", "Electric Bass", "Electric Bass (finger)", "4", "34"),
    ),
    ("minimalist", "mallet"): (
        ("P5", "Crotales", "Crotales", "5", "11"),
        ("P1", "Marimba", "Marimba", "1", "13"),
        ("P2", "Full Choir", "Voice", "2", "53"),
        ("P3", "Harpsichord", "Harpsichord", "3", "7"),
        ("P4", "Electric Bass", "Electric Bass (finger)", "4", "34"),
    ),
    ("minimalist", "guitar"): (
        ("P5", "Flute 2", "Flute", "5", "74"),
        ("P1", "Acoustic Steel Plucked", "Acoustic Guitar", "1", "26"),
        ("P2", "Cellos", "Cello", "2", "43"),
        ("P3", "Upright Piano", "Upright Piano", "3", "1"),
        ("P4", "Electric Bass", "Electric Bass (finger)", "4", "34"),
    ),
    ("ambient", "breath"): (
        ("P5", "Handchimes", "Handchimes", "5", "113"),
        ("P1", "English Horn", "English Horn", "1", "70"),
        ("P2", "Bass Clarinet", "Bass Clarinet", "2", "72"),
        ("P3", "Trombones a3", "Trombone", "3", "58"),
        ("P4", "Contrabassoon", "Contrabassoon", "4", "71"),
    ),
    ("ambient", "choir"): (
        ("P5", "Handbells", "Hand Bells", "5", "113"),
        ("P1", "Clarinet in Bb", "Clarinet", "1", "72"),
        ("P2", "Tenors", "Tenor", "2", "53"),
        ("P3", "Violas", "Viola", "3", "42"),
        ("P4", "Basses", "Bass", "4", "53"),
    ),
}

_ALLOWED: dict[Variant, frozenset[Ensemble]] = {
    "symphony": frozenset({"classic", "wood", "brass"}),
    "jazz": frozenset({"classic", "soul", "organ"}),
    "minimalist": frozenset({"classic", "mallet", "guitar"}),
    "ambient": frozenset({"classic", "breath", "choir"}),
}

OBOE_FLOOR = 58  # Bb3
CLARINET_FLOOR = 50  # D3
TRUMPET_CEILING = 82  # Bb5
HORN_FILL_CEILING = 77  # F5
SOPRANO_FLOOR = 56  # Ab3
VIOLA_FLOOR = 48  # C3
BASS_VOICE_FLOOR = 36  # C2


def ensemble_for(variant: Variant, name: str) -> Ensemble:
    """Accept a query value for this variant. `classic` is the row already shipping."""
    if name not in ENSEMBLES or name not in _ALLOWED[variant]:
        raise ValueError(f"ensemble {name} is not part of {variant}")
    return cast(Ensemble, name)


def parts_for(variant: Variant, ensemble: Ensemble) -> tuple[PartSpec, ...] | None:
    """Replacement part row, or None when the variant keeps its original instruments."""
    if ensemble == "classic":
        return None
    return _ROWS[(variant, ensemble)]


def sounds_at_pitch(ensemble: Ensemble) -> bool:
    """Choir basses sing the written pitch. Every other bass part is written an octave up."""
    return ensemble == "choir"


def fit_ensemble(score: Score) -> Score:
    """Fold the notes a voice cannot play. `classic` and the held English-horn top stay put."""
    if score.ensemble == "classic":
        return score
    shift = score.key.semitones
    if score.ensemble == "wood":
        return replace(
            score,
            lead=_map(score.lead, lambda midi: _above(midi, shift, OBOE_FLOOR)),
            support=_map(score.support, lambda midi: _above(midi, shift, CLARINET_FLOOR)),
        )
    if score.ensemble == "brass":
        return replace(
            score,
            lead=_map(score.lead, lambda midi: _below(midi, shift, TRUMPET_CEILING)),
            comp=_map(score.comp, lambda midi: _below(midi, shift, HORN_FILL_CEILING)),
        )
    if score.ensemble == "organ":
        stay: list[NoteEvent] = []
        moved: list[NoteEvent] = []
        for note in score.lead:
            if note.midi is not None and note.midi + shift < SOPRANO_FLOOR:
                moved.append(note)
            else:
                stay.append(note)
        return replace(score, lead=tuple(stay), support=score.support + tuple(moved))
    if score.ensemble == "choir":
        return replace(
            score,
            comp=_map(score.comp, lambda midi: _above(midi, shift, VIOLA_FLOOR)),
            low=_map(score.low, lambda midi: _above(midi, shift, BASS_VOICE_FLOOR)),
        )
    return score


def _above(midi: int, shift: int, floor: int) -> int:
    while midi + shift < floor:
        midi += 12
    return midi


def _below(midi: int, shift: int, ceiling: int) -> int:
    while midi + shift > ceiling:
        midi -= 12
    return midi


def _map(notes: tuple[NoteEvent, ...], edit) -> tuple[NoteEvent, ...]:
    return tuple(
        replace(note, midi=edit(note.midi)) if note.midi is not None else note for note in notes
    )
