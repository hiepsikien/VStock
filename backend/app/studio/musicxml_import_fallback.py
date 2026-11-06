"""Small stdlib-only MusicXML reader used until ``musicxml_import`` lands.

The Studio API is written against one contract::

    parse_musicxml(data, filename=...) -> ImportedScore
    slice_score(score, bar_start=, bar_end=, voices=) -> ImportedScore
    score_summary(score) -> dict

The real parser is a separate workstream (``app/studio/musicxml_import.py``).
When that module exists, :mod:`app.studio.musicxml_source` prefers it and this
file is no longer imported. Until then this module implements the same names so
the router, the tests, and the mobile client can be built against the contract.

Scope, deliberately:

* ``score-partwise`` only, first ``<part>`` only (solo guitar);
* note placement from ``<duration>``/``<backup>``/``<forward>`` at the current
  ``<divisions>``; ``bar`` is 0-based, ``beat`` and ``duration`` are quarter-note
  beats;
* sounding MIDI is written pitch plus the part ``<transpose>`` (chromatic and
  octave-change), so a standard guitar part written an octave high reads 12
  semitones lower;
* voices are remapped to 1..4 in first-appearance order because
  ``AuthoredEvent.voice`` is bounded to 1..4;
* unsupported constructs (grace notes, cue notes, ``score-timewise``, extra
  parts) are reported through ``warnings`` instead of failing the upload.

It is not a general MusicXML implementation. It does not read layout, slurs
across parts, articulations other than accent/tenuto/staccato, or tempo
changes as a map.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "ImportedScore",
    "MusicXmlImportError",
    "parse_musicxml",
    "score_summary",
    "slice_score",
]

_STEP_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_MIDI_NAMES = (
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
)
_MAX_VOICES = 4


class MusicXmlImportError(ValueError):
    """The uploaded bytes are not a MusicXML score this reader understands."""


@dataclass(frozen=True)
class ImportedScore:
    """One parsed score, in the shape the Studio API consumes.

    ``notes`` entries are mappings with ``bar`` (0-based), ``beat`` (quarter
    beats from the bar start), ``duration`` (quarter beats), ``midi`` (sounding),
    ``voice`` (1..4), ``staff`` (1..2), ``tie``/``slur`` (authored vocabulary),
    ``accent``/``tenuto``/``staccato`` (bools), ``string``/``fret`` (optional
    tab metadata) and ``written_pitch``/``sounding_pitch`` (strings).
    """

    notes: tuple[dict[str, Any], ...] = ()
    meter: str = "4/4"
    measure_count: int = 0
    key_fifths: int = 0
    key_mode: str | None = None
    tempo: float | None = None
    title: str = ""
    warnings: tuple[str, ...] = ()
    source_hash: str = ""


# ---------------------------------------------------------------------------
# XML helpers (namespace-agnostic)


def _local(tag: Any) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in elem if _local(child.tag) == name]


def _child(elem: ET.Element, name: str) -> ET.Element | None:
    for child in elem:
        if _local(child.tag) == name:
            return child
    return None


def _text(elem: ET.Element | None, name: str) -> str | None:
    if elem is None:
        return None
    child = _child(elem, name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _int_text(elem: ET.Element | None, name: str) -> int | None:
    raw = _text(elem, name)
    if raw is None:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def _descend(elem: ET.Element, *names: str) -> ET.Element | None:
    current: ET.Element | None = elem
    for name in names:
        if current is None:
            return None
        current = _child(current, name)
    return current


def _midi_name(midi: int) -> str:
    octave = midi // 12 - 1
    return f"{_MIDI_NAMES[midi % 12]}{octave}"


def _written_name(step: str, alter: int, octave: int) -> str:
    accidental = ""
    if alter > 0:
        accidental = "#" * min(alter, 2)
    elif alter < 0:
        accidental = "b" * min(-alter, 2)
    return f"{step}{accidental}{octave}"


# ---------------------------------------------------------------------------
# Parsing


def parse_musicxml(
    data: bytes | str, filename: str | None = None
) -> ImportedScore:
    """Parse one ``score-partwise`` musicxml document.

    Raises :class:`MusicXmlImportError` (a ``ValueError``) when the bytes are
    not XML, are not a partwise score, or contain no part/measure/note.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not isinstance(data, (bytes, bytearray)):
        raise MusicXmlImportError("MusicXML input must be bytes")
    raw = bytes(data)
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if not raw.strip():
        raise MusicXmlImportError("the uploaded file is empty")
    # ElementTree expands internal entity declarations; a 5 MB "billion laughs"
    # document must not be able to balloon in memory before the cap matters.
    if b"<!ENTITY" in raw:
        raise MusicXmlImportError("XML entity declarations are not supported")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise MusicXmlImportError(f"not well-formed XML: {exc}") from None

    root_name = _local(root.tag)
    if root_name == "score-timewise":
        raise MusicXmlImportError(
            "score-timewise MusicXML is not supported; export score-partwise"
        )
    if root_name != "score-partwise":
        raise MusicXmlImportError(
            f"root element must be <score-partwise>, found <{root_name}>"
        )

    warnings: list[str] = []

    parts = _children(root, "part")
    if not parts:
        raise MusicXmlImportError("the score has no <part>")
    if len(parts) > 1:
        warnings.append(
            f"the score has {len(parts)} parts; importing only the first "
            "(solo guitar)"
        )
    part = parts[0]

    measures = _children(part, "measure")
    if not measures:
        raise MusicXmlImportError("the first part has no <measure>")

    title = (
        _text(_descend(root, "work"), "work-title")
        or _text(root, "movement-title")
        or (Path(filename).stem if filename else "")
        or "Untitled"
    )

    divisions = 1
    divisions_seen = False

    meter: str | None = None
    meter_seen: list[str] = []
    key_fifths = 0
    key_mode: str | None = None
    tempo: float | None = None
    transpose = 0
    voice_map: dict[int, int] = {}
    notes: list[dict[str, Any]] = []
    staff_warned = False

    for bar_index, measure in enumerate(measures):
        cursor = 0  # divisions from the start of this measure
        chord_start: int | None = None

        for child in measure:
            name = _local(child.tag)
            if name == "attributes":
                found_divisions = _int_text(child, "divisions")
                if found_divisions:
                    divisions = found_divisions
                    divisions_seen = True
                found_meter = _parse_time(child)
                if found_meter is not None:
                    meter_seen.append(found_meter)
                    if meter is None:
                        meter = found_meter
                fifths = _int_text(_child(child, "key"), "fifths")
                if fifths is not None:
                    key_fifths = fifths
                    key_mode = _text(_child(child, "key"), "mode") or key_mode
                found_transpose = _parse_transpose(child)
                if found_transpose is not None:
                    transpose = found_transpose
            elif name == "backup":
                cursor -= max(0, _int_text(child, "duration") or 0)
            elif name == "forward":
                cursor += max(0, _int_text(child, "duration") or 0)
            elif name == "sound":
                found = _float_attr(child, "tempo")
                if found is not None and tempo is None:
                    tempo = found
            elif name == "direction":
                found = _direction_tempo(child)
                if found is not None and tempo is None:
                    tempo = found
            elif name == "note":
                is_grace = _child(child, "grace") is not None
                is_cue = _child(child, "cue") is not None
                if is_grace:
                    warnings.append(
                        f"bar {bar_index + 1}: grace note skipped"
                    )
                    continue
                if is_cue:
                    warnings.append(f"bar {bar_index + 1}: cue note skipped")
                    continue

                is_chord = _child(child, "chord") is not None
                duration_div = max(0, _int_text(child, "duration") or 0)
                if is_chord and chord_start is not None:
                    start = chord_start
                else:
                    start = cursor
                    chord_start = start
                    if duration_div:
                        cursor += duration_div

                rest = _child(child, "rest") is not None
                pitch = _child(child, "pitch")
                if rest or pitch is None:
                    continue
                if duration_div <= 0:
                    warnings.append(
                        f"bar {bar_index + 1}: zero-duration note skipped"
                    )
                    continue

                step = (_text(pitch, "step") or "C").upper()
                octave = _int_text(pitch, "octave")
                if step not in _STEP_SEMITONES or octave is None:
                    warnings.append(
                        f"bar {bar_index + 1}: note without a readable pitch "
                        "skipped"
                    )
                    continue
                alter = _int_text(pitch, "alter") or 0
                written_midi = (octave + 1) * 12 + _STEP_SEMITONES[step] + alter
                sounding_midi = written_midi + transpose
                if not 0 <= sounding_midi <= 127:
                    warnings.append(
                        f"bar {bar_index + 1}: sounding pitch "
                        f"{sounding_midi} is outside MIDI 0..127; skipped"
                    )
                    continue

                raw_voice = _int_text(child, "voice") or 1
                if raw_voice not in voice_map:
                    if len(voice_map) >= _MAX_VOICES:
                        warnings.append(
                            f"bar {bar_index + 1}: voice {raw_voice} folded "
                            f"into voice {_MAX_VOICES} (only {_MAX_VOICES} "
                            "voices are supported)"
                        )
                        voice_map[raw_voice] = _MAX_VOICES
                    else:
                        voice_map[raw_voice] = len(voice_map) + 1
                voice = voice_map[raw_voice]

                staff = _int_text(child, "staff") or 1
                if staff not in (1, 2):
                    if not staff_warned:
                        warnings.append(
                            f"bar {bar_index + 1}: staff {staff} folded into "
                            "staff 1 (only 1..2 are supported)"
                        )
                        staff_warned = True
                    staff = 1

                tie = _parse_endpoint(child, "tie", ("start", "stop"))
                slur = _parse_slur(child)
                articulations = _child(child, "notations")
                accent = _has_articulation(articulations, "accent")
                tenuto = _has_articulation(articulations, "tenuto")
                staccato = _has_articulation(articulations, "staccato")
                technical = _descend(child, "notations", "technical")
                string = _int_text(technical, "string")
                fret = _int_text(technical, "fret")
                if string is not None and not 1 <= string <= 6:
                    string = None
                    fret = None
                if string is None:
                    fret = None

                note = {
                    "bar": bar_index,
                    "beat": start / divisions,
                    "duration": duration_div / divisions,
                    "midi": sounding_midi,
                    "voice": voice,
                    "staff": staff,
                    "tie": tie,
                    "slur": slur,
                    "accent": accent,
                    "tenuto": tenuto,
                    "staccato": staccato,
                    "string": string,
                    "fret": fret,
                    "written_pitch": _written_name(step, alter, octave),
                    "sounding_pitch": _midi_name(sounding_midi),
                }
                notes.append(note)

    if not notes:
        raise MusicXmlImportError("the first part contains no pitched notes")

    if not divisions_seen:
        warnings.append(
            "no <divisions> in the first measure; assumed 1 division per quarter"
        )
    if meter is None:
        meter = "4/4"
        warnings.append("no <time> signature; assumed 4/4")
    distinct_meters = sorted(set(meter_seen))
    if len(distinct_meters) > 1:
        warnings.append(
            "meter changes are not modelled per bar; using "
            f"{meter!r} for the whole score (saw {', '.join(distinct_meters)})"
        )

    notes.sort(key=lambda item: (item["bar"], item["beat"], item["voice"]))

    return ImportedScore(
        notes=tuple(notes),
        meter=meter,
        measure_count=len(measures),
        key_fifths=key_fifths,
        key_mode=key_mode,
        tempo=tempo,
        title=title,
        warnings=tuple(warnings),
        source_hash=digest,
    )


def _parse_time(attributes: ET.Element) -> str | None:
    time = _child(attributes, "time")
    if time is None:
        return None
    if _child(time, "senza-misura") is not None:
        return "senza-misura"
    beats_nodes = _children(time, "beats")
    type_nodes = _children(time, "beat-type")
    if not beats_nodes or not type_nodes:
        return None
    try:
        beats = sum(int(node.text or "0") for node in beats_nodes)
        beat_type = int(type_nodes[0].text or "0")
    except ValueError:
        return None
    if beats <= 0 or beat_type <= 0:
        return None
    return f"{beats}/{beat_type}"


def _parse_transpose(attributes: ET.Element) -> int | None:
    transpose = _child(attributes, "transpose")
    if transpose is None:
        return None
    chromatic = _int_text(transpose, "chromatic") or 0
    octave_change = _int_text(transpose, "octave-change") or 0
    return chromatic + 12 * octave_change


def _direction_tempo(direction: ET.Element) -> float | None:
    sound = _child(direction, "sound")
    if sound is not None:
        found = _float_attr(sound, "tempo")
        if found is not None:
            return found
    metronome = _descend(direction, "direction-type", "metronome")
    if metronome is not None:
        per_minute = _text(metronome, "per-minute")
        if per_minute:
            try:
                return float(per_minute)
            except ValueError:
                return None
    return None


def _float_attr(elem: ET.Element, name: str) -> float | None:
    raw = elem.get(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_endpoint(
    note: ET.Element, tag: str, values: tuple[str, str]
) -> str:
    kinds = {
        child.get("type")
        for child in note
        if _local(child.tag) == tag
    }
    notations = _child(note, "notations")
    if notations is not None:
        alternative = "tied" if tag == "tie" else tag
        kinds.update(
            child.get("type")
            for child in _children(notations, alternative)
        )
    has_start = values[0] in kinds
    has_stop = values[1] in kinds
    if has_start and has_stop:
        return "continue"
    if has_start:
        return "start"
    if has_stop:
        return "stop"
    return "none"


def _parse_slur(note: ET.Element) -> str:
    notations = _child(note, "notations")
    if notations is None:
        return "none"
    kinds = {
        child.get("type")
        for child in _children(notations, "slur")
    }
    has_start = "start" in kinds
    has_stop = "stop" in kinds
    if has_start and has_stop:
        return "continue"
    if has_start:
        return "start"
    if has_stop:
        return "stop"
    return "none"


def _has_articulation(notations: ET.Element | None, name: str) -> bool:
    if notations is None:
        return False
    return _descend(notations, "articulations", name) is not None


# ---------------------------------------------------------------------------
# Slicing + summary


def slice_score(
    score: ImportedScore,
    *,
    bar_start: int = 0,
    bar_end: int | None = None,
    voices: Iterable[int] | None = None,
) -> ImportedScore:
    """Return the notes in ``[bar_start, bar_end)``, keeping absolute bars.

    Bars stay absolute (0-based) so the caller can rebase and report the
    passage window without guessing which side of the slice it is on. Tie/slur
    endpoints that no longer pair inside the window are cleared, mirroring the
    documented ``slice_score`` boundary rule from the texture studio design.
    """
    if not isinstance(score, ImportedScore):
        raise TypeError("score must be an ImportedScore")
    total = score.measure_count
    start = max(0, int(bar_start))
    stop = total if bar_end is None else max(0, int(bar_end))
    if stop < start:
        stop = start
    wanted_voices = None if voices is None else {int(v) for v in voices}

    notes = [
        dict(note)
        for note in score.notes
        if start <= int(note["bar"]) < stop
        and (wanted_voices is None or int(note["voice"]) in wanted_voices)
    ]
    notes.sort(key=lambda item: (item["bar"], item["beat"], item["voice"]))
    _clear_unpaired_endpoints(notes)
    return replace(
        score,
        notes=tuple(notes),
        measure_count=max(0, stop - start),
    )


def _clear_unpaired_endpoints(notes: list[dict[str, Any]]) -> None:
    for field in ("tie", "slur"):
        open_starts: list[int] = []
        by_voice: dict[int, list[int]] = {}
        for index, note in enumerate(notes):
            by_voice.setdefault(int(note["voice"]), []).append(index)
        for indexes in by_voice.values():
            indexes.sort(key=lambda i: (notes[i]["bar"], notes[i]["beat"]))
            open_starts = []
            for index in indexes:
                value = notes[index].get(field, "none")
                if value in ("start", "next_bar"):
                    open_starts.append(index)
                elif value == "continue":
                    if not open_starts:
                        notes[index][field] = "none"
                elif value == "stop":
                    if open_starts:
                        open_starts.pop()
                    else:
                        notes[index][field] = "none"
            for index in open_starts:
                notes[index][field] = "none"


def score_summary(score: ImportedScore) -> dict[str, Any]:
    """Return a small JSON-ready summary of one parsed score."""
    if not isinstance(score, ImportedScore):
        raise TypeError("score must be an ImportedScore")
    return {
        "title": score.title,
        "meter": score.meter,
        "measureCount": score.measure_count,
        "keyFifths": score.key_fifths,
        "keyMode": score.key_mode,
        "tempo": score.tempo,
        "noteCount": len(score.notes),
        "voices": sorted({int(note["voice"]) for note in score.notes}),
        "sourceHash": score.source_hash,
    }
