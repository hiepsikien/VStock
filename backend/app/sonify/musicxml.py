"""Write a score as MusicXML 4.0 partwise.

Piano carries the melody, the chord voicing, and a <harmony> symbol at each
chord attack. It has no dynamics in this phase: liquidity is the bass part.
Bass is a single root per attack. Its loudness is a <dynamics> letter from
ppp to fff, plus the matching <sound dynamics> percentage, written only when
the letter changes.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from app.sonify.dynamics import MARKINGS
from app.sonify.form import BEATS_PER_BAR, MUSICAL_BARS
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score

DIVISIONS = 2  # per quarter note, so an eighth note is 1

_PC_STEPS = {
    0: "C",
    2: "D",
    4: "E",
    5: "F",
    7: "G",
    9: "A",
    11: "B",
}


def midi_to_pitch(midi: int) -> tuple[str, int]:
    step = _PC_STEPS.get(midi % 12)
    if step is None:
        raise ValueError(f"MIDI {midi} is not diatonic to C major")
    return step, midi // 12 - 1


def _add(parent: ET.Element, tag: str, text: str | None = None, **attrib: str) -> ET.Element:
    node = ET.SubElement(parent, tag, attrib)
    if text is not None:
        node.text = text
    return node


def _duration(beats: float) -> int:
    units = int(round(beats * DIVISIONS))
    if units < 1:
        raise ValueError("note duration is shorter than one division")
    return units


def _note_type(beats: float) -> str:
    if beats == 0.5:
        return "eighth"
    if beats == 4:
        return "whole"
    raise ValueError(f"unsupported duration: {beats} beats")


def _add_note(parent: ET.Element, event: NoteEvent, *, chord: bool) -> None:
    note = _add(parent, "note")
    if chord:
        _add(note, "chord")
    step, octave = midi_to_pitch(event.midi)
    pitch = _add(note, "pitch")
    _add(pitch, "step", step)
    _add(pitch, "octave", str(octave))
    _add(note, "duration", str(_duration(event.duration_beats)))
    if event.tie_stop:
        _add(note, "tie", type="stop")
    if event.tie_start:
        _add(note, "tie", type="start")
    _add(note, "voice", str(event.voice))
    _add(note, "type", _note_type(event.duration_beats))
    if event.tie_start or event.tie_stop:
        notations = _add(note, "notations")
        if event.tie_stop:
            _add(notations, "tied", type="stop")
        if event.tie_start:
            _add(notations, "tied", type="start")


def _attributes(parent: ET.Element, clef_sign: str, clef_line: str) -> None:
    attributes = _add(parent, "attributes")
    _add(attributes, "divisions", str(DIVISIONS))
    key = _add(attributes, "key")
    _add(key, "fifths", "0")
    _add(key, "mode", "major")
    time = _add(attributes, "time")
    _add(time, "beats", str(BEATS_PER_BAR))
    _add(time, "beat-type", "4")
    clef = _add(attributes, "clef")
    _add(clef, "sign", clef_sign)
    _add(clef, "line", clef_line)


def _metronome(parent: ET.Element, bpm: int) -> None:
    direction = _add(parent, "direction", placement="above")
    direction_type = _add(direction, "direction-type")
    metronome = _add(direction_type, "metronome")
    _add(metronome, "beat-unit", "quarter")
    _add(metronome, "per-minute", str(bpm))
    _add(direction, "sound", tempo=str(bpm))


def _harmony(parent: ET.Element, event: HarmonyEvent) -> None:
    harmony = _add(parent, "harmony", placement="above")
    root = _add(harmony, "root")
    _add(root, "root-step", event.chord.root_step)
    kind = _add(harmony, "kind", event.chord.kind)
    kind.set("text", event.chord.kind_text)


def _dynamic(parent: ET.Element, event: DynamicEvent) -> None:
    if event.marking not in MARKINGS:
        raise ValueError(f"dynamic {event.marking} is outside ppp–fff")
    direction = _add(parent, "direction", placement="below")
    direction_type = _add(direction, "direction-type")
    dynamics = _add(direction_type, "dynamics")
    _add(dynamics, event.marking)
    _add(direction, "sound", dynamics=str(event.sound))


def _group(events: tuple[NoteEvent, ...] | tuple[DynamicEvent, ...] | tuple[HarmonyEvent, ...]) -> list[list]:
    grouped: list[list] = [[] for _ in range(MUSICAL_BARS)]
    for event in events:
        grouped[event.bar].append(event)
    return grouped


def _part_list(root: ET.Element) -> None:
    part_list = _add(root, "part-list")
    piano = _add(part_list, "score-part", id="P1")
    _add(piano, "part-name", "Piano")
    piano_instrument = _add(piano, "score-instrument", id="P1-I1")
    _add(piano_instrument, "instrument-name", "Piano")
    piano_midi = _add(piano, "midi-instrument", id="P1-I1")
    _add(piano_midi, "midi-channel", "1")
    _add(piano_midi, "midi-program", "1")

    bass = _add(part_list, "score-part", id="P2")
    _add(bass, "part-name", "Bass")
    bass_instrument = _add(bass, "score-instrument", id="P2-I1")
    _add(bass_instrument, "instrument-name", "Acoustic Bass")
    bass_midi = _add(bass, "midi-instrument", id="P2-I1")
    _add(bass_midi, "midi-channel", "2")
    _add(bass_midi, "midi-program", "33")


def _piano_part(root: ET.Element, score: Score) -> None:
    part = _add(root, "part", id="P1")
    melody = _group(score.piano)
    voicing = _group(score.pad)
    symbols = _group(score.harmonies)
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(measure, "G", "2")
            _metronome(measure, score.bpm)
        for event in symbols[bar]:
            _harmony(measure, event)
        for event in melody[bar]:
            _add_note(measure, event, chord=False)
        backup = _add(measure, "backup")
        _add(backup, "duration", str(BEATS_PER_BAR * DIVISIONS))
        for index, event in enumerate(voicing[bar]):
            _add_note(measure, event, chord=index > 0)


def _bass_part(root: ET.Element, score: Score) -> None:
    part = _add(root, "part", id="P2")
    notes = _group(score.bass)
    printed: dict[int, DynamicEvent] = {}
    previous: str | None = None
    for event in score.dynamics:
        if event.marking == previous:
            continue
        printed[event.bar] = event
        previous = event.marking
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(measure, "F", "4")
        event = printed.get(bar)
        if event is not None:
            _dynamic(measure, event)
        if len(notes[bar]) != 1:
            raise ValueError(f"bass bar {bar} should hold exactly one root")
        _add_note(measure, notes[bar][0], chord=False)


def score_to_musicxml(score: Score) -> str:
    root = ET.Element("score-partwise", version="4.0")
    work = _add(root, "work")
    _add(work, "work-title", score.title)
    identification = _add(root, "identification")
    encoding = _add(identification, "encoding")
    _add(encoding, "software", "vstock-sonify")
    _part_list(root)
    _piano_part(root, score)
    _bass_part(root, score)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
