"""Heitor Villa-Lobos Etude No. 1 arpeggio wave, Etude No. 11 block chords, and Prelude No. 1 thumb cantabile."""

from __future__ import annotations

from dataclasses import replace
import itertools
import math

from app.sonify.chords import Chord
from app.sonify.model import NoteEvent, Phrase, Score
from app.sonify.phrasing import MIN_RISE, swell

# Default velocity constants evaluated at function definition time
_MELODY = 64
_MELODY_APEX = 72
_BASS = 56
_INNER = 46
_MORDENT_SPAN = 4
BARRIOS_TREMOLO_MIN_BPM = 90

def _villa_wave(ctx: _Ctx, bar: int, low: list[NoteEvent], offsets: list[int]) -> list[NoteEvent]:
    """Thumb keeps root and fifth. i and m roll up and down the inner chord."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    support: list[NoteEvent] = []
    previous: int | None = None
    step = 0
    offset_set = set(offsets)
    for offset in offsets:
        sung = _melody_at(ctx, start + offset)
        bass = _sounding_midi(low, start + offset, ctx.epb) or _choose_bass(
            chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones
        )
        tones = _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True)
        if offset + 1 < ctx.epb and (offset + 1) not in offset_set:
            next_sung = _melody_at(ctx, start + offset + 1)
            next_bass = _sounding_midi(low, start + offset + 1, ctx.epb) or bass
            if next_bass > bass:
                shared_tones = _inner_choices(
                    chord,
                    min(sung, next_sung),
                    max(bass, next_bass),
                    ctx.mid_low,
                    ctx.mid_high,
                    ctx.semitones,
                    True,
                )
                if shared_tones:
                    tones = shared_tones
            outer_ok = _playable([next_bass + ctx.semitones, next_sung + ctx.semitones])
            ring_able = [
                tone
                for tone in tones
                if next_bass < tone < next_sung
                and _strings_differ(tone, next_sung, ctx.semitones)
                and _playable(
                    ([next_bass + ctx.semitones] if outer_ok else [])
                    + [tone + ctx.semitones, next_sung + ctx.semitones]
                )
            ]
            if ring_able:
                tones = ring_able
        if len(tones) >= 2 and previous is not None:
            crossed = [tone for tone in tones if tone != previous and _strings_differ(previous, tone, ctx.semitones)]
            if len(crossed) >= 2:
                tones = crossed
        if not tones:
            tone = _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True, offset)
        else:
            tone = _wave_tone(sorted(tones), step, previous)
            step += 1
        if tone is None:
            continue
        previous = tone
        support.extend(_eighth_event(start + offset, 1, tone, ctx.epb, 2, _INNER))
    return support



def _villa_bass(ctx: _Ctx, bar: int) -> list[NoteEvent]:
    """Root and fifth on the strong beats, even when `character` is None.

    Keeping 4/4 `f` on two half-note thumb attacks (0 and 4) leaves eighth 6 to
    the inner wave, so the 3+3+2 tresillo accents `{0, 3, 6}` always fall on
    the thumb at 0 and the inner voice at 3 and 6 in both `mf` and `f`.
    """
    band = ctx.band(bar)
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    lead = _melody_at(ctx, start)
    root = _choose_bass(chord, 0, lead, ctx.bass_low, ctx.bass_high, ctx.semitones)
    fifth = _choose_bass(chord, 2, lead, ctx.bass_low, ctx.bass_high, ctx.semitones)
    if band == "p":
        return _eighth_event(start, epb, root, epb, 3, _BASS)
    if ctx.kind == "4/4":
        return [
            *_eighth_event(start, 4, root, epb, 3, _BASS),
            *_eighth_event(start + 4, 4, fifth, epb, 3, _BASS),
        ]
    if ctx.kind == "6/8":
        return [
            *_eighth_event(start, 3, root, epb, 3, _BASS),
            *_eighth_event(start + 3, 3, fifth, epb, 3, _BASS),
        ]
    return [
        *_eighth_event(start, 4, root, epb, 3, _BASS),
        *_eighth_event(start + 4, max(1, epb - 4), fifth, epb, 3, _BASS),
    ]



def _render_villa_bar(ctx: _Ctx, bar: int, approach: bool) -> tuple[list[NoteEvent], list[NoteEvent]]:
    band = ctx.band(bar)
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    low = _villa_bass(ctx, bar)
    if band in {"mf", "f"} and ctx.kind == "4/4":
        # Full roll on every eighth the thumb does not open. The bass eighths
        # stay empty so the previous inner note can ring across them (campanella).
        occupied = {(_start16(event, epb) // 2) - start for event in low if event.midi is not None}
        offsets = [offset for offset in range(epb) if offset not in occupied]
    else:
        offsets = sorted(_support_eighths(ctx.kind, band, True, 1 if band in {"mf", "f"} else 0))
    support = _villa_wave(ctx, bar, low, offsets)
    if approach and band == "f":
        nxt = ctx.chord(bar + 1)
        target = _choose_bass(nxt, 0, _melody_at(ctx, (bar + 1) * epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
        leading = target - 1
        if leading < ctx.bass_low or leading > ctx.bass_high:
            leading = _fit((target - 1) % 12, ctx.bass_low, ctx.bass_high)
        last = start + epb - 1
        low = _cut_before(low, last, epb)
        low.extend(_eighth_event(last, 1, leading, epb, 3, _INNER))
        support = [event for event in support if _start16(event, epb) // 2 != last]
    accents = set()
    tresillo = _tresillo_bars(ctx.bars, ctx.epb, ctx.band_at, ctx.character, ctx.character_at)
    if bar in tresillo and ctx.kind == "4/4":
        accents = {0, 3, 6}
    elif ctx.kind == "6/8" and band in {"mf", "f"}:
        accents = {0, 3}
    elif ctx.kind == "3/4" and band == "f":
        accents = {0, 3}
    support, low = _shape_accompaniment(ctx, support, low)
    if accents:
        support = [_accent_at(ctx, event, start, accents, epb, "support") for event in support]
        low = [_accent_at(ctx, event, start, accents, epb, "bass") for event in low]
    return support, low



def _accent_at(
    ctx: _Ctx,
    event: NoteEvent,
    start: int,
    accents: set[int],
    epb: int,
    role: str,
) -> NoteEvent:
    if event.midi is None:
        return event
    eighth = _start16(event, epb) // 2 - start
    lead_vel = _covering_melody_velocity(ctx, start + eighth)
    if eighth in accents:
        cap = max(44, lead_vel - (1 if role == "bass" else 2))
        velocity = None if event.velocity is None else min(cap, event.velocity + 8)
        return replace(event, accent=True, velocity=velocity)
    if event.velocity is not None:
        return replace(event, velocity=max(40, event.velocity - 2))
    return event



def _chord_grid(ctx: _Ctx, bar: int, phrase: Phrase | None) -> tuple[list[int], list[int]]:
    rise = phrase is not None and _peak(ctx.melody, phrase) - min(ctx.melody[phrase.start : phrase.end]) >= MIN_RISE
    if ctx.kind == "4/4":
        if phrase is not None and rise and bar <= phrase.apex.start // ctx.epb:
            return [0, 2, 4, 6], [2, 2, 2, 2]
        return [0, 4], [4, 4]
    if ctx.kind == "6/8":
        if phrase is not None and rise:
            apex_bar = phrase.apex.start // ctx.epb
            if bar == apex_bar or bar == apex_bar - 1 and phrase.start <= bar * ctx.epb:
                return [0, 3], [3, 3]
        return [0], [ctx.epb]
    points, spans = [0], [ctx.epb]
    if phrase is None:
        return points, spans
    apex_bar = phrase.apex.start // ctx.epb
    end_bar = (phrase.end - 1) // ctx.epb
    if (rise and phrase.start <= bar * ctx.epb <= phrase.apex.start) or bar == apex_bar or (phrase.closes and bar == end_bar):
        return [0, 4], [4, 2]
    return points, spans



def _place_thumb(ctx: _Ctx, phrase: Phrase) -> list[int]:
    floor = 48 - ctx.semitones
    top = 64 - ctx.semitones
    window = list(ctx.raw[phrase.start : phrase.end])
    if ctx.mode == "minor":
        window = [note - 1 if note % 12 == 11 else note for note in window]
    scale = _melody_scale(ctx.mode)
    degree = {note: index for index, note in enumerate(scale)}
    snapped = []
    for note in window:
        snapped.append(note if note in degree else _nearest(note, ctx.mode, 24, 120))
    found: list[tuple[int, int, list[int]]] = []
    for shift in (-12, -24):
        shifted = [note + shift for note in snapped]
        if any(note not in degree for note in shifted):
            continue
        overflow = _overflow(shifted, floor, top)
        line = list(shifted) if overflow == 0 else _compress_monotone(shifted, floor, top, degree, scale)
        found.append((overflow, abs(shift), line))
    if found:
        line = min(found, key=lambda item: (item[0], item[1]))[2]
    else:
        line = [max(floor, min(top, note)) for note in snapped]
    pad = [line[0]] * phrase.start + line
    window_scale = tuple(note for note in scale if floor <= note <= top)
    if window_scale and ctx.chord_at:
        pad = quantize_strong_beats(pad, ctx.chord_at, window_scale, ctx.mode)
        line = pad[phrase.start : phrase.end]
    return [max(floor, min(top, note)) for note in line]



def _upper_dyad(ctx: _Ctx, chord: Chord, floor_pitch: int) -> tuple[int, int] | None:
    pool = _pool(chord)
    notes = [
        note
        for pc in pool
        for note in range(max(ctx.mid_low, floor_pitch + 1), ctx.treble_top + 1)
        if note % 12 == pc and note > floor_pitch
    ]
    best: tuple[int, int] | None = None
    for lower in notes:
        for higher in notes:
            if higher <= lower:
                continue
            if lower > ctx.mid_high and not (higher >= 80 and higher - lower <= 12):
                if lower > ctx.treble_top:
                    continue
            if not _playable([floor_pitch + ctx.semitones, lower + ctx.semitones, higher + ctx.semitones]):
                continue
            if best is None or (lower, higher) < best:
                best = (lower, higher)
    return best



def _thumb_offsets(ctx: _Ctx, band: str) -> tuple[int, ...]:
    if ctx.kind == "3/4":
        return (2, 4)
    if ctx.kind == "6/8":
        return (1, 2, 4, 5) if band in {"mf", "f"} else (2, 5)
    return (2, 6)



def _render_thumb(ctx: _Ctx, phrase: Phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    line = _place_thumb(ctx, phrase)
    peak = max(line) if line else 0
    low = _sustain(
        [0] * phrase.start + line,
        phrase.start,
        phrase.end,
        ctx.epb,
        {phrase.start + offset for offset, note in enumerate(line) if note == peak},
    )
    for index, event in enumerate(low):
        if event.midi is None:
            continue
        eighth = _start16(event, ctx.epb) // 2
        if _rises(phrase):
            # The thumb sings from the written melody level up to the apex.
            if phrase.apex.start <= eighth < phrase.apex.end:
                velocity = _MELODY_APEX
            else:
                amount = swell(phrase, min(max(eighth, phrase.start), phrase.end - 1))
                velocity = int(round(_MELODY + (_MELODY_APEX - _MELODY) * amount))
        else:
            velocity = _MELODY_APEX if event.midi == peak else _MELODY
        low[index] = replace(event, velocity=velocity, voice=3)
    support: list[NoteEvent] = []
    lead: list[NoteEvent] = []
    for bar in range(phrase.start // ctx.epb, (phrase.end - 1) // ctx.epb + 1):
        for offset in _thumb_offsets(ctx, ctx.band(bar)):
            eighth = bar * ctx.epb + offset
            if not phrase.start <= eighth < phrase.end:
                continue
            sung = _sounding_midi(low, eighth, ctx.epb)
            if sung is None and 0 <= eighth - phrase.start < len(line):
                sung = line[eighth - phrase.start]
            if sung is None:
                continue
            dyad = _upper_dyad(ctx, ctx.chord(bar), sung)
            if dyad is None:
                continue
            lower, higher = dyad
            thumb_vel = _INNER
            for event in low:
                if event.midi is not None and _covers(event, eighth * 2, ctx.epb) and event.velocity is not None:
                    thumb_vel = event.velocity
                    break
            amount = swell(phrase, min(eighth, phrase.end - 1)) if _rises(phrase) else 0.0
            # Both dyad notes stay in the bell window [_INNER - 4, _INNER],
            # and the lower one is the softer of the pair when the window allows.
            upper_vel = int(round((_INNER - 4) + 4 * amount))
            upper_vel = min(_INNER, max(_INNER - 4, upper_vel), thumb_vel - 2)
            lower_vel = min(upper_vel - 2, _INNER - 2)
            lower_vel = max(_INNER - 4, lower_vel)
            if lower_vel > upper_vel:
                lower_vel = upper_vel
            support.extend(_eighth_event(eighth, 1, lower, ctx.epb, 2, lower_vel))
            lead.extend(_eighth_event(eighth, 1, higher, ctx.epb, 1, upper_vel))
    return lead, support, low


from app.sonify.guitar_patterns import (  # noqa: E402
    _BASS,
    _Ctx,
    _INNER,
    _MELODY,
    _MELODY_APEX,
    _choose_bass,
    _choose_inner,
    _compress_monotone,
    _covering_melody_velocity,
    _covers,
    _cut_before,
    _eighth_event,
    _fit,
    _inner_choices,
    _melody_at,
    _melody_scale,
    _nearest,
    _overflow,
    _peak,
    _playable,
    _pool,
    _rises,
    _shape_accompaniment,
    _sounding_midi,
    _start16,
    _strings_differ,
    _support_eighths,
    _sustain,
    _tresillo_bars,
    _wave_tone,
    quantize_strong_beats,
)
