"""Write a score as MusicXML 4.0 partwise across all three orchestration variants.

Five parts (`P5`, `P1`, `P2`, `P3`, `P4`) map to each variant's ensemble via
`_PARTS_BY_VARIANT`:
- `symphony`: Flute (`P5`), Violin (`P1`), Cello (`P2`), Piano (`P3`), Bass (`P4`)
- `jazz`: Vibraphone (`P5`), Alto Saxophone (`P1`), Tenor Saxophone (`P2`),
  Rhodes Piano (`P3`), Upright Bass (`P4`), with eighth-note `<swing>` (2:1)
- `minimalist`: Synth Bell (`P5`), Synth Arpeggio (`P1`), Synth Pad (`P2`),
  Synth Pulse (`P3`), Sub-Bass (`P4`), with `divisions=4` for 16th-note pulses
- `ambient`: Celesta (`P5`), Alto Flute (`P1`), Bass Flute (`P2`, treble),
  French Horn (`P3`, one staff, `p < mp/mf >` swell), Contrabass (`P4`)

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
liquidity changes). Parts are written in concert pitch. The key signature is
`score.key.fifths` (C major when the score was not transposed). `P4` Bass
is written one octave above sounding pitch with `<transpose><octave-change>-1`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TypeVar

from app.sonify.chords import Chord
from app.sonify.dynamics import COOLDOWN_MARKING, SOUND
from app.sonify.form import BEATS_PER_BAR, MUSICAL_BARS
from app.sonify.keys import KeySpec, midi_to_spelled_pitch, signature_fifths, transpose_chord
from app.sonify.ensemble import parts_for, sounds_at_pitch
from app.sonify.model import DynamicEvent, Ensemble, HarmonyEvent, NoteEvent, Score, Variant, WedgeEvent

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
        # A chromatic approach or leading tone (F♯, C♯, …) is not in the
        # C-major collection. Spell it as a sharp so the guitar can print it.
        raised = _PC_STEPS.get((pitch_class - 1) % 12)
        if raised is None:
            raise ValueError(f"MIDI {midi} is not diatonic to C major")
        return raised, 1, octave
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
    6.0: ("whole", 1),
}


def _note_type(beats: float) -> tuple[str, int]:
    try:
        return _NOTE_TYPES[beats]
    except KeyError as exc:
        raise ValueError(f"unsupported duration: {beats} beats") from exc


def _is_sixth(beats: float) -> bool:
    """One note of a sextuplet: a sixteenth inside 6:4."""
    return abs(beats * 6 - 1.0) < 1e-3


def _sextuplet_roles(events: list[NoteEvent]) -> list[str | None]:
    """Bracket each run of six sixths that fills one quarter."""
    roles: list[str | None] = [None] * len(events)
    index = 0
    while index < len(events):
        if not _is_sixth(events[index].duration_beats):
            index += 1
            continue
        end = index
        total = 0.0
        while end < len(events) and _is_sixth(events[end].duration_beats) and total < 1.0 - 1e-3:
            total += events[end].duration_beats
            end += 1
        if end - index == 6 and abs(total - 1.0) < 1e-3:
            roles[index] = "start"
            roles[end - 1] = "stop"
        index = end
    return roles


def _add_note(
    parent: ET.Element,
    event: NoteEvent,
    *,
    chord: bool = False,
    staves: int = 1,
    written_shift: int = 0,
    divisions: int = DIVISIONS,
    harmony: Chord | None = None,
    key: KeySpec | None = None,
    bar_beats: float | None = None,
    mode: str = "major",
    slur_number: str = "1",
    tuplet: str | None = None,
) -> None:
    note = _add(parent, "note")
    if event.velocity is not None and event.midi is not None:
        note.set("dynamics", f"{event.velocity * 100 / FORTE_VELOCITY:.2f}")
    if chord:
        _add(note, "chord")
    whole_rest = (
        event.midi is None
        and event.beat == 0.0
        and bar_beats is not None
        and abs(event.duration_beats - bar_beats) < 1e-6
    )
    if event.midi is None:
        if whole_rest:
            _add(note, "rest", measure="yes")
        else:
            _add(note, "rest")
    else:
        sounding = event.midi + written_shift
        if key is None:
            step, alter, octave = midi_to_pitch(sounding, harmony)
        else:
            step, alter, octave = midi_to_spelled_pitch(
                sounding + key.semitones, key, harmony, mode
            )
        pitch = _add(note, "pitch")
        _add(pitch, "step", step)
        if alter:
            _add(pitch, "alter", str(alter))
        _add(pitch, "octave", str(octave))
    _add(note, "duration", str(_duration(event.duration_beats, divisions)))
    if whole_rest:
        _add(note, "voice", str(event.voice))
        if staves > 1:
            _add(note, "staff", str(event.staff))
        return
    if event.tie_stop:
        _add(note, "tie", type="stop")
    if event.tie_start:
        _add(note, "tie", type="start")
    _add(note, "voice", str(event.voice))
    sixth = _is_sixth(event.duration_beats)
    note_type, dots = ("16th", 0) if sixth else _note_type(event.duration_beats)
    _add(note, "type", note_type)
    for _ in range(dots):
        _add(note, "dot")
    if sixth:
        modification = _add(note, "time-modification")
        _add(modification, "actual-notes", "6")
        _add(modification, "normal-notes", "4")
        _add(modification, "normal-type", "16th")
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
    if tuplet or any(marks):
        notations = _add(note, "notations")
        if tuplet:
            _add(notations, "tuplet", type=tuplet, bracket="yes")
        if event.tie_stop:
            _add(notations, "tied", type="stop")
        if event.tie_start:
            _add(notations, "tied", type="start")
        if event.slur_start:
            _add(notations, "slur", type="start", number=slur_number)
        if event.slur_stop:
            _add(notations, "slur", type="stop", number=slur_number)
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
    fifths: int = 0,
    mode: str = "major",
    beats: int = BEATS_PER_BAR,
    beat_type: int = 4,
) -> None:
    attributes = _add(parent, "attributes")
    _add(attributes, "divisions", str(divisions))
    key = _add(attributes, "key")
    _add(key, "fifths", str(fifths))
    _add(key, "mode", mode)
    time = _add(attributes, "time")
    _add(time, "beats", str(beats))
    _add(time, "beat-type", str(beat_type))
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


def _format_tempo(bpm: float) -> str:
    rounded = round(float(bpm), 2)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.2f}"


def _opening_tempo(score: Score) -> float | None:
    for event in score.tempos:
        if event.bar == 0 and event.beat <= 1e-6:
            return event.bpm
    return None


def _hidden_tempo(parent: ET.Element, bpm: float, offset: int | None) -> None:
    """Playback tempo without a second printed metronome mark."""
    direction = _add(parent, "direction", placement="above")
    direction_type = _add(direction, "direction-type")
    words = _add(direction_type, "words", "a tempo")
    words.set("print-object", "no")
    if offset:
        _add(direction, "offset", str(offset))
    _add(direction, "sound", tempo=_format_tempo(bpm))


def _write_tempo_directions(measure: ET.Element, score: Score, bar: int) -> None:
    for event in score.tempos:
        if event.bar != bar or (bar == 0 and event.beat <= 1e-6):
            continue
        offset = int(round(event.beat * score.divisions))
        _hidden_tempo(measure, event.bpm, offset if offset else None)


def _metronome(
    parent: ET.Element,
    bpm: int,
    *,
    swing: bool = False,
    sound_bpm: float | None = None,
) -> None:
    direction = _add(parent, "direction", placement="above")
    direction_type = _add(direction, "direction-type")
    metronome = _add(direction_type, "metronome")
    _add(metronome, "beat-unit", "quarter")
    _add(metronome, "per-minute", str(bpm))
    heard = float(bpm) if sound_bpm is None else float(sound_bpm)
    _add(direction, "sound", tempo=_format_tempo(heard))
    if swing:
        swing_dir = _add(parent, "direction", placement="above")
        word_type = _add(swing_dir, "direction-type")
        _add(word_type, "words", "Swing")
        swing_sound = _add(swing_dir, "sound")
        swing_node = _add(swing_sound, "swing")
        _add(swing_node, "first", "2")
        _add(swing_node, "second", "1")
        _add(swing_node, "swing-type", "eighth")


def _harmony(parent: ET.Element, event: HarmonyEvent, key: KeySpec, mode: str = "major") -> None:
    from app.sonify.keys import spelling_key

    chord = transpose_chord(event.chord, spelling_key(key, mode), mode)
    harmony = _add(parent, "harmony", placement="above")
    root = _add(harmony, "root")
    _add(root, "root-step", chord.root_step)
    if chord.alter:
        _add(root, "root-alter", str(chord.alter))
    kind = _add(harmony, "kind", chord.kind)
    kind.set("text", chord.kind_text)


def _dynamic(parent: ET.Element, event: DynamicEvent) -> None:
    if event.marking not in SOUND:
        raise ValueError(f"dynamic {event.marking} is outside ppp–f")
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
    "ambient": (
        ("P5", "Celesta", "Celesta", "5", "9"),
        ("P1", "Glass", "Alto Flute", "1", "74"),
        ("P2", "Halo", "Bass Flute", "2", "74"),
        ("P3", "Swell", "Horn in F", "3", "61"),
        ("P4", "Drone", "Contrabass", "4", "43"),
    ),
    "guitar": (("P1", "Acoustic Nylon", "Classical Guitar", "1", "25"),),
}


def _part_list(root: ET.Element, variant: Variant = "symphony", ensemble: Ensemble = "classic") -> None:
    part_list = _add(root, "part-list")
    parts = parts_for(variant, ensemble) or _PARTS_BY_VARIANT.get(variant, _PARTS)
    for part_id, part_name, instrument_name, channel, program in parts:
        part = _add(part_list, "score-part", id=part_id)
        _add(part, "part-name", part_name)
        instrument = _add(part, "score-instrument", id=f"{part_id}-I1")
        _add(instrument, "instrument-name", instrument_name)
        if part_name == "Acoustic Nylon":
            # "Acoustic Guitar" is MuseScore's steel instrument. Nylon is this id.
            _add(instrument, "instrument-sound", "pluck.guitar.nylon-string")
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
    opening_dynamic: DynamicEvent = MELODY_DYNAMIC,
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
            _attributes(
                measure,
                clef,
                divisions=score.divisions,
                fifths=signature_fifths(score.key, score.mode),
                mode=score.mode,
                beats=score.beats,
                beat_type=score.beat_type,
            )
            if lead:
                _metronome(measure, score.bpm, swing=score.swing, sound_bpm=_opening_tempo(score))
            _dynamic(measure, opening_dynamic)
        if lead:
            _write_tempo_directions(measure, score, bar)
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
                key=score.key,
                bar_beats=score.bar_beats,
                mode=score.mode,
            )
            previous_beat = event.beat
        flush(score.bar_beats)


PIANO_DYNAMIC = DynamicEvent(bar=0, marking="p", sound=SOUND["p"])


def _opening_dynamic(
    dynamics: tuple[DynamicEvent, ...], default: DynamicEvent
) -> tuple[DynamicEvent, tuple[DynamicEvent, ...]]:
    """The first downbeat letter is the part's opening dynamic. Later letters stay in the bar."""
    if dynamics and dynamics[0].bar == 0 and dynamics[0].beat == 0.0:
        return dynamics[0], dynamics[1:]
    return default, dynamics


def _opening_p(
    dynamics: tuple[DynamicEvent, ...], default: DynamicEvent
) -> tuple[DynamicEvent, tuple[DynamicEvent, ...]]:
    """A printed p on the first downbeat is the part's opening dynamic."""
    if dynamics and dynamics[0].bar == 0 and dynamics[0].beat == 0.0 and dynamics[0].marking == "p":
        return dynamics[0], dynamics[1:]
    return default, dynamics


def _piano_part(root: ET.Element, score: Score) -> None:
    """Right hand on the treble staff, left hand on the bass staff, one voice each.

    Carries the `<harmony>` symbols on staff 1 so chord-symbol playback stays
    at the comping part's steady `p` dynamic rather than riding `P1` hairpins.
    """
    part = _add(root, "part", id="P3")
    events = _group(score.comp, score.bars)
    symbols = _group(score.harmonies, score.bars)
    symphony = score.variant == "symphony"
    if symphony:
        comp_open, comp_rest = _opening_dynamic(score.comp_dynamics, PIANO_DYNAMIC)
        rest_by_bar = _group(comp_rest, score.bars)
        wedge_by_bar = _group(score.comp_wedges, score.bars)
    else:
        comp_open = PIANO_DYNAMIC
        rest_by_bar = []
        wedge_by_bar = []
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(
                measure,
                TREBLE,
                BASS_CLEF,
                divisions=score.divisions,
                fifths=signature_fifths(score.key, score.mode),
                mode=score.mode,
                beats=score.beats,
                beat_type=score.beat_type,
            )
            _dynamic(measure, comp_open)
        elif symphony:
            for event in rest_by_bar[bar]:
                if event.beat == 0.0:
                    _dynamic(measure, event)
        for event in symbols[bar]:
            _harmony(measure, event, score.key, score.mode)
        if score.variant == "jazz" and score.low_wedges:
            bar_wedges = [wedge for wedge in score.low_wedges if wedge.bar == bar]
            letters: list[DynamicEvent] = []
            if any(wedge.kind == "stop" and wedge.beat == 0.0 and bar == 2 for wedge in bar_wedges):
                letters.append(DynamicEvent(bar, "mp", SOUND["mp"]))
            if any(wedge.kind == "diminuendo" and wedge.beat == 0.0 for wedge in bar_wedges):
                letters.append(DynamicEvent(bar, "mp", SOUND["mp"]))
            if any(wedge.kind == "stop" and bar >= 32 for wedge in bar_wedges):
                letters.append(DynamicEvent(bar, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING]))
            for direction in sorted([*bar_wedges, *letters], key=_direction_order):
                if isinstance(direction, DynamicEvent):
                    _dynamic(measure, direction)
                else:
                    _wedge(measure, direction)
        for staff in (1, 2):
            if staff > 1:
                backup = _add(measure, "backup")
                _add(backup, "duration", str(int(round(score.bar_beats * score.divisions))))
            hand = sorted(
                (event for event in events[bar] if event.staff == staff),
                key=lambda event: event.beat,
            )
            pending: list[WedgeEvent | DynamicEvent] = []
            if symphony and staff == 1:
                pending = sorted(
                    [event for event in rest_by_bar[bar] if event.beat > 0.0] + wedge_by_bar[bar],
                    key=_direction_order,
                )

            def flush(until: float) -> None:
                while pending and pending[0].beat <= until:
                    direction = pending.pop(0)
                    if isinstance(direction, DynamicEvent):
                        _dynamic(measure, direction)
                    else:
                        _wedge(measure, direction)

            previous_beat: float | None = None
            for event in hand:
                if symphony and staff == 1:
                    flush(event.beat)
                _add_note(
                    measure,
                    event,
                    chord=event.beat == previous_beat and event.midi is not None,
                    staves=2,
                    harmony=_chord_on(score, bar),
                    divisions=score.divisions,
                    key=score.key,
                    bar_beats=score.bar_beats,
                    mode=score.mode,
                )
                previous_beat = event.beat
            if symphony and staff == 1:
                flush(score.bar_beats)


BASS_WRITTEN_OCTAVES = 1


def _bass_part(root: ET.Element, score: Score) -> None:
    """Bass part (P4) is written an octave above where it sounds.

    Choir basses sing the sounding pitch, so that row skips the octave shift.
    """
    sounding = sounds_at_pitch(score.ensemble)
    written_shift = 0 if sounding else 12 * BASS_WRITTEN_OCTAVES
    octave_change = 0 if sounding else -BASS_WRITTEN_OCTAVES
    part = _add(root, "part", id="P4")
    notes = _group(score.low, score.bars)
    if score.low_wedges:
        frame_wedges = _group(score.low_wedges, score.bars)
    elif score.variant == "ambient":
        frame_wedges = _group(score.support_wedges, score.bars)
    else:
        frame_wedges = None
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
                octave_change=octave_change,
                divisions=score.divisions,
                fifths=signature_fifths(score.key, score.mode),
                mode=score.mode,
                beats=score.beats,
                beat_type=score.beat_type,
            )
        bar_wedges = [] if frame_wedges is None else frame_wedges[bar]
        for wedge in bar_wedges:
            if wedge.beat <= 0 and wedge.kind == "stop":
                _wedge(measure, wedge)
        event = printed.get(bar)
        if event is not None:
            _dynamic(measure, event)
        for wedge in bar_wedges:
            if wedge.beat <= 0 and wedge.kind != "stop":
                _wedge(measure, wedge)
        previous_beat: float | None = None
        for note in sorted(notes[bar], key=lambda note: (note.beat, note.midi is None, note.midi or 0)):
            _add_note(
                measure,
                note,
                chord=note.beat == previous_beat and note.midi is not None,
                written_shift=written_shift,
                divisions=score.divisions,
                harmony=_chord_on(score, bar),
                key=score.key,
                bar_beats=score.bar_beats,
                mode=score.mode,
            )
            previous_beat = note.beat
        for wedge in bar_wedges:
            if wedge.beat > 0:
                _wedge(measure, wedge)


def _ambient_swell_part(root: ET.Element, score: Score) -> None:
    """One treble staff. Every swell blooms p < mp/mf > across its two tied halves."""
    part = _add(root, "part", id="P3")
    events = _group(score.comp, score.bars)
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(
                measure,
                TREBLE,
                divisions=score.divisions,
                fifths=signature_fifths(score.key, score.mode),
                mode=score.mode,
                beats=score.beats,
                beat_type=score.beat_type,
            )
            _dynamic(measure, PIANO_DYNAMIC)
        hand = sorted(events[bar], key=lambda event: (event.beat, event.midi is None, event.midi or 0))
        sounding = [event for event in hand if event.midi is not None]
        continues_from_prev_bar = any(event.tie_stop and event.beat == 0.0 for event in sounding)
        harmony_bar = bar - 1 if continues_from_prev_bar and bar > 0 else bar
        previous_beat: float | None = None
        for event in hand:
            is_new_beat = event.beat != previous_beat
            if is_new_beat and event.midi is not None:
                if not event.tie_stop:
                    if bar > 0 or event.beat > 0.0:
                        _dynamic(
                            measure,
                            DynamicEvent(bar=bar, marking="p", sound=SOUND["p"], beat=event.beat),
                        )
                    _wedge(measure, WedgeEvent(bar=bar, beat=event.beat, kind="crescendo"))
                else:
                    peak_marking = "mf" if (event.velocity or 0) >= 80 else "mp"
                    _wedge(measure, WedgeEvent(bar=bar, beat=event.beat, kind="stop"))
                    _dynamic(
                        measure,
                        DynamicEvent(
                            bar=bar,
                            marking=peak_marking,
                            sound=SOUND[peak_marking],
                            beat=event.beat,
                        ),
                    )
                    _wedge(measure, WedgeEvent(bar=bar, beat=event.beat, kind="diminuendo"))
            _add_note(
                measure,
                event,
                chord=not is_new_beat and event.midi is not None,
                divisions=score.divisions,
                harmony=_chord_on(score, harmony_bar),
                key=score.key,
                bar_beats=score.bar_beats,
                mode=score.mode,
            )
            previous_beat = event.beat
        if any(event.tie_stop and not event.tie_start for event in sounding):
            _wedge(measure, WedgeEvent(bar=bar, beat=score.bar_beats, kind="stop"))


def _guitar_part(root: ET.Element, score: Score) -> None:
    """One nylon part. Three voices share the measure and meet again through backup."""
    part = _add(root, "part", id="P1")
    voices = (
        _group(score.lead, score.bars),
        _group(score.support, score.bars),
        _group(score.low, score.bars),
    )
    symbols = _group(score.harmonies, score.bars)
    bar_units = str(int(round(score.bar_beats * score.divisions)))
    for bar in range(score.bars):
        measure = _add(part, "measure", number=str(bar + 1))
        if bar == 0:
            _attributes(
                measure,
                TREBLE,
                octave_change=-1,
                divisions=score.divisions,
                fifths=signature_fifths(score.key, score.mode),
                mode=score.mode,
                beats=score.beats,
                beat_type=score.beat_type,
            )
            _metronome(measure, score.bpm, swing=False, sound_bpm=_opening_tempo(score))
            if score.ensemble != "barrios":
                _dynamic(measure, MELODY_DYNAMIC)
        _write_tempo_directions(measure, score, bar)
        for event in symbols[bar]:
            _harmony(measure, event, score.key, score.mode)
        for voice_index, voice in enumerate(voices):
            if voice_index:
                backup = _add(measure, "backup")
                _add(backup, "duration", bar_units)
            if bar == 0 and score.ensemble == "barrios":
                # One letter per voice, printed inside that voice's own stream:
                # the tremolo fill and both thumb voices (the middle colour
                # and the bass) all sit around mp.
                marking = ("mp", "mp", "mp")[voice_index]
                _dynamic(measure, DynamicEvent(bar=0, marking=marking, sound=SOUND[marking]))
            ordered = sorted(voice[bar], key=lambda note: note.beat)
            roles = _sextuplet_roles(ordered)
            previous_beat: float | None = None
            for event, role in zip(ordered, roles):
                _add_note(
                    measure,
                    event,
                    chord=event.beat == previous_beat and event.midi is not None,
                    written_shift=12,
                    divisions=score.divisions,
                    harmony=_chord_on(
                        score,
                        bar - 1 if event.tie_stop and event.beat == 0.0 and bar > 0 else bar,
                    )
                    or _chord_on(score, bar),
                    key=score.key,
                    bar_beats=score.bar_beats,
                    mode=score.mode,
                    slur_number=str(event.voice),
                    tuplet=role,
                )
                previous_beat = event.beat


def score_to_musicxml(score: Score) -> str:
    root = ET.Element("score-partwise", version="4.0")
    work = _add(root, "work")
    _add(work, "work-title", score.title)
    identification = _add(root, "identification")
    encoding = _add(identification, "encoding")
    _add(encoding, "software", "vstock-sonify")
    _part_list(root, score.variant, score.ensemble)
    if score.variant == "guitar":
        _guitar_part(root, score)
        ET.indent(root, space="  ")
        body = ET.tostring(root, encoding="unicode")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
    if score.variant == "symphony":
        high_open, high_rest = _opening_dynamic(score.high_dynamics, MELODY_DYNAMIC)
        high_wedges = score.high_wedges
    elif score.variant == "ambient":
        high_open = DynamicEvent(bar=0, marking="f", sound=SOUND["f"])
        high_rest = ()
        high_wedges = ()
    else:
        high_open, high_rest, high_wedges = MELODY_DYNAMIC, (), ()
    _melody_part(
        root,
        score,
        "P5",
        score.high,
        high_wedges,
        high_rest,
        TREBLE,
        opening_dynamic=high_open,
    )
    if score.variant == "ambient" and score.lead_dynamics and score.lead_dynamics[0].bar == 0 and score.lead_dynamics[0].beat == 0.0:
        lead_dynamic, lead_rest_dynamics = score.lead_dynamics[0], score.lead_dynamics[1:]
    else:
        lead_dynamic, lead_rest_dynamics = _opening_p(score.lead_dynamics, MELODY_DYNAMIC)
    _melody_part(
        root,
        score,
        "P1",
        score.lead,
        score.lead_wedges,
        lead_rest_dynamics,
        TREBLE,
        lead=True,
        opening_dynamic=lead_dynamic,
    )
    support_clef = TREBLE if score.variant == "ambient" else BASS_CLEF
    if score.variant == "ambient":
        support_dynamic, support_dynamics = PIANO_DYNAMIC, score.support_dynamics
    else:
        support_dynamic, support_dynamics = _opening_p(score.support_dynamics, MELODY_DYNAMIC)
    _melody_part(
        root,
        score,
        "P2",
        score.support,
        score.support_wedges,
        support_dynamics,
        support_clef,
        opening_dynamic=support_dynamic,
    )
    if score.variant == "ambient":
        _ambient_swell_part(root, score)
    else:
        _piano_part(root, score)
    _bass_part(root, score)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n"
