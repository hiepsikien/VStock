"""Composer intro and outro frames for a framed guitar movement.

The pedal region at the start (`intro` / `warmup`) and at the end
(`cooldown` / `outro`) is a safety buffer: the price there is one repeated
close. These frames ignore that flat line and write a short Sor, Barrios, or
Villa-Lobos entrance and cadence instead. A frame of one or two bars uses the
direct version. A frame of three bars or more uses the four-bar version and
stretches it across the region.

Every attack stays inside the written guitar registers, one note per voice,
low under the inner voice under the lead.
"""

from __future__ import annotations

from dataclasses import replace

from app.sonify.guitar import _fit

_MAJOR = (0, 2, 4, 5, 7, 9, 11)
_MINOR = (0, 2, 3, 5, 7, 8, 10)
_OPENS = (40, 45, 50, 55, 59, 64)
_P = 50
_MP = 56
_PP = 46
_MF = 64


def frame_roles(length: int) -> list[int]:
    """Which script step each bar of a frame plays.

    One or two bars stay on the two-bar script. Longer frames use four steps.
    The last bar is always the script's final step, so a cadence still resolves.
    """
    if length <= 0:
        return []
    steps = 2 if length <= 2 else 4
    if length == 1:
        return [0]
    if length < steps:
        if length == 2:
            return [0, steps - 1]
        return [0, steps - 2, steps - 1]
    roles = [min(steps - 1, index * steps // length) for index in range(length)]
    roles[-1] = steps - 1
    return roles


def render_intro(ctx, bars: list[int]) -> tuple[list, list, list]:
    """Musical entrance for the contiguous opening pedal bars."""
    return _render_region(ctx, bars, closing=False)


def render_outro(ctx, bars: list[int]) -> tuple[list, list, list]:
    """Musical cadence for the contiguous closing pedal bars."""
    return _render_region(ctx, bars, closing=True)


def _render_region(ctx, bars: list[int], *, closing: bool) -> tuple[list, list, list]:
    roles = frame_roles(len(bars))
    steps = 2 if len(bars) <= 2 else 4
    lead: list = []
    support: list = []
    low: list = []
    for index, bar in enumerate(bars):
        gesture = _gesture(
            ctx,
            bar,
            roles[index],
            steps=steps,
            closing=closing,
            index=index,
            length=len(bars),
        )
        bar_lead, bar_support, bar_low = _realize(ctx, bar, gesture)
        bar_lead, bar_support, bar_low = _sanitize(ctx, bar_lead, bar_support, bar_low)
        _ensure(ctx, bar, bar_lead, bar_support, bar_low)
        lead.extend(bar_lead)
        support.extend(bar_support)
        low.extend(bar_low)
    return lead, support, low


def _gesture(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int, length: int) -> list[tuple]:
    if length == 1:
        return _compressed(ctx, bar, closing)
    composer = {"villa": _villa, "barrios": _barrios}.get(ctx.ensemble, _sor)
    return composer(ctx, bar, role, steps=steps, closing=closing, index=index)


def _compressed(ctx, bar: int, closing: bool) -> list[tuple]:
    """One bar has to both enter and leave. The second half is the cadence."""
    epb = ctx.epb
    cut = max(1, epb // 2)
    first = _gesture_body(ctx, bar, 0, closing=closing)
    second = _gesture_body(ctx, bar, 1, closing=closing)
    specs: list[tuple] = []
    for offset, length, midi, voice, velocity, flags in first:
        if offset >= cut:
            continue
        specs.append((offset, min(length, cut - offset), midi, voice, velocity, flags))
    for offset, length, midi, voice, velocity, flags in second:
        start = cut if offset < cut else offset
        room = epb - start
        if room <= 0:
            continue
        specs.append((start, min(length, room), midi, voice, velocity, flags))
    return _clip_voice(specs, epb)


def _gesture_body(ctx, bar: int, role: int, *, closing: bool) -> list[tuple]:
    composer = {"villa": _villa, "barrios": _barrios}.get(ctx.ensemble, _sor)
    return composer(ctx, bar, role, steps=2, closing=closing, index=role)


def _sor(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    if closing and steps == 2:
        return _sor_outro_short(ctx, bar, role)
    if closing:
        return _sor_outro_long(ctx, bar, role, index)
    if steps == 2:
        return _sor_intro_short(ctx, bar, role)
    return _sor_intro_long(ctx, bar, role, index)


def _barrios(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    if closing and steps == 2:
        return _barrios_outro_short(ctx, bar, role)
    if closing:
        return _barrios_outro_long(ctx, bar, role)
    if steps == 2:
        return _barrios_intro_short(ctx, bar, role)
    return _barrios_intro_long(ctx, bar, role, index)


def _villa(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    bright = ctx.character in {"rally", "volatile"}
    if closing and steps == 2:
        return _villa_outro_short(ctx, bar, role, bright)
    if closing:
        return _villa_outro_long(ctx, bar, role, index, bright)
    if steps == 2:
        return _villa_intro_short(ctx, bar, role)
    return _villa_intro_long(ctx, bar, role, index)


def _sor_intro_short(ctx, bar: int, role: int) -> list[tuple]:
    """Direct classical entry: tonic bloom, then a dominant step into the body."""
    epb = ctx.epb
    if role == 0:
        bass, inner, lead = _stack(ctx, _function(ctx, bar, "I"))
        specs = [(0, epb, bass, 3, _P, {})]
        if inner is not None:
            specs.append((min(2, epb - 1), max(1, epb - min(2, epb - 1)), inner, 2, _P, {}))
        specs.append((min(4, epb - 1) if epb >= 6 else 1, max(1, epb - (min(4, epb - 1) if epb >= 6 else 1)), lead, 1, _P, {}))
        return _clip_voice(specs, epb)
    bass, inner, lead = _stack(ctx, _function(ctx, bar, "V7"), lead_floor=_lead_lo(ctx))
    cut = max(1, epb // 2)
    specs = [(0, epb, bass, 3, _MP, {})]
    if inner is not None and cut > 1:
        specs.append((0, cut, inner, 2, _MP, {}))
    specs.extend(_scale_into(ctx, bar, cut, epb - cut, _MP))
    return _clip_voice(specs, epb)


def _sor_intro_long(ctx, bar: int, role: int, index: int) -> list[tuple]:
    """Formal cadence: clean tonic, a bass step, dotted dominant, gentle tonic."""
    epb = ctx.epb
    if role == 0:
        bass, inner, lead = _stack(ctx, _function(ctx, bar, "I"))
        specs = [
            (0, min(2, epb), bass, 3, _P, {"staccato": True}),
            (0, min(2, epb), lead, 1, _P, {"staccato": True}),
        ]
        if inner is not None:
            specs.append((0, min(2, epb), inner, 2, _P, {"staccato": True}))
        rest = epb - min(2, epb)
        if rest > 0:
            specs.append((min(2, epb), rest, bass, 3, _PP, {}))
            specs.append((min(2, epb), rest, lead, 1, _PP, {}))
        return _clip_voice(specs, epb)
    if role == 1:
        return _bass_walk(ctx, bar, ("I", "IV", "V"), _P, index)
    if role == 2:
        return _dotted(ctx, bar, "V7", _MP, index)
    bass, inner, lead = _stack(ctx, _function(ctx, bar, "I"))
    cut = max(1, epb // 2)
    specs = [(0, epb, bass, 3, _P, {})]
    if inner is not None:
        specs.append((0, cut, inner, 2, _P, {}))
    specs.extend(_scale_into(ctx, bar, cut, epb - cut, _MP))
    return _clip_voice(specs, epb)


def _sor_outro_short(ctx, bar: int, role: int) -> list[tuple]:
    """Direct cadence: a compact dominant, then the tonic on beat 1."""
    epb = ctx.epb
    if role == 0:
        return _compact(ctx, bar, "V7", _MP)
    bass, inner, lead = _stack(ctx, _function(ctx, bar, "I"))
    specs = [(0, epb, bass, 3, _P, {}), (0, epb, lead, 1, _P, {})]
    if inner is not None:
        specs.append((0, epb, inner, 2, _PP, {}))
    return specs


def _sor_outro_long(ctx, bar: int, role: int, index: int) -> list[tuple]:
    epb = ctx.epb
    if role == 0:
        return _bass_walk(ctx, bar, ("I", "IV", "V"), _P, index)
    if role in {1, 2}:
        return _dotted(ctx, bar, "V7", _MP if role == 1 else _MF, index)
    bass, inner, lead = _stack(ctx, _function(ctx, bar, "I"), high=True)
    specs = [(0, epb, bass, 3, _P, {}), (0, epb, lead, 1, _P, {})]
    if inner is not None:
        specs.append((0, epb, inner, 2, _PP, {}))
    return specs


def _barrios_intro_short(ctx, bar: int, role: int) -> list[tuple]:
    """Harmonic bells, then the tonic bass wakes under a rising arpeggio."""
    if role == 0:
        return _bells(ctx, bar, _PP)
    return _rising_over_bass(ctx, bar, "I", _P)


def _barrios_intro_long(ctx, bar: int, role: int, index: int) -> list[tuple]:
    if role == 0:
        return _bells(ctx, bar, _PP)
    if role == 1:
        return _cantabile(ctx, bar, _P, index)
    if role == 2:
        return _rising_over_bass(ctx, bar, "ii", _P)
    return _settled(ctx, bar, "I", _MP)


def _barrios_outro_short(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _sparse(ctx, bar, "I", _P)
    return _bell_chord(ctx, bar, _PP, picardy=True)


def _barrios_outro_long(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _sparse(ctx, bar, "I", _P)
    if role == 1:
        return _cantabile(ctx, bar, _PP, 1)
    if role == 2:
        return _compact(ctx, bar, "ii", _PP)
    return _bell_chord(ctx, bar, _PP, picardy=True)


def _villa_intro_short(ctx, bar: int, role: int) -> list[tuple]:
    """Open-string roll, then two syncopated stabs back to the open bass."""
    if role == 0:
        return _roll(ctx, bar, "I", _P, shift=0)
    return _stabs(ctx, bar, "I", _MP, release=True)


def _villa_intro_long(ctx, bar: int, role: int, index: int) -> list[tuple]:
    if role in {0, 1}:
        return _roll(ctx, bar, "I", _P if role == 0 else _MP, shift=index)
    if role == 2:
        return _ascending(ctx, bar, "I", _MP)
    bass, inner, lead = _stack(ctx, _function(ctx, bar, "I"), high=True)
    epb = ctx.epb
    specs = [
        (0, min(2, epb), bass, 3, _MF, {"accent": True}),
        (0, min(2, epb), lead, 1, _MF, {"accent": True}),
    ]
    if inner is not None:
        specs.append((0, min(2, epb), inner, 2, _MP, {"accent": True}))
    rest = epb - min(2, epb)
    if rest:
        specs.append((min(2, epb), rest, bass, 3, _P, {}))
        specs.append((min(2, epb), rest, lead, 1, _P, {}))
    return _clip_voice(specs, epb)


def _villa_outro_short(ctx, bar: int, role: int, bright: bool) -> list[tuple]:
    if bright and role == 1:
        return _stabs(ctx, bar, "I", _MF, release=True)
    if role == 0:
        return _ascending(ctx, bar, "I", _MP)
    return _roll(ctx, bar, "I", _P, shift=1)


def _villa_outro_long(ctx, bar: int, role: int, index: int, bright: bool) -> list[tuple]:
    if role == 0:
        return _roll(ctx, bar, "I", _MP, shift=max(0, 2 - index))
    if role == 1:
        return _open_pedal(ctx, bar, _P)
    if role == 2:
        return _ascending(ctx, bar, "I", _MP)
    if bright:
        return _stabs(ctx, bar, "I", _MF, release=True)
    return _bell_chord(ctx, bar, _P, picardy=False)


def _function(ctx, bar: int, name: str) -> list[int]:
    root = ctx.chord(bar).pitches[0] % 12
    minor = ctx.mode == "minor"
    if name == "I":
        third = 3 if minor else 4
        return [root, (root + third) % 12, (root + 7) % 12]
    if name == "I+":
        return [root, (root + 4) % 12, (root + 7) % 12]
    if name == "IV":
        sub = (root + 5) % 12
        third = 3 if minor else 4
        return [sub, (sub + third) % 12, (sub + 7) % 12]
    if name == "V":
        dom = (root + 7) % 12
        return [dom, (dom + 4) % 12, (dom + 7) % 12]
    if name == "V7":
        dom = (root + 7) % 12
        return [dom, (dom + 4) % 12, (dom + 7) % 12, (dom + 10) % 12]
    if name == "ii":
        sup = (root + 2) % 12
        return [sup, (sup + 3) % 12, (sup + 7) % 12]
    return [root, (root + 4) % 12, (root + 7) % 12]


def _classes(mode: str) -> tuple[int, ...]:
    return _MINOR if mode == "minor" else _MAJOR


def _on_scale(pc: int, mode: str) -> bool:
    return pc % 12 in _classes(mode)


def _step(note: int, direction: int, mode: str, low: int, high: int) -> int:
    for shift in range(1, 13):
        candidate = note + direction * shift
        if low <= candidate <= high and _on_scale(candidate, mode):
            return candidate
    return note


def _lead_lo(ctx) -> int:
    return max(ctx.treble_floor, 59 - ctx.semitones)


def _lead_hi(ctx) -> int:
    return min(ctx.treble_top, ctx.ceiling, 81 - ctx.semitones)


def _bass_hi(ctx) -> int:
    return min(ctx.bass_high, 53 - ctx.semitones)


def _mid_lo(ctx) -> int:
    return max(ctx.mid_low, 50 - ctx.semitones)


def _mid_hi(ctx) -> int:
    return min(ctx.mid_high, 65 - ctx.semitones)


def _open_written(ctx, sounding: int) -> int:
    return sounding - ctx.semitones


def _is_open(ctx, written: int) -> bool:
    return written + ctx.semitones in _OPENS


def _pcs_in(pc: int, low: int, high: int) -> list[int]:
    if high < low:
        return []
    return [note for note in range(low, high + 1) if note % 12 == pc]


def _stack(ctx, pcs: list[int], *, lead_floor: int | None = None, high: bool = False, shift: int = 0) -> tuple[int, int | None, int]:
    """One playable bass / inner / lead stack. The inner voice may be absent."""
    from app.sonify.guitar_patterns import _playable

    shifted = [((pc + shift) % 12) for pc in pcs[1:]] or pcs
    bass_pcs = pcs
    lead_pcs = shifted
    inner_pcs = shifted
    lo = _lead_lo(ctx) if lead_floor is None else max(_lead_lo(ctx), lead_floor)
    hi = _lead_hi(ctx)
    if high:
        lo = max(lo, min(hi, 72 - ctx.semitones))
    basses: list[int] = []
    for pc in bass_pcs:
        basses.extend(_pcs_in(pc, ctx.bass_low, _bass_hi(ctx)))
    basses.sort(key=lambda note: (not _is_open(ctx, note), note))
    leads: list[int] = []
    for pc in lead_pcs:
        leads.extend(_pcs_in(pc, lo, hi))
    if not leads:
        for pc in pcs:
            leads.extend(_pcs_in(pc, _lead_lo(ctx), hi))
    aim = (76 if high else 67) - ctx.semitones
    leads.sort(key=lambda note: (abs(note - aim), note))
    inners: list[int] = []
    for pc in inner_pcs:
        inners.extend(_pcs_in(pc, _mid_lo(ctx), _mid_hi(ctx)))
    inners.sort()
    for bass in basses:
        for lead in leads:
            if lead <= bass:
                continue
            for inner in inners:
                if not bass < inner < lead:
                    continue
                sounding = [bass + ctx.semitones, inner + ctx.semitones, lead + ctx.semitones]
                if _playable(sounding):
                    return bass, inner, lead
    for bass in basses:
        for lead in leads:
            if lead <= bass:
                continue
            if _playable([bass + ctx.semitones, lead + ctx.semitones]):
                return bass, None, lead
    bass = _fit(pcs[0], ctx.bass_low, _bass_hi(ctx))
    lead = _fit(pcs[min(2, len(pcs) - 1)], _lead_lo(ctx), hi)
    if lead <= bass:
        lead = min(hi, max(_lead_lo(ctx), bass + 12))
    return bass, None, lead


def _bass_note(ctx, pc: int, lead: int | None) -> int:
    found = _bass_match(ctx, pc, lead)
    if found is not None:
        return found
    high = _bass_hi(ctx)
    if lead is not None:
        high = min(high, lead - 1)
    return _fit(pc, ctx.bass_low, max(ctx.bass_low, high))


def _bass_match(ctx, pc: int, lead: int | None) -> int | None:
    """A bass pitch of `pc` that shares a hand with `lead`, or nothing."""
    from app.sonify.guitar_patterns import _playable

    high = _bass_hi(ctx)
    if lead is not None:
        high = min(high, lead - 1)
    found = _pcs_in(pc, ctx.bass_low, high)
    found.sort(key=lambda note: (not _is_open(ctx, note), note))
    for note in found:
        sounding = [note + ctx.semitones] if lead is None else [note + ctx.semitones, lead + ctx.semitones]
        if _playable(sounding):
            return note
    return None


def _bass_for_chord(ctx, pcs: list[int], lead: int) -> int | None:
    """Prefer an open root, then an open fifth, then any chord tone that fits `lead`."""
    ordered: list[int] = []
    for pc in (pcs[0], pcs[2] if len(pcs) > 2 else pcs[-1], *pcs):
        if pc not in ordered:
            ordered.append(pc)
    high = min(_bass_hi(ctx), lead - 1)
    opens: list[int] = []
    folded: list[int] = []
    for pc in ordered:
        for note in _pcs_in(pc, ctx.bass_low, high):
            (opens if _is_open(ctx, note) else folded).append(note)
    from app.sonify.guitar_patterns import _playable

    for note in [*opens, *folded]:
        if _playable([note + ctx.semitones, lead + ctx.semitones]):
            return note
    return None


def _best_lead(ctx, pcs: list[int], bass_pcs: list[int], *, high: bool) -> int:
    """Highest practical melody note that every bass pitch below it can reach."""
    hi = _lead_hi(ctx)
    floors = [_lead_lo(ctx)]
    if high:
        floors.insert(0, min(hi, max(_lead_lo(ctx), 72 - ctx.semitones)))
    aim = (76 if high else 67) - ctx.semitones
    for floor in floors:
        found: list[int] = []
        for pc in [*pcs, *_classes(ctx.mode)]:
            for note in _pcs_in(pc, floor, hi):
                if note not in found:
                    found.append(note)
        found.sort(key=lambda note: (note % 12 not in pcs, abs(note - aim), -note))
        for lead in found:
            if all(_bass_match(ctx, pc, lead) is not None for pc in bass_pcs):
                return lead
    return min(hi, max(_lead_lo(ctx), aim))


def _scale_into(ctx, bar: int, start: int, count: int, velocity: int) -> list[tuple]:
    """A short scale on the lead that stops one step before the next bar's melody."""
    if count <= 0:
        return []
    target = _lead_lo(ctx) + 5
    nxt = bar + 1
    if nxt < ctx.bars and nxt * ctx.epb < len(ctx.melody):
        target = ctx.melody[nxt * ctx.epb]
    lo, hi = _lead_lo(ctx), _lead_hi(ctx)
    while target < lo and target + 12 <= hi:
        target += 12
    while target > hi and target - 12 >= lo:
        target -= 12
    cursor = min(hi, max(lo, target))
    pitches = []
    for _ in range(count):
        cursor = _step(cursor, -1, ctx.mode, lo, hi)
        pitches.append(cursor)
    pitches.reverse()
    specs = []
    level = velocity
    for offset, pitch in enumerate(pitches):
        specs.append((start + offset, 1, pitch, 1, min(_MF, level), {}))
        level = min(_MF, level + 2)
    return specs


def _bass_walk(ctx, bar: int, names: tuple[str, ...], velocity: int, index: int) -> list[tuple]:
    epb = ctx.epb
    lengths = _lengths(epb, len(names))
    bass_pcs: list[int] = []
    for name in names:
        pc = _function(ctx, bar, name)[0]
        if index:
            walked = _step(_fit(pc, ctx.bass_low, _bass_hi(ctx)), -index, ctx.mode, ctx.bass_low, _bass_hi(ctx))
            pc = walked % 12
        bass_pcs.append(pc)
    lead = _best_lead(ctx, _function(ctx, bar, "I"), bass_pcs, high=False)
    specs = [(0, epb, lead, 1, velocity, {})]
    cursor = 0
    for pc, length in zip(bass_pcs, lengths):
        specs.append((cursor, length, _bass_note(ctx, pc, lead), 3, velocity, {}))
        cursor += length
    return _clip_voice(specs, epb)


def _dotted(ctx, bar: int, name: str, velocity: int, index: int) -> list[tuple]:
    """Long-short march. The short note takes the fifth, never a sighing step."""
    epb = ctx.epb
    pcs = _function(ctx, bar, name)
    root = pcs[0]
    fifth = pcs[2] if len(pcs) > 2 else pcs[-1]
    lead = _best_lead(ctx, pcs, [root, fifth], high=index > 0)
    root_bass = _bass_note(ctx, root, lead)
    inner = _between(ctx, pcs, root_bass, lead)
    if ctx.epb >= 8:
        cells = ((0, 3, root), (3, 1, fifth), (4, 3, root), (7, 1, fifth))
    elif ctx.kind == "6/8":
        cells = ((0, 2, root), (2, 1, fifth), (3, 2, root), (5, 1, fifth))
    else:
        cells = ((0, 3, root), (3, 1, fifth), (4, 2, root))
    specs = [(0, epb, lead, 1, velocity, {})]
    if inner is not None:
        specs.append((0, min(2, epb), inner, 2, max(_PP, velocity - 4), {}))
    for offset, length, pc in cells:
        if offset >= epb:
            continue
        specs.append((offset, min(length, epb - offset), _bass_note(ctx, pc, lead), 3, velocity, {}))
    return _clip_voice(specs, epb)


def _compact(ctx, bar: int, name: str, velocity: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _stack(ctx, _function(ctx, bar, name))
    span = 2 if epb >= 4 else 1
    specs = []
    cursor = 0
    while cursor < epb:
        length = min(span, epb - cursor)
        flags = {"staccato": True} if length <= 2 else {}
        specs.append((cursor, length, bass, 3, velocity, flags))
        specs.append((cursor, length, lead, 1, velocity, flags))
        if inner is not None:
            specs.append((cursor, length, inner, 2, max(_PP, velocity - 4), flags))
        cursor += length
    return specs


def _bells(ctx, bar: int, velocity: int) -> list[tuple]:
    pcs = _function(ctx, bar, "I+")
    notes = _bell_pitches(ctx, pcs, 3)
    if not notes:
        notes = [_lead_hi(ctx)]
    lengths = _lengths(ctx.epb, len(notes))
    specs = []
    cursor = 0
    for pitch, length in zip(notes, lengths):
        specs.append((cursor, length, pitch, 1, min(_P, velocity + (cursor % 3) * 2), {}))
        cursor += length
    return specs


def _bell_pitches(ctx, pcs: list[int], count: int) -> list[int]:
    lo = 76 - ctx.semitones
    hi = min(ctx.ceiling, 81 - ctx.semitones)
    if hi < lo:
        hi = _lead_hi(ctx)
        lo = max(_lead_lo(ctx), hi - 5)
    found: list[int] = []
    pools = [set(pcs), set(_classes(ctx.mode))]
    for pool in pools:
        for note in range(hi, lo - 1, -1):
            if note % 12 in pool and note not in found:
                found.append(note)
            if len(found) >= count:
                found.sort()
                return found
    found.sort()
    return found


def _bell_chord(ctx, bar: int, velocity: int, *, picardy: bool) -> list[tuple]:
    name = "I+" if picardy or ctx.mode == "minor" else "I"
    pcs = _function(ctx, bar, name)
    candidates = _bell_pitches(ctx, pcs, 4)
    for note in range(_lead_hi(ctx), _lead_lo(ctx) - 1, -1):
        if note % 12 in pcs and note not in candidates:
            candidates.append(note)
    if not candidates:
        candidates = [_lead_hi(ctx)]
    epb = ctx.epb
    for lead in candidates:
        bass = _bass_for_chord(ctx, pcs, lead)
        if bass is None:
            continue
        inner = _between(ctx, pcs, bass, lead)
        specs = [(0, epb, bass, 3, velocity, {}), (0, epb, lead, 1, velocity, {})]
        if inner is not None:
            specs.append((0, epb, inner, 2, velocity, {}))
        return specs
    bass, inner, lead = _stack(ctx, pcs, high=True)
    specs = [(0, epb, bass, 3, velocity, {}), (0, epb, lead, 1, velocity, {})]
    if inner is not None:
        specs.append((0, epb, inner, 2, velocity, {}))
    return specs


def _between(ctx, pcs: list[int], bass: int, lead: int) -> int | None:
    from app.sonify.guitar_patterns import _playable

    found = []
    for pc in pcs:
        for note in _pcs_in(pc, _mid_lo(ctx), _mid_hi(ctx)):
            if bass < note < lead:
                found.append(note)
    found.sort(key=lambda note: (not _is_open(ctx, note), abs(note - (bass + lead) // 2)))
    for note in found:
        if _playable([bass + ctx.semitones, note + ctx.semitones, lead + ctx.semitones]):
            return note
    return None


def _rising_over_bass(ctx, bar: int, name: str, velocity: int) -> list[tuple]:
    epb = ctx.epb
    pcs = _function(ctx, bar, name)
    bass, _inner, lead = _stack(ctx, pcs)
    line = _rising(ctx, pcs, epb, lead)
    specs = [(0, epb, bass, 3, velocity, {})]
    for offset, pitch in enumerate(line):
        specs.append((offset, 1, pitch, 1, min(_MF, velocity + offset), {}))
    inner = _between(ctx, pcs, bass, min(line) if line else lead)
    if inner is not None and epb > 2:
        specs.append((1, 1, inner, 2, velocity, {}))
    return _clip_voice(specs, epb)


def _rising(ctx, pcs: list[int], count: int, fallback: int) -> list[int]:
    lo, hi = _lead_lo(ctx), _lead_hi(ctx)
    found: list[int] = []
    for note in range(lo, hi + 1):
        if note % 12 in pcs:
            found.append(note)
    if not found:
        return [fallback] * count
    if len(found) >= count:
        return found[:count]
    line = list(found)
    while len(line) < count:
        line.append(line[-1])
    return line


def _cantabile(ctx, bar: int, velocity: int, index: int) -> list[tuple]:
    """A slow inner line over a held tonic bass."""
    epb = ctx.epb
    pcs = _function(ctx, bar, "I")
    bass, inner, lead = _stack(ctx, pcs, high=True)
    specs = [(0, epb, bass, 3, velocity, {}), (0, epb, lead, 1, velocity, {})]
    if inner is None:
        return specs
    cursor = inner
    lengths = _lengths(epb, min(4, epb))
    start = 0
    for length in lengths:
        pitch = cursor
        if not (bass < pitch < lead and _mid_lo(ctx) <= pitch <= _mid_hi(ctx)):
            pitch = inner
        specs.append((start, length, pitch, 2, velocity, {}))
        cursor = _step(pitch, 1 if index % 2 == 0 else -1, ctx.mode, _mid_lo(ctx), _mid_hi(ctx))
        if not bass < cursor < lead:
            cursor = inner
        start += length
    return _clip_voice(specs, epb)


def _sparse(ctx, bar: int, name: str, velocity: int) -> list[tuple]:
    epb = ctx.epb
    pcs = _function(ctx, bar, name)
    bass, inner, lead = _stack(ctx, pcs)
    specs = [(0, epb, bass, 3, velocity, {})]
    points = list(range(0, epb, 2))[:3]
    level = velocity
    for offset in points:
        specs.append((offset, 1, lead, 1, max(_PP, level), {}))
        level -= 2
    if inner is not None and epb > 3:
        specs.append((2, 1, inner, 2, max(_PP, velocity - 4), {}))
    return _clip_voice(specs, epb)


def _settled(ctx, bar: int, name: str, velocity: int) -> list[tuple]:
    epb = ctx.epb
    pcs = _function(ctx, bar, name)
    bass, inner, lead = _stack(ctx, pcs)
    cut = max(1, epb // 2)
    specs = [(0, epb, bass, 3, velocity, {})]
    for offset in range(cut):
        specs.append((offset, 1, lead, 1, velocity, {}))
    if inner is not None:
        specs.append((0, min(2, cut), inner, 2, max(_PP, velocity - 4), {}))
    # The second half steps toward the first note of the body.
    specs.extend(_scale_into(ctx, bar, cut, epb - cut, velocity))
    return _clip_voice(specs, epb)


def _roll(ctx, bar: int, name: str, velocity: int, shift: int) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _stack(ctx, _function(ctx, bar, name), shift=shift * 2)
    support_at = min(1, epb - 1)
    lead_at = min(2, epb - 1)
    specs = [(0, epb, bass, 3, velocity, {})]
    if inner is not None:
        specs.append((support_at, epb - support_at, inner, 2, velocity, {}))
    specs.append((lead_at, epb - lead_at, lead, 1, velocity, {}))
    return _clip_voice(specs, epb)


def _open_pedal(ctx, bar: int, velocity: int) -> list[tuple]:
    pcs = _function(ctx, bar, "I")
    # Prefer a real open bass string when one matches the root or the fifth.
    root = pcs[0]
    fifth = pcs[2] if len(pcs) > 2 else root
    bass = None
    for sounding in (40, 45, 50):
        written = _open_written(ctx, sounding)
        if ctx.bass_low <= written <= _bass_hi(ctx) and written % 12 in {root, fifth}:
            bass = written
            break
    _stacked_bass, inner, lead = _stack(ctx, pcs)
    if bass is None:
        bass = _stacked_bass
    specs = [(0, ctx.epb, bass, 3, velocity, {}), (min(2, ctx.epb - 1), max(1, ctx.epb - min(2, ctx.epb - 1)), lead, 1, velocity, {})]
    if inner is not None and bass < inner < lead:
        specs.append((1 if ctx.epb > 1 else 0, 1, inner, 2, velocity, {}))
    return _clip_voice(specs, ctx.epb)


def _ascending(ctx, bar: int, name: str, velocity: int) -> list[tuple]:
    epb = ctx.epb
    pcs = _function(ctx, bar, name)
    bass, _inner, lead = _stack(ctx, pcs)
    line = _rising(ctx, list(_classes(ctx.mode)), epb, lead)
    specs = [(0, epb, bass, 3, velocity, {})]
    level = velocity
    for offset, pitch in enumerate(line):
        if pitch <= bass:
            continue
        specs.append((offset, 1, pitch, 1, min(_MF, level), {}))
        level += 1
    return _clip_voice(specs, epb)


def _stabs(ctx, bar: int, name: str, velocity: int, *, release: bool) -> list[tuple]:
    epb = ctx.epb
    bass, inner, lead = _stack(ctx, _function(ctx, bar, name))
    if epb >= 8:
        points = ((1, 2), (4, 2))
        release_at = 6
    elif epb == 6:
        points = ((1, 1), (3, 2))
        release_at = 5
    else:
        points = ((0, max(1, epb // 2)),)
        release_at = epb
    specs = []
    for offset, length in points:
        if offset >= epb:
            continue
        length = min(length, epb - offset)
        specs.append((offset, length, bass, 3, velocity, {"accent": True}))
        specs.append((offset, length, lead, 1, velocity, {"accent": True}))
        if inner is not None:
            specs.append((offset, length, inner, 2, max(_P, velocity - 4), {"accent": True}))
    if release and release_at < epb:
        specs.append((release_at, epb - release_at, _bass_note(ctx, _function(ctx, bar, name)[0], lead), 3, _P, {}))
    return _clip_voice(specs, epb)


def _lengths(total: int, parts: int) -> list[int]:
    parts = max(1, min(parts, total))
    base = total // parts
    extra = total % parts
    return [base + (1 if index < extra else 0) for index in range(parts)]


def _clip_voice(specs: list[tuple], epb: int) -> list[tuple]:
    """Drop a later note that would overlap an earlier one in the same voice."""
    occupied: dict[int, list[tuple[int, int]]] = {1: [], 2: [], 3: []}
    kept: list[tuple] = []
    for offset, length, midi, voice, velocity, flags in sorted(specs, key=lambda item: (item[3], item[0], -item[1])):
        if length <= 0 or offset >= epb or midi is None:
            continue
        length = min(length, epb - offset)
        spans = occupied[voice]
        if any(not (offset + length <= start or offset >= stop) for start, stop in spans):
            continue
        spans.append((offset, offset + length))
        kept.append((offset, length, midi, voice, velocity, flags))
    return kept


def _realize(ctx, bar: int, specs: list[tuple]) -> tuple[list, list, list]:
    from app.sonify.guitar_patterns import _eighth_event

    voices: dict[int, list] = {1: [], 2: [], 3: []}
    origin = bar * ctx.epb
    for offset, length, midi, voice, velocity, flags in specs:
        events = _eighth_event(origin + offset, length, midi, ctx.epb, voice, int(velocity))
        if flags and events:
            events = [replace(events[0], **flags), *events[1:]]
        voices[voice].extend(events)
    return voices[1], voices[2], voices[3]


def _sanitize(ctx, lead: list, support: list, low: list) -> tuple[list, list, list]:
    """Drop an inner note that crosses a voice or will not fit one hand."""
    from app.sonify.guitar_patterns import _playable

    def onset(event) -> int:
        return event.bar * ctx.epb * 2 + int(round(event.beat * 4))

    def covers(events, when: int) -> list[int]:
        found = []
        for event in events:
            if event.midi is None:
                continue
            start = onset(event)
            if start <= when < start + max(1, int(round(event.duration_beats * 4))):
                found.append(event.midi)
        return found

    kept = []
    for event in support:
        if event.midi is None:
            continue
        when = onset(event)
        basses = covers(low, when)
        highs = covers(lead, when)
        if basses and event.midi <= max(basses):
            continue
        if highs and event.midi >= min(highs):
            continue
        if event.midi < _mid_lo(ctx) or event.midi > _mid_hi(ctx):
            continue
        sounding = [*(note + ctx.semitones for note in basses), event.midi + ctx.semitones, *(note + ctx.semitones for note in highs)]
        if not _playable(sounding):
            continue
        kept.append(event)
    return lead, kept, low


def _ensure(ctx, bar: int, lead: list, support: list, low: list) -> None:
    if any(event.bar == bar and event.midi is not None for event in (*lead, *support, *low)):
        return
    from app.sonify.guitar_patterns import _eighth_event

    root = _bass_note(ctx, ctx.chord(bar).pitches[0] % 12, None)
    low.extend(_eighth_event(bar * ctx.epb, ctx.epb, root, ctx.epb, 3, _P))
