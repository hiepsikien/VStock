"""Adapter between the MusicXML importer dataclasses and the Studio API.

``app.studio.musicxml_import`` is the deterministic parser; this module keeps
one stable, JSON-shaped note contract for the router and the future UI. It also
pins the bar convention at the API boundary:

* parser bars are **0-based** and ``slice_score`` is **inclusive**;
* API requests are **1-based inclusive**, so this adapter subtracts one from
  both ends before calling the parser.

Rests stay in the note stream (``rest: true``, ``midi: null``). The API returns
them separately as rhythm cells so a matrix can draw an explicit rest instead
of leaving a silent gap.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.studio.musicxml_import import (
    ImportedNote,
    ImportedScore,
    MusicXmlImportError,
    parse_musicxml,
    score_summary,
    slice_score as _slice_score,
)

PARSER_MODULE = "app.studio.musicxml_import"

_PITCH_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _pitch_name(midi: int | None) -> str | None:
    if midi is None:
        return None
    octave, pc = divmod(int(midi), 12)
    return f"{_PITCH_NAMES[pc]}{octave - 1}"


def _tie_name(note: ImportedNote) -> str:
    if note.tie_start and note.tie_stop:
        return "continue"
    if note.tie_start:
        return "start"
    if note.tie_stop:
        return "stop"
    return "none"


def _slur_name(note: ImportedNote) -> str:
    if note.slur_start and note.slur_stop:
        return "continue"
    if note.slur_start:
        return "start"
    if note.slur_stop:
        return "stop"
    return "none"


def note_to_dict(note: ImportedNote | Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable JSON note shape used by upload and passage responses."""
    if isinstance(note, Mapping):
        return dict(note)
    return {
        "bar": note.bar,
        "beat": note.beat,
        "duration": note.duration,
        "voice": note.voice,
        "midi": note.midi,
        "written_midi": note.written_midi,
        "staff": note.staff,
        "tie_start": note.tie_start,
        "tie_stop": note.tie_stop,
        "slur_start": note.slur_start,
        "slur_stop": note.slur_stop,
        "chord": note.chord,
        "rest": note.rest,
        "source_measure": note.source_measure,
        # Compatibility spelling used by the existing Studio API/UI helpers.
        "tie": _tie_name(note),
        "slur": _slur_name(note),
        "accent": note.accent,
        "tenuto": note.tenuto,
        "staccato": note.staccato,
        "string": note.string,
        "fret": note.fret,
        "written_pitch": _pitch_name(note.written_midi),
        "sounding_pitch": _pitch_name(note.midi),
    }


def slice_score(
    score: ImportedScore,
    *,
    bar_start: int,
    bar_end: int,
    voices: Iterable[int] | int | None = None,
) -> tuple[dict[str, Any], ...]:
    """Slice by **1-based inclusive** bars and return JSON-shaped notes."""
    notes = _slice_score(
        score,
        bar_start=bar_start - 1,
        bar_end=bar_end - 1,
        voices=voices,
    )
    return tuple(note_to_dict(note) for note in notes)


def score_notes(score: ImportedScore) -> tuple[dict[str, Any], ...]:
    """All notes in the stable JSON shape, including rests."""
    return tuple(note_to_dict(note) for note in score.notes)


__all__ = [
    "ImportedNote",
    "ImportedScore",
    "MusicXmlImportError",
    "PARSER_MODULE",
    "note_to_dict",
    "parse_musicxml",
    "score_notes",
    "score_summary",
    "slice_score",
]
