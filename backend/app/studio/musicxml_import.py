"""Deterministic solo-guitar MusicXML importer.

This module reads a MusicXML 4.0 ``score-partwise`` document and returns a
plain, immutable score value. It is deliberately narrow:

* no network, no Gemini, no UI, no database, and no renderer;
* the first ``<part>`` only, with a warning when the document has more;
* written pitch is converted to sounding pitch by ``guitar_transpose``
  (default ``-12``, because guitar music is written an octave high);
* repeats, endings, multi-part scores, and grace notes are reported as
  warnings and are *not* expanded or performed.

The writer in :mod:`app.sonify.musicxml` is intentionally not reused: it is a
one-way score-to-XML writer with its own part layout, and importing through it
would invert the wrong abstraction.

Timing model
------------
MusicXML places notes with a cursor in *divisions* per quarter note. The
importer keeps that cursor per measure as an exact :class:`fractions.Fraction`
and emits quarter-note beats and durations as floats. ``<chord/>`` notes reuse
the onset of the preceding non-chord note. ``<backup>``/``<forward>`` move the
cursor, and tuplet durations are already expressed in divisions, so they need
no ratio arithmetic.

Every note carries its 1-based MusicXML voice as ``voice``. Non-numeric voice
labels are assigned stable integers in first-appearance order. ``bar`` is the
0-based measure index; ``source_measure`` keeps the printed ``number``
attribute for provenance.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

__all__ = [
    "ImportedNote",
    "ImportedScore",
    "MusicXmlImportError",
    "parse_musicxml",
    "score_summary",
    "slice_score",
]


class MusicXmlImportError(ValueError):
    """The document is not a supported, well-formed solo-guitar score."""


@dataclass(frozen=True)
class ImportedNote:
    """One imported MusicXML note.

    ``midi`` is the sounding pitch and ``written_midi`` is the pitch as
    written in the file. Both are ``None`` for rests. ``beat`` is a
    quarter-note position inside ``bar`` and ``duration`` is in quarter beats.
    ``chord`` is true only for notes that carried a ``<chord/>`` marker, which
    makes them members of the chord that starts at the same onset.
    """

    bar: int
    beat: float
    duration: float
    voice: int
    midi: int | None
    written_midi: int | None
    staff: int = 1
    tie_start: bool = False
    tie_stop: bool = False
    slur_start: bool = False
    slur_stop: bool = False
    chord: bool = False
    rest: bool = False
    accent: bool = False
    tenuto: bool = False
    staccato: bool = False
    string: int | None = None
    fret: int | None = None
    source_measure: str = ""


@dataclass(frozen=True)
class ImportedScore:
    """A compact, deterministic import result for one part."""

    id: str
    source_hash: str
    filename: str | None
    title: str
    meter: str
    key_fifths: int
    key_mode: str
    tempo: float | None
    measure_count: int
    part_count: int
    notes: tuple[ImportedNote, ...]
    warnings: tuple[str, ...]


_STEP_PC = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}

# Duration of a metronome beat unit in quarter notes. `<beat-unit-dot>` adds
# half of the preceding value each time.
_BEAT_UNIT_QUARTERS = {
    "breve": 8.0,
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "16th": 0.25,
    "32nd": 0.125,
    "64th": 0.0625,
    "128th": 0.03125,
    "256th": 0.015625,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_musicxml(
    data: bytes,
    *,
    filename: str | None = None,
    guitar_transpose: int = -12,
) -> ImportedScore:
    """Parse one solo-guitar ``score-partwise`` document.

    ``guitar_transpose`` is added to every written MIDI pitch to produce the
    sounding pitch. The default ``-12`` matches standard guitar notation.
    Out-of-range written or sounding pitches raise :class:`MusicXmlImportError`
    rather than being clamped. Passing ``0`` imports the written pitches
    unchanged, which is useful for inspection and tests.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data must be bytes-like")
    if filename is not None and not isinstance(filename, str):
        raise TypeError("filename must be a string or None")
    if not isinstance(guitar_transpose, int) or isinstance(guitar_transpose, bool):
        raise TypeError("guitar_transpose must be an integer")

    raw = bytes(data)
    source_hash = hashlib.sha256(raw).hexdigest()
    if not raw:
        raise MusicXmlImportError("the MusicXML document is empty")
    if raw[:2] == b"PK":
        raise MusicXmlImportError(
            "compressed MusicXML (.mxl) is not supported; unzip it and pass the "
            "extracted .musicxml/.xml bytes"
        )

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        label = f"{filename}: " if filename else ""
        raise MusicXmlImportError(f"{label}not well-formed MusicXML: {exc}") from None

    _strip_namespaces(root)
    if root.tag == "score-timewise":
        raise MusicXmlImportError(
            "score-timewise is not supported; convert the document to "
            "score-partwise first"
        )
    if root.tag != "score-partwise":
        raise MusicXmlImportError(
            f"expected a score-partwise document, found <{root.tag}>"
        )

    parts = root.findall("part")
    if not parts:
        raise MusicXmlImportError("the document has no <part> elements")

    parser = _Parser(guitar_transpose=guitar_transpose)
    if len(parts) > 1:
        parser.warn(
            f"{len(parts)} parts found; only the first part "
            f"({parts[0].get('id') or 'without id'}) is imported"
        )
    parser.parse_part(parts[0])

    meter = parser.meter
    if meter is None:
        meter = "4/4"
        parser.warn("no time signature found; assumed 4/4")
    if not parser.key_seen:
        parser.warn("no key signature found; assumed C major")

    if (
        parser.score_transpose is not None
        and parser.score_transpose != guitar_transpose
    ):
        parser.warn(
            f"the score declares a transpose of {parser.score_transpose:+d} "
            f"semitones but guitar_transpose={guitar_transpose:+d} was used"
        )

    notes = tuple(sorted(parser.notes, key=_note_sort_key))
    digest = source_hash
    return ImportedScore(
        id=f"musicxml:{digest[:16]}",
        source_hash=digest,
        filename=filename,
        title=_score_title(root, parts[0], filename),
        meter=meter,
        key_fifths=parser.key_fifths,
        key_mode=parser.key_mode,
        tempo=parser.tempo,
        measure_count=parser.measure_count,
        part_count=len(parts),
        notes=notes,
        warnings=parser.warnings.as_tuple(),
    )


def slice_score(
    score: ImportedScore,
    *,
    bar_start: int,
    bar_end: int,
    voices: Iterable[int] | int | None = None,
) -> tuple[ImportedNote, ...]:
    """Return notes in the inclusive bar range ``[bar_start, bar_end]``.

    ``voices`` is an optional filter of 1-based voice numbers. Boundary
    violations raise ``ValueError``; the score itself is never modified.
    """
    if not isinstance(score, ImportedScore):
        raise TypeError("score must be an ImportedScore")
    _check_int(bar_start, "bar_start")
    _check_int(bar_end, "bar_end")
    if bar_start < 0:
        raise ValueError("bar_start must be >= 0")
    if bar_end < bar_start:
        raise ValueError("bar_end must be >= bar_start")
    if bar_end >= score.measure_count:
        raise ValueError(
            f"bar_end {bar_end} is outside the score "
            f"(0..{score.measure_count - 1})"
        )

    selected: frozenset[int] | None = None
    if voices is not None:
        if isinstance(voices, int) and not isinstance(voices, bool):
            voices = (voices,)
        values: list[int] = []
        for voice in voices:
            _check_int(voice, "voices entry")
            if voice < 1:
                raise ValueError("voices entries must be >= 1")
            values.append(voice)
        selected = frozenset(values)

    return tuple(
        note
        for note in score.notes
        if bar_start <= note.bar <= bar_end
        and (selected is None or note.voice in selected)
    )


def score_summary(score: ImportedScore) -> dict[str, Any]:
    """Return compact, JSON-friendly metadata for API and UI listings.

    Keys are camelCase to match the Studio API boundary. ``noteCount`` counts
    sounding notes only; ``restCount`` is reported separately.
    """
    if not isinstance(score, ImportedScore):
        raise TypeError("score must be an ImportedScore")

    sounding = [note for note in score.notes if not note.rest]
    pitches = [note.midi for note in sounding if note.midi is not None]
    return {
        "id": score.id,
        "sourceHash": score.source_hash,
        "filename": score.filename,
        "title": score.title,
        "meter": score.meter,
        "keyFifths": score.key_fifths,
        "keyMode": score.key_mode,
        "tempo": None if score.tempo is None else round(score.tempo, 6),
        "measureCount": score.measure_count,
        "partCount": score.part_count,
        "eventCount": len(score.notes),
        "noteCount": len(sounding),
        "restCount": len(score.notes) - len(sounding),
        "voices": sorted({note.voice for note in score.notes}),
        "lowestMidi": min(pitches) if pitches else None,
        "highestMidi": max(pitches) if pitches else None,
        "tieStarts": sum(1 for note in score.notes if note.tie_start),
        "tieStops": sum(1 for note in score.notes if note.tie_stop),
        "slurStarts": sum(1 for note in score.notes if note.slur_start),
        "slurStops": sum(1 for note in score.notes if note.slur_stop),
        "warnings": list(score.warnings),
    }


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


class _Warnings:
    """Insertion-ordered warnings with exact-duplicate suppression."""

    def __init__(self) -> None:
        self._items: list[str] = []
        self._seen: set[str] = set()

    def add(self, message: str) -> None:
        if message not in self._seen:
            self._seen.add(message)
            self._items.append(message)

    def as_tuple(self) -> tuple[str, ...]:
        return tuple(self._items)


class _Parser:
    def __init__(self, *, guitar_transpose: int) -> None:
        self.guitar_transpose = guitar_transpose
        self.warnings = _Warnings()
        self.notes: list[ImportedNote] = []

        self.divisions = 1
        self.measure_count = 0
        self.bar = 0
        self.source_measure = "1"

        self.meter: str | None = None
        self.current_meter: str | None = None
        self.key_fifths = 0
        self.key_mode = "major"
        self.key_seen = False
        self.current_key: tuple[int, str] | None = None
        self.tempo: float | None = None
        self.score_transpose: int | None = None
        self.current_clef: str | None = None

        self.voice_map: dict[str, int] = {}
        self.cursor = Fraction(0)
        self.last_onset: Fraction | None = None
        self.last_duration_units: int | None = None

    # -- helpers ---------------------------------------------------------

    def warn(self, message: str) -> None:
        self.warnings.add(message)

    def _measure(self) -> str:
        position = self.bar + 1
        label = self.source_measure or str(position)
        if label == str(position):
            return f"measure {label}"
        return f"measure {label} (bar {position})"

    def parse_part(self, part: ET.Element) -> None:
        measures = part.findall("measure")
        if not measures:
            raise MusicXmlImportError(
                f"part {part.get('id') or '(no id)'} has no <measure> elements"
            )
        self.measure_count = len(measures)
        self.voice_map = _voice_map(part)
        for index, measure in enumerate(measures):
            self._parse_measure(index, measure)

    def _parse_measure(self, index: int, measure: ET.Element) -> None:
        self.bar = index
        number = (measure.get("number") or "").strip()
        self.source_measure = number or str(index + 1)
        self.cursor = Fraction(0)
        self.last_onset = None
        self.last_duration_units = None

        for child in measure:
            if not isinstance(child.tag, str):
                continue
            if child.tag == "attributes":
                self._attributes(child)
            elif child.tag == "note":
                self._note(child)
            elif child.tag == "backup":
                duration = self._duration_units(child, what="backup")
                if duration is None:
                    continue
                if duration <= 0:
                    self.warn(
                        f"{self._measure()}: backup with non-positive duration "
                        "ignored"
                    )
                    continue
                self.cursor -= Fraction(duration, self.divisions)
                if self.cursor < 0:
                    self.cursor = Fraction(0)
                    self.warn(
                        f"{self._measure()}: backup past the start of the bar "
                        "was clamped to beat 0"
                    )
            elif child.tag == "forward":
                duration = self._duration_units(child, what="forward")
                if duration is None:
                    continue
                if duration <= 0:
                    self.warn(
                        f"{self._measure()}: forward with non-positive duration "
                        "ignored"
                    )
                    continue
                self.cursor += Fraction(duration, self.divisions)
            elif child.tag == "direction":
                self._direction(child)
            elif child.tag == "barline":
                self._barline(child)

    # -- attributes ------------------------------------------------------

    def _attributes(self, attributes: ET.Element) -> None:
        divisions_text = _child_text(attributes, "divisions")
        if divisions_text is not None:
            divisions = _int_text(divisions_text)
            if divisions is None or divisions <= 0:
                self.warn(
                    f"{self._measure()}: invalid divisions {divisions_text!r} "
                    "ignored"
                )
            else:
                self.divisions = divisions

        key = attributes.find("key")
        if key is not None:
            self._key(key)

        time = attributes.find("time")
        if time is not None:
            self._time(time)

        clef = attributes.find("clef")
        if clef is not None:
            self._clef(clef)

        transpose = attributes.find("transpose")
        if transpose is not None:
            chromatic = _child_int(transpose, "chromatic", 0)
            octave_change = _child_int(transpose, "octave-change", 0)
            octaves = octave_change + (1 if transpose.find("double") is not None else 0)
            total = chromatic + 12 * octaves
            if self.score_transpose is None:
                self.score_transpose = total
            elif total != self.score_transpose:
                self.warn(
                    f"{self._measure()}: the score transpose changes to "
                    f"{total:+d} semitones; written pitches are still read as "
                    "written"
                )
                self.score_transpose = total

    def _key(self, key: ET.Element) -> None:
        fifths_text = _child_text(key, "fifths")
        mode_text = _child_text(key, "mode")
        fifths = 0 if fifths_text is None else _int_text(fifths_text)
        if fifths is None:
            self.warn(
                f"{self._measure()}: invalid key fifths {fifths_text!r}; "
                "using 0"
            )
            fifths = 0
        mode = (mode_text or "major").lower()
        current = (fifths, mode)
        if not self.key_seen:
            self.key_fifths = fifths
            self.key_mode = mode
            self.key_seen = True
        elif current != self.current_key:
            self.warn(
                f"{self._measure()}: key changes from "
                f"{self.current_key[0]} fifths/{self.current_key[1]} to "
                f"{fifths} fifths/{mode}; the summary keeps the first key"
            )
        self.current_key = current

    def _time(self, time: ET.Element) -> None:
        if time.find("senza-misura") is not None:
            self.warn(
                f"{self._measure()}: senza misura has no fixed meter; "
                "the current meter is kept"
            )
            return

        beats_text = _child_text(time, "beats")
        beat_type_text = _child_text(time, "beat-type")
        if beats_text is None or beat_type_text is None:
            self.warn(
                f"{self._measure()}: incomplete time signature ignored"
            )
            return
        try:
            beats = sum(int(part) for part in beats_text.split("+"))
            beat_type = int(beat_type_text)
        except ValueError:
            self.warn(
                f"{self._measure()}: invalid time signature "
                f"{beats_text}/{beat_type_text} ignored"
            )
            return
        if beats <= 0 or beat_type <= 0:
            self.warn(
                f"{self._measure()}: invalid time signature "
                f"{beats_text}/{beat_type_text} ignored"
            )
            return

        meter = f"{beats}/{beat_type}"
        if self.meter is None:
            self.meter = meter
        elif meter != self.current_meter:
            self.warn(
                f"{self._measure()}: meter changes from {self.current_meter} "
                f"to {meter}; the summary keeps {self.meter}"
            )
        self.current_meter = meter

    def _clef(self, clef: ET.Element) -> None:
        sign = _child_text(clef, "sign")
        line_text = _child_text(clef, "line")
        if sign is None:
            self.warn(f"{self._measure()}: clef without a sign ignored")
            return
        line = "" if line_text is None else line_text
        current = f"{sign}{line}"
        if self.current_clef is None:
            self.current_clef = current
        elif current != self.current_clef:
            self.warn(
                f"{self._measure()}: clef changes from "
                f"{self.current_clef} to {current}; pitches are imported at "
                "their written values"
            )
            self.current_clef = current

    # -- directions and barlines ----------------------------------------

    def _direction(self, direction: ET.Element) -> None:
        sound = direction.find("sound")
        tempo_text = None if sound is None else sound.get("tempo")
        if tempo_text:
            try:
                bpm = float(tempo_text)
            except ValueError:
                self.warn(
                    f"{self._measure()}: invalid <sound tempo> "
                    f"{tempo_text!r} ignored"
                )
            else:
                self._set_tempo(bpm)
                return

        for direction_type in direction.findall("direction-type"):
            metronome = direction_type.find("metronome")
            if metronome is None:
                continue
            per_minute = _child_text(metronome, "per-minute")
            if per_minute is None:
                continue
            try:
                bpm = float(per_minute)
            except ValueError:
                self.warn(
                    f"{self._measure()}: invalid metronome per-minute "
                    f"{per_minute!r} ignored"
                )
                return
            unit = _child_text(metronome, "beat-unit") or "quarter"
            quarters = _BEAT_UNIT_QUARTERS.get(unit)
            if quarters is None:
                self.warn(
                    f"{self._measure()}: unknown metronome beat unit "
                    f"{unit!r}; reading per-minute as quarter-note BPM"
                )
                quarters = 1.0
            factor = 1.0
            dot = 0.5
            for _ in metronome.findall("beat-unit-dot"):
                factor += dot
                dot /= 2.0
            self._set_tempo(bpm * quarters * factor)
            return

    def _set_tempo(self, bpm: float) -> None:
        if not math.isfinite(bpm) or bpm <= 0:
            self.warn(f"{self._measure()}: non-positive tempo ignored")
            return
        if self.tempo is None:
            self.tempo = bpm
            return
        if abs(bpm - self.tempo) > 1e-6:
            self.warn(
                f"{self._measure()}: tempo changes to {bpm:g} BPM; the summary "
                f"keeps the first tempo ({self.tempo:g} BPM)"
            )

    def _barline(self, barline: ET.Element) -> None:
        for repeat in barline.findall("repeat"):
            direction = (repeat.get("direction") or "unspecified").strip()
            self.warn(
                f"{self._measure()}: repeat ({direction}) is not expanded; "
                "the bar is imported once"
            )
        for ending in barline.findall("ending"):
            number = (ending.get("number") or "?").strip()
            self.warn(
                f"{self._measure()}: ending {number} is not expanded; "
                "the bar is imported once"
            )

    # -- notes -----------------------------------------------------------

    def _duration_units(
        self, element: ET.Element, *, what: str, warn_missing: bool = True
    ) -> int | None:
        text = _child_text(element, "duration")
        if text is None:
            if warn_missing:
                self.warn(f"{self._measure()}: {what} without <duration> ignored")
            return None
        value = _int_text(text)
        if value is None:
            self.warn(
                f"{self._measure()}: {what} with invalid duration {text!r} "
                "ignored"
            )
            return None
        return value

    def _note(self, note: ET.Element) -> None:
        if note.find("grace") is not None:
            self.warn(
                f"{self._measure()}: grace note(s) skipped (grace has no "
                "performed duration)"
            )
            return

        if note.find("cue") is not None:
            self.warn(
                f"{self._measure()}: cue note(s) imported as sounding; cue "
                "status is not preserved"
            )

        if _has_tuplet(note):
            self.warn(
                f"{self._measure()}: tuplet imported as fractional durations "
                "(ratio and bracket are not preserved)"
            )

        is_rest = note.find("rest") is not None
        is_chord = note.find("chord") is not None
        duration_units = self._duration_units(
            note, what="note", warn_missing=not is_chord
        )
        if duration_units is None:
            if is_chord and self.last_duration_units is not None:
                duration_units = self.last_duration_units
                self.warn(
                    f"{self._measure()}: chord note without <duration> reused "
                    "the previous duration"
                )
            else:
                if is_chord:
                    self.warn(
                        f"{self._measure()}: chord note without a usable "
                        "duration skipped"
                    )
                return
        if duration_units <= 0:
            self.warn(
                f"{self._measure()}: note with non-positive duration skipped"
            )
            return

        if is_chord:
            if self.last_onset is None:
                onset = self.cursor
                self.warn(
                    f"{self._measure()}: chord note without a preceding note "
                    "was placed at the cursor"
                )
            else:
                onset = self.last_onset
        else:
            onset = self.cursor
            self.last_onset = onset
            self.last_duration_units = duration_units
            self.cursor += Fraction(duration_units, self.divisions)

        written_midi: int | None = None
        sounding_midi: int | None = None
        if not is_rest:
            pitch = note.find("pitch")
            if pitch is None:
                self.warn(
                    f"{self._measure()}: unpitched note skipped (solo-guitar "
                    "import needs <pitch>)"
                )
                return
            written_midi = self._written_midi(pitch)
            if written_midi is None:
                return
            sounding_midi = written_midi + self.guitar_transpose
            if not 0 <= written_midi <= 127:
                raise MusicXmlImportError(
                    f"{self._measure()}: written MIDI {written_midi} is outside "
                    "0..127"
                )
            if not 0 <= sounding_midi <= 127:
                raise MusicXmlImportError(
                    f"{self._measure()}: sounding MIDI {sounding_midi} "
                    f"(written {written_midi} with guitar_transpose="
                    f"{self.guitar_transpose:+d}) is outside 0..127"
                )

        tie_start, tie_stop = _tie_flags(note)
        slur_start, slur_stop = _slur_flags(note)
        notations = note.find("notations")
        accent = (
            notations is not None
            and notations.find("articulations/accent") is not None
        )
        tenuto = (
            notations is not None
            and notations.find("articulations/tenuto") is not None
        )
        staccato = (
            notations is not None
            and notations.find("articulations/staccato") is not None
        )
        string = _optional_int(
            _child_text(notations, "technical/string")
            if notations is not None
            else None
        )
        fret = _optional_int(
            _child_text(notations, "technical/fret")
            if notations is not None
            else None
        )
        voice_text = _child_text(note, "voice")
        voice = self.voice_map.get(voice_text or "", 1)
        staff = _staff(note, self._measure(), self.warn)

        self.notes.append(
            ImportedNote(
                bar=self.bar,
                beat=float(onset),
                duration=float(Fraction(duration_units, self.divisions)),
                voice=voice,
                midi=sounding_midi,
                written_midi=written_midi,
                staff=staff,
                tie_start=tie_start,
                tie_stop=tie_stop,
                slur_start=slur_start,
                slur_stop=slur_stop,
                chord=is_chord,
                rest=is_rest,
                accent=accent,
                tenuto=tenuto,
                staccato=staccato,
                string=string,
                fret=fret,
                source_measure=self.source_measure,
            )
        )

    def _written_midi(self, pitch: ET.Element) -> int | None:
        step_text = _child_text(pitch, "step")
        octave_text = _child_text(pitch, "octave")
        if step_text is None or octave_text is None:
            self.warn(
                f"{self._measure()}: pitch without <step>/<octave> skipped"
            )
            return None
        step = step_text.upper()
        if step not in _STEP_PC:
            self.warn(
                f"{self._measure()}: unknown pitch step {step_text!r} skipped"
            )
            return None
        octave = _int_text(octave_text)
        if octave is None:
            self.warn(
                f"{self._measure()}: invalid pitch octave {octave_text!r} "
                "skipped"
            )
            return None

        alter = 0
        alter_text = _child_text(pitch, "alter")
        if alter_text is not None:
            try:
                raw_alter = float(alter_text)
            except ValueError:
                self.warn(
                    f"{self._measure()}: invalid pitch alter {alter_text!r} "
                    "treated as 0"
                )
            else:
                if not raw_alter.is_integer():
                    self.warn(
                        f"{self._measure()}: microtonal alter rounded to the "
                        "nearest semitone"
                    )
                alter = int(round(raw_alter))
        return (octave + 1) * 12 + _STEP_PC[step] + alter


# ---------------------------------------------------------------------------
# XML and value helpers
# ---------------------------------------------------------------------------


def _strip_namespaces(root: ET.Element) -> None:
    """Make local tag names available to ordinary ``find``/``findall``."""
    for element in root.iter():
        if isinstance(element.tag, str) and "}" in element.tag:
            element.tag = element.tag.rsplit("}", 1)[-1]


def _child_text(
    element: ET.Element, path: str, default: str | None = None
) -> str | None:
    child = element.find(path)
    if child is None or child.text is None:
        return default
    text = child.text.strip()
    return text or default


def _optional_int(text: str | None) -> int | None:
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _int_text(text: str) -> int | None:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _child_int(element: ET.Element, path: str, default: int) -> int:
    text = _child_text(element, path)
    if text is None:
        return default
    value = _int_text(text)
    return default if value is None else value


def _check_int(value: Any, name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")


def _score_title(
    root: ET.Element, part: ET.Element, filename: str | None
) -> str:
    for path in ("work/work-title", "movement-title"):
        title = _child_text(root, path)
        if title:
            return title
    part_id = part.get("id")
    part_list = root.find("part-list")
    score_part = None
    if part_list is not None:
        score_parts = part_list.findall("score-part")
        for candidate in score_parts:
            if part_id is None or candidate.get("id") == part_id:
                score_part = candidate
                break
        if score_part is None and score_parts:
            score_part = score_parts[0]
    if score_part is not None:
        name = _child_text(score_part, "part-name")
        if name:
            return name
    if filename:
        stem = Path(filename).stem.strip()
        if stem:
            return stem
    return "Untitled"


def _voice_map(part: ET.Element) -> dict[str, int]:
    """Map raw voice labels to stable positive integers.

    Numeric labels keep their number. Non-numeric labels take the next free
    integer in first-appearance order. The whole part is pre-scanned so a
    later numeric voice can never collide with an alias assigned earlier.
    """
    labels: list[str] = []
    for note in part.iter("note"):
        text = _child_text(note, "voice")
        if text is not None and text not in labels:
            labels.append(text)
    if not labels:
        return {}

    mapping: dict[str, int] = {}
    used: set[int] = set()
    for label in labels:
        value = _int_text(label)
        if value is not None and value >= 1:
            mapping[label] = value
            used.add(value)

    next_free = 1
    for label in labels:
        if label in mapping:
            continue
        while next_free in used:
            next_free += 1
        mapping[label] = next_free
        used.add(next_free)
        next_free += 1
    return mapping


def _staff(note: ET.Element, measure: str, warn: Callable[[str], None]) -> int:
    text = _child_text(note, "staff")
    if text is None:
        return 1
    value = _int_text(text)
    if value is None or value < 1:
        warn(f"{measure}: invalid staff {text!r}; using staff 1")
        return 1
    return value


def _tie_flags(note: ET.Element) -> tuple[bool, bool]:
    types: set[str] = set()
    for tie in note.findall("tie"):
        types.add(tie.get("type") or "")
    for notations in note.findall("notations"):
        for tied in notations.findall("tied"):
            types.add(tied.get("type") or "")
    return (
        "start" in types or "continue" in types,
        "stop" in types or "continue" in types,
    )


def _slur_flags(note: ET.Element) -> tuple[bool, bool]:
    types: list[str] = []
    for notations in note.findall("notations"):
        for slur in notations.findall("slur"):
            types.append(slur.get("type") or "")
    return (
        any(value in ("start", "continue") for value in types),
        any(value in ("stop", "continue") for value in types),
    )


def _has_tuplet(note: ET.Element) -> bool:
    if note.find("time-modification") is not None:
        return True
    for notations in note.findall("notations"):
        if notations.find("tuplet") is not None:
            return True
    return False


def _note_sort_key(note: ImportedNote) -> tuple[Any, ...]:
    return (
        note.bar,
        note.beat,
        note.voice,
        -1 if note.midi is None else note.midi,
        note.staff,
        note.duration,
        1 if note.rest else 0,
        note.source_measure,
    )
