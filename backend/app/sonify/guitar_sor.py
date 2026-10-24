"""Fernando Sor classical guitar studies, Galop, Op. 9 variations, Elegiaque, Cantabile, and Grand Solo."""

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

def _classic_macro(ctx: _Ctx, mood: str | None, bars: list[int]) -> str:
    if mood == "selloff" or ctx.bpm <= 72:
        return "elegiaque"
    if mood == "calm":
        return "cantabile"
    if mood == "volatile":
        return "mozart_var"
    if mood == "rally":
        # `character is None` or a narrow rally (< 1.2% span) stays on the
        # classical study. An energetic major rally dances Galop Op. 32 No. 6.
        if ctx.character is None and not _region_marked(ctx, bars, "rally"):
            return "study"
        if ctx.rel_span >= 0.012 and ctx.mode != "minor":
            return "galop"
        return "study"
    return "study"



def _galop_bass_points(ctx: _Ctx) -> tuple[int, ...]:
    if ctx.kind == "6/8":
        return (0, 3)
    return (0, 4)



def _galop_inner_offsets(ctx: _Ctx) -> tuple[int, ...]:
    if ctx.kind == "4/4":
        return (1, 3, 5, 7)
    if ctx.kind == "6/8":
        return (1, 2, 4, 5)
    return (1, 3, 5)



def _galop_leap(
    ctx: _Ctx,
    anchor: int,
    chord: Chord,
    support: list[NoteEvent],
    low: list[NoteEvent],
    eighth: int,
) -> int | None:
    """A diatonic third, or the next chord tone, above a strong-beat melody note."""
    bass = _sounding_midi(low, eighth, ctx.epb)
    inner = _sounding_midi(support, eighth, ctx.epb)
    floor = ctx.treble_floor
    if inner is not None:
        floor = max(floor, inner + 1)
    if bass is not None:
        floor = max(floor, bass + 1)
    high = min(ctx.treble_top, ctx.ceiling, 81 - ctx.semitones)
    if floor > high:
        return None
    third = _walk(anchor, 2, ctx.mode, floor, high)
    candidates: list[int] = []
    if third > anchor and floor <= third <= high:
        candidates.append(third)
    for pc in chord.pitch_classes:
        for note in range(max(floor, anchor + 1), high + 1):
            if note % 12 == pc and note not in candidates:
                candidates.append(note)
                break
    for pitch in candidates:
        sounding = [pitch + ctx.semitones]
        if bass is not None:
            sounding.append(bass + ctx.semitones)
        if inner is not None:
            sounding.append(inner + ctx.semitones)
        above = inner if inner is not None else bass
        if above is not None and pitch <= above:
            continue
        if _playable(sounding):
            return pitch
    return None



def _replace_eighth(events: list[NoteEvent], eighth: int, pitch: int, epb: int, **flags) -> list[NoteEvent]:
    """Split the note that covers `eighth` and put `pitch` on that eighth alone."""
    when = eighth * 2
    rewritten: list[NoteEvent] = []
    for event in events:
        if event.midi is None:
            rewritten.append(event)
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if finish <= when or begin >= when + 2:
            rewritten.append(event)
            continue
        if begin < when:
            rewritten.extend(_spell16(begin, when - begin, event.midi, epb, event.voice, event.velocity, event.accent))
        leap = _spell16(when, 2, pitch, epb, event.voice, event.velocity or _MELODY, False)
        if leap:
            leap[0] = replace(leap[0], **flags)
        rewritten.extend(leap)
        if finish > when + 2:
            rewritten.extend(
                _spell16(when + 2, finish - (when + 2), event.midi, epb, event.voice, event.velocity, False)
            )
    return rewritten



def _galop_sparkle(
    ctx: _Ctx,
    bar: int,
    lead: list[NoteEvent],
    support: list[NoteEvent],
    low: list[NoteEvent],
    phrase: Phrase | None,
) -> list[NoteEvent]:
    """Op. 32 No. 6: the second eighth of a strong-beat hold leaps a diatonic third."""
    window = ctx.melody[bar * ctx.epb : (bar + 1) * ctx.epb]
    rising = bool(window) and window[-1] > window[0]
    if phrase is not None and phrase.rise >= MIN_RISE and bar * ctx.epb <= phrase.apex.start:
        rising = True
    if ctx.mood(bar) != "rally" and not rising:
        return lead
    start = bar * ctx.epb
    end = min(len(ctx.melody), start + ctx.epb)
    eighth = start
    while eighth < end:
        nxt = eighth + 1
        while nxt < end and ctx.melody[nxt] == ctx.melody[eighth]:
            nxt += 1
        local = eighth - start
        if local in ctx.strong and nxt - eighth >= 2:
            leap_at = eighth + 1
            pitch = _galop_leap(ctx, ctx.melody[eighth], ctx.chord(bar), support, low, leap_at)
            if pitch is not None and pitch != ctx.melody[eighth]:
                lead = _replace_eighth(lead, leap_at, pitch, ctx.epb, staccato=True)
        eighth = max(nxt, eighth + 1)
    return lead



def _render_galop_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Galop Op. 32 No. 6: bouncing root/fifth, off-beat chords, a sparkling melody."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    sung = _melody_at(ctx, start)
    root = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
    fifth = _choose_bass(chord, 2, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
    points = _galop_bass_points(ctx)
    low: list[NoteEvent] = []
    for index, offset in enumerate(points):
        if offset >= ctx.epb:
            continue
        nxt = points[index + 1] if index + 1 < len(points) else ctx.epb
        length = min(2, ctx.epb - offset, nxt - offset)
        if length <= 0:
            continue
        pitch = root if index % 2 == 0 else fifth
        low.extend(_stamp(_eighth_event(start + offset, length, pitch, ctx.epb, 3, _BASS), staccato=True, accent=offset == 0))
    support: list[NoteEvent] = []
    pair_step = 0
    for offset in _galop_inner_offsets(ctx):
        if offset >= ctx.epb:
            continue
        melody = _melody_at(ctx, start + offset)
        bass = _sounding_midi(low, start + offset, ctx.epb) or root
        choices = _inner_choices(chord, melody, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if len(choices) >= 2:
            pair = _study_pair(chord, choices)
            tone = pair[pair_step % len(pair)] if len(pair) >= 2 else choices[pair_step % len(choices)]
            pair_step += 1
        elif choices:
            tone = choices[0]
        else:
            tone = _choose_inner(chord, melody, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False, offset)
        if tone is None:
            continue
        support.extend(_stamp(_eighth_event(start + offset, 1, tone, ctx.epb, 2, _INNER), staccato=True, accent=True))
    support, low = _shape_accompaniment(ctx, support, low)
    part_lead = _sustain(ctx.melody, start, start + ctx.epb, ctx.epb, apex, phrase=phrase)
    part_lead = _galop_sparkle(ctx, bar, part_lead, support, low, phrase)
    return part_lead, support, low



def _mozart_offsets(ctx: _Ctx) -> tuple[int, ...]:
    if ctx.kind == "6/8":
        return (1, 2, 4, 5)
    if ctx.kind == "3/4":
        return (1, 2, 3, 5)
    return (1, 2, 3, 5, 6, 7)



def _mozart_pool(ctx: _Ctx, sung: int, bass: int) -> list[int]:
    """Scale notes strictly between `bass` and `sung` that fit one hand position."""
    if sung <= bass + 1:
        return []
    return [
        note
        for note in range(max(ctx.mid_low, bass + 1), min(ctx.mid_high, sung - 1) + 1)
        if _on_scale(note, ctx.mode)
        and _playable([bass + ctx.semitones, note + ctx.semitones, sung + ctx.semitones])
    ]



def _mozart_bass_plan(ctx: _Ctx, bar: int, root: int, fifth: int) -> tuple[tuple[int, int, int], ...]:
    start = bar * ctx.epb
    if ctx.kind == "6/8":
        raw = ((0, 3, root), (3, 3, fifth))
    elif ctx.kind == "3/4":
        raw = ((0, 4, root), (4, max(1, ctx.epb - 4), fifth))
    else:
        raw = ((0, 4, root), (4, 4, fifth))
    candidates = [root, fifth]
    for open_pitch in _OPENS:
        written_open = open_pitch - ctx.semitones
        if ctx.bass_low <= written_open <= ctx.bass_high and written_open not in candidates:
            candidates.append(written_open)
    for pitch in range(ctx.bass_low, ctx.bass_high + 1):
        if pitch not in candidates:
            candidates.append(pitch)
    resolved: list[tuple[int, int, int]] = []
    prev_pool: list[int] = []
    for offset, length, preferred in raw:
        span_eighths = [
            start + step
            for step in range(offset, min(ctx.epb, offset + length))
        ]
        chosen = preferred
        order = [preferred, *(cand for cand in candidates if cand != preferred)]
        for cand in order:
            span_pools = [_mozart_pool(ctx, _melody_at(ctx, eighth), cand) for eighth in span_eighths]
            if not all(
                len(pool) >= 2 and any(0 < abs(a - b) <= 2 for a in pool for b in pool)
                for pool in span_pools
            ):
                continue
            if prev_pool and span_pools:
                first_pool = span_pools[0]
                if not any(abs(a - b) <= 2 for a in prev_pool for b in first_pool):
                    continue
            chosen = cand
            prev_pool = span_pools[-1]
            break
        else:
            for cand in order:
                if all(_mozart_pool(ctx, _melody_at(ctx, eighth), cand) for eighth in span_eighths):
                    chosen = cand
                    break
        resolved.append((offset, length, chosen))
    return tuple(resolved)



def _mozart_bridge_notes(
    ctx: _Ctx,
    previous: int,
    tone: int,
    sung: int,
    bass: int,
) -> list[int]:
    """Scale steps strictly between `previous` and `tone` that fit the hand."""
    pool = _mozart_pool(ctx, sung, bass)
    if not pool:
        return []
    single = [
        note
        for note in pool
        if (previous < note < tone or tone < note < previous)
        and abs(note - previous) <= 2
        and abs(tone - note) <= 2
    ]
    if single:
        mid = (previous + tone) / 2.0
        return [min(single, key=lambda note: abs(note - mid))]
    direction = 1 if tone > previous else -1
    for first in pool:
        if not (0 < (first - previous) * direction <= 2):
            continue
        for second in pool:
            if not (0 < (second - first) * direction <= 2):
                continue
            if 0 < (tone - second) * direction <= 2:
                return [first, second]
    return []



def _mozart_valid_bridge(
    ctx: _Ctx,
    previous: int,
    tone: int,
    sung_then: int,
    bass_then: int,
    melody: int,
    bass: int,
    *,
    has_gap: bool,
    can_split_prev: bool,
) -> list[int]:
    if not has_gap and not can_split_prev:
        return []
    bridge = _mozart_bridge_notes(ctx, previous, tone, sung_then, bass_then)
    if not bridge:
        return []
    if not has_gap and len(bridge) >= 2:
        if not (
            bass < bridge[1] < melody
            and _playable([bass + ctx.semitones, bridge[1] + ctx.semitones, melody + ctx.semitones])
        ):
            return []
    return bridge



def _mozart_inner(
    ctx: _Ctx,
    chord: Chord,
    sung: int,
    bass: int,
    previous: int | None,
    *,
    follow_leap: bool = False,
    allowed_pool: list[int] | None = None,
    bridge_sung: int | None = None,
    bridge_bass: int | None = None,
    has_gap: bool = False,
    can_split_prev: bool = True,
) -> int | None:
    """A stepwise third or sixth under the melody. Every step stays playable and <= 2 semitones."""
    del chord
    parallel = _parallel(sung, bass, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, previous)
    pool = allowed_pool if allowed_pool is not None else _mozart_pool(ctx, sung, bass)
    if not pool:
        return None
    if previous is None:
        if parallel is not None and parallel in pool:
            return parallel
        target = parallel if parallel is not None else pool[len(pool) // 2]
        return min(pool, key=lambda tone: (abs(tone - target), tone))
    b_sung = sung if bridge_sung is None else bridge_sung
    b_bass = bass if bridge_bass is None else bridge_bass
    if follow_leap and parallel is not None and abs(parallel - previous) >= 3:
        reachable = [
            tone
            for tone in pool
            if 3 <= abs(tone - previous) <= 5
            and bool(
                _mozart_valid_bridge(
                    ctx,
                    previous,
                    tone,
                    b_sung,
                    b_bass,
                    sung,
                    bass,
                    has_gap=has_gap,
                    can_split_prev=can_split_prev,
                )
            )
        ]
        if parallel in reachable:
            return parallel
        if reachable:
            return min(reachable, key=lambda tone: abs(tone - parallel))
    stepped = [tone for tone in pool if 0 < abs(tone - previous) <= 2]
    if stepped:
        if parallel is not None and parallel in stepped:
            return parallel
        target = parallel if parallel is not None else previous
        return min(stepped, key=lambda tone: (abs(tone - previous), abs(tone - target), tone))
    if previous in pool:
        return previous
    bridged = [
        tone
        for tone in pool
        if bool(
            _mozart_valid_bridge(
                ctx,
                previous,
                tone,
                b_sung,
                b_bass,
                sung,
                bass,
                has_gap=has_gap,
                can_split_prev=can_split_prev,
            )
        )
    ]
    if bridged:
        return min(bridged, key=lambda tone: (abs(tone - previous), tone))
    return None



def _render_mozart_var_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Op. 9 variations: classical bass, and a stepwise counter-melody in the inner voice."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    sung = _melody_at(ctx, start)
    root = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
    fifth = _choose_bass(chord, 2, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
    low: list[NoteEvent] = []
    for offset, length, pitch in _mozart_bass_plan(ctx, bar, root, fifth):
        if offset >= ctx.epb or length <= 0:
            continue
        low.extend(_eighth_event(start + offset, min(length, ctx.epb - offset), pitch, ctx.epb, 3, _BASS))
    offsets = [offset for offset in _mozart_offsets(ctx) if offset < ctx.epb]
    pools: list[list[int]] = []
    for offset in offsets:
        melody = _melody_at(ctx, start + offset)
        bass = _sounding_midi(low, start + offset, ctx.epb) or root
        pools.append(_mozart_pool(ctx, melody, bass))
    for idx in range(len(offsets) - 2, -1, -1):
        curr_pool = pools[idx]
        next_pool = pools[idx + 1]
        if not curr_pool or not next_pool:
            continue
        has_gap = offsets[idx + 1] - offsets[idx] >= 2
        gap_eighth = start + (offsets[idx + 1] - 1 if has_gap else offsets[idx])
        gap_sung = _melody_at(ctx, gap_eighth)
        gap_bass = _sounding_midi(low, gap_eighth, ctx.epb) or root
        next_sung = _melody_at(ctx, start + offsets[idx + 1])
        next_bass = _sounding_midi(low, start + offsets[idx + 1], ctx.epb) or root
        filtered = [
            u
            for u in curr_pool
            if any(abs(v - u) <= 2 for v in next_pool)
            or any(
                bool(
                    _mozart_valid_bridge(
                        ctx,
                        u,
                        v,
                        gap_sung,
                        gap_bass,
                        next_sung,
                        next_bass,
                        has_gap=has_gap,
                        can_split_prev=True,
                    )
                )
                for v in next_pool
            )
        ]
        if filtered:
            pools[idx] = filtered
    support: list[NoteEvent] = []
    previous: int | None = None
    previous_offset: int | None = None
    previous_melody: int | None = None
    for idx, offset in enumerate(offsets):
        melody = _melody_at(ctx, start + offset)
        bass = _sounding_midi(low, start + offset, ctx.epb) or root
        has_gap = previous_offset is not None and offset - previous_offset >= 2
        bridge_eighth = start + ((offset - 1) if has_gap else (previous_offset or offset))
        sung_then = _melody_at(ctx, bridge_eighth)
        bass_then = _sounding_midi(low, bridge_eighth, ctx.epb) or bass
        can_split_prev = bool(
            support
            and support[-1].midi is not None
            and abs(support[-1].duration_beats - 0.5) < 1e-6
        )
        leapt = (
            has_gap
            and previous_melody is not None
            and abs(melody - previous_melody) >= 4
        )
        tone = _mozart_inner(
            ctx,
            chord,
            melody,
            bass,
            previous,
            follow_leap=leapt,
            allowed_pool=pools[idx],
            bridge_sung=sung_then,
            bridge_bass=bass_then,
            has_gap=has_gap,
            can_split_prev=can_split_prev,
        )
        if tone is None:
            continue
        if (
            previous is not None
            and previous_offset is not None
            and abs(tone - previous) >= 3
        ):
            bridge = _mozart_valid_bridge(
                ctx,
                previous,
                tone,
                sung_then,
                bass_then,
                melody,
                bass,
                has_gap=has_gap,
                can_split_prev=can_split_prev,
            )
            if not bridge:
                continue
            if has_gap:
                if len(bridge) == 1:
                    support.extend(_eighth_event(bridge_eighth, 1, bridge[0], ctx.epb, 2, _INNER))
                else:
                    support.extend(_spell16(bridge_eighth * 2, 1, bridge[0], ctx.epb, 2, _INNER))
                    support.extend(_spell16(bridge_eighth * 2 + 1, 1, bridge[1], ctx.epb, 2, _INNER))
            else:
                held = support[-1]
                support[-1] = replace(held, duration_beats=0.25)
                support.append(
                    replace(
                        held,
                        beat=held.beat + 0.25,
                        duration_beats=0.25,
                        midi=bridge[0],
                        tie_start=False,
                        tie_stop=False,
                    )
                )
                if len(bridge) >= 2:
                    support.extend(_spell16((start + offset) * 2, 1, bridge[1], ctx.epb, 2, _INNER))
                    support.extend(_spell16((start + offset) * 2 + 1, 1, tone, ctx.epb, 2, _INNER))
                    previous = tone
                    previous_offset = offset
                    previous_melody = melody
                    continue
        support.extend(_eighth_event(start + offset, 1, tone, ctx.epb, 2, _INNER))
        previous = tone
        previous_offset = offset
        previous_melody = melody
    support, low = _shape_accompaniment(ctx, support, low)
    part_lead = _sustain(ctx.melody, start, start + ctx.epb, ctx.epb, apex, phrase=phrase)
    return part_lead, support, low



def _render_plain_arpeggio(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Root on the strong eighths only. This is the texture `character is None` keeps."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    strong = [offset for offset in ctx.strong if offset < ctx.epb] or [0]
    bounds = [*strong, ctx.epb]
    low: list[NoteEvent] = []
    for left, right in zip(bounds, bounds[1:]):
        if right > left:
            low.extend(_eighth_event(start + left, right - left, root, ctx.epb, 3, _BASS))
    pool = _pool(chord)
    support: list[NoteEvent] = []
    for local in sorted(_inner_eighths(ctx.epb, set(ctx.strong), ctx.band(bar))):
        sung = _melody_at(ctx, start + local)
        tone = _fit(pool[local % len(pool)], ctx.mid_low, ctx.mid_high)
        while tone >= sung and tone - 12 >= ctx.mid_low:
            tone -= 12
        if tone >= sung or tone <= root:
            continue
        support.extend(_eighth_event(start + local, 1, tone, ctx.epb, 2, _INNER))
    return support, low



def _render_study_bar(ctx: _Ctx, bar: int, level: int, color: bool) -> tuple[list[NoteEvent], list[NoteEvent]]:
    if ctx.mood(bar) is None:
        return _render_plain_arpeggio(ctx, bar)
    band = ctx.band(bar)
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    lead = _melody_at(ctx, start)
    root = _choose_bass(chord, 0, lead, ctx.bass_low, ctx.bass_high, ctx.semitones)
    fifth = _choose_bass(chord, 2, lead, ctx.bass_low, ctx.bass_high, ctx.semitones)
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []
    epb = ctx.epb
    if ctx.kind == "4/4":
        if band == "p" and level < 1:
            low.extend(_eighth_event(start, epb, root, epb, 3, _BASS))
        elif band == "f" or (level >= 1 and band == "f"):
            low.extend(_eighth_event(start, 4, root, epb, 3, _BASS))
            low.extend(_eighth_event(start + 4, 2, fifth, epb, 3, _BASS))
            low.extend(_eighth_event(start + 6, 2, root, epb, 3, _BASS))
        elif band == "mp" and level < 1:
            low.extend(_eighth_event(start, 4, root, epb, 3, _BASS))
            low.extend(_eighth_event(start + 4, 4, fifth, epb, 3, _BASS))
        else:
            low.extend(_eighth_event(start, 4, root, epb, 3, _BASS))
            low.extend(_eighth_event(start + 4, 4, fifth, epb, 3, _BASS))
    elif ctx.kind == "6/8":
        if band == "p" and level < 1:
            low.extend(_eighth_event(start, epb, root, epb, 3, _BASS))
        else:
            low.extend(_eighth_event(start, 3, root, epb, 3, _BASS))
            low.extend(_eighth_event(start + 3, 3, fifth, epb, 3, _BASS))
    else:
        if band == "p" and level < 1:
            low.extend(_eighth_event(start, epb, root, epb, 3, _BASS))
        else:
            low.extend(_eighth_event(start, 4, root, epb, 3, _BASS))
            low.extend(_eighth_event(start + 4, 2, fifth, epb, 3, _BASS))
    points = sorted(_support_eighths(ctx.kind, band, color, level))
    step = 0
    previous: int | None = None
    for offset in points:
        sung = _melody_at(ctx, start + offset)
        sounding_bass = root
        for event in low:
            if event.midi is None:
                continue
            begin = _start16(event, epb) // 2
            if begin <= start + offset < begin + _dur16(event) // 2:
                sounding_bass = event.midi
        tone = _choose_inner(chord, sung, sounding_bass, ctx.mid_low, ctx.mid_high, ctx.semitones, color, offset)
        quiet = band == "p" and level < 1
        choices = _inner_choices(chord, sung, sounding_bass, ctx.mid_low, ctx.mid_high, ctx.semitones, color)
        if not quiet and len(points) >= 2 and len(choices) >= 2:
            pair = _study_pair(chord, choices)
            if len(pair) >= 2:
                tone = pair[step % 2]
                if previous is not None and tone == previous:
                    tone = pair[(step + 1) % 2]
                step += 1
                previous = tone
        elif quiet and tone is not None:
            # A quiet bar keeps one inner note, the 3rd when it fits.
            third = _choose_bass(chord, 1, sung, ctx.mid_low, ctx.mid_high, ctx.semitones)
            if sounding_bass < third < sung:
                tone = third
            elif not (sounding_bass < tone < sung):
                tone = None
        if tone is None:
            continue
        previous = tone
        support.extend(_eighth_event(start + offset, 1, tone, epb, 2, _INNER))
    return _shape_accompaniment(ctx, support, low)



def _step_down(note: int, mode: str, low: int, high: int) -> int:
    classes = C_NATURAL_MINOR_PCS if mode == "minor" else C_MAJOR_PCS
    for shift in range(1, 12):
        candidate = note - shift
        if candidate % 12 in classes:
            return _clamp(candidate, low, high)
    return _clamp(note - 1, low, high)



def _march_grid(ctx: _Ctx) -> list[tuple[int, int, str]]:
    if ctx.epb == 8:
        return [(0, 3, "root"), (3, 1, "step"), (4, 3, "fifth"), (7, 1, "step")]
    if ctx.kind == "6/8":
        return [(0, 2, "root"), (2, 1, "step"), (3, 2, "fifth"), (5, 1, "step")]
    return [(0, 3, "root"), (3, 1, "step"), (4, 2, "fifth")]



def _render_elegiaque_bar(ctx: _Ctx, bar: int, phrase: Phrase | None, descend: bool) -> tuple[list[NoteEvent], list[NoteEvent]]:
    del descend
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    fifth = _clamp(chord.pitches[2], ctx.bass_low, ctx.bass_high) if len(chord.pitches) >= 3 else root
    low: list[NoteEvent] = []
    owner = _owner(ctx, bar)
    key = owner if owner is not None else -1
    prev = ctx.elegy_prev.get(key)
    closes = bool(phrase is not None and phrase.closes)
    last_bar = (phrase.end - 1) // ctx.epb if phrase is not None else bar
    start_bar = phrase.start // ctx.epb if phrase is not None else bar
    sustain = bool(ctx.kind == "3/4" and closes and bar == last_bar)
    lament = bool(ctx.mode == "minor" and closes and bar >= max(start_bar, last_bar - 1))
    if sustain:
        low.extend(_eighth_event(start, ctx.epb, root, ctx.epb, 3, _BASS))
        prev = root
    else:
        for local, length, role in _march_grid(ctx):
            if lament:
                pitch = root if prev is None else _step_down(prev, ctx.mode, ctx.bass_low, ctx.bass_high)
            elif role == "fifth":
                pitch = fifth
            elif role == "step":
                pitch = _step_down(root if prev is None else prev, ctx.mode, ctx.bass_low, ctx.bass_high)
            else:
                pitch = root
            low.extend(_eighth_event(start + local, length, pitch, ctx.epb, 3, _BASS))
            prev = pitch
    ctx.elegy_prev[key] = prev
    thinner = _SPARSER.get(ctx.band(bar), "mp")
    pool = _pool(chord)
    support: list[NoteEvent] = []
    sounding: dict[int, int] = {}
    for event in low:
        if event.midi is None:
            continue
        begin = _start16(event, ctx.epb) // 2
        for offset in range(max(1, _dur16(event) // 2)):
            sounding[begin + offset] = event.midi
    previous_inner: int | None = None
    previous_bass: int | None = None
    root_pc = chord.pitches[0] % 12
    rich_pcs = {(root_pc + interval) % 12 for interval in (3, 4, 8, 9, 10, 11)}
    for local in sorted(_inner_eighths(ctx.epb, set(ctx.strong), thinner)):
        eighth = start + local
        sung = _melody_at(ctx, eighth)
        bass = sounding.get(eighth, root)
        bass_delta = 0 if previous_bass is None else bass - previous_bass
        playable_now = [
            note
            for note in range(ctx.mid_low, ctx.mid_high + 1)
            if note % 12 in rich_pcs and bass < note < sung and _playable(
                [bass + ctx.semitones, note + ctx.semitones, sung + ctx.semitones]
            )
        ]
        tone: int | None = None
        if playable_now and previous_inner is not None and bass_delta < 0:
            higher = [note for note in playable_now if note > previous_inner]
            others = [note for note in playable_now if note != previous_inner]
            tone = min(higher) if higher else (max(others) if others else playable_now[-1])
        elif playable_now and previous_inner is not None and bass_delta > 0:
            lower = [note for note in playable_now if note < previous_inner]
            tone = max(lower) if lower else min(playable_now)
        elif playable_now:
            thirds = [note for note in playable_now if note % 12 in {(root_pc + 3) % 12, (root_pc + 4) % 12}]
            tone = max(thirds or playable_now)
        if tone is None:
            tone = _fit(pool[local % len(pool)], ctx.mid_low, ctx.mid_high)
            while tone >= sung and tone - 12 >= ctx.mid_low:
                tone -= 12
            if tone >= sung or tone <= bass:
                previous_bass = bass
                continue
        previous_inner = tone
        previous_bass = bass
        support.extend(_eighth_event(eighth, 1, tone, ctx.epb, 2, _INNER))
    return _shape_accompaniment(ctx, support, low)



def _step_below(note: int, mode: str, floor: int) -> int | None:
    for candidate in range(note - 1, floor - 1, -1):
        if _on_scale(candidate, mode) and note - candidate in {1, 2}:
            return candidate
    return None



def _dotted_pair(ctx: _Ctx, eighth: int, root: int, descend: bool) -> list[NoteEvent]:
    short = _step_below(root, ctx.mode, ctx.bass_low) if descend else None
    events = _eighth_event(eighth, 3, root, ctx.epb, 3, _BASS)
    if short is None:
        events.extend(_eighth_event(eighth + 3, 1, root, ctx.epb, 3, _BASS))
    else:
        events.extend(_eighth_event(eighth + 3, 1, short, ctx.epb, 3, _INNER))
    return events



def _short_pair(ctx: _Ctx, eighth: int, long: int, short_len: int, root: int, descend: bool) -> list[NoteEvent]:
    nxt = _step_below(root, ctx.mode, ctx.bass_low) if descend else None
    events = _eighth_event(eighth, long, root, ctx.epb, 3, _BASS)
    events.extend(_eighth_event(eighth + long, short_len, nxt if nxt is not None else root, ctx.epb, 3, _INNER if nxt else _BASS))
    return events



def _render_cantabile(ctx: _Ctx, phrase: Phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    apex = _apex_eighths(ctx.phrases)
    lead = _sustain(ctx.melody, phrase.start, phrase.end, ctx.epb, apex, phrase=phrase)
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for bar in range(phrase.start // ctx.epb, (phrase.end - 1) // ctx.epb + 1):
        band = ctx.band(bar)
        root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * ctx.epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
        low.extend(_eighth_event(bar * ctx.epb, 4 if ctx.kind == "4/4" and band in {"mf", "f"} else ctx.epb, root, ctx.epb, 3, _BASS))
        if ctx.kind == "4/4" and band in {"mf", "f"}:
            fifth = _choose_bass(ctx.chord(bar), 2, _melody_at(ctx, bar * ctx.epb + 4), ctx.bass_low, ctx.bass_high, ctx.semitones)
            low.extend(_eighth_event(bar * ctx.epb + 4, 4, fifth, ctx.epb, 3, _BASS))
    low = _shape_line(ctx, low, "bass")
    ceiling = _bass_ceiling(ctx, low)
    previous: int | None = None
    shaped: list[NoteEvent] = []
    for event in lead:
        if event.midi is None:
            continue
        eighth = _start16(event, ctx.epb) // 2
        bass = _sounding_midi(low, eighth, ctx.epb) or ctx.bass_low
        tone = _parallel(event.midi, bass, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, previous)
        if tone is None:
            continue
        previous = tone
        lead_vel = event.velocity or _MELODY
        band = ctx.band(event.bar)
        if _rises(phrase):
            band = _swell_band(swell(phrase, min(eighth, phrase.end - 1)))
        support_vel, _bass_vel = _under_lead(lead_vel, band)
        if eighth in ceiling:
            support_vel = min(support_vel, ceiling[eighth])
        support_vel = max(40, min(support_vel, lead_vel - 4))
        shaped.append(replace(event, midi=tone, velocity=support_vel, voice=2, slur_start=False, slur_stop=False))
    return lead, shaped, low



def _grand_levels(ctx: _Ctx, patterns: list[str]) -> dict[int, int]:
    """Figuration level for Sor study phrases that belong to a Grand Solo family."""
    if ctx.ensemble != "classic" or ctx.bpm < BARRIOS_TREMOLO_MIN_BPM:
        return {}
    first_body = None
    for index, phrase in enumerate(ctx.phrases):
        bar = phrase.start // ctx.epb
        if ctx.kind_at.get(bar, "phrase") not in _PEDAL:
            first_body = index
            break
    levels: dict[int, int] = {}
    last_section = None
    last_sig = None
    last_level = 0
    last_index = None
    seen_slots: dict[int, tuple] = {}
    originals: set[int] = set()
    for index, phrase in enumerate(ctx.phrases):
        if patterns[index] != "study" or index == first_body:
            continue
        bar = min(ctx.bars - 1, phrase.apex.start // ctx.epb)
        if ctx.mood(bar) not in {"rally", "volatile"}:
            continue
        section = ctx.section(bar)
        slot = 0 if section is None else section.regime_slot
        sig = _signature(ctx, phrase)
        recap = slot in originals and (section is None or id(section) not in {id(item) for item in ctx.sections[:1]})
        # A later section that reuses a regime slot is the recapitulation.
        if section is not None and slot in seen_slots and section is not seen_slots[slot][0]:
            recap = True
        new_section = section is not last_section
        if new_section and not recap:
            level = 0
        elif new_section and recap:
            prev = seen_slots.get(slot)
            level = min(2, prev[2] + 1) if prev is not None and _same_family(ctx, prev[1], sig) else 0
        elif last_index == index - 1 and last_sig is not None and _same_family(ctx, last_sig, sig):
            level = min(2, last_level + 1)
        else:
            level = 0
        levels[index] = level
        if section is not None and slot not in seen_slots:
            seen_slots[slot] = (section, sig, level)
            originals.add(slot)
        elif section is not None:
            seen_slots[slot] = (seen_slots[slot][0], sig, level)
        last_section = section
        last_sig = sig
        last_level = level
        last_index = index
    return levels



def _signature(ctx: _Ctx, phrase: Phrase) -> tuple:
    opening = ctx.chord(phrase.start // ctx.epb).pitches[0] % 12
    first = ctx.melody[phrase.start]
    last = ctx.melody[phrase.end - 1]
    contour = (last > first) - (last < first)
    apex = _peak(ctx.melody, phrase)
    try:
        apex_degree = _degree(apex, ctx.mode) if _on_scale(apex, ctx.mode) else apex % 12
    except ValueError:
        apex_degree = apex % 12
    return (opening, contour, apex_degree, phrase.end - phrase.start, apex)



def _same_family(ctx: _Ctx, left: tuple, right: tuple) -> bool:
    if left[0] != right[0] or left[1] != right[1]:
        return False
    if abs(left[3] - right[3]) > 4:
        return False
    if isinstance(left[2], int) and isinstance(right[2], int) and left[2] < 7 and right[2] < 7:
        gap = min((left[2] - right[2]) % 7, (right[2] - left[2]) % 7)
        return gap <= 2
    return abs(left[4] - right[4]) <= 4



def _fanfare_bars(ctx: _Ctx, levels: dict[int, int]) -> set[int]:
    if ctx.ensemble != "classic" or ctx.bpm < BARRIOS_TREMOLO_MIN_BPM or not levels:
        return set()
    wanted: set[int] = set()
    sections = list(ctx.sections) or [None]
    for section in sections:
        begin, end = (0, ctx.bars) if section is None else (section.start, section.end)
        owns = False
        for index in levels:
            phrase = ctx.phrases[index]
            if begin <= phrase.start // ctx.epb < end:
                owns = True
                break
        if not owns:
            continue
        if ctx.band(begin) == "f":
            wanted.add(begin)
    return wanted



def _caesura_eighths(ctx: _Ctx, levels: dict[int, int]) -> set[int]:
    if not levels:
        return set()
    found: set[int] = set()
    groups: dict[tuple, list[int]] = {}
    for index, phrase in enumerate(ctx.phrases):
        section = ctx.section(phrase.start // ctx.epb)
        key = (0, ctx.bars) if section is None else (section.start, section.end)
        if any(key[0] <= ctx.phrases[item].start // ctx.epb < key[1] for item in levels):
            groups.setdefault(key, []).append(index)
    for indexes in groups.values():
        best_index = None
        best_peak = None
        for index in indexes:
            phrase = ctx.phrases[index]
            peak = _peak(ctx.melody, phrase)
            if best_peak is None or peak >= best_peak:
                best_peak = peak
                best_index = index
        if best_index is None:
            continue
        position = indexes.index(best_index)
        if position == 0:
            continue
        previous = ctx.phrases[indexes[position - 1]]
        if previous.closes:
            found.add(previous.end - 1)
    return found



def _apply_fanfare(ctx: _Ctx, lead, support, low, bar: int) -> tuple[list, list, list]:
    sung = _melody_at(ctx, bar * ctx.epb)
    root = _choose_bass(ctx.chord(bar), 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
    tone = _choose_inner(ctx.chord(bar), sung, root, ctx.mid_low, ctx.mid_high, ctx.semitones, False, 1)
    if tone is None:
        tone = _choose_inner(ctx.chord(bar), sung, root, ctx.mid_low, ctx.mid_high, ctx.semitones, False, 0)

    def ensure(events: list[NoteEvent], midi: int, voice: int, velocity: int) -> list[NoteEvent]:
        for event in events:
            if event.bar == bar and abs(event.beat) < 1e-6 and event.midi is not None:
                return events
        return [*_eighth_event(bar * ctx.epb, 1, midi, ctx.epb, voice, velocity), *events]

    lead = ensure(lead, sung, 1, _MELODY)
    if tone is not None:
        support = ensure(support, tone, 2, _INNER)
    low = ensure(low, root, 3, _BASS)
    return lead, support, low



def _phrase_appoggiatura(ctx: _Ctx, phrase: Phrase) -> dict[int, tuple[int, bool]]:
    """One accented neighbor, a scale step against the step into the next note.

    The neighbor may sit inside or outside the chord. The next eighth keeps the
    written pitch and is not accented.
    """
    scale = _melody_scale(ctx.mode)
    degree = {note: index for index, note in enumerate(scale)}
    spans: list[tuple[int, int, int]] = []
    index = phrase.start
    limit = min(phrase.end, len(ctx.melody))
    while index < limit:
        nxt = index + 1
        while nxt < limit and ctx.melody[nxt] == ctx.melody[index]:
            nxt += 1
        spans.append((index, nxt, ctx.melody[index]))
        index = nxt
    for position, (start, end, pitch) in enumerate(spans):
        if start % ctx.epb not in ctx.strong or end - start < 2 or position + 1 >= len(spans):
            continue
        nxt_pitch = spans[position + 1][2]
        if pitch not in degree or nxt_pitch not in degree:
            continue
        diff = degree[nxt_pitch] - degree[pitch]
        if abs(diff) != 1:
            continue
        neighbor = degree[pitch] - diff
        if neighbor < 0 or neighbor >= len(scale):
            continue
        return {start: (scale[neighbor], True)}
    return {}



def _apply_appoggiatura(ctx: _Ctx, lead: list[NoteEvent], ornaments: dict[int, tuple[int, bool]]) -> list[NoteEvent]:
    if not ornaments:
        return lead
    eighth, (pitch, accent) = next(iter(ornaments.items()))
    rewritten: list[NoteEvent] = []
    for event in lead:
        if event.midi is None:
            rewritten.append(event)
            continue
        begin = _start16(event, ctx.epb) // 2
        dur = max(1, _dur16(event) // 2)
        if not begin <= eighth < begin + dur:
            rewritten.append(event)
            continue
        if begin < eighth:
            rewritten.extend(_eighth_event(begin, eighth - begin, event.midi, ctx.epb, 1, event.velocity or _MELODY))
        rewritten.extend(_eighth_event(eighth, 1, pitch, ctx.epb, 1, _MELODY_APEX if accent else _MELODY, accent=accent))
        if begin + dur > eighth + 1:
            rewritten.extend(
                _eighth_event(
                    eighth + 1,
                    begin + dur - (eighth + 1),
                    event.midi,
                    ctx.epb,
                    1,
                    event.velocity or _MELODY,
                    accent=False,
                )
            )
    return rewritten


from app.sonify.guitar_patterns import (  # noqa: E402
    BARRIOS_TREMOLO_MIN_BPM,
    C_MAJOR_PCS,
    C_NATURAL_MINOR_PCS,
    _BASS,
    _Ctx,
    _INNER,
    _MELODY,
    _MELODY_APEX,
    _OPENS,
    _PEDAL,
    _SPARSER,
    _apex_eighths,
    _bass_ceiling,
    _choose_bass,
    _choose_inner,
    _clamp,
    _degree,
    _dur16,
    _eighth_event,
    _fit,
    _inner_choices,
    _inner_eighths,
    _melody_at,
    _melody_scale,
    _on_scale,
    _owner,
    _parallel,
    _peak,
    _playable,
    _pool,
    _region_marked,
    _rises,
    _shape_accompaniment,
    _shape_line,
    _sounding_midi,
    _spell16,
    _stamp,
    _start16,
    _study_pair,
    _support_eighths,
    _sustain,
    _swell_band,
    _under_lead,
    _walk,
)
