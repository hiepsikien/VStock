"""Intro and outro doors for the seven Torroba pedal patterns.

Each door sings scale degrees of I, iv/IV, and V7. The pedal has no price line.
A 1-bar frame still uses the short script: the first half of step 0, then step 1
in the second half. When step 1 already attacks at or after the cut, the notes
before that cut are left out so the compressor does not slide an earlier note
onto the pattern's own second-half attack.
"""

from __future__ import annotations

import inspect

from app.sonify.chords import Chord
from app.sonify.guitar_frame import (
    _MF,
    _MP,
    _P,
    _PP,
    _bell_chord,
    _between,
    _function,
    _lead_hi,
    _lead_lo,
    _mid_hi,
    _mid_lo,
    _scale_into,
    _step,
)

_DEGREE_SLOT = {1: 0, 3: 1, 5: 2}


def _from_compressed() -> bool:
    frame = inspect.currentframe()
    while frame is not None:
        if frame.f_code.co_name == "_compressed":
            return True
        frame = frame.f_back
    return False


def _finish(ctx, role: int, specs: list[tuple]) -> list[tuple]:
    epb = ctx.epb
    kept: list[tuple] = []
    for offset, length, midi, voice, velocity, flags in specs:
        if midi is None or length <= 0 or offset < 0 or offset >= epb:
            continue
        if offset + length > epb:
            length = epb - offset
        if length <= 0:
            continue
        kept.append((offset, length, midi, voice, velocity, flags))
    cut = max(1, epb // 2)
    if role == 1 and _from_compressed() and any(item[0] >= cut for item in kept):
        kept = [item for item in kept if item[0] >= cut]
    return kept


def _at_body(ctx, bar: int) -> bool:
    nxt = bar + 1
    if nxt >= getattr(ctx, "bars", bar + 1):
        return True
    kinds = getattr(ctx, "kind_at", None) or {}
    return kinds.get(nxt, "phrase") not in {"intro", "warmup"}


def _into_body(ctx, bar: int, closing: bool) -> bool:
    return not closing and _at_body(ctx, bar)


def _beds(velocity: int) -> tuple[int, int]:
    from app.sonify.guitar_patterns import _under_lead

    return _under_lead(velocity, "mf")


def _one_step_under(velocity: int) -> int:
    from app.sonify.guitar_patterns import _MICRO

    return max(40, velocity - _MICRO)


def _cut(ctx) -> int:
    return max(1, ctx.epb // 2)


def _ranked(pcs: list[int], prefer: tuple[int, ...]) -> list[int]:
    ranked: list[int] = []
    for degree in prefer:
        slot = _DEGREE_SLOT.get(degree)
        if slot is None or slot >= len(pcs):
            continue
        pc = pcs[slot]
        if pc not in ranked:
            ranked.append(pc)
    for pc in pcs:
        if pc not in ranked:
            ranked.append(pc)
    return ranked


def _lead_choices(ctx, pcs: list[int], prefer: tuple[int, ...], below: int | None) -> list[int]:
    lo, hi = _lead_lo(ctx), _lead_hi(ctx)
    aim = 67 - ctx.semitones
    found: list[tuple[int, int, int]] = []
    for rank, pc in enumerate(_ranked(pcs, prefer)):
        for note in range(lo, hi + 1):
            if note % 12 != pc:
                continue
            if below is not None and not below - 12 <= note < below:
                continue
            found.append((rank, abs(note - aim), note))
    found.sort()
    return [note for _rank, _distance, note in found]


def _functional(ctx, bar: int, name: str) -> Chord:
    return Chord(name, "C", "other", "", tuple(_function(ctx, bar, name)))


def _bass_for(ctx, bar: int, name: str, lead: int | None) -> int | None:
    from app.sonify.guitar_torroba import _torroba_bass

    found = _torroba_bass(ctx, _functional(ctx, bar, name), bar, lead)
    if found is None:
        return None
    sounding = found + ctx.semitones
    if sounding < 40 or sounding > 53:
        return None
    if lead is not None and found >= lead:
        return None
    return found


def _pair(ctx, bar: int, name: str, *, prefer: tuple[int, ...] = (5, 3, 1), below: int | None = None):
    from app.sonify.guitar_patterns import _playable

    pcs = _function(ctx, bar, name)
    choices = _lead_choices(ctx, pcs, prefer, below)
    if not choices and below is not None:
        choices = _lead_choices(ctx, pcs, prefer, None)
    for lead in choices:
        bass = _bass_for(ctx, bar, name, lead)
        if bass is None:
            continue
        if _playable([bass + ctx.semitones, lead + ctx.semitones]):
            return lead, bass
    return None


def _degree_pitch(ctx, pcs: list[int], prefer: tuple[int, ...]) -> int:
    choices = _lead_choices(ctx, pcs, prefer, None)
    if choices:
        return choices[0]
    return _lead_lo(ctx)


def _fit_lead(ctx, pitch: int) -> int:
    lo, hi = _lead_lo(ctx), _lead_hi(ctx)
    while pitch < lo and pitch + 12 <= hi:
        pitch += 12
    while pitch > hi and pitch - 12 >= lo:
        pitch -= 12
    return min(hi, max(lo, pitch))


def _marked_pitch(ctx, bar: int, *, earlier: bool) -> int | None:
    kinds = getattr(ctx, "kind_at", None) or {}
    if earlier:
        scan = range(bar - 1, -1, -1)
        skip = {"intro", "warmup", "outro", "cooldown"}
    else:
        scan = range(bar + 1, getattr(ctx, "bars", bar + 1))
        skip = {"intro", "warmup"}
    for other in scan:
        if kinds.get(other, "phrase") in skip:
            continue
        index = other * ctx.epb
        if index < len(ctx.melody):
            return ctx.melody[index]
        return None
    return None


def _scale_pitch(ctx, bar: int, velocity: int) -> int:
    """One degree before the body note. The caller writes the duration."""
    notes = _scale_into(ctx, bar, 0, 1, velocity)
    if not notes:
        return _lead_lo(ctx)
    return notes[0][2]


def _later_strong(ctx) -> int:
    for eighth in ctx.strong:
        if eighth > 0:
            return eighth
    return min(2, ctx.epb - 1)


def _chord_specs(
    ctx,
    bar: int,
    name: str,
    offset: int,
    velocity: int,
    *,
    length: int = 1,
    accent: bool = False,
    staccato: bool = False,
    prefer: tuple[int, ...] = (5, 3, 1),
) -> list[tuple]:
    if offset < 0 or offset >= ctx.epb:
        return []
    length = min(length, ctx.epb - offset)
    if length <= 0:
        return []
    pair = _pair(ctx, bar, name, prefer=prefer)
    if pair is None:
        return []
    lead, bass = pair
    support_velocity, bass_velocity = _beds(velocity)
    lead_flags: dict = {}
    other_flags: dict = {}
    if accent:
        lead_flags["accent"] = True
    if staccato:
        lead_flags["staccato"] = True
        other_flags["staccato"] = True
    specs = [
        (offset, length, lead, 1, velocity, lead_flags),
        (offset, length, bass, 3, bass_velocity, other_flags),
    ]
    inner = _between(ctx, _function(ctx, bar, name), bass, lead)
    if inner is not None:
        specs.append((offset, length, inner, 2, support_velocity, other_flags))
    return specs


def _bass_alone(ctx, bar: int, name: str, velocity: int, length: int | None = None) -> list[tuple]:
    bass = _bass_for(ctx, bar, name, None)
    if bass is None:
        return []
    span = ctx.epb if length is None else min(length, ctx.epb)
    if span <= 0:
        return []
    return [(0, span, bass, 3, velocity, {})]


def _sung(
    ctx,
    bar: int,
    name: str,
    velocity: int,
    *,
    lead_from: int | None,
    bass_length: int,
    below: int | None = None,
    price: bool = False,
) -> list[tuple]:
    from app.sonify.guitar_patterns import _playable

    pair = None
    if price:
        raw = _marked_pitch(ctx, bar, earlier=True)
        if raw is not None:
            lead = _fit_lead(ctx, raw)
            bass = _bass_for(ctx, bar, name, lead)
            if bass is not None and _playable([bass + ctx.semitones, lead + ctx.semitones]):
                pair = (lead, bass)
    if pair is None:
        pair = _pair(ctx, bar, name, below=below)
    if pair is None:
        return _bass_alone(ctx, bar, name, velocity, bass_length or None)
    lead, bass = pair
    specs = []
    if bass_length > 0:
        specs.append((0, min(bass_length, ctx.epb), bass, 3, velocity, {}))
    if lead_from is not None and lead_from < ctx.epb:
        specs.append((lead_from, ctx.epb - lead_from, lead, 1, velocity, {}))
    return specs


def _upper(ctx, pitch: int) -> int | None:
    nxt = _step(pitch, 1, ctx.mode, _lead_lo(ctx), _lead_hi(ctx))
    if nxt == pitch:
        return None
    return nxt


def _motif(ctx, pitch: int, velocity: int, *, slur: bool) -> list[tuple]:
    cut = _cut(ctx)
    if cut >= ctx.epb:
        return []
    specs = [
        (cut, min(0.5, ctx.epb - cut), pitch, 1, velocity, {}),
    ]
    if cut + 0.5 < ctx.epb:
        specs.append((cut + 0.5, min(0.5, ctx.epb - (cut + 0.5)), pitch, 1, velocity, {}))
    eighth_at = cut + 1
    mid = cut + (ctx.epb - cut) // 2
    if not slur:
        if eighth_at < ctx.epb:
            specs.append((eighth_at, min(1, ctx.epb - eighth_at), pitch, 1, velocity, {}))
        return specs
    if eighth_at < mid and eighth_at < ctx.epb:
        specs.append((eighth_at, min(1, ctx.epb - eighth_at), pitch, 1, velocity, {}))
    neighbor = _upper(ctx, pitch)
    if neighbor is None or mid >= ctx.epb or mid + 0.5 >= ctx.epb:
        if mid < ctx.epb:
            specs.append((mid, min(1, ctx.epb - mid), pitch, 1, velocity, {}))
        return specs
    specs.append((mid, 0.5, neighbor, 1, velocity, {"slur_start": True}))
    specs.append((mid + 0.5, 0.5, pitch, 1, velocity, {"slur_stop": True}))
    return specs


def _call(
    ctx,
    bar: int,
    name: str,
    velocity: int,
    *,
    slur: bool = False,
    support: bool = True,
    bass_whole: bool = False,
    motif: bool = True,
) -> list[tuple]:
    pair = _pair(ctx, bar, name)
    if pair is None:
        return []
    lead, bass = pair
    support_velocity, bass_velocity = _beds(velocity)
    cut = _cut(ctx)
    specs: list[tuple] = [(0, ctx.epb if bass_whole else cut, bass, 3, bass_velocity, {})]
    if support:
        inner = _between(ctx, _function(ctx, bar, name), bass, lead)
        if inner is not None:
            specs.append((0, cut, inner, 2, support_velocity, {}))
    if motif:
        specs.extend(_motif(ctx, lead, velocity, slur=slur))
    return specs


def _echo_inner(ctx, pcs: list[int], bass: int, lead: int) -> int | None:
    from app.sonify.guitar_patterns import _playable

    found = []
    for note in range(_mid_lo(ctx), _mid_hi(ctx) + 1):
        if note % 12 not in pcs or not bass < note < lead:
            continue
        sounding = [bass + ctx.semitones, note + ctx.semitones, lead + ctx.semitones]
        if _playable(sounding):
            found.append(note)
    if not found:
        return None
    return max(found)


def _held_echo(ctx, bar: int, name: str, velocity: int, *, bass_edges: bool) -> list[tuple]:
    pair = _pair(ctx, bar, name, prefer=(5, 3, 1))
    if pair is None:
        return []
    lead, bass = pair
    support_velocity, bass_velocity = _beds(velocity)
    echo = _one_step_under(support_velocity)
    specs: list[tuple] = [(0, ctx.epb, lead, 1, velocity, {})]
    if bass_edges:
        specs.append((0, 1, bass, 3, bass_velocity, {}))
        if ctx.epb > 1:
            specs.append((ctx.epb - 1, 1, bass, 3, bass_velocity, {}))
    inner = _echo_inner(ctx, _function(ctx, bar, name), bass, lead)
    if inner is None:
        return specs
    strong = set(ctx.strong)
    for eighth in range(ctx.epb):
        if eighth in strong:
            continue
        specs.append((eighth, 1, inner, 2, echo, {}))
    return specs


def _third(ctx, bar: int, velocity: int) -> list[tuple]:
    from app.sonify.guitar_patterns import _playable

    pair = _pair(ctx, bar, "I", prefer=(5, 3, 1))
    if pair is None:
        return []
    lead, bass = pair
    pcs = set(_function(ctx, bar, "I"))
    inner = None
    for note in range(_mid_hi(ctx), _mid_lo(ctx) - 1, -1):
        if note % 12 not in pcs or not bass < note < lead:
            continue
        if (lead - note) % 12 not in {3, 4}:
            continue
        sounding = [bass + ctx.semitones, note + ctx.semitones, lead + ctx.semitones]
        if _playable(sounding):
            inner = note
            break
    if inner is None:
        inner = _between(ctx, list(pcs), bass, lead)
    support_velocity, bass_velocity = _beds(velocity)
    specs = [
        (0, ctx.epb, lead, 1, velocity, {}),
        (0, ctx.epb, bass, 3, bass_velocity, {}),
    ]
    if inner is not None:
        specs.append((0, ctx.epb, inner, 2, support_velocity, {}))
    return specs


def _downbeat_pair(ctx, bar: int, name: str, velocity: int, *, length: int = 1) -> list[tuple]:
    pair = _pair(ctx, bar, name)
    if pair is None:
        return _bass_alone(ctx, bar, name, velocity, length)
    lead, bass = pair
    _support, bass_velocity = _beds(velocity)
    span = min(length, ctx.epb)
    return [
        (0, span, lead, 1, velocity, {}),
        (0, span, bass, 3, bass_velocity, {}),
    ]


def _juglar_motor(ctx, bar: int, name: str, velocity: int, *, lead_in: bool) -> list[tuple]:
    if ctx.kind != "3/4":
        return _downbeat_pair(ctx, bar, name, velocity, length=1)
    pair = _pair(ctx, bar, name)
    if pair is None:
        return []
    lead, bass = pair
    support, bass_velocity = _beds(velocity)
    echo = support if support < velocity else velocity
    fourth = 1 if lead_in else 2
    specs = [
        (0, 2, lead, 1, velocity, {}),
        (0, 1, bass, 3, bass_velocity, {}),
        (2, 2, lead, 1, echo, {}),
        (4, fourth, lead, 1, echo, {}),
    ]
    if lead_in and ctx.epb > 5:
        specs.extend(_scale_into(ctx, bar, 5, 1, velocity))
    return specs


def _juglar_hold(ctx, bar: int, name: str, velocity: int) -> list[tuple]:
    if ctx.kind != "3/4":
        return _downbeat_pair(ctx, bar, name, velocity, length=1)
    pair = _pair(ctx, bar, name)
    if pair is None:
        return _bass_alone(ctx, bar, name, velocity)
    lead, bass = pair
    _support, bass_velocity = _beds(velocity)
    return [
        (0, ctx.epb, lead, 1, velocity, {}),
        (0, 2, bass, 3, bass_velocity, {}),
    ]


def _alcaniz_pairs(ctx) -> list[tuple[int, int]]:
    if ctx.kind == "4/4":
        return [(0, 1), (4, 5)]
    if ctx.kind == "3/4":
        return [(0, 1)]
    return [(0, 1), (3, 4)]


def _alcaniz_bar(
    ctx,
    bar: int,
    name: str,
    velocity: int,
    *,
    groups: int,
    sustain: bool,
    scale_later: bool,
    accent_first: bool,
    accent_later: bool,
) -> list[tuple]:
    pairs = _alcaniz_pairs(ctx)[:groups]
    pair = _pair(ctx, bar, name)
    if pair is None:
        return []
    lead, bass = pair
    _support, bass_velocity = _beds(velocity)
    from app.sonify.guitar_patterns import _playable

    scale = _scale_pitch(ctx, bar, velocity) if scale_later and len(pairs) > 1 else None
    specs = []
    for index, (lead_at, bass_at) in enumerate(pairs):
        if lead_at >= ctx.epb:
            continue
        length = 3 if sustain else 1
        if index + 1 < len(pairs):
            length = min(length, pairs[index + 1][0] - lead_at)
        length = min(length, ctx.epb - lead_at)
        if length <= 0:
            continue
        pitch = scale if scale is not None and index == len(pairs) - 1 else lead
        flags = {}
        if accent_first and index == 0:
            flags["accent"] = True
        if accent_later and index > 0:
            flags["accent"] = True
        specs.append((lead_at, length, pitch, 1, velocity, flags))
        if bass_at >= ctx.epb or not bass < pitch:
            continue
        sounding = [bass + ctx.semitones, pitch + ctx.semitones]
        if not _playable(sounding):
            continue
        specs.append((bass_at, 1, bass, 3, bass_velocity, {}))
    return specs


def _olite_onsets(ctx) -> list[int]:
    if ctx.kind == "3/4":
        return [0]
    if ctx.kind == "6/8":
        return [eighth for eighth in (0, 3) if eighth < ctx.epb]
    return [eighth for eighth in (0, 4) if eighth < ctx.epb]


def _olite_chords(
    ctx,
    bar: int,
    name: str,
    velocity: int,
    *,
    accents: str,
    index: int,
    steps: int,
    closing: bool,
) -> list[tuple]:
    """Quarter-note chords. Only the last onset of the final outro bar is a staccato eighth."""
    onsets = _olite_onsets(ctx)
    specs: list[tuple] = []
    final_bar = closing and index == steps - 1
    last = len(onsets) - 1
    for onset_index, onset in enumerate(onsets):
        if accents == "both":
            accent = True
        elif accents == "later":
            accent = onset_index == last and len(onsets) > 1
        else:
            accent = False
        final_stroke = final_bar and onset_index == last
        specs.extend(
            _chord_specs(
                ctx,
                bar,
                name,
                onset,
                velocity,
                length=1 if final_stroke else 2,
                accent=accent,
                staccato=final_stroke,
            )
        )
    return specs


def _olite_breath(ctx, bar: int) -> list[tuple]:
    pair = _pair(ctx, bar, "I")
    if pair is None:
        return []
    lead, _bass = pair
    return [(0, min(2, ctx.epb), lead, 1, _P, {})]


def _lead_in_scale(ctx, bar: int, velocity: int) -> list[tuple]:
    if ctx.epb <= 7:
        return []
    return _scale_into(ctx, bar, 6, 2, velocity)


def _fan_scale(ctx, bar: int, velocity: int) -> list[tuple]:
    cut = _cut(ctx)
    return _scale_into(ctx, bar, cut, min(3, ctx.epb - cut), velocity)


def _fan_strokes(ctx, bar: int, name: str, velocity: int, *, later_accent: bool) -> list[tuple]:
    later = _later_strong(ctx)
    onsets = [0] if later == 0 or later >= ctx.epb else [0, later]
    specs: list[tuple] = []
    for index, onset in enumerate(onsets):
        accent = later_accent and index == len(onsets) - 1 and len(onsets) > 1
        specs.extend(_chord_specs(ctx, bar, name, onset, velocity, accent=accent, staccato=True))
    return specs


def _single_lead(ctx, bar: int, name: str, onset: int, velocity: int) -> list[tuple]:
    if onset < 0 or onset >= ctx.epb:
        return []
    pair = _pair(ctx, bar, name)
    if pair is None:
        return []
    lead, _bass = pair
    return [(onset, 1, lead, 1, velocity, {})]


def _danza_layout(ctx, shape: str) -> tuple[list[int], list[int]]:
    epb = ctx.epb
    if shape == "chord":
        return [0], []
    if shape == "one":
        return [0], ([1] if epb > 1 else [])
    if shape == "answer":
        return [], ([1] if epb > 1 else [])
    if shape == "close-short":
        return ([0, 3] if ctx.kind == "6/8" and epb > 3 else [0]), []
    if shape == "close-two":
        later = _later_strong(ctx)
        onsets = [0] if later == 0 or later >= epb else [0, later]
        return onsets, []
    if ctx.kind == "6/8" and epb > 4:
        return [0, 3], [1, 4]
    return [0], [eighth for eighth in (1, 2) if eighth < epb]


def _danza_bar(
    ctx,
    bar: int,
    name: str,
    velocity: int,
    *,
    shape: str,
    scale_last: bool,
    accent_later: bool,
) -> list[tuple]:
    chords, replies = _danza_layout(ctx, shape)
    specs: list[tuple] = []
    chord_lead = None
    for index, onset in enumerate(chords):
        accent = accent_later and len(chords) > 1 and index == len(chords) - 1
        block = _chord_specs(ctx, bar, name, onset, velocity, accent=accent, staccato=True)
        specs.extend(block)
        if chord_lead is None:
            for item in block:
                if item[3] == 1:
                    chord_lead = item[2]
    pcs = _function(ctx, bar, name)
    for index, onset in enumerate(replies):
        if onset in chords or onset >= ctx.epb:
            continue
        if scale_last and index == len(replies) - 1:
            specs.extend(_scale_into(ctx, bar, onset, 1, velocity))
            continue
        pitch = _degree_pitch(ctx, pcs, (3, 1, 5))
        if chord_lead is not None and pitch == chord_lead:
            alt = _degree_pitch(ctx, pcs, (1, 5, 3))
            if alt != chord_lead:
                pitch = alt
        specs.append((onset, 1, pitch, 1, velocity, {}))
    return specs


def _castillo_intro_short(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _bass_alone(ctx, bar, "I", _PP)
    raw = _marked_pitch(ctx, bar, earlier=False)
    below = _fit_lead(ctx, raw) if raw is not None else None
    return _sung(ctx, bar, "I", _P, lead_from=_cut(ctx), bass_length=2, below=below)


def _castillo_intro_long(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _bass_alone(ctx, bar, "I", _PP)
    if role == 1:
        return _sung(ctx, bar, "I", _P, lead_from=_cut(ctx), bass_length=2)
    if role == 2:
        return _sung(ctx, bar, "IV", _MP, lead_from=_cut(ctx), bass_length=2)
    specs = _bass_alone(ctx, bar, "V7", _MP, _cut(ctx))
    if _into_body(ctx, bar, False):
        specs.extend(_scale_into(ctx, bar, _cut(ctx), 1, _MP))
        return specs
    return specs + _sung(ctx, bar, "V7", _MP, lead_from=_cut(ctx), bass_length=0)


def _castillo_outro_short(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _sung(ctx, bar, "V7", _P, lead_from=0, bass_length=1, price=True)
    return _bell_chord(ctx, bar, _PP, picardy=ctx.mode == "minor")


def _castillo_outro_long(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _sung(ctx, bar, "IV", _P, lead_from=0, bass_length=2)
    if role == 1:
        return _sung(ctx, bar, "V7", _P, lead_from=0, bass_length=2)
    if role == 2:
        return _sung(ctx, bar, "I", _PP, lead_from=_cut(ctx), bass_length=2)
    return _bell_chord(ctx, bar, _PP, picardy=ctx.mode == "minor")


def _castillo(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    del index
    if closing and steps == 2:
        specs = _castillo_outro_short(ctx, bar, role)
    elif closing:
        specs = _castillo_outro_long(ctx, bar, role)
    elif steps == 2:
        specs = _castillo_intro_short(ctx, bar, role)
    else:
        specs = _castillo_intro_long(ctx, bar, role)
    return _finish(ctx, role, specs)


def _sonatina_intro_short(ctx, bar: int, role: int, closing: bool) -> list[tuple]:
    if role == 0:
        return _call(ctx, bar, "I", _P)
    if not _into_body(ctx, bar, closing):
        return _call(ctx, bar, "V7", _MP)
    cut = _cut(ctx)
    return _call(ctx, bar, "V7", _MP, motif=False) + _scale_into(ctx, bar, cut, ctx.epb - cut, _MP)


def _sonatina_intro_long(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _call(ctx, bar, "I", _PP, support=False, bass_whole=True)
    if role == 1:
        return _call(ctx, bar, "I", _P)
    if role == 2:
        return _call(ctx, bar, "V7", _MP, slur=True)
    return _held_echo(ctx, bar, "I", _MP, bass_edges=True)


def _sonatina_outro_short(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _call(ctx, bar, "V7", _MP)
    return _third(ctx, bar, _P)


def _sonatina_outro_long(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _call(ctx, bar, "IV", _P)
    if role == 1:
        return _call(ctx, bar, "V7", _MP)
    if role == 2:
        return _held_echo(ctx, bar, "I", _P, bass_edges=False)
    return _third(ctx, bar, _PP)


def _sonatina(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    del index
    if closing and steps == 2:
        specs = _sonatina_outro_short(ctx, bar, role)
    elif closing:
        specs = _sonatina_outro_long(ctx, bar, role)
    elif steps == 2:
        specs = _sonatina_intro_short(ctx, bar, role, closing)
    else:
        specs = _sonatina_intro_long(ctx, bar, role)
    return _finish(ctx, role, specs)


def _fandanguillo_intro_short(ctx, bar: int, role: int, closing: bool) -> list[tuple]:
    if role == 0:
        return _chord_specs(ctx, bar, "I", 0, _MF, accent=True, staccato=True)
    specs = _chord_specs(ctx, bar, "V7", 0, _MP, staccato=True)
    if _into_body(ctx, bar, closing):
        specs.extend(_fan_scale(ctx, bar, _MP))
    return specs


def _fandanguillo_intro_long(ctx, bar: int, role: int, closing: bool) -> list[tuple]:
    if role == 0:
        return _chord_specs(ctx, bar, "I", 0, _P, staccato=True)
    if role == 1:
        return _chord_specs(ctx, bar, "IV", 0, _P, staccato=True) + _single_lead(ctx, bar, "IV", _later_strong(ctx), _P)
    if role == 2:
        return _chord_specs(ctx, bar, "V7", 0, _MP, staccato=True)
    specs = _chord_specs(ctx, bar, "V7", 0, _MF, staccato=True)
    if _into_body(ctx, bar, closing):
        specs.extend(_fan_scale(ctx, bar, _MF))
    return specs


def _fandanguillo_outro_short(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _chord_specs(ctx, bar, "V7", 0, _MP, staccato=True)
    return _chord_specs(ctx, bar, "I", 0, _MF, accent=True, staccato=True)


def _fandanguillo_outro_long(ctx, bar: int, role: int) -> list[tuple]:
    if role == 0:
        return _chord_specs(ctx, bar, "IV", 0, _MP, staccato=True)
    if role == 1:
        return _chord_specs(ctx, bar, "V7", 0, _MP, staccato=True)
    if role == 2:
        return _single_lead(ctx, bar, "V7", 0, _P)
    return _fan_strokes(ctx, bar, "I", _MF, later_accent=True)


def _fandanguillo(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    del index
    if closing and steps == 2:
        specs = _fandanguillo_outro_short(ctx, bar, role)
    elif closing:
        specs = _fandanguillo_outro_long(ctx, bar, role)
    elif steps == 2:
        specs = _fandanguillo_intro_short(ctx, bar, role, closing)
    else:
        specs = _fandanguillo_intro_long(ctx, bar, role, closing)
    return _finish(ctx, role, specs)


def _danza(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    del index
    into = _into_body(ctx, bar, closing)
    if closing and steps == 2:
        if role == 0:
            specs = _danza_bar(ctx, bar, "V7", _MP, shape="full", scale_last=False, accent_later=False)
        else:
            specs = _danza_bar(ctx, bar, "I", _MF, shape="close-short", scale_last=False, accent_later=True)
    elif closing:
        shapes = {0: ("IV", _MP, "full"), 1: ("V7", _MP, "full"), 2: ("I", _P, "answer"), 3: ("I", _MF, "close-two")}
        name, velocity, shape = shapes.get(role, shapes[3])
        specs = _danza_bar(ctx, bar, name, velocity, shape=shape, scale_last=False, accent_later=False)
    elif steps == 2:
        if role == 0:
            specs = _danza_bar(ctx, bar, "I", _P, shape="full", scale_last=False, accent_later=False)
        else:
            specs = _danza_bar(ctx, bar, "V7", _MP, shape="full", scale_last=into, accent_later=False)
    elif role == 0:
        specs = _danza_bar(ctx, bar, "I", _P, shape="chord", scale_last=False, accent_later=False)
    elif role == 1:
        specs = _danza_bar(ctx, bar, "I", _P, shape="one", scale_last=False, accent_later=False)
    elif role == 2:
        specs = _danza_bar(ctx, bar, "V7", _MP, shape="one", scale_last=False, accent_later=False)
    else:
        specs = _danza_bar(ctx, bar, "V7", _MP, shape="full", scale_last=into, accent_later=False)
    return _finish(ctx, role, specs)


def _juglar(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    del index
    into = _into_body(ctx, bar, closing)
    if closing and steps == 2:
        specs = _juglar_motor(ctx, bar, "V7", _P, lead_in=False) if role == 0 else _juglar_hold(ctx, bar, "I", _PP)
    elif closing:
        if role == 0:
            specs = _juglar_motor(ctx, bar, "IV", _P, lead_in=False)
        elif role == 1:
            specs = _juglar_motor(ctx, bar, "V7", _P, lead_in=False)
        else:
            specs = _juglar_hold(ctx, bar, "I", _PP)
    elif steps == 2:
        if role == 0:
            specs = _juglar_motor(ctx, bar, "I", _PP, lead_in=False)
        else:
            specs = _juglar_motor(ctx, bar, "V7", _P, lead_in=into)
    elif role == 0:
        specs = _juglar_motor(ctx, bar, "I", _PP, lead_in=False)
    elif role == 1:
        specs = _juglar_motor(ctx, bar, "I", _P, lead_in=False)
    elif role == 2:
        specs = _juglar_motor(ctx, bar, "IV", _MP, lead_in=False)
    else:
        specs = _juglar_motor(ctx, bar, "V7", _MP, lead_in=into)
    return _finish(ctx, role, specs)


def _alcaniz(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    del index
    into = _into_body(ctx, bar, closing)
    if closing and steps == 2:
        if role == 0:
            specs = _alcaniz_bar(ctx, bar, "V7", _MP, groups=2, sustain=True, scale_later=False, accent_first=False, accent_later=False)
        else:
            specs = _alcaniz_bar(ctx, bar, "I", _MF, groups=2, sustain=False, scale_later=False, accent_first=False, accent_later=True)
    elif closing:
        if role == 0:
            specs = _alcaniz_bar(ctx, bar, "IV", _MP, groups=2, sustain=True, scale_later=False, accent_first=False, accent_later=False)
        elif role == 1:
            specs = _alcaniz_bar(ctx, bar, "V7", _MP, groups=2, sustain=True, scale_later=False, accent_first=False, accent_later=False)
        elif role == 2:
            specs = _alcaniz_bar(ctx, bar, "I", _P, groups=2, sustain=True, scale_later=False, accent_first=False, accent_later=False)
        else:
            specs = _alcaniz_bar(ctx, bar, "I", _MF, groups=2, sustain=False, scale_later=False, accent_first=False, accent_later=True)
    elif steps == 2:
        if role == 0:
            specs = _alcaniz_bar(ctx, bar, "I", _P, groups=2, sustain=True, scale_later=False, accent_first=True, accent_later=False)
        else:
            specs = _alcaniz_bar(ctx, bar, "V7", _MP, groups=2, sustain=True, scale_later=into, accent_first=False, accent_later=False)
    elif role == 0:
        specs = _alcaniz_bar(ctx, bar, "I", _P, groups=1, sustain=True, scale_later=False, accent_first=False, accent_later=False)
    elif role == 1:
        specs = _alcaniz_bar(ctx, bar, "I", _P, groups=2, sustain=True, scale_later=False, accent_first=True, accent_later=False)
    elif role == 2:
        specs = _alcaniz_bar(ctx, bar, "V7", _MP, groups=2, sustain=True, scale_later=False, accent_first=False, accent_later=False)
    else:
        specs = _alcaniz_bar(ctx, bar, "V7", _MP, groups=2, sustain=True, scale_later=into, accent_first=False, accent_later=False)
    return _finish(ctx, role, specs)


def _olite(ctx, bar: int, role: int, *, steps: int, closing: bool, index: int) -> list[tuple]:
    into = _into_body(ctx, bar, closing)

    def chords(name: str, velocity: int, accents: str) -> list[tuple]:
        return _olite_chords(
            ctx,
            bar,
            name,
            velocity,
            accents=accents,
            index=index,
            steps=steps,
            closing=closing,
        )

    if closing and steps == 2:
        if role == 0:
            specs = chords("V7", _MP, "none")
        else:
            specs = chords("I", _MF, "later")
    elif closing:
        if role == 0:
            specs = chords("IV", _MP, "none")
        elif role == 1:
            specs = chords("V7", _MP, "none")
        elif role == 2:
            specs = _olite_breath(ctx, bar)
        else:
            specs = chords("I", _MF, "later")
    elif steps == 2:
        if role == 0:
            specs = chords("I", _P, "both")
        else:
            specs = chords("V7", _MP, "both")
            if into:
                specs.extend(_lead_in_scale(ctx, bar, _MP))
    elif role == 0:
        specs = chords("I", _P, "both")
    elif role == 1:
        specs = chords("I", _P, "both")
    elif role == 2:
        specs = chords("IV", _MP, "none")
    else:
        specs = chords("V7", _MF, "both")
        if into:
            specs.extend(_lead_in_scale(ctx, bar, _MF))
    return _finish(ctx, role, specs)


DOORS = {
    ("torroba", "castillo"): _castillo,
    ("torroba", "sonatina"): _sonatina,
    ("torroba", "fandanguillo"): _fandanguillo,
    ("torroba", "danza"): _danza,
    ("torroba", "torroba_tremolo"): _juglar,
    ("torroba", "alcaniz"): _alcaniz,
    ("torroba", "olite"): _olite,
}
