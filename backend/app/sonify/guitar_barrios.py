"""Agustin Barrios Mangore Preludio Saudade, Ultimo Tremolo, Andante, Choro, Polca, and Vals."""

from __future__ import annotations

from dataclasses import replace
import itertools

from app.sonify.chords import Chord
from app.sonify.model import NoteEvent, Phrase, Score

# Default velocity constants evaluated at function definition time
_MELODY = 64
_MELODY_APEX = 72
_BASS = 56
_INNER = 46
_MORDENT_SPAN = 4
BARRIOS_TREMOLO_MIN_BPM = 90

def _catedral_preludio(ctx: _Ctx) -> bool:
    """Authentic *La Catedral* sixteenths, not the Phase 1 eighth-note arpeggio.

    Every real movement is framed (`1D`, `1W`, `1M`, `3M`, `1Y`). A score that
    already carries sections is the same texture. Empty-section fixtures keep
    the older flowing eighths.
    """
    return _framed(ctx) or bool(ctx.sections)



def _daily_barrios_pattern(ctx: _Ctx, mood: str | None, phrases: list[Phrase], bars: list[int]) -> str:
    """1D at 120 BPM. Any rally or selloff under 1.4% span sings Preludio."""
    activity = min(_raw_activity(ctx, bars), _melody_activity(ctx, bars))
    if mood == "volatile":
        return "choro" if activity >= 0.35 else "tremolo"
    if mood in {"rally", "selloff"}:
        if ctx.rel_span < 0.014:
            return "preludio"
        return "tremolo"
    holds = sum(1 for phrase in phrases if _has_hold(ctx.melody, phrase))
    if phrases and holds / len(phrases) >= 0.3:
        return "tremolo"
    return "preludio"



def _andante_grid(ctx: _Ctx, bar: int, phrase: Phrase | None) -> tuple[list[int], list[int]]:
    if ctx.kind == "4/4":
        return [0, 4], [4, 4]
    if ctx.kind == "6/8":
        return [0, 3], [3, 3]
    points, spans = [0], [ctx.epb]
    special = False
    if phrase is not None:
        apex_bar = phrase.apex.start // ctx.epb
        end_bar = (phrase.end - 1) // ctx.epb
        special = bar == apex_bar or (phrase.closes and bar == end_bar)
    if special:
        return [0, 4], [4, 2]
    return points, spans



def _lead_attacks(melody: list[int], start: int, end: int) -> set[int]:
    attacks = {start}
    for eighth in range(start + 1, end):
        if melody[eighth] != melody[eighth - 1]:
            attacks.add(eighth)
    return attacks



def _tone_below(chord: Chord, sung: int, mid_low: int, mid_high: int, prefer: str) -> int | None:
    """Third, then the kept seventh or augmented-sixth tone, then the rest of the pool."""
    third = chord.pitches[1] % 12 if len(chord.pitches) > 1 else chord.pitches[0] % 12
    seventh = chord.pitches[3] % 12 if len(chord.pitches) >= 4 else None
    if prefer == "seventh":
        order = [tone for tone in (seventh, third, *_pool(chord)) if tone is not None]
    else:
        order = [tone for tone in (third, seventh, *_pool(chord)) if tone is not None]
    seen: list[int] = []
    for pitch_class in order:
        if pitch_class in seen:
            continue
        seen.append(pitch_class)
        tone = _fit(pitch_class, mid_low, mid_high)
        while tone >= sung and tone - 12 >= mid_low:
            tone -= 12
        if tone < sung:
            return tone
    return None



def _approach_pitch(ctx: _Ctx, chord: Chord) -> int:
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    note = root - 1
    if ctx.bass_low <= note <= ctx.bass_high:
        return note
    return _fit(note % 12, ctx.bass_low, ctx.bass_high)



def _lead_bar(ctx: _Ctx, bar: int, breath: int | None, apex: set[int]) -> list[NoteEvent]:
    """Melody on the eighth grid. A pattern-change breath is one eighth of rest."""
    start = bar * ctx.epb
    end = start + ctx.epb
    phrase = _phrase_at(ctx, start)
    events: list[NoteEvent] = []
    eighth = start
    while eighth < end:
        if breath is not None and eighth == breath:
            eighth += 1
            continue
        pitch = _melody_at(ctx, eighth)
        nxt = eighth + 1
        while nxt < end and nxt != breath and _melody_at(ctx, nxt) == pitch:
            nxt += 1
        events.extend(
            _eighth_event(eighth, nxt - eighth, pitch, ctx.epb, 1, _note_velocity(eighth, nxt - eighth, apex, phrase))
        )
        eighth = nxt
    return events



def _dance_exit(ctx: _Ctx, bar: int, patterns: list[str]) -> tuple[bool, int | None, bool]:
    """Leaving a dance drops the approach and breathes; a continued dance may approach."""
    owner = _owner(ctx, bar)
    phrase = ctx.phrases[owner] if owner is not None else None
    ends = phrase is not None and bar == (phrase.end - 1) // ctx.epb
    following = None
    if owner is not None:
        for index in range(owner + 1, len(patterns)):
            start_bar = ctx.phrases[index].start // ctx.epb
            if ctx.kind_at.get(start_bar, "phrase") in _PEDAL:
                continue
            following = patterns[index]
            break
    leaving = bool(ends and following not in _DANCE)
    breath = None
    if (
        leaving
        and following is not None
        and phrase is not None
        and phrase.end - phrase.start >= 4
    ):
        breath = phrase.end - 1
    approach = False
    if not leaving and bar + 1 < ctx.bars and _fifth_down(ctx, bar):
        nxt = _bar_pattern(ctx, bar + 1, patterns)
        if nxt in _DANCE:
            approach = True
    return leaving, breath, approach



def _finish_dance_grid(
    low: list[tuple[int | None, int | None]],
    support: list[tuple[int | None, int | None]],
    *,
    leaving: bool,
    approach: int | None,
    breath: int | None,
    bar: int,
    epb: int,
) -> None:
    last = len(low) - 1
    if leaving:
        low[last] = (None, None)
        support[last] = (None, None)
        for index in range(max(0, len(support) - 4), len(support)):
            if index % 2 == 1:
                support[index] = (None, None)
    elif approach is not None:
        support[last] = (None, None)
        low[last] = (approach, _BASS)
    if breath is not None and bar * epb <= breath < (bar + 1) * epb:
        local = (breath - bar * epb) * 2
        if 0 <= local < len(support):
            support[local] = (None, None)
        if 0 <= local + 1 < len(support):
            support[local + 1] = (None, None)



def _events_from_slots(
    bar: int,
    slots: list[tuple[int | None, int | None]],
    voice: int,
    accents: set[int] | None = None,
) -> list[NoteEvent]:
    marked = accents or set()
    events: list[NoteEvent] = []
    for index, (midi, velocity) in enumerate(slots):
        if midi is None:
            continue
        event = _hit(bar, index * 0.25, 0.25, midi, voice, velocity if velocity is not None else _INNER)
        if index in marked:
            event = replace(event, accent=True)
        events.append(event)
    return events



def _dance_ranked(chord: Chord, sung: int, low: int, high: int) -> list[int]:
    """Third, then seventh or sixth, then the rest of the chord."""
    third = chord.pitches[1] % 12 if len(chord.pitches) > 1 else chord.pitches[0] % 12
    seventh = chord.pitches[3] % 12 if len(chord.pitches) >= 4 else None
    sixth = (chord.pitches[0] + 9) % 12
    fifth = chord.pitches[2] % 12 if len(chord.pitches) > 2 else None
    found: list[int] = []
    seen: set[int] = set()
    for pc in (third, seventh, sixth, fifth, *_pool(chord)):
        if pc is None or pc in seen:
            continue
        seen.add(pc)
        tone = _fit(pc, low, high)
        while tone >= sung and tone - 12 >= low:
            tone -= 12
        if low <= tone < sung and tone not in found:
            found.append(tone)
    return found



def _dance_velocity(ctx: _Ctx, eighth: int, role: str, *, sync: bool) -> int:
    lead_vel = _covering_melody_velocity(ctx, eighth)
    support_vel, bass_vel = _under_lead(lead_vel, ctx.band(eighth // ctx.epb))
    velocity = bass_vel if role == "bass" else support_vel
    if sync:
        bumped = velocity + 4
        limit = lead_vel - 2 if role == "bass" else min(lead_vel - 4, bass_vel - 2)
        if bumped < limit:
            velocity = bumped
    return max(40, velocity)



def _render_vals_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    leaving, breath, do_approach = _dance_exit(ctx, bar, patterns)
    start = bar * ctx.epb
    chord = ctx.chord(bar)
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    fifth = _clamp(chord.pitches[2], ctx.bass_low, ctx.bass_high) if len(chord.pitches) >= 3 else root
    passing = _clamp(chord.pitches[1], ctx.bass_low, ctx.bass_high) if len(chord.pitches) > 1 else root
    lead = _lead_bar(ctx, bar, breath, apex)
    support: list[NoteEvent] = []
    low = [
        _hit(bar, 0.0, 0.5, root, 3, _dance_velocity(ctx, start, "bass", sync=False)),
        _hit(bar, 1.5, 0.5, fifth, 3, _dance_velocity(ctx, start + 3, "bass", sync=False)),
        replace(
            _hit(bar, 2.0, 0.25, passing, 3, _dance_velocity(ctx, start + 4, "bass", sync=True)),
            accent=True,
        ),
    ]
    previous: int | None = None
    step = 0
    for eighth in (1, 2, 4, 5):
        melody = _melody_at(ctx, start + eighth)
        legacy = _tone_below(chord, melody, ctx.mid_low, ctx.mid_high, "third")
        ranked = [
            tone
            for tone in _dance_ranked(chord, melody, ctx.mid_low, ctx.mid_high)
            if root < tone < melody and _playable([tone + ctx.semitones, melody + ctx.semitones])
        ]
        if len(ranked) >= 2:
            tone = ranked[step % 2]
            if previous is not None and tone == previous:
                tone = ranked[(step + 1) % len(ranked)]
            step += 1
        else:
            tone = legacy
        if tone is None or not root < tone < melody:
            continue
        previous = tone
        # Eighth 4 is beat 2, where 6/8 and 3/4 cross.
        sync = eighth == 4
        event = _hit(bar, eighth * 0.5, 0.25, tone, 2, _dance_velocity(ctx, start + eighth, "support", sync=sync))
        if sync:
            event = replace(event, accent=True)
        support.append(event)
    if do_approach and bar + 1 < ctx.bars:
        low.append(_hit(bar, ctx.bar_beats - 0.25, 0.25, _approach_pitch(ctx, ctx.chord(bar + 1)), 3, _BASS))
    if leaving:
        support = [
            event
            for event in support
            if not (
                int(round(event.beat * 4)) >= (ctx.epb * 2 - 4)
                and int(round(event.beat * 4)) % 2 == 1
            )
        ]
        if breath is not None and bar * ctx.epb <= breath < (bar + 1) * ctx.epb:
            local = (breath - bar * ctx.epb) * 0.5
            support = [event for event in support if not local <= event.beat < local + 0.5]
    return lead, support, low



def _slot_dance(
    ctx: _Ctx,
    bar: int,
    patterns: list[str],
    apex: set[int],
    *,
    kind: str,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    leaving, breath, do_approach = _dance_exit(ctx, bar, patterns)
    chord = ctx.chord(bar)
    sixteenths = ctx.epb * 2
    low: list[tuple[int | None, int | None]] = [(None, None)] * sixteenths
    support: list[tuple[int | None, int | None]] = [(None, None)] * sixteenths
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    fifth = _clamp(chord.pitches[2], ctx.bass_low, ctx.bass_high) if len(chord.pitches) >= 3 else root

    low_accents: set[int] = set()
    support_accents: set[int] = set()
    step = 0
    previous: int | None = None

    def sung(index: int) -> int:
        return _melody_at(ctx, bar * ctx.epb + index // 2)

    def place_low(index: int, midi: int, *, sync: bool = False) -> None:
        eighth = bar * ctx.epb + index // 2
        low[index] = (midi, _dance_velocity(ctx, eighth, "bass", sync=sync))
        if sync:
            low_accents.add(index)

    def support_at(index: int, prefer: str, *, sync: bool = False) -> None:
        nonlocal step, previous
        del prefer
        melody = sung(index)
        legacy = _tone_below(chord, melody, ctx.mid_low, ctx.mid_high, "third" if not sync else "seventh")
        ranked = [
            tone
            for tone in _dance_ranked(chord, melody, ctx.mid_low, ctx.mid_high)
            if root < tone < melody and _playable([tone + ctx.semitones, melody + ctx.semitones])
        ]
        if len(ranked) >= 2:
            tone = ranked[step % 2]
            if previous is not None and tone == previous:
                tone = ranked[(step + 1) % len(ranked)]
            step += 1
        else:
            tone = legacy
        if tone is None:
            return
        previous = tone
        eighth = bar * ctx.epb + index // 2
        support[index] = (tone, _dance_velocity(ctx, eighth, "support", sync=sync))
        if sync:
            support_accents.add(index)

    if kind == "hemiola":
        place_low(0, root)
        place_low(4, fifth, sync=True)
        place_low(8, root, sync=True)
        for index in (0, 4, 8):
            support_at(index, "third", sync=index in {4, 8})
    elif kind == "polca":
        place_low(0, root)
        place_low(6, fifth, sync=True)
        for index in (2, 4, 8, 10):
            support_at(index, "third", sync=index in {4, 10})
    else:
        for origin in (0, 8):
            place_low(origin, root)
            place_low(origin + 4, fifth)
            support_at(origin + 3, "third")
            support_at(origin + 6, "seventh", sync=True)
            support_at(origin + 7, "third", sync=True)
    leading = _approach_pitch(ctx, ctx.chord(bar + 1)) if do_approach and bar + 1 < ctx.bars else None
    _finish_dance_grid(
        low,
        support,
        leaving=leaving,
        approach=leading,
        breath=breath,
        bar=bar,
        epb=ctx.epb,
    )
    if leading is not None and not leaving:
        last = len(low) - 1
        if low[last][0] == leading:
            eighth = bar * ctx.epb + last // 2
            low[last] = (leading, _dance_velocity(ctx, eighth, "bass", sync=False))
    return (
        _lead_bar(ctx, bar, breath, apex),
        _events_from_slots(bar, support, 2, support_accents),
        _events_from_slots(bar, low, 3, low_accents),
    )



def _render_hemiola_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _slot_dance(ctx, bar, patterns, apex, kind="hemiola")



def _render_polca_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _slot_dance(ctx, bar, patterns, apex, kind="polca")



def _render_choro_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _slot_dance(ctx, bar, patterns, apex, kind="choro")



def _fifth_down(ctx: _Ctx, bar: int) -> bool:
    if bar + 1 >= ctx.bars:
        return False
    current = ctx.chord(bar).pitches[0] % 12
    nxt = ctx.chord(bar + 1).pitches[0] % 12
    return (current - nxt) % 12 == 7



def _bell_pitch(pc: int, ctx: _Ctx, above: int) -> int | None:
    floor = 76 - ctx.semitones
    best = None
    for note in range(floor, ctx.ceiling + 1):
        if note % 12 == pc and note > above:
            best = note
    return best



def _bell_groups(ctx: _Ctx, enabled_bars: set[int]) -> list[tuple[int | None, list[int]]]:
    """1D keeps the default cap. A long-form section caps at 15% of its eighths."""
    order: list[tuple] = []
    found: dict[tuple, list] = {}
    for bar in sorted(enabled_bars):
        section = ctx.section(bar) if ctx.sections else None
        if not ctx.sections or section is None:
            key = ("plain",)
            cap = None
        else:
            key = (section.start, section.end)
            cap = round(0.15 * (section.end - section.start) * ctx.epb)
        if key not in found:
            found[key] = [cap, []]
            order.append(key)
        found[key][1].append(bar)
    return [(found[key][0], found[key][1]) for key in order]



def _bell_slot(ctx: _Ctx, bar: int) -> tuple[int, int] | None:
    """One unaccented eighth: the second eighth of a hold, or the first weak eighth."""
    start = bar * ctx.epb
    end = min(len(ctx.melody), start + ctx.epb)
    eighth = start
    while eighth < end:
        nxt = eighth + 1
        limit = min(len(ctx.melody), (bar + 1) * ctx.epb if eighth // ctx.epb == bar else len(ctx.melody))
        while nxt < len(ctx.melody) and ctx.melody[nxt] == ctx.melody[eighth]:
            nxt += 1
        if nxt - eighth >= 2:
            candidate = eighth + 1
            if start <= candidate < end and candidate % ctx.epb not in ctx.strong:
                return candidate, ctx.melody[eighth]
        eighth = max(nxt, eighth + 1)
    for candidate in range(start, end):
        if candidate % ctx.epb not in ctx.strong:
            return candidate, ctx.melody[candidate]
    return None



def _insert_bells(ctx: _Ctx, lead: list[NoteEvent], support: list[NoteEvent], enabled_bars: set[int]) -> tuple[list[NoteEvent], list[NoteEvent]]:
    if not enabled_bars or ctx.rel_span <= 0.005:
        return lead, support
    bells: list[tuple[int, int, int]] = []
    for cap, bars in _bell_groups(ctx, enabled_bars):
        budget = bell_budget(ctx.rel_span) if cap is None else bell_budget(ctx.rel_span, cap)
        placed: list[int] = []
        for bar in bars:
            if budget <= 0:
                break
            if placed and bar < placed[-1] + 2:
                continue
            found = _bell_slot(ctx, bar)
            if found is None:
                continue
            slot, sung = found
            window = ctx.melody[bar * ctx.epb : (bar + 1) * ctx.epb] or [sung]
            pcs = [max(window) % 12, *sorted(ctx.chord(bar).pitch_classes, reverse=True)]
            pitch = None
            for pc in pcs:
                pitch = _bell_pitch(pc, ctx, max(sung, ctx.melody[slot]))
                if pitch is not None:
                    break
            if pitch is None:
                continue
            bells.append((slot, 1, pitch))
            placed.append(bar)
            budget -= 1
    if not bells:
        return lead, support
    for eighth, dur, pitch in bells:
        start16 = eighth * 2
        end16 = (eighth + dur) * 2
        rewritten: list[NoteEvent] = []
        for event in lead:
            if event.midi is None:
                rewritten.append(event)
                continue
            begin = _start16(event, ctx.epb)
            finish = begin + _dur16(event)
            if finish <= start16 or begin >= end16:
                rewritten.append(event)
                continue
            if begin < start16:
                rewritten.extend(_spell16(begin, start16 - begin, event.midi, ctx.epb, 1, event.velocity))
            if finish > end16:
                rewritten.extend(_spell16(end16, finish - end16, event.midi, ctx.epb, 1, event.velocity))
        # The bell replaces the held tail. Voice 1 stays monophonic, so no <chord/>.
        rewritten.extend(_spell16(start16, end16 - start16, pitch, ctx.epb, 1, _MELODY_APEX))
        lead = rewritten
    return lead, support



def _pulse_bass(ctx: _Ctx, low: list[NoteEvent], bars: set[int]) -> list[NoteEvent]:
    kept = [event for event in low if event.bar not in bars]
    points = (0, 3) if ctx.kind == "6/8" else (0, 4)
    span = 3 if ctx.kind == "6/8" else (4 if ctx.kind == "4/4" else 4)
    for bar in sorted(bars):
        root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * ctx.epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
        for offset in points:
            if offset < ctx.epb:
                length = min(span, ctx.epb - offset)
                kept.extend(_eighth_event(bar * ctx.epb + offset, length, root, ctx.epb, 3, _BASS))
    return kept



def _held_bars(ctx: _Ctx, phrase: Phrase) -> list[int]:
    found = []
    for bar in range(phrase.start // ctx.epb, (phrase.end - 1) // ctx.epb + 1):
        eighths = range(max(phrase.start, bar * ctx.epb), min(phrase.end, (bar + 1) * ctx.epb))
        pitches = [ctx.melody[eighth] for eighth in eighths]
        if pitches and len(set(pitches)) == 1 and len(pitches) == ctx.epb:
            found.append(bar)
    return found



def _perpetual_bars(ctx: _Ctx, phrase: Phrase, limit: int) -> list[int]:
    if ctx.ensemble != "barrios" or ctx.bpm < BARRIOS_TREMOLO_MIN_BPM or limit <= 0:
        return []
    apex_bar = min(ctx.bars - 1, phrase.apex.start // ctx.epb)
    if ctx.band(apex_bar) != "f" or ctx.mood(apex_bar) != "volatile":
        return []
    held = [bar for bar in _held_bars(ctx, phrase) if ctx.band(bar) == "f"]
    if not held:
        return []
    run = [held[0]]
    for bar in held[1:]:
        if bar == run[-1] + 1 and len(run) < 2:
            run.append(bar)
        else:
            break
    return run[:limit]



def _apply_perpetual(ctx: _Ctx, lead, support, low, bars: list[int]) -> tuple[list, list, list]:
    if not bars:
        return lead, support, low
    drop = set(bars)
    lead = [event for event in lead if event.bar not in drop]
    support = [event for event in support if event.bar not in drop]
    low = _pulse_bass(ctx, [event for event in low if event.bar not in drop], drop)
    for bar in bars:
        start = bar * ctx.epb
        held = ctx.melody[start]
        beats = ctx.epb // 2
        for beat in range(beats):
            direction = 1 if beat % 2 == 0 else -1
            step = _walk(held, direction, ctx.mode, ctx.treble_floor, ctx.treble_top)
            moving = _walk(held, 2 * direction, ctx.mode, ctx.treble_floor, ctx.treble_top)
            if moving == held:
                moving = _walk(held, -direction, ctx.mode, ctx.treble_floor, ctx.treble_top)
            if step == held:
                step = moving
            pitches = [held, step, moving, held]
            origin = (start + beat * 2) * 2
            for offset, pitch in enumerate(pitches):
                lead.extend(_spell16(origin + offset, 1, pitch, ctx.epb, 1, _MELODY))
    return lead, support, low



def _bells_here(ctx: _Ctx, bar: int, patterns: list[str]) -> bool:
    kind = ctx.kind_at.get(bar, "phrase")
    if kind in {"intro", "warmup"}:
        return True
    first = None
    for index, phrase in enumerate(ctx.phrases):
        start_bar = phrase.start // ctx.epb
        if ctx.kind_at.get(start_bar, "phrase") in _PEDAL:
            continue
        first = index
        break
    owner = _owner(ctx, bar)
    return owner is not None and owner == first and patterns[owner] == "preludio"



def _preludio_anchor(ctx: _Ctx, bar: int, patterns: list[str]) -> int:
    """The bar whose pedal attack rings under this preludio bar."""
    region = bar
    while region > 0 and _bar_pattern(ctx, region - 1, patterns) == "preludio":
        region -= 1
    end = bar
    while end + 1 < ctx.bars and _bar_pattern(ctx, end + 1, patterns) == "preludio":
        end += 1
    if end == region:
        return bar
    anchor = region + ((bar - region) // 2) * 2
    if anchor + 1 > end:
        return bar
    return anchor



def _catedral_bass(ctx: _Ctx, bar: int, patterns: list[str]) -> int:
    """The pedal pitch `_preludio_bass` will hold under this bar."""
    anchor = _preludio_anchor(ctx, bar, patterns)
    return _choose_bass(
        ctx.chord(anchor),
        0,
        _melody_at(ctx, anchor * ctx.epb),
        ctx.bass_low,
        ctx.bass_high,
        ctx.semitones,
    )



def _catedral_open(ctx: _Ctx, tone: int) -> bool:
    """Open 4th, 3rd, 2nd, or 1st string: D3, G3, B3, E4."""
    return (tone + ctx.semitones) in {50, 55, 59, 64}



def _catedral_canto_ceiling(ctx: _Ctx) -> int:
    return min(ctx.treble_top, 79 - ctx.semitones)



def _catedral_canto_pitch(ctx: _Ctx, pitch: int) -> int:
    """Lift a dull canto note onto the singing 1st string.

    Notes already at F4 and above stay put, so a line that is already
    `[72, 74, 76, 72]` is not moved. A C4–E4 canto steps up by octaves until
    it rings at G4 or higher, and never past the glass ceiling.
    """
    ceiling = _catedral_canto_ceiling(ctx)
    shimmer = 65 - ctx.semitones
    lifted = pitch
    while lifted < shimmer and lifted + 12 <= ceiling:
        lifted += 12
    return lifted



def _catedral_canto_pair(ctx: _Ctx, pitch_a: int, pitch_b: int) -> tuple[int, int]:
    """Lift a low cell by the same octave so the two canto notes keep their shape."""
    lifted_a = _catedral_canto_pitch(ctx, pitch_a)
    lifted_b = _catedral_canto_pitch(ctx, pitch_b)
    glass = 66 - ctx.semitones
    if pitch_a < glass and pitch_b < glass:
        shift = max(lifted_a - pitch_a, lifted_b - pitch_b)
        ceiling = _catedral_canto_ceiling(ctx)
        if shift and pitch_a + shift <= ceiling and pitch_b + shift <= ceiling:
            return pitch_a + shift, pitch_b + shift
    return lifted_a, lifted_b



def _catedral_glass_tones(ctx: _Ctx, tones: list[int], lead: int) -> list[int]:
    """Three inner tones. Prefer an open string as the top of the wave.

    The open string sits on a different string from the fretted canto, so the
    two ring together. When nothing is open, the highest three stay.
    """
    ordered = sorted(tones)
    if len(ordered) <= 3:
        return ordered
    best: tuple[int, ...] | None = None
    best_key: tuple[int, ...] | None = None
    for combo in itertools.combinations(ordered, 3):
        low, mid, upper = combo
        opens = sum(_catedral_open(ctx, tone) for tone in combo)
        upper_open = int(_catedral_open(ctx, upper))
        distinct = sum(_strings_differ(tone, lead, ctx.semitones) for tone in combo)
        spread = (
            int(_strings_differ(low, mid, ctx.semitones))
            + int(_strings_differ(mid, upper, ctx.semitones))
            + int(_strings_differ(low, upper, ctx.semitones))
        )
        key = (upper_open, opens, upper, distinct, spread)
        if best_key is None or key > best_key:
            best_key = key
            best = combo
    return list(best if best is not None else tones[-3:])



def _catedral_rank_glass(ctx: _Ctx, tones: list[int], lead: int) -> list[int]:
    """Keep every legal tone, with the campanella triple at the end."""
    if len(tones) <= 3:
        return list(tones)
    glass = _catedral_glass_tones(ctx, tones, lead)
    chosen = set(glass)
    return [tone for tone in tones if tone not in chosen] + glass



def _catedral_whisper(pitches: list[int | None], base_vel: int = 52) -> list[int]:
    """Warm inner wave (~50..55), ~2 steps gentler at the bottom of the V."""
    sounding = [pitch for pitch in pitches if pitch is not None]
    bottom = min(sounding) if sounding else None
    levels: list[int] = []
    for pitch in pitches:
        level = base_vel - 2 if pitch is not None and pitch == bottom else base_vel
        levels.append(max(48, min(55, level)))
    return levels



def _catedral_playable_tones(ctx: _Ctx, chord: Chord, bass: int, lead: int) -> list[int]:
    """Chord tones strictly between the bass and this canto note, low to high.

    Each one has to share a hand with the bass and the note that is actually
    ringing, so `_repair` has nothing to drop. Open strings under the canto
    are kept and floated into the campanella triple.
    """
    if lead <= bass + 1:
        return []
    tones = _inner_choices(chord, lead, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)

    def fits(note: int) -> bool:
        return bass < note < lead and _playable(
            [bass + ctx.semitones, note + ctx.semitones, lead + ctx.semitones]
        )

    playable = [tone for tone in tones if fits(tone)]
    if playable:
        return _catedral_rank_glass(ctx, playable, lead)
    # No chord tone frets. A scale tone in the same window keeps the sixteenths moving.
    found: list[int] = []
    low = max(ctx.mid_low, bass + 1)
    high = min(ctx.mid_high, lead - 1)
    for note in range(low, high + 1):
        if _on_scale(note, ctx.mode) and fits(note):
            found.append(note)
    return _catedral_rank_glass(ctx, found, lead)



def _catedral_lead_note(
    start: int,
    length: int,
    midi: int,
    epb: int,
    velocity: int,
    *,
    tenuto: bool = False,
) -> list[NoteEvent]:
    events = _spell16(start, length, midi, epb, 1, velocity)
    if tenuto and events:
        events[0] = replace(events[0], tenuto=True)
    return events



def _catedral_wave(ctx: _Ctx, tones: list[int], pitch_b: int, lead: int) -> list[int]:
    """Six inner pitches for sixteenths 1, 2, 3, 4, 5, and 7 of one 2-beat cell."""
    chosen = _catedral_glass_tones(ctx, tones, lead)
    if len(chosen) >= 3:
        low_mid, mid, upper_mid = chosen[-3:]
        last = upper_mid if upper_mid < pitch_b else mid
        return [upper_mid, mid, low_mid, mid, upper_mid, last]
    if len(chosen) == 2:
        lower, higher = chosen
        # Neighbours change pitch. The second example in the spec.
        return [higher, lower, higher, lower, higher, lower]
    return [chosen[0]] * 6



def _catedral_descend(ctx: _Ctx, tones: list[int], count: int, lead: int) -> list[int]:
    """`upper_mid, mid, low_mid` across the leftover beat of a 3/4 or 6/8 bar."""
    chosen = _catedral_glass_tones(ctx, tones, lead)
    if count <= 0 or not chosen:
        return []
    if len(chosen) >= 3:
        low_mid, mid, upper_mid = chosen[-3:]
        pattern = [upper_mid, mid, low_mid]
    elif len(chosen) == 2:
        lower, higher = chosen
        pattern = [higher, lower, lower]
    else:
        pattern = [chosen[0]]
    if count <= len(pattern):
        return pattern[:count]
    return [*pattern, *([pattern[-1]] * (count - len(pattern)))]



def _catedral_schedule(ctx: _Ctx, chord: Chord, bass: int, pitch_a: int, pitch_b: int) -> list[int | None]:
    """Inner pitches for sixteenths 1, 2, 3, 4, 5, 7, each playable under the canto then sounding."""
    under_a = _catedral_playable_tones(ctx, chord, bass, pitch_a)
    under_b = _catedral_playable_tones(ctx, chord, bass, pitch_b)
    shared = [tone for tone in under_a if tone in set(under_b)]
    source = shared or under_a or under_b
    canto = max(pitch_a, pitch_b)
    planned = _catedral_wave(ctx, source, pitch_b, canto) if source else [None] * 6
    pools = (under_a, under_a, under_a, under_a, under_a, under_b)
    resolved: list[int | None] = []
    previous: int | None = None
    for planned_tone, pool in zip(planned, pools):
        tone = planned_tone if pool and planned_tone in pool else None
        if tone is None and pool:
            choices = list(reversed(pool))
            if previous is not None and len(pool) > 1:
                different = [item for item in choices if item != previous]
                choices = different or choices
            tone = choices[0]
        resolved.append(tone)
        if tone is not None:
            previous = tone
    return resolved



def _catedral_emit_support(
    events: list[NoteEvent],
    start16: int,
    slots: tuple[int, ...] | list[int],
    pitches: list[int | None],
    epb: int,
    velocities: list[int],
) -> None:
    for slot, pitch, velocity in zip(slots, pitches, velocities):
        if pitch is None:
            continue
        events.extend(_spell16(start16 + slot, 1, pitch, epb, 2, max(48, min(55, velocity))))



def _catedral_cell(
    ctx: _Ctx,
    bar: int,
    eighth: int,
    bass: int,
    apex: set[int],
    phrase: Phrase | None,
    _patterns: list[str],
    lead: list[NoteEvent],
    support: list[NoteEvent],
) -> None:
    """One 2-beat *La Catedral* cell: dotted quarter, V-wave, eighth, closing inner note."""
    pitch_a = _melody_at(ctx, eighth)
    pitch_b = _melody_at(ctx, eighth + 3)
    start16 = eighth * 2
    # Keep canto under the harsh MS Basic nail-snap threshold (65): warm 56..63 range.
    raw_vel = _note_velocity(eighth, 3, apex, phrase)
    vel_a = min(63, max(56, raw_vel - 4))
    vel_b = max(54, vel_a - 2)
    lead.extend(_catedral_lead_note(start16, 6, pitch_a, ctx.epb, vel_a, tenuto=False))
    lead.extend(_catedral_lead_note(start16 + 6, 2, pitch_b, ctx.epb, vel_b, tenuto=False))
    slots = (1, 2, 3, 4, 5, 7)
    pitches = _catedral_schedule(ctx, ctx.chord(bar), bass, pitch_a, pitch_b)
    base_sup = {"p": 50, "mp": 52, "mf": 53, "f": 55}.get(ctx.band(bar), 52)
    levels = _catedral_whisper(pitches, min(base_sup, min(vel_a, vel_b) - 4))
    # Sixteenths 1..5 ring under the dotted quarter. Sixteenth 7 rings under the eighth.
    _catedral_emit_support(support, start16, slots[:5], pitches[:5], ctx.epb, levels[:5])
    _catedral_emit_support(support, start16, slots[5:], pitches[5:], ctx.epb, levels[5:])



def _catedral_tail(
    ctx: _Ctx,
    bar: int,
    eighth: int,
    eighths: int,
    bass: int,
    apex: set[int],
    phrase: Phrase | None,
    _patterns: list[str],
    lead: list[NoteEvent],
    support: list[NoteEvent],
) -> None:
    """The leftover beat of 3/4 or 6/8: one melody note, then a descending inner group."""
    if eighths <= 0:
        return
    pitch = _melody_at(ctx, eighth)
    start16 = eighth * 2
    length16 = eighths * 2
    raw_vel = _note_velocity(eighth, eighths, apex, phrase)
    velocity = min(63, max(56, raw_vel - 4))
    lead.extend(_catedral_lead_note(start16, length16, pitch, ctx.epb, velocity, tenuto=False))
    tones = _catedral_playable_tones(ctx, ctx.chord(bar), bass, pitch)
    descending = _catedral_descend(ctx, tones, length16 - 1, pitch)
    base_sup = {"p": 50, "mp": 52, "mf": 53, "f": 55}.get(ctx.band(bar), 52)
    _catedral_emit_support(
        support,
        start16,
        list(range(1, length16)),
        descending,
        ctx.epb,
        _catedral_whisper(descending, min(base_sup, velocity - 4)),
    )



def _render_catedral_preludio_bar(
    ctx: _Ctx,
    bar: int,
    patterns: list[str],
    apex: set[int],
    phrase: Phrase | None,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Voice 1 and voice 2 for one bar of *La Catedral — Preludio (Saudade)*."""
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    bass = _catedral_bass(ctx, bar, patterns)
    eighth = bar * ctx.epb
    end = eighth + ctx.epb
    while eighth + 4 <= end:
        _catedral_cell(ctx, bar, eighth, bass, apex, phrase, patterns, lead, support)
        eighth += 4
    if eighth < end:
        _catedral_tail(ctx, bar, eighth, end - eighth, bass, apex, phrase, patterns, lead, support)
    return lead, support



def _preludio_inner(ctx: _Ctx, bar: int, patterns: list[str]) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    anchor = _preludio_anchor(ctx, bar, patterns)
    anchor_lead = _covering_melody_velocity(ctx, anchor * ctx.epb)
    _support_vel, bass_vel = _under_lead(anchor_lead, ctx.band(anchor))
    strong = set(ctx.strong)
    midpoints = {ctx.epb // 2}
    if ctx.epb >= 4:
        midpoints |= {ctx.epb // 4, (3 * ctx.epb) // 4}
    previous: int | None = None
    for offset in range(ctx.epb):
        sung = _melody_at(ctx, start + offset)
        bass_guess = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
        tones = _inner_choices(chord, sung, bass_guess, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if tones:
            tone = _contour_tone(chord, tones, offset, previous)
        else:
            tone = _choose_inner(chord, sung, bass_guess, ctx.mid_low, ctx.mid_high, ctx.semitones, False, offset)
        if tone is None:
            continue
        previous = tone
        lead_vel = _covering_melody_velocity(ctx, start + offset)
        support_vel, _bass = _under_lead(lead_vel, ctx.band(bar))
        if offset not in strong and offset not in midpoints:
            support_vel = max(40, support_vel - 4)
        support_vel = min(support_vel, bass_vel - 2, lead_vel - 4)
        events.extend(_eighth_event(start + offset, 1, tone, ctx.epb, 2, max(40, support_vel)))
    return events



def _preludio_bass(ctx: _Ctx, patterns: list[str]) -> list[NoteEvent]:
    bars = [bar for bar in range(ctx.bars) if _bar_pattern(ctx, bar, patterns) == "preludio"]
    events: list[NoteEvent] = []
    index = 0
    while index < len(bars):
        run = [bars[index]]
        while index + 1 < len(bars) and bars[index + 1] == run[-1] + 1:
            index += 1
            run.append(bars[index])
        index += 1
        cursor = 0
        while cursor < len(run):
            span = 2 if cursor + 1 < len(run) else 1
            # A one-bar section rings for one bar; a longer region pairs bars.
            if len(run) == 1:
                span = 1
            bar = run[cursor]
            root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * ctx.epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
            _support_vel, bass_vel = _under_lead(_covering_melody_velocity(ctx, bar * ctx.epb), ctx.band(bar))
            if span == 1:
                # A one-bar opening keeps the strong-beat arpeggio, not a whole-note pedal.
                strong = [offset for offset in ctx.strong if offset < ctx.epb] or [0]
                bounds = [*strong, ctx.epb]
                for left, right in zip(bounds, bounds[1:]):
                    if right > left:
                        events.extend(_eighth_event(bar * ctx.epb + left, right - left, root, ctx.epb, 3, bass_vel))
            else:
                length = span * ctx.epb
                events.extend(_eighth_event(bar * ctx.epb, length, root, ctx.epb, 3, bass_vel))
            cursor += span
    return events


def barrios_scale_step(ctx: _Ctx, pitch: int, direction: int) -> int:
    """One diatonic step. The chromatic approach sits on the note before a strong beat."""
    high = min(ctx.treble_top, ctx.ceiling)
    return _walk(pitch, 1 if direction >= 0 else -1, ctx.mode, ctx.treble_floor, high)


def barrios_chromatic_approach(target: int, ascending: bool) -> int:
    """Semitone neighbor into a strong note or the passage target."""
    return target - 1 if ascending else target + 1


from app.sonify.guitar_patterns import (  # noqa: E402
    BARRIOS_TREMOLO_MIN_BPM,
    _BASS,
    _Ctx,
    _DANCE,
    _INNER,
    _MELODY,
    _MELODY_APEX,
    _PEDAL,
    _bar_pattern,
    _choose_bass,
    _choose_inner,
    _clamp,
    _contour_tone,
    _covering_melody_velocity,
    _dur16,
    _eighth_event,
    _fit,
    _framed,
    _has_hold,
    _hit,
    _inner_choices,
    _melody_activity,
    _melody_at,
    _note_velocity,
    _on_scale,
    _owner,
    _phrase_at,
    _playable,
    _pool,
    _raw_activity,
    _rises,
    _spell16,
    _start16,
    _strings_differ,
    _under_lead,
    _walk,
    bell_budget,
)
