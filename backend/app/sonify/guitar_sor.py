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
# One micro step inside a galop beat. Four of these equal one dynamic degree.
_GALOP_STEP = 2
_GALOP_FLOOR = 40
# Intro hoof only. The sixteenths stay two and four under their eighth.
# The second beat of that half-bar sits a full degree above the first.
_GALOP_INTRO_INNER = 4
_GALOP_INTRO_RISE = 8
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



def _galop_body_index(ctx: _Ctx, bar: int, patterns: list[str]) -> int:
    """Index of `bar` inside its run of consecutive body bars whose id is galop.

    Intro and outro doors are not counted. A study bar, or any other id, ends
    the run. The first bar of a run is 0.
    """
    index = 0
    cursor = bar - 1
    while cursor >= 0:
        if ctx.kind_at.get(cursor, "phrase") in _PEDAL:
            break
        if _bar_pattern(ctx, cursor, patterns) != "galop":
            break
        index += 1
        cursor -= 1
    return index


def _lead_cap(ctx: _Ctx) -> int:
    return min(ctx.treble_top, ctx.ceiling, 81 - ctx.semitones)


def _chord_tone_under(pcs, upper: int, span: int = 7) -> int | None:
    """Nearest chord tone strictly below `upper`, at most `span` semitones down."""
    classes = {pc % 12 for pc in pcs}
    for note in range(upper - 1, upper - span - 1, -1):
        if note % 12 in classes:
            return note
    return None


def _octave_pair_ok(ctx: _Ctx, upper: int, under: int | None, bass: int | None) -> bool:
    """Rest the pair when no chord tone fits, or a bass still sounding will not share the octave.

    The staccato root is an eighth and has ended before these sixteenths, so the
    cell bass is not in this sonority. `bass` is reserved for a note that is
    still covering the attack.
    """
    del bass
    if under is None:
        return False
    cap = _lead_cap(ctx)
    if not ctx.treble_floor <= upper <= cap or not ctx.treble_floor <= under <= cap:
        return False
    return _playable([upper + ctx.semitones]) and _playable([under + ctx.semitones])


def _pickup_blocks_pair(
    ctx: _Ctx,
    bar: int,
    eighth: int,
    upper: int,
    under: int,
    patterns: list[str] | None,
    bass: int | None,
) -> bool:
    """The body-to-outro pickup is an eighth bass on the last eighth of a boundary bar.

    It sounds through both sixteenths. When that bass cannot share a hand with
    the octave or the chord tone, the pair rests and the price eighth remains.
    The cell root is already in the bass voice, so the prediction has to see
    it. An empty bass line makes `_safe_pickup` fall back to a different pitch
    and can rest a pair the real pickup can still play.
    """
    if patterns is None or eighth % ctx.epb != ctx.epb - 1:
        return False
    if ctx.kind_at.get(bar, "phrase") in _PEDAL:
        return False
    from app.sonify.guitar_patterns import _boundary_bars, _safe_pickup

    if bar not in _boundary_bars(ctx, patterns):
        return False
    attack = NoteEvent(
        bar=bar,
        beat=(eighth % ctx.epb) / 2,
        midi=upper,
        duration_beats=0.25,
        voice=1,
    )
    low: list[NoteEvent] = []
    if bass is not None:
        root_eighth = (eighth // 4) * 4
        low.append(
            NoteEvent(
                bar=bar,
                beat=root_eighth / 2,
                midi=bass,
                duration_beats=0.5,
                voice=3,
                staccato=True,
            )
        )
    pitch = _safe_pickup(ctx, bar, [], [attack], low)
    sounding = pitch + ctx.semitones
    return not (
        _playable([sounding, upper + ctx.semitones])
        and _playable([sounding, under + ctx.semitones])
    )


def _add_octave_pair(
    notes: list[tuple],
    ctx: _Ctx,
    eighth: int,
    price: int,
    bass: int | None,
    pcs,
    *,
    bar: int | None = None,
    patterns: list[str] | None = None,
) -> None:
    upper = price + 12
    under = _chord_tone_under(pcs, upper)
    if not _octave_pair_ok(ctx, upper, under, bass):
        return
    if (
        bar is not None
        and under is not None
        and _pickup_blocks_pair(ctx, bar, eighth, upper, under, patterns, bass)
    ):
        return
    notes.append((float(eighth), 0.5, upper, 1, {}))
    notes.append((float(eighth) + 0.5, 0.5, under, 1, {}))


def _galop1_cell(
    ctx: _Ctx,
    origin: int,
    melody_at,
    bass: int,
    pcs,
    *,
    variant: bool,
    accent: bool,
    bar: int | None = None,
    patterns: list[str] | None = None,
) -> list[tuple]:
    """One 2/4 gallop cell. Offsets are eighths inside the 4/4 bar and may be halves."""
    price0 = melody_at(origin)
    bass_flags = {"staccato": True}
    if accent:
        bass_flags["accent"] = True
    notes: list[tuple] = [
        (float(origin), 1.0, price0, 1, {"staccato": True}),
        (float(origin), 1.0, bass, 3, bass_flags),
    ]
    _add_octave_pair(
        notes, ctx, origin + 1, price0, bass, pcs, bar=bar, patterns=patterns
    )
    if variant:
        notes.append((float(origin + 2), 1.0, melody_at(origin + 2), 1, {"staccato": True}))
        notes.append((float(origin + 3), 1.0, melody_at(origin + 3), 1, {}))
    else:
        price2 = melody_at(origin + 2)
        notes.append((float(origin + 2), 1.0, price2, 1, {"staccato": True}))
        _add_octave_pair(
            notes, ctx, origin + 3, price2, bass, pcs, bar=bar, patterns=patterns
        )
    return notes


def _galop2_twelfth(ctx: _Ctx, root: int, left: int, right: int) -> tuple[int, int] | None:
    """Low root and the perfect twelfth above it, or nothing when the leap will not sit.

    Drop the root by octaves, never the upper note, and never below `guitar_floor`.
    The upper note stays voice 3 and is not folded through the bass window.
    """
    floor = ctx.bass_low
    cursor = root
    while cursor >= floor:
        upper = cursor + 19
        under_melody = upper < left and upper < right
        root_ok = cursor < left and _playable([cursor + ctx.semitones, left + ctx.semitones])
        upper_ok = _playable([upper + ctx.semitones])
        if under_melody and root_ok and upper_ok:
            return cursor, upper
        nxt = cursor - 12
        if nxt < floor:
            break
        cursor = nxt
    return None


def _galop2_cell(ctx: _Ctx, origin: int, melody_at, chord: Chord) -> list[tuple]:
    """Answer cell: price eighth, twelfth in the rest, price eighth, rest.

    When the twelfth cannot sit under the melody, the half keeps one root eighth.
    """
    price0 = melody_at(origin)
    price2 = melody_at(origin + 2)
    root = _choose_bass(chord, 0, price0, ctx.bass_low, ctx.bass_high, ctx.semitones)
    notes: list[tuple] = [
        (float(origin), 1.0, price0, 1, {}),
        (float(origin + 2), 1.0, price2, 1, {}),
    ]
    leap = _galop2_twelfth(ctx, root, price0, price2)
    if leap is None:
        notes.append((float(origin), 1.0, root, 3, {}))
    else:
        low, upper = leap
        notes.append((float(origin), 1.0, low, 3, {"slur_start": True}))
        notes.append((float(origin + 1), 1.0, upper, 3, {"slur_stop": True}))
    return notes


def _emit_galop(
    ctx: _Ctx,
    bar: int,
    figures: list[tuple],
    apex: set[int],
    phrase: Phrase | None,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    epb = ctx.epb
    voices: dict[int, list[NoteEvent]] = {1: [], 2: [], 3: []}
    for offset, length, midi, voice, flags in sorted(figures, key=lambda item: (item[3], item[0])):
        if midi is None or length <= 0:
            continue
        start16 = int(round((bar * epb + offset) * 2))
        dur16 = int(round(length * 2))
        if dur16 <= 0:
            continue
        slot = bar * epb + int(math.floor(offset + 1e-9))
        if voice == 3:
            velocity = _BASS
        else:
            velocity = _note_velocity(slot, 1 if length < 1 else int(round(length)), apex, phrase)
        events = _spell16(
            start16,
            dur16,
            midi,
            epb,
            voice,
            velocity,
            accent=bool(flags.get("accent")),
        )
        if flags.get("staccato") and events:
            events[0] = replace(events[0], staccato=True)
        if events and (flags.get("slur_start") or flags.get("slur_stop")):
            events[0] = replace(
                events[0],
                slur_start=bool(flags.get("slur_start")),
                slur_stop=bool(flags.get("slur_stop")),
            )
        voices[voice].extend(events)
    return voices[1], voices[2], voices[3]


def _render_galop_dance(
    ctx: _Ctx,
    bar: int,
    apex: set[int],
    phrase: Phrase | None,
    patterns: list[str],
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Four bars of the gallop cell, then four of the answer, counted inside the run."""
    index = _galop_body_index(ctx, bar, patterns)
    chord = ctx.chord(bar)
    pcs = list(chord.pitch_classes)

    def melody_at(offset: int) -> int:
        return _melody_at(ctx, bar * ctx.epb + offset)

    figures: list[tuple] = []
    if index % 8 >= 4:
        for origin in (0, 4):
            figures.extend(_galop2_cell(ctx, origin, melody_at, chord))
    else:
        for origin in (0, 4):
            sung = melody_at(origin)
            bass = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
            figures.extend(
                _galop1_cell(
                    ctx,
                    origin,
                    melody_at,
                    bass,
                    pcs,
                    variant=index == 0 and origin == 4,
                    accent=origin == 0,
                    bar=bar,
                    patterns=patterns,
                )
            )
    part_lead, support, low = _emit_galop(ctx, bar, figures, apex, phrase)
    support, low = _shape_accompaniment(ctx, support, low)
    if index % 8 >= 4:
        low = _slur_galop2_bass(low)
        part_lead, low = _contour_galop2(part_lead, low)
    else:
        part_lead, low = _contour_galop1(part_lead, low)
    return part_lead, support, low


def _local_beat(beat: float) -> float:
    """Position inside one packed 2/4 bar. Beat 2.0 of the 4/4 bar is 0."""
    local = round(beat % 2.0, 2)
    if local >= 2.0:
        return 0.0
    return local


def _galop1_parts(beat: float, duration: float = 0.25, *, peak_quarter: int = 3) -> tuple[int, int]:
    """Sixteenth steps inside the beat, then how many quarters sit under the peak."""
    quarter = int(math.floor(beat + 1e-9))
    quarter = min(max(quarter, 0), peak_quarter)
    local = round(beat - quarter, 2)
    if local <= 0.0:
        inner = 0
    elif duration >= 0.49:
        inner = 1
    elif local < 0.7:
        inner = 1
    else:
        inner = 2
    return inner, peak_quarter - quarter


def _galop1_steps(beat: float, duration: float = 0.25, *, peak_quarter: int = 3) -> int:
    """Steps below the written level. The bar rises toward `peak_quarter`.

    Inside one beat the eighth is the weight and the two sixteenths fall away.
    Each later beat sits one step higher, so the hoof grows louder.
    """
    inner, below = _galop1_parts(beat, duration, peak_quarter=peak_quarter)
    return inner + below


def _galop1_heard(
    velocity: int,
    beat: float,
    duration: float,
    *,
    peak_quarter: int = 3,
    inner_step: int = _GALOP_STEP,
    rise_step: int = _GALOP_STEP,
) -> int:
    """Drop each note from the written level. Lift the peak only to clear the floor.

    The softest note is the second sixteenth of the first quarter. A quiet door
    cannot hold a wide rise by dropping alone, so the peak moves up by the
    missing room and the earlier notes keep their places under it.
    """
    inner, below = _galop1_parts(beat, duration, peak_quarter=peak_quarter)
    deepest = peak_quarter * rise_step + 2 * inner_step
    lift = max(0, deepest - (velocity - _GALOP_FLOOR))
    drop = inner * inner_step + below * rise_step
    return max(_GALOP_FLOOR, velocity + lift - drop)


def _contour_galop1(
    lead: list[NoteEvent], low: list[NoteEvent]
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """One written peak for the bar. The last eighth sits on it, and each earlier beat is quieter.

    Measuring from each note's own velocity lets a rising phrase cancel the
    two-step gap inside a beat. The peak is the loudest lead already written.
    """
    written = [
        event.velocity
        for event in lead
        if event.midi is not None and event.velocity is not None
    ]
    if not written:
        return lead, low
    peak = max(written)

    def place(event: NoteEvent) -> NoteEvent:
        if event.midi is None or event.velocity is None:
            return event
        velocity = max(_GALOP_FLOOR, peak - _galop1_steps(event.beat, event.duration_beats) * _GALOP_STEP)
        if velocity == event.velocity:
            return event
        return replace(event, velocity=velocity)

    return [place(event) for event in lead], [place(event) for event in low]


def _galop2_steps(beat: float) -> int:
    """Steps under the bar's written peak.

    The second cell is the arrival, two steps above the first. Inside a cell
    the twelfth sits two steps above the statement and the answering eighth
    sits two steps under that statement.
    """
    second = beat >= 1.99
    local = _local_beat(beat)
    cell = 0 if second else 2
    if local <= 0.0:
        inner = 2
    elif local < 1.0:
        inner = 0
    else:
        inner = 4
    return inner + cell


def _contour_galop2(
    lead: list[NoteEvent], low: list[NoteEvent]
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """One written peak for the bar. The second twelfth sits on it, and the first cell is quieter."""
    written = [
        event.velocity
        for event in lead
        if event.midi is not None and event.velocity is not None
    ]
    if not written:
        return lead, low
    peak = max(written)

    def place(event: NoteEvent) -> NoteEvent:
        if event.midi is None or event.velocity is None:
            return event
        velocity = max(_GALOP_FLOOR, peak - _galop2_steps(event.beat) * _GALOP_STEP)
        if velocity == event.velocity:
            return event
        return replace(event, velocity=velocity)

    return [place(event) for event in lead], [place(event) for event in low]


def _slur_galop2_bass(low: list[NoteEvent]) -> list[NoteEvent]:
    """One slur over the root eighth and the twelfth. The thin root has none.

    `_shape_accompaniment` may replace a note to change its velocity. The slur
    is written on the events that leave that pass, so the flags stay.
    """
    by_beat = {
        round(event.beat, 2): index
        for index, event in enumerate(low)
        if event.midi is not None
    }
    updated = list(low)
    for origin in (0.0, 2.0):
        root_at = by_beat.get(origin)
        upper_at = by_beat.get(round(origin + 0.5, 2))
        if root_at is None or upper_at is None:
            continue
        root = updated[root_at]
        upper = updated[upper_at]
        if root.midi is None or upper.midi is None or upper.midi - root.midi != 19:
            continue
        updated[root_at] = replace(root, slur_start=True, slur_stop=False)
        updated[upper_at] = replace(upper, slur_start=False, slur_stop=True)
    return updated


def _render_galop_bar(
    ctx: _Ctx,
    bar: int,
    apex: set[int],
    phrase: Phrase | None,
    patterns: list[str] | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Galop Op. 32 No. 6. 4/4 alternates the gallop cell with the answer cell."""
    if ctx.kind == "4/4" and ctx.epb >= 8:
        return _render_galop_dance(ctx, bar, apex, phrase, patterns or [])
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



def _contour_mozart_diminution(support: list[NoteEvent], beats: set[float]) -> list[NoteEvent]:
    """Connecting sixteenths fall one step. Structural eighths stay even."""
    if not beats:
        return support
    updated: list[NoteEvent] = []
    for event in support:
        if (
            event.midi is not None
            and event.velocity is not None
            and abs(event.duration_beats - 0.25) < 1e-6
            and round(event.beat, 2) in beats
        ):
            updated.append(_micro_drop(event, 1))
        else:
            updated.append(event)
    return updated


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
    diminutions: set[float] = set()
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
                    gap_beat = (bridge_eighth - start) / 2.0
                    diminutions.add(round(gap_beat, 2))
                    diminutions.add(round(gap_beat + 0.25, 2))
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
                diminutions.add(round(held.beat + 0.25, 2))
                if len(bridge) >= 2:
                    dest = offset / 2.0
                    diminutions.add(round(dest, 2))
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
    support = _contour_mozart_diminution(support, diminutions)
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



def _fit_elegiaque_melody(ctx: _Ctx, patterns: list[str]) -> None:
    """Shift a high Elegiaque melody down an octave only when the whole score fits `treble_floor..69`.

    When every note in the score is at least `treble_floor + 12` (like a held `76`
    or a high phrase `71..81`), shifting the whole score by `-12` keeps every
    interval and rhythm 100% exact while placing the melody in first position
    over the `[48, 47, 43, 41]` march bass. When the score also contains lower
    notes (`< treble_floor + 12`), keep the melody untouched (no compression)
    and let `_elegiaque_bass_pitch` adapt the bass notes that need a closer hand
    position.
    """
    elegy_bars = [
        bar for bar in range(ctx.bars) if _bar_pattern(ctx, bar, patterns) == "elegiaque"
    ]
    if not elegy_bars or not ctx.melody:
        return
    first_pos_top = min(ctx.treble_top, 69 - ctx.semitones)
    floor = ctx.treble_floor
    if all(
        max(ctx.melody[bar * ctx.epb : (bar + 1) * ctx.epb] or [floor]) <= first_pos_top
        for bar in elegy_bars
    ):
        return
    if all(floor <= note - 12 <= first_pos_top for note in ctx.melody):
        ctx.melody = [note - 12 for note in ctx.melody]


def _elegiaque_bass_pitch(
    ctx: _Ctx,
    chord: Chord,
    preferred: int,
    role: str,
    prev: int | None,
    uppers: list[int],
    *,
    need_inner: bool,
) -> int:
    if not uppers:
        return preferred

    def fits(bass: int) -> bool:
        if bass >= min(uppers):
            return False
        if not all(_playable([bass + ctx.semitones, u + ctx.semitones]) for u in uppers):
            return False
        if need_inner:
            return any(
                any(
                    _playable([bass + ctx.semitones, m + ctx.semitones, u + ctx.semitones])
                    for m in range(max(ctx.mid_low, bass + 1), min(ctx.mid_high, u - 1) + 1)
                )
                for u in uppers
            )
        return True

    if fits(preferred):
        return preferred
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    third = _clamp(chord.pitches[1], ctx.bass_low, ctx.bass_high) if len(chord.pitches) > 1 else root
    fifth = _clamp(chord.pitches[2], ctx.bass_low, ctx.bass_high) if len(chord.pitches) > 2 else root
    candidates: list[int] = []
    if role == "step" and prev is not None:
        step = prev
        for _ in range(4):
            step = _step_down(step, ctx.mode, ctx.bass_low, ctx.bass_high)
            if step not in candidates:
                candidates.append(step)
    for note in (root, fifth, third):
        if note not in candidates:
            candidates.append(note)
    for open_pitch in (50, 45, 40):
        written = open_pitch - ctx.semitones
        if ctx.bass_low <= written <= ctx.bass_high and written not in candidates:
            candidates.append(written)
    for note in range(ctx.bass_high, ctx.bass_low - 1, -1):
        if note not in candidates:
            candidates.append(note)
    for cand in candidates:
        if fits(cand):
            return cand
    return preferred


def _contour_elegiaque_march(
    support: list[NoteEvent], low: list[NoteEvent]
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Long notes at the half are heavier than the short eighths. A colliding inner note yields."""
    low = list(low)
    support = list(support)
    for index, event in enumerate(low):
        if event.midi is None or event.velocity is None:
            continue
        if abs(event.duration_beats - 0.5) < 1e-6:
            steps = 2
        elif abs(event.beat) < 1e-6:
            steps = 0
        else:
            steps = 1
        low[index] = _micro_drop(event, steps)
    for index, event in enumerate(support):
        if event.midi is None or event.velocity is None:
            continue
        bass_vel: int | None = None
        for bass in low:
            if bass.midi is None or bass.velocity is None:
                continue
            if bass.beat <= event.beat + 1e-6 < bass.beat + bass.duration_beats:
                bass_vel = bass.velocity
                break
        if bass_vel is not None and bass_vel < event.velocity + _MICRO:
            support[index] = replace(event, velocity=max(_MICRO_FLOOR, bass_vel - _MICRO))
    return support, low


def _render_elegiaque_bar(
    ctx: _Ctx,
    bar: int,
    phrase: Phrase | None,
    descend: bool,
    ornaments: dict[int, tuple[int, bool]] | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
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
    thinner = _SPARSER.get(ctx.band(bar), "mp")
    inner_locals = set(_inner_eighths(ctx.epb, set(ctx.strong), thinner))
    orn_map = ornaments or {}

    def sung_at(eighth: int) -> int:
        if eighth in orn_map:
            return orn_map[eighth][0]
        return _melody_at(ctx, eighth)

    if sustain:
        uppers = [sung_at(start + step) for step in range(ctx.epb)]
        pitch = _elegiaque_bass_pitch(
            ctx, chord, root, "root", prev, uppers, need_inner=bool(inner_locals)
        )
        low.extend(_eighth_event(start, ctx.epb, pitch, ctx.epb, 3, _BASS))
        prev = pitch
    else:
        for local, length, role in _march_grid(ctx):
            if lament:
                preferred = root if prev is None else _step_down(prev, ctx.mode, ctx.bass_low, ctx.bass_high)
            elif role == "fifth":
                preferred = fifth
            elif role == "step":
                preferred = _step_down(root if prev is None else prev, ctx.mode, ctx.bass_low, ctx.bass_high)
            else:
                preferred = root
            span_locals = [step for step in range(local, min(ctx.epb, local + length))]
            uppers = [sung_at(start + step) for step in span_locals]
            has_inner = any(step in inner_locals for step in span_locals)
            pitch = _elegiaque_bass_pitch(
                ctx, chord, preferred, role, prev, uppers, need_inner=has_inner
            )
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
        sung = sung_at(eighth)
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
    support, low = _shape_accompaniment(ctx, support, low)
    if not sustain:
        support, low = _contour_elegiaque_march(support, low)
    return support, low



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


def classic_scale_step(
    ctx: _Ctx,
    pitch: int,
    direction: int,
    *,
    low: int | None = None,
    high: int | None = None,
) -> int:
    """One classical diatonic step. Strong beats stay on the chord tone the passage anchors."""
    floor = ctx.treble_floor if low is None else low
    top = min(ctx.treble_top, ctx.ceiling) if high is None else high
    return _walk(pitch, 1 if direction >= 0 else -1, ctx.mode, floor, top)


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
    _bar_pattern,
    _bass_ceiling,
    _choose_bass,
    _choose_inner,
    _clamp,
    _compress_monotone,
    _degree,
    _dur16,
    _eighth_event,
    _fit,
    _inner_choices,
    _inner_eighths,
    _MICRO,
    _MICRO_FLOOR,
    _melody_at,
    _melody_scale,
    _micro_drop,
    _nearest,
    _note_velocity,
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
    quantize_strong_beats,
)
