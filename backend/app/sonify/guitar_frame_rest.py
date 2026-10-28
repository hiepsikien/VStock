"""Intro and outro doors for the Barrios, Villa-Lobos, and Brouwer patterns
that do not keep the shared composer frame.

Each door is one bar of one script step. A repeated role is the same bar:
nothing here reads ``index``. Helpers come from ``guitar_frame`` when the
door runs, so this module can be wired in later without an import cycle.
"""

from __future__ import annotations

from collections.abc import Callable

# A sextuplet sixth. One quarter is two eighths, and Étude No. 11 puts six
# notes in that quarter. The duration is a hair under 1/3 so float error cannot
# make two slots overlap; onsets stay on slot/3. This is never a thirty-second.
_SIXTH = 1 / 3
_SIXTH_LEN = _SIXTH - 1e-6


def _andante(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _andante_bar(frame, ctx, bar, role, steps, closing)


def _tremolo(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _tremolo_bar(frame, ctx, bar, role, steps, closing)


def _choro(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _choro_bar(frame, ctx, bar, role, steps, closing)


def _polca(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _polca_bar(frame, ctx, bar, role, steps, closing)


def _hemiola(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _hemiola_bar(frame, ctx, bar, role, steps, closing)


def _vals(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _vals_bar(frame, ctx, bar, role, steps, closing)


def _barrios_thumb(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _thumb_bar(frame, ctx, bar, role, steps, closing, arrive=False)


def _chord_melody(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _chord_melody_bar(frame, ctx, bar, role, steps, closing)


def _villa_thumb(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _thumb_bar(frame, ctx, bar, role, steps, closing, arrive=True)


def _etude1(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _etude1_bar(frame, ctx, bar, role, steps, closing)


def _etude11(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _etude11_bar(frame, ctx, bar, role, steps, closing)


def _brouwer_etude(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _brouwer_etude_bar(frame, ctx, bar, role, steps, closing)


def _sarabande(ctx, bar, role, *, steps: int, closing: bool, index: int) -> list[tuple]:
    import app.sonify.guitar_frame as frame

    _ = index
    return _sarabande_bar(frame, ctx, bar, role, steps, closing)


DOORS: dict[tuple[str, str], Callable] = {
    ("barrios", "andante"): _andante,
    ("barrios", "tremolo"): _tremolo,
    ("barrios", "choro"): _choro,
    ("barrios", "polca"): _polca,
    ("barrios", "hemiola"): _hemiola,
    ("barrios", "vals"): _vals,
    ("barrios", "thumb_cantabile"): _barrios_thumb,
    ("villa", "chord_melody"): _chord_melody,
    ("villa", "thumb_cantabile"): _villa_thumb,
    ("villa", "etude1"): _etude1,
    ("villa", "etude11"): _etude11,
    ("brouwer", "brouwer_etude"): _brouwer_etude,
    ("brouwer", "sarabande"): _sarabande,
}


def _role(steps: int, role: int) -> int:
    if steps <= 2:
        return 0 if role <= 0 else 1
    return min(3, max(0, role))


def _finish(frame, ctx, specs: list[tuple]) -> list[tuple]:
    epb = ctx.epb
    cleaned = []
    for offset, length, midi, voice, velocity, flags in specs:
        if midi is None or voice not in (1, 2, 3):
            continue
        if length <= 0 or offset < 0 or offset >= epb:
            continue
        if offset + length > epb:
            length = epb - offset
        if length <= 0:
            continue
        cleaned.append((offset, length, int(midi), voice, int(velocity), dict(flags or {})))
    done = frame._clip_voice(cleaned, epb)
    if done:
        return done
    bass, inner, lead = frame._stack(ctx, frame._function(ctx, 0, "I"))
    return frame._clip_voice(_chord(0, epb, bass, inner, lead, frame._P), epb)


def _harmony(frame, ctx, bar: int, name: str) -> list[int]:
    """Mode-true harmony. Minor tonic stays minor: no Picardy third."""
    root = ctx.chord(bar).pitches[0] % 12
    minor = ctx.mode == "minor"
    if name == "VI":
        step = 8 if minor else 9
        third = 4 if minor else 3
        sub = (root + step) % 12
        return [sub, (sub + third) % 12, (sub + 7) % 12]
    if name == "sus2":
        return frame._sus2(ctx, bar)
    if name == "sus4":
        return [root, (root + 5) % 12, (root + 7) % 12]
    if name == "add9":
        third = 3 if minor else 4
        return [root, (root + 2) % 12, (root + third) % 12, (root + 7) % 12]
    if name == "I6":
        triad = frame._function(ctx, bar, "I")
        sixth = (root + (8 if minor else 9)) % 12
        return [*triad, sixth]
    if name == "color-":
        shifted = (root - 2) % 12
        return [shifted, (shifted + 2) % 12, (shifted + 7) % 12]
    return frame._function(ctx, bar, name)


def _lerp(start: int, end: int, count: int, index: int) -> int:
    if count <= 1:
        return int(start)
    return int(round(start + (end - start) * index / (count - 1)))


def _playable(ctx, notes: list[int]) -> bool:
    from app.sonify.guitar_patterns import _playable as hands

    return hands([note + ctx.semitones for note in notes])


def _chord(offset, length, bass, inner, lead, velocity, flags=None) -> list[tuple]:
    if lead <= bass:
        return [(offset, length, bass, 3, velocity, dict(flags or {}))]
    mark = dict(flags or {})
    specs = [
        (offset, length, bass, 3, velocity, dict(mark)),
        (offset, length, lead, 1, velocity, dict(mark)),
    ]
    if inner is not None and bass < inner < lead:
        specs.append((offset, length, inner, 2, velocity, dict(mark)))
    return specs


def _voicing(frame, ctx, bar: int, name: str, *, shift: int = 0, color: bool = False, floor: int | None = None):
    pcs = _harmony(frame, ctx, bar, name)
    bass, inner, lead = frame._stack(ctx, pcs, shift=shift, lead_floor=floor)
    if color:
        tinted = _color_inner(frame, ctx, pcs[0], bass, lead)
        if tinted is not None:
            inner = tinted
    return bass, inner, lead


def _color_inner(frame, ctx, root_pc: int, bass: int, lead: int) -> int | None:
    """2/5/10, then a third or seventh, between the two outer voices."""
    wanted = [(root_pc + step) % 12 for step in (2, 5, 10, 3, 4, 11)]
    for pc in wanted:
        for note in range(frame._mid_hi(ctx), frame._mid_lo(ctx) - 1, -1):
            if note % 12 != pc or not bass < note < lead:
                continue
            if _playable(ctx, [bass, note, lead]):
                return note
    return None


def _pair_grid(ctx) -> list[tuple[int, int]]:
    """Two block chords. 6/8 is [0, 3]; 4/4 and 3/4 are [0, 4]."""
    epb = ctx.epb
    if epb <= 1:
        return [(0, epb)]
    if getattr(ctx, "kind", "") == "6/8":
        cut = min(3, epb - 1)
        return [(0, cut), (cut, epb - cut)]
    if epb > 4:
        return [(0, 4), (4, epb - 4)]
    cut = max(1, epb // 2)
    return [(0, cut), (cut, epb - cut)]


def _halves(ctx) -> list[tuple[int, int]]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    if cut >= epb:
        return [(0, epb)]
    return [(0, cut), (cut, epb - cut)]


def _quarters(epb: int) -> list[int]:
    """One attack per quarter. 3/4 and 6/8 (epb 6) stay on 0, 2, 4."""
    return [offset for offset in range(0, epb, 2) if offset < epb]


def _beat(ctx, number: int) -> int | None:
    """1-based beat as an eighth. 6/8 has two dotted beats."""
    epb = ctx.epb
    if getattr(ctx, "kind", "") == "6/8":
        offset = 0 if number <= 1 else 3
    else:
        offset = (number - 1) * 2
    if offset < 0 or offset >= epb:
        return None
    return offset


def _thumb_points(ctx) -> tuple[int, ...]:
    epb = ctx.epb
    kind = getattr(ctx, "kind", "")
    if kind == "6/8":
        points = (2, 5)
    elif kind == "3/4" or epb == 6:
        points = (2, 4)
    else:
        points = (2, 6)
    return tuple(point for point in points if point < epb)


def _thumb_hi(ctx) -> int:
    return 64 - ctx.semitones


def _thumb_lo(ctx) -> int:
    return 48 - ctx.semitones


def _ahead(ctx, bar: int) -> int | None:
    melody = getattr(ctx, "melody", None) or []
    index = (bar + 1) * ctx.epb
    if 0 <= index < len(melody):
        return melody[index]
    return None


def _fold_thumb(ctx, pitch: int | None) -> int:
    lo, hi = _thumb_lo(ctx), _thumb_hi(ctx)
    if pitch is None:
        return min(hi, max(lo, 55 - ctx.semitones))
    while pitch < lo and pitch + 12 <= hi:
        pitch += 12
    while pitch > hi and pitch - 12 >= lo:
        pitch -= 12
    if pitch < lo:
        return lo
    if pitch > hi:
        return hi
    return pitch


def _lay(frame, ctx, bar, plan, *, color: bool = False, stepwise: bool = False, semitone: bool = False) -> list[tuple]:
    """Place block chords. ``plan`` is (offset, length, name, velocity, flags)."""
    previous_lead = None
    previous_inner = None
    specs: list[tuple] = []
    for offset, length, name, velocity, flags in plan:
        if offset >= ctx.epb or length <= 0:
            continue
        bass, inner, lead = _voicing(frame, ctx, bar, name, color=color)
        if stepwise and previous_lead is not None:
            bass, inner, lead = _step_lead(frame, ctx, previous_lead, bass, inner, lead, _harmony(frame, ctx, bar, name))
        if semitone and previous_inner is not None:
            inner = _semitone_inner(ctx, previous_inner, bass, lead, inner)
        specs.extend(_chord(offset, min(length, ctx.epb - offset), bass, inner, lead, velocity, flags))
        previous_lead = lead
        previous_inner = inner
    return specs


def _step_lead(frame, ctx, previous: int, bass: int, inner, lead: int, pcs: list[int]):
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    pool = set(pcs)
    candidates = []
    for direction in (1, -1):
        stepped = frame._step(previous, direction, ctx.mode, lo, hi)
        if stepped != previous and stepped > bass:
            candidates.append(stepped)
    candidates.sort(key=lambda note: (note % 12 not in pool, abs(note - previous)))
    for stepped in candidates:
        between = frame._between(ctx, pcs, bass, stepped)
        if between is not None and not bass < between < stepped:
            between = None
        voices = [bass, stepped] if between is None else [bass, between, stepped]
        if _playable(ctx, voices):
            return bass, between, stepped
    return bass, inner, lead


def _semitone_inner(ctx, previous: int, bass: int, lead: int, fallback):
    for nudged in (previous + 1, previous - 1):
        if bass < nudged < lead and _playable(ctx, [bass, nudged, lead]):
            return nudged
    return fallback


def _open_pitches(frame, ctx, low: int, high: int) -> list[int]:
    found = []
    for sounding in (40, 45, 50, 55, 59, 64):
        written = frame._open_written(ctx, sounding)
        if low <= written <= high:
            found.append(written)
    return found


def _open_bass(frame, ctx, pc: int | None = None) -> int:
    matches = [note for note in _open_pitches(frame, ctx, ctx.bass_low, frame._bass_hi(ctx)) if pc is None or note % 12 == pc]
    if matches:
        return matches[0]
    if pc is None:
        return frame._deep_open(ctx)
    return frame._bass_note(ctx, pc, None)


def _low_pc(frame, ctx, pc: int, ceiling: int, *upper: int) -> int | None:
    high = min(frame._bass_hi(ctx), ceiling - 1)
    notes = frame._pcs_in(pc, ctx.bass_low, high)
    notes.sort(key=lambda note: (not frame._is_open(ctx, note), note))
    for note in notes:
        if any(note >= other for other in upper):
            continue
        if _playable(ctx, [note, *upper]):
            return note
    return None


def _dyad(frame, ctx, sung: int, pcs: list[int]) -> tuple[int | None, int | None]:
    colors = set(pcs) or set(frame._classes(ctx.mode))
    inners = [
        note
        for note in range(frame._mid_lo(ctx), frame._mid_hi(ctx) + 1)
        if note > sung and note % 12 in colors
    ]
    leads = [
        note
        for note in range(frame._lead_lo(ctx), frame._lead_hi(ctx) + 1)
        if note > sung and note % 12 in colors
    ]
    for inner in inners:
        for lead in leads:
            if sung < inner < lead and _playable(ctx, [sung, inner, lead]):
                return inner, lead
    for lead in leads:
        if lead > sung and _playable(ctx, [sung, lead]):
            return None, lead
    return None, None


def _by_tone(pitch: int, direction: int, low: int, high: int) -> int:
    """One or two semitones, never a wider leap."""
    for size in (2, 1):
        nxt = pitch + direction * size
        if low <= nxt <= high:
            return nxt
    return pitch


def _swarm(start: int, count: int, pitch: int, direction: int, low: int, high: int) -> list[tuple[int, int]]:
    notes = []
    cursor = min(high, max(low, pitch))
    for step in range(count):
        at = start + step
        notes.append((at, cursor))
        cursor = _by_tone(cursor, direction, low, high)
    return notes


def _repeats(start: float, count: int, pitch: int, v0: int, v1: int, epb: int) -> list[tuple]:
    specs = []
    for index in range(count):
        offset = start + index * 0.5
        if offset >= epb:
            break
        specs.append((offset, 0.5, pitch, 1, _lerp(v0, v1, count, index), {}))
    return specs


def _andante_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    grid = _pair_grid(ctx)
    halves = _halves(ctx)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "I", frame._P, None),
            (*grid[1], "IV", frame._P, None),
        )))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "ii", frame._P, None),
            (*grid[1], "V7", frame._MP, None),
        ), stepwise=True))
    if not closing and role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, ctx.epb, "I", frame._PP, None),)))
    if not closing and role == 1:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*halves[0], "IV", frame._P, None),
            (*halves[1], "I", frame._P, None),
        )))
    if not closing and role == 2:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "ii", frame._MP, None),
            (*grid[1], "V7", frame._MP, None),
        ), semitone=True))
    if not closing:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "I", frame._P, None),
            (*grid[1], "V7", frame._P, None),
        )))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*halves[0], "IV", frame._P, None),
            (*halves[1], "I", frame._P, None),
        )))
    if steps <= 2:
        return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, ctx.epb, "I", frame._PP, None),)))
    if role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "I", frame._P, None),
            (*grid[1], "VI", frame._P, None),
        )))
    if role == 1:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "ii", frame._P, None),
            (*grid[1], "V7", frame._P, None),
        )))
    if role == 2:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*halves[0], "IV", frame._PP, None),
            (*halves[1], "I", frame._PP, None),
        )))
    return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, ctx.epb, "I", frame._PP, None),)))


def _degree_lead(frame, ctx, bar, name: str, degrees: set[int]) -> tuple[int, int | None, int]:
    root = ctx.chord(bar).pitches[0] % 12
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    wanted = {(root + degree) % 12 for degree in degrees}
    if lead % 12 in wanted:
        return bass, inner, lead
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    pcs = _harmony(frame, ctx, bar, name)
    for note in range(hi, lo - 1, -1):
        if note % 12 not in wanted or note <= bass:
            continue
        between = frame._between(ctx, pcs, bass, note)
        voices = [bass, note] if between is None else [bass, between, note]
        if between is not None and not bass < between < note:
            continue
        if _playable(ctx, voices):
            return bass, between, note
    return bass, inner, lead


def _tremolo_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    epb = ctx.epb
    half = epb / 2
    if not closing and steps <= 2 and role == 0:
        bass, _inner, lead = _voicing(frame, ctx, bar, "I")
        return _finish(frame, ctx, [(0, epb, bass, 3, frame._P, {}), (0, epb, lead, 1, frame._P, {})])
    if not closing and steps <= 2:
        bass, _inner, lead = _voicing(frame, ctx, bar, "V7")
        specs = [(0, epb, bass, 3, frame._P, {}), (0, half, lead, 1, frame._P, {})]
        specs.extend(_repeats(half, epb, lead, 48, 58, epb))
        return _finish(frame, ctx, specs)
    if not closing and role == 0:
        return _finish(frame, ctx, _rising_bar(frame, ctx, bar, "I", frame._PP, frame._P))
    if not closing and role == 1:
        return _finish(frame, ctx, _two_sustains(frame, ctx, bar, "ii", frame._P))
    if not closing and role == 2:
        bass, _inner, lead = _degree_lead(frame, ctx, bar, "V7", {7, 11})
        return _finish(frame, ctx, [(0, epb, bass, 3, frame._MP, {}), (0, epb, lead, 1, frame._MP, {})])
    if not closing:
        bass, _inner, lead = _degree_lead(frame, ctx, bar, "V7", {7, 11})
        specs = [(0, epb, bass, 3, frame._MP, {}), (0, half, lead, 1, frame._MP, {})]
        specs.extend(_repeats(half, epb, lead, frame._MP, 60, epb))
        return _finish(frame, ctx, specs)
    if steps <= 2 and role == 0:
        bass, _inner, lead = _voicing(frame, ctx, bar, "I")
        specs = [(0, epb, bass, 3, frame._P, {})]
        specs.extend(_repeats(0, epb, lead, 54, 50, epb))
        for offset in range(epb // 2, epb):
            specs.append((offset, 1, lead, 1, _lerp(54, 46, epb, offset), {}))
        return _finish(frame, ctx, specs)
    if steps <= 2:
        _bass, _inner, lead = _voicing(frame, ctx, bar, "I")
        return _finish(frame, ctx, [(0, epb, lead, 1, frame._PP, {})])
    if role == 0:
        bass, _inner, lead = _voicing(frame, ctx, bar, "I")
        lower = frame._step(bass, -1, ctx.mode, ctx.bass_low, frame._bass_hi(ctx))
        if not lower < lead:
            lower = bass
        cut = max(1, epb // 2)
        specs = [
            (0, cut, bass, 3, frame._P, {}),
            (cut, epb - cut, lower, 3, frame._P, {}),
        ]
        specs.extend(_repeats(0, epb, lead, frame._P, frame._P, epb))
        for offset in range(epb // 2, epb):
            specs.append((offset, 1, lead, 1, frame._P, {}))
        return _finish(frame, ctx, specs)
    if role == 1:
        return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, epb, "ii", frame._P, None),)))
    if role == 2:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*_halves(ctx)[0], "V7", frame._PP, None),
            (*_halves(ctx)[1], "I", frame._PP, None),
        )))
    return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, epb, "I", frame._PP, None),)))


def _rising_bar(frame, ctx, bar, name: str, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    cursor = lead
    for _ in range(max(0, epb - 1)):
        nxt = frame._step(cursor, -1, ctx.mode, lo, hi)
        if nxt >= cursor or nxt <= bass:
            break
        cursor = nxt
    specs = [*_split_bass(bass, epb, v0, v1)]
    for offset in range(epb):
        specs.append((offset, 1, cursor, 1, _lerp(v0, v1, epb, offset), {}))
        nxt = frame._step(cursor, 1, ctx.mode, lo, hi)
        if nxt > bass:
            cursor = nxt
    if inner is not None and bass < inner < lead and epb > 2:
        specs.append((1, 1, inner, 2, v0, {}))
    return specs


def _split_bass(bass: int, epb: int, v0: int, v1: int) -> list[tuple]:
    cut = max(1, epb // 2)
    if cut >= epb:
        return [(0, epb, bass, 3, v0, {})]
    return [(0, cut, bass, 3, v0, {}), (cut, epb - cut, bass, 3, v1, {})]


def _two_sustains(frame, ctx, bar, name: str, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    cut = max(1, epb // 2)
    second = frame._step(lead, 1, ctx.mode, frame._lead_lo(ctx), frame._lead_hi(ctx))
    if second <= bass:
        second = lead
    specs = [(0, epb, bass, 3, velocity, {})]
    if cut < epb:
        specs.append((0, cut, lead, 1, velocity, {}))
        specs.append((cut, epb - cut, second, 1, velocity, {}))
    else:
        specs.append((0, epb, lead, 1, velocity, {}))
    if inner is not None and bass < inner < min(lead, second):
        specs.append((0, min(2, epb), inner, 2, velocity, {}))
    return specs


def _choro_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(
            frame, ctx, _choro_bed(frame, ctx, bar, "I6", frame._P, frame._MP, anticipations=True)
        )
    if not closing and steps <= 2:
        specs = _choro_bed(frame, ctx, bar, "V7", frame._MP, frame._MP, limit=ctx.epb / 2)
        specs.extend(_choro_run(frame, ctx, bar, frame._MP, approach=True))
        return _finish(frame, ctx, specs)
    if not closing and role == 0:
        return _finish(frame, ctx, _choro_bed(frame, ctx, bar, "I6", frame._P, frame._P))
    if not closing and role == 1:
        return _finish(frame, ctx, _choro_offbeat_lead(frame, ctx, bar, ("I", "ii"), frame._MP))
    if not closing and role == 2:
        return _finish(frame, ctx, _choro_bed(frame, ctx, bar, "V7", frame._MP, frame._MP))
    if not closing:
        landing = _approach(frame, ctx, bar, frame._MF)
        specs = [item for item in _choro_bed(frame, ctx, bar, "V7", frame._MF, frame._MF) if item[3] != 2]
        if landing:
            specs = _clear_tail(specs, ctx.epb - 1)
        specs.extend(frame._scale_into(ctx, bar, 0, max(1, ctx.epb - (1 if landing else 0)), frame._MF))
        specs.extend(landing)
        return _finish(frame, ctx, specs)
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _choro_bed(frame, ctx, bar, "V7", frame._MP, frame._MP))
    if steps <= 2:
        return _finish(frame, ctx, _choro_close(frame, ctx, bar, frame._MF))
    if role == 0:
        return _finish(frame, ctx, _choro_halves(frame, ctx, bar, ("I", "ii"), frame._MP))
    if role == 1:
        return _finish(frame, ctx, _choro_bed(frame, ctx, bar, "V7", frame._MP, frame._MP))
    if role == 2:
        return _finish(frame, ctx, _choro_down(frame, ctx, bar))
    return _finish(frame, ctx, _choro_close(frame, ctx, bar, frame._MF))


def _choro_points(epb: int) -> list[float]:
    """Inner sixteenths: slots 3, 6, 7 and 11, 14, 15."""
    return [slot / 2 for slot in (3, 6, 7, 11, 14, 15) if slot / 2 < epb]


def _choro_bed(
    frame, ctx, bar, name, v0, v1, *, limit: float | None = None, anticipations: bool = False
) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    root = _harmony(frame, ctx, bar, name)[0]
    fifth = _harmony(frame, ctx, bar, name)[2] if len(_harmony(frame, ctx, bar, name)) > 2 else root
    ceiling = inner if inner is not None else lead
    root_bass = _low_pc(frame, ctx, root, ceiling, ceiling) or bass
    fifth_bass = _low_pc(frame, ctx, fifth, ceiling, ceiling) or root_bass
    specs = []
    attacks = [offset for offset in (0, 2, 4, 6) if offset < epb and (limit is None or offset < limit)]
    for index, offset in enumerate(attacks):
        nxt = attacks[index + 1] if index + 1 < len(attacks) else epb
        if limit is not None:
            nxt = min(nxt, int(limit))
        pitch = root_bass if index % 2 == 0 else fifth_bass
        length = max(1, nxt - offset)
        specs.append((offset, length, pitch, 3, _lerp(v0, v1, max(1, len(attacks)), index), {}))
    if anticipations:
        # The sixteenth before each beat. The accented off-beats arrive with the full cell.
        points = [slot / 2 for slot in (3, 7, 11, 15) if slot / 2 < epb and (limit is None or slot / 2 < limit)]
        accent_slots: set[int] = set()
    else:
        points = [point for point in _choro_points(epb) if limit is None or point < limit]
        accent_slots = {6, 7, 14, 15}
    for index, offset in enumerate(points):
        if inner is None or not (max(root_bass, fifth_bass) < inner < lead):
            break
        slot = int(round(offset * 2))
        flags = {"accent": True} if slot in accent_slots else {}
        specs.append((offset, 0.5, inner, 2, _lerp(v0, v1, max(1, len(points)), index), flags))
    return specs


def _fifth_lower(ctx, bar: int) -> bool:
    """The next root is a perfect fifth under this bar's root."""
    if bar + 1 >= getattr(ctx, "bars", 0):
        return False
    current = ctx.chord(bar).pitches[0] % 12
    nxt = ctx.chord(bar + 1).pitches[0] % 12
    return (current - nxt) % 12 == 7


def _choro_run(frame, ctx, bar, velocity: int, *, approach: bool) -> list[tuple]:
    epb = ctx.epb
    start = max(1, epb // 2)
    landing = _approach(frame, ctx, bar, velocity) if approach else []
    count = max(1, epb - start - (1 if landing else 0))
    specs = list(frame._scale_into(ctx, bar, start, count, velocity))
    specs.extend(landing)
    return specs


def _approach(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Voice 3, a semitone under the next root, only when that root is a fifth lower."""
    epb = ctx.epb
    if epb < 2 or not _fifth_lower(ctx, bar):
        return []
    root = ctx.chord(bar + 1).pitches[0] % 12
    pitch = frame._bass_note(ctx, (root - 1) % 12, frame._lead_lo(ctx))
    return [(epb - 1, 1, pitch, 3, velocity, {})]


def _choro_offbeat_lead(frame, ctx, bar, names: tuple[str, str], velocity: int) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    specs = []
    for name, start, end in ((names[0], 0, cut), (names[1], cut, epb)):
        bass, inner, lead = _voicing(frame, ctx, bar, name)
        if end > start:
            specs.append((start, end - start, bass, 3, velocity, {}))
        for offset in range(start + 1, end, 2):
            specs.append((offset, 1, lead, 1, velocity, {}))
            if inner is not None and bass < inner < lead and offset + 1 <= end:
                specs.append((offset, 1, inner, 2, velocity, {}))
    return specs


def _clear_tail(specs: list[tuple], cut: int) -> list[tuple]:
    """Shorten voice 3 so a chromatic approach can land on the last eighth."""
    cleared = []
    for offset, length, midi, voice, velocity, flags in specs:
        if voice == 3 and offset < cut < offset + length:
            length = cut - offset
        if length > 0:
            cleared.append((offset, length, midi, voice, velocity, flags))
    return cleared


def _choro_halves(frame, ctx, bar, names: tuple[str, str], velocity: int) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    first = [item for item in _choro_bed(frame, ctx, bar, names[0], velocity, velocity) if item[0] < cut]
    second = _choro_bed(frame, ctx, bar, names[1], velocity, velocity)
    # Rebuild the second half in place by keeping only attacks at or after the cut.
    kept = []
    for offset, length, midi, voice, level, flags in second:
        if offset + length <= cut:
            continue
        if offset < cut:
            length -= cut - offset
            offset = cut
        kept.append((offset, length, midi, voice, level, flags))
    return first + kept


def _choro_down(frame, ctx, bar) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "V7")
    cursor = bass
    specs = []
    steps = [offset for offset in (0, 2, 4) if offset < epb]
    for index, offset in enumerate(steps):
        nxt = steps[index + 1] if index + 1 < len(steps) else min(epb, 6 if epb > 6 else epb - 1)
        length = max(1, nxt - offset)
        specs.append((offset, length, cursor, 3, _lerp(frame._P, frame._MP, len(steps) + 1, index), {}))
        walked = frame._step(cursor, -1, ctx.mode, ctx.bass_low, frame._bass_hi(ctx))
        if walked < lead:
            cursor = walked
    offbeats = [slot / 2 for slot in (6, 7, 14, 15) if slot / 2 < epb]
    sync = offbeats[-1] if offbeats else None
    if sync is not None and inner is not None and inner < lead:
        cover = [
            midi
            for offset, length, midi, voice, _level, _flags in specs
            if voice == 3 and offset <= sync < offset + length
        ]
        floor = max(cover) if cover else bass
        if floor < inner and _playable(ctx, [floor, inner, lead]):
            specs.append((sync, 0.5, inner, 2, frame._MP, {"accent": True}))
            specs.append((sync, 0.5, lead, 1, frame._MP, {"accent": True}))
    return specs


def _choro_close(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "I")
    beat = _beat(ctx, 2)
    if beat is None:
        beat = min(2, epb - 1)
    specs = []
    anticipate = beat - 0.5
    if anticipate >= 0:
        specs.append((anticipate, 0.5, lead, 1, velocity, {"accent": True}))
    specs.extend(_chord(beat, 1, bass, inner, lead, velocity, {"staccato": True, "accent": True}))
    return specs


def _polca_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "I", frame._P, frame._P, pickup=False))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "V7", frame._MP, frame._MP, pickup=True))
    if not closing and role == 0:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "I", frame._P, frame._P, pickup=False))
    if not closing and role == 1:
        return _finish(frame, ctx, _polca_leap(frame, ctx, bar, frame._MP))
    if not closing and role == 2:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "V7", frame._MP, frame._MP, pickup=False))
    if not closing:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "V7", frame._MP, frame._MF, pickup=True))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "V7", frame._MP, frame._MP, pickup=False))
    if steps <= 2:
        return _finish(frame, ctx, _polca_close(frame, ctx, bar, "V7", "I"))
    if role == 0:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "IV", frame._MP, frame._MP, pickup=False))
    if role == 1:
        return _finish(frame, ctx, _polca_bed(frame, ctx, bar, "V7", frame._MP, frame._MP, pickup=False))
    if role == 2:
        halves = _halves(ctx)
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*halves[0], "I", frame._P, None),
            (*halves[1], "V7", frame._MP, None),
        )))
    return _finish(frame, ctx, _polca_close(frame, ctx, bar, "I", "I"))


def _polca_bed(frame, ctx, bar, name, v0, v1, *, pickup: bool) -> list[tuple]:
    epb = ctx.epb
    pcs = _harmony(frame, ctx, bar, name)
    _stack_bass, inner, lead = _voicing(frame, ctx, bar, name)
    root = _low_pc(frame, ctx, pcs[0], inner or lead, inner or lead) or _stack_bass
    fifth_pc = pcs[2] if len(pcs) > 2 else pcs[0]
    fifth = _low_pc(frame, ctx, fifth_pc, inner or lead, inner or lead) or root
    specs = []
    if 0 < epb:
        specs.append((0, min(3, epb), root, 3, v0, {}))
    if 3 < epb:
        specs.append((3, epb - 3, fifth, 3, v1, {"accent": True}))
    inners = [offset for offset in (1, 2, 4, 5) if offset < epb]
    for index, offset in enumerate(inners):
        floor = fifth if offset >= 3 else root
        pitch = inner if inner is not None and floor < inner < lead else None
        if pitch is None:
            continue
        specs.append((offset, 1, pitch, 2, _lerp(v0, v1, len(inners), index), {}))
    if pickup:
        start = max(0, epb - 2)
        goal = _ahead(ctx, bar)
        lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
        cursor = lead
        if goal is not None:
            while goal > hi and goal - 12 >= lo:
                goal -= 12
            while goal < lo and goal + 12 <= hi:
                goal += 12
            cursor = frame._step(min(hi, max(lo, goal)), -1, ctx.mode, lo, hi)
        for index, offset in enumerate(range(start, epb)):
            if cursor <= (inner or root):
                cursor = lead if lead > (inner or root) else cursor
            specs.append((offset, 1, cursor, 1, _lerp(v0, v1, max(1, epb - start), index), {}))
            cursor = frame._step(cursor, 1, ctx.mode, lo, hi)
    return specs


def _polca_leap(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Lead leaps a third across I, then IV, on the polca eighths."""
    epb = ctx.epb
    cut = max(1, epb // 2)
    specs = []
    previous = None
    for name, start, end in (("I", 0, cut), ("IV", cut, epb)):
        bass, inner, lead = _voicing(frame, ctx, bar, name)
        if previous is not None:
            lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
            leaped = previous + (3 if ctx.mode != "minor" else 3)
            if lo <= leaped <= hi and leaped > bass and _playable(ctx, [bass, lead] if inner is None else [bass, inner, leaped]):
                lead = leaped
            else:
                lead = frame._step(frame._step(previous, 1, ctx.mode, lo, hi), 1, ctx.mode, lo, hi)
        specs.extend(_chord(start, max(1, end - start), bass, inner, lead, velocity))
        previous = lead
    return specs


def _polca_close(frame, ctx, bar, first: str, second: str) -> list[tuple]:
    epb = ctx.epb
    specs = []
    for offset, name, flags in (
        (0, first, {"staccato": True}),
        (3, second, {"staccato": True, "accent": True}),
    ):
        if offset >= epb:
            continue
        bass, inner, lead = _voicing(frame, ctx, bar, name)
        specs.extend(_chord(offset, 1, bass, inner, lead, frame._MF, flags))
    return specs


def _hemiola_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "I", frame._MP, frame._MP, accent=True))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "V7", frame._MP, frame._MF, accent=True))
    if not closing and role == 0:
        return _finish(frame, ctx, _straight(frame, ctx, bar, "I", frame._P, frame._P))
    if not closing and role == 1:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "IV", frame._MP, frame._MP, accent=False))
    if not closing and role == 2:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "V7", frame._MP, frame._MP, accent=True))
    if not closing:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "V7", frame._MF, frame._MF, accent=True))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "V7", frame._MP, frame._MP, accent=False))
    if steps <= 2:
        return _finish(frame, ctx, _hemiola_ring(frame, ctx, bar, frame._P))
    if role == 0:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "IV", frame._MP, frame._MP, accent=True))
    if role == 1:
        return _finish(frame, ctx, _hemiola_grid(frame, ctx, bar, "V7", frame._MP, frame._MP, accent=True))
    if role == 2:
        return _finish(frame, ctx, _straight_pair(frame, ctx, bar, frame._P))
    return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, ctx.epb, "I", frame._P, None),)))


def _hemiola_grid(frame, ctx, bar, name, v0, v1, *, accent: bool) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    specs = []
    points = [offset for offset in (0, 2, 4) if offset < epb]
    for index, offset in enumerate(points):
        nxt = points[index + 1] if index + 1 < len(points) else epb
        flags = {"accent": True} if accent and offset in {2, 4} else {}
        velocity = _lerp(v0, v1, len(points), index)
        specs.append((offset, max(1, nxt - offset), bass, 3, velocity, dict(flags)))
        if inner is not None and bass < inner < lead:
            specs.append((offset, max(1, nxt - offset), inner, 2, velocity, dict(flags)))
    if 0 < epb:
        first = min(3, epb)
        specs.append((0, first, lead, 1, v0, {}))
        if 3 < epb:
            specs.append((3, epb - 3, lead, 1, v1, {}))
    return specs


def _straight(frame, ctx, bar, name, v0, v1) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    pcs = _harmony(frame, ctx, bar, name)
    fifth = _low_pc(frame, ctx, pcs[2] if len(pcs) > 2 else pcs[0], inner or lead, inner or lead) or bass
    specs = [(0, min(3, epb), bass, 3, v0, {})]
    if 3 < epb:
        specs.append((3, epb - 3, fifth, 3, v1, {}))
    if inner is not None and bass < inner < lead and epb > 1:
        specs.append((min(2, epb - 1), 1, inner, 2, v1, {}))
    specs.append((0, epb, lead, 1, v1, {}))
    return specs


def _straight_pair(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    cut = 3 if epb > 3 else max(1, epb // 2)
    if cut >= epb:
        return _lay(frame, ctx, bar, ((0, epb, "I", velocity, None),))
    return _lay(frame, ctx, bar, (
        (0, cut, "I", velocity, None),
        (cut, epb - cut, "V7", velocity, None),
    ))


def _hemiola_ring(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Sustained tonic blocks. No staccato, so the bar does not become a stab."""
    epb = ctx.epb
    if 3 < epb:
        return _lay(frame, ctx, bar, (
            (0, 3, "I", velocity, None),
            (3, epb - 3, "I", velocity, None),
        ))
    return _lay(frame, ctx, bar, ((0, epb, "I", velocity, None),))


def _vals_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _waltz(frame, ctx, bar, "I", frame._P, accent_at=None))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _vals_through(frame, ctx, bar, frame._MP))
    if not closing and role == 0:
        return _finish(frame, ctx, frame._ascending(ctx, bar, "I", frame._P))
    if not closing and role == 1:
        return _finish(frame, ctx, _waltz(frame, ctx, bar, "I", frame._P, accent_at=None))
    if not closing and role == 2:
        return _finish(frame, ctx, _waltz(frame, ctx, bar, "V7", frame._MP, accent_at=4))
    if not closing:
        bass_only = [item for item in _waltz(frame, ctx, bar, "V7", frame._MP, accent_at=None) if item[3] != 1]
        bass_only.extend(frame._scale_into(ctx, bar, max(1, ctx.epb // 2), ctx.epb - max(1, ctx.epb // 2), frame._MP))
        return _finish(frame, ctx, bass_only)
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _waltz(frame, ctx, bar, "V7", frame._P, accent_at=None))
    if steps <= 2:
        return _finish(frame, ctx, _vals_ring(frame, ctx, bar, frame._PP))
    if role == 0:
        return _finish(frame, ctx, _waltz(frame, ctx, bar, "IV", frame._P, accent_at=None))
    if role == 1:
        return _finish(frame, ctx, _waltz(frame, ctx, bar, "V7", frame._P, accent_at=None))
    if role == 2:
        return _finish(frame, ctx, frame._sparse(ctx, bar, "I", frame._PP))
    return _finish(frame, ctx, _vals_ring(frame, ctx, bar, frame._PP))


def _waltz(frame, ctx, bar, name, velocity, *, accent_at: int | None) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    specs = [(0, epb, bass, 3, velocity, {})]
    for offset in (2, 4):
        if offset >= epb:
            continue
        flags = {"accent": True} if accent_at == offset else {}
        length = min(2, epb - offset)
        specs.append((offset, length, lead, 1, velocity, dict(flags)))
        if inner is not None and bass < inner < lead:
            specs.append((offset, length, inner, 2, velocity, dict(flags)))
    return specs


def _vals_through(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Bass walks V7 under a stepwise lead. Each pair has to fit one hand."""
    epb = ctx.epb
    pcs = _harmony(frame, ctx, bar, "V7")
    bass, _inner, lead = _voicing(frame, ctx, bar, "V7")
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    cursor = lead if lead > bass else frame._lead_lo(ctx)
    specs = []
    for offset in range(epb):
        if cursor <= bass or not _playable(ctx, [bass, cursor]):
            cursor = lead
        pc = pcs[min(offset, len(pcs) - 1)]
        low = _low_pc(frame, ctx, pc, cursor, cursor) or bass
        if not _playable(ctx, [low, cursor]):
            low = bass
        specs.append((offset, 1, low, 3, velocity, {}))
        specs.append((offset, 1, cursor, 1, velocity, {}))
        nxt = frame._step(cursor, 1, ctx.mode, lo, hi)
        if nxt > low and _playable(ctx, [low, nxt]):
            cursor = nxt
    return specs


def _vals_ring(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "I")
    beat = _beat(ctx, 2)
    if beat is None:
        beat = min(2, epb - 1)
    specs = [(0, epb, bass, 3, velocity, {})]
    specs.append((beat, epb - beat, lead, 1, velocity, {}))
    if inner is not None and bass < inner < lead:
        specs.append((beat, epb - beat, inner, 2, velocity, {}))
    return specs


def _thumb_bar(frame, ctx, bar, role, steps, closing, *, arrive: bool) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        if arrive:
            return _finish(frame, ctx, _villa_thumb_open(frame, ctx, bar))
        return _finish(frame, ctx, _thumb_sustain(frame, ctx, bar, "I", frame._P))
    if not closing and steps <= 2:
        if arrive:
            return _finish(frame, ctx, _thumb_arrive_hold(frame, ctx, bar, frame._MP))
        return _finish(frame, ctx, _thumb_v_to_i(frame, ctx, bar))
    if not closing and role == 0:
        if arrive:
            return _finish(frame, ctx, _thumb_three(frame, ctx, bar, frame._P, frame._MP))
        return _finish(frame, ctx, _thumb_open_dyad(frame, ctx, bar))
    if not closing and role == 1:
        if arrive:
            return _finish(frame, ctx, _thumb_peak(frame, ctx, bar))
        return _finish(frame, ctx, _thumb_two(frame, ctx, bar, "I", frame._P, frame._P))
    if not closing and role == 2:
        return _finish(frame, ctx, _thumb_functions(frame, ctx, bar, ("IV", "V7"), frame._P, frame._MP))
    if not closing:
        return _finish(frame, ctx, _thumb_into_body(frame, ctx, bar, frame._MP, land=arrive))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _thumb_resolve(frame, ctx, bar, frame._P))
    if steps <= 2:
        return _finish(frame, ctx, _thumb_alone(frame, ctx, bar, frame._PP))
    if role == 0:
        return _finish(frame, ctx, _thumb_functions(frame, ctx, bar, ("IV", "I"), frame._P, frame._P))
    if role == 1:
        if arrive:
            return _finish(frame, ctx, _thumb_one_dyad(frame, ctx, bar, ("V7", "I"), frame._PP))
        return _finish(frame, ctx, _thumb_functions(frame, ctx, bar, ("V7", "I"), frame._P, frame._P))
    if role == 2:
        if arrive:
            return _finish(frame, ctx, _thumb_harmonic(frame, ctx, bar))
        return _finish(frame, ctx, _thumb_with_inner(frame, ctx, bar, frame._PP))
    if arrive:
        return _finish(frame, ctx, _thumb_low_tonic(frame, ctx, bar))
    return _finish(frame, ctx, _thumb_alone(frame, ctx, bar, frame._PP))


def _sung(frame, ctx, bar, name: str, aim: int | None = None, *, low: bool = False) -> int:
    """Thumb-register pitch. ``aim`` keeps the body's pitch; otherwise the root."""
    pcs = _harmony(frame, ctx, bar, name)
    if aim is not None:
        return _fold_thumb(ctx, aim)
    root = pcs[0]
    found = [note for note in range(_thumb_lo(ctx), _thumb_hi(ctx) + 1) if note % 12 == root]
    if not found:
        found = [note for note in range(_thumb_lo(ctx), _thumb_hi(ctx) + 1) if note % 12 in set(pcs)]
    if not found:
        return _fold_thumb(ctx, frame._bass_note(ctx, root, None))
    return found[0] if low else found[-1]


def _place_dyads(frame, ctx, bar, name: str, sung: int, points: tuple[int, ...], velocity: int) -> list[tuple]:
    inner, lead = _dyad(frame, ctx, sung, _harmony(frame, ctx, bar, name))
    quiet = min(frame._P, max(frame._PP, velocity))
    specs = []
    for offset in points:
        if offset >= ctx.epb:
            continue
        if inner is not None:
            specs.append((offset, 1, inner, 2, quiet, {}))
        if lead is not None:
            specs.append((offset, 1, lead, 1, quiet, {}))
    return specs


def _thumb_sustain(frame, ctx, bar, name: str, velocity: int) -> list[tuple]:
    sung = _sung(frame, ctx, bar, name)
    specs = [(0, ctx.epb, sung, 3, velocity, {})]
    specs.extend(_place_dyads(frame, ctx, bar, name, sung, _thumb_points(ctx), frame._PP))
    return specs


def _villa_thumb_open(frame, ctx, bar) -> list[tuple]:
    epb = ctx.epb
    beat = _beat(ctx, 2) or min(2, epb - 1)
    start = _open_bass(frame, ctx)
    lo, hi = ctx.bass_low, _thumb_hi(ctx)
    specs = [(0, beat, start, 3, frame._P, {})]
    cursor = start
    steps = list(range(beat, epb))
    for index, offset in enumerate(steps):
        cursor = frame._step(cursor, 1, ctx.mode, lo, hi)
        if cursor > hi:
            cursor = hi
        specs.append((offset, 1, cursor, 3, _lerp(frame._P, frame._MP, max(1, len(steps)), index), {}))
    points = _thumb_points(ctx)
    if points:
        at = points[-1]
        sounding = next((midi for offset, _length, midi, voice, _vel, _flags in specs if voice == 3 and offset == at), cursor)
        specs.extend(_place_dyads(frame, ctx, bar, "I", sounding, (at,), frame._PP))
    return specs


def _thumb_v_to_i(frame, ctx, bar) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    dominant = _sung(frame, ctx, bar, "V7")
    arrival = _fold_thumb(ctx, _ahead(ctx, bar))
    if dominant == arrival:
        pcs = set(_harmony(frame, ctx, bar, "V7"))
        for note in range(_thumb_hi(ctx), _thumb_lo(ctx) - 1, -1):
            if note % 12 in pcs and note != arrival:
                dominant = note
                break
    specs = [
        (0, cut, dominant, 3, 52, {}),
        (cut, epb - cut, arrival, 3, 56, {}),
    ]
    points = [point for point in _thumb_points(ctx) if point >= cut] or list(_thumb_points(ctx))
    if points:
        host = arrival if points[0] >= cut else dominant
        name = "I" if points[0] >= cut else "V7"
        specs.extend(_place_dyads(frame, ctx, bar, name, host, (points[0],), frame._PP))
    return specs


def _thumb_arrive_hold(frame, ctx, bar, velocity: int) -> list[tuple]:
    sung = _fold_thumb(ctx, _ahead(ctx, bar))
    specs = [(0, ctx.epb, sung, 3, velocity, {})]
    specs.extend(_place_dyads(frame, ctx, bar, "I", sung, _thumb_points(ctx), frame._PP))
    return specs


def _thumb_three(frame, ctx, bar, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    lengths = frame._lengths(epb, min(3, epb))
    cursor = _open_bass(frame, ctx)
    hi = _thumb_hi(ctx)
    specs = []
    offset = 0
    for index, length in enumerate(lengths):
        if cursor > hi:
            cursor = hi
        specs.append((offset, length, cursor, 3, _lerp(v0, v1, len(lengths), index), {}))
        cursor = frame._step(cursor, 1, ctx.mode, ctx.bass_low, hi)
        offset += length
    return specs


def _thumb_open_dyad(frame, ctx, bar) -> list[tuple]:
    bass = _open_bass(frame, ctx, ctx.chord(bar).pitches[0] % 12)
    specs = [(0, ctx.epb, bass, 3, frame._PP, {})]
    specs.extend(_place_dyads(frame, ctx, bar, "I", bass, _thumb_points(ctx), frame._PP))
    return specs


def _thumb_two(frame, ctx, bar, name: str, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    first = _sung(frame, ctx, bar, name)
    second = frame._step(first, 1, ctx.mode, _thumb_lo(ctx), _thumb_hi(ctx))
    if second > _thumb_hi(ctx) or second == first:
        second = first
    return [
        (0, cut, first, 3, v0, {}),
        (cut, epb - cut, second, 3, v1, {}),
    ]


def _thumb_peak(frame, ctx, bar) -> list[tuple]:
    pcs = _harmony(frame, ctx, bar, "I")
    peak = _thumb_hi(ctx)
    for note in range(peak, _thumb_lo(ctx) - 1, -1):
        if note % 12 in pcs:
            peak = note
            break
    specs = [(0, ctx.epb, peak, 3, frame._PP, {})]
    specs.extend(_place_dyads(frame, ctx, bar, "I", peak, _thumb_points(ctx), frame._PP))
    return specs


def _thumb_functions(frame, ctx, bar, names: tuple[str, str], v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    first = _sung(frame, ctx, bar, names[0])
    second = _sung(frame, ctx, bar, names[1])
    specs = [
        (0, cut, first, 3, v0, {}),
        (cut, epb - cut, second, 3, v1, {}),
    ]
    points = _thumb_points(ctx)
    sparse = (points[0],) if points else ()
    if sparse and sparse[0] < cut:
        specs.extend(_place_dyads(frame, ctx, bar, names[0], first, sparse, frame._PP))
    late = tuple(point for point in points if point >= cut)
    if late:
        specs.extend(_place_dyads(frame, ctx, bar, names[1], second, (late[0],), frame._P if v1 > frame._P else frame._PP))
    return specs


def _thumb_into_body(frame, ctx, bar, velocity: int, *, land: bool) -> list[tuple]:
    epb = ctx.epb
    target = _fold_thumb(ctx, _ahead(ctx, bar))
    if not land:
        before = frame._step(target, -1, ctx.mode, _thumb_lo(ctx), _thumb_hi(ctx))
        if before == target and target - 1 >= _thumb_lo(ctx):
            before = target - 1
        target = before
    count = min(4, epb)
    start = epb - count
    cursor = target
    pitches = [cursor]
    for _ in range(count - 1):
        cursor = frame._step(cursor, -1, ctx.mode, _thumb_lo(ctx), _thumb_hi(ctx))
        pitches.append(cursor)
    pitches.reverse()
    if land:
        pitches[-1] = _fold_thumb(ctx, _ahead(ctx, bar))
    specs = []
    for index, pitch in enumerate(pitches):
        specs.append((start + index, 1, min(_thumb_hi(ctx), max(ctx.bass_low, pitch)), 3, velocity, {}))
    return specs


def _thumb_resolve(frame, ctx, bar, velocity: int) -> list[tuple]:
    sung = _sung(frame, ctx, bar, "I")
    specs = [(0, ctx.epb, sung, 3, velocity, {})]
    if 2 < ctx.epb:
        specs.extend(_place_dyads(frame, ctx, bar, "I", sung, (2,), frame._PP))
    return specs


def _thumb_alone(frame, ctx, bar, velocity: int) -> list[tuple]:
    return [(0, ctx.epb, _sung(frame, ctx, bar, "I"), 3, velocity, {})]


def _thumb_one_dyad(frame, ctx, bar, names: tuple[str, str], velocity: int) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    first = _sung(frame, ctx, bar, names[0])
    second = _sung(frame, ctx, bar, names[1])
    specs = [
        (0, cut, first, 3, velocity, {}),
        (cut, epb - cut, second, 3, velocity, {}),
    ]
    if 2 < epb:
        host = second if 2 >= cut else first
        name = names[1] if 2 >= cut else names[0]
        specs.extend(_place_dyads(frame, ctx, bar, name, host, (2,), frame._PP))
    return specs


def _thumb_with_inner(frame, ctx, bar, velocity: int) -> list[tuple]:
    sung = _sung(frame, ctx, bar, "I", low=True)
    pcs = _harmony(frame, ctx, bar, "I")
    specs = [(0, ctx.epb, sung, 3, velocity, {})]
    for note in range(frame._mid_lo(ctx), frame._mid_hi(ctx) + 1):
        if note % 12 not in pcs or not sung < note:
            continue
        if _playable(ctx, [sung, note]):
            specs.append((0, max(1, ctx.epb // 2), note, 2, velocity, {}))
            break
    return specs


def _thumb_harmonic(frame, ctx, bar) -> list[tuple]:
    """Voice 3 holds the tonic. A high open string rings above it when it fits."""
    roots = [note for note in range(_thumb_lo(ctx), _thumb_hi(ctx) + 1) if note % 12 == ctx.chord(bar).pitches[0] % 12]
    roots.append(_open_bass(frame, ctx, ctx.chord(bar).pitches[0] % 12))
    for sung in reversed(roots):
        for sounding in (64, 59, 55, 50):
            written = frame._open_written(ctx, sounding)
            if written <= sung or written > _thumb_hi(ctx) + 12:
                continue
            if frame._lead_lo(ctx) <= written <= frame._lead_hi(ctx):
                voice = 1
            elif frame._mid_lo(ctx) <= written <= frame._mid_hi(ctx):
                voice = 2
            else:
                continue
            if sung <= _thumb_hi(ctx) and _playable(ctx, [sung, written]):
                return [
                    (0, ctx.epb, sung, 3, frame._PP, {}),
                    (0, ctx.epb, written, voice, frame._PP, {}),
                ]
    return [(0, ctx.epb, _sung(frame, ctx, bar, "I", low=True), 3, frame._PP, {})]


def _thumb_low_tonic(frame, ctx, bar) -> list[tuple]:
    root = ctx.chord(bar).pitches[0] % 12
    pitch = _open_bass(frame, ctx, root)
    if pitch > _thumb_hi(ctx):
        pitch = frame._bass_note(ctx, root, None)
    return [(0, ctx.epb, pitch, 3, frame._PP, {})]


def _chord_melody_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    grid = _pair_grid(ctx)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "I", frame._P, None),
            (*grid[1], "I", frame._P, None),
        ), color=True))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "V7", frame._MP, None),
            (*grid[1], "I", frame._MP, None),
        ), color=True, stepwise=True))
    if not closing and role == 0:
        return _finish(frame, ctx, _swell(frame, ctx, bar, "I", frame._PP, frame._P))
    if not closing and role == 1:
        bass, inner, lead = _voicing(frame, ctx, bar, "I", color=True)
        shifted = frame._stack(ctx, _harmony(frame, ctx, bar, "I"), shift=2)
        plan = []
        plan.extend(_chord(*grid[0], bass, inner, lead, frame._P))
        plan.extend(_chord(*grid[1], shifted[0], shifted[1], shifted[2], frame._P))
        return _finish(frame, ctx, plan)
    if not closing and role == 2:
        quarters = _quarters(ctx.epb)
        names = ("I", "IV", "V7", "I")
        specs = []
        for index, offset in enumerate(quarters):
            name = names[index % len(names)]
            bass, inner, lead = _voicing(frame, ctx, bar, name, color=True)
            specs.extend(_chord(offset, min(2, ctx.epb - offset), bass, inner, lead, frame._MP))
        return _finish(frame, ctx, specs)
    if not closing:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "V7", frame._P, None),
            (*grid[1], "I", frame._P, None),
        ), color=True))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "V7", frame._P, None),
            (*grid[1], "I", frame._P, None),
        ), color=True))
    if steps <= 2:
        return _finish(frame, ctx, _melody_release(frame, ctx, bar, frame._PP))
    if role == 0:
        return _finish(frame, ctx, _lay(frame, ctx, bar, (
            (*grid[0], "IV", frame._P, None),
            (*grid[1], "I", frame._P, None),
        ), color=True))
    if role == 1:
        return _finish(frame, ctx, _lay(frame, ctx, bar, ((0, ctx.epb, "V7", frame._P, None),), color=True))
    if role == 2:
        return _finish(frame, ctx, _melody_release(frame, ctx, bar, frame._PP))
    return _finish(frame, ctx, _octave_or_tenth(frame, ctx, bar, frame._PP))


def _swell(frame, ctx, bar, name, v0, v1) -> list[tuple]:
    bass, inner, lead = _voicing(frame, ctx, bar, name, color=True)
    epb = ctx.epb
    cut = max(1, epb // 2)
    specs = _chord(0, cut, bass, inner, lead, v0)
    specs.extend(_chord(cut, epb - cut, bass, inner, lead, v1))
    return specs


def _melody_release(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Three voices on beat 1. The inner voice lets go after half a bar."""
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "I", color=True)
    specs = [
        (0, epb, bass, 3, velocity, {}),
        (0, epb, lead, 1, velocity, {}),
    ]
    if inner is not None and bass < inner < lead:
        specs.append((0, max(1, epb // 2), inner, 2, velocity, {}))
    return specs


def _octave_or_tenth(frame, ctx, bar, velocity: int) -> list[tuple]:
    root = ctx.chord(bar).pitches[0] % 12
    third = 3 if ctx.mode == "minor" else 4
    candidates = []
    for bass in _open_pitches(frame, ctx, ctx.bass_low, frame._bass_hi(ctx)):
        for span in (12, 24, 15, 16, 27, 28):
            lead = bass + span
            if third == 3 and span in {16, 28}:
                continue
            if frame._lead_lo(ctx) <= lead <= frame._lead_hi(ctx) and _playable(ctx, [bass, lead]):
                rank = 0 if bass % 12 == root or lead % 12 == root else 1
                candidates.append((rank, span not in {12, 24}, bass, lead))
    if candidates:
        _rank, _span, bass, lead = min(candidates)
        return [(0, ctx.epb, bass, 3, velocity, {}), (0, ctx.epb, lead, 1, velocity, {})]
    bass, _inner, lead = _voicing(frame, ctx, bar, "I")
    return [(0, ctx.epb, bass, 3, velocity, {}), (0, ctx.epb, lead, 1, velocity, {})]


def _etude1_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _etude_opens(frame, ctx, bar, frame._P))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _etude_cycle(
            frame, ctx, bar, "I", frame._P, frame._MP, breathe=False, prepare=True,
        ))
    if not closing and role == 0:
        return _finish(frame, ctx, _etude_slow(frame, ctx, bar, frame._PP, frame._P))
    if not closing and role == 1:
        return _finish(frame, ctx, _etude_cycle(frame, ctx, bar, "I", frame._P, frame._P, breathe=False))
    if not closing and role == 2:
        return _finish(frame, ctx, _etude_cycle(
            frame, ctx, bar, "V7", frame._MP, frame._MP, breathe=False, pedal="I", higher=True,
        ))
    if not closing:
        return _finish(frame, ctx, _etude_cycle(
            frame, ctx, bar, "I", frame._MP, frame._MP, breathe=True, prepare=True,
        ))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _etude_cycle(frame, ctx, bar, "I", frame._MP, frame._P, breathe=True))
    if steps <= 2:
        return _finish(frame, ctx, _etude_cadence(frame, ctx, bar, frame._PP))
    if role == 0:
        return _finish(frame, ctx, _etude_cycle(frame, ctx, bar, "I", frame._MP, frame._MP, breathe=False))
    if role == 1:
        return _finish(frame, ctx, _etude_cycle(frame, ctx, bar, "I", frame._P, frame._P, breathe=True))
    if role == 2:
        return _finish(frame, ctx, _etude_eighths_down(frame, ctx, bar, frame._P, frame._PP))
    return _finish(frame, ctx, _etude_ring(frame, ctx, bar, frame._PP))


_ETUDE_INNER = (1, 2, 3, 4, 5, 6, 8, 10, 11, 12, 13, 14, 15)


def _etude_cycle(frame, ctx, bar, name, v0, v1, *, breathe: bool, prepare: bool = False, pedal: str | None = None, higher: bool = False) -> list[tuple]:
    epb = ctx.epb
    floor = frame._lead_lo(ctx) + 3 if higher else None
    bass, inner, lead = _voicing(frame, ctx, bar, name, floor=floor)
    if pedal is not None:
        pedal_bass, _pedal_inner, _pedal_lead = _voicing(frame, ctx, bar, pedal)
        if pedal_bass < (inner or lead) and _playable(ctx, [pedal_bass, lead] if inner is None else [pedal_bass, inner, lead]):
            bass = pedal_bass
    pcs = _harmony(frame, ctx, bar, name)
    tones = [
        note
        for note in range(frame._mid_lo(ctx), frame._mid_hi(ctx) + 1)
        if bass < note < lead and note % 12 in set(pcs) and _playable(ctx, [bass, note, lead])
    ]
    if not tones and inner is not None and bass < inner < lead:
        tones = [inner]
    lead_pitch = lead
    if prepare:
        target = _ahead(ctx, bar)
        if target is not None:
            lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
            while target > hi and target - 12 >= lo:
                target -= 12
            while target < lo and target + 12 <= hi:
                target += 12
            stepped = frame._step(min(hi, max(lo, target)), -1, ctx.mode, lo, hi)
            if stepped > bass and stepped % 12 in set(pcs) and _playable(ctx, [bass, stepped]):
                lead_pitch = stepped
    tones = [tone for tone in tones if tone < lead_pitch]
    specs = [(0, epb, bass, 3, v0, {})]
    slots = [slot for slot in _ETUDE_INNER if not (breathe and slot >= 12) and slot / 2 < epb]
    for index, slot in enumerate(slots):
        if not tones:
            break
        pitch = tones[index % len(tones)]
        specs.append((slot / 2, 0.5, pitch, 2, _lerp(v0, v1, 16, slot), {}))
    for slot in (7, 9):
        if breathe and slot >= 12:
            continue
        if slot / 2 >= epb:
            continue
        specs.append((slot / 2, 0.5, lead_pitch, 1, _lerp(v0, v1, 16, slot), {}))
    return specs


def _etude_opens(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    half = max(1, epb // 2)
    pcs = set(_harmony(frame, ctx, bar, "I"))
    opens = [note for note in _open_pitches(frame, ctx, ctx.bass_low, frame._lead_hi(ctx)) if note % 12 in pcs]
    if not opens:
        opens = _open_pitches(frame, ctx, ctx.bass_low, frame._lead_hi(ctx)) or [frame._deep_open(ctx)]
    bass = _open_bass(frame, ctx, ctx.chord(bar).pitches[0] % 12)
    specs = [(0, half, bass, 3, velocity, {})]
    for offset in range(half):
        pitch = opens[offset % len(opens)]
        if pitch <= bass:
            continue
        voice = 1 if pitch >= frame._lead_lo(ctx) else 2
        if voice == 2 and not frame._mid_lo(ctx) <= pitch <= frame._mid_hi(ctx):
            voice = 1 if pitch >= frame._lead_lo(ctx) else 3
        if voice == 3:
            continue
        specs.append((offset, 1, pitch, voice, velocity, {}))
    _bass, inner, lead = _voicing(frame, ctx, bar, "I")
    for slot in _ETUDE_INNER:
        offset = slot / 2
        if offset < half or offset >= epb or inner is None:
            continue
        if bass < inner < lead:
            specs.append((offset, 0.5, inner, 2, velocity, {}))
    return specs


def _etude_slow(frame, ctx, bar, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    bass = _open_bass(frame, ctx, ctx.chord(bar).pitches[0] % 12)
    _stack_bass, inner, lead = _voicing(frame, ctx, bar, "I")
    if not bass < lead:
        bass = _stack_bass
    specs = [(0, epb, bass, 3, v0, {})]
    count = min(4, epb)
    span = max(1, epb // count)
    cursor = lead
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    for index in range(count):
        offset = min(epb - 1, index * span)
        length = span if index < count - 1 else epb - offset
        specs.append((offset, max(1, length), cursor, 1, _lerp(v0, v1, count, index), {}))
        nxt = frame._step(cursor, 1, ctx.mode, lo, hi)
        if nxt > bass:
            cursor = nxt
    if inner is not None and bass < inner < lead:
        specs.append((min(1, epb - 1), 1, inner, 2, v0, {}))
    return specs


def _etude_cadence(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "I")
    beat2 = _beat(ctx, 2) or min(2, epb - 1)
    beat3 = _beat(ctx, 3)
    if beat3 is None:
        beat3 = min(epb - 1, beat2 + 2)
    specs = [(0, epb, bass, 3, velocity, {})]
    if inner is not None and bass < inner < lead:
        specs.append((beat2, 1, inner, 2, velocity, {}))
    specs.append((beat3, epb - beat3, lead, 1, velocity, {}))
    return specs


def _etude_eighths_down(frame, ctx, bar, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    bass, _inner, lead = _voicing(frame, ctx, bar, "I")
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    specs = [(0, epb, bass, 3, v1, {})]
    cursor = lead
    for offset in range(epb):
        if cursor <= bass:
            break
        specs.append((offset, 1, cursor, 1, _lerp(v0, v1, epb, offset), {}))
        nxt = frame._step(cursor, -1, ctx.mode, lo, hi)
        if nxt <= bass or nxt == cursor:
            nxt = _by_tone(cursor, -1, max(lo, bass + 1), hi)
        cursor = nxt
    return specs


def _etude_ring(frame, ctx, bar, velocity: int) -> list[tuple]:
    bass = _open_bass(frame, ctx)
    _stack_bass, _inner, lead = _voicing(frame, ctx, bar, "I")
    if bass >= lead:
        bass = _stack_bass
    return [(0, ctx.epb, bass, 3, velocity, {}), (0, ctx.epb, lead, 1, velocity, {})]


def _etude11_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _eleven_opens(frame, ctx, bar, frame._P))
    if not closing and steps <= 2:
        half = max(1, ctx.epb // 2)
        specs = _lay(frame, ctx, bar, ((0, half, "V7", frame._MP, None),))
        specs.extend(_arches(frame, ctx, bar, "I", frame._MP, quarters=_late_quarters(ctx.epb), drop_last=False))
        return _finish(frame, ctx, specs)
    if not closing and role == 0:
        return _finish(frame, ctx, _eleven_color(frame, ctx, bar, frame._PP))
    if not closing and role == 1:
        return _finish(frame, ctx, _eleven_slow(frame, ctx, bar, frame._P))
    if not closing and role == 2:
        specs = _arches(frame, ctx, bar, "I", frame._MP, quarters=[0], drop_last=False)
        sustain = min(ctx.epb, 2)
        bass, inner, lead = _voicing(frame, ctx, bar, "I")
        if sustain < ctx.epb:
            specs.extend(_chord(sustain, ctx.epb - sustain, bass, inner, lead, frame._MP))
        return _finish(frame, ctx, specs)
    if not closing:
        return _finish(frame, ctx, _arches(
            frame, ctx, bar, "I", frame._MP,
            quarters=list(range(ctx.epb // 2)), drop_last=True,
        ))
    if steps <= 2 and role == 0:
        early = [quarter for quarter in range(ctx.epb // 2) if quarter * 2 < ctx.epb / 2]
        specs = _arches(frame, ctx, bar, "I", frame._MP, quarters=early[:2], drop_last=False)
        specs.extend(_resolve_eighths(frame, ctx, bar, frame._MP, frame._P))
        return _finish(frame, ctx, specs)
    if steps <= 2:
        return _finish(frame, ctx, _eleven_chord(frame, ctx, bar, frame._MP))
    if role == 0:
        quarters = list(range(ctx.epb // 2))
        return _finish(frame, ctx, _arches(frame, ctx, bar, "I", frame._MP, quarters=quarters, drop_last=False, end=frame._P))
    if role == 1:
        early = [quarter for quarter in range(ctx.epb // 2) if quarter * 2 < ctx.epb / 2]
        specs = _arches(frame, ctx, bar, "I", frame._P, quarters=early[:2], drop_last=False)
        specs.extend(_eleven_slow(frame, ctx, bar, frame._P, start=ctx.epb // 2))
        return _finish(frame, ctx, specs)
    if role == 2:
        return _finish(frame, ctx, _eleven_down(frame, ctx, bar, frame._P, frame._PP))
    return _finish(frame, ctx, _eleven_chord(frame, ctx, bar, frame._PP))


def _late_quarters(epb: int) -> list[int]:
    return [quarter for quarter in range(epb // 2) if quarter * 2 >= epb / 2]


def _arches(frame, ctx, bar, name, velocity, *, quarters: list[int], drop_last: bool, end: int | None = None) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    usable = [quarter for quarter in quarters if quarter * 2 < epb]
    specs = []
    for index, quarter in enumerate(usable):
        origin = quarter * 2
        level = velocity if end is None else _lerp(velocity, end, len(usable), index)
        room = epb - origin
        specs.append((origin, min(2, room), bass, 3, level, {}))
        specs.append((origin, min(1, room), lead, 1, level, {}))
        if origin + 1 < epb:
            specs.append((origin + 1, min(1, epb - (origin + 1)), lead, 1, max(frame._PP, level - 4), {}))
        drop = drop_last and index == len(usable) - 1
        if drop or inner is None or not bass < inner < lead:
            continue
        for slot in (1, 2, 4, 5):
            offset = origin + slot * _SIXTH
            if offset >= epb:
                continue
            specs.append((offset, min(_SIXTH_LEN, epb - offset), inner, 2, max(frame._PP, level - 6), {}))
    return specs


def _eleven_opens(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    opens = _open_pitches(frame, ctx, ctx.bass_low, frame._bass_hi(ctx)) or [frame._deep_open(ctx)]
    cut = max(1, epb // 2)
    first = opens[0]
    second = opens[1] if len(opens) > 1 else first
    return [(0, cut, first, 3, velocity, {}), (cut, epb - cut, second, 3, velocity, {})]


def _eleven_color(frame, ctx, bar, velocity: int) -> list[tuple]:
    bass, inner, lead = _voicing(frame, ctx, bar, "sus2", color=True)
    opens = [note for note in _open_pitches(frame, ctx, ctx.bass_low, frame._lead_hi(ctx))]
    for note in opens:
        if ctx.bass_low <= note <= frame._bass_hi(ctx) and note < lead:
            bass = note
            break
    for note in opens:
        if frame._mid_lo(ctx) <= note <= frame._mid_hi(ctx) and bass < note < lead and _playable(ctx, [bass, note, lead]):
            inner = note
            break
    specs = [(0, ctx.epb, bass, 3, velocity, {})]
    if inner is not None and bass < inner < lead:
        specs.append((0, ctx.epb, inner, 2, velocity, {}))
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    cursor = lead if lead > bass else frame._lead_lo(ctx)
    for offset in _quarters(ctx.epb):
        if cursor <= bass:
            break
        specs.append((offset, min(2, ctx.epb - offset), cursor, 1, velocity, {}))
        cursor = frame._step(cursor, 1, ctx.mode, lo, hi)
    return specs


def _eleven_slow(frame, ctx, bar, velocity: int, start: int = 0) -> list[tuple]:
    epb = ctx.epb
    bass, _inner, lead = _voicing(frame, ctx, bar, "I")
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    specs = []
    if start == 0:
        specs.append((0, epb, bass, 3, velocity, {}))
    cursor = lead
    points = [offset for offset in _quarters(epb) if offset >= start]
    for offset in points:
        specs.append((offset, min(2, epb - offset), cursor, 1, velocity, {}))
        cursor = frame._step(cursor, -1 if start else 1, ctx.mode, lo, hi)
    return specs


def _resolve_eighths(frame, ctx, bar, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    start = max(1, epb // 2)
    bass, _inner, lead = _voicing(frame, ctx, bar, "I")
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    specs = [(start, epb - start, bass, 3, v1, {})]
    cursor = lead
    for index, offset in enumerate(range(start, epb)):
        specs.append((offset, 1, cursor, 1, _lerp(v0, v1, max(1, epb - start), index), {}))
        nxt = frame._step(cursor, -1, ctx.mode, lo, hi)
        if nxt > bass:
            cursor = nxt
    return specs


def _eleven_chord(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Velocity is the accent. No staccato, and no accent flag for villa_stab."""
    bass, inner, lead = _voicing(frame, ctx, bar, "I")
    return _chord(0, ctx.epb, bass, inner, lead, velocity)


def _eleven_down(frame, ctx, bar, v0: int, v1: int) -> list[tuple]:
    epb = ctx.epb
    root = ctx.chord(bar).pitches[0] % 12
    tonic = frame._bass_note(ctx, root, frame._lead_lo(ctx))
    cursor = min(frame._bass_hi(ctx), tonic + 5)
    if cursor > frame._bass_hi(ctx):
        cursor = tonic
    specs = []
    for offset in range(epb):
        specs.append((offset, 1, cursor, 3, _lerp(v0, v1, epb, offset), {}))
        if cursor <= tonic:
            cursor = tonic
        else:
            nxt = frame._step(cursor, -1, ctx.mode, ctx.bass_low, frame._bass_hi(ctx))
            cursor = tonic if nxt < tonic else nxt
    specs[-1] = (epb - 1, 1, tonic, 3, v1, {})
    return specs


def _brouwer_etude_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _tumbao(frame, ctx, bar, "I", frame._P, inner=False, open_at=2))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _tumbao(frame, ctx, bar, "sus2", frame._MP, inner=True, toward=True))
    if not closing and role == 0:
        return _finish(frame, ctx, _bass_points(frame, ctx, bar, (0, 3), frame._PP, frame._P))
    if not closing and role == 1:
        return _finish(frame, ctx, _tumbao(frame, ctx, bar, "I", frame._P, inner=False, opens=2))
    if not closing and role == 2:
        return _finish(frame, ctx, _tumbao_return(frame, ctx, bar, frame._MP))
    if not closing:
        specs = _tumbao(frame, ctx, bar, "I", frame._MP, inner=True)
        specs.extend(frame._scale_into(ctx, bar, max(1, ctx.epb // 2), ctx.epb - max(1, ctx.epb // 2), frame._MP))
        return _finish(frame, ctx, specs)
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, _tumbao(frame, ctx, bar, "I", frame._MP, inner=True, only=(1, 4), end=frame._P))
    if steps <= 2:
        return _finish(frame, ctx, _ring_sus(frame, ctx, bar, frame._P))
    if role == 0:
        return _finish(frame, ctx, _tumbao(frame, ctx, bar, "I", frame._P, inner=True))
    if role == 1:
        return _finish(frame, ctx, _bass_points(frame, ctx, bar, (0, 3), frame._P, frame._P, opens=2))
    if role == 2:
        specs = list(frame._tonic_steps(ctx, bar, frame._PP))
        specs.extend(_open_above(frame, ctx, bar, specs))
        return _finish(frame, ctx, specs)
    return _finish(frame, ctx, _ring_sus(frame, ctx, bar, frame._PP))


def _tumbao_cells(ctx) -> list[tuple[int, int, int]]:
    epb = ctx.epb
    kind = getattr(ctx, "kind", "")
    if kind == "6/8":
        cells = [(0, 2, 0), (2, 3, 2), (5, 1, 0)]
    elif kind == "3/4" or epb <= 6:
        cells = [(0, 3, 0), (3, 3, 2)]
    else:
        cells = [(0, 3, 0), (3, 3, 2), (6, 2, 0)]
    return [(offset, min(length, epb - offset), degree) for offset, length, degree in cells if offset < epb and length > 0]


def _tumbao(frame, ctx, bar, name, velocity, *, inner: bool, open_at: int | None = None, opens: int = 0, toward: bool = False, only: tuple[int, ...] | None = None, end: int | None = None) -> list[tuple]:
    epb = ctx.epb
    pcs = _harmony(frame, ctx, bar, name)
    _bass, stack_inner, lead = _voicing(frame, ctx, bar, name)
    cells = _tumbao_cells(ctx)
    specs = []
    attacks = []
    for index, (offset, length, degree) in enumerate(cells):
        pc = pcs[min(degree, len(pcs) - 1)]
        pitch = _low_pc(frame, ctx, pc, stack_inner or lead, stack_inner or lead) or frame._bass_note(ctx, pc, lead)
        level = velocity if end is None else _lerp(velocity, end, len(cells), index)
        if toward and index == len(cells) - 1 and length > 1 and _root_moves(ctx, bar):
            specs.append((offset, length - 1, pitch, 3, level, {}))
            stepped = _toward_bass(frame, ctx, bar, pitch)
            last = offset + length - 1
            specs.append((last, 1, stepped if stepped is not None else pitch, 3, level, {}))
        else:
            specs.append((offset, length, pitch, 3, level, {}))
        attacks.append(offset)
    if open_at is not None and open_at < epb:
        cover = _sounding_bass(specs, open_at)
        opened = _open_between(frame, ctx, cover, lead)
        if opened is not None:
            specs.append((open_at, 1, opened, 2, velocity, {}))
    if opens:
        placed = 0
        for offset in range(epb):
            if offset in attacks or placed >= opens:
                continue
            cover = _sounding_bass(specs, offset)
            opened = _open_between(frame, ctx, cover, lead)
            if opened is None:
                continue
            specs.append((offset, 1, opened, 2, velocity, {}))
            placed += 1
    if inner:
        free = [offset for offset in range(epb) if offset not in attacks and (only is None or offset in only)]
        for index, offset in enumerate(free):
            cover = _sounding_bass(specs, offset)
            pitch = _open_between(frame, ctx, cover, lead)
            if pitch is None and stack_inner is not None and cover < stack_inner < lead:
                pitch = stack_inner
            if pitch is None:
                continue
            level = velocity if end is None else _lerp(velocity, end, max(1, len(free)), index)
            specs.append((offset, 1, pitch, 2, level, {}))
    return specs


def _sounding_bass(specs: list[tuple], offset: int) -> int:
    found = [midi for start, length, midi, voice, _velocity, _flags in specs if voice == 3 and start <= offset < start + length]
    return max(found) if found else 0


def _open_between(frame, ctx, bass: int, lead: int | None) -> int | None:
    ceiling = lead if lead is not None else frame._mid_hi(ctx) + 1
    for note in _open_pitches(frame, ctx, frame._mid_lo(ctx), frame._mid_hi(ctx)):
        if not bass < note < ceiling:
            continue
        voices = [bass, note] if lead is None or lead <= note else [bass, note, lead]
        if lead is not None and note >= lead:
            continue
        if _playable(ctx, voices):
            return note
    return None


def _root_moves(ctx, bar: int) -> bool:
    if bar + 1 >= getattr(ctx, "bars", 0):
        return False
    return ctx.chord(bar).pitches[0] % 12 != ctx.chord(bar + 1).pitches[0] % 12


def _toward_bass(frame, ctx, bar: int, origin: int) -> int | None:
    try:
        from app.sonify.guitar_patterns import _toward_next
    except ImportError:
        return None
    eighth = bar * ctx.epb + max(0, ctx.epb - 1)
    return _toward_next(ctx, bar, origin, eighth)


def _bass_points(frame, ctx, bar, points: tuple[int, ...], v0: int, v1: int, opens: int = 0) -> list[tuple]:
    epb = ctx.epb
    pcs = _harmony(frame, ctx, bar, "I")
    _bass, inner, lead = _voicing(frame, ctx, bar, "I")
    usable = [offset for offset in points if offset < epb]
    specs = []
    for index, offset in enumerate(usable):
        nxt = usable[index + 1] if index + 1 < len(usable) else epb
        pc = pcs[0] if index % 2 == 0 else (pcs[2] if len(pcs) > 2 else pcs[0])
        pitch = _low_pc(frame, ctx, pc, inner or lead, inner or lead) or frame._bass_note(ctx, pc, lead)
        specs.append((offset, max(1, nxt - offset), pitch, 3, _lerp(v0, v1, len(usable), index), {}))
    placed = 0
    for offset in range(epb):
        if placed >= opens or offset in usable:
            continue
        cover = _sounding_bass(specs, offset)
        opened = _open_between(frame, ctx, cover, lead)
        if opened is None:
            continue
        specs.append((offset, 1, opened, 2, v1, {}))
        placed += 1
    return specs


def _tumbao_return(frame, ctx, bar, velocity: int) -> list[tuple]:
    epb = ctx.epb
    cut = max(1, epb // 2)
    specs = _tumbao(frame, ctx, bar, "color-", velocity, inner=True)
    # Keep the shifted color for the first half and return the rest to I.
    kept = []
    for offset, length, midi, voice, level, flags in specs:
        if offset >= cut:
            continue
        if offset + length > cut:
            length = cut - offset
        kept.append((offset, length, midi, voice, level, flags))
    bass, inner, lead = _voicing(frame, ctx, bar, "I")
    kept.extend(_chord(cut, epb - cut, bass, inner, lead, velocity))
    return kept


def _open_above(frame, ctx, bar, specs: list[tuple]) -> list[tuple]:
    lead = max((midi for _o, _l, midi, voice, _v, _f in specs if voice == 1), default=None)
    bass = max((midi for _o, _l, midi, voice, _v, _f in specs if voice == 3), default=None)
    if lead is None or bass is None:
        return []
    opened = _open_between(frame, ctx, bass, lead)
    if opened is None:
        return []
    return [(0, 1, opened, 2, frame._PP, {})]


def _ring_sus(frame, ctx, bar, velocity: int) -> list[tuple]:
    """Sus2, with the root in the bass when that hand still fits. No third."""
    pcs = frame._sus2(ctx, bar)
    bass, inner, lead = frame._stack(ctx, pcs)
    root = _low_pc(frame, ctx, pcs[0], inner or lead, *([inner, lead] if inner is not None else [lead]))
    if root is not None and (inner is None or root < inner < lead):
        bass = root
    return _chord(0, ctx.epb, bass, inner, lead, velocity)


def _sarabande_bar(frame, ctx, bar, role, steps, closing) -> list[tuple]:
    role = _role(steps, role)
    accent = 3 if getattr(ctx, "kind", "") == "6/8" else min(2, ctx.epb - 1)
    if not closing and steps <= 2 and role == 0:
        return _finish(frame, ctx, _hang(frame, ctx, bar, "sus2", frame._P, frame._MP, accent))
    if not closing and steps <= 2:
        return _finish(frame, ctx, _sarabande_color(frame, ctx, bar, accent, frame._MP))
    if not closing and role == 0:
        return _finish(frame, ctx, _sarabande_open(frame, ctx, bar, accent))
    if not closing and role == 1:
        return _finish(frame, ctx, _hang(frame, ctx, bar, "sus4", frame._P, frame._P, accent))
    if not closing and role == 2:
        return _finish(frame, ctx, _sarabande_swarm(frame, ctx, bar, accent, frame._MP))
    if not closing:
        return _finish(frame, ctx, _sarabande_into(frame, ctx, bar, accent))
    if steps <= 2 and role == 0:
        return _finish(frame, ctx, frame._beat_two_hang(ctx, bar, frame._P))
    if steps <= 2:
        return _finish(frame, ctx, _open_fifth(frame, ctx, bar, frame._PP, low=False))
    if role == 0:
        return _finish(frame, ctx, _sarabande_fall(frame, ctx, bar, accent, frame._P))
    if role == 1:
        return _finish(frame, ctx, frame._tonic_steps(ctx, bar, frame._P))
    if role == 2:
        return _finish(frame, ctx, frame._beat_two_hang(ctx, bar, frame._PP))
    return _finish(frame, ctx, _open_fifth(frame, ctx, bar, frame._PP, low=True))


def _hang(frame, ctx, bar, name, bass_velocity, chord_velocity, accent: int) -> list[tuple]:
    bass, inner, lead = _voicing(frame, ctx, bar, name)
    epb = ctx.epb
    specs = [(0, epb, bass, 3, bass_velocity, {})]
    if accent <= 0:
        return specs + _chord(0, epb, bass, inner, lead, chord_velocity)[1:]
    specs.append((accent, epb - accent, lead, 1, chord_velocity, {"accent": True}))
    if inner is not None and bass < inner < lead:
        specs.append((accent, epb - accent, inner, 2, chord_velocity, {"accent": True}))
    return specs


def _sarabande_color(frame, ctx, bar, accent: int, velocity: int) -> list[tuple]:
    """Beat 2 takes the lower color. The second half is three or four lead steps."""
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "color-")
    half = max(1, epb // 2)
    specs = [(0, epb, bass, 3, velocity, {})]
    # Beat 2 already opens the second half in 6/8, so the figure starts there.
    figure = accent if accent >= half else half
    if accent < figure:
        specs.append((accent, figure - accent, lead, 1, velocity, {"accent": True}))
        if inner is not None and bass < inner < lead:
            specs.append((accent, figure - accent, inner, 2, velocity, {"accent": True}))
    count = min(4, epb - figure)
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    for offset, pitch in _swarm(figure, count, lead, -1, max(lo, bass + 1), hi):
        if offset >= epb or pitch <= bass:
            continue
        flags = {"accent": True} if offset == accent else {}
        specs.append((offset, 1, pitch, 1, velocity, flags))
        if offset == accent and inner is not None and bass < inner < pitch:
            specs.append((offset, 1, inner, 2, velocity, {"accent": True}))
    return specs


def _sarabande_into(frame, ctx, bar, accent: int) -> list[tuple]:
    """A lighter beat 2, then a lead that stops one step before the body."""
    epb = ctx.epb
    start = min(epb - 1, max(accent, epb // 2))
    specs = []
    for offset, length, midi, voice, velocity, flags in _hang(frame, ctx, bar, "sus2", frame._PP, frame._P, accent):
        if voice in (1, 2) and offset < start < offset + length:
            length = start - offset
        if voice in (1, 2) and offset >= start:
            continue
        if length <= 0:
            continue
        specs.append((offset, length, midi, voice, velocity, flags))
    specs.extend(frame._scale_into(ctx, bar, start, epb - start, frame._P))
    return specs


def _sarabande_open(frame, ctx, bar, accent: int) -> list[tuple]:
    epb = ctx.epb
    bass = _open_bass(frame, ctx, ctx.chord(bar).pitches[0] % 12)
    stack_bass, inner, lead = _voicing(frame, ctx, bar, "sus2")
    if bass >= lead:
        bass = stack_bass
    specs = [(0, max(1, accent), bass, 3, frame._PP, {})]
    specs.extend(_chord(accent, epb - accent, stack_bass, inner, lead, frame._P))
    return specs


def _sarabande_swarm(frame, ctx, bar, accent: int, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "sus2")
    specs = [(0, epb, bass, 3, velocity, {})]
    if inner is not None and bass < inner < lead:
        specs.append((accent, 1, inner, 2, velocity, {"accent": True}))
    start = min(epb - 1, accent + 1)
    count = min(4, epb - start)
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    for offset, pitch in _swarm(start, count, lead, 1, max(lo, bass + 1), hi):
        if offset < epb and pitch > bass:
            specs.append((offset, 1, pitch, 1, velocity, {}))
    return specs


def _sarabande_fall(frame, ctx, bar, accent: int, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _voicing(frame, ctx, bar, "sus2")
    specs = _chord(accent, 1, bass, inner, lead, velocity, {"accent": True})
    start = min(epb - 1, accent + 1)
    lo, hi = frame._lead_lo(ctx), frame._lead_hi(ctx)
    for offset, pitch in _swarm(start, min(3, epb - start), lead, -1, max(lo, bass + 1), hi):
        if offset < epb and pitch > bass:
            specs.append((offset, 1, pitch, 1, velocity, {}))
    return specs


def _open_fifth(frame, ctx, bar, velocity: int, *, low: bool) -> list[tuple]:
    """Root and fifth only. The sarabande cadence is not a bell chord."""
    epb = ctx.epb
    root = ctx.chord(bar).pitches[0] % 12
    fifth = (root + 7) % 12
    bass = _open_bass(frame, ctx, root)
    if bass % 12 != root:
        bass = frame._bass_note(ctx, root, None)
    lead = None
    voice = 1
    search_hi = frame._mid_hi(ctx) if low else frame._lead_hi(ctx)
    search_lo = bass + 1
    for note in range(search_lo, search_hi + 1):
        if note % 12 != fifth:
            continue
        if low and frame._mid_lo(ctx) <= note <= frame._mid_hi(ctx):
            chosen_voice = 2
        elif frame._lead_lo(ctx) <= note <= frame._lead_hi(ctx):
            chosen_voice = 1
        elif frame._mid_lo(ctx) <= note <= frame._mid_hi(ctx):
            chosen_voice = 2
        else:
            continue
        if _playable(ctx, [bass, note]):
            lead = note
            voice = chosen_voice
            if low and chosen_voice == 2:
                break
    if lead is None:
        for note in range(frame._lead_hi(ctx), frame._lead_lo(ctx) - 1, -1):
            if note % 12 == fifth and note > bass and _playable(ctx, [bass, note]):
                lead = note
                voice = 1
                break
    specs = [(0, epb, bass, 3, velocity, {})]
    if lead is not None:
        specs.append((0, epb, lead, voice, velocity, {}))
    return specs
