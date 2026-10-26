"""Leo Brouwer Un Dia de Noviembre, Estudio Sencillo No. 6, Elogio de la Danza, and Sarabande modal swarm."""

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

def _brouwer_primary(ctx: _Ctx, mood: str | None) -> str:
    """One Brouwer texture for a phrase, a section, or a daily session."""
    if mood == "calm":
        return "noviembre"
    if mood == "selloff" or ctx.bpm <= 72:
        return "sarabande"
    if mood == "volatile":
        return "elogio_pizz"
    return "brouwer_etude"



def _brouwer_contrast(primary: str) -> str:
    """The lyrical ballad answers the motor, and the motor answers the ballad."""
    if primary in {"noviembre", "sarabande"}:
        return "brouwer_etude"
    return "noviembre"



def _brouwer_open_tones(ctx: _Ctx, chord: Chord, sung: int, bass: int) -> list[int]:
    """Playable open D, G, and B whose pitch class belongs to `chord` or its color tones."""
    allowed = set(chord.pitch_classes) | set(_ordered_pool(chord, True))
    found: list[int] = []
    for sounding in (50, 55, 59):
        tone = sounding - ctx.semitones
        if (tone % 12) not in allowed:
            continue
        if not bass < tone < sung:
            continue
        if tone < ctx.mid_low or tone > ctx.mid_high:
            continue
        if not _playable([bass + ctx.semitones, tone + ctx.semitones, sung + ctx.semitones]):
            continue
        found.append(tone)
    return found



def _color_inner(ctx: _Ctx, chord: Chord, sung: int, bass: int, step: int, previous: int | None) -> int | None:
    """A 3rd, 7th, or sus/add9 color that sits above every legal bass note.

    Brouwer alternates those colors with the open D, G, and B strings when the
    chord owns them, so the etude motor can ring them across the next eighth.
    """
    tones = [
        tone
        for tone in _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True)
        if tone > ctx.bass_high
    ]
    opens = _brouwer_open_tones(ctx, chord, sung, bass) if ctx.ensemble == "brouwer" else []
    if not tones and not opens:
        return _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True, step)
    root = chord.pitches[0] % 12
    rich = {(root + interval) % 12 for interval in (2, 3, 4, 10, 11)}
    if _uses_color(chord):
        rich.update(_ordered_pool(chord, True)[:2])
    preferred = [tone for tone in tones if tone % 12 in rich] or list(tones)
    for tone in opens:
        if tone not in preferred:
            preferred.append(tone)
    if opens:
        colored = [tone for tone in preferred if tone not in set(opens)]
        if step % 2 == 0:
            choices = [tone for tone in opens if tone != previous] or opens
        else:
            choices = [tone for tone in colored if tone != previous] or colored or opens
    else:
        choices = preferred
    if previous is not None:
        crossed = [
            tone
            for tone in choices
            if tone != previous and _strings_differ(previous, tone, ctx.semitones)
        ]
        if crossed:
            choices = crossed
    tone = _wave_tone(sorted(choices), step, previous)
    if bass < tone < sung:
        return tone
    return None



def _brouwer_wave(ctx: _Ctx, bar: int, low: list[NoteEvent], offsets: list[int]) -> list[NoteEvent]:
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    support: list[NoteEvent] = []
    previous: int | None = None
    for step, offset in enumerate(offsets):
        eighth = start + offset
        sung = _melody_at(ctx, eighth)
        bass = _sounding_midi(low, eighth, ctx.epb) or _bass_at(ctx, chord, 0, eighth)
        tone = _color_inner(ctx, chord, sung, bass, step, previous)
        if tone is None:
            continue
        previous = tone
        support.extend(_eighth_event(eighth, 1, tone, ctx.epb, 2, _INNER))
    return support



def _render_noviembre_bar(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Two-beat ballad pulse, a walking pickup, and a color arpeggio."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    pulses = [0, 3] if ctx.kind == "6/8" else ([0, 4] if epb > 4 else [0])
    pulses = [offset for offset in pulses if offset < epb]
    root = _bass_at(ctx, chord, 0, start)
    fifth = _bass_at(ctx, chord, 2, start + pulses[-1])
    last = epb - 1
    pickup = _toward_next(ctx, bar, fifth if len(pulses) > 1 else root, start + last)
    low: list[NoteEvent] = []
    for index, offset in enumerate(pulses):
        end = pulses[index + 1] if index + 1 < len(pulses) else epb
        if pickup is not None and end == epb:
            end = last
        length = end - offset
        if length <= 0:
            continue
        pitch = root if index == 0 else fifth
        low.extend(_eighth_event(start + offset, length, pitch, epb, 3, _BASS))
    if pickup is not None:
        low.extend(_eighth_event(start + last, 1, pickup, epb, 3, _BASS))
    wanted = (1, 2, 3, 5, 6) if ctx.kind == "4/4" else (1, 2, 4, 5)
    support = _brouwer_wave(ctx, bar, low, [offset for offset in wanted if offset < epb])
    support, low = _shape_accompaniment(ctx, support, low)
    if pickup is not None:
        low = _soften_attack(low, start + last, epb)
    return support, low



def _etude_cells(ctx: _Ctx) -> list[tuple[int, int, int, bool]]:
    """Thumb cells: offset, length, chord degree, and whether the cell may walk."""
    epb = ctx.epb
    if ctx.kind == "6/8":
        # Afro-Cuban tumbao: bass on eighths 0, 2, and 5. The fifth ties across
        # beat 1.5 and the last eighth picks up into the next bar.
        cells = [(0, 2, 0, False), (2, 3, 2, False), (5, 1, 0, True)]
    elif ctx.kind == "3/4":
        cells = [(0, 3, 0, False), (3, 3, 2, False)]
    elif epb >= 8:
        cells = [(0, 3, 0, False), (3, 3, 2, False), (6, 2, 0, True)]
    else:
        cells = [(0, max(1, epb // 2), 0, False)]
        if epb > cells[0][1]:
            cells.append((cells[0][1], epb - cells[0][1], 2, False))
    clipped: list[tuple[int, int, int, bool]] = []
    for offset, length, degree, approach in cells:
        if offset >= epb or length <= 0:
            continue
        clipped.append((offset, min(length, epb - offset), degree, approach))
    return clipped



def _render_etude_bar(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Afro-Cuban tumbao: 3+3+2 in 4/4, with the inner voice on the off-eighths."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    low: list[NoteEvent] = []
    occupied: set[int] = set()
    previous = _bass_at(ctx, chord, 0, start)
    for offset, length, degree, approach in _etude_cells(ctx):
        eighth = start + offset
        pitch = _bass_at(ctx, chord, degree, eighth)
        if approach:
            stepped = _toward_next(ctx, bar, previous, eighth)
            if stepped is not None:
                pitch = stepped
        low.extend(_eighth_event(eighth, length, pitch, epb, 3, _BASS, accent=offset == 0))
        occupied.add(offset)
        previous = pitch
    support = _brouwer_wave(ctx, bar, low, [offset for offset in range(epb) if offset not in occupied])
    support, low = _shape_accompaniment(ctx, support, low)
    low = _punch(low, start, epb, amount=4)
    return support, low



def _elogio_offsets(ctx: _Ctx) -> list[int]:
    wanted = (0, 2, 3, 5, 6) if ctx.kind == "4/4" or ctx.epb >= 8 else (0, 2, 3, 5)
    return [offset for offset in wanted if offset < ctx.epb]



def _render_elogio_bar(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent], int | None]:
    """Staccato ostinato. Eighth 3 is the Bartók slap when it falls in the bar."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    offsets = _elogio_offsets(ctx)
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []
    for index, offset in enumerate(offsets):
        eighth = start + offset
        sung = _melody_at(ctx, eighth)
        bass = _bass_at(ctx, chord, 0 if index % 2 == 0 else 2, eighth)
        low.extend(_mark(_eighth_event(eighth, 1, bass, epb, 3, _BASS), staccato=True))
        tone = _color_inner(ctx, chord, sung, bass, index, None)
        if tone is None:
            tone = _color_note(ctx, chord, sung, bass)
            if tone is not None and not bass < tone < sung:
                tone = None
        if tone is not None:
            support.extend(_mark(_eighth_event(eighth, 1, tone, epb, 2, _INNER), staccato=True))
    support, low = _shape_accompaniment(ctx, support, low)
    slap = start + 3 if 3 in offsets else None
    if slap is not None:
        low = _punch(low, slap, epb, staccato=True, amount=12)
        support = _punch(support, slap, epb, staccato=True, amount=12)
    return support, low, slap



def _sarabande_points(ctx: _Ctx) -> tuple[int, int]:
    epb = ctx.epb
    accent = 3 if ctx.kind == "6/8" else min(2, epb - 1)
    figure = max(epb // 2, accent + 1)
    if figure > epb:
        figure = epb
    return accent, figure



def _sarabande_swarms(ctx: _Ctx, bar: int, figure_at: int) -> bool:
    """A moving bar swarms. A flat bar, or a bar whose second half holds, does not."""
    start = bar * ctx.epb
    begin = start + figure_at
    end = (bar + 1) * ctx.epb
    bar_line = ctx.melody[start:end]
    half_line = ctx.melody[begin:end]
    if not bar_line or not half_line:
        return False
    if half_line[0] == half_line[-1] or max(half_line) == min(half_line):
        return False
    threshold = 2 if ctx.mood(bar) == "selloff" else MIN_RISE
    return max(bar_line) - min(bar_line) >= threshold



def _swarm_line(start: int, arrival: int, steps: int, lo: int, hi: int, direction: int) -> list[int]:
    """Stepwise pitches into `arrival`. Every move is strictly 1 or 2 semitones."""
    if steps <= 0:
        return [arrival]
    max_reach = steps * 2
    if abs(arrival - start) > max_reach:
        # Clamp the entry of the run within `max_reach` of `arrival` so no step
        # ever exceeds 2 semitones, even across a wide 6/8 or 4/4 drop.
        start = max(lo, min(hi, arrival - (max_reach if arrival > start else -max_reach)))
    seg_lo = max(lo, min(start, arrival)) if start != arrival else lo
    seg_hi = min(hi, max(start, arrival)) if start != arrival else hi
    inside_nudge = (1 if start > arrival else -1) if start != arrival else (direction if direction in (1, -1) else 1)
    line = [start]
    cursor = start
    for index in range(steps):
        left = steps - index
        remaining = arrival - cursor
        if left == 1:
            step = max(-2, min(2, remaining))
        elif remaining == 0:
            step = 0
            for candidate in (inside_nudge, -inside_nudge, 2 * inside_nudge, -2 * inside_nudge):
                nxt = cursor + candidate
                if seg_lo <= nxt <= seg_hi and 1 <= abs(arrival - nxt) <= (left - 1) * 2:
                    step = candidate
                    break
            if step == 0:
                for candidate in (inside_nudge, -inside_nudge, 2 * inside_nudge, -2 * inside_nudge):
                    nxt = cursor + candidate
                    if lo <= nxt <= hi and 1 <= abs(arrival - nxt) <= (left - 1) * 2:
                        step = candidate
                        break
        elif left == 2 and abs(remaining) == 1:
            toward = 1 if remaining > 0 else -1
            step = 0
            for candidate in (-toward, 2 * toward):
                nxt = cursor + candidate
                if seg_lo <= nxt <= seg_hi and 1 <= abs(arrival - nxt) <= 2:
                    step = candidate
                    break
            if step == 0:
                for candidate in (2 * toward, -toward):
                    nxt = cursor + candidate
                    if lo <= nxt <= hi and 1 <= abs(arrival - nxt) <= 2:
                        step = candidate
                        break
            if step == 0:
                step = toward
        else:
            toward = 1 if remaining > 0 else -1
            min_needed = max(1, abs(remaining) - (left - 1) * 2)
            size = min(2, max(min_needed, 2 if abs(remaining) > left else 1))
            step = toward * size
        nxt = max(lo, min(hi, cursor + step))
        line.append(nxt)
        cursor = nxt
    line[-1] = arrival
    return line



def _punched_accent_velocity(
    ctx: _Ctx,
    bar: int,
    accent: int,
    figure_eighth: int,
    phrase: Phrase | None,
) -> int:
    """Velocity `_sustain` writes on the accent, before `_punch` adds 8."""
    epb = ctx.epb
    bar_start = bar * epb
    accent_eighth = bar_start + accent
    if accent_eighth < 0 or accent_eighth >= len(ctx.melody):
        return _MELODY
    bar_end = min(len(ctx.melody), bar_start + epb)
    cuts = {accent_eighth, figure_eighth}
    nxt = accent_eighth + 1
    while nxt < bar_end and ctx.melody[nxt] == ctx.melody[accent_eighth] and nxt not in cuts:
        nxt += 1
    length = max(1, nxt - accent_eighth)
    return _note_velocity(accent_eighth, length, _apex_eighths(ctx.phrases), phrase)


def _swarm_velocities(
    ctx: _Ctx,
    bar: int,
    line: list[int],
    direction: int,
    origin16: int,
    accent: int,
    phrase: Phrase | None,
    prior_lead: list[NoteEvent] | None,
) -> list[int]:
    """Hát hairpin over the whole swarm. The last note is the last ramp step."""
    from app.sonify.guitar_scale_passages import (
        _PATTERN_BASS,
        _hairpin_open,
        _pattern_window,
        _ramp_attacks,
        _velocity_before,
    )

    if not line:
        return []
    epb = ctx.epb
    bar_start = bar * epb
    accent16 = (bar_start + accent) * 2
    soft, loud = _pattern_window("sarabande", ctx.band(bar))
    # A swarm that opens on the accent is itself the hairpin. `prev` is the
    # lead already sounding, not the accent `_punch` will skip.
    if origin16 <= accent16:
        first_eighth = origin16 // 2
        if first_eighth == bar_start:
            prev = _velocity_before(prior_lead or [], bar_start, epb)
        else:
            prev = _MELODY
    else:
        prev = min(88, _punched_accent_velocity(ctx, bar, accent, origin16 // 2, phrase) + 8)
    going_up = direction >= 0
    on_strong = (origin16 // 2) % epb in ctx.strong
    open_v, arrival = _hairpin_open(
        "up" if going_up else "down",
        prev,
        soft,
        loud,
        "sarabande",
        on_strong,
    )
    if not going_up:
        arrival = max(soft, _PATTERN_BASS + 2)
    if len(line) < 2:
        return [arrival]
    # The figure never outlasts the bar, so the ramp stays linear.
    return _ramp_attacks(len(line), open_v, arrival, 1.0, pull=True)


def _modal_figure(
    ctx: _Ctx,
    bar: int,
    figure_at: int,
    bass_midi: int,
    phrase: Phrase | None,
    prior_lead: list[NoteEvent] | None = None,
) -> list[NoteEvent]:
    """Ornamental swarm over the second half. Every step, including the seam, is <= 2 semitones."""
    epb = ctx.epb
    bar_start = bar * epb
    begin = bar_start + figure_at
    end = (bar + 1) * epb
    if begin >= end:
        return []
    lo = max(ctx.treble_floor, bass_midi + 7)
    hi = min(ctx.treble_top, ctx.ceiling)
    if lo > hi:
        lo = ctx.treble_floor
    accent, _fig = _sarabande_points(ctx)
    open_pitch = max(lo, min(hi, _melody_at(ctx, bar_start)))
    accent_pitch = max(lo, min(hi, _melody_at(ctx, bar_start + accent)))
    prev_pitch = max(lo, min(hi, _melody_at(ctx, begin - 1)))
    start_pitch = max(lo, min(hi, _melody_at(ctx, begin)))
    end_pitch = max(lo, min(hi, _melody_at(ctx, end - 1)))
    direction = -1 if end_pitch < start_pitch or (end_pitch == start_pitch and end_pitch < open_pitch) else 1
    count = end - begin
    first_half = [max(lo, min(hi, _melody_at(ctx, bar_start + offset))) for offset in range(figure_at)]
    first_half_ok = all(abs(right - left) <= 2 for left, right in zip(first_half, first_half[1:]))
    pre_accent = [max(lo, min(hi, _melody_at(ctx, bar_start + offset))) for offset in range(accent + 1)]
    pre_accent_ok = all(abs(right - left) <= 2 for left, right in zip(pre_accent, pre_accent[1:]))
    # If the first half opens with a leap onto an arch plateau (e.g. [60, 72, 72, 72] -> 67),
    # reach the plateau pitch stepwise before continuing the swarm so every step across the bar is <= 2.
    plateau_after_open = len(first_half) >= 2 and all(
        abs(right - left) <= 2 for left, right in zip(first_half[1:], first_half[2:])
    )
    arch_reversal = (start_pitch - open_pitch) * (end_pitch - start_pitch) < 0
    sixteenths = False
    origin16 = begin * 2
    if (
        first_half_ok
        and abs(start_pitch - prev_pitch) <= 2
        and abs(end_pitch - start_pitch) <= max(0, count - 1) * 2
    ):
        line = _swarm_line(start_pitch, end_pitch, count - 1, lo, hi, direction)
    elif (
        first_half_ok
        and abs(start_pitch - prev_pitch) <= 2
        and abs(end_pitch - start_pitch) <= max(0, count * 2 - 1) * 2
    ):
        sixteenths = True
        line = _swarm_line(start_pitch, end_pitch, count * 2 - 1, lo, hi, direction)
    elif first_half_ok and abs(end_pitch - prev_pitch) <= count * 4:
        sixteenths = True
        line = _swarm_line(prev_pitch, end_pitch, count * 2, lo, hi, direction)[1:]
    else:
        sixteenths = True
        after_accent = epb * 2 - (accent * 2 + 1)
        if pre_accent_ok and after_accent > 0 and abs(end_pitch - accent_pitch) <= after_accent * 2:
            origin16 = (bar_start + accent) * 2 + 1
            line = _swarm_line(accent_pitch, end_pitch, after_accent, lo, hi, direction)[1:]
        elif plateau_after_open and arch_reversal and figure_at > 0:
            peak_steps = max(1, min(figure_at * 2, (abs(start_pitch - open_pitch) + 1) // 2))
            rest_steps = max(1, (epb * 2 - 1) - peak_steps)
            if (
                abs(start_pitch - open_pitch) <= peak_steps * 2
                and abs(end_pitch - start_pitch) <= rest_steps * 2
            ):
                origin16 = bar_start * 2
                dir1 = 1 if start_pitch >= open_pitch else -1
                dir2 = 1 if end_pitch >= start_pitch else -1
                leg1 = _swarm_line(open_pitch, start_pitch, peak_steps, lo, hi, dir1)
                leg2 = _swarm_line(start_pitch, end_pitch, rest_steps, lo, hi, dir2)
                line = leg1[:-1] + leg2
            else:
                origin16 = bar_start * 2
                line = _swarm_line(open_pitch, end_pitch, epb * 2 - 1, lo, hi, direction)
        else:
            origin16 = bar_start * 2
            line = _swarm_line(open_pitch, end_pitch, epb * 2 - 1, lo, hi, direction)
    events: list[NoteEvent] = []
    velocities = _swarm_velocities(
        ctx, bar, line, direction, origin16, accent, phrase, prior_lead
    )
    for offset, pitch in enumerate(line):
        level = velocities[offset] if offset < len(velocities) else _MELODY
        if sixteenths:
            events.extend(_spell16(origin16 + offset, 1, pitch, epb, 1, level))
        else:
            events.extend(_eighth_event(begin + offset, 1, pitch, epb, 1, level))
    return events



def _render_sarabande_bar(
    ctx: _Ctx,
    bar: int,
    phrase: Phrase | None,
    prior_lead: list[NoteEvent] | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent], int, list[NoteEvent]]:
    """Beat 2 carries the heavy chord. A moving line then swarms over the price."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    accent, figure = _sarabande_points(ctx)
    swarms = _sarabande_swarms(ctx, bar, figure) and figure < epb
    figure_at = figure if swarms else epb
    root = _bass_at(ctx, chord, 0, start)
    figure_events = (
        _modal_figure(ctx, bar, figure_at, root, phrase, prior_lead) if swarms else []
    )
    sung = _melody_at(ctx, start + accent)
    if figure_events:
        accent16 = (start + accent) * 2
        end16 = (start + max(accent + 1, figure_at)) * 2
        covered = [
            event.midi
            for event in figure_events
            if event.midi is not None and accent16 <= _start16(event, epb) < end16
        ]
        if covered:
            sung = min(covered)
    fifth = _bass_at(ctx, chord, 2, start + accent)
    if fifth >= sung:
        fifth = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
    low: list[NoteEvent] = []
    if accent > 0:
        low.extend(_eighth_event(start, accent, root, epb, 3, _BASS))
    low.extend(_eighth_event(start + accent, max(1, figure_at - accent), fifth, epb, 3, _BASS))
    if figure_at < epb:
        low.extend(_eighth_event(start + figure_at, epb - figure_at, root, epb, 3, _BASS))
    tone = _color_inner(ctx, chord, sung, fifth, 0, None)
    support: list[NoteEvent] = []
    if tone is not None and fifth < tone < sung:
        support.extend(_eighth_event(start + accent, max(1, figure_at - accent), tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    low = _punch(low, start + accent, epb, amount=8)
    support = _punch(support, start + accent, epb, amount=8)
    return support, low, accent, figure_events


_DORIAN_PCS = frozenset({0, 2, 3, 5, 7, 9, 10})
_PHRYGIAN_PCS = frozenset({0, 1, 3, 5, 7, 8, 10})


def brouwer_scale_step(ctx: _Ctx, pitch: int, direction: int) -> int:
    """A 1- or 2-semitone swarm step, preferring dorian / phrygian color and bVII."""
    step = 1 if direction >= 0 else -1
    modal = _DORIAN_PCS | _PHRYGIAN_PCS
    low = ctx.treble_floor
    high = min(ctx.treble_top, ctx.ceiling)
    for size in (2, 1):
        nxt = pitch + step * size
        if low <= nxt <= high and nxt % 12 in modal:
            return nxt
    nxt = pitch + step
    if low <= nxt <= high:
        return nxt
    return pitch


def brouwer_group2_window(ctx: _Ctx, bar: int) -> tuple[int, int] | None:
    """Inclusive eighths of the sarabande swarm window (`figure_at .. epb`)."""
    _accent, figure = _sarabande_points(ctx)
    epb = ctx.epb
    if figure >= epb:
        return None
    start = bar * epb
    return start + figure, start + epb - 1


def brouwer_group2_intrinsic_eighths(ctx: _Ctx, bar: int) -> set[int]:
    """Eighths the modal swarm already spends. Empty when the bar does not swarm."""
    window = brouwer_group2_window(ctx, bar)
    if window is None:
        return set()
    _accent, figure = _sarabande_points(ctx)
    if not _sarabande_swarms(ctx, bar, figure):
        return set()
    lo, hi = window
    eighths = set(range(lo, hi + 1))
    events = _modal_figure(ctx, bar, figure, ctx.bass_low, None)
    for event in events:
        if event.midi is None:
            continue
        eighths.add(event.bar * ctx.epb + int(math.floor(event.beat * 2 + 1e-9)))
    return eighths


from app.sonify.guitar_patterns import (  # noqa: E402
    _BASS,
    _Ctx,
    _INNER,
    _MELODY,
    _apex_eighths,
    _bass_at,
    _choose_bass,
    _choose_inner,
    _color_note,
    _eighth_event,
    _inner_choices,
    _mark,
    _melody_at,
    _note_velocity,
    _ordered_pool,
    _playable,
    _punch,
    _shape_accompaniment,
    _soften_attack,
    _sounding_midi,
    _spell16,
    _start16,
    _strings_differ,
    _toward_next,
    _uses_color,
    _wave_tone,
)
