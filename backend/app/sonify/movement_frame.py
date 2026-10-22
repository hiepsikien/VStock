"""Warm-up and cool-down for a movement from 1M upward.

The body is already written. This pass clears the frame bars and pedals the
opening chord in, then the closing chord out. Candles never sit on these bars.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.sonify.chords import Chord
from app.sonify.dynamics import COOLDOWN_MARKING, SOUND
from app.sonify.form import FormSpec, compose_meter
from app.sonify.keys import active_register
from app.sonify.model import DynamicEvent, NoteEvent, Score, WedgeEvent
from app.sonify.phrasing import with_rests, written


def apply_span_frame(score: Score, spec: FormSpec) -> Score:
    warmup = next(section for section in spec.sections if section.kind == "warmup")
    cool = next(section for section in spec.sections if section.kind == "cooldown")
    with compose_meter(spec.meter):
        if score.variant == "jazz":
            return _jazz(score, warmup.start, warmup.end, cool.start, cool.end)
        if score.variant == "minimalist":
            return _minimalist(score, warmup.start, warmup.end, cool.start, cool.end)
        if score.variant == "ambient":
            return _ambient(score, warmup.start, warmup.end, cool.start, cool.end)
        return _symphony(score, warmup.start, warmup.end, cool.start, cool.end)


def _symphony(score: Score, warm_start: int, body: int, cool: int, end: int) -> Score:
    reg = active_register()
    opening = _chord(score, body)
    closing = _chord(score, cool - 1)
    total = score.bars * _epb()
    violin_at = warm_start + (body - warm_start) // 2
    beats = _beats()

    lead_body = _body(score.lead, body, cool)
    support_body = _body(score.support, body, cool)
    low_body = _body(score.low, body, cool)
    violin_in = _fold(opening.pitches[0] % 12, reg.violin_lowest, reg.violin_ceiling, _midi_at(lead_body, body))
    violin_out = _fold(closing.pitches[0] % 12, reg.violin_lowest, reg.violin_ceiling, _latest(lead_body))
    cello_high = max(reg.cello_handback, reg.violin_lowest)
    cello_in = _fold(opening.pitches[0] % 12, 48, cello_high, _midi_at(support_body, body))
    cello_out = _fold(closing.pitches[0] % 12, 48, cello_high, _latest(support_body))

    lead_touch = _touching(lead_body, cool - 1, violin_out, beats)
    cello_touch = _touching(support_body, cool - 1, cello_out, beats)
    bass_touch = _touching(low_body, cool - 1, closing.bass_midi, beats)
    if lead_touch is not None:
        lead_body = _retie(lead_body, lead_touch, beats)
    if cello_touch is not None:
        support_body = _retie(support_body, cello_touch, beats)
    if bass_touch is not None:
        low_body = _retie(low_body, bass_touch, beats)

    lead = with_rests(
        [
            *lead_body,
            *_pedal(violin_at, body, violin_in, tie_out=_joins(lead_body, body, violin_in)),
            *_pedal(cool, end, violin_out, tie_in=lead_touch is not None),
        ],
        total,
    )
    support = with_rests(
        [
            *support_body,
            *_pedal(warm_start, body, cello_in),
            *_pedal(cool, end, cello_out, tie_in=cello_touch is not None),
        ],
        total,
    )
    low = (
        *low_body,
        *_pedal(warm_start, body, opening.bass_midi),
        *_pedal(cool, end, closing.bass_midi, tie_in=bass_touch is not None),
    )
    return replace(
        score,
        high=with_rests(_body(score.high, body, cool), total),
        lead=lead,
        support=support,
        low=tuple(sorted(low, key=lambda note: (note.bar, note.beat, note.midi or -1))),
        lead_wedges=_body_wedges(score.lead_wedges, body, cool) + _hairpin(violin_at, body, cool, end - 1),
        support_wedges=_body_wedges(score.support_wedges, body, cool) + _hairpin(warm_start, body, cool, end - 1),
        lead_dynamics=_letters(score.lead_dynamics, body, cool, end),
        support_dynamics=_letters(score.support_dynamics, body, cool, end),
        low_wedges=_hairpin(warm_start, body, cool, end - 1),
    )


def _jazz(score: Score, warm_start: int, body: int, cool: int, end: int) -> Score:
    total = score.bars * _epb()
    closing = _chord(score, cool - 1)
    beats = _beats()
    lead_body = _body(score.lead, body, cool)
    support_body = _body(score.support, body, cool)
    sung = _latest(lead_body) or _latest(support_body) or closing.pitches[0]
    touch = _touching(lead_body, cool - 1, sung, beats)
    if touch is not None:
        lead_body = _retie(lead_body, touch, beats)
    added = _pedal(cool, end, sung, tie_in=touch is not None) if touch is not None else []
    low_body = _body(score.low, body, cool)
    bass_touch = _touching(low_body, cool - 1, closing.bass_midi, beats)
    if bass_touch is not None:
        low_body = _retie(low_body, bass_touch, beats)
    return replace(
        score,
        high=with_rests(_body(score.high, body, cool), total),
        lead=with_rests([*lead_body, *added], total),
        support=with_rests(support_body, total),
        low=tuple(
            [
                *low_body,
                *_pedal(warm_start, body, _chord(score, body).bass_midi),
                *_pedal(cool, end, closing.bass_midi, tie_in=bass_touch is not None),
            ]
        ),
        lead_wedges=_body_wedges(score.lead_wedges, body, cool) + _fade(cool, end - 1),
        lead_dynamics=_letters(score.lead_dynamics, body, cool, end),
    )


def _minimalist(score: Score, warm_start: int, body: int, cool: int, end: int) -> Score:
    total = score.bars * _epb()
    opening = _chord(score, body)
    closing = _chord(score, cool - 1)
    pulse = _even_pulse(warm_start, body, opening.bass_midi) + _even_pulse(cool, end, closing.bass_midi)
    pad = _body(score.support, body, cool) + _pedal(warm_start, end, _fold(opening.pitches[0] % 12, 46, 68, None))
    return replace(
        score,
        high=with_rests(_body(score.high, body, cool), total),
        lead=with_rests(_body(score.lead, body, cool), total),
        support=with_rests(pad, total),
        low=tuple([*_body(score.low, body, cool), *pulse]),
        support_wedges=_body_wedges(score.support_wedges, body, cool) + _fade(cool, end - 1),
        support_dynamics=(DynamicEvent(end - 1, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING], beat=0.0),),
        low_wedges=_fade(cool, end - 1),
    )


def _ambient(score: Score, warm_start: int, body: int, cool: int, end: int) -> Score:
    total = score.bars * _epb()
    beats = _beats()
    opening = _chord(score, body)
    lead_body = _body(score.lead, body, cool)
    sung = _latest(lead_body)
    touch = _touching(lead_body, cool - 1, sung, beats) if sung is not None else None
    if touch is not None:
        lead_body = _retie(lead_body, touch, beats)
    added = _pedal(cool, end, sung, tie_in=True) if touch is not None and sung is not None else []
    glass = _fold(opening.pitches[0] % 12, 72, 88, _midi_at(lead_body, body))
    return replace(
        score,
        high=with_rests(_body(score.high, body, cool), total),
        lead=with_rests(
            [*lead_body, *_pedal(warm_start, body, glass), *added],
            total,
        ),
        support_wedges=_body_wedges(score.support_wedges, body, cool) + _fade(cool, end - 1),
        lead_dynamics=_letters(score.lead_dynamics, body, cool, end),
    )


def _epb() -> int:
    from app.sonify.form import active_meter

    return active_meter().eighths_per_bar


def _beats() -> float:
    from app.sonify.form import active_meter

    return active_meter().quarter_beats


def _chord(score: Score, bar: int) -> Chord:
    for slot in score.slots:
        if slot.start <= bar < slot.start + slot.length:
            return slot.chord
    return score.slots[-1].chord


def _body(notes: Sequence[NoteEvent], body: int, cool: int) -> list[NoteEvent]:
    return [note for note in notes if note.midi is not None and body <= note.bar < cool]


def _midi_at(notes: Sequence[NoteEvent], bar: int) -> int | None:
    for note in notes:
        if note.bar == bar and note.beat == 0.0 and note.midi is not None:
            return note.midi
    return None


def _latest(notes: Sequence[NoteEvent]) -> int | None:
    sounding = [note for note in notes if note.midi is not None]
    if not sounding:
        return None
    return max(sounding, key=lambda note: (note.bar, note.beat)).midi


def _joins(notes: Sequence[NoteEvent], bar: int, midi: int) -> bool:
    return _midi_at(notes, bar) == midi


def _fold(pc: int, low: int, high: int, neighbor: int | None) -> int:
    if high < low:
        high = low
    seeds = [midi for midi in range(low, high + 1) if midi % 12 == pc]
    if not seeds:
        seeds = [low]
    if neighbor is None:
        return min(seeds, key=lambda midi: (abs(midi - (low + high) / 2), midi))
    return min(seeds, key=lambda midi: (abs(midi - neighbor), midi))


def _touching(notes: Sequence[NoteEvent], bar: int, midi: int | None, beats: float) -> NoteEvent | None:
    if midi is None:
        return None
    sounding = [note for note in notes if note.bar == bar and note.midi == midi]
    if not sounding:
        return None
    last = max(sounding, key=lambda note: note.beat + note.duration_beats)
    if last.beat + last.duration_beats < beats - 0.5 - 1e-6:
        return None
    return last


def _retie(notes: list[NoteEvent], target: NoteEvent, beats: float) -> list[NoteEvent]:
    out: list[NoteEvent] = []
    for note in notes:
        if note is target:
            end = note.beat + note.duration_beats
            duration = beats - note.beat if end < beats - 1e-6 else note.duration_beats
            note = replace(note, duration_beats=duration, tie_start=True)
        out.append(note)
    return out


def _pedal(
    start: int, end: int, midi: int, *, tie_in: bool = False, tie_out: bool = False
) -> list[NoteEvent]:
    epb = _epb()
    notes: list[NoteEvent] = []
    for bar in range(start, end):
        first = bar == start
        last = bar == end - 1
        for note in written(bar * epb, epb, midi):
            tie_start = note.tie_start or (not last) or (last and tie_out)
            tie_stop = note.tie_stop or (first and tie_in and note.beat == 0.0)
            notes.append(replace(note, tie_start=tie_start, tie_stop=tie_stop))
    return notes


def _even_pulse(start: int, end: int, midi: int) -> list[NoteEvent]:
    from app.sonify.form import active_meter

    meter = active_meter()
    notes: list[NoteEvent] = []
    if (meter.beats, meter.beat_type) == (7, 8):
        pulses = ((0.0, 1.0), (1.0, 1.0), (2.0, 1.5))
        for bar in range(start, end):
            for beat, duration in pulses:
                notes.append(
                    NoteEvent(
                        bar=bar,
                        beat=beat,
                        midi=midi,
                        duration_beats=duration,
                        voice=1,
                        tenuto=beat == 0.0,
                    )
                )
        return notes
    step = 1.0
    count = int(meter.quarter_beats) if meter.quarter_beats == int(meter.quarter_beats) else 0
    if count < 1:
        return _pedal(start, end, midi)
    for bar in range(start, end):
        for beat in range(count):
            notes.append(
                NoteEvent(
                    bar=bar,
                    beat=float(beat) * step,
                    midi=midi,
                    duration_beats=1.0,
                    voice=1,
                    tenuto=beat == 0,
                )
            )
    return notes


def _hairpin(start: int, body: int, cool: int, last: int) -> tuple[WedgeEvent, ...]:
    return (
        WedgeEvent(start, 0.0, "crescendo"),
        WedgeEvent(body, 0.0, "stop"),
        WedgeEvent(cool, 0.0, "diminuendo"),
        WedgeEvent(last, 0.0, "stop"),
    )


def _fade(cool: int, last: int) -> tuple[WedgeEvent, ...]:
    return (WedgeEvent(cool, 0.0, "diminuendo"), WedgeEvent(last, 0.0, "stop"))


def _body_wedges(wedges: Sequence[WedgeEvent], body: int, cool: int) -> tuple[WedgeEvent, ...]:
    return tuple(wedge for wedge in wedges if body <= wedge.bar < cool)


def _letters(
    events: Sequence[DynamicEvent], body: int, cool: int, end: int
) -> tuple[DynamicEvent, ...]:
    kept = [event for event in events if body <= event.bar < cool]
    return tuple([*kept, DynamicEvent(end - 1, COOLDOWN_MARKING, SOUND[COOLDOWN_MARKING])])
