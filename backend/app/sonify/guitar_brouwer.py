"""Leo Brouwer Afro-Cuban and Avant-Garde classical guitar patterns (`ensemble = "brouwer"`)."""

from __future__ import annotations

from app.sonify.chords import Chord
from app.sonify.guitar import _BASS, _INNER, _MELODY, _MELODY_APEX
from app.sonify.guitar_patterns import (
    _Ctx,
    _choose_bass,
    _choose_inner,
    _color_note,
    _eighth_event,
    _inner_choices,
    _mark,
    _melody_at,
    _ordered_pool,
    _playable,
    _punch,
    _shape_accompaniment,
    _soften_attack,
    _sounding_midi,
    _spell16,
    _start16,
    _strings_differ,
    _uses_color,
    _walk,
    _wave_tone,
)
from app.sonify.model import NoteEvent, Phrase
from app.sonify.phrasing import MIN_RISE


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


def _bass_at(ctx: _Ctx, chord: Chord, degree: int, eighth: int) -> int:
    """A chord bass under this melody. A fifth that will not fret falls back."""
    sung = _melody_at(ctx, eighth)
    low, high = ctx.bass_low, ctx.bass_high

    def fits(note: int) -> bool:
        return note < sung and _playable([note + ctx.semitones, sung + ctx.semitones])

    preferred = _choose_bass(chord, degree, sung, low, high, ctx.semitones)
    if fits(preferred):
        return preferred
    root = _choose_bass(chord, 0, sung, low, high, ctx.semitones)
    if fits(root):
        return root
    wanted = chord.pitches[min(degree, len(chord.pitches) - 1)] % 12
    pcs = {pitch % 12 for pitch in chord.pitches}
    found = [note for note in range(low, high + 1) if fits(note)]
    if not found:
        return preferred if preferred < sung else low
    found.sort(key=lambda note: (note % 12 != wanted, note % 12 not in pcs, note + ctx.semitones not in {40, 45, 50}, note))
    return found[0]


def _root_changes(ctx: _Ctx, bar: int) -> bool:
    if bar + 1 >= ctx.bars:
        return False
    return ctx.chord(bar).pitches[0] % 12 != ctx.chord(bar + 1).pitches[0] % 12


def _toward_next(ctx: _Ctx, bar: int, origin: int, eighth: int) -> int | None:
    """One scale step from `origin` toward the next chord's root."""
    if not _root_changes(ctx, bar):
        return None
    target = _bass_at(ctx, ctx.chord(bar + 1), 0, min(len(ctx.melody) - 1, (bar + 1) * ctx.epb))
    while target - origin > 5 and target - 12 >= ctx.bass_low:
        target -= 12
    while origin - target > 5 and target + 12 <= ctx.bass_high:
        target += 12
    if target == origin:
        return None
    direction = 1 if target > origin else -1
    step = _walk(origin, direction, ctx.mode, ctx.bass_low, ctx.bass_high)
    if step == origin:
        nudged = origin + direction
        if ctx.bass_low <= nudged <= ctx.bass_high:
            step = nudged
        else:
            return None
    sung = _melody_at(ctx, eighth)
    if step < sung and _playable([step + ctx.semitones, sung + ctx.semitones]):
        return step
    root = _bass_at(ctx, ctx.chord(bar), 0, eighth)
    if root != origin and root < sung and _playable([root + ctx.semitones, sung + ctx.semitones]):
        return root
    return None


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
    """A 3rd, 7th, or sus/add9 color that sits above every legal bass note."""
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


def _modal_figure(
    ctx: _Ctx,
    bar: int,
    figure_at: int,
    bass_midi: int,
    phrase: Phrase | None,
) -> list[NoteEvent]:
    """Ornamental swarm over the second half. Every step, including the seam, is <= 2 semitones."""
    del phrase
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
        elif (
            figure_at > 0
            and abs(start_pitch - open_pitch) <= figure_at * 4
            and abs(end_pitch - start_pitch) <= max(0, count * 2 - 1) * 2
        ):
            origin16 = bar_start * 2
            dir1 = 1 if start_pitch >= open_pitch else -1
            dir2 = 1 if end_pitch >= start_pitch else -1
            leg1 = _swarm_line(open_pitch, start_pitch, figure_at * 2, lo, hi, dir1)
            leg2 = _swarm_line(start_pitch, end_pitch, count * 2 - 1, lo, hi, dir2)
            line = leg1[:-1] + leg2
        else:
            origin16 = bar_start * 2
            line = _swarm_line(open_pitch, end_pitch, epb * 2 - 1, lo, hi, direction)
    events: list[NoteEvent] = []
    level = _MELODY
    for offset, pitch in enumerate(line):
        if sixteenths:
            events.extend(_spell16(origin16 + offset, 1, pitch, epb, 1, level))
        else:
            events.extend(_eighth_event(begin + offset, 1, pitch, epb, 1, level))
        level = max(48, level - 1) if direction < 0 else min(_MELODY_APEX, level + 1)
    return events


def _render_sarabande_bar(
    ctx: _Ctx,
    bar: int,
    phrase: Phrase | None,
) -> tuple[list[NoteEvent], list[NoteEvent], int, list[NoteEvent]]:
    """Beat 2 carries the heavy chord. A moving line then swarms over the price."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    accent, figure = _sarabande_points(ctx)
    swarms = _sarabande_swarms(ctx, bar, figure) and figure < epb
    figure_at = figure if swarms else epb
    root = _bass_at(ctx, chord, 0, start)
    figure_events = _modal_figure(ctx, bar, figure_at, root, phrase) if swarms else []
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
