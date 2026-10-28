"""J.S. Bach classical guitar counterpoint, dance suites, and Chaconne."""

from __future__ import annotations

from dataclasses import replace
import itertools
import math

from app.sonify.chords import Chord
from app.sonify.model import NoteEvent, Phrase, Score
from app.sonify.phrasing import MIN_RISE, swell
from app.sonify.quantize import C_MAJOR_PCS, C_NATURAL_MINOR_PCS

# Default velocity constants evaluated at function definition time
_MELODY = 64
_MELODY_APEX = 72
_BASS = 56
_INNER = 46
_MORDENT_SPAN = 4
BARRIOS_TREMOLO_MIN_BPM = 90
# Calm splits here. Rally still uses the 1.4% Barrios mark, and only the 1D
# fingerprint also asks whether the line is lively.
BACH_NARROW_SPAN = 0.008
_BACH_WIDE_SPAN = 0.014
_BACH_LIVELY = 0.35


def _bach_hold_ratio(ctx: _Ctx, phrases: list[Phrase]) -> float:
    if not phrases:
        return 0.0
    holds = sum(1 for phrase in phrases if _has_hold(ctx.melody, phrase))
    return holds / len(phrases)


def _bach_narrow_or_held(ctx: _Ctx, phrases: list[Phrase]) -> bool:
    return _bach_hold_ratio(ctx, phrases) >= 0.3 or ctx.rel_span < BACH_NARROW_SPAN


def _bach_wide(ctx: _Ctx) -> bool:
    return ctx.rel_span >= _BACH_WIDE_SPAN


def _bach_lively(ctx: _Ctx, bars: list[int]) -> bool:
    return min(_raw_activity(ctx, bars), _melody_activity(ctx, bars)) >= _BACH_LIVELY


def _bach_daily_fingerprint(ctx: _Ctx) -> bool:
    """Framed 1D: 34 bars, 96 BPM, 4/4. One pattern, and no suite row."""
    return _framed(ctx) and ctx.bars == 34 and ctx.bpm == 96 and ctx.kind == "4/4"


def _bach_unframed_primary(ctx: _Ctx, mood: str | None) -> str:
    """The six-pattern scheduler. Prelude, Allemande, and Courante stay framed."""
    if ctx.kind == "3/4" or ctx.bpm <= 72:
        if mood == "selloff" and ctx.rel_span >= 0.016 and not _has_contrast_section(ctx):
            return "bach_chaconne"
        return "bach_sarabande"
    if mood == "volatile":
        return "bach_fuga"
    if mood == "selloff":
        return "bach_chaconne"
    if ctx.kind == "6/8":
        return "bach_gigue"
    if mood == "calm":
        return "bach_gavotte"
    return "bach_bourree"


def _bach_daily_pattern(ctx: _Ctx, phrases: list[Phrase], bars: list[int], mood: str | None) -> str:
    """Section 3.2. Gavotte-on-a-wide-rally lives only on this fingerprint."""
    if mood == "volatile":
        return "bach_fuga"
    if mood == "selloff":
        return "bach_chaconne"
    if mood == "calm":
        return "bach_prelude" if _bach_narrow_or_held(ctx, phrases) else "bach_allemande"
    if not _bach_wide(ctx):
        return "bach_bourree"
    if _bach_lively(ctx, bars):
        return "bach_courante"
    return "bach_gavotte"


def _bach_finale_primary(mood: str | None) -> str:
    """4/4 finale. A wide rally stays Bourrée; the only guest is the Fugue."""
    if mood == "volatile":
        return "bach_fuga"
    if mood == "selloff":
        return "bach_chaconne"
    if mood == "calm":
        return "bach_gavotte"
    return "bach_bourree"


def _bach_framed_primary(ctx: _Ctx, phrases: list[Phrase], bars: list[int], mood: str | None) -> str:
    """Section 3.3. Lively does not promote Courante except on the 1D fingerprint."""
    if _bach_daily_fingerprint(ctx):
        return _bach_daily_pattern(ctx, phrases, bars, mood)
    # A long 6/8 scherzo can share the numeric pedal of a finale. The finale
    # menu is the 4/4 row; 3/4 and 6/8 keep their own primaries.
    if _is_suite_finale(ctx) and ctx.kind == "4/4":
        return _bach_finale_primary(mood)
    if ctx.kind == "6/8":
        if mood == "volatile":
            return "bach_fuga"
        if mood == "selloff":
            return "bach_chaconne"
        if mood == "calm":
            return "bach_courante"
        return "bach_gigue"
    if ctx.kind == "4/4":
        if mood == "volatile":
            return "bach_fuga"
        if mood == "selloff":
            return "bach_chaconne"
        if mood == "calm":
            return "bach_prelude" if _bach_narrow_or_held(ctx, phrases) else "bach_allemande"
        if _bach_wide(ctx):
            return "bach_bourree"
        return "bach_allemande"
    if ctx.kind == "3/4" or ctx.bpm <= 72:
        return "bach_sarabande"
    return "bach_bourree"


def _bach_primary(ctx: _Ctx, phrases: list[Phrase], bars: list[int], mood: str | None) -> str:
    """One Bach dance for a body, a section, or a single phrase."""
    if not bars and not phrases and mood is None and ctx.kind not in {"4/4", "3/4", "6/8"}:
        return "bach_bourree"
    if not _framed(ctx):
        return _bach_unframed_primary(ctx, mood)
    return _bach_framed_primary(ctx, phrases, bars, mood)



def _bach_contrast(ctx: _Ctx, primary: str, mood: str | None) -> str:
    """Trio and bridge: the palette guest, then the dance returns.

    Prelude, Allemande, and Courante take their own guest. The 6/8 branch
    below would otherwise send a calm Courante to Bourrée.
    """
    if primary == "bach_prelude":
        return "bach_allemande"
    if primary == "bach_allemande":
        return "bach_courante"
    if primary == "bach_courante":
        return "bach_gigue"
    if ctx.kind == "6/8" or primary == "bach_gigue":
        return "bach_bourree" if mood == "calm" else "bach_fuga"
    if ctx.kind == "3/4" or primary == "bach_sarabande":
        return "bach_chaconne"
    if primary in {"bach_bourree", "bach_gavotte"}:
        return "bach_fuga"
    if primary in {"bach_fuga", "bach_chaconne"}:
        return "bach_bourree" if mood == "rally" else "bach_gavotte"
    return "bach_bourree"


def _bach_palette(ctx: _Ctx, primary: str, mood: str | None) -> tuple[str, ...]:
    """Framed suite row. `palette[2]` is heard only from the fourth region on.

    The opening pattern is already chosen. Later regions walk this row,
    including movements that have a bridge or a trio. A Prelude opening does
    not reprise itself at the close. The finale never invites Prelude, so the
    last movement of a suite is another dance. Unframed scores never call this.
    """
    if _is_suite_finale(ctx) and ctx.kind == "4/4":
        rows = {
            "bach_gavotte": ("bach_gavotte", "bach_bourree"),
            "bach_bourree": ("bach_bourree", "bach_fuga"),
            "bach_fuga": ("bach_fuga", "bach_allemande"),
            "bach_chaconne": ("bach_chaconne", "bach_fuga"),
        }
        return rows.get(primary, ("bach_bourree", "bach_fuga"))
    if ctx.kind == "6/8":
        rows = {
            "bach_gigue": ("bach_gigue", "bach_courante"),
            "bach_courante": ("bach_courante", "bach_gigue"),
            "bach_fuga": ("bach_fuga", "bach_courante"),
            "bach_chaconne": ("bach_chaconne", "bach_gavotte"),
        }
        return rows.get(primary, ("bach_gigue", "bach_courante"))
    if ctx.kind == "4/4":
        rows = {
            "bach_prelude": ("bach_prelude", "bach_allemande", "bach_bourree"),
            "bach_allemande": ("bach_allemande", "bach_courante", "bach_gavotte"),
            "bach_bourree": ("bach_bourree", "bach_gavotte", "bach_fuga"),
            "bach_fuga": ("bach_fuga", "bach_allemande", "bach_bourree"),
            "bach_chaconne": ("bach_chaconne", "bach_sarabande", "bach_fuga"),
        }
        return rows.get(primary, (primary, "bach_allemande"))
    if ctx.kind == "3/4" or ctx.bpm <= 72:
        if mood == "volatile":
            return ("bach_sarabande", "bach_courante")
        if mood == "selloff":
            return ("bach_sarabande", "bach_chaconne")
        return ("bach_sarabande", "bach_prelude")
    return (primary, "bach_allemande")



def _bach_bass_high(ctx: _Ctx) -> int:
    """Walking counterpoint stays inside the bass register, E2 through F3."""
    return min(ctx.bass_high, 53 - ctx.semitones)



def _bach_lead_high(ctx: _Ctx) -> int:
    return min(ctx.treble_top, 81 - ctx.semitones)



def _bach_opens(ctx: _Ctx) -> list[int]:
    high = _bach_bass_high(ctx)
    return [
        pitch - ctx.semitones
        for pitch in (40, 45, 50)
        if ctx.bass_low <= pitch - ctx.semitones <= high
    ]



def _quarter_ok(pitches: list[int]) -> bool:
    """The sixteenth-scale rule: a tight group must share one hand position."""
    ordered = sorted(set(pitches))
    if len(ordered) < 2:
        return True
    if any(abs(left - right) > 4 for left, right in zip(ordered, ordered[1:])):
        return True
    return _position_ok(ordered)



def _scale_cell(ctx: _Ctx, pitch: int, count: int) -> list[int]:
    """One quarter of a Baroque run: steps or a turn, and it fits one hand position."""
    if count <= 0:
        return []
    low = ctx.treble_floor
    high = _bach_lead_high(ctx)
    mode = ctx.mode
    if not low <= pitch <= high or not _on_scale(pitch, mode):
        pitch = _nearest(pitch, mode, low, high)
    below = _walk(pitch, -1, mode, low, high)
    above = _walk(pitch, 1, mode, low, high)
    below2 = _walk(below, -1, mode, low, high)
    cells: list[list[int]] = []

    def ascend(steps: int) -> list[int]:
        notes: list[int] = []
        cursor = pitch
        for _ in range(steps):
            nxt = _walk(cursor, -1, mode, low, high)
            if nxt == cursor:
                break
            notes.append(nxt)
            cursor = nxt
        notes.reverse()
        return notes + [pitch]

    rising = ascend(max(0, count - 1))
    if len(rising) < count:
        rising = [rising[0]] * (count - len(rising)) + rising
    cells.append(rising[-count:])
    if below != pitch:
        turn = []
        while len(turn) < count - 1:
            turn.append(below if len(turn) % 2 == 0 else pitch)
        cells.append(turn + [pitch])
        if below2 != below:
            cells.append(([below2, below, below, pitch] + [pitch] * count)[: count - 1] + [pitch])
            cells.append(([below2, below2, below, pitch] + [pitch] * count)[: count - 1] + [pitch])
    if above != pitch:
        turn = []
        while len(turn) < count - 1:
            turn.append(above if len(turn) % 2 == 0 else pitch)
        cells.append(turn + [pitch])
    # A leap wider than a hand cluster is legal, then the line settles on the note.
    cursor = pitch
    for _ in range(6):
        cursor = _walk(cursor, -1, mode, low, high)
        if abs(cursor - pitch) > 4:
            cells.append([cursor] * (count - 1) + [pitch])
            break
    cells.append([pitch] * count)

    def rank(cell: list[int]) -> tuple[int, int, int]:
        steps = [abs(right - left) for left, right in zip(cell, cell[1:])]
        leaps = sum(1 for step in steps if step > 2)
        repeats = sum(1 for step in steps if step == 0)
        motion = sum(1 for step in steps if 0 < step <= 2)
        return (leaps, repeats, -motion)

    valid = [cell for cell in cells if len(cell) == count and cell[-1] == pitch and _quarter_ok(cell)]
    if not valid:
        return [pitch] * count
    return min(valid, key=rank)



def _fitting_scale(ctx: _Ctx, start_slot: int, target: int, count: int) -> list[int]:
    """Diatonic sixteenths that land on `target` and satisfy the scale-position rule.

    Each quarter is its own cell. The last cell arrives on `target`; earlier
    cells end a step below the next one, so a long run still climbs.
    """
    if count <= 0:
        return []
    low = ctx.treble_floor
    high = _bach_lead_high(ctx)
    mode = ctx.mode
    if not low <= target <= high or not _on_scale(target, mode):
        target = _nearest(target, mode, low, high)
    spans: list[int] = []
    index = 0
    while index < count:
        room = 4 - ((start_slot + index) % 4)
        take = min(room, count - index)
        spans.append(take)
        index += take
    cells: list[list[int]] = []
    arrival = target
    for length in reversed(spans):
        cell = _scale_cell(ctx, arrival, length)
        cells.append(cell)
        arrival = _walk(cell[0], -1, mode, low, high)
    cells.reverse()
    line = [pitch for cell in cells for pitch in cell]
    line[-1] = target
    groups: dict[int, list[int]] = {}
    for note_index, pitch in enumerate(line):
        groups.setdefault((start_slot + note_index) // 4, []).append(pitch)
    if all(_quarter_ok(group) for group in groups.values()):
        return line
    return [target] * count



def _lead_during(lead: list[NoteEvent], eighth: int, length: int, epb: int) -> list[int]:
    found: list[int] = []
    for offset in range(max(1, length)):
        pitch = _sounding_midi(lead, eighth + offset, epb)
        if pitch is not None and pitch not in found:
            found.append(pitch)
    return found



def _hold_at(events: list[NoteEvent], eighth: int, epb: int) -> int:
    pitch = _sounding_midi(events, eighth, epb)
    if pitch is None:
        return 0
    left = eighth
    while left > 0 and _sounding_midi(events, left - 1, epb) == pitch:
        left -= 1
    right = eighth + 1
    while _sounding_midi(events, right, epb) == pitch:
        right += 1
    return right - left



def _covers_upper(ctx: _Ctx, note: int, uppers: list[int]) -> bool:
    if any(note >= upper for upper in uppers):
        return False
    return all(_playable([note + ctx.semitones, upper + ctx.semitones]) for upper in uppers)



def _bach_bass(
    ctx: _Ctx,
    chord: Chord,
    uppers: list[int],
    *,
    previous: int | None,
    direction: int,
    strong: bool,
    degree: int = 0,
) -> int:
    """A bass tone under `uppers`. Strong beats snap to root, third, or fifth."""
    ceiling = min(uppers) if uppers else _bach_lead_high(ctx)
    high = min(_bach_bass_high(ctx), ceiling - 1)
    if high < ctx.bass_low:
        high = ctx.bass_low

    def ok(note: int) -> bool:
        if not ctx.bass_low <= note <= high:
            return False
        if uppers and not _covers_upper(ctx, note, uppers):
            return False
        return True

    degrees = []
    for index in (degree, 0, 2, 1):
        if index < len(chord.pitches) and index not in degrees:
            degrees.append(index)
    pcs = [chord.pitches[index] % 12 for index in degrees]
    tones = [note for note in range(ctx.bass_low, high + 1) if note % 12 in pcs and ok(note)]
    playable = [note for note in range(ctx.bass_low, high + 1) if ok(note)]
    opens = [note for note in _bach_opens(ctx) if ok(note)]

    if not strong:
        step = 1 if direction >= 0 else -1
        anchor = previous if previous is not None else (tones[0] if tones else ctx.bass_low)
        cursor = anchor
        for _ in range(7):
            nxt = _walk(cursor, step, ctx.mode, ctx.bass_low, high)
            if nxt == cursor:
                break
            if ok(nxt) and ((step > 0 and nxt > anchor) or (step < 0 and nxt < anchor)):
                return nxt
            cursor = nxt
        aimed = [note for note in playable if (step > 0 and note > anchor) or (step < 0 and note < anchor)]
        if aimed:
            return min(aimed) if step > 0 else max(aimed)

    if previous is None or direction == 0 or strong:
        prefer = chord.pitches[min(degree, len(chord.pitches) - 1)] % 12
        preferred = [note for note in tones if note % 12 == prefer]
        open_preferred = [note for note in preferred if note in opens]
        if previous is not None and direction > 0:
            above = [note for note in (preferred or tones or playable) if note > previous]
            if above:
                return min(above)
            # The window has no chord tone above. Hold the nearest one instead of
            # leaping back to the open string and reversing the subject's rise.
            held = [note for note in (preferred or tones or playable) if note <= previous]
            if held:
                return max(held)
        if previous is not None and direction < 0:
            below = [note for note in (preferred or tones or playable) if note < previous]
            if below:
                return max(below)
            held = [note for note in (preferred or tones or playable) if note >= previous]
            if held:
                return min(held)
        # Enter on the lowest chord tone so a rising answer still has room.
        # Open strings stay in the pool when that degree is not in the window.
        pool = preferred or [note for note in opens if note % 12 in pcs] or opens or tones or playable
        if pool:
            return pool[0]
    if previous is not None and ok(previous):
        return previous
    return opens[0] if opens else ctx.bass_low



def _bach_keep_bass_below(ctx: _Ctx, lead: list[NoteEvent], low: list[NoteEvent]) -> list[NoteEvent]:
    """Drop a Bach bass note that crosses the melody onto an open string under it."""
    fixed: list[NoteEvent] = []
    for event in low:
        if event.midi is None:
            fixed.append(event)
            continue
        when = _start16(event, ctx.epb)
        dur = _dur16(event)
        highs: list[int] = []
        for note in lead:
            if note.midi is None:
                continue
            begin = _start16(note, ctx.epb)
            if begin < when + dur and begin + _dur16(note) > when:
                highs.append(note.midi)
        if not highs or (
            event.midi < min(highs) and all(_playable([event.midi + ctx.semitones, high + ctx.semitones]) for high in highs)
        ):
            fixed.append(event)
            continue
        ceiling = min(highs)
        replacement = None
        for note in _bach_opens(ctx):
            if note < ceiling and all(_playable([note + ctx.semitones, high + ctx.semitones]) for high in highs):
                replacement = note
                break
        if replacement is None:
            continue
        fixed.append(replace(event, midi=replacement))
    return fixed



def _bach_lag_bar(ctx: _Ctx, bar: int) -> int:
    if bar >= 2 and ctx.kind_at.get(bar - 2, "phrase") not in _PEDAL:
        return bar - 2
    if bar >= 1 and ctx.kind_at.get(bar - 1, "phrase") not in _PEDAL:
        return bar - 1
    return bar



def _fuga_motif(ctx: _Ctx, src_bar: int) -> list[tuple[int, int, int]]:
    """(offset, length, direction) of the lagged subject, 1:1 and never retrograde.

    A repeated pitch is direction 0. A flat bar stays one held value; nothing
    is invented when the subject has a single run.
    """
    epb = ctx.epb
    start = src_bar * epb
    runs = _runs(ctx.melody, start, min(len(ctx.melody), start + epb))
    if not runs:
        return [(0, epb, 0)]
    motif: list[tuple[int, int, int]] = []
    previous: int | None = None
    for eighth, length, midi in runs:
        if previous is None or midi == previous:
            direction = 0
        elif midi > previous:
            direction = 1
        else:
            direction = -1
        motif.append((eighth - start, length, direction))
        previous = midi
    return motif



def _fuga_bass_ok(ctx: _Ctx, note: int, sung: list[int]) -> bool:
    high = _bach_bass_high(ctx)
    if sung:
        high = min(high, min(sung) - 1)
    if not ctx.bass_low <= note <= high:
        return False
    if not sung:
        return True
    return all(_playable([note + ctx.semitones, upper + ctx.semitones]) for upper in sung)



def _fuga_pitch(
    ctx: _Ctx,
    bar: int,
    sung: list[int],
    *,
    previous: int | None,
    direction: int,
    strong: bool,
    degree: int = 0,
) -> int:
    """Retarget one subject step. A held step stays put; a strong beat snaps to the chord."""
    chord = ctx.chord(bar)
    if direction == 0:
        pcs = {pitch % 12 for pitch in chord.pitches}
        if strong and previous is not None and previous % 12 in pcs and _fuga_bass_ok(ctx, previous, sung):
            return previous
        if not strong and previous is not None and _fuga_bass_ok(ctx, previous, sung):
            return previous
        if strong and previous is not None:
            high = _bach_bass_high(ctx)
            if sung:
                high = min(high, min(sung) - 1)
            tones = [
                note
                for note in range(ctx.bass_low, high + 1)
                if note % 12 in pcs and _fuga_bass_ok(ctx, note, sung)
            ]
            if tones:
                return min(tones, key=lambda note: (abs(note - previous), note))
        return _bach_bass(
            ctx, chord, sung, previous=previous, direction=0, strong=True, degree=degree
        )
    return _bach_bass(
        ctx,
        chord,
        sung,
        previous=previous,
        direction=direction,
        strong=strong,
        degree=degree,
    )



def _treble_step(ctx: _Ctx, pitch: int, steps: int) -> int:
    high = _bach_lead_high(ctx)
    stepped = _walk(pitch, steps, ctx.mode, ctx.treble_floor, high)
    if stepped == pitch and steps:
        nudged = pitch + (1 if steps > 0 else -1)
        if ctx.treble_floor <= nudged <= high:
            return nudged
    return max(ctx.treble_floor, min(high, stepped))



def _approach_eighths(ctx: _Ctx, target: int, count: int) -> list[int]:
    """Scale steps that rise or fall into the next downbeat."""
    high = _bach_lead_high(ctx)
    if not ctx.treble_floor <= target <= high or not _on_scale(target, ctx.mode):
        target = _nearest(target, ctx.mode, ctx.treble_floor, high)
    notes: list[int] = []
    cursor = target
    for _ in range(count):
        nxt = _walk(cursor, -1, ctx.mode, ctx.treble_floor, high)
        if nxt == cursor:
            break
        notes.append(nxt)
        cursor = nxt
    notes.reverse()
    while len(notes) < count:
        notes.insert(0, notes[0] if notes else target)
    return notes[-count:]



def _compose_fuga_bass(ctx: _Ctx, bar: int, lead: list[NoteEvent]) -> list[NoteEvent]:
    """Voice 3 answers with the subject from two bars earlier, under `lead`.

    The soprano may already be a scale. The bass still follows `_fuga_motif`
    of the lagged bar, one step at a time, never retrograde.
    """
    epb = ctx.epb
    start = bar * epb
    src = _bach_lag_bar(ctx, bar)
    low: list[NoteEvent] = []

    def sing(offset: int, length: int, direction: int, previous: int | None) -> int:
        length = max(1, min(length, epb - offset))
        sung = _lead_during(lead, start + offset, length, epb) or [_melody_at(ctx, start + offset)]
        pitch = _fuga_pitch(
            ctx,
            bar,
            sung,
            previous=previous,
            direction=direction,
            strong=offset in ctx.strong,
        )
        low.extend(_eighth_event(start + offset, length, pitch, epb, 3, _BASS))
        return pitch

    if src == bar:
        half = max(1, epb // 2)
        uppers = _lead_during(lead, start, half, epb) or [_melody_at(ctx, start)]
        root = _fuga_pitch(ctx, bar, uppers, previous=None, direction=0, strong=True)
        low.extend(_eighth_event(start, half, root, epb, 3, _BASS))
        motif = [(offset, length, direction) for offset, length, direction in _fuga_motif(ctx, bar) if offset < half]
        moving = len(motif) > 1 or any(direction != 0 for _offset, _length, direction in motif)
        if not moving:
            rest = epb - half
            sung = _lead_during(lead, start + half, rest, epb) or uppers
            held = _fuga_pitch(ctx, bar, sung, previous=root, direction=0, strong=True)
            low.extend(_eighth_event(start + half, rest, held, epb, 3, _BASS))
        else:
            previous = root
            for index, (offset, length, direction) in enumerate(motif):
                dest = half + offset
                if dest >= epb:
                    break
                nxt = motif[index + 1][0] if index + 1 < len(motif) else half
                previous = sing(dest, min(length, nxt - offset), direction, previous)
    else:
        motif = _fuga_motif(ctx, src)
        previous = None
        for index, (offset, length, direction) in enumerate(motif):
            if offset >= epb:
                continue
            nxt = motif[index + 1][0] if index + 1 < len(motif) else epb
            previous = sing(offset, min(length, nxt - offset), direction, previous)
    return low


def _fuga_bass_under_lead(ctx: _Ctx, bar: int, lead: list[NoteEvent]) -> list[NoteEvent]:
    """Rebuild the lagged subject after a scale replaces the soprano of `bar`."""
    low = _compose_fuga_bass(ctx, bar, lead)
    _support, low = _shape_accompaniment(ctx, [], low)
    if _bach_lag_bar(ctx, bar) == bar and low:
        low = _soften_attack(low, bar * ctx.epb, ctx.epb, amount=8)
    return low


def _render_bach_fuga_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Soprano sings the price now. The bass answers two bars later, 1:1, on this chord."""
    epb = ctx.epb
    start = bar * epb
    lead = _sustain(ctx.melody, start, start + epb, epb, apex, phrase=phrase)
    low = _compose_fuga_bass(ctx, bar, lead)
    support: list[NoteEvent] = []
    strong_offsets = (0, 4) if ctx.kind == "4/4" else tuple(offset for offset in ctx.strong if offset < epb)
    for offset in strong_offsets:
        eighth = start + offset
        if _hold_at(lead, eighth, epb) < 2:
            continue
        sung = _sounding_midi(lead, eighth, epb)
        bass = _sounding_midi(low, eighth, epb)
        if sung is None or bass is None or not bass < sung:
            continue
        tone = _choose_inner(ctx.chord(bar), sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if tone is None:
            continue
        support.extend(_eighth_event(eighth, 1, tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    if _bach_lag_bar(ctx, bar) == bar and low:
        low = _soften_attack(low, start, epb, amount=8)
    return lead, support, low



def _bourree_cells(ctx: _Ctx) -> list[tuple[int, int]]:
    if ctx.kind == "6/8":
        return [(0, 3), (3, 3)]
    if ctx.kind == "4/4":
        return [(0, 4), (4, 4)]
    return [(0, ctx.epb)]



def _render_bach_bourree_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Bourrée: the treble is pure price action. Bass quarters answer eighths; two eighths answer a hold."""
    epb = ctx.epb
    start = bar * epb
    lead = _sustain(ctx.melody, start, start + epb, epb, apex, phrase=phrase)
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []

    def place(
        origin: int,
        offset: int,
        length: int,
        degree: int,
        *,
        previous: int | None,
        direction: int,
        strong: bool,
        staccato: bool,
    ) -> int:
        eighth = start + origin + offset
        sung = _lead_during(lead, eighth, length, epb) or [_melody_at(ctx, eighth)]
        pitch = _bach_bass(
            ctx,
            ctx.chord(bar),
            sung,
            previous=previous,
            direction=direction,
            strong=strong,
            degree=degree,
        )
        events = _eighth_event(eighth, length, pitch, epb, 3, _BASS)
        if staccato:
            events = _stamp(events, staccato=True)
        low.extend(events)
        return pitch

    def walk_pair(origin: int, span: int, cell_index: int, cursor: int) -> None:
        if origin + span < epb:
            goal_bar = bar
            goal_eighth = start + origin + span
            goal_degree = 0 if cell_index % 2 else 2
        else:
            goal_bar = min(ctx.bars - 1, bar + 1)
            goal_eighth = goal_bar * epb
            goal_degree = 0
        goal_lead = [_melody_at(ctx, min(len(ctx.melody) - 1, goal_eighth))]
        goal = _bach_bass(
            ctx, ctx.chord(goal_bar), goal_lead, previous=None, direction=0, strong=True, degree=goal_degree
        )
        for step, offset in enumerate((2, 3)):
            direction = 1 if goal > cursor else -1 if goal < cursor else (1 if step == 0 else -1)
            cursor = place(
                origin,
                offset,
                1,
                goal_degree,
                previous=cursor,
                direction=direction,
                strong=False,
                staccato=step == 0,
            )

    for cell_index, (origin, span) in enumerate(_bourree_cells(ctx)):
        degree = 0 if cell_index == 0 else 2
        if span >= 4 and origin + 3 < epb:
            lead_moves_downbeat = _melody_at(ctx, start + origin) != _melody_at(ctx, start + origin + 1)
            lead_holds_upbeat = _melody_at(ctx, start + origin + 2) == _melody_at(ctx, start + origin + 3)
            downbeat = place(origin, 0, 2, degree, previous=None, direction=0, strong=True, staccato=False)
            # A held quarter (this upbeat, or the downbeat before it) takes the two-note anacrusis.
            if lead_holds_upbeat or not lead_moves_downbeat:
                walk_pair(origin, span, cell_index, downbeat)
            else:
                place(
                    origin,
                    2,
                    2,
                    2 if cell_index == 0 else 0,
                    previous=downbeat,
                    direction=0,
                    strong=True,
                    staccato=True,
                )
        else:
            pitches = [_melody_at(ctx, start + origin + offset) for offset in range(max(span, 1))]
            if pitches and len(set(pitches)) == 1 and span > 1:
                cursor = None
                for offset in range(span):
                    cursor = place(
                        origin,
                        offset,
                        1,
                        degree,
                        previous=cursor,
                        direction=0 if cursor is None else 1,
                        strong=offset == 0,
                        staccato=offset > 0,
                    )
            else:
                place(
                    origin,
                    0,
                    max(1, span),
                    degree,
                    previous=None,
                    direction=0,
                    strong=True,
                    staccato=cell_index > 0,
                )
        eighth = start + origin
        sung_now = _sounding_midi(lead, eighth, epb)
        bass_now = _sounding_midi(low, eighth, epb)
        if sung_now is None or bass_now is None:
            continue
        tone = _parallel(sung_now, bass_now, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, None)
        if tone is None:
            tone = _choose_inner(ctx.chord(bar), sung_now, bass_now, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if tone is not None:
            support.extend(_eighth_event(eighth, 1, tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    return lead, support, low



def _gavotte_sung(ctx: _Ctx, eighth: int) -> int:
    return max(ctx.treble_floor, min(_bach_lead_high(ctx), _melody_at(ctx, eighth)))


def _render_bach_gavotte_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Gavotte: quarter, staccato quarter, then four eighths in parallel thirds or sixths.

    In 4/4 the four eighths are the price at hooks 4 and 5. Hooks 6 and 7 stay
    the price when this is the last bar, or when the next downbeat matches hook
    4. They step into the next downbeat only when that bar exists and differs.
    The old four-note scale is not used.
    """
    epb = ctx.epb
    start = bar * epb
    if ctx.kind == "4/4":
        heads = (0, 2)
        tail = 4
        tail_len = 4
    elif epb >= 6:
        heads = (0, 2)
        tail = 4
        tail_len = epb - 4
    else:
        heads = (0,)
        tail = 2
        tail_len = max(1, epb - 2)
    lead: list[NoteEvent] = []
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []
    for index, offset in enumerate(heads):
        if offset >= epb:
            continue
        length = 1 if offset + 2 > epb or (tail <= offset + 1) else min(2, epb - offset, tail - offset)
        if length <= 0:
            continue
        sung = _melody_at(ctx, start + offset)
        sung = max(ctx.treble_floor, min(_bach_lead_high(ctx), sung))
        velocity = _note_velocity(start + offset, length, apex, phrase)
        lead_events = _eighth_event(start + offset, length, sung, epb, 1, velocity)
        uppers = [sung]
        degree = 0 if index % 2 == 0 else 2
        bass = _bach_bass(ctx, ctx.chord(bar), uppers, previous=None, direction=0, strong=True, degree=degree)
        bass_events = _eighth_event(start + offset, length, bass, epb, 3, _BASS)
        if offset == 2:
            lead_events = _stamp(lead_events, staccato=True)
            bass_events = _stamp(bass_events, staccato=True)
        lead.extend(lead_events)
        low.extend(bass_events)
        tone = _choose_inner(ctx.chord(bar), sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if tone is not None:
            support.extend(_eighth_event(start + offset, length, tone, epb, 2, _INNER))
    if ctx.kind == "4/4":
        line = [_gavotte_sung(ctx, start + 4), _gavotte_sung(ctx, start + 5)]
        if bar + 1 < ctx.bars:
            target = _melody_at(ctx, min(len(ctx.melody) - 1, (bar + 1) * epb))
            if target == _melody_at(ctx, start + 4):
                line.extend((_gavotte_sung(ctx, start + 6), _gavotte_sung(ctx, start + 7)))
            else:
                line.extend(_approach_eighths(ctx, target, 2))
        else:
            line.extend((_gavotte_sung(ctx, start + 6), _gavotte_sung(ctx, start + 7)))
    else:
        target = _melody_at(
            ctx, min(len(ctx.melody) - 1, (bar + 1) * epb if bar + 1 < ctx.bars else start)
        )
        line = _approach_eighths(ctx, target, tail_len)
    long_bass = _gavotte_tail_bass(ctx, ctx.chord(bar), line)
    low.extend(_eighth_event(start + tail, tail_len, long_bass, epb, 3, _BASS))
    previous_inner: int | None = None
    for index, pitch in enumerate(line):
        eighth = start + tail + index
        velocity = _note_velocity(eighth, 1, apex, phrase)
        lead.extend(_eighth_event(eighth, 1, pitch, epb, 1, velocity))
        tone = _parallel(pitch, long_bass, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, previous_inner)
        if tone is not None and _playable([long_bass + ctx.semitones, tone + ctx.semitones, pitch + ctx.semitones]):
            previous_inner = tone
            support.extend(_eighth_event(eighth, 1, tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    return lead, support, low



def _ornament_neighbor(ctx: _Ctx, principal: int) -> int:
    """Upper neighbor when the pair fits one position; otherwise a lower one or a leap."""
    low = ctx.treble_floor
    high = _bach_lead_high(ctx)
    for step in (1, -1, 2, -2):
        neighbor = _treble_step(ctx, principal, step)
        if neighbor != principal and low <= neighbor <= high and _quarter_ok([principal, neighbor]):
            return neighbor
    cursor = principal
    for _ in range(6):
        cursor = _walk(cursor, -1, ctx.mode, low, high)
        if cursor != principal and _quarter_ok([principal, cursor]):
            return cursor
    return principal



def _gavotte_tail_bass(ctx: _Ctx, chord: Chord, line: list[int]) -> int:
    """Highest root, fifth, or third that still leaves a third or sixth under every eighth."""
    if not line:
        return ctx.bass_low
    floor = min(line)

    def supports(bass: int) -> bool:
        if bass >= floor:
            return False
        if not all(_playable([bass + ctx.semitones, pitch + ctx.semitones]) for pitch in line):
            return False
        for pitch in line:
            tone = _parallel(pitch, bass, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, None)
            if tone is None or not _playable([bass + ctx.semitones, tone + ctx.semitones, pitch + ctx.semitones]):
                return False
        return True

    found: list[int] = []
    for degree in (0, 2, 1):
        if degree >= len(chord.pitches):
            continue
        pc = chord.pitches[degree] % 12
        for note in range(_bach_bass_high(ctx), ctx.bass_low - 1, -1):
            if note % 12 == pc and note not in found:
                found.append(note)
    for note in found:
        if supports(note):
            return note
    return _bach_bass(ctx, chord, line, previous=None, direction=0, strong=True, degree=0)



def _mordent_events(ctx: _Ctx, eighth: int, principal: int, epb: int, velocity: int) -> list[NoteEvent]:
    neighbor = _ornament_neighbor(ctx, principal)
    base = eighth * 2
    events: list[NoteEvent] = []
    events.extend(_spell16(base, 1, principal, epb, 1, velocity, accent=True))
    events.extend(_spell16(base + 1, 1, neighbor, epb, 1, velocity))
    events.extend(_spell16(base + 2, 2, principal, epb, 1, velocity))
    return events



def _sarabande_pitch(ctx: _Ctx, eighth: int) -> int:
    return max(ctx.treble_floor, min(_bach_lead_high(ctx), _melody_at(ctx, eighth)))



def _sarabande_ornament(ctx: _Ctx, bar: int, start: int, epb: int, apex: set[int], phrase: Phrase | None) -> bool:
    """Mordent the first bar of a phrase, an apex bar, and bar 0 of a unit fixture."""
    if bar == 0 or (phrase is not None and phrase.start == start):
        return True
    if any(item.start == start for item in ctx.phrases):
        return True
    return any(start <= eighth < start + epb for eighth in apex)



def _sarabande_passes(ctx: _Ctx, bar: int, start: int, epb: int) -> bool:
    """A passing scale only when the bar opens, or the chord or phrase is about to change."""
    if bar == 0:
        return True
    if bar + 1 >= ctx.bars:
        return False
    if ctx.chord(bar + 1) != ctx.chord(bar):
        return True
    return (start + epb) in {item.start for item in ctx.phrases}



def _render_bach_sarabande_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Beat 2 rolls the chord. The last beat passes, or sings the price, into the next bar."""
    epb = ctx.epb
    start = bar * epb
    accent = 3 if ctx.kind == "6/8" else 2
    passing = 6 if ctx.kind == "4/4" else (5 if ctx.kind == "6/8" else 4)
    accent = min(accent, epb - 1)
    passing = min(max(passing, accent + 2), epb)
    melody = _sarabande_pitch(ctx, start)
    beat_two = _sarabande_pitch(ctx, start + min(accent, epb - 1))
    beat_two_next = _sarabande_pitch(ctx, start + min(accent + 1, epb - 1))
    lead: list[NoteEvent] = []
    cursor = start
    while cursor < start + accent:
        pitch = _sarabande_pitch(ctx, cursor)
        nxt = cursor + 1
        while nxt < start + accent and _sarabande_pitch(ctx, nxt) == pitch:
            nxt += 1
        lead.extend(_eighth_event(cursor, nxt - cursor, pitch, epb, 1, _note_velocity(cursor, nxt - cursor, apex, phrase)))
        cursor = nxt
    ornament = _sarabande_ornament(ctx, bar, start, epb, apex, phrase)
    if ornament:
        lead.extend(_mordent_events(ctx, start + accent, beat_two, epb, _note_velocity(start + accent, 2, apex, phrase)))
        voiced = accent + 2
    else:
        lead.extend(_eighth_event(start + accent, 1, beat_two, epb, 1, _note_velocity(start + accent, 1, apex, phrase)))
        if accent + 1 < passing:
            lead.extend(
                _eighth_event(
                    start + accent + 1,
                    1,
                    beat_two_next,
                    epb,
                    1,
                    _note_velocity(start + accent + 1, 1, apex, phrase),
                )
            )
        voiced = min(passing, accent + 2)
    while voiced < passing:
        pitch = _sarabande_pitch(ctx, start + voiced)
        lead.extend(
            _eighth_event(start + voiced, 1, pitch, epb, 1, _note_velocity(start + voiced, 1, apex, phrase))
        )
        voiced += 1
    scale: list[int] = []
    if _sarabande_passes(ctx, bar, start, epb):
        passing_count = max(2, min(4, (epb - passing) * 2))
        target_eighth = (bar + 1) * epb if bar + 1 < ctx.bars else start
        target = _melody_at(ctx, min(len(ctx.melody) - 1, target_eighth))
        scale = _fitting_scale(ctx, passing * 2, target, passing_count)
        for index, pitch in enumerate(scale):
            lead.extend(_spell16((start + passing) * 2 + index, 1, pitch, epb, 1, _MELODY))
    else:
        offset = passing
        while offset < epb:
            pitch = _sarabande_pitch(ctx, start + offset)
            nxt = offset + 1
            while nxt < epb and _sarabande_pitch(ctx, start + nxt) == pitch:
                nxt += 1
            lead.extend(
                _eighth_event(
                    start + offset,
                    nxt - offset,
                    pitch,
                    epb,
                    1,
                    _note_velocity(start + offset, nxt - offset, apex, phrase),
                )
            )
            offset = nxt
    opening = min(2, accent) if accent else epb
    root = _bach_bass(ctx, ctx.chord(bar), [melody], previous=None, direction=0, strong=True, degree=0)
    low: list[NoteEvent] = []
    low.extend(_eighth_event(start, opening, root, epb, 3, _BASS))
    neighbor = _ornament_neighbor(ctx, beat_two) if ornament else beat_two_next
    gravity = _bach_bass(
        ctx,
        ctx.chord(bar),
        [beat_two, neighbor],
        previous=root,
        direction=-1,
        strong=True,
        degree=2,
    )
    gravity_len = min(2, max(1, passing - accent))
    low.extend(_spell16((start + accent) * 2, gravity_len * 2, gravity, epb, 3, _BASS, accent=True))
    if passing > accent + gravity_len:
        low.extend(_eighth_event(start + accent + gravity_len, passing - accent - gravity_len, gravity, epb, 3, _BASS))
    tail = scale or [beat_two, beat_two_next]
    step = _bach_bass(ctx, ctx.chord(bar), tail, previous=gravity, direction=-1, strong=False, degree=0)
    low.extend(_eighth_event(start + passing, max(1, epb - passing), step, epb, 3, _BASS))
    support: list[NoteEvent] = []
    ceiling = min(beat_two, neighbor)
    tone = _parallel(ceiling, gravity, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, None)
    if tone is None:
        tone = _choose_inner(ctx.chord(bar), ceiling, gravity, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
    sounding = [gravity + ctx.semitones, beat_two + ctx.semitones]
    if neighbor != beat_two:
        sounding.append(neighbor + ctx.semitones)
    if tone is not None and _playable([*sounding, tone + ctx.semitones]) and gravity < tone < ceiling:
        support_len = max(1, gravity_len * 2 - 1)
        support.extend(
            _spell16((start + accent) * 2 + 1, support_len, tone, epb, 2, _INNER, accent=True)
        )
    support, low = _shape_accompaniment(ctx, support, low)
    low = _punch(low, start + accent, epb, amount=8)
    support = _punch(support, start + accent, epb, amount=8)
    lead = _punch(lead, start + accent, epb, amount=8)
    return lead, support, low



def _gigue_plan(ctx: _Ctx) -> dict:
    if ctx.epb <= 6:
        return {
            "down": (0, 3),
            "pickup": (2, 5),
            "inner": (1, 2, 4, 5),
            "bass": ((0, 3), (3, 2), (5, 1)),
            "scale_at": 6,
            "scale_count": 6,
        }
    return {
        "down": (0, 4),
        "pickup": (3, 7),
        "inner": (1, 2, 5, 6),
        "bass": ((0, 4), (4, 3), (7, 1)),
        "scale_at": 8,
        "scale_count": 8,
    }



def _render_bach_gigue_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Compound gigue: broken chords across the strings, and a scale when the line rises."""
    epb = ctx.epb
    start = bar * epb
    plan = _gigue_plan(ctx)
    rising = _rises(phrase)
    scale: list[int] = []
    if rising:
        target_eighth = (bar + 1) * epb if bar + 1 < ctx.bars else start
        target = _melody_at(ctx, min(len(ctx.melody) - 1, target_eighth))
        scale = _fitting_scale(ctx, plan["scale_at"], target, plan["scale_count"])
    scale_eighths = {plan["scale_at"] // 2 + index // 2 for index in range(len(scale))}
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    melody = _melody_at(ctx, start)
    bass_pitch = _bach_bass(ctx, ctx.chord(bar), [melody], previous=None, direction=0, strong=True, degree=0)
    for offset, length in plan["bass"]:
        if offset >= epb:
            continue
        length = min(length, epb - offset)
        degree = 0 if offset == 0 else 2
        sung = [melody]
        if scale and offset >= plan["scale_at"] // 2:
            sung = scale
        pitch = bass_pitch if offset == 0 else _bach_bass(
            ctx, ctx.chord(bar), sung, previous=bass_pitch, direction=1 if offset == plan["bass"][-1][0] else -1, strong=offset in plan["down"], degree=degree
        )
        events = _eighth_event(start + offset, length, pitch, epb, 3, _BASS)
        if offset in plan["down"]:
            events = _stamp(events, accent=True)
        low.extend(events)
        bass_pitch = pitch
    lows = [tone for tone in _inner_choices(ctx.chord(bar), max(melody, 67), bass_pitch if bass_pitch < melody else ctx.bass_low, ctx.mid_low, ctx.mid_high, ctx.semitones, False)]
    if not lows:
        fallback = _choose_inner(ctx.chord(bar), max(melody, 67), min(bass_pitch, 50), ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        lows = [fallback] if fallback is not None else []
    for offset in range(epb):
        if offset in scale_eighths and scale:
            continue
        eighth = start + offset
        sung = _melody_at(ctx, eighth)
        sung = max(ctx.treble_floor, min(_bach_lead_high(ctx), sung))
        if offset in plan["pickup"]:
            sung = _treble_step(ctx, sung, 2)
        bass_now = _sounding_midi(low, eighth, epb) or bass_pitch
        if offset in plan["down"] or offset in plan["pickup"]:
            if sung <= bass_now:
                sung = _treble_step(ctx, max(bass_now + 1, ctx.treble_floor), 1)
            events = _eighth_event(eighth, 1, sung, epb, 1, _note_velocity(eighth, 1, apex, phrase))
            if offset in plan["down"]:
                events = _stamp(events, accent=True)
            lead.extend(events)
        if offset in plan["inner"] and lows:
            ceiling = sung if offset in plan["down"] or offset in plan["pickup"] else _bach_lead_high(ctx)
            choices = [tone for tone in lows if bass_now < tone < ceiling]
            if not choices:
                continue
            tone = choices[0] if (offset % 2 == 1) else choices[-1]
            if not _playable([bass_now + ctx.semitones, tone + ctx.semitones] + ([ceiling + ctx.semitones] if ceiling < _bach_lead_high(ctx) else [])):
                playable = [
                    candidate
                    for candidate in choices
                    if _playable([bass_now + ctx.semitones, candidate + ctx.semitones])
                ]
                if not playable:
                    continue
                tone = playable[0]
            support.extend(_eighth_event(eighth, 1, tone, epb, 2, _INNER))
    for index, pitch in enumerate(scale):
        slot = plan["scale_at"] + index
        lead.extend(
            _spell16(start * 2 + slot, 1, pitch, epb, 1, _MELODY_APEX if index == 0 else _MELODY, accent=index == 0)
        )
    support, low = _shape_accompaniment(ctx, support, low)
    for offset in plan["down"]:
        lead = _punch(lead, start + offset, epb, amount=6)
        low = _punch(low, start + offset, epb, amount=6)
    return lead, support, low



def _bariolage_pair(ctx: _Ctx, chord: Chord, bass: int, lead: int | None) -> tuple[int | None, int | None]:
    ceiling = lead if lead is not None else ctx.mid_high + 1
    if ceiling <= bass + 1:
        ceiling = bass + 12
    raw = _inner_choices(chord, ceiling, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)

    def fits(note: int) -> bool:
        if not bass < note < ceiling:
            return False
        sounding = [bass + ctx.semitones, note + ctx.semitones]
        if lead is not None and note < lead:
            sounding.append(lead + ctx.semitones)
        return _playable(sounding)

    choices = [note for note in raw if fits(note)]
    opens = [
        note
        for note in (pitch - ctx.semitones for pitch in (50, 55, 59))
        if fits(note) and ctx.mid_low <= note <= ctx.mid_high
    ]
    upper = opens[-1] if opens else (choices[-1] if choices else None)
    lower = choices[0] if choices else upper
    if lower is not None and upper is not None and lower > upper:
        lower, upper = upper, lower
    return lower, upper



def _chaconne_bass_slots(ctx: _Ctx) -> list[int]:
    if ctx.kind == "3/4":
        return [0, 4]
    if ctx.kind == "6/8":
        return [0, 6]
    return [0, 8]



def _chaconne_beats(ctx: _Ctx, eighth: int) -> tuple[int, int]:
    """The two price-action eighths of one quarter, with a step when the second repeats."""
    beat_melody = max(ctx.treble_floor, min(_bach_lead_high(ctx), _melody_at(ctx, eighth)))
    second_at = min(len(ctx.melody) - 1, eighth + 1) if ctx.melody else eighth
    beat_second = max(ctx.treble_floor, min(_bach_lead_high(ctx), _melody_at(ctx, second_at)))
    if beat_second == beat_melody:
        beat_second = _treble_step(ctx, beat_melody, 1)
    return beat_melody, beat_second



def _render_bach_chaconne_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Chaconne ground in the bass, bariolage sixteenths above, and a breakout scale."""
    epb = ctx.epb
    start = bar * epb
    total = epb * 2
    breakout = bool(_rises(phrase) and ctx.band(bar) in {"mf", "f"})
    scale_at = 8 if epb >= 8 else 4
    scale_count = total - scale_at
    scale: list[int] = []
    if breakout and scale_count >= 4:
        target_eighth = (bar + 1) * epb if bar + 1 < ctx.bars else start
        target = _melody_at(ctx, min(len(ctx.melody) - 1, target_eighth))
        scale = _fitting_scale(ctx, scale_at, target, scale_count)
    slots = [slot for slot in _chaconne_bass_slots(ctx) if slot < total]
    beats = {
        quarter: _chaconne_beats(ctx, start + quarter // 2)
        for quarter in range(0, total, 4)
        if not (scale and quarter >= scale_at)
    }
    bass_at: dict[int, int] = {}
    previous: int | None = None
    for index, slot in enumerate(slots):
        nxt = slots[index + 1] if index + 1 < len(slots) else total
        if scale and slot >= scale_at:
            uppers = list(scale)
        else:
            uppers = [
                pitch
                for quarter, pair in beats.items()
                if slot <= quarter < nxt
                for pitch in pair
            ]
            if not uppers:
                uppers = list(next(iter(beats.values()))) if beats else [ctx.treble_floor]
        pitch = _bach_bass(
            ctx,
            ctx.chord(bar),
            uppers,
            previous=previous,
            direction=0 if previous is None else -1,
            strong=True,
            degree=0 if previous is None else 2,
        )
        if previous is not None and pitch > previous:
            lower = _bach_bass(
                ctx, ctx.chord(bar), uppers, previous=previous, direction=-1, strong=False, degree=0
            )
            if lower <= previous:
                pitch = lower
        bass_at[slot] = pitch
        previous = pitch
    low: list[NoteEvent] = []
    for index, slot in enumerate(slots):
        nxt = slots[index + 1] if index + 1 < len(slots) else total
        length = max(1, min(8, nxt - slot))
        low.extend(_spell16(start * 2 + slot, length, bass_at[slot], epb, 3, _BASS))

    def bass_under(slot: int) -> int:
        earlier = [point for point in slots if point <= slot]
        return bass_at[earlier[-1]] if earlier else next(iter(bass_at.values()))

    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    for quarter in range(0, total, 4):
        if scale and quarter >= scale_at:
            continue
        bass = bass_under(quarter)
        beat_melody, beat_second = beats.get(quarter, _chaconne_beats(ctx, start + quarter // 2))
        lower, upper = _bariolage_pair(ctx, ctx.chord(bar), bass, beat_melody)
        base = start * 2 + quarter
        if quarter in slots:
            lead.extend(_spell16(base, 2, beat_melody, epb, 1, _note_velocity(start + quarter // 2, 1, apex, phrase)))
            if lower is not None:
                support.extend(_spell16(base + 1, 1, lower, epb, 2, _INNER))
            if upper is not None:
                support.extend(_spell16(base + 2, 1, upper, epb, 2, _INNER))
            top = beat_second if _quarter_ok([beat_melody, beat_second]) else beat_melody
            if not _playable([bass + ctx.semitones, top + ctx.semitones]):
                top = beat_melody
            lead.extend(_spell16(base + 3, 1, top, epb, 1, _MELODY))
        else:
            first = beat_melody
            second = beat_second if _quarter_ok([beat_melody, beat_second]) else beat_melody
            if not _playable([bass + ctx.semitones, first + ctx.semitones]):
                first = max(first, bass + 7)
            if not _playable([bass + ctx.semitones, second + ctx.semitones]):
                second = first
            lead.extend(_spell16(base, 1, first, epb, 1, _MELODY))
            lead.extend(_spell16(base + 2, 1, second, epb, 1, _MELODY))
            if upper is not None:
                support.extend(_spell16(base + 1, 1, upper, epb, 2, _INNER))
            if lower is not None:
                support.extend(_spell16(base + 3, 1, lower, epb, 2, _INNER))
    for index, pitch in enumerate(scale):
        lead.extend(
            _spell16(
                start * 2 + scale_at + index,
                1,
                pitch,
                epb,
                1,
                _MELODY_APEX if index == len(scale) - 1 else _MELODY,
                accent=index == len(scale) - 1,
            )
        )
    support, low = _shape_accompaniment(ctx, support, low)
    return lead, support, low


_MELODIC_MINOR_PCS = frozenset({0, 2, 3, 5, 7, 9, 11})


def bach_scale_classes(ctx: _Ctx, impulse_direction: str, approaching_tonic: bool) -> frozenset[int]:
    """Diatonic tirata. Minor follows the wave, not each one-eighth retreat.

    An upward wave stays on melodic minor (raised 6 and 7), including a short
    retreat. A downward wave stays on natural minor, and raises 6 and 7 only
    while the line is approaching the tonic.
    """
    if ctx.mode != "minor":
        return frozenset(C_MAJOR_PCS)
    if impulse_direction == "up" or approaching_tonic:
        return _MELODIC_MINOR_PCS
    return frozenset(C_NATURAL_MINOR_PCS)


def _bach_step_in(pitch: int, direction: int, classes: frozenset[int], low: int, high: int) -> int:
    step = 1 if direction >= 0 else -1
    cursor = pitch
    for _ in range(12):
        cursor += step
        if cursor < low or cursor > high:
            return pitch
        if cursor % 12 in classes:
            return cursor
    return pitch


def bach_scale_step(
    ctx: _Ctx,
    pitch: int,
    direction: int,
    *,
    impulse_direction: str = "up",
    approaching_tonic: bool = False,
    low: int | None = None,
    high: int | None = None,
) -> int:
    """One diatonic step of a Bach tirata, inside the compass passed by the scale line."""
    floor = ctx.treble_floor if low is None else low
    top = min(ctx.treble_top, ctx.ceiling) if high is None else high
    classes = bach_scale_classes(ctx, impulse_direction, approaching_tonic)
    return _bach_step_in(pitch, direction, classes, floor, top)


def _bach_phrase_at(ctx: _Ctx, bar: int) -> Phrase | None:
    eighth = bar * ctx.epb
    for phrase in ctx.phrases:
        if phrase.start <= eighth < phrase.end:
            return phrase
    return None


def _bach_passing_offset(ctx: _Ctx) -> int:
    epb = ctx.epb
    accent = 3 if ctx.kind == "6/8" else 2
    passing = 6 if ctx.kind == "4/4" else (5 if ctx.kind == "6/8" else 4)
    accent = min(accent, epb - 1)
    return min(max(passing, accent + 2), epb)


def bach_group2_window(ctx: _Ctx, bar: int, pattern: str) -> tuple[int, int] | None:
    """Inclusive eighths of the group-2 second-half window, whether or not it is drawn."""
    if pattern not in {"bach_gigue", "bach_chaconne", "bach_sarabande"}:
        return None
    epb = ctx.epb
    start = bar * epb
    if pattern == "bach_gigue":
        lo = _gigue_plan(ctx)["scale_at"] // 2
    elif pattern == "bach_chaconne":
        lo = (8 if epb >= 8 else 4) // 2
    else:
        lo = _bach_passing_offset(ctx)
    if lo >= epb:
        return None
    return start + lo, start + epb - 1


def bach_group2_intrinsic_eighths(ctx: _Ctx, bar: int, pattern: str) -> set[int]:
    """Eighths of the scale figuration this bar already draws. Empty when it draws none."""
    window = bach_group2_window(ctx, bar, pattern)
    if window is None:
        return set()
    phrase = _bach_phrase_at(ctx, bar)
    if pattern == "bach_gigue":
        drawn = _rises(phrase)
    elif pattern == "bach_chaconne":
        epb = ctx.epb
        scale_at = 8 if epb >= 8 else 4
        drawn = bool(_rises(phrase) and ctx.band(bar) in {"mf", "f"} and epb * 2 - scale_at >= 4)
    else:
        drawn = _sarabande_passes(ctx, bar, bar * ctx.epb, ctx.epb)
    if not drawn:
        return set()
    lo, hi = window
    return set(range(lo, hi + 1))


def _sounding_ok(ctx: _Ctx, pitches: list[int]) -> bool:
    cleaned = [pitch for pitch in pitches if pitch is not None]
    if not cleaned:
        return True
    return _playable([pitch + ctx.semitones for pitch in cleaned])


def _clamp_lead_pitch(ctx: _Ctx, pitch: int) -> int:
    return max(ctx.treble_floor, min(_bach_lead_high(ctx), pitch))


def _lead_at(ctx: _Ctx, eighth: int) -> int:
    return _clamp_lead_pitch(ctx, _melody_at(ctx, eighth))


def _inner_between(
    ctx: _Ctx,
    chord: Chord,
    lead: int,
    bass: int,
    previous: int | None = None,
) -> int | None:
    """A third or sixth under the lead, then any playable inner tone."""
    if not bass < lead:
        return None
    low = max(ctx.mid_low, bass + 1)
    high = min(ctx.mid_high, lead - 1, 65)
    if low > high:
        return None
    tone = _parallel(lead, bass, ctx.mode, low, high, ctx.semitones, previous)
    if (
        tone is not None
        and bass < tone < lead
        and low <= tone <= high
        and _sounding_ok(ctx, [bass, tone, lead])
    ):
        return tone
    tone = _choose_inner(chord, lead, bass, low, high, ctx.semitones, False)
    if tone is not None and bass < tone < lead and tone <= high and _sounding_ok(ctx, [bass, tone, lead]):
        return tone
    for note in range(high, low - 1, -1):
        if _sounding_ok(ctx, [bass, note, lead]):
            return note
    return None


def _bass_under_leads(ctx: _Ctx, chord: Chord, leads: list[int], degree: int) -> int:
    """Chord tone under every lead. Open strings win when a high leap needs them."""
    ceiling = min(leads) if leads else _bach_lead_high(ctx)
    high = min(_bach_bass_high(ctx), ceiling - 1)
    if high < ctx.bass_low:
        high = ctx.bass_low
    pcs: list[int] = []
    for index in (degree, 0, 2, 1):
        if index < len(chord.pitches):
            pc = chord.pitches[index] % 12
            if pc not in pcs:
                pcs.append(pc)
    opens = set(_bach_opens(ctx))

    def fits(note: int) -> bool:
        if not ctx.bass_low <= note <= high or any(note >= lead for lead in leads):
            return False
        return all(_sounding_ok(ctx, [note, lead]) for lead in leads)

    found = [note for note in range(ctx.bass_low, high + 1) if note % 12 in pcs and fits(note)]
    if not found:
        found = [note for note in range(ctx.bass_low, high + 1) if fits(note)]
    if not found:
        return _bach_bass(ctx, chord, leads or [ceiling], previous=None, direction=0, strong=True, degree=degree)
    prefer = chord.pitches[min(degree, len(chord.pitches) - 1)] % 12
    found.sort(key=lambda note: (note % 12 != prefer, note not in opens, note))
    return found[0]


def _chord_third(chord: Chord) -> int | None:
    if len(chord.pitches) < 2:
        return None
    return chord.pitches[1] % 12


def _prelude_neighbor(ctx: _Ctx, current: int, nxt: int) -> int:
    """One diatonic step. A moving price keeps the neighbor inside the interval."""
    if nxt == current:
        step = _treble_step(ctx, current, 1)
        if step == current:
            step = _treble_step(ctx, current, -1)
        return step
    direction = 1 if nxt > current else -1
    step = _treble_step(ctx, current, direction)
    if direction > 0 and current < step <= nxt:
        return step
    if direction < 0 and nxt <= step < current:
        return step
    if direction > 0 and current < nxt < step:
        return nxt
    if direction < 0 and step < nxt < current:
        return nxt
    if (step - current) * direction > 0:
        return step
    return nxt


def _fits_bass(ctx: _Ctx, bass: int, leads: list[int]) -> bool:
    if any(bass >= lead for lead in leads):
        return False
    return all(_sounding_ok(ctx, [bass, lead]) for lead in leads)


def _ordered_basses(ctx: _Ctx, chord: Chord, degrees: tuple[int, ...], ceiling: int) -> list[int]:
    """Preferred degrees from high to low, then any lower pitch that can still fit."""
    high = min(_bach_bass_high(ctx), ceiling - 1)
    if high < ctx.bass_low:
        return []
    ordered: list[int] = []
    seen: set[int] = set()
    for degree in degrees:
        if degree >= len(chord.pitches):
            continue
        pc = chord.pitches[degree] % 12
        for note in range(high, ctx.bass_low - 1, -1):
            if note % 12 == pc and note not in seen:
                seen.add(note)
                ordered.append(note)
    for note in range(high, ctx.bass_low - 1, -1):
        if note not in seen:
            ordered.append(note)
    return ordered


def _place_third(ctx: _Ctx, chord: Chord, bass: int, leads: list[int]) -> int | None:
    """One chord third under every lead, or nothing when the hand cannot hold it."""
    third = _chord_third(chord)
    if third is None or not leads:
        return None
    floor = max(ctx.mid_low, bass + 1, 50)
    ceiling = min(ctx.mid_high, 65, min(leads) - 1)
    if floor > ceiling:
        return None
    for note in range(ceiling, floor - 1, -1):
        if note % 12 != third:
            continue
        if all(_sounding_ok(ctx, [bass, note, lead]) for lead in leads):
            return note
    return None


def _degree_notes(ctx: _Ctx, chord: Chord, degree: int, ceiling: int) -> list[int]:
    if degree >= len(chord.pitches):
        return []
    high = min(_bach_bass_high(ctx), ceiling - 1)
    if high < ctx.bass_low:
        return []
    pc = chord.pitches[degree] % 12
    return [note for note in range(high, ctx.bass_low - 1, -1) if note % 12 == pc]


def _third_already(chord: Chord, bass: int, prices: list[int]) -> bool:
    third = _chord_third(chord)
    return third is None or third in {bass % 12, *(pitch % 12 for pitch in prices)}


def _select_bass(
    ctx: _Ctx,
    chord: Chord,
    degrees: tuple[int, ...],
    prices: list[int],
    sounding: list[int],
    *,
    want_third: bool,
) -> tuple[int, int | None]:
    """Keep the on-beat prices. Lower the bass until the hand fits.

    Degrees are tried in order. A later degree is used only when no note of an
    earlier degree fits under the lead. Within one degree the bass drops until
    the chord third can sit between it and the lead.
    """
    ceiling = min(sounding) if sounding else _bach_lead_high(ctx)
    seen: set[int] = set()
    for degree in degrees:
        notes = _degree_notes(ctx, chord, degree, ceiling)
        seen.update(notes)
        fallback: int | None = None
        for bass in notes:
            if not _fits_bass(ctx, bass, sounding):
                continue
            if fallback is None:
                fallback = bass
            if not want_third or _third_already(chord, bass, prices):
                return bass, None
            tone = _place_third(ctx, chord, bass, sounding)
            if tone is not None:
                return bass, tone
        if fallback is not None:
            return fallback, None
    for bass in _ordered_basses(ctx, chord, (), ceiling):
        if bass in seen or not _fits_bass(ctx, bass, sounding):
            continue
        if not want_third or _third_already(chord, bass, prices):
            return bass, None
        tone = _place_third(ctx, chord, bass, sounding)
        if tone is not None:
            return bass, tone
        return bass, None
    return ctx.bass_low, None


def _softer_than_price(
    support: list[NoteEvent], lead: list[NoteEvent], epb: int
) -> list[NoteEvent]:
    """The inner note stays under the price that sounds with it."""
    softened: list[NoteEvent] = []
    for event in support:
        if event.midi is None or event.velocity is None:
            softened.append(event)
            continue
        when = _start16(event, epb)
        heard = [
            note.velocity
            for note in lead
            if note.midi is not None
            and note.velocity is not None
            and _start16(note, epb) <= when < _start16(note, epb) + _dur16(note)
        ]
        if heard and event.velocity >= min(heard):
            event = replace(event, velocity=max(40, min(heard) - 1))
        softened.append(event)
    return softened


def _prelude_halves(ctx: _Ctx) -> list[tuple[int, int]]:
    """`(origin, eighths)` for each half bar. 3/4 and 6/8 keep the second bass on eighth 3."""
    epb = ctx.epb
    if ctx.kind in {"3/4", "6/8"} or (ctx.kind != "4/4" and epb < 8):
        mid = min(3, epb)
    else:
        mid = min(4, epb)
    halves = [(0, mid)] if mid > 0 else []
    if mid < epb:
        halves.append((mid, epb - mid))
    return halves


def _render_bach_prelude_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Two voices. Each price eighth is the price plus one diatonic neighbor.

    The bass attacks once per half bar and rings through it. Voice 1 may attack
    on that same sixteenth. Voice 2 is at most one sustained note, and only when
    the bass and the prices of that half do not already include the chord third.
    """
    epb = ctx.epb
    start = bar * epb
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    chord = ctx.chord(bar)
    for index, (origin, span) in enumerate(_prelude_halves(ctx)):
        prices: list[int] = []
        neighbors: list[int] = []
        for step in range(span):
            eighth = start + origin + step
            price = _melody_at(ctx, eighth)
            neighbor = _prelude_neighbor(ctx, price, _melody_at(ctx, eighth + 1))
            prices.append(price)
            neighbors.append(neighbor)
            velocity = _note_velocity(eighth, 1, apex, phrase)
            slot = eighth * 2
            lead.extend(_spell16(slot, 1, price, epb, 1, velocity))
            lead.extend(_spell16(slot + 1, 1, neighbor, epb, 1, velocity))
        sounding = [*prices, *neighbors]
        degrees = (0,) if index == 0 else (2, 1)
        bass, tone = _select_bass(ctx, chord, degrees, prices, sounding, want_third=True)
        low.extend(_eighth_event(start + origin, span, bass, epb, 3, _BASS))
        if tone is not None:
            support.extend(_eighth_event(start + origin, span, tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    support = _softer_than_price(support, lead, epb)
    return lead, support, low


def _allemande_passes(ctx: _Ctx, bar: int, start: int, epb: int) -> bool:
    """Opening bar, or the chord or the phrase changes on the next bar."""
    if bar == 0:
        return True
    if bar + 1 >= ctx.bars:
        return False
    if ctx.chord(bar + 1) != ctx.chord(bar):
        return True
    return (start + epb) in {item.start for item in ctx.phrases}


def _allemande_bass_plan(ctx: _Ctx, passes: bool) -> list[tuple[int, int, int]]:
    """`(offset, degree, eighths)` for the structural bass, already clear of a pickup."""
    kind = ctx.kind
    epb = ctx.epb
    pickup = epb - 2 if passes else None
    if kind == "6/8":
        points = [(0, 0), (3, 2)]
    else:
        points = [(0, 0), (4, 2)]
    if passes and kind == "3/4":
        points = [(0, 0)]
    plan: list[tuple[int, int, int]] = []
    for index, (offset, degree) in enumerate(points):
        if offset >= epb:
            continue
        nxt = points[index + 1][0] if index + 1 < len(points) else epb
        if passes and kind == "3/4" and offset == 0:
            duration = 2
        elif passes and kind == "4/4" and offset == 4:
            duration = 2
        elif passes and kind == "6/8" and offset == 3:
            duration = 1
        else:
            limit = nxt
            if pickup is not None:
                limit = min(limit, pickup)
            duration = max(1, limit - offset)
        plan.append((offset, degree, min(duration, epb - offset)))
    return plan


def _allemande_support_plan(ctx: _Ctx, passes: bool) -> list[tuple[int, int]]:
    """Support enters one eighth after the bass. A half-bar pickup drops the late one."""
    kind = ctx.kind
    epb = ctx.epb
    pickup = epb - 2 if passes else None
    if kind == "6/8":
        points = [(1, 2), (4, 2)]
    elif kind == "3/4":
        points = [(1, 2), (5, 1)]
    else:
        points = [(1, 2), (5, 2)]
    if passes and kind == "4/4":
        points = [(1, 2), (5, 1)]
    elif passes and kind == "3/4":
        points = [(1, 2)]
    elif passes and kind == "6/8":
        points = [(1, 2)]
    plan: list[tuple[int, int]] = []
    for offset, duration in points:
        if offset >= epb or (pickup is not None and offset >= pickup):
            continue
        if pickup is not None:
            duration = min(duration, pickup - offset)
        if duration > 0:
            plan.append((offset, duration))
    return plan


def _allemande_walk_ok(ctx: _Ctx, passes: bool, offset: int, duration: int) -> bool:
    """The second half of a structural beat. A pickup owns the last two eighths."""
    walk_at = offset + 1
    if duration < 2 or walk_at >= ctx.epb:
        return False
    if passes and ctx.kind == "3/4":
        return False
    if passes and ctx.kind == "4/4" and offset == 4:
        return False
    if passes and ctx.kind == "6/8" and offset == 3:
        return False
    if passes and walk_at >= ctx.epb - 2:
        return False
    return True


def _walk_bass(ctx: _Ctx, previous: int, ceiling: int) -> int | None:
    high = min(_bach_bass_high(ctx), ceiling - 1)
    for direction in (1, -1):
        nxt = _walk(previous, direction, ctx.mode, ctx.bass_low, high)
        if nxt != previous and nxt < ceiling and _sounding_ok(ctx, [nxt, ceiling]):
            return nxt
    return None


def _render_bach_allemande_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Style brisé in eighths, with a four-sixteenth pickup and no staccato.

    The scheduler only seats this dance in 4/4. 3/4 still stresses eighth 4 and
    6/8 still stresses eighth 3, so a forced call does not borrow the other meter.
    """
    epb = ctx.epb
    start = bar * epb
    passes = _allemande_passes(ctx, bar, start, epb)
    lead = _sustain(ctx.melody, start, start + epb, epb, apex, phrase=phrase)
    if passes:
        pickup = start + epb - 2
        lead = _cut_before(lead, pickup, epb)
        target_eighth = (bar + 1) * epb if bar + 1 < ctx.bars else start
        target = _lead_at(ctx, min(len(ctx.melody) - 1, target_eighth))
        scale = _fitting_scale(ctx, (epb - 2) * 2, target, 4)
        for index, pitch in enumerate(scale):
            lead.extend(_spell16(pickup * 2 + index, 1, pitch, epb, 1, _MELODY))
    chord = ctx.chord(bar)
    low: list[NoteEvent] = []
    for offset, degree, duration in _allemande_bass_plan(ctx, passes):
        eighth = start + offset
        sung = _lead_during(lead, eighth, duration, epb) or [_lead_at(ctx, eighth)]
        bass = _bass_under_leads(ctx, chord, sung, degree)
        walk = None
        if _allemande_walk_ok(ctx, passes, offset, duration) and _hold_at(lead, eighth, epb) >= 2:
            ceiling = _sounding_midi(lead, eighth + 1, epb) or _lead_at(ctx, eighth + 1)
            walk = _walk_bass(ctx, bass, ceiling)
        if walk is None:
            low.extend(_eighth_event(eighth, duration, bass, epb, 3, _BASS))
            continue
        low.extend(_eighth_event(eighth, 1, bass, epb, 3, _BASS))
        low.extend(_eighth_event(eighth + 1, duration - 1, walk, epb, 3, _BASS))
    support: list[NoteEvent] = []
    previous_inner: int | None = None
    pickup_at = epb - 2 if passes else None
    for offset, duration in _allemande_support_plan(ctx, passes):
        eighth = start + offset
        # A running lead leaves this beat empty. One third or sixth only while it holds.
        if _hold_at(lead, eighth, epb) < 2:
            continue
        sung = _sounding_midi(lead, eighth, epb) or _lead_at(ctx, eighth)
        remaining = 0
        while remaining < epb and _sounding_midi(lead, eighth + remaining, epb) == sung:
            remaining += 1
        duration = min(duration, remaining)
        if pickup_at is not None:
            if offset >= pickup_at:
                continue
            duration = min(duration, pickup_at - offset)
        if duration <= 0:
            continue
        bass_now = _sounding_midi(low, eighth, epb)
        if bass_now is None or not bass_now < sung:
            continue
        tone = _inner_between(ctx, chord, sung, bass_now, previous_inner)
        if tone is None:
            continue
        previous_inner = tone
        support.extend(_eighth_event(eighth, duration, tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    return lead, support, low


def _courante_closes(bar: int, phrase: Phrase | None, epb: int) -> bool:
    """The last bar of a phrase whose cadence closes. 4/4 never hemiolas."""
    if phrase is None or not phrase.closes:
        return False
    return bar == max(phrase.start, phrase.end - 1) // epb


def _line_quarters_ok(line: list[int], start_slot: int) -> bool:
    groups: dict[int, list[int]] = {}
    for index, pitch in enumerate(line):
        groups.setdefault((start_slot + index) // 4, []).append(pitch)
    return all(_quarter_ok(group) for group in groups.values())


def _scale_path(ctx: _Ctx, origin: int, arrival: int) -> list[int]:
    """Diatonic pitches from `origin` to `arrival`, inclusive, without turning back."""
    if origin == arrival:
        return [origin]
    direction = 1 if arrival > origin else -1
    path = [origin]
    cursor = origin
    for _ in range(48):
        if cursor == arrival:
            break
        nxt = _treble_step(ctx, cursor, direction)
        if nxt == cursor:
            break
        if direction > 0 and nxt > arrival:
            break
        if direction < 0 and nxt < arrival:
            break
        path.append(nxt)
        cursor = nxt
    if path[-1] != arrival:
        path.append(arrival)
    return path


def _fit_directed(path: list[int], count: int) -> list[int]:
    """`count` notes along `path`. The ends stay put. Extra slots repeat; they do not turn back."""
    if count <= 0:
        return []
    if count == 1:
        return [path[-1]]
    if len(path) == 1:
        return [path[0]] * count
    direction = 1 if path[-1] > path[0] else -1
    if len(path) > count:
        chosen = [path[0]]
        for index in range(1, count - 1):
            pos = round(index * (len(path) - 1) / (count - 1))
            pitch = path[min(max(pos, 0), len(path) - 1)]
            if direction > 0:
                pitch = max(chosen[-1], min(pitch, path[-1]))
            else:
                pitch = min(chosen[-1], max(pitch, path[-1]))
            chosen.append(pitch)
        chosen.append(path[-1])
        return chosen
    line = [path[0]]
    extras = count - len(path)
    line.extend([path[0]] * extras)
    line.extend(path[1:])
    return line[:count]


def _tirata_neighbor(ctx: _Ctx, pitch: int) -> int:
    """A diatonic neighbor. The upper step is first; a ceiling uses the lower step."""
    above = _treble_step(ctx, pitch, 1)
    if above != pitch:
        return above
    below = _treble_step(ctx, pitch, -1)
    return below


def _tirata_line(ctx: _Ctx, start_slot: int, origin: int, arrival: int, count: int) -> list[int]:
    """Sixteenths from `origin` to `arrival`. Equal ends neighbor on slots 2 and 3.

    This never falls back to `[arrival] * count`.
    """
    if count <= 0:
        return []
    if count == 1:
        return [arrival]
    if origin == arrival:
        neighbor = _tirata_neighbor(ctx, arrival)
        line = [arrival] * count
        if neighbor != arrival:
            line[1] = neighbor
            if count > 2:
                line[2] = neighbor
        else:
            forced = arrival + 1
            line[1] = forced
            if count > 2:
                line[2] = forced
        if not _line_quarters_ok(line, start_slot) and neighbor != arrival:
            other = _treble_step(ctx, arrival, -1 if neighbor > arrival else 1)
            if other != arrival and other != neighbor:
                swapped = [arrival] * count
                swapped[1] = other
                if count > 2:
                    swapped[2] = other
                if _line_quarters_ok(swapped, start_slot):
                    return swapped
        return line
    path = _scale_path(ctx, origin, arrival)
    line = _fit_directed(path, count)
    line[0] = origin
    line[-1] = arrival
    if line == [arrival] * count:
        line[0] = origin
    if not _line_quarters_ok(line, start_slot):
        compact = [origin] * (count - 1) + [arrival]
        compact[0] = origin
        compact[-1] = arrival
        if _line_quarters_ok(compact, start_slot):
            line = compact
    return line


def _step_toward(ctx: _Ctx, origin: int, target: int) -> int:
    """One diatonic step from `origin` toward `target`. A unison takes the upper step."""
    if target == origin:
        step = _treble_step(ctx, origin, 1)
        if step == origin:
            step = _treble_step(ctx, origin, -1)
        return step
    return _treble_step(ctx, origin, 1 if target > origin else -1)


def _courante_span(ctx: _Ctx) -> tuple[int, int, int]:
    """Melody ends at `open_off`. The arrival is the penultimate eighth of the rhythm half."""
    epb = ctx.epb
    if ctx.kind == "4/4" or (ctx.kind not in {"3/4", "6/8"} and epb >= 8):
        return min(4, epb), min(6, epb - 1), epb - 1
    return min(3, epb), min(4, epb - 1), epb - 1


def _render_bach_courante_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Melody eighths, then a price-directed rhythm. One bass rings the whole bar.

    Equal prices on eighth 0 and 1 leap a diatonic third and turn staccato.
    A differing pair sings the price, including a fall. The rhythm half runs in
    sixteenths from the price that opens it to the price on the penultimate
    eighth. The last eighth steps toward the next bar. A closing bar sings the
    rhythm half as eighths and may hold one inner note with the bass.
    """
    epb = ctx.epb
    start = bar * epb
    closes = _courante_closes(bar, phrase, epb)
    chord = ctx.chord(bar)
    melody_end, arrival_off, last_off = _courante_span(ctx)
    open_off = melody_end
    prices = [_melody_at(ctx, start + offset) for offset in range(epb)]
    sung0 = prices[0]
    same_open = epb > 1 and prices[0] == prices[1]
    leap = _treble_step(ctx, sung0, 2) if same_open else prices[1]
    next_price = _melody_at(ctx, (bar + 1) * epb if bar + 1 < ctx.bars else start + epb)
    arrival = prices[arrival_off] if arrival_off < epb else prices[-1]
    opener = prices[open_off] if open_off < epb else prices[-1]
    step = _step_toward(ctx, arrival, next_price)
    count = max(0, (arrival_off - open_off + 1) * 2)
    rhythm = [] if closes or count < 2 or open_off > arrival_off else _tirata_line(ctx, open_off * 2, opener, arrival, count)

    lead: list[NoteEvent] = []
    sounding: list[int] = []

    def add_lead(offset: int, eighths: int, pitch: int, *, accent: bool = False, staccato: bool = False) -> None:
        if offset >= epb or eighths <= 0:
            return
        events = _eighth_event(
            start + offset,
            eighths,
            pitch,
            epb,
            1,
            _note_velocity(start + offset, eighths, apex, phrase),
            accent,
        )
        if staccato:
            events = _stamp(events, staccato=True)
        lead.extend(events)
        sounding.append(pitch)

    def hemiola(offset: int) -> bool:
        if not closes:
            return False
        if ctx.kind == "3/4":
            return offset in {0, 3}
        if ctx.kind == "6/8":
            return offset in {0, 2, 4}
        return False

    for offset in range(melody_end):
        if offset == 1 and same_open:
            add_lead(1, 1, leap, accent=True, staccato=True)
            continue
        add_lead(offset, 1, prices[offset], accent=hemiola(offset))
    if closes:
        for offset in range(open_off, epb):
            add_lead(offset, 1, prices[offset], accent=hemiola(offset))
    else:
        origin = (start + open_off) * 2
        for index, pitch in enumerate(rhythm):
            lead.extend(_spell16(origin + index, 1, pitch, epb, 1, _note_velocity(start + open_off + index // 2, 1, apex, phrase)))
            sounding.append(pitch)
        if last_off >= open_off and (not rhythm or last_off > arrival_off):
            add_lead(last_off, 1, step, accent=hemiola(last_off))

    bass, tone = _select_bass(ctx, chord, (0,), sounding, sounding, want_third=closes)
    low = _eighth_event(start, epb, bass, epb, 3, _BASS, accent=True)
    support: list[NoteEvent] = []
    if closes and tone is not None:
        support.extend(_eighth_event(start, epb, tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    support = _softer_than_price(support, lead, epb)
    return lead, support, low


from app.sonify.guitar_patterns import (  # noqa: E402
    _BASS,
    _Ctx,
    _INNER,
    _MELODY,
    _MELODY_APEX,
    _PEDAL,
    _choose_inner,
    _dur16,
    _eighth_event,
    _has_contrast_section,
    _inner_choices,
    _melody_at,
    _nearest,
    _note_velocity,
    _on_scale,
    _parallel,
    _playable,
    _position_ok,
    _punch,
    _rises,
    _runs,
    _shape_accompaniment,
    _soften_attack,
    _sounding_midi,
    _spell16,
    _stamp,
    _start16,
    _sustain,
    _walk,
    _cut_before,
    _framed,
    _has_hold,
    _is_suite_finale,
    _melody_activity,
    _raw_activity,
)
