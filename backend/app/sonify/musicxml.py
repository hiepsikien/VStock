"""Write a score as MusicXML 4.0 partwise across all three orchestration variants.

Five parts (`P5`, `P1`, `P2`, `P3`, `P4`) map to each variant's ensemble via
`_PARTS_BY_VARIANT`:
- `symphony`: Flute (`P5`), Violin (`P1`), Cello (`P2`), Piano (`P3`), Bass (`P4`)
- `jazz`: Vibraphone (`P5`), Alto Saxophone (`P1`), Tenor Saxophone (`P2`),
  Rhodes Piano (`P3`), Upright Bass (`P4`), with eighth-note `<swing>` (2:1)
- `minimalist`: Synth Bell (`P5`), Synth Arpeggio (`P1`), Synth Pad (`P2`),
  Synth Pulse (`P3`), Sub-Bass (`P4`), with `divisions=4` for 16th-note pulses

In `symphony` and `jazz`, the lead (`P1`), low-mid support (`P2`), and high
accent (`P5`) parts share or layer the price melody; whichever is not playing
rests. Each melody part is marked `mp`, and phrases carry a slur, `<wedge>`
hairpins toward the apex, `<accent/>` on the stressed held note, and a per-note
`dynamics` attribute. Breakout held notes and high-end bell/flute entries carry
`<tenuto/>`, while low-cutoff minimalist arpeggio notes carry `<staccato/>`.
Vibrato is left to the instrument: a `<wavy-line>` imports as a trill.

A hairpin with no target letter moves playback one step and stays there, so
`mp` is printed again wherever earlier hairpins did not cancel out.
The lead part (`P1`) carries the opening tempo (plus `<swing>` when
`score.swing` is enabled).

`P3` is a two-staff grand staff (comping + fills in `symphony` and `jazz`, or
liquidity pulse + backbeat in `minimalist`), marked `p` once so it stays behind
the lead. `P3` also carries the `<harmony>` symbol at each chord attack on
staff 1 so MuseScore's chord-symbol piano stays at `P3`'s steady `p` dynamic
instead of swelling with the lead's hairpins. `P4` is the bass part (marked from `p` up to `BASS_CEILING` as
liquidity changes). All parts are written in C-major concert pitch (`fifths=0`)
for direct visual comparison and General MIDI playback, except `P4` Bass which
is written one octave above sounding pitch with `<transpose><octave-change>-1`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TypeVar

from app.sonify.chords import Chord
from app.sonify.dynamics import MARKINGS, SOUND
from app.sonify.form import BEATS_PER_BAR, MUSICAL_BARS
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score, Variant, WedgeEvent

DIVISIONS = 2  # default per quarter note, so an eighth note is 1
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


def midi_to_pitch(midi: int, harmony: Chord | None = None) -> tuple[str, int, int]:
    """Step, alter, octave. Chord tones use that chord's spelling; the melody stays diatonic."""
    pitch_class = midi % 12
    octave = midi // 12 - 1
    if harmony is not None:
        spelled = harmony.spelling(pitch_class)
        if spelled is not None:
            step, alter = spelled
            return step, alter, octave
    step = _PC_STEPS.get(pitch_class)
    if step is None:
        raise ValueError(f"MIDI {midi} is not diatonic to C major")
    return step, 0, octave


def _chord_on(score: Score, bar: int) -> Chord | None:
    for slot in score.slots:
        if slot.start <= bar < slot.start + slot.length:
            return slot.chord
    return None


def _add(parent: ET.Element, tag: str, text: str | None = None, **attrib: str) -> ET.Element:
    node = ET.SubElement(parent, tag, attrib)
    if text is not None:
        node.text = text
    return node


def _duration(beats: float, divisions: int = DIVISIONS) -> int:
    units = int(round(beats * divisions))
    if units < 1:
        raise ValueError("note duration is shorter than one division")
    return units


_NOTE_TYPES = {
    0.25: ("16th", 0),
    0.5: ("eighth", 0),
    0.75: ("eighth", 1),
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
    divisions: int = DIVISIONS,
    harmony: Chord | None = None,
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
        step, alter, octave = midi_to_pitch(event.midi + written_shift, harmony)
        pitch = _add(note, "pitch")
        _add(pitch, "step", step)
        if alter:
            _add(pitch, "alter", str(alter))
        _add(pitch, "octave", str(octave))
    _add(note, "duration", str(_duration(event.duration_beats, divisions)))
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
        event.staccato,
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
        if event.accent or event.tenuto or event.staccato:
            articulations = _add(notations, "articulations")
            if event.accent:
                _add(articulations, "accent")
            if event.tenuto:
                _add(articulations, "tenuto")
            if event.staccato:
                _add(articulations, "staccato")


TREBLE = ("G", "2")
BASS_CLEF = ("F", "4")


def _attributes(
    parent: ET.Element,
    *clefs: tuple[str, str],
    octave_change: int = 0,
    divisions: int = DIVISIONS,
) -> None:
    attributes = _add(parent, "attributes")
    _add(attributes, "divisions", str(divisions))
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


def _metronome(parent: ET.Element, bpm: int, *, swing: bool = False) -> None:
    direction = _add(parent, "direction", placement="above")
    direction_type = _add(direction, "direction-type")
    metronome = _add(direction_type, "metronome")
    _add(metronome, "beat-unit", "quarter")
    _add(metronome, "per-minute", str(bpm))
    _add(direction, "sound", tempo=str(bpm))
    if swing:
        swing_dir = _add(parent, "direction", placement="above")
        word_type = _add(swing_dir, "direction-type")
        _add(word_type, "words", "Swing")
        swing_sound = _add(swing_dir, "sound")
        swing_node = _add(swing_sound, "swing")
        _add(swing_node, "first", "2")
        _add(swing_node, "second", "1")
        _add(swing_node, "swing-type", "eighth")


def _harmony(parent: ET.Element, event: HarmonyEvent) -> None:
    harmony = _add(parent, "harmony", placement="above")
    root = _add(harmony, "root")
    _add(root, "root-step", event.chord.root_step)
    if event.chord.alter:
        _add(root, "root-alter", str(event.chord.alter))
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


def _group(events: tuple[E, ...], bars: int = MUSICAL_BARS) -> list[list[E]]:
    grouped: list[list[E]] = [[] for _ in range(bars)]
    for event in events:
        grouped[event.bar].append(event)
    return grouped


_PARTS = (
    ("P5", "Flute", "Flute", "5", "74"),
    ("P1", "Violin", "Violin", "1", "41"),
    ("P2", "Cello", "Cello", "2", "43"),
    ("P3", "Piano", "Piano", "3", "1"),
    ("P4", "Bass", "Electric Bass (finger)", "4", "34"),
)

_PARTS_BY_VARIANT: dict[Variant, tuple[tuple[str, str, str, str, str], ...]] = {
    "symphony": _PARTS,
    "jazz": (
        ("P5", "Vibraphone", "Vibraphone", "5", "12"),
        ("P1", "Alto Saxophone", "Alto Sax", "1", "66"),
        ("P2", "Tenor Saxophone", "Tenor Sax", "2", "67"),
        ("P3", "Rhodes Piano", "Electric Piano 1", "3", "5"),
        ("P4", "Upright Bass", "Acoustic Bass", "4", "33"),
    ),
    "minimalist": (
        ("P5", "Synth Bell", "FX 3 (crystal)", "5", "99"),
        ("P1", "Synth Arpeggio", "Lead 2 (sawtooth)", "1", "82"),
        ("P2", "Synth Pad", "Pad 2 (warm)", "2", "90"),
        ("P3", "Synth Pulse", "Lead 1 (square)", "3", "81"),
        ("P4", "Sub-Bass", "Synth Bass 1", "4", "39"),
    ),
}


def _part_list(root: ET.Element, variant: Variant = "symphony") -> None:
    part_list = _add(root, "part-list")
    parts = _PARTS_BY_VARIANT.get(variant, _PARTS)
    for part_id, part_name, instrument_name, channel, program in parts:
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

    The lead part also carries the opening tempo (and swing, when enabled).
    """
    part = _add(root, "part", id=part_id)
    melody = _group(notes, score.bars)
    edges = _group(wedges, score.bars)
    letters = _group(dynamics, score.bars)
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(measure, clef, divisions=score.divisions)
            if lead:
                _metronome(measure, score.bpm, swing=score.swing)
            _dynamic(measure, MELODY_DYNAMIC)
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

        previous_beat: float | None = None
        for event in sorted(melody[bar], key=lambda note: note.beat):
            flush(event.beat)
            is_chord = event.beat == previous_beat and event.midi is not None
            _add_note(
                measure,
                event,
                chord=is_chord,
                divisions=score.divisions,
                harmony=_chord_on(score, bar),
            )
            previous_beat = event.beat
        flush(float(BEATS_PER_BAR))


PIANO_DYNAMIC = DynamicEvent(bar=0, marking="p", sound=SOUND["p"])


def _piano_part(root: ET.Element, score: Score) -> None:
    """Right hand on the treble staff, left hand on the bass staff, one voice each.

    Carries the `<harmony>` symbols on staff 1 so chord-symbol playback stays
    at the comping part's steady `p` dynamic rather than riding `P1` hairpins.
    """
    part = _add(root, "part", id="P3")
    events = _group(score.comp, score.bars)
    symbols = _group(score.harmonies, score.bars)
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(measure, TREBLE, BASS_CLEF, divisions=score.divisions)
            _dynamic(measure, PIANO_DYNAMIC)
        for event in symbols[bar]:
            _harmony(measure, event)
        for staff in (1, 2):
            if staff > 1:
                backup = _add(measure, "backup")
                _add(backup, "duration", str(BEATS_PER_BAR * score.divisions))
            hand = sorted(
                (event for event in events[bar] if event.staff == staff),
                key=lambda event: event.beat,
            )
            previous_beat: float | None = None
            for event in hand:
                _add_note(
                    measure,
                    event,
                    chord=event.beat == previous_beat and event.midi is not None,
                    staves=2,
                    harmony=_chord_on(score, bar),
                    divisions=score.divisions,
                )
                previous_beat = event.beat


BASS_WRITTEN_OCTAVES = 1


def _bass_part(root: ET.Element, score: Score) -> None:
    """Bass part (P4) is written an octave above where it sounds."""
    part = _add(root, "part", id="P4")
    notes = _group(score.low, score.bars)
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
            _attributes(
                measure,
                BASS_CLEF,
                octave_change=-BASS_WRITTEN_OCTAVES,
                divisions=score.divisions,
            )
        event = printed.get(bar)
        if event is not None:
            _dynamic(measure, event)
        for note in sorted(notes[bar], key=lambda note: note.beat):
            _add_note(
                measure,
                note,
                written_shift=12 * BASS_WRITTEN_OCTAVES,
                divisions=score.divisions,
                harmony=_chord_on(score, bar),
            )


def score_to_musicxml(score: Score) -> str:
    root = ET.Element("score-partwise", version="4.0")
    work = _add(root, "work")
    _add(work, "work-title", score.title)
    identification = _add(root, "identification")
    encoding = _add(identification, "encoding")
    _add(encoding, "software", "vstock-sonify")
    _part_list(root, score.variant)
    _melody_part(
        root, score, "P5", score.high, (), (), TREBLE
    )
    _melody_part(
        root, score, "P1", score.lead, score.lead_wedges, score.lead_dynamics, TREBLE, lead=True
    )
    _melody_part(
        root, score, "P2", score.support, score.support_wedges, score.support_dynamics, BASS_CLEF
    )
    _piano_part(root, score)
    _bass_part(root, score)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
