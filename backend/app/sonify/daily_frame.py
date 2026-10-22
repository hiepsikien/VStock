"""Warm-up and cool-down for a 1D symphony, jazz, or minimalist score.

The 30-bar price body is already written. This pass clears bars 0–1 and 32–33
and writes a tonic frame: two bars in, two bars out. Ambient keeps its own
frame and does not come through here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.sonify.chords import Chord
from app.sonify.dynamics import COOLDOWN_MARKING, SOUND
from app.sonify.form import DAILY_AMBIENT_BARS, EIGHTHS_PER_BAR
from app.sonify.keys import active_register
from app.sonify.model import DynamicEvent, NoteEvent, Score, WedgeEvent
from app.sonify.phrasing import with_rests

BODY_START = 2
COOL_START = 32
PIECE_END = DAILY_AMBIENT_BARS
_BEAT = 4.0
_BREATH = 0.5  # one eighth, the rest a closing phrase leaves before the bar line


def apply_daily_frame(score: Score) -> Score:
    """Replace the empty edge bars with the variant's frame. The body stays."""
    if score.bars != PIECE_END or score.variant == "ambient":
        return score
    if score.variant == "symphony":
        return _symphony(score)
    if score.variant == "jazz":
        return _jazz(score)
    if score.variant == "minimalist":
        return _minimalist(score)
    return score


def _symphony(score: Score) -> Score:
    reg = active_register()
    cello_high = max(reg.cello_handback, reg.violin_lowest)
    intro = _chord(score, 0)
    outro = _chord(score, COOL_START)
    total = score.bars * EIGHTHS_PER_BAR

    flute = with_rests(_body_notes(score.high), total)

    violin_body = _body_notes(score.lead)
    lead_low = max(reg.violin_lowest, reg.lead_floor)
    violin_in = _fold(intro.pitches[0] % 12, lead_low, reg.violin_ceiling, _midi_at(violin_body, BODY_START))
    violin_out = _fold(outro.pitches[0] % 12, lead_low, reg.violin_ceiling, _latest_midi(violin_body))
    violin_join = _midi_at(violin_body, BODY_START) == violin_in
    violin_touch = _reaching(violin_body, COOL_START - 1, violin_out) is not None
    if violin_join:
        violin_body = _retie(violin_body, BODY_START, violin_in, stop=True)
    if violin_touch:
        violin_body = _retie(violin_body, COOL_START - 1, violin_out, start=True)
    violin = with_rests(
        [
            *violin_body,
            *_sustain(1, BODY_START, violin_in, tie_out=violin_join),
            *_sustain(COOL_START, PIECE_END, violin_out, tie_in=violin_touch),
        ],
        total,
    )

    cello_body = _body_notes(score.support)
    cello_in = _fold(intro.pitches[0] % 12, reg.support_floor, cello_high, _midi_at(cello_body, BODY_START))
    cello_out = _fold(outro.pitches[0] % 12, reg.support_floor, cello_high, _latest_midi(cello_body))
    cello_join = _midi_at(cello_body, BODY_START) == cello_in
    cello_touch = _reaching(cello_body, COOL_START - 1, cello_out) is not None
    if cello_join:
        cello_body = _retie(cello_body, BODY_START, cello_in, stop=True)
    if cello_touch:
        cello_body = _retie(cello_body, COOL_START - 1, cello_out, start=True)
    cello = with_rests(
        [
            *cello_body,
            *_sustain(0, BODY_START, cello_in, tie_out=cello_join),
            *_sustain(COOL_START, PIECE_END, cello_out, tie_in=cello_touch),
        ],
        total,
    )

    bass_body = _body_notes(score.low)
    bass_join = _midi_at(bass_body, BODY_START) == intro.bass_midi
    bass_touch = _reaching(bass_body, COOL_START - 1, outro.bass_midi) is not None
    if bass_join:
        bass_body = _retie(bass_body, BODY_START, intro.bass_midi, stop=True)
    if bass_touch:
        bass_body = _retie(bass_body, COOL_START - 1, outro.bass_midi, start=True)
    bass = (
        *bass_body,
        *_sustain(0, BODY_START, intro.bass_midi, tie_out=bass_join),
        *_sustain(COOL_START, PIECE_END, outro.bass_midi, tie_in=bass_touch),
    )

    return replace(
        score,
        high=flute,
        lead=violin,
        support=cello,
        comp=_rest_both(_kept_comp(score.comp)),
        low=tuple(sorted(bass, key=_order)),
        dynamics=_bass_letters(score.dynamics),
        lead_wedges=_body_wedges(score.lead_wedges) + _hairpin(1),
        support_wedges=_body_wedges(score.support_wedges) + _hairpin(0),
        lead_dynamics=_line_letters(score.lead_dynamics, cool_attack=not violin_touch),
        support_dynamics=_line_letters(score.support_dynamics, cool_attack=not cello_touch),
        low_wedges=_hairpin(0),
    )


def _jazz(score: Score) -> Score:
    reg = active_register()
    total = score.bars * EIGHTHS_PER_BAR
    outro = _chord(score, COOL_START)
    lead_body = _body_notes(score.lead)
    support_body = _body_notes(score.support)
    neighbor = _latest_midi(lead_body)
    support_neighbor = _latest_midi(support_body)
    if support_neighbor is not None and (neighbor is None or _later(support_body, lead_body)):
        neighbor = support_neighbor
    tonic = _fold(outro.pitches[0] % 12, reg.violin_lowest, reg.sax_ceiling, neighbor)
    lead_touch = _reaching(lead_body, COOL_START - 1, tonic)
    support_touch = _reaching(support_body, COOL_START - 1, tonic)
    lead_added: list[NoteEvent] = []
    support_added: list[NoteEvent] = []
    if lead_touch is not None:
        lead_body = _retie(lead_body, COOL_START - 1, tonic, start=True)
        lead_added = _sustain(COOL_START, PIECE_END, tonic, tie_in=True)
    elif support_touch is not None:
        support_body = _retie(support_body, COOL_START - 1, tonic, start=True)
        support_added = _sustain(COOL_START, PIECE_END, tonic, tie_in=True)
    else:
        lead_added = _sustain(COOL_START, PIECE_END, tonic)

    cool_on_lead = bool(lead_added)
    cool_on_support = bool(support_added)
    return replace(
        score,
        high=with_rests(_body_notes(score.high), total),
        lead=with_rests([*lead_body, *lead_added], total),
        support=with_rests([*support_body, *support_added], total),
        comp=_jazz_rhodes(score.comp),
        low=tuple(_tie_outro_bass(score.low, outro.bass_midi)),
        dynamics=_bass_letters(score.dynamics),
        lead_wedges=_body_wedges(score.lead_wedges) + (_fade() if cool_on_lead else ()),
        support_wedges=_body_wedges(score.support_wedges) + (_fade() if cool_on_support else ()),
        lead_dynamics=_cool_letters(score.lead_dynamics, sing=cool_on_lead, attack=lead_touch is None),
        support_dynamics=_cool_letters(
            score.support_dynamics, sing=cool_on_support, attack=support_touch is None
        ),
        low_wedges=_hairpin(0),
    )


def _minimalist(score: Score) -> Score:
    total = score.bars * EIGHTHS_PER_BAR
    pad = [
        note
        for note in score.support
        if note.midi is not None and (BODY_START <= note.bar < COOL_START or note.bar in (32, 33))
    ]
    return replace(
        score,
        high=with_rests(_body_notes(score.high), total),
        lead=with_rests(_body_notes(score.lead), total),
        support=with_rests(pad, total),
        comp=_pulse_rests(score.comp),
        low=_even_sub(score.low),
        dynamics=_bass_letters(score.dynamics),
        lead_wedges=_body_wedges(score.lead_wedges),
        support_wedges=(
            WedgeEvent(COOL_START, 0.0, "diminuendo"),
            WedgeEvent(33, _BEAT, "stop"),
        ),
        lead_dynamics=_body_dynamics(score.lead_dynamics),
        support_dynamics=(DynamicEvent(33, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING]),),
        low_wedges=_hairpin(0),
    )


def _chord(score: Score, bar: int) -> Chord:
    for slot in score.slots:
        if slot.start <= bar < slot.start + slot.length:
            return slot.chord
    return score.slots[-1].chord


def _fold(pc: int, low: int, high: int, neighbor: int | None) -> int:
    if high < low:
        high = low
    seeds = [midi for midi in range(low, high + 1) if midi % 12 == pc]
    if not seeds:
        seeds = [midi for midi in range(low - 11, high + 12) if midi % 12 == pc]
    if neighbor is None:
        mid = (low + high) / 2
        return min(seeds, key=lambda midi: (abs(midi - mid), midi))
    near = [midi for midi in seeds if abs(midi - neighbor) <= 12]
    return min(near or seeds, key=lambda midi: (abs(midi - neighbor), midi))


def _in_frame(bar: int) -> bool:
    return bar < BODY_START or bar >= COOL_START


def _body_notes(notes: Sequence[NoteEvent]) -> list[NoteEvent]:
    kept: list[NoteEvent] = []
    for note in notes:
        if note.midi is None or _in_frame(note.bar):
            continue
        reaches = note.bar == COOL_START - 1 and note.beat + note.duration_beats >= _BEAT - 1e-6
        tie_stop = note.tie_stop and not (note.bar == BODY_START and note.beat == 0.0)
        tie_start = note.tie_start and not reaches
        slur_stop = note.slur_stop and not (note.bar == BODY_START and note.beat == 0.0)
        slur_start = note.slur_start and not reaches
        if (tie_stop, tie_start, slur_stop, slur_start) != (
            note.tie_stop,
            note.tie_start,
            note.slur_stop,
            note.slur_start,
        ):
            note = replace(
                note,
                tie_stop=tie_stop,
                tie_start=tie_start,
                slur_stop=slur_stop,
                slur_start=slur_start,
            )
        kept.append(note)
    return kept


def _midi_at(notes: Sequence[NoteEvent], bar: int, staff: int = 1) -> int | None:
    for note in notes:
        if note.bar == bar and note.staff == staff and note.beat == 0.0 and note.midi is not None:
            return note.midi
    return None


def _latest_midi(notes: Sequence[NoteEvent], staff: int = 1) -> int | None:
    sounding = [note for note in notes if note.midi is not None and note.staff == staff]
    if not sounding:
        return None
    return max(sounding, key=lambda note: (note.bar, note.beat)).midi


def _later(left: Sequence[NoteEvent], right: Sequence[NoteEvent]) -> bool:
    left_note = max((note for note in left if note.midi is not None), key=lambda note: (note.bar, note.beat), default=None)
    right_note = max((note for note in right if note.midi is not None), key=lambda note: (note.bar, note.beat), default=None)
    if left_note is None:
        return False
    if right_note is None:
        return True
    return (left_note.bar, left_note.beat) > (right_note.bar, right_note.beat)


def _reaching(notes: Sequence[NoteEvent], bar: int, midi: int, staff: int = 1) -> NoteEvent | None:
    """The last note of the bar when it is `midi` and a breath is all that remains.

    A phrase that closes drops its last eighth. That note still belongs to the
    cool-down: the gap is a breath, not a rest that ended the pitch.
    """
    sounding = [note for note in notes if note.bar == bar and note.staff == staff and note.midi is not None]
    if not sounding:
        return None
    last = max(sounding, key=lambda note: (note.beat + note.duration_beats, note.beat))
    if last.midi != midi:
        return None
    if last.beat + last.duration_beats < _BEAT - _BREATH - 1e-6:
        return None
    return last


def _retie(notes: list[NoteEvent], bar: int, midi: int, *, start: bool = False, stop: bool = False) -> list[NoteEvent]:
    target = _reaching(notes, bar, midi) if start else None
    out: list[NoteEvent] = []
    done = False
    for note in notes:
        if stop and not done and note.bar == bar and note.midi == midi and note.beat == 0.0:
            note = replace(note, tie_stop=True)
            done = True
        if start and note is target:
            end = note.beat + note.duration_beats
            duration = _BEAT - note.beat if end < _BEAT - 1e-6 else note.duration_beats
            note = replace(note, duration_beats=duration, tie_start=True)
        out.append(note)
    return out


def _sustain(
    start: int,
    end: int,
    midi: int,
    *,
    tie_in: bool = False,
    tie_out: bool = False,
    voice: int = 1,
    staff: int = 1,
) -> list[NoteEvent]:
    notes: list[NoteEvent] = []
    for bar in range(start, end):
        first = bar == start
        last = bar == end - 1
        notes.append(
            NoteEvent(
                bar=bar,
                beat=0.0,
                midi=midi,
                duration_beats=_BEAT,
                voice=voice,
                staff=staff,
                tie_stop=tie_in if first else True,
                tie_start=tie_out if last else True,
            )
        )
    return notes


def _order(note: NoteEvent) -> tuple[int, float, int]:
    return note.bar, note.beat, note.midi or -1


def _kept_comp(notes: Sequence[NoteEvent]) -> list[NoteEvent]:
    kept: list[NoteEvent] = []
    for note in notes:
        if _in_frame(note.bar):
            continue
        reaches = note.bar == COOL_START - 1 and note.midi is not None and note.beat + note.duration_beats >= _BEAT - 1e-6
        crosses_in = note.tie_stop and note.bar == BODY_START and note.beat == 0.0
        if reaches or crosses_in:
            note = replace(note, tie_start=False if reaches else note.tie_start, tie_stop=False if crosses_in else note.tie_stop)
        kept.append(note)
    return kept


def _rest_both(notes: list[NoteEvent]) -> tuple[NoteEvent, ...]:
    rests = [
        NoteEvent(bar=bar, beat=0.0, midi=None, duration_beats=_BEAT, voice=voice, staff=staff)
        for bar in (*range(BODY_START), *range(COOL_START, PIECE_END))
        for staff, voice in ((1, 1), (2, 5))
    ]
    return tuple(notes + rests)


def _hairpin(start: int) -> tuple[WedgeEvent, ...]:
    return (
        WedgeEvent(start, 0.0, "crescendo"),
        WedgeEvent(BODY_START, 0.0, "stop"),
        WedgeEvent(COOL_START, 0.0, "diminuendo"),
        WedgeEvent(PIECE_END - 1, 0.0, "stop"),
    )


def _fade() -> tuple[WedgeEvent, ...]:
    return (
        WedgeEvent(COOL_START, 0.0, "diminuendo"),
        WedgeEvent(PIECE_END - 1, 0.0, "stop"),
    )


def _body_wedges(wedges: Sequence[WedgeEvent]) -> tuple[WedgeEvent, ...]:
    kept: list[WedgeEvent] = []
    for wedge in wedges:
        if wedge.bar < BODY_START or wedge.bar >= COOL_START:
            if wedge.kind == "stop" and wedge.bar >= COOL_START and kept and kept[-1].kind != "stop":
                kept.append(WedgeEvent(COOL_START - 1, _BEAT, "stop"))
            continue
        if wedge.bar == BODY_START and wedge.beat == 0.0 and wedge.kind == "stop":
            continue
        kept.append(wedge)
    return tuple(kept)


def _body_dynamics(events: Sequence[DynamicEvent]) -> tuple[DynamicEvent, ...]:
    return tuple(event for event in events if BODY_START <= event.bar < COOL_START)


def _line_letters(events: Sequence[DynamicEvent], *, cool_attack: bool) -> tuple[DynamicEvent, ...]:
    kept = list(_body_dynamics(events))
    letters = [DynamicEvent(0, "p", SOUND["p"])]
    if not any(event.bar == BODY_START and event.beat == 0.0 for event in kept):
        letters.append(DynamicEvent(BODY_START, "mp", SOUND["mp"]))
    letters.extend(kept)
    if cool_attack:
        letters.append(DynamicEvent(COOL_START, "mp", SOUND["mp"]))
    letters.append(DynamicEvent(PIECE_END - 1, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING]))
    return tuple(letters)


def _cool_letters(events: Sequence[DynamicEvent], *, sing: bool, attack: bool) -> tuple[DynamicEvent, ...]:
    letters = list(_body_dynamics(events))
    if not sing:
        return tuple(letters)
    if attack:
        letters.append(DynamicEvent(COOL_START, "mp", SOUND["mp"]))
    letters.append(DynamicEvent(PIECE_END - 1, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING]))
    return tuple(letters)


def _bass_letters(events: Sequence[DynamicEvent]) -> tuple[DynamicEvent, ...]:
    kept = list(_body_dynamics(events))
    letters = [DynamicEvent(0, "p", SOUND["p"])]
    if not any(event.bar == BODY_START and event.beat == 0.0 for event in kept):
        letters.append(DynamicEvent(BODY_START, "mp", SOUND["mp"]))
    letters.extend(kept)
    if not kept or kept[-1].marking != "mp":
        letters.append(DynamicEvent(COOL_START, "mp", SOUND["mp"]))
    letters.append(DynamicEvent(PIECE_END - 1, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING]))
    return tuple(letters)


def _tie_outro_bass(notes: Sequence[NoteEvent], root: int) -> list[NoteEvent]:
    target = _reaching(notes, COOL_START - 1, root)
    out: list[NoteEvent] = []
    for note in notes:
        if note is target:
            end = note.beat + note.duration_beats
            duration = _BEAT - note.beat if end < _BEAT - 1e-6 else note.duration_beats
            note = replace(note, duration_beats=duration, tie_start=True)
        elif COOL_START <= note.bar < PIECE_END and note.midi is not None and note.beat == 0.0:
            note = replace(
                note,
                tie_stop=note.bar > COOL_START or target is not None,
                tie_start=note.bar < PIECE_END - 1,
            )
        out.append(note)
    return out


def _jazz_rhodes(notes: Sequence[NoteEvent]) -> tuple[NoteEvent, ...]:
    body = _kept_comp(note for note in notes if note.bar >= BODY_START)
    warm: list[NoteEvent] = []
    for bar in range(BODY_START):
        midis: list[int] = []
        for note in notes:
            if note.bar == bar and note.staff == 1 and note.beat == 0.0 and note.midi is not None and note.velocity is None:
                if note.midi not in midis:
                    midis.append(note.midi)
        if midis:
            for midi in midis:
                warm.append(NoteEvent(bar=bar, beat=0.0, midi=midi, duration_beats=2.0, voice=1, staff=1))
            warm.append(NoteEvent(bar=bar, beat=2.0, midi=None, duration_beats=2.0, voice=1, staff=1))
        else:
            warm.append(NoteEvent(bar=bar, beat=0.0, midi=None, duration_beats=_BEAT, voice=1, staff=1))
        left = [
            note
            for note in notes
            if note.bar == bar and note.staff == 2
        ]
        warm.extend(left or [NoteEvent(bar=bar, beat=0.0, midi=None, duration_beats=_BEAT, voice=5, staff=2)])

    right: list[int] = []
    for note in notes:
        if note.bar == COOL_START and note.staff == 1 and note.beat == 0.0 and note.midi is not None and note.velocity is None:
            if note.midi not in right:
                right.append(note.midi)
    left_midi = next(
        (
            note.midi
            for note in notes
            if note.bar == COOL_START and note.staff == 2 and note.beat == 0.0 and note.midi is not None
        ),
        None,
    )
    cool: list[NoteEvent] = []
    for midi in right:
        cool.extend(_sustain(COOL_START, PIECE_END, midi, staff=1, voice=1))
    if not right:
        cool.extend(
            NoteEvent(bar=bar, beat=0.0, midi=None, duration_beats=_BEAT, voice=1, staff=1)
            for bar in range(COOL_START, PIECE_END)
        )
    if left_midi is not None:
        cool.extend(_sustain(COOL_START, PIECE_END, left_midi, staff=2, voice=5))
    else:
        cool.extend(
            NoteEvent(bar=bar, beat=0.0, midi=None, duration_beats=_BEAT, voice=5, staff=2)
            for bar in range(COOL_START, PIECE_END)
        )
    return tuple(warm + body + cool)


def _pulse_rests(notes: Sequence[NoteEvent]) -> tuple[NoteEvent, ...]:
    kept = [note for note in notes if not _in_frame(note.bar)]
    rests = [
        NoteEvent(bar=bar, beat=0.0, midi=None, duration_beats=_BEAT, voice=voice, staff=staff)
        for bar in (*range(BODY_START), *range(COOL_START, PIECE_END))
        for staff, voice in ((1, 1), (2, 5))
    ]
    return tuple(kept + rests)


def _even_sub(notes: Sequence[NoteEvent]) -> tuple[NoteEvent, ...]:
    roots = {
        note.bar: note.midi
        for note in notes
        if _in_frame(note.bar) and note.beat == 0.0 and note.midi is not None
    }
    out = [note for note in notes if not _in_frame(note.bar)]
    for bar, midi in sorted(roots.items()):
        for beat in range(4):
            out.append(
                NoteEvent(
                    bar=bar,
                    beat=float(beat),
                    midi=midi,
                    duration_beats=1.0,
                    voice=1,
                    tenuto=beat == 0,
                )
            )
    return tuple(out)
