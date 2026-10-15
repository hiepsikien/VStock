"""Write a score as MusicXML 4.0 partwise.

Violin and cello share the legato melody; whichever is not playing rests.
Each is marked mp, then every phrase carries a slur, <wedge> hairpins toward
its apex, <accent/> on its stressed held note, and a per-note dynamics
attribute. Breakout held notes carry a <tenuto/>. Vibrato is left to the
instrument: a <wavy-line> imports as a trill.

A hairpin with no target letter moves playback one step and stays there, so
mp is printed again wherever earlier hairpins did not cancel out.
Violin also carries a <harmony> symbol at each chord attack. Piano is a grand
staff of light comping, marked p once so it stays behind the melody; its
answering arpeggios carry a per-note mp. Liquidity is the bass part, which
plays root, fifth, and octave more often as volume rises. Its loudness is a
<dynamics> letter from p up to BASS_CEILING, plus the matching <sound dynamics>
percentage, written only when the letter changes.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TypeVar

from app.sonify.dynamics import MARKINGS, SOUND
from app.sonify.form import BEATS_PER_BAR, MUSICAL_BARS
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score, WedgeEvent

DIVISIONS = 2  # per quarter note, so an eighth note is 1
FORTE_VELOCITY = 90  # MusicXML dynamics percentages are relative to this

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


_NOTE_TYPES = {
    0.5: ("eighth", 0),
    1.0: ("quarter", 0),
    1.5: ("quarter", 1),
    2.0: ("half", 0),
    3.0: ("half", 1),
    4.0: ("whole", 0),
}


def _note_type(beats: float) -> tuple[str, int]:
    try:
        return _NOTE_TYPES[beats]
    except KeyError as exc:
        raise ValueError(f"unsupported duration: {beats} beats") from exc


def _add_note(
    parent: ET.Element,
    event: NoteEvent,
    *,
    chord: bool = False,
    staves: int = 1,
    written_shift: int = 0,
) -> None:
    note = _add(parent, "note")
    if event.velocity is not None and event.midi is not None:
        note.set("dynamics", f"{event.velocity * 100 / FORTE_VELOCITY:.2f}")
    if chord:
        _add(note, "chord")
    if event.midi is None:
        if event.duration_beats == BEATS_PER_BAR:
            _add(note, "rest", measure="yes")
        else:
            _add(note, "rest")
    else:
        step, octave = midi_to_pitch(event.midi + written_shift)
        pitch = _add(note, "pitch")
        _add(pitch, "step", step)
        _add(pitch, "octave", str(octave))
    _add(note, "duration", str(_duration(event.duration_beats)))
    if event.tie_stop:
        _add(note, "tie", type="stop")
    if event.tie_start:
        _add(note, "tie", type="start")
    _add(note, "voice", str(event.voice))
    note_type, dots = _note_type(event.duration_beats)
    _add(note, "type", note_type)
    for _ in range(dots):
        _add(note, "dot")
    if staves > 1:
        _add(note, "staff", str(event.staff))
    marks = (
        event.tie_start,
        event.tie_stop,
        event.slur_start,
        event.slur_stop,
        event.accent,
        event.tenuto,
    )
    if any(marks):
        notations = _add(note, "notations")
        if event.tie_stop:
            _add(notations, "tied", type="stop")
        if event.tie_start:
            _add(notations, "tied", type="start")
        if event.slur_start:
            _add(notations, "slur", type="start", number="1")
        if event.slur_stop:
            _add(notations, "slur", type="stop", number="1")
        if event.accent or event.tenuto:
            articulations = _add(notations, "articulations")
            if event.accent:
                _add(articulations, "accent")
            if event.tenuto:
                _add(articulations, "tenuto")


TREBLE = ("G", "2")
BASS_CLEF = ("F", "4")


def _attributes(
    parent: ET.Element, *clefs: tuple[str, str], octave_change: int = 0
) -> None:
    attributes = _add(parent, "attributes")
    _add(attributes, "divisions", str(DIVISIONS))
    key = _add(attributes, "key")
    _add(key, "fifths", "0")
    _add(key, "mode", "major")
    time = _add(attributes, "time")
    _add(time, "beats", str(BEATS_PER_BAR))
    _add(time, "beat-type", "4")
    if len(clefs) > 1:
        _add(attributes, "staves", str(len(clefs)))
    for number, (sign, line) in enumerate(clefs, start=1):
        clef = _add(attributes, "clef")
        if len(clefs) > 1:
            clef.set("number", str(number))
        _add(clef, "sign", sign)
        _add(clef, "line", line)
    if octave_change:
        transpose = _add(attributes, "transpose")
        _add(transpose, "diatonic", "0")
        _add(transpose, "chromatic", "0")
        _add(transpose, "octave-change", str(octave_change))


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
        raise ValueError(f"dynamic {event.marking} is outside p–f")
    direction = _add(parent, "direction", placement="below")
    direction_type = _add(direction, "direction-type")
    dynamics = _add(direction_type, "dynamics")
    _add(dynamics, event.marking)
    _add(direction, "sound", dynamics=str(event.sound))


def _wedge(parent: ET.Element, event: WedgeEvent) -> None:
    direction = _add(parent, "direction", placement="below")
    direction_type = _add(direction, "direction-type")
    _add(direction_type, "wedge", type=event.kind, number="1")


E = TypeVar("E", NoteEvent, DynamicEvent, HarmonyEvent, WedgeEvent)


def _group(events: tuple[E, ...]) -> list[list[E]]:
    grouped: list[list[E]] = [[] for _ in range(MUSICAL_BARS)]
    for event in events:
        grouped[event.bar].append(event)
    return grouped


_PARTS = (
    ("P1", "Violin", "Violin", "1", "41"),
    ("P2", "Cello", "Cello", "2", "43"),
    ("P3", "Piano", "Piano", "3", "1"),
    ("P4", "Bass", "Electric Bass (finger)", "4", "34"),
    ("P5", "Flute", "Flute", "5", "74"),
)


def _part_list(root: ET.Element) -> None:
    part_list = _add(root, "part-list")
    for part_id, part_name, instrument_name, channel, program in _PARTS:
        part = _add(part_list, "score-part", id=part_id)
        _add(part, "part-name", part_name)
        instrument = _add(part, "score-instrument", id=f"{part_id}-I1")
        _add(instrument, "instrument-name", instrument_name)
        midi = _add(part, "midi-instrument", id=f"{part_id}-I1")
        _add(midi, "midi-channel", channel)
        _add(midi, "midi-program", program)


MELODY_DYNAMIC = DynamicEvent(bar=0, marking="mp", sound=SOUND["mp"])


def _direction_order(event: WedgeEvent | DynamicEvent) -> tuple[float, int]:
    """On one beat: close the old hairpin, print the letter, open the new hairpin."""
    if isinstance(event, DynamicEvent):
        return event.beat, 1
    return event.beat, 0 if event.kind == "stop" else 2


def _melody_part(
    root: ET.Element,
    score: Score,
    part_id: str,
    notes: tuple[NoteEvent, ...],
    wedges: tuple[WedgeEvent, ...],
    dynamics: tuple[DynamicEvent, ...],
    clef: tuple[str, str],
    *,
    lead: bool = False,
) -> None:
    """Each hairpin edge and letter is written just before the note or rest it lands on.

    The lead part also carries the tempo and the chord symbols.
    """
    part = _add(root, "part", id=part_id)
    melody = _group(notes)
    edges = _group(wedges)
    letters = _group(dynamics)
    symbols = _group(score.harmonies) if lead else [[] for _ in range(score.bars)]
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(measure, clef)
            if lead:
                _metronome(measure, score.bpm)
            _dynamic(measure, MELODY_DYNAMIC)
        for event in symbols[bar]:
            _harmony(measure, event)
        pending: list[WedgeEvent | DynamicEvent] = sorted(
            [*edges[bar], *letters[bar]], key=_direction_order
        )

        def flush(until: float) -> None:
            while pending and pending[0].beat <= until:
                direction = pending.pop(0)
                if isinstance(direction, DynamicEvent):
                    _dynamic(measure, direction)
                else:
                    _wedge(measure, direction)

        for event in sorted(melody[bar], key=lambda note: note.beat):
            flush(event.beat)
            _add_note(measure, event)
        flush(float(BEATS_PER_BAR))


PIANO_DYNAMIC = DynamicEvent(bar=0, marking="p", sound=SOUND["p"])


def _piano_part(root: ET.Element, score: Score) -> None:
    """Right hand on the treble staff, left hand on the bass staff, one voice each."""
    part = _add(root, "part", id="P3")
    events = _group(score.piano)
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(measure, TREBLE, BASS_CLEF)
            _dynamic(measure, PIANO_DYNAMIC)
        for staff in (1, 2):
            if staff > 1:
                backup = _add(measure, "backup")
                _add(backup, "duration", str(BEATS_PER_BAR * DIVISIONS))
            hand = sorted(
                (event for event in events[bar] if event.staff == staff),
                key=lambda event: event.beat,
            )
            previous_beat: float | None = None
            for event in hand:
                _add_note(measure, event, chord=event.beat == previous_beat, staves=2)
                previous_beat = event.beat


BASS_WRITTEN_OCTAVES = 1


def _bass_part(root: ET.Element, score: Score) -> None:
    """Bass guitar is written an octave above where it sounds."""
    part = _add(root, "part", id="P4")
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
            _attributes(measure, BASS_CLEF, octave_change=-BASS_WRITTEN_OCTAVES)
        event = printed.get(bar)
        if event is not None:
            _dynamic(measure, event)
        for note in sorted(notes[bar], key=lambda note: note.beat):
            _add_note(measure, note, written_shift=12 * BASS_WRITTEN_OCTAVES)


def score_to_musicxml(score: Score) -> str:
    root = ET.Element("score-partwise", version="4.0")
    work = _add(root, "work")
    _add(work, "work-title", score.title)
    identification = _add(root, "identification")
    encoding = _add(identification, "encoding")
    _add(encoding, "software", "vstock-sonify")
    _part_list(root)
    _melody_part(
        root, score, "P1", score.violin, score.violin_wedges, score.violin_dynamics, TREBLE, lead=True
    )
    _melody_part(
        root, score, "P2", score.cello, score.cello_wedges, score.cello_dynamics, BASS_CLEF
    )
    _piano_part(root, score)
    _bass_part(root, score)
    _melody_part(
        root, score, "P5", score.flute, (), (), TREBLE
    )
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
