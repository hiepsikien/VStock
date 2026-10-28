"""Intro and outro doors for Bach gavotte, gigue, sarabande, chaconne, prelude, allemande, courante, and Sor cantabile, elegiaque, galop.

Each door writes one bar of the short script (``steps == 2``) or the long script
(``steps == 4``). Repeated roles ignore ``index``. Helpers are imported inside
the doors so this module can load beside ``guitar_frame`` without a cycle.

Sixteenth ornaments (Bach mordents written here, and chaconne bariolage) use
half-eighth offsets and length ``0.5``. Every other attack stays on the eighth
grid. Nothing in this module writes a 32nd.
"""

from __future__ import annotations

from collections.abc import Callable

_EPS = 1e-9


def _frame():
    from app.sonify import guitar_frame as frame

    return frame


def _playable_line(ctx, pitches: list[int]) -> bool:
    from app.sonify.guitar_patterns import _playable

    if any(pitch is None for pitch in pitches):
        return False
    ordered = sorted(pitches)
    if len(ordered) != len(set(ordered)):
        return False
    return _playable([pitch + ctx.semitones for pitch in ordered])


def _harmony(frame, ctx, bar: int, name: str) -> list[int]:
    """Pitch classes for a degree. ``iv`` and ``VI`` are not in ``_function``."""
    root = ctx.chord(bar).pitches[0] % 12
    minor = ctx.mode == "minor"
    if name in {"iv", "IV"}:
        sub = (root + 5) % 12
        third = 3 if name == "iv" or minor else 4
        return [sub, (sub + third) % 12, (sub + 7) % 12]
    if name == "VI":
        base = (root + 8) % 12 if minor else (root + 9) % 12
        third = 4 if minor else 3
        return [base, (base + third) % 12, (base + 7) % 12]
    if name == "vi":
        base = (root + 9) % 12
        return [base, (base + 3) % 12, (base + 7) % 12]
    if name == "i":
        return [root, (root + 3) % 12, (root + 7) % 12]
    return frame._function(ctx, bar, name)


def _half(epb: int) -> int:
    return max(1, epb // 2)


def _meter(ctx) -> tuple[int, int, int]:
    """Eighths per bar, eighths per beat, and the sarabande accent eighth."""
    epb = ctx.epb
    if getattr(ctx, "kind", None) == "6/8":
        beat = 3
        accent = 3 if epb > 3 else 0
    else:
        beat = 2
        accent = 2 if epb > 2 else 0
    return epb, beat, min(accent, max(0, epb - 1))


def _fit_register(midi: int, low: int, high: int) -> int | None:
    if high < low:
        return None
    while midi > high:
        midi -= 12
    while midi < low:
        midi += 12
    if low <= midi <= high:
        return midi
    return None


def _tones(low: int, high: int, pcs: list[int]) -> list[int]:
    want = set(pcs)
    return [note for note in range(low, high + 1) if note % 12 in want]


def _lead_tones(frame, ctx, pcs: list[int]) -> list[int]:
    return _tones(frame._lead_lo(ctx), frame._lead_hi(ctx), pcs)


def _stack_pitches(frame, ctx, pcs: list[int]) -> tuple[int, int | None, int]:
    """A ``_stack`` chord whose bass is the root when that voicing still fits."""
    bass, inner, lead = frame._stack(ctx, pcs)
    if not pcs:
        return bass, inner, lead
    capped = min(frame._bass_hi(ctx), lead - 1)
    root = _fit_register(frame._bass_note(ctx, pcs[0] % 12, lead), ctx.bass_low, capped)
    if root is None or not (root < lead and _playable_line(ctx, [root, lead])):
        return bass, inner, lead
    if inner is not None and root < inner < lead and _playable_line(ctx, [root, inner, lead]):
        return root, inner, lead
    bridged = frame._between(ctx, pcs, root, lead)
    if bridged is not None and root < bridged < lead and _playable_line(ctx, [root, bridged, lead]):
        return root, bridged, lead
    return root, None, lead


def _under_lead(frame, ctx, lead: int, bass: int, previous: int | None) -> int | None:
    """A diatonic third under ``lead``, or a sixth when the third will not fit."""
    from app.sonify.guitar_patterns import _parallel

    if lead <= bass:
        return None
    if not _playable_line(ctx, [bass, lead]):
        return None
    tone = _parallel(
        lead,
        bass,
        ctx.mode,
        frame._mid_lo(ctx),
        frame._mid_hi(ctx),
        ctx.semitones,
        previous,
    )
    if tone is None or not bass < tone < lead:
        return None
    if not frame._mid_lo(ctx) <= tone <= frame._mid_hi(ctx):
        return None
    if not _playable_line(ctx, [bass, tone, lead]):
        return None
    return tone


def _third_under(frame, ctx, lead: int, bass: int) -> int | None:
    """Strict parallel third, used where the spec asks for a third and not a sixth."""
    cursor = lead
    for _ in range(2):
        nxt = frame._step(cursor, -1, ctx.mode, frame._mid_lo(ctx), lead - 1)
        if nxt == cursor or nxt >= lead:
            return None
        cursor = nxt
    if not bass < cursor < lead:
        return None
    if not frame._mid_lo(ctx) <= cursor <= frame._mid_hi(ctx):
        return None
    if not _playable_line(ctx, [bass, cursor, lead]):
        return None
    return cursor


def _degree_lead(frame, ctx, interval: int, aim: int, bass: int | None = None) -> int | None:
    root = 0
    pc = interval % 12
    found = _tones(frame._lead_lo(ctx), frame._lead_hi(ctx), [pc])
    if bass is not None:
        found = [note for note in found if note > bass and _playable_line(ctx, [bass, note])]
    if not found:
        return None
    return min(found, key=lambda note: (abs(note - aim), note))


def _chord(
    frame,
    ctx,
    pcs: list[int],
    offset: int,
    length: int | float,
    velocity: int,
    flags: dict | None = None,
) -> list[tuple]:
    epb = ctx.epb
    if offset >= epb or length <= 0:
        return []
    length = min(length, epb - offset)
    bass, inner, lead = _stack_pitches(frame, ctx, pcs)
    mark = dict(flags or {})
    specs = [
        (offset, length, bass, 3, velocity, dict(mark)),
        (offset, length, lead, 1, velocity, dict(mark)),
    ]
    if inner is not None and bass < inner < lead and _playable_line(ctx, [bass, inner, lead]):
        specs.append((offset, length, inner, 2, velocity, dict(mark)))
    return specs


def _bass_only(frame, ctx, pc: int, offset: int, length: int | float, velocity: int, lead: int | None, flags: dict | None = None) -> list[tuple]:
    epb = ctx.epb
    if offset >= epb or length <= 0:
        return []
    length = min(length, epb - offset)
    pitch = frame._bass_note(ctx, pc % 12, lead)
    pitch = _fit_register(pitch, ctx.bass_low, frame._bass_hi(ctx))
    if pitch is None:
        return []
    if lead is not None and not (pitch < lead and _playable_line(ctx, [pitch, lead])):
        return []
    return [(offset, length, pitch, 3, velocity, dict(flags or {}))]


def _neighbor(frame, ctx, principal: int, bass: int, inner: int | None) -> int | None:
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    for direction in (1, -1):
        candidate = frame._step(principal, direction, ctx.mode, lo, hi)
        if candidate == principal or not lo <= candidate <= hi:
            continue
        if inner is not None and not (bass < inner < candidate):
            continue
        if not bass < candidate:
            continue
        group = [bass, candidate] if inner is None else [bass, inner, candidate]
        home = [bass, principal] if inner is None else [bass, inner, principal]
        if _playable_line(ctx, group) and _playable_line(ctx, home):
            return candidate
    return None


def _mordent(
    frame,
    ctx,
    eighth: int,
    principal: int,
    bass: int,
    inner: int | None,
    velocity: int,
    *,
    sustain_to: int | None = None,
) -> list[tuple]:
    """Principal, upper neighbor, principal. The ornament is sixteenths; the return can ring."""
    epb = ctx.epb
    if eighth >= epb:
        return []
    upper = _neighbor(frame, ctx, principal, bass, inner)
    specs: list[tuple] = []
    if upper is None:
        length = epb - eighth if sustain_to is None else max(1, min(epb, sustain_to) - eighth)
        specs.append((eighth, length, principal, 1, velocity, {"accent": True}))
        return specs
    specs.append((eighth, 0.5, principal, 1, velocity, {"accent": True}))
    if eighth + 0.5 < epb:
        specs.append((eighth + 0.5, 0.5, upper, 1, velocity, {}))
    return_at = eighth + 1
    if return_at >= epb:
        return specs
    end = epb if sustain_to is None else min(epb, sustain_to)
    length = end - return_at
    if length > 0:
        specs.append((return_at, length, principal, 1, velocity, {}))
    return specs


def _scaled(frame, ctx, bar: int, start: int, count: int, velocity: int) -> list[tuple]:
    if count <= 0 or start >= ctx.epb:
        return []
    count = min(count, ctx.epb - start)
    notes = frame._scale_into(ctx, bar, start, count, velocity)
    return [
        (offset, length, midi, voice, velocity, flags)
        for offset, length, midi, voice, _velocity, flags in notes
        if offset < ctx.epb
    ]


def _parallel_over(
    frame,
    ctx,
    lead_notes: list[tuple],
    bass: int,
    velocity: int,
    *,
    third: bool = False,
) -> list[tuple]:
    specs = list(lead_notes)
    previous = None
    for offset, length, midi, _voice, _velocity, _flags in lead_notes:
        if third:
            tone = _third_under(frame, ctx, midi, bass)
        else:
            tone = _under_lead(frame, ctx, midi, bass, previous)
        if tone is None:
            continue
        specs.append((offset, length, tone, 2, velocity, {}))
        previous = tone
    return specs


def _quarters(
    frame,
    ctx,
    pcs: list[int],
    start: int,
    velocity: int,
    *,
    staccato_second: bool = True,
) -> list[tuple]:
    """Two gavotte quarters. The inner voice is a third or a sixth under the lead."""
    bass, _inner, lead = _stack_pitches(frame, ctx, pcs)
    specs: list[tuple] = []
    for index, offset in enumerate((start, start + 2)):
        if offset >= ctx.epb:
            continue
        length = min(2, ctx.epb - offset)
        flags = {"staccato": True} if staccato_second and index == 1 else {}
        tone = _under_lead(frame, ctx, lead, bass, None)
        specs.append((offset, length, bass, 3, velocity, dict(flags)))
        specs.append((offset, length, lead, 1, velocity, dict(flags)))
        if tone is not None and (lead - tone) % 12 in {3, 4, 8, 9}:
            specs.append((offset, length, tone, 2, velocity, dict(flags)))
    return specs


def _gavotte_eighths(
    frame,
    ctx,
    bar: int,
    pcs: list[int],
    start: int,
    velocity: int,
    *,
    into_body: bool,
) -> list[tuple]:
    epb = ctx.epb
    count = min(4, epb - start)
    if count <= 0:
        return []
    bass, _inner, lead = _stack_pitches(frame, ctx, pcs)
    if into_body:
        lead_notes = _scaled(frame, ctx, bar, start, count, velocity)
    else:
        tones = _lead_tones(frame, ctx, pcs) or [lead]
        lead_notes = []
        for index, offset in enumerate(range(start, start + count)):
            pitch = tones[min(index, len(tones) - 1)]
            if pitch <= bass or not _playable_line(ctx, [bass, pitch]):
                pitch = lead if lead > bass and _playable_line(ctx, [bass, lead]) else None
            if pitch is None:
                continue
            lead_notes.append((offset, 1, pitch, 1, velocity, {}))
    if not lead_notes:
        return _chord(frame, ctx, pcs, start, count, velocity, {})
    ceiling = min(note[2] for note in lead_notes)
    root = frame._bass_note(ctx, pcs[0], ceiling)
    if not all(root < note[2] and _playable_line(ctx, [root, note[2]]) for note in lead_notes):
        root = bass
    end = max(note[0] + note[1] for note in lead_notes)
    specs = [(start, max(1, end - start), root, 3, velocity, {})]
    specs.extend(_parallel_over(frame, ctx, lead_notes, root, velocity))
    return specs


def _bariolage(
    frame,
    ctx,
    pcs: list[int],
    start: int,
    velocity: int,
    *,
    final_lead: int | None = None,
) -> list[tuple]:
    """Alternating lead and inner sixteenths over a sustained bass."""
    epb = ctx.epb
    if start >= epb:
        return []
    bass, inner, lead = _stack_pitches(frame, ctx, pcs)
    if inner is None or not bass < inner < lead:
        inner = None
    specs: list[tuple] = [(start, epb - start, bass, 3, velocity, {})]
    lead_slots: list[int] = []
    slot = 0
    eighth = start
    while eighth < epb:
        for half in (0.0, 0.5):
            at = eighth + half
            if at >= epb:
                break
            if slot % 2 == 0:
                specs.append((at, 0.5, lead, 1, velocity, {}))
                lead_slots.append(len(specs) - 1)
            elif inner is not None and bass < inner and _playable_line(ctx, [bass, inner]):
                specs.append((at, 0.5, inner, 2, velocity, {}))
            slot += 1
        eighth += 1
    if final_lead is not None and lead_slots:
        from app.sonify.guitar_patterns import _position_ok

        index = lead_slots[-1]
        at, length, _pitch, voice, vel, flags = specs[index]
        lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
        if lo <= final_lead <= hi and bass < final_lead and _playable_line(ctx, [bass, final_lead]):
            previous = specs[lead_slots[-2]][2] if len(lead_slots) > 1 else None
            close = previous is not None and abs(final_lead - previous) <= 4
            positioned = (not close) or _position_ok(
                [previous + ctx.semitones, final_lead + ctx.semitones]
            )
            if positioned:
                specs[index] = (at, length, final_lead, voice, vel, flags)
    return specs


def _approach_pitch(frame, ctx, bar: int) -> int:
    notes = _scaled(frame, ctx, bar, 0, 1, frame._P)
    if notes:
        return notes[-1][2]
    return frame._lead_lo(ctx)


def _march_cells(epb: int) -> list[tuple[int, int]]:
    if epb >= 8:
        cells = [(0, 3), (3, 1), (4, 3), (7, 1)]
    elif epb == 6:
        cells = [(0, 2), (2, 1), (3, 2), (5, 1)]
    else:
        cells = []
        offset = 0
        while offset < epb:
            room = epb - offset
            if room >= 4:
                cells.append((offset, 3))
                cells.append((offset + 3, 1))
                offset += 4
            else:
                cells.append((offset, room))
                offset += room
    return [(offset, length) for offset, length in cells if offset < epb]


def _descending_from(frame, ctx, start: int, count: int, ceiling: int | None) -> list[int]:
    hi = frame._bass_hi(ctx)
    if ceiling is not None:
        hi = min(hi, ceiling - 1)
    pitch = _fit_register(start, ctx.bass_low, hi)
    if pitch is None:
        pitch = ctx.bass_low
    line = [pitch]
    for _ in range(max(0, count - 1)):
        nxt = frame._step(pitch, -1, ctx.mode, ctx.bass_low, hi)
        if ceiling is not None and nxt >= ceiling:
            nxt = pitch
        if nxt > pitch:
            nxt = pitch
        line.append(nxt)
        pitch = nxt
    return line


def _emit_bass_line(
    ctx,
    cells: list[tuple[int, int]],
    pitches: list[int],
    velocity: int | list[int],
    uppers: list[int],
) -> list[tuple]:
    specs = []
    levels = velocity if isinstance(velocity, list) else [velocity] * len(cells)
    for (offset, length), pitch, level in zip(cells, pitches, levels):
        if uppers and not _playable_line(ctx, [pitch, *uppers]):
            continue
        if uppers and any(pitch >= upper for upper in uppers):
            continue
        specs.append((offset, length, pitch, 3, level, {}))
    return specs


def _scale_steps(frame, note: int, steps: int, mode: str, low: int, high: int) -> int:
    """Walk ``abs(steps)`` scale tones. ``_step`` treats its direction as semitones."""
    direction = 1 if steps >= 0 else -1
    cursor = note
    for _ in range(abs(steps)):
        nxt = frame._step(cursor, direction, mode, low, high)
        if nxt == cursor:
            break
        cursor = nxt
    return cursor


def _diatonic_third(frame, ctx, anchor: int, low: int, high: int) -> int:
    """Two scale steps: a minor or major third, never ``_step(note, 2)``."""
    for direction in (2, -2):
        leap = _scale_steps(frame, anchor, direction, ctx.mode, low, high)
        if abs(leap - anchor) in {3, 4}:
            return leap
    return anchor


def _galop_points(ctx) -> tuple[tuple[int, ...], tuple[int, ...]]:
    epb = ctx.epb
    kind = getattr(ctx, "kind", None)
    if kind == "6/8" or (epb == 6 and kind != "3/4"):
        bass = (0, 3)
        inner = (1, 2, 4, 5)
    elif epb >= 8:
        bass = (0, 4)
        inner = (1, 3, 5, 7)
    else:
        bass = tuple(offset for offset in (0, max(1, epb // 2)) if offset < epb)
        inner = tuple(offset for offset in range(1, epb, 2))
    return (
        tuple(offset for offset in bass if offset < epb),
        tuple(offset for offset in inner if offset < epb),
    )


def _galop_span(
    frame,
    ctx,
    pcs: list[int],
    velocity: int,
    *,
    start: int,
    end: int,
    lead: bool,
    sparkle: bool,
) -> list[tuple]:
    """Staccato root/fifth, off-beat inner chords, and an optional third-leap."""
    epb = ctx.epb
    end = min(end, epb)
    if start >= end:
        return []
    bass_points, inner_offsets = _galop_points(ctx)
    bass_points = tuple(offset for offset in bass_points if start <= offset < end)
    inner_offsets = tuple(offset for offset in inner_offsets if start <= offset < end)
    _bass, inner, melody = _stack_pitches(frame, ctx, pcs)
    root_pc = pcs[0]
    fifth_pc = pcs[2] if len(pcs) > 2 else (root_pc + 7) % 12
    root = frame._bass_note(ctx, root_pc, melody)
    fifth = frame._bass_note(ctx, fifth_pc, melody)
    specs: list[tuple] = []
    voiced_bass: list[tuple[int, int, int]] = []
    for index, offset in enumerate(bass_points):
        nxt = bass_points[index + 1] if index + 1 < len(bass_points) else end
        length = min(2, end - offset, nxt - offset)
        if length <= 0:
            continue
        pitch = root if index % 2 == 0 else fifth
        specs.append((offset, length, pitch, 3, velocity, {"staccato": True}))
        voiced_bass.append((offset, offset + length, pitch))

    def bass_ref(offset: int) -> int:
        """The bass sounding here, or the latest attack, so weak beats still have a hand."""
        latest = root
        for begin, stop, pitch in voiced_bass:
            if begin <= offset:
                latest = pitch
            if begin <= offset < stop:
                return pitch
        return latest

    if inner is not None:
        for offset in inner_offsets:
            floor = bass_ref(offset)
            if not floor < inner < melody:
                continue
            group = [floor, inner] if not lead else [floor, inner, melody]
            if lead and not inner < melody:
                continue
            if not _playable_line(ctx, group if lead else [floor, inner]):
                continue
            specs.append((offset, 1, inner, 2, velocity, {"staccato": True}))
    if lead and not sparkle:
        if start < end and melody > root and _playable_line(ctx, [root, melody]):
            specs.append((start, 1, melody, 1, velocity, {"staccato": True}))
    if sparkle:
        strong = [offset for offset in (0, 3, 4) if start <= offset < end - 1 and offset + 1 < epb]
        if not strong:
            strong = [start] if start + 1 < end else []
        for offset in strong:
            floor = bass_ref(offset)
            anchor = melody if melody > floor else frame._lead_lo(ctx)
            leap = None
            for direction in (2, -2):
                candidate = _scale_steps(
                    frame, anchor, direction, ctx.mode, frame._lead_lo(ctx), frame._lead_hi(ctx)
                )
                if abs(candidate - anchor) not in {3, 4} or candidate <= floor:
                    continue
                if not _playable_line(ctx, [floor, candidate]):
                    continue
                leap = candidate
                break
            if leap is None:
                continue
            inner_now = inner if inner is not None and floor < inner < min(anchor, leap) else None
            if inner_now is not None and offset + 1 in inner_offsets:
                if not _playable_line(ctx, [floor, inner_now, leap]):
                    inner_now = None
            if anchor > floor and _playable_line(ctx, [floor, anchor]):
                specs.append((offset, 1, anchor, 1, velocity, {"staccato": True}))
            leap_flags = {"staccato": True}
            if inner_now is not None and not (inner_now < leap and _playable_line(ctx, [floor, inner_now, leap])):
                specs = [item for item in specs if not (item[0] == offset + 1 and item[3] == 2)]
            specs.append((offset + 1, 1, leap, 1, velocity, leap_flags))
    if end >= epb:
        specs = _short_last_bass(specs)
    return specs


def _lead_leaps(frame, ctx, pcs: list[int], start: int, end: int, velocity: int) -> list[tuple]:
    epb = ctx.epb
    end = min(end, epb)
    tones = _lead_tones(frame, ctx, pcs)
    if not tones:
        return []
    specs = []
    offset = start
    cursor = tones[len(tones) // 2]
    while offset < end:
        leap = _diatonic_third(frame, ctx, cursor, frame._lead_lo(ctx), frame._lead_hi(ctx))
        specs.append((offset, 1, cursor, 1, velocity, {"staccato": True}))
        if offset + 1 < end and leap != cursor:
            specs.append((offset + 1, 1, leap, 1, velocity, {"staccato": True}))
            cursor = leap
            offset += 2
        else:
            offset += 1
    return specs


def _staccato_hits(
    frame,
    ctx,
    plan: list[tuple[int, list[int]]],
    velocity: int,
    *,
    accent_all: bool = False,
    accent_index: int | None = 0,
) -> list[tuple]:
    specs: list[tuple] = []
    for index, (offset, pcs) in enumerate(plan):
        if offset >= ctx.epb:
            continue
        accent = accent_all or index == accent_index
        flags = {"staccato": True, "accent": True} if accent else {"staccato": True}
        specs.extend(_chord(frame, ctx, pcs, offset, 1, velocity, flags))
    return specs


def _has_lament(bass: list[tuple]) -> bool:
    previous = None
    for offset, length, midi, _voice, _velocity, _flags in bass:
        del offset
        if previous is not None:
            prev_len, prev_midi = previous
            if length <= 1 + _EPS and prev_len >= 2 - _EPS and prev_midi - midi in {1, 2}:
                return True
        previous = (length, midi)
    return False


def _shortest_first(total: int, parts: int) -> list[int]:
    parts = max(1, parts)
    total = max(parts, total)
    base = total // parts
    extra = total % parts
    return [base + (1 if index >= parts - extra else 0) for index in range(parts)]


def _retime_bass(bass: list[tuple], epb: int) -> list[tuple]:
    if len(bass) < 2:
        return bass
    ordered = sorted(bass, key=lambda item: (item[0], -item[1]))
    total = sum(max(1, int(round(item[1]))) for item in ordered)
    lengths = _shortest_first(total, len(ordered))
    offset = ordered[0][0]
    if abs(offset - round(offset)) > _EPS:
        offset = int(offset)
    rebuilt = []
    for item, length in zip(ordered, lengths):
        if offset >= epb or length <= 0:
            break
        length = min(length, epb - offset)
        rebuilt.append((offset, length, item[2], 3, item[4], dict(item[5])))
        offset += length
    return rebuilt or ordered


def _next_root(ctx, bar: int) -> int | None:
    nxt = bar + 1
    if nxt >= getattr(ctx, "bars", 0):
        return None
    return ctx.chord(nxt).pitches[0] % 12


def _is_approach(ctx, bar: int, offset: float, length: float, midi: int, epb: int) -> bool:
    root = _next_root(ctx, bar)
    if root is None or length > 1 + _EPS:
        return False
    if offset + length < epb - _EPS:
        return False
    return midi % 12 == (root - 1) % 12


def _safe_bass_pitch(frame, ctx, midi: int, avoid: int | None, ceiling: int | None, previous: int | None) -> int:
    hi = frame._bass_hi(ctx)
    if ceiling is not None:
        hi = min(hi, ceiling - 1)
    candidates = []
    if previous is not None:
        for leap in (0, 7, 5, -7, -5, 3, 4, 8, 9):
            candidates.append(previous + leap)
    candidates.append(midi)
    for candidate in candidates:
        folded = _fit_register(candidate, ctx.bass_low, hi)
        if folded is None or (avoid is not None and folded % 12 == avoid):
            continue
        if previous is not None and previous - folded in {1, 2}:
            continue
        if ceiling is not None and not _playable_line(ctx, [folded, ceiling]):
            continue
        return folded
    folded = _fit_register(midi, ctx.bass_low, hi)
    return midi if folded is None else folded


def _fix_bass(frame, ctx, bar: int, specs: list[tuple], *, allow_lament: bool) -> list[tuple]:
    epb = ctx.epb
    others = [item for item in specs if item[3] != 3]
    bass = sorted((item for item in specs if item[3] == 3), key=lambda item: (item[0], -item[1]))
    if not bass:
        return specs
    if not allow_lament and _has_lament(bass):
        bass = _retime_bass(bass, epb)
    avoid = _next_root(ctx, bar)
    fixed = []
    previous = None
    for offset, length, midi, voice, velocity, flags in bass:
        lament = False
        if previous is not None:
            prev_len, prev_midi = previous
            lament = length <= 1 + _EPS and prev_len >= 2 - _EPS and prev_midi - midi in {1, 2}
        approach = _is_approach(ctx, bar, offset, length, midi, epb)
        if approach and not (allow_lament and lament):
            uppers = [
                item[2]
                for item in others
                if item[0] <= offset < item[0] + item[1] - _EPS
            ]
            ceiling = min(uppers) if uppers else None
            prev_midi = previous[1] if previous is not None else None
            midi = _safe_bass_pitch(frame, ctx, midi, (avoid - 1) % 12 if avoid is not None else None, ceiling, prev_midi)
        fixed.append((offset, length, midi, voice, velocity, flags))
        previous = (length, midi)
    return others + fixed


def _drop_crossed(frame, ctx, specs: list[tuple]) -> list[tuple]:
    """Drop an inner note that crosses a voice or will not fit the hand."""
    kept_inner = []
    rest = [item for item in specs if item[3] != 2]
    for item in specs:
        if item[3] != 2:
            continue
        offset, length, midi, _voice, _velocity, _flags = item
        ok = True
        sample = offset + 0.01
        while sample < offset + length - _EPS:
            sounding = {"bass": [], "lead": []}
            for off, span, pitch, voice, _vel, _flags in rest:
                if off <= sample < off + span - _EPS:
                    if voice == 3:
                        sounding["bass"].append(pitch)
                    elif voice == 1:
                        sounding["lead"].append(pitch)
            basses = sounding["bass"]
            leads = sounding["lead"]
            if basses and midi <= max(basses):
                ok = False
                break
            if leads and midi >= min(leads):
                ok = False
                break
            if not frame._mid_lo(ctx) <= midi <= frame._mid_hi(ctx):
                ok = False
                break
            group = [*basses, midi, *leads]
            if not _playable_line(ctx, group):
                ok = False
                break
            sample += 0.5
        if ok:
            kept_inner.append(item)
    return rest + kept_inner


def _finish(frame, ctx, bar: int, specs: list[tuple], *, allow_lament: bool) -> list[tuple]:
    epb = ctx.epb
    cleaned = []
    for offset, length, midi, voice, velocity, flags in specs:
        if midi is None or length <= 0 or offset >= epb or offset < 0:
            continue
        length = min(length, epb - offset)
        if length <= 0:
            continue
        if voice == 3:
            midi = _fit_register(int(midi), ctx.bass_low, frame._bass_hi(ctx))
        elif voice == 1:
            midi = _fit_register(int(midi), frame._lead_lo(ctx), frame._lead_hi(ctx))
        else:
            midi = int(midi)
            if not frame._mid_lo(ctx) <= midi <= frame._mid_hi(ctx):
                continue
        if midi is None:
            continue
        cleaned.append((offset, length, int(midi), int(voice), int(velocity), dict(flags or {})))
    cleaned = _fix_bass(frame, ctx, bar, cleaned, allow_lament=allow_lament)
    cleaned = _drop_crossed(frame, ctx, cleaned)
    return frame._clip_voice(cleaned, epb)


def _dyad(
    frame,
    ctx,
    pcs: list[int],
    offset: int,
    length: int | float,
    velocity: int,
    *,
    bass: bool = True,
    third: bool = False,
    flags: dict | None = None,
) -> list[tuple]:
    epb = ctx.epb
    if offset >= epb or length <= 0:
        return []
    length = min(length, epb - offset)
    stacked_bass, _inner, lead = _stack_pitches(frame, ctx, pcs)
    aim = 64 - ctx.semitones
    if third:
        # A third below the lead has to sit in the middle register.
        lowered = [note for note in _lead_tones(frame, ctx, pcs) if frame._mid_lo(ctx) < note <= frame._mid_hi(ctx) + 4]
        if lowered:
            lead = min(lowered, key=lambda note: abs(note - aim))
    root = stacked_bass
    tone = _third_under(frame, ctx, lead, root) if third else _under_lead(frame, ctx, lead, root, None)
    if tone is None and third:
        tone = _under_lead(frame, ctx, lead, root, None)
    specs = [(offset, length, lead, 1, velocity, dict(flags or {}))]
    if tone is not None:
        specs.append((offset, length, tone, 2, velocity, dict(flags or {})))
    if bass:
        specs.append((offset, length, root, 3, velocity, dict(flags or {})))
    return specs


def _appoggiatura_dyad(frame, ctx, pcs: list[int], velocity: int, *, start: int = 0, end: int | None = None) -> list[tuple]:
    epb = ctx.epb
    end = epb if end is None else min(end, epb)
    if start >= end:
        return []
    bass, _inner, lead = _stack_pitches(frame, ctx, pcs)
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    neighbor = frame._step(lead, 1, ctx.mode, lo, hi)
    if neighbor == lead or neighbor <= bass or not _playable_line(ctx, [bass, neighbor]):
        neighbor = frame._step(lead, -1, ctx.mode, max(lo, bass + 1), hi)
    if neighbor == lead or not _playable_line(ctx, [bass, neighbor]):
        return _dyad(frame, ctx, pcs, start, end - start, velocity)
    resolve_at = start + 1
    if resolve_at >= end:
        return _dyad(frame, ctx, pcs, start, end - start, velocity)
    lead_notes = [
        (start, 1, neighbor, 1, velocity, {"accent": True}),
        (resolve_at, end - resolve_at, lead, 1, velocity, {}),
    ]
    if not _playable_line(ctx, [bass, lead]):
        return _dyad(frame, ctx, pcs, start, end - start, velocity)
    specs = [(start, end - start, bass, 3, velocity, {})]
    specs.extend(_parallel_over(frame, ctx, lead_notes, bass, velocity))
    return specs


def _held_degree(frame, ctx, bar: int, interval: int, bass_pc: int, velocity: int) -> list[tuple]:
    epb = ctx.epb
    root_pitch = frame._bass_note(ctx, bass_pc, None)
    lead = _degree_lead(frame, ctx, (ctx.chord(bar).pitches[0] + interval) % 12, 67 - ctx.semitones, root_pitch)
    if lead is None:
        return [(0, epb, root_pitch, 3, velocity, {})]
    bass = frame._bass_note(ctx, bass_pc, lead)
    specs = [(0, epb, bass, 3, velocity, {}), (0, epb, lead, 1, velocity, {})]
    return specs


# --- Gavotte -----------------------------------------------------------------


def _gavotte_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    epb = ctx.epb
    role = min(role, 1 if short else 3)
    tonic = _harmony(frame, ctx, bar, "I")
    dominant = _harmony(frame, ctx, bar, "V7")
    sub = _harmony(frame, ctx, bar, "IV")
    half = _half(epb)
    tail = 4 if epb > 4 else half
    if short and not closing:
        if role == 0:
            bass = _stack_pitches(frame, ctx, tonic)[0]
            specs = [(0, half, bass, 3, frame._PP, {})]
            specs.extend(_quarters(frame, ctx, tonic, tail, frame._P, staccato_second=True))
            return specs
        specs = _quarters(frame, ctx, dominant, 0, frame._MP, staccato_second=True)
        specs.extend(_gavotte_eighths(frame, ctx, bar, dominant, tail, frame._MP, into_body=True))
        return specs
    if short and closing:
        if role == 0:
            return _gavotte_eighths(frame, ctx, bar, dominant, 0, frame._MP, into_body=False)
        specs = _quarters(frame, ctx, tonic, 0, frame._P, staccato_second=True)
        block_at = tail if tail < epb else half
        specs.extend(_chord(frame, ctx, tonic, block_at, epb - block_at, frame._P, {}))
        return specs
    if not closing:
        if role == 0:
            return _quarters(frame, ctx, tonic, tail, frame._P, staccato_second=True)
        if role == 1:
            specs = _quarters(frame, ctx, sub, 0, frame._P, staccato_second=True)
            specs.extend(_gavotte_eighths(frame, ctx, bar, tonic, tail, frame._P, into_body=False))
            return specs
        if role == 2:
            return frame._bach_mordent(ctx, bar, frame._MP)
        bass_v = frame._bass_note(ctx, _harmony(frame, ctx, bar, "V")[0], None)
        specs = [(0, half, bass_v, 3, frame._MP, {})]
        specs.extend(_quarters(frame, ctx, dominant, tail, frame._MP, staccato_second=True))
        return specs
    if role == 0:
        specs = _quarters(frame, ctx, sub, 0, frame._MP, staccato_second=True)
        specs.extend(_gavotte_eighths(frame, ctx, bar, sub, tail, frame._MP, into_body=False))
        return specs
    if role == 1:
        specs = _gavotte_eighths(frame, ctx, bar, dominant, 0, frame._MP, into_body=False)
        # Four eighths occupy 0..3. The mordent sits on eighth 4.
        mordent_at = 4 if epb > 4 else half
        bass, inner, lead = _stack_pitches(frame, ctx, dominant)
        if mordent_at < epb:
            # Keep the opening eighths from running into the ornament.
            specs = [item for item in specs if not (item[3] == 1 and item[0] >= mordent_at)]
            specs = [
                (off, min(length, mordent_at - off), midi, voice, vel, flags)
                if voice == 1 and off < mordent_at
                else (off, length, midi, voice, vel, flags)
                for off, length, midi, voice, vel, flags in specs
            ]
            specs.extend(_mordent(frame, ctx, mordent_at, lead, bass, inner, frame._MP, sustain_to=epb))
            if not any(item[3] == 3 and item[0] <= mordent_at < item[0] + item[1] for item in specs):
                specs.append((mordent_at, epb - mordent_at, bass, 3, frame._MP, {}))
        return specs
    if role == 2:
        block_at = tail if tail < epb else half
        return _chord(frame, ctx, tonic, block_at, epb - block_at, frame._P, {})
    return frame._bach_block(ctx, bar, "I", frame._P)


# --- Gigue -------------------------------------------------------------------


def _gigue_downs(epb: int) -> list[int]:
    return [offset for offset in (0, 3) if offset < epb]


def _broken_arpeggio(
    frame,
    ctx,
    pcs: list[int],
    velocity: int,
    *,
    bass: bool,
    inner: bool,
    lead: bool,
    limit: int | None = None,
    accent_bass: bool = False,
    lead_every: bool = False,
    inner_downs: bool = False,
) -> list[tuple]:
    epb = ctx.epb
    stop = epb if limit is None else min(epb, limit)
    stacked_bass, stacked_inner, stacked_lead = _stack_pitches(frame, ctx, pcs)
    specs: list[tuple] = []
    points = [offset for offset in _gigue_downs(epb) if offset < stop]
    if bass:
        root_pc = pcs[0]
        fifth_pc = pcs[2] if len(pcs) > 2 else (root_pc + 7) % 12
        for index, offset in enumerate(points):
            nxt = points[index + 1] if index + 1 < len(points) else stop
            length = max(1, min(nxt, stop) - offset)
            pitch = frame._bass_note(ctx, root_pc if index % 2 == 0 else fifth_pc, stacked_lead)
            pitch = _fit_register(pitch, ctx.bass_low, frame._bass_hi(ctx))
            if pitch is None:
                continue
            flags = {"accent": True} if accent_bass else {}
            specs.append((offset, length, pitch, 3, velocity, flags))

    def bass_at(offset: int) -> int | None:
        found = None
        for off, length, midi, voice, _vel, _flags in specs:
            if voice == 3 and off <= offset < off + length:
                found = midi
        return found

    if inner and inner_downs:
        for off, length, midi, voice, _vel, _flags in list(specs):
            if voice != 3:
                continue
            mid = stacked_inner if stacked_inner is not None and midi < stacked_inner else None
            if mid is None or not _playable_line(ctx, [midi, mid]):
                mid = frame._between(ctx, pcs, midi, stacked_lead)
            if mid is None:
                for note in _tones(frame._mid_lo(ctx), frame._mid_hi(ctx), pcs):
                    if midi < note and _playable_line(ctx, [midi, note]):
                        mid = note
                        break
            if mid is not None and midi < mid and _playable_line(ctx, [midi, mid]):
                specs.append((off, length, mid, 2, velocity, {}))
    if lead:
        solo = lead_every and not any(item[3] == 3 for item in specs)
        if solo:
            lead_tones = _lead_tones(frame, ctx, pcs) or [stacked_lead]
        else:
            lead_tones = [
                note
                for note in _lead_tones(frame, ctx, pcs)
                if note > stacked_bass and _playable_line(ctx, [stacked_bass, note])
            ] or [stacked_lead]
        for offset in range(stop):
            if not lead_every and offset % 2 != 0:
                continue
            floor = None if solo else bass_at(offset)
            start_index = (offset if lead_every else offset // 2) % len(lead_tones)
            ordered = lead_tones[start_index:] + lead_tones[:start_index]
            chosen = None
            for candidate in ordered:
                if floor is not None and (candidate <= floor or not _playable_line(ctx, [floor, candidate])):
                    continue
                chosen = candidate
                break
            if chosen is None:
                continue
            specs.append((offset, 1, chosen, 1, velocity, {}))
    if inner and not inner_downs:
        inner_tones = [
            note
            for note in _tones(frame._mid_lo(ctx), frame._mid_hi(ctx), pcs)
            if stacked_bass < note < stacked_lead and _playable_line(ctx, [stacked_bass, note])
        ]
        if stacked_inner is not None and stacked_inner not in inner_tones and stacked_bass < stacked_inner < stacked_lead:
            inner_tones.append(stacked_inner)
        for offset in range(1, stop, 2):
            if not inner_tones:
                break
            floor = bass_at(offset)
            if floor is None:
                floor = stacked_bass
            leads_here = [
                item[2]
                for item in specs
                if item[3] == 1 and item[0] <= offset < item[0] + item[1]
            ]
            ceiling = min(leads_here) if leads_here else stacked_lead
            placed = None
            for candidate in inner_tones:
                if not floor < candidate < ceiling:
                    continue
                group = [floor, candidate, *leads_here]
                if _playable_line(ctx, group):
                    placed = candidate
                    break
            if placed is not None:
                specs.append((offset, 1, placed, 2, velocity, {}))
    return specs


def _gigue_ramp(frame, ctx, bar: int, velocity_start: int, velocity_end: int) -> list[tuple]:
    epb = ctx.epb
    pcs = _harmony(frame, ctx, bar, "V7")
    bass, _inner, _lead = _stack_pitches(frame, ctx, pcs)
    tones = [note for note in _lead_tones(frame, ctx, pcs) if note > bass and _playable_line(ctx, [bass, note])]
    if not tones:
        tones = [frame._lead_lo(ctx)]
    count = epb
    while len(tones) < count:
        tones.append(tones[-1])
    tones = tones[:count]
    goal = _approach_pitch(frame, ctx, bar)
    if bass < goal <= frame._lead_hi(ctx) and _playable_line(ctx, [bass, goal]):
        tones[-1] = goal
    levels = [velocity_end] if count <= 1 else [
        int(round(velocity_start + (velocity_end - velocity_start) * index / (count - 1)))
        for index in range(count)
    ]
    specs = [(0, epb, bass, 3, velocity_start, {})]
    for offset, (pitch, level) in enumerate(zip(tones, levels)):
        specs.append((offset, 1, pitch, 1, level, {}))
    return specs


def _gigue_flourish(frame, ctx, bar: int, velocity: int) -> list[tuple]:
    """The dominant flourish, filled out to six eighths when the helper stops short."""
    specs = list(frame._bach_dominant_flourish(ctx, bar, velocity))
    want = min(6, ctx.epb)
    covered = {
        int(round(item[0]))
        for item in specs
        if item[3] == 1 and abs(item[0] - round(item[0])) <= _EPS and item[0] < want
    }
    basses = [item[2] for item in specs if item[3] == 3]
    bass = basses[0] if basses else None
    leads = sorted((item for item in specs if item[3] == 1), key=lambda item: item[0])
    last = leads[-1][2] if leads else frame._lead_lo(ctx)
    members = set(_harmony(frame, ctx, bar, "V7"))
    for offset in range(want):
        if offset in covered:
            continue
        chosen = None
        for note in range(last + 1, frame._lead_hi(ctx) + 1):
            if note % 12 not in members or (bass is not None and note <= bass):
                continue
            if bass is not None and not _playable_line(ctx, [bass, note]):
                continue
            chosen = note
            break
        if chosen is None:
            chosen = last
            if bass is not None and not (chosen > bass and _playable_line(ctx, [bass, chosen])):
                continue
        specs.append((offset, 1, chosen, 1, min(frame._MF, velocity + offset), {}))
        covered.add(offset)
        last = chosen
    return specs


def _gigue_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    tonic = _harmony(frame, ctx, bar, "I")
    sub = _harmony(frame, ctx, bar, "IV")
    if short and not closing:
        if role == 0:
            return _broken_arpeggio(
                frame, ctx, tonic, frame._P, bass=True, inner=True, lead=True, limit=6, accent_bass=True
            )
        return _gigue_flourish(frame, ctx, bar, frame._MP)
    if short and closing:
        if role == 0:
            return _gigue_flourish(frame, ctx, bar, frame._MP)
        return _chord(frame, ctx, tonic, 0, ctx.epb, frame._P, {"accent": True})
    if not closing:
        if role == 0:
            return _broken_arpeggio(
                frame, ctx, tonic, frame._P, bass=False, inner=False, lead=True, limit=6, lead_every=True
            )
        if role == 1:
            return _broken_arpeggio(
                frame,
                ctx,
                tonic,
                frame._P,
                bass=True,
                inner=True,
                lead=False,
                limit=None,
                accent_bass=False,
                inner_downs=True,
            )
        if role == 2:
            return _gigue_flourish(frame, ctx, bar, frame._MP)
        return _gigue_ramp(frame, ctx, bar, 52, 60)
    if role == 0:
        return _broken_arpeggio(
            frame, ctx, sub, frame._MP, bass=True, inner=True, lead=True, limit=ctx.epb, accent_bass=False
        )
    if role == 1:
        return _gigue_flourish(frame, ctx, bar, frame._MP)
    if role == 2:
        pcs = _harmony(frame, ctx, bar, "V7")
        bass, inner, lead = _stack_pitches(frame, ctx, pcs)
        specs = [(0, min(5, ctx.epb), bass, 3, frame._P, {})]
        specs.extend(_mordent(frame, ctx, 0, lead, bass, inner, frame._P, sustain_to=5 if ctx.epb > 5 else ctx.epb))
        if ctx.epb > 5:
            pickup = _scaled(frame, ctx, bar, 5, 1, frame._P)
            for note in pickup:
                if bass < note[2] and _playable_line(ctx, [bass, note[2]]):
                    specs.append(note)
                elif note[2] > bass:
                    specs.append(note)
        return specs
    return frame._bach_block(ctx, bar, "I", frame._P)


# --- Sarabande ---------------------------------------------------------------


def _sarabande_body(
    frame,
    ctx,
    bar: int,
    pcs: list[int],
    beat1: int,
    beat2: int,
    *,
    mordent: bool,
    passing: int,
    voices_on_beat1: str,
) -> list[tuple]:
    """Beat 1, weighted beat 2, then either a sustain or a passing tail.

    ``voices_on_beat1`` is ``both`` (bass and lead), ``bass``, or ``full``.
    ``passing`` is how many eighths at the end step into the next bar. Zero sustains.
    """
    epb, beat, accent = _meter(ctx)
    bass, inner, lead = _stack_pitches(frame, ctx, pcs)
    tail = epb - passing if passing else epb
    if tail < accent:
        tail = accent
    specs: list[tuple] = []
    beat1_end = min(accent, tail)
    if beat1_end > 0 and voices_on_beat1 in {"both", "full", "bass"}:
        specs.append((0, beat1_end, bass, 3, beat1, {}))
        if voices_on_beat1 in {"both", "full"}:
            specs.append((0, beat1_end, lead, 1, beat1, {}))
        if voices_on_beat1 == "full" and inner is not None and bass < inner < lead:
            specs.append((0, beat1_end, inner, 2, beat1, {}))
    if accent >= tail:
        return specs
    sustain_to = tail
    specs.append((accent, sustain_to - accent, bass, 3, beat2, {"accent": True}))
    if inner is not None and bass < inner < lead and _playable_line(ctx, [bass, inner, lead]):
        specs.append((accent, sustain_to - accent, inner, 2, beat2, {"accent": True}))
    if mordent:
        specs.extend(
            _mordent(frame, ctx, accent, lead, bass, inner if inner is not None and bass < inner < lead else None, beat2, sustain_to=sustain_to)
        )
    else:
        specs.append((accent, sustain_to - accent, lead, 1, beat2, {"accent": True}))
    if passing:
        specs.extend(_scaled(frame, ctx, bar, tail, passing, beat1 if beat1 <= beat2 else beat2))
    return specs


def _suspension(frame, ctx, bar: int, velocity: int) -> list[tuple]:
    """Bass on the tonic. The lead hangs on degree 4 and resolves to degree 3 on beat 2."""
    epb, _beat, accent = _meter(ctx)
    root = ctx.chord(bar).pitches[0] % 12
    third = 3 if ctx.mode == "minor" else 4
    bass = frame._bass_note(ctx, root, None)
    fourth = _degree_lead(frame, ctx, (root + 5) % 12, 70 - ctx.semitones, bass)
    resolved = _degree_lead(frame, ctx, (root + third) % 12, (fourth or 67) - 1, bass)
    if fourth is None or resolved is None:
        return frame._bach_block(ctx, bar, "I", velocity)
    if resolved > fourth:
        resolved = frame._step(fourth, -1, ctx.mode, frame._lead_lo(ctx), fourth)
    bass = frame._bass_note(ctx, root, min(fourth, resolved))
    if not (_playable_line(ctx, [bass, fourth]) and _playable_line(ctx, [bass, resolved])):
        return [(0, epb, bass, 3, velocity, {})]
    resolve_at = accent if 0 < accent < epb else min(2, epb - 1)
    if resolve_at <= 0:
        return [(0, epb, bass, 3, velocity, {}), (0, epb, resolved, 1, velocity, {})]
    return [
        (0, epb, bass, 3, velocity, {}),
        (0, resolve_at, fourth, 1, velocity, {}),
        (resolve_at, epb - resolve_at, resolved, 1, velocity, {}),
    ]


def _sarabande_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    tonic = "I"
    dominant = "V7"
    sub = "IV"
    if short and not closing:
        if role == 0:
            return _sarabande_body(
                frame, ctx, bar, _harmony(frame, ctx, bar, tonic), frame._P, frame._MP, mordent=True, passing=0, voices_on_beat1="both"
            )
        _epb, beat, _accent = _meter(ctx)
        return _sarabande_body(
            frame, ctx, bar, _harmony(frame, ctx, bar, dominant), frame._P, frame._MP, mordent=True, passing=min(2, beat), voices_on_beat1="both"
        )
    if short and closing:
        if role == 0:
            return _sarabande_body(
                frame, ctx, bar, _harmony(frame, ctx, bar, dominant), frame._P, frame._P, mordent=True, passing=0, voices_on_beat1="both"
            )
        _epb, _beat, accent = _meter(ctx)
        bass = _stack_pitches(frame, ctx, _harmony(frame, ctx, bar, tonic))[0]
        specs = [(0, min(accent, ctx.epb), bass, 3, frame._P, {})]
        if accent < ctx.epb:
            specs.extend(_chord(frame, ctx, _harmony(frame, ctx, bar, tonic), accent, ctx.epb - accent, frame._P, {}))
        return specs
    if not closing:
        if role == 0:
            return _sarabande_body(
                frame, ctx, bar, _harmony(frame, ctx, bar, tonic), frame._P, frame._P, mordent=False, passing=0, voices_on_beat1="both"
            )
        if role == 1:
            return _sarabande_body(
                frame, ctx, bar, _harmony(frame, ctx, bar, sub), frame._P, frame._P, mordent=False, passing=0, voices_on_beat1="both"
            )
        if role == 2:
            return _sarabande_body(
                frame, ctx, bar, _harmony(frame, ctx, bar, dominant), frame._MP, frame._MP, mordent=True, passing=0, voices_on_beat1="both"
            )
        _epb, beat, accent = _meter(ctx)
        passing_at = min(ctx.epb, max(accent + 2, _beat_index_start(ctx, 2)))
        passing = max(2, ctx.epb - passing_at)
        return _sarabande_body(
            frame, ctx, bar, _harmony(frame, ctx, bar, tonic), frame._P, frame._P, mordent=False, passing=passing, voices_on_beat1="full"
        )
    if role == 0:
        return _sarabande_body(
            frame, ctx, bar, _harmony(frame, ctx, bar, sub), frame._P, frame._P, mordent=False, passing=0, voices_on_beat1="both"
        )
    if role == 1:
        return _sarabande_body(
            frame, ctx, bar, _harmony(frame, ctx, bar, dominant), frame._P, frame._P, mordent=False, passing=0, voices_on_beat1="both"
        )
    if role == 2:
        return _suspension(frame, ctx, bar, frame._PP)
    return frame._bach_block(ctx, bar, "I", frame._PP)


def _beat_index_start(ctx, index: int) -> int:
    _epb, beat, _accent = _meter(ctx)
    return index * beat


# --- Chaconne ----------------------------------------------------------------


def _descent_anchor(frame, ctx, pc: int, ceiling: int | None) -> int:
    """A tonic in the bass that can still fall, rather than the open fifth on the floor."""
    hi = frame._bass_hi(ctx)
    if ceiling is not None:
        hi = min(hi, ceiling - 1)
    found = [note for note in range(ctx.bass_low, hi + 1) if note % 12 == pc % 12]
    if not found:
        folded = _fit_register(pc, ctx.bass_low, max(ctx.bass_low, hi))
        return ctx.bass_low if folded is None else folded
    best = found[-1]
    best_score = -1
    for note in found:
        line = _descending_from(frame, ctx, note, 4, ceiling)
        score = len(set(line)) * 20 + note
        if score > best_score:
            best = note
            best_score = score
    return best


def _ground(frame, ctx, bar: int, velocity: int, *, passes: int) -> list[tuple]:
    epb, _beat, accent = _meter(ctx)
    pcs = _harmony(frame, ctx, bar, "I")
    _stacked, inner, lead = _stack_pitches(frame, ctx, pcs)
    start = _descent_anchor(frame, ctx, pcs[0], lead)
    if inner is not None and not start < inner < lead:
        inner = frame._between(ctx, pcs, start, lead)
    if passes <= 2:
        opening = min(accent, epb) or epb
        specs = [(0, opening, start, 3, velocity, {})]
        if accent < epb:
            ceiling = min(frame._bass_hi(ctx), lead - 1)
            stepped = frame._step(start, -1, ctx.mode, ctx.bass_low, ceiling)
            if stepped >= start or not _playable_line(ctx, [stepped, lead]):
                stepped = start
            beat_inner = inner
            if beat_inner is not None and not (
                stepped < beat_inner < lead and _playable_line(ctx, [stepped, beat_inner, lead])
            ):
                beat_inner = frame._between(ctx, pcs, stepped, lead)
            specs.append((accent, epb - accent, stepped, 3, velocity, {}))
            if _playable_line(ctx, [stepped, lead]):
                specs.append((accent, epb - accent, lead, 1, velocity, {"accent": True}))
            if (
                beat_inner is not None
                and stepped < beat_inner < lead
                and _playable_line(ctx, [stepped, beat_inner, lead])
            ):
                specs.append((accent, epb - accent, beat_inner, 2, velocity, {"accent": True}))
        return specs
    line = _descending_from(frame, ctx, start, 4, lead)
    lengths = _shortest_first(epb, len(line))
    specs: list[tuple] = []
    if all(note < lead and _playable_line(ctx, [note, lead]) for note in line):
        specs.append((0, epb, lead, 1, velocity, {}))
    if inner is not None and all(note < inner < lead for note in line) and all(
        _playable_line(ctx, [note, inner, lead]) for note in line
    ):
        specs.append((0, epb, inner, 2, max(frame._PP, velocity - 4), {}))
    offset = 0
    for pitch, length in zip(line, lengths):
        if offset >= epb:
            break
        length = min(length, epb - offset)
        specs.append((offset, length, pitch, 3, velocity, {}))
        offset += length
    return specs


def _chaconne_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    tonic = _harmony(frame, ctx, bar, "I")
    dominant = _harmony(frame, ctx, bar, "V7")
    if short and not closing:
        if role == 0:
            return frame._bach_tetrachord(ctx, bar, frame._MP)
        cut = _half(ctx.epb)
        bass, _inner, lead = _stack_pitches(frame, ctx, dominant)
        specs = [(0, cut, bass, 3, frame._MP, {}), (0, cut, lead, 1, frame._MP, {})]
        goal = _approach_pitch(frame, ctx, bar)
        specs.extend(_bariolage(frame, ctx, dominant, cut, frame._MP, final_lead=goal))
        return specs
    if short and closing:
        if role == 0:
            return frame._bach_tetrachord(ctx, bar, frame._MP)
        _epb, _beat, _accent = _meter(ctx)
        end = _beat_index_start(ctx, 2)
        if end <= 0 or end > ctx.epb:
            end = ctx.epb
        return _chord(frame, ctx, tonic, 0, end, frame._P, {})
    if not closing:
        if role == 0:
            return _ground(frame, ctx, bar, frame._P, passes=2)
        if role == 1:
            return _ground(frame, ctx, bar, frame._MP, passes=4)
        if role == 2:
            return frame._bach_arpeggiato(ctx, bar, "I", frame._MP)
        return _bariolage(frame, ctx, dominant, 0, frame._MP, final_lead=_approach_pitch(frame, ctx, bar))
    if role == 0:
        return frame._bach_tetrachord(ctx, bar, frame._MP)
    if role == 1:
        return frame._bach_arpeggiato(ctx, bar, "I", frame._P)
    if role == 2:
        return frame._bach_converge_dominant(ctx, bar, frame._P)
    return frame._bach_block(ctx, bar, "I", frame._P)


# --- Cantabile ---------------------------------------------------------------


def _cantabile_into(frame, ctx, bar: int, pcs: list[int], velocity: int) -> list[tuple]:
    epb = ctx.epb
    cut = _half(epb)
    specs = _dyad(frame, ctx, pcs, 0, cut, velocity)
    bass = _stack_pitches(frame, ctx, pcs)[0]
    tail = _scaled(frame, ctx, bar, cut, epb - cut, velocity)
    tail = [note for note in tail if note[2] > bass and _playable_line(ctx, [bass, note[2]])]
    if tail:
        specs.append((cut, epb - cut, bass, 3, velocity, {}))
        specs.extend(_parallel_over(frame, ctx, tail, bass, velocity))
    else:
        specs.extend(_dyad(frame, ctx, pcs, cut, epb - cut, velocity))
    return specs


def _cantabile_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    tonic = _harmony(frame, ctx, bar, "I")
    dominant = _harmony(frame, ctx, bar, "V7")
    sub = _harmony(frame, ctx, bar, "IV")
    epb = ctx.epb
    half = _half(epb)
    if short and not closing:
        if role == 0:
            return _dyad(frame, ctx, tonic, 0, epb, frame._P)
        return _cantabile_into(frame, ctx, bar, dominant, frame._MP)
    if short and closing:
        if role == 0:
            return _appoggiatura_dyad(frame, ctx, dominant, frame._P)
        return _dyad(frame, ctx, tonic, 0, epb, frame._PP, third=True)
    if not closing:
        if role == 0:
            specs = _dyad(frame, ctx, tonic, 0, half, frame._PP, bass=False)
            specs.extend(_dyad(frame, ctx, tonic, half, epb - half, frame._P, bass=True))
            return specs
        if role == 1:
            return frame._sor_lyric_walk(ctx, bar, frame._P, 0)
        if role == 2:
            return _appoggiatura_dyad(frame, ctx, dominant, frame._MP)
        return _cantabile_into(frame, ctx, bar, tonic, frame._P)
    if role == 0:
        specs = _dyad(frame, ctx, tonic, 0, half, frame._P)
        specs.extend(_dyad(frame, ctx, sub, half, epb - half, frame._P))
        return specs
    if role == 1:
        return _appoggiatura_dyad(frame, ctx, dominant, frame._P)
    if role == 2:
        root = tonic[0]
        fifth = tonic[2] if len(tonic) > 2 else (root + 7) % 12
        _stacked, _inner, lead = _stack_pitches(frame, ctx, tonic)
        low_fifth = frame._bass_note(ctx, fifth, lead)
        low_root = frame._bass_note(ctx, root, lead)
        specs = _dyad(frame, ctx, tonic, 0, epb, frame._PP, bass=False, third=True)
        specs.append((0, half, low_fifth, 3, frame._PP, {}))
        specs.append((half, epb - half, low_root, 3, frame._PP, {}))
        return specs
    return _dyad(frame, ctx, tonic, 0, epb, frame._PP, third=True)


# --- Elegiaque ---------------------------------------------------------------


def _one_lead(frame, ctx, pcs: list[int], basses: list[int], velocity: int) -> list[tuple]:
    if not basses:
        return []
    _bass, _inner, lead = _stack_pitches(frame, ctx, pcs)
    if all(bass < lead and _playable_line(ctx, [bass, lead]) for bass in basses):
        return [(0, ctx.epb, lead, 1, velocity, {})]
    return []


def _march_bass(
    frame,
    ctx,
    bar: int,
    name: str,
    velocity: int,
    *,
    descend: bool,
    rise_to: int | None = None,
    cells: list[tuple[int, int]] | None = None,
) -> tuple[list[tuple], list[int]]:
    pcs = _harmony(frame, ctx, bar, name)
    root = frame._bass_note(ctx, pcs[0], None)
    fifth_pc = pcs[2] if len(pcs) > 2 else (pcs[0] + 7) % 12
    fifth = frame._bass_note(ctx, fifth_pc, None)
    grid = cells if cells is not None else _march_cells(ctx.epb)
    if descend:
        pitches = _descending_from(frame, ctx, root, len(grid), None)
    else:
        pitches = []
        cursor = root
        for index, (_offset, _length) in enumerate(grid):
            if index % 4 == 0:
                chosen = root
            elif index % 4 == 2:
                chosen = fifth if fifth <= frame._bass_hi(ctx) else root
            else:
                chosen = frame._step(cursor, -1, ctx.mode, ctx.bass_low, frame._bass_hi(ctx))
                if cursor - chosen not in {1, 2}:
                    chosen = cursor - 1 if cursor - 1 >= ctx.bass_low else cursor
            if chosen > frame._bass_hi(ctx):
                chosen = frame._bass_hi(ctx)
            pitches.append(chosen)
            cursor = chosen
    levels = []
    for index in range(len(grid)):
        if rise_to is None or index == 0:
            levels.append(velocity)
        else:
            levels.append(rise_to)
    specs = _emit_bass_line(ctx, grid, pitches, levels, [])
    sounded = [item[2] for item in specs]
    return specs, sounded


def _sigh(frame, ctx, bar: int, bass_notes: list[int], velocity: int) -> list[tuple]:
    """Minor degree 6 resolving down to degree 5, above the march bass."""
    if not bass_notes:
        return []
    root = ctx.chord(bar).pitches[0] % 12
    sixth_pc = (root + 8) % 12 if ctx.mode == "minor" else (root + 9) % 12
    fifth_pc = (root + 7) % 12
    ceiling = max(bass_notes) + 1
    fifths = [note for note in _lead_tones(frame, ctx, [fifth_pc]) if note > max(bass_notes)]
    if not fifths:
        return []
    fifth = min(fifths, key=lambda note: abs(note - (67 - ctx.semitones)))
    gap = 1 if ctx.mode == "minor" else 2
    sixth = fifth + gap
    if sixth % 12 != sixth_pc or sixth > frame._lead_hi(ctx) or sixth < frame._lead_lo(ctx):
        higher = [note for note in _lead_tones(frame, ctx, [sixth_pc]) if note > fifth]
        sixth = higher[0] if higher else None
    if sixth is None:
        return [(0, ctx.epb, fifth, 1, velocity, {})]
    if not all(_playable_line(ctx, [bass, sixth]) for bass in bass_notes if bass < sixth):
        sixth = None
    if not all(bass < fifth and _playable_line(ctx, [bass, fifth]) for bass in bass_notes):
        return []
    if sixth is None:
        return [(0, ctx.epb, fifth, 1, velocity, {})]
    return [
        (0, 1, sixth, 1, velocity, {"accent": True}),
        (1, ctx.epb - 1, fifth, 1, velocity, {}),
    ]


def _half_grid(epb: int) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    cut = _half(epb)
    if epb >= 8:
        return [(0, 3), (3, 1)], [(cut, 3), (cut + 3, 1)]
    if epb == 6:
        return [(0, 2), (2, 1)], [(3, 2), (5, 1)]
    return [(0, cut)], [(cut, epb - cut)]


def _elegiaque_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    tonic_name = "I"
    if short and not closing:
        if role == 0:
            bass, sounded = _march_bass(frame, ctx, bar, tonic_name, frame._PP, descend=False, rise_to=frame._P)
            bass.extend(_one_lead(frame, ctx, _harmony(frame, ctx, bar, tonic_name), sounded, frame._PP))
            return bass
        bass, sounded = _march_bass(frame, ctx, bar, "V7", frame._P, descend=True)
        bass.extend(_sigh(frame, ctx, bar, sounded, frame._P))
        return bass
    if short and closing:
        if role == 0:
            return _lament_to_tonic(frame, ctx, bar, frame._P)
        return _chord(frame, ctx, _harmony(frame, ctx, bar, tonic_name), 0, ctx.epb, frame._PP, {})
    if not closing:
        if role == 0:
            bass, sounded = _march_bass(frame, ctx, bar, tonic_name, frame._PP, descend=False)
            bass.extend(_one_lead(frame, ctx, _harmony(frame, ctx, bar, tonic_name), sounded, frame._PP))
            return bass
        if role == 1:
            bass, sounded = _march_bass(frame, ctx, bar, tonic_name, frame._P, descend=True)
            bass.extend(_sigh(frame, ctx, bar, sounded, frame._P))
            return bass
        if role == 2:
            return _iv_then_v(frame, ctx, bar, frame._MP)
        bass, sounded = _march_bass(frame, ctx, bar, "V7", frame._P, descend=False)
        return bass
    if role == 0:
        bass, _sounded = _march_bass(frame, ctx, bar, tonic_name, frame._P, descend=True)
        return bass
    if role == 1:
        return _appoggiatura_halves(frame, ctx, bar, frame._P)
    if role == 2:
        bass, sounded = _march_bass(frame, ctx, bar, tonic_name, frame._PP, descend=False)
        bass.extend(_one_lead(frame, ctx, _harmony(frame, ctx, bar, tonic_name), sounded, frame._PP))
        return bass
    open_bass = _lowest_open(frame, ctx)
    if open_bass is None:
        open_bass = frame._bass_note(ctx, ctx.chord(bar).pitches[0] % 12, None)
    return [(0, ctx.epb, open_bass, 3, frame._PP, {})]


def _lowest_open(frame, ctx) -> int | None:
    for sounding in (40, 45, 50):
        written = sounding - ctx.semitones
        if ctx.bass_low <= written <= frame._bass_hi(ctx):
            return written
    return None


def _lament_to_tonic(frame, ctx, bar: int, velocity: int) -> list[tuple]:
    """Degree 5 falls, by a lament step, onto degree 1. The lead resolves 6–5."""
    epb = ctx.epb
    root_pc = ctx.chord(bar).pitches[0] % 12
    fifth = frame._bass_note(ctx, (root_pc + 7) % 12, None)
    tonic = frame._bass_note(ctx, root_pc, None)
    grid = _march_cells(epb)
    if len(grid) >= 4:
        cells = grid
        step = frame._step(fifth, -1, ctx.mode, ctx.bass_low, frame._bass_hi(ctx))
        if fifth - step not in {1, 2}:
            step = fifth
        pitches = [fifth, step, tonic, tonic]
    elif len(grid) >= 2:
        cells = [grid[0], (grid[0][0] + grid[0][1], epb - grid[0][0] - grid[0][1])]
        pitches = [fifth, tonic]
    else:
        cells = [(0, epb)]
        pitches = [tonic]
    specs = _emit_bass_line(ctx, cells, pitches, velocity, [])
    sounded = [item[2] for item in specs]
    specs.extend(_sigh(frame, ctx, bar, sounded, velocity))
    return specs


def _iv_then_v(frame, ctx, bar: int, velocity: int) -> list[tuple]:
    left, right = _half_grid(ctx.epb)
    first, sounded_iv = _march_bass(frame, ctx, bar, "iv", velocity, descend=False, cells=left)
    second, sounded_v = _march_bass(frame, ctx, bar, "V7", velocity, descend=False, cells=right)
    specs = first + second
    lead_iv = _one_lead(frame, ctx, _harmony(frame, ctx, bar, "iv"), sounded_iv, velocity)
    lead_v = _one_lead(frame, ctx, _harmony(frame, ctx, bar, "V7"), sounded_v, velocity)
    cut = _half(ctx.epb)
    for offset, length, midi, voice, level, flags in lead_iv:
        if offset < cut:
            specs.append((offset, min(length, cut - offset), midi, voice, level, flags))
    for offset, length, midi, voice, level, flags in lead_v:
        if offset >= cut or length > cut:
            start = max(offset, cut)
            specs.append((start, min(length, ctx.epb - start), midi, voice, level, flags))
        elif offset + length > cut:
            specs.append((cut, offset + length - cut, midi, voice, level, flags))
    return specs


def _appoggiatura_halves(frame, ctx, bar: int, velocity: int) -> list[tuple]:
    cut = _half(ctx.epb)
    specs = _appoggiatura_dyad(frame, ctx, _harmony(frame, ctx, bar, "iv"), velocity, start=0, end=cut)
    specs.extend(_appoggiatura_dyad(frame, ctx, _harmony(frame, ctx, bar, "V7"), velocity, start=cut, end=ctx.epb))
    return specs


# --- Galop -------------------------------------------------------------------


def _short_last_bass(specs: list[tuple]) -> list[tuple]:
    """Leave the last bass as one eighth so a following step down is not a lament."""
    last = None
    for index, item in enumerate(specs):
        if item[3] == 3:
            last = index
    if last is None:
        return specs
    offset, length, midi, voice, velocity, flags = specs[last]
    if length <= 1:
        return specs
    shortened = list(specs)
    shortened[last] = (offset, 1, midi, voice, velocity, flags)
    return shortened


def _galop_hits(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    tonic = _harmony(frame, ctx, bar, "I")
    sub = _harmony(frame, ctx, bar, "IV")
    dominant = _harmony(frame, ctx, bar, "V7")
    epb = ctx.epb
    half = _half(epb)
    if short and not closing:
        if role == 0:
            # First half stays at _P, including the downbeat lead. The fifth and
            # the later off-beats answer at _MP.
            opening = _galop_span(
                frame, ctx, tonic, frame._P, start=0, end=half, lead=True, sparkle=False
            )
            answer = _galop_span(
                frame, ctx, tonic, frame._MP, start=half, end=epb, lead=False, sparkle=False
            )
            return opening + answer
        specs = _galop_span(frame, ctx, dominant, frame._MP, start=0, end=half, lead=False, sparkle=False)
        specs.extend(_lead_leaps(frame, ctx, dominant, half, epb, frame._MP))
        return specs
    if short and closing:
        if role == 0:
            return _galop_span(frame, ctx, dominant, frame._MP, start=0, end=epb, lead=True, sparkle=True)
        points = [0]
        second = 2 if epb > 2 else None
        if second is None or second >= epb:
            second = 4 if 4 < epb else None
        if second is not None:
            points.append(second)
        return _staccato_hits(
            frame,
            ctx,
            [(offset, tonic) for offset in points],
            frame._MF,
            accent_all=True,
        )
    if not closing:
        if role == 0:
            return _galop_span(frame, ctx, tonic, frame._P, start=0, end=epb, lead=False, sparkle=False)
        if role == 1:
            specs = _galop_span(frame, ctx, tonic, frame._MP, start=0, end=half, lead=True, sparkle=True)
            specs.extend(_galop_span(frame, ctx, sub, frame._MP, start=half, end=epb, lead=True, sparkle=True))
            return specs
        if role == 2:
            return _galop_span(frame, ctx, dominant, frame._MP, start=0, end=epb, lead=True, sparkle=True)
        # Galop through the first half, one eighth of rest at the midpoint,
        # then three tonic eighths that throw the dance into the body.
        start = max(0, epb - 3)
        rest = start - 1
        specs: list[tuple] = []
        if rest > 0:
            specs.extend(
                _galop_span(
                    frame, ctx, tonic, frame._MF, start=0, end=rest, lead=False, sparkle=False
                )
            )
        specs.extend(
            _staccato_hits(
                frame,
                ctx,
                [(offset, tonic) for offset in range(start, epb)],
                frame._MF,
                accent_index=None,
            )
        )
        return specs
    if role == 0:
        specs = _galop_span(frame, ctx, tonic, frame._MP, start=0, end=half, lead=True, sparkle=True)
        specs.extend(_galop_span(frame, ctx, sub, frame._MP, start=half, end=epb, lead=True, sparkle=True))
        return specs
    if role == 1:
        return _galop_span(frame, ctx, dominant, frame._MP, start=0, end=epb, lead=True, sparkle=True)
    if role == 2:
        offsets = [offset for offset in (0, 2, 4) if offset < epb]
        names = [dominant, tonic, dominant]
        return _staccato_hits(
            frame,
            ctx,
            list(zip(offsets, names)),
            frame._MF,
            accent_index=None,
        )
    points = [0]
    second = 4 if 4 < epb else (2 if 2 < epb else None)
    if second is not None:
        points.append(second)
    return _staccato_hits(
        frame,
        ctx,
        [(offset, tonic) for offset in points],
        frame._MF,
        accent_all=True,
    )


def _note(offset, length, midi, voice, velocity, flags=None) -> tuple:
    return (offset, length, midi, voice, velocity, dict(flags or {}))


def _register_pool(low: int, high: int, pcs: set[int]) -> list[int]:
    if high < low:
        return []
    return [midi for midi in range(low, high + 1) if midi % 12 in pcs]


def _open_first(frame, ctx, notes: list[int]) -> list[int]:
    return sorted(notes, key=lambda midi: (not frame._is_open(ctx, midi), midi))


def _leading_pc(pcs: list[int]) -> int | None:
    """The third of V7 is the leading tone. Triads have no seventh to keep away from the bass."""
    if len(pcs) >= 4:
        return pcs[1] % 12
    return None


def _beside_bass(midi: int, bass: int, leading: int | None) -> bool:
    return leading is not None and midi % 12 == leading and abs(midi - bass) <= 2


def _roll_voices(
    frame,
    ctx,
    pcs: list[int],
    *,
    pedal_pc: int | None = None,
) -> tuple[int, int, int, int]:
    """Bass, low mid, upper mid, and lead.

    A tonic pedal is used only when some stack passes ``_playable_line``.
    Otherwise the bass is the chord root, and the inner voices are chosen
    against that root. The leading tone of V7 never sits within two semitones
    of whichever bass is kept.
    """
    members = {pc % 12 for pc in pcs}
    leading = _leading_pc(pcs)
    root = pcs[0] % 12
    mids = _register_pool(frame._mid_lo(ctx), frame._mid_hi(ctx), members)
    leads = _register_pool(frame._lead_lo(ctx), frame._lead_hi(ctx), members)
    aim = 67 - ctx.semitones
    leads.sort(key=lambda midi: (abs(midi - aim), midi))
    root_basses = _open_first(frame, ctx, _register_pool(ctx.bass_low, frame._bass_hi(ctx), {root}))

    def stack_for(bass: int) -> tuple[int, int, int, int] | None:
        uppers = [midi for midi in mids if bass < midi and not _beside_bass(midi, bass, leading)]
        high = [midi for midi in leads if bass < midi and not _beside_bass(midi, bass, leading)]
        for lead in high:
            for low_mid in uppers:
                if not bass < low_mid < lead:
                    continue
                for upper_mid in uppers:
                    if not low_mid < upper_mid < lead:
                        continue
                    if _playable_line(ctx, [bass, low_mid, upper_mid, lead]):
                        return bass, low_mid, upper_mid, lead
        return None

    def against_root(bass: int) -> tuple[int, int, int, int]:
        uppers = [midi for midi in mids if bass < midi and not _beside_bass(midi, bass, leading)]
        high = [midi for midi in leads if bass < midi and not _beside_bass(midi, bass, leading)]
        lead = next((midi for midi in high if _playable_line(ctx, [bass, midi])), None)
        if lead is None:
            lead = high[0] if high else frame._lead_lo(ctx)
        between = [midi for midi in uppers if midi < lead and _playable_line(ctx, [bass, midi, lead])]
        if not between:
            between = [midi for midi in uppers if midi < lead]
        low_mid = between[0] if between else lead
        upper_mid = next((midi for midi in between if midi > low_mid), low_mid)
        return bass, low_mid, upper_mid, lead

    if pedal_pc is not None:
        pedal = _open_first(frame, ctx, _register_pool(ctx.bass_low, frame._bass_hi(ctx), {pedal_pc % 12}))
        for bass in pedal:
            found = stack_for(bass)
            if found is not None:
                return found
    for bass in root_basses:
        found = stack_for(bass)
        if found is not None:
            return found
    if root_basses:
        return against_root(root_basses[0])
    stacked, _inner, _lead = _stack_pitches(frame, ctx, pcs)
    return against_root(stacked)


def _next_melody(frame, ctx, bar: int) -> int | None:
    """The next bar's melody, folded into the lead the same way ``_scale_into`` does."""
    nxt = bar + 1
    if nxt >= getattr(ctx, "bars", 0) or nxt * ctx.epb >= len(ctx.melody):
        return None
    pitch = ctx.melody[nxt * ctx.epb]
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    while pitch < lo and pitch + 12 <= hi:
        pitch += 12
    while pitch > hi and pitch - 12 >= lo:
        pitch -= 12
    if lo <= pitch <= hi:
        return pitch
    return None


def _aimed_lead(
    frame,
    ctx,
    bar: int,
    current: int,
    bass: int,
    company: list[int],
) -> int:
    """One diatonic step from ``current`` toward ``_approach_pitch``.

    The approach pitch is already one step before the next melody. A step that
    leaves the lead, meets the bass or ``company``, or is the next melody stays
    on ``current``. This does not leap to the approach pitch.
    """
    target = _approach_pitch(frame, ctx, bar)
    if target == current:
        return current
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    direction = 1 if target > current else -1
    stepped = frame._step(current, direction, ctx.mode, lo, hi)
    if stepped == current or not lo <= stepped <= hi or stepped <= bass:
        return current
    melody = _next_melody(frame, ctx, bar)
    if melody is not None and stepped % 12 == melody % 12:
        return current
    if any(stepped <= other for other in company):
        return current
    if not _playable_line(ctx, [bass, *company, stepped]):
        return current
    return stepped


def _prelude_roll(
    frame,
    ctx,
    bar: int,
    pcs: list[int],
    start: int,
    span: int,
    velocity: int,
    *,
    lead_aim: bool = False,
    eighth_grid: bool = False,
    pedal_pc: int | None = None,
) -> list[tuple]:
    """Half-bar roll. Slot 0 is bass. The lead at sixteenth 3 rings across the next slot."""
    if span <= 0 or start >= ctx.epb:
        return []
    span = min(span, ctx.epb - start)
    bass, low_mid, upper_mid, lead = _roll_voices(frame, ctx, pcs, pedal_pc=pedal_pc)
    if eighth_grid:
        # One attack per eighth of this half. A 3-eighth half stops before a fifth note.
        order = [(bass, 3), (low_mid, 2), (upper_mid, 2), (lead, 1), (low_mid, 2)]
        specs = []
        for index in range(span):
            pitch, voice = order[index] if index < len(order) else (low_mid, 2)
            if voice == 1 and lead_aim:
                pitch = _aimed_lead(frame, ctx, bar, pitch, bass, [])
            specs.append(_note(start + index, 1, pitch, voice, velocity))
        return specs
    if span >= 4:
        arch = [
            (low_mid, 2),
            (upper_mid, 2),
            (lead, 1),
            (low_mid, 2),
            (upper_mid, 2),
            (lead, 1),
            (upper_mid, 2),
        ]
    else:
        arch = [
            (low_mid, 2),
            (upper_mid, 2),
            (lead, 1),
            (low_mid, 2),
            (upper_mid, 2),
        ]
    lead_at = [index for index, (_pitch, voice) in enumerate(arch) if voice == 1]
    last_lead = lead_at[-1] if lead_at else None
    specs = [_note(start, span, bass, 3, velocity)]
    for index, (pitch, voice) in enumerate(arch):
        at = start + 0.5 * (index + 1)
        if at >= start + span:
            break
        # Sixteenth 3 of the half (arch index 2) sustains across the next slot.
        length = 1.0 if index == 2 and voice == 1 else 0.5
        if voice == 1 and index == last_lead and lead_aim:
            company = []
            if index == 2 and index + 1 < len(arch):
                company = [arch[index + 1][0]]
            pitch = _aimed_lead(frame, ctx, bar, pitch, bass, company)
        voice_here = 2 if index == 3 else voice
        specs.append(_note(at, length, pitch, voice_here, velocity))
    return specs


def _scale_run(frame, ctx, bar: int, count: int) -> list[int]:
    """``count`` rising scale steps in the lead, the last one step before the next melody."""
    from app.sonify.guitar_patterns import _position_ok

    if count <= 0:
        return []
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    target = lo + 5
    nxt = bar + 1
    if nxt < ctx.bars and nxt * ctx.epb < len(ctx.melody):
        target = ctx.melody[nxt * ctx.epb]
    found: list[list[int]] = []
    for shift in (0, 12, -12, 24, -24):
        aimed = target + shift
        cursor = aimed
        walked: list[int] = []
        for _ in range(count):
            step = frame._step(cursor, -1, ctx.mode, lo, hi)
            if step == cursor or step >= cursor:
                break
            walked.append(step)
            cursor = step
        if len(walked) != count:
            continue
        walked.reverse()
        if walked[-1] >= aimed:
            continue
        if not all(lo <= pitch <= hi for pitch in walked):
            continue
        if not _position_ok([pitch + ctx.semitones for pitch in walked]):
            continue
        found.append(walked)
    if not found:
        return []
    return min(found, key=lambda line: (abs(line[-1] - (target - 2)), abs(line[0] - 60)))


def _stepwise_line(frame, ctx, bass: int, count: int) -> list[int]:
    """A rising scale in the lead that sits over ``bass`` in one hand position."""
    from app.sonify.guitar_patterns import _position_ok

    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    best: tuple[int, list[int]] | None = None
    for start in range(lo, hi + 1):
        if start <= bass or not _playable_line(ctx, [bass, start]):
            continue
        line = [start]
        cursor = start
        for _ in range(count - 1):
            step = frame._step(cursor, 1, ctx.mode, lo, hi)
            if step == cursor or step <= cursor or not _playable_line(ctx, [bass, step]):
                break
            line.append(step)
            cursor = step
        if len(line) != count:
            continue
        if not _position_ok([pitch + ctx.semitones for pitch in line]):
            continue
        rank = abs(line[len(line) // 2] - (67 - ctx.semitones))
        if best is None or rank < best[0]:
            best = (rank, line)
    return [] if best is None else best[1]


def _bass_degree(frame, ctx, pc: int, ceiling: int | None, previous: int | None) -> int | None:
    high = frame._bass_hi(ctx)
    if ceiling is not None:
        high = min(high, ceiling - 1)
    found = _open_first(frame, ctx, _register_pool(ctx.bass_low, high, {pc % 12}))
    playable = []
    for midi in found:
        if previous is not None and previous - midi in {1, 2}:
            continue
        if ceiling is not None and not _playable_line(ctx, [midi, ceiling]):
            continue
        playable.append(midi)
    if playable:
        return playable[0]
    if found and previous is None:
        return found[0]
    return None


def _guard_bass(frame, ctx, specs: list[tuple]) -> list[tuple]:
    """A short bass may rise or leap. A step down after a long bass is a lament."""
    others = [item for item in specs if item[3] != 3]
    bass = sorted((item for item in specs if item[3] == 3), key=lambda item: (item[0], -item[1]))
    fixed = []
    previous = None
    for offset, length, midi, voice, velocity, flags in bass:
        if previous is not None:
            prev_len, prev_midi = previous
            if length <= 1 + _EPS and prev_len >= 2 - _EPS and prev_midi - midi in {1, 2}:
                uppers = [
                    item[2]
                    for item in others
                    if item[0] <= offset < item[0] + item[1] - _EPS
                ]
                ceiling = min(uppers) if uppers else None
                midi = _safe_bass_pitch(frame, ctx, prev_midi, None, ceiling, prev_midi)
        fixed.append(_note(offset, length, midi, voice, velocity, flags))
        previous = (length, midi)
    return others + fixed


def _brise_cell(
    frame,
    ctx,
    bar: int,
    pcs: list[int],
    start: int,
    span: int,
    velocity: int,
    *,
    pickup_into: bool = False,
    previous_bass: int | None = None,
) -> list[tuple]:
    """Legato style brisé. Support enters one eighth later. A pickup is four sixteenths."""
    if span <= 0 or start >= ctx.epb:
        return []
    span = min(span, ctx.epb - start)
    _root, _inner, lead = _stack_pitches(frame, ctx, pcs)
    bass = _bass_degree(frame, ctx, pcs[0], lead, previous_bass)
    if bass is None or not bass < lead:
        bass = _root
    held = max(1, span - (2 if pickup_into and span >= 3 else 0))
    specs = [
        _note(start, held, bass, 3, velocity),
        _note(start, held, lead, 1, velocity),
    ]
    support_length = min(2, span - 1 - (2 if pickup_into and span >= 3 else 0))
    if support_length > 0:
        tone = _under_lead(frame, ctx, lead, bass, None)
        if tone is None or not _playable_line(ctx, [bass, tone, lead]):
            members = {pc % 12 for pc in pcs}
            between = [
                midi
                for midi in range(max(bass + 1, frame._mid_lo(ctx)), min(lead, frame._mid_hi(ctx) + 1))
                if midi % 12 in members and _playable_line(ctx, [bass, midi, lead])
            ]
            tone = between[0] if between else None
        if tone is not None and bass < tone < lead and _playable_line(ctx, [bass, tone, lead]):
            specs.append(_note(start + 1, support_length, tone, 2, velocity))
    if pickup_into and span >= 3:
        tail = start + span - 2
        line = _scale_run(frame, ctx, bar, 4)
        for index, pitch in enumerate(line):
            specs.append(_note(tail + 0.5 * index, 0.5, pitch, 1, velocity))
    return specs


def _leap_pair(frame, ctx, pcs: list[int], bass: int, lead: int) -> tuple[int, int]:
    """A diatonic third. The lower note is the accent; the upper note is the staccato."""
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    pairs: list[tuple[int, int]] = []
    anchors = _register_pool(lo, hi, {pc % 12 for pc in pcs}) or [lead]
    for anchor in anchors:
        above = _scale_steps(frame, anchor, 2, ctx.mode, lo, hi)
        below = _scale_steps(frame, anchor, -2, ctx.mode, lo, hi)
        if abs(above - anchor) in {3, 4} and bass < anchor < above <= hi:
            pairs.append((anchor, above))
        if abs(anchor - below) in {3, 4} and lo <= below < anchor and bass < below:
            pairs.append((below, anchor))
    if lead > bass:
        above = _scale_steps(frame, lead, 2, ctx.mode, lo, hi)
        below = _scale_steps(frame, lead, -2, ctx.mode, lo, hi)
        if abs(above - lead) in {3, 4} and bass < lead < above:
            pairs.insert(0, (lead, above))
        if abs(lead - below) in {3, 4} and bass < below < lead:
            pairs.insert(0, (below, lead))
    for low_lead, leap_lead in pairs:
        if _playable_line(ctx, [bass, low_lead, leap_lead]):
            return low_lead, leap_lead
        if _playable_line(ctx, [bass, low_lead]) and _playable_line(ctx, [bass, leap_lead]):
            return low_lead, leap_lead
    if bass < lead:
        return lead, lead
    return lead, lead


def _courante_leap_cell(frame, ctx, pcs: list[int], velocity: int) -> list[tuple]:
    """Eighth 0 accent, eighth 1 staccato. On 6/8 the bass lasts through eighth 2."""
    kind = getattr(ctx, "kind", None)
    stacked, inner, lead = _stack_pitches(frame, ctx, pcs)
    low_lead, leap_lead = _leap_pair(frame, ctx, pcs, stacked, lead)
    bass_length = 3 if kind == "6/8" else 2
    specs = [
        _note(0, bass_length, stacked, 3, velocity, {"accent": True}),
        _note(0, 1, low_lead, 1, velocity, {"accent": True}),
        _note(1, 1, leap_lead, 1, velocity, {"staccato": True}),
    ]
    support = inner if inner is not None and stacked < inner < leap_lead else None
    if support is None or not _playable_line(ctx, [stacked, support, leap_lead]):
        support = _under_lead(frame, ctx, leap_lead, stacked, None)
    if support is not None and stacked < support < leap_lead and _playable_line(ctx, [stacked, support, leap_lead]):
        specs.append(_note(1, 1, support, 2, velocity))
    if kind == "6/8":
        specs.append(_note(2, 1, leap_lead, 1, velocity))
        if support is not None and stacked < support < leap_lead:
            specs.append(_note(2, 1, support, 2, velocity))
    return specs


def _courante_hold(
    frame,
    ctx,
    pcs: list[int],
    velocity: int,
    leap: list[tuple],
) -> list[tuple]:
    """Eighths after the leap bass, still on the same chord. No tirata."""
    del frame, pcs
    basses = [item for item in leap if item[3] == 3]
    leads = [item for item in leap if item[3] == 1]
    if not basses or not leads:
        return []
    bass = basses[0][2]
    cut = int(basses[0][0] + basses[0][1])
    pitch = leads[-1][2]
    if cut >= ctx.epb:
        return []
    specs = [_note(cut, ctx.epb - cut, bass, 3, velocity)]
    for offset in range(cut, ctx.epb):
        specs.append(_note(offset, 1, pitch, 1, velocity))
    return specs


def _fifth_bass(frame, ctx, pcs: list[int], previous: int | None) -> tuple[int, list[int]]:
    fifth = pcs[2] % 12 if len(pcs) > 2 else pcs[-1] % 12
    found = _open_first(frame, ctx, _register_pool(ctx.bass_low, frame._bass_hi(ctx), {fifth}))
    ordered = sorted(found, key=lambda midi: (previous is not None and previous - midi in {1, 2}, midi))
    for bass in ordered:
        if previous is not None and previous - bass in {1, 2}:
            continue
        line = _stepwise_line(frame, ctx, bass, 4)
        if line:
            return bass, line
    for bass in ordered:
        line = _stepwise_line(frame, ctx, bass, 4)
        if line:
            return bass, line
    fallback = ordered[0] if ordered else _stack_pitches(frame, ctx, pcs)[0]
    line = _stepwise_line(frame, ctx, fallback, 4)
    return fallback, line


def _pickup_bass(frame, ctx, pcs: list[int], previous: int, ceiling: int) -> int:
    root = _bass_degree(frame, ctx, pcs[0], ceiling, previous)
    if root is not None:
        return root
    same = _safe_bass_pitch(frame, ctx, previous, None, ceiling, previous)
    return same


def _courante_tirata_cell(
    frame,
    ctx,
    bar: int,
    pcs: list[int],
    velocity: int,
    *,
    into_body: bool = False,
    leap: list[tuple] | None = None,
) -> list[tuple]:
    """The middle sixteenths and the final eighth. Eighths the leap already holds stay untouched."""
    kind = getattr(ctx, "kind", None)
    leap = leap or []
    previous = None
    leap_basses = [item for item in leap if item[3] == 3]
    if leap_basses:
        previous = leap_basses[-1][2]
    leap_lead = None
    leap_leads = [item for item in leap if item[3] == 1]
    if leap_leads:
        leap_lead = leap_leads[-1][2]
    fifth, line = _fifth_bass(frame, ctx, pcs, previous)
    specs: list[tuple] = []
    if kind == "6/8":
        tirata_at = 3
        specs.append(_note(tirata_at, 2, fifth, 3, velocity, {"accent": True}))
        tail_lead = 5
        tail_bass = 5
    elif kind == "3/4":
        tirata_at = 2
        specs.append(_note(tirata_at, 2, fifth, 3, velocity))
        tail_lead = 4
        tail_bass = 5
    else:
        tirata_at = 4
        held = leap_lead if leap_lead is not None else (line[0] if line else fifth + 12)
        if held <= fifth:
            held = line[0] if line else held
        specs.append(_note(2, 2, previous if previous is not None else fifth, 3, velocity))
        specs.append(_note(2, 2, held, 1, velocity))
        support = _under_lead(frame, ctx, held, previous if previous is not None else fifth, None)
        if support is not None:
            specs.append(_note(3, 1, support, 2, velocity))
        specs.append(_note(tirata_at, 2, fifth, 3, velocity))
        tail_lead = 6
        tail_bass = 7
    for index, pitch in enumerate(line):
        specs.append(_note(tirata_at + 0.5 * index, 0.5, pitch, 1, velocity))
    staccato = line[-1] if line else leap_lead
    if staccato is not None and kind != "6/8":
        specs.append(_note(tail_lead, 1, staccato, 1, velocity, {"staccato": True}))
        support_bass = fifth
        tone = _under_lead(frame, ctx, staccato, support_bass, None)
        if tone is not None and tone < staccato:
            specs.append(_note(tail_lead, 1, tone, 2, velocity))
    pickup_lead = staccato if staccato is not None else (line[-1] if line else None)
    if into_body and pickup_lead is not None:
        pickup_lead = _aimed_lead(frame, ctx, bar, pickup_lead, fifth, [])
    elif pickup_lead is None and line:
        pickup_lead = line[-1]
    if pickup_lead is not None:
        bass = _pickup_bass(frame, ctx, pcs, fifth, pickup_lead)
        if bass >= pickup_lead:
            bass = fifth if fifth < pickup_lead else bass
        specs.append(_note(tail_bass, 1, pickup_lead, 1, velocity))
        specs.append(_note(tail_bass, 1, bass, 3, velocity))
    return specs


def _courante_hemiola_bar(frame, ctx, pcs: list[int], velocity: int) -> list[tuple]:
    """One chord. 4/4 has no hemiola. Eighth 5 stays free for the pickup."""
    kind = getattr(ctx, "kind", None)
    if kind not in {"3/4", "6/8"}:
        return []
    bass, inner, lead = _stack_pitches(frame, ctx, pcs)
    if kind == "3/4":
        attacks = [(0, 3, True), (3, 2, True), (5, 1, False)]
    else:
        attacks = [(0, 2, True), (2, 2, True), (4, 1, True), (5, 1, False)]
    specs: list[tuple] = []
    for offset, length, accent in attacks:
        flags = {"accent": True} if accent else {}
        specs.append(_note(offset, length, bass, 3, velocity, flags))
        specs.append(_note(offset, length, lead, 1, velocity, flags))
        if inner is not None and bass < inner < lead and _playable_line(ctx, [bass, inner, lead]):
            specs.append(_note(offset, length, inner, 2, velocity, flags))
    return specs


def _prelude_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    half = _half(ctx.epb)
    tonic = _harmony(frame, ctx, bar, "I")
    sub = _harmony(frame, ctx, bar, "IV")
    dominant = _harmony(frame, ctx, bar, "V7")
    root = ctx.chord(bar).pitches[0] % 12
    if not closing:
        if role == 0:
            specs = _prelude_roll(frame, ctx, bar, tonic, 0, half, frame._PP)
            specs.extend(_prelude_roll(frame, ctx, bar, tonic, half, ctx.epb - half, frame._P))
        elif role == 1 and short:
            specs = _prelude_roll(frame, ctx, bar, dominant, 0, half, frame._P, pedal_pc=root)
            specs.extend(
                _prelude_roll(
                    frame, ctx, bar, dominant, half, ctx.epb - half, frame._MP, lead_aim=True, pedal_pc=root
                )
            )
        elif role == 1:
            specs = _prelude_roll(frame, ctx, bar, sub, 0, half, frame._P, pedal_pc=root)
            specs.extend(_prelude_roll(frame, ctx, bar, sub, half, ctx.epb - half, frame._P, pedal_pc=root))
        elif role == 2:
            specs = _prelude_roll(frame, ctx, bar, dominant, 0, half, frame._MP, pedal_pc=root)
            specs.extend(_prelude_roll(frame, ctx, bar, dominant, half, ctx.epb - half, frame._MP, pedal_pc=root))
        else:
            specs = _prelude_roll(frame, ctx, bar, dominant, 0, half, frame._MP, pedal_pc=root)
            specs.extend(
                _prelude_roll(
                    frame, ctx, bar, dominant, half, ctx.epb - half, 58, lead_aim=True, pedal_pc=root
                )
            )
        return _guard_bass(frame, ctx, specs)
    if short:
        if role == 0:
            specs = _prelude_roll(frame, ctx, bar, dominant, 0, half, frame._MP)
            specs.extend(
                _prelude_roll(frame, ctx, bar, dominant, half, ctx.epb - half, frame._P, eighth_grid=True)
            )
            return _guard_bass(frame, ctx, specs)
        return frame._bach_block(ctx, bar, "I", frame._P)
    if role == 0:
        specs = _prelude_roll(frame, ctx, bar, sub, 0, half, frame._MP)
        specs.extend(_prelude_roll(frame, ctx, bar, sub, half, ctx.epb - half, frame._MP))
        return _guard_bass(frame, ctx, specs)
    if role == 1:
        specs = _prelude_roll(frame, ctx, bar, dominant, 0, half, frame._P)
        specs.extend(_prelude_roll(frame, ctx, bar, dominant, half, ctx.epb - half, frame._P, eighth_grid=True))
        return _guard_bass(frame, ctx, specs)
    if role == 2:
        return frame._bach_arpeggiato(ctx, bar, "I", frame._P)
    return frame._bach_block(ctx, bar, "I", frame._PP)


def _allemande_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    half = _half(ctx.epb)
    tonic = _harmony(frame, ctx, bar, "I")
    sub = _harmony(frame, ctx, bar, "IV")
    dominant = _harmony(frame, ctx, bar, "V7")
    if not closing:
        if role == 0 and short:
            specs = _brise_cell(frame, ctx, bar, tonic, 0, half, frame._P)
            previous = next(item[2] for item in reversed(specs) if item[3] == 3)
            specs.extend(_brise_cell(frame, ctx, bar, tonic, half, ctx.epb - half, frame._P, pickup_into=True, previous_bass=previous))
        elif role == 0:
            bass, _inner, _lead = _stack_pitches(frame, ctx, tonic)
            specs = [_note(0, half, bass, 3, frame._PP)]
            for index, pitch in enumerate(_scale_run(frame, ctx, bar, 4)):
                specs.append(_note(ctx.epb - 2 + 0.5 * index, 0.5, pitch, 1, frame._P))
        elif role == 1 and short:
            specs = _brise_cell(frame, ctx, bar, sub, 0, half, frame._P)
            previous = next(item[2] for item in reversed(specs) if item[3] == 3)
            specs.extend(
                _brise_cell(
                    frame, ctx, bar, dominant, half, ctx.epb - half, frame._MP, pickup_into=True, previous_bass=previous
                )
            )
        elif role == 1:
            specs = _brise_cell(frame, ctx, bar, tonic, 0, half, frame._P)
            previous = next(item[2] for item in reversed(specs) if item[3] == 3)
            specs.extend(_brise_cell(frame, ctx, bar, sub, half, ctx.epb - half, frame._P, previous_bass=previous))
        elif role == 2:
            specs = _brise_cell(frame, ctx, bar, dominant, 0, half, frame._MP)
            bass, inner, lead = _stack_pitches(frame, ctx, dominant)
            first = next(item[2] for item in specs if item[3] == 3)
            specs.append(_note(half, ctx.epb - half, first, 3, frame._MP))
            tone = inner if inner is not None and first < inner < lead else None
            specs.extend(_mordent(frame, ctx, half, lead, first, tone, frame._MP, sustain_to=ctx.epb))
        else:
            specs = _brise_cell(frame, ctx, bar, tonic, 0, half, frame._MP)
            previous = next(item[2] for item in reversed(specs) if item[3] == 3)
            specs.extend(
                _brise_cell(
                    frame, ctx, bar, dominant, half, ctx.epb - half, frame._MP, pickup_into=True, previous_bass=previous
                )
            )
        return _guard_bass(frame, ctx, specs)
    if short:
        if role == 0:
            specs = _brise_cell(frame, ctx, bar, sub, 0, half, frame._MP)
            previous = next(item[2] for item in reversed(specs) if item[3] == 3)
            specs.extend(_brise_cell(frame, ctx, bar, dominant, half, ctx.epb - half, frame._MP, previous_bass=previous))
            return _guard_bass(frame, ctx, specs)
        return frame._bach_block(ctx, bar, "I", frame._P)
    if role == 0:
        specs = _brise_cell(frame, ctx, bar, sub, 0, half, frame._P)
        previous = next(item[2] for item in reversed(specs) if item[3] == 3)
        specs.extend(_brise_cell(frame, ctx, bar, tonic, half, ctx.epb - half, frame._P, previous_bass=previous))
        return _guard_bass(frame, ctx, specs)
    if role == 1:
        specs = _brise_cell(frame, ctx, bar, dominant, 0, half, frame._MP)
        bass, inner, lead = _stack_pitches(frame, ctx, dominant)
        first = next(item[2] for item in specs if item[3] == 3)
        specs.append(_note(half, ctx.epb - half, first, 3, frame._MP))
        tone = inner if inner is not None and first < inner < lead else None
        specs.extend(_mordent(frame, ctx, half, lead, first, tone, frame._MP, sustain_to=ctx.epb))
        return _guard_bass(frame, ctx, specs)
    if role == 2:
        return _suspension(frame, ctx, bar, frame._P)
    return frame._bach_block(ctx, bar, "I", frame._PP)


def _courante_specs(frame, ctx, bar: int, role: int, *, short: bool, closing: bool) -> list[tuple]:
    role = min(role, 1 if short else 3)
    kind = getattr(ctx, "kind", None)
    tonic = _harmony(frame, ctx, bar, "I")
    sub = _harmony(frame, ctx, bar, "IV")
    dominant = _harmony(frame, ctx, bar, "V7")
    if not closing:
        if role == 0:
            leap = _courante_leap_cell(frame, ctx, tonic, frame._P)
            specs = [*leap, *_courante_hold(frame, ctx, tonic, frame._P, leap)]
        elif role == 1 and short:
            leap = _courante_leap_cell(frame, ctx, dominant, frame._MP)
            specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, dominant, frame._MP, into_body=True, leap=leap)]
        elif role == 1:
            leap = _courante_leap_cell(frame, ctx, sub, frame._P)
            specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, sub, frame._P, leap=leap)]
        elif role == 2:
            leap = _courante_leap_cell(frame, ctx, dominant, frame._MP)
            specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, dominant, frame._MP, leap=leap)]
        else:
            leap = _courante_leap_cell(frame, ctx, dominant, frame._MP)
            specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, dominant, 58, into_body=True, leap=leap)]
        return _guard_bass(frame, ctx, specs)
    if short:
        if role == 0:
            if kind in {"3/4", "6/8"}:
                specs = _courante_hemiola_bar(frame, ctx, dominant, frame._MP)
            else:
                leap = _courante_leap_cell(frame, ctx, dominant, frame._MP)
                specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, dominant, frame._MP, leap=leap)]
            return _guard_bass(frame, ctx, specs)
        return _chord(frame, ctx, tonic, 0, ctx.epb, frame._P, {"accent": True})
    if role == 0:
        leap = _courante_leap_cell(frame, ctx, sub, frame._MP)
        specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, sub, frame._MP, leap=leap)]
    elif role == 1:
        leap = _courante_leap_cell(frame, ctx, dominant, frame._MP)
        specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, dominant, frame._MP, leap=leap)]
    elif role == 2:
        if kind in {"3/4", "6/8"}:
            specs = _courante_hemiola_bar(frame, ctx, dominant, frame._P)
        else:
            leap = _courante_leap_cell(frame, ctx, dominant, frame._P)
            specs = [*leap, *_courante_tirata_cell(frame, ctx, bar, dominant, frame._P, leap=leap)]
    else:
        return frame._bach_block(ctx, bar, "I", frame._P)
    return _guard_bass(frame, ctx, specs)


def _run(builder, ctx, bar, role, *, steps, closing, index):
    del index
    frame = _frame()
    short = steps <= 2
    specs = builder(frame, ctx, bar, role, short=short, closing=closing)
    allow_lament = builder is _elegiaque_specs
    return _finish(frame, ctx, bar, specs, allow_lament=allow_lament)


def bach_gavotte(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Half-bar gavotte quarters in thirds or sixths, then a tonic block at _P."""
    return _run(_gavotte_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def bach_gigue(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """6/8 broken chords; the dominant flourish belongs only to the gigue."""
    return _run(_gigue_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def bach_sarabande(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Beat 2 carries the sarabande. Minor cadences stay minor."""
    return _run(_sarabande_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def bach_chaconne(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Ground bass, bariolage, and the tetrachord and arpeggio that left the other dances."""
    return _run(_chaconne_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def bach_prelude(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Half-bar sixteenth rolls. The last bar stays on V7 and aims into the body."""
    return _run(_prelude_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def bach_allemande(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Legato style brisé, a four-sixteenth pickup, then a 4–3 suspension."""
    return _run(_allemande_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def bach_courante(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Opening leap, tirata, and a hemiola only in 3/4 and 6/8."""
    return _run(_courante_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def cantabile(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Parallel thirds and sixths. No dotted overture rhythm."""
    return _run(_cantabile_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def elegiaque(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """March bass with a lament step. A chromatic approach has to be that lament."""
    return _run(_elegiaque_specs, ctx, bar, role, steps=steps, closing=closing, index=index)


def galop(ctx, bar, role, *, steps: int, closing: bool, index: int):
    """Staccato galop. The last step is an accented chord at _MF, not a held pianissimo block."""
    return _run(_galop_hits, ctx, bar, role, steps=steps, closing=closing, index=index)


DOORS: dict[tuple[str, str], Callable] = {
    ("bach", "bach_gavotte"): bach_gavotte,
    ("bach", "bach_gigue"): bach_gigue,
    ("bach", "bach_sarabande"): bach_sarabande,
    ("bach", "bach_chaconne"): bach_chaconne,
    ("bach", "bach_prelude"): bach_prelude,
    ("bach", "bach_allemande"): bach_allemande,
    ("bach", "bach_courante"): bach_courante,
    ("classic", "cantabile"): cantabile,
    ("classic", "elegiaque"): elegiaque,
    ("classic", "galop"): galop,
}
