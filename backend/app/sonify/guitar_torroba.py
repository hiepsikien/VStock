"""Federico Moreno Torroba: castillo, sonatina, fandanguillo, and danza.

The Andalucian loop lives in the dialect. These patterns only read the placed
price. A leap into a strong beat is one sixteenth before that beat. A short
run into the apex is the same idea stretched to three approaches. Neither one
replaces the price note, and neither one is recorded as a scale passage.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.sonify.chords import Chord
from app.sonify.model import NoteEvent
from app.sonify.phrasing import MIN_RISE

_OPEN_BASS = (40, 45, 50)
_HARMONICS = frozenset({52, 57, 62, 67, 71, 76, 79})
_TORROBA_PATTERNS = frozenset({"castillo", "sonatina", "fandanguillo", "danza"})
_DEGREE_I = 0
_DEGREE_V = 7


def _torroba_primary(ctx, mood: str | None, *, framed_macro: bool = False) -> str:
    """One Torroba texture for a phrase or, when framed, a whole section.

    Unframed phrases use the 4/4 mood map at every meter. A framed scherzo
    in 6/8 is the only place `danza` is chosen. `danza` never stands in 4/4.
    """
    if ctx.bpm <= 72:
        return "castillo"
    if framed_macro and ctx.kind == "6/8":
        if mood in {"rally", "volatile"}:
            return "fandanguillo"
        if mood == "selloff":
            return "castillo"
        return "danza"
    if mood == "volatile":
        return "fandanguillo"
    if mood in {"rally", "selloff"}:
        return "sonatina"
    return "castillo"


def _torroba_contrast(ctx, primary: str) -> str:
    """The other formal area. Slow writing answers with the sonatina."""
    if ctx.bpm <= 72:
        return "sonatina"
    if ctx.kind == "6/8" and ctx.bpm > 72 and primary in {"danza", "fandanguillo"}:
        return "castillo"
    if primary == "castillo":
        return "sonatina"
    return "castillo"


_PEDAL_BARS = frozenset({"intro", "outro", "warmup", "cooldown"})


def _breath_tails(ctx, bar: int) -> list[set[int]]:
    """In-bar offsets of each phrase that closes in this bar, cut at `phrase.end`.

    `_owner` only sees the phrase that contains the downbeat. A phrase that
    starts later in the bar is still a tail, so this scans `ctx.phrases`.
    Pedal bars and a `held_over` phrase (which does not `close`) contribute
    nothing. The same scan covers every span: `_Ctx` has no span field.
    """
    if ctx.kind_at.get(bar, "phrase") in _PEDAL_BARS:
        return []
    epb = ctx.epb
    origin = bar * epb
    tails: list[set[int]] = []
    for phrase in ctx.phrases:
        if phrase.end <= phrase.start or not phrase.closes:
            continue
        if (phrase.end - 1) // epb != bar:
            continue
        start = max(phrase.start, origin)
        stop = min(phrase.end, origin + epb)
        if stop <= start:
            continue
        tails.append({eighth - origin for eighth in range(start, stop)})
    return tails


def _closing_offsets(ctx, bar: int) -> set[int]:
    """Eighths in this bar that sit inside a closing phrase's last bar."""
    found: set[int] = set()
    for tail in _breath_tails(ctx, bar):
        found.update(tail)
    return found


def _attack_band(ctx, bar: int, offset: int, closing: set[int]) -> str:
    """`p` only on an attack whose eighth is inside the close."""
    if offset in closing:
        return "p"
    return ctx.band(bar)


def _bar_band(ctx, bar: int, closing: set[int]) -> str:
    """Bed for a note that sounds from the downbeat through the whole bar.

    `p` only when the close covers every eighth. A phrase that stops early
    leaves that bed on `ctx.band`, so the held Castillo price is not rewritten.
    """
    if all(offset in closing for offset in range(ctx.epb)):
        return "p"
    return ctx.band(bar)


def _open_bass_tone(ctx, written: int) -> bool:
    from app.sonify.guitar_frame import _is_open

    sounding = written + ctx.semitones
    return sounding in _OPEN_BASS and _is_open(ctx, written)


def _bass_window(ctx) -> tuple[int, int]:
    low = max(ctx.bass_low, 40 - ctx.semitones)
    high = min(ctx.bass_high, 53 - ctx.semitones)
    return low, high


def _torroba_bass(ctx, chord: Chord, bar: int, lead: int | None) -> int | None:
    """Open pedal in {40, 45, 50}, else the lowest chord tone in 40–53.

    Open G3 (55) is outside the bass ceiling. `uptrend` takes degree I when
    the chord has it, even fretted. `downtrend` takes degree V. `sideway`
    and a missing regime do not tilt.
    """
    low, high = _bass_window(ctx)
    if high < low:
        return None
    semi = ctx.semitones
    pcs = chord.pitch_classes

    def legal(written: int) -> bool:
        sounding = written + semi
        if sounding < 40 or sounding > 53 or sounding == 55:
            return False
        if written % 12 not in pcs:
            return False
        if lead is not None and written >= lead:
            return False
        return True

    def lowest(predicate) -> int | None:
        found = [note for note in range(low, high + 1) if legal(note) and predicate(note)]
        return min(found) if found else None

    regime = None
    regime_at = getattr(ctx, "regime_at", None) or {}
    if isinstance(regime_at, dict):
        regime = regime_at.get(bar)
    if regime == "uptrend" and _DEGREE_I in pcs:
        tilted = lowest(lambda note: note % 12 == _DEGREE_I)
        if tilted is not None:
            return tilted
    elif regime == "downtrend" and _DEGREE_V in pcs:
        tilted = lowest(lambda note: note % 12 == _DEGREE_V)
        if tilted is not None:
            return tilted
    opened = lowest(_open_bass_tone_for(ctx))
    if opened is not None:
        return opened
    return lowest(lambda _note: True)


def _open_bass_tone_for(ctx):
    def predicate(written: int) -> bool:
        return _open_bass_tone(ctx, written)

    return predicate


def _harmonic_velocity(ctx, midi: int, duration_beats: float, ordinary: int) -> int:
    """48 only when the sounding pitch is already a natural node and the hold is long."""
    sounding = midi + ctx.semitones
    if sounding in _HARMONICS and duration_beats >= 2:
        return 48
    return ordinary


def skips_bar_extra(ctx, event: NoteEvent) -> bool:
    """A note already painted 48 on a natural node does not take the whole-bar extra.

    Type 8's eighth and quarter are shorter than two beats, so they stay on the
    bass bed. That bed still takes the extra.
    """
    if event.midi is None or event.velocity != 48:
        return False
    return event.midi + ctx.semitones in _HARMONICS


def _torroba_inner(
    ctx,
    chord: Chord,
    lead: int,
    bass: int,
    *,
    allow_high: bool,
    prev_lead: int | None = None,
) -> int | None:
    """A chord tone under the price. A 3rd or 6th shadow only while the price steps."""
    semi = ctx.semitones
    lead_s = lead + semi
    bass_s = bass + semi
    cap_s = lead_s - 1 if allow_high else min(65, lead_s - 1)
    low = max(bass + 1, 50 - semi)
    high = min(lead - 1, cap_s - semi)
    if high < low:
        return None
    pcs = chord.pitch_classes

    def playable(note: int) -> bool:
        return _playable([bass_s, note + semi, lead_s])

    pool = [note for note in range(low, high + 1) if note % 12 in pcs]
    under = [note for note in pool if note + semi <= 65 and playable(note)]
    if under:
        return max(under)
    if prev_lead is not None and abs(lead - prev_lead) <= 2:
        shadows = []
        for interval in (3, 4, 8, 9):
            note = lead - interval
            if low <= note <= high and (_on_scale(note, ctx.mode) or note % 12 in pcs):
                shadows.append(note)
        fitted = [note for note in shadows if playable(note)]
        if fitted:
            return max(fitted)
    if allow_high:
        fitted = [note for note in pool if playable(note)]
        if fitted:
            return max(fitted)
    return None


def _gap_inner(ctx, chord: Chord, bar: int) -> int | None:
    """One middle note with no lead sounding, so it stays at or under 65."""
    semi = ctx.semitones
    low = max(ctx.mid_low, 50 - semi)
    high = min(ctx.mid_high, 65 - semi)
    if high < low:
        return None
    found = [note for note in range(low, high + 1) if note % 12 in chord.pitch_classes]
    if not found:
        return None
    playable = [note for note in found if _playable([note + semi])]
    return max(playable or found)


def _thin(eighths: list[int], ctx, bar: int) -> list[int]:
    """Keep inner offsets outside a close. Thin each closing tail on its own.

    Two or more inner offsets in one tail keep every other attack. A tail with
    exactly one inner offset drops that offset: the old `len < 2` guard would
    have preserved it. Castillo in 4/4 only plants inners at 2 and 6, so a
    phrase that ends at eighth 4 leaves offset 2 alone.
    """
    drop: set[int] = set()
    kept: set[int] = set()
    for tail in _breath_tails(ctx, bar):
        chosen = [offset for offset in eighths if offset in tail]
        if len(chosen) >= 2:
            drop.update(chosen)
            kept.update(chosen[::2])
        elif len(chosen) == 1:
            drop.add(chosen[0])
    return [offset for offset in eighths if offset not in drop or offset in kept]


def _lead_velocity(ctx, eighth: int, phrase, *, dance: bool) -> tuple[int, bool]:
    apex = _apex_eighths(ctx.phrases)
    ordinary = _note_velocity(eighth, 1, apex, phrase)
    if dance and eighth % ctx.epb in ctx.strong:
        return max(ordinary, 68), True
    if dance:
        return 64, False
    return ordinary, eighth % ctx.epb in ctx.strong


def _attack(eighth: int, midi: int, epb: int, velocity: int, *, accent: bool, length: int = 1) -> NoteEvent:
    event = _eighth_event(eighth, length, midi, epb, 1, velocity, accent)[0]
    return event


def _support_event(eighth: int, midi: int, epb: int, velocity: int, *, length: int = 1, staccato: bool = False) -> NoteEvent:
    event = _eighth_event(eighth, length, midi, epb, 2, velocity, False)[0]
    if staccato:
        return replace(event, staccato=True)
    return event


def _bass_event(eighth: int, midi: int, epb: int, velocity: int, *, length: int = 1, staccato: bool = False) -> NoteEvent:
    event = _eighth_event(eighth, length, midi, epb, 3, velocity, False)[0]
    if staccato:
        return replace(event, staccato=True)
    return event


def _bed(lead_vel: int, band: str) -> tuple[int, int]:
    return _under_lead(lead_vel, band)


def _render_castillo_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    epb = ctx.epb
    origin = bar * epb
    midi = _melody_at(ctx, origin)
    beats = epb * 0.5
    ordinary, _accent = _lead_velocity(ctx, origin, phrase, dance=False)
    velocity = _harmonic_velocity(ctx, midi, beats, ordinary)
    lead = written(origin, epb, midi, accent=True, velocity=velocity)
    closing = _closing_offsets(ctx, bar)
    # The price is one note from the downbeat. Its bass is the bar bed, not `p`,
    # unless the close itself runs through the last eighth.
    _inner_vel, bass_vel = _bed(velocity, _bar_band(ctx, bar, closing))
    bass = _torroba_bass(ctx, ctx.chord(bar), bar, midi)
    low = []
    if bass is not None:
        low = written(origin, epb, bass, velocity=bass_vel)
        low = [replace(event, voice=3, accent=False) for event in low]
    support: list[NoteEvent] = []
    if velocity == 48:
        return lead, support, low
    offsets = {2, 6} if ctx.kind == "4/4" else {2, 5} if ctx.kind == "6/8" else {2, 4}
    kept = _thin(sorted(offset for offset in offsets if offset < epb), ctx, bar)
    prev = None
    for offset in kept:
        sung = _melody_at(ctx, origin + offset)
        inner = None if bass is None else _torroba_inner(
            ctx, ctx.chord(bar), midi, bass, allow_high=True, prev_lead=prev
        )
        prev = sung
        if inner is None:
            continue
        band = _attack_band(ctx, bar, offset, closing)
        support.append(_support_event(origin + offset, inner, epb, _bed(velocity, band)[0]))
    return lead, support, low


def _approaches(ctx, target: int, count: int) -> list[int]:
    found: list[int] = []
    cursor = target
    for _step in range(count):
        nxt = _walk(cursor, -1, ctx.mode, ctx.treble_floor, ctx.treble_top)
        if nxt == cursor or nxt == target:
            break
        found.append(nxt)
        cursor = nxt
    found.reverse()
    return found


def _sixteenth(
    bar_eighth: int,
    slots_before: int,
    index: int,
    midi: int,
    epb: int,
    velocity: int,
    *,
    slur_start: bool,
) -> NoteEvent | None:
    """`slots_before` sixteenths end on the strong beat. `index` counts from the first.

    A downbeat's last sixteenth belongs to the previous bar. Beat 0 in 4/4
    puts that note at 3.75, and a three-note run starts at 3.25. Bar 0 has
    nowhere to put it.
    """
    bar = bar_eighth // epb
    beat = (bar_eighth % epb) * 0.5 - 0.25 * (slots_before - index)
    bar_beats = epb * 0.5
    while beat < -1e-9:
        bar -= 1
        beat += bar_beats
    if bar < 0:
        return None
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=0.25,
        voice=1,
        velocity=velocity,
        slur_start=slur_start,
    )


def _into_strong(ctx, target: int, eighth: int, phrase, *, run: bool) -> list[NoteEvent]:
    count = 3 if run else 1
    pitches = _approaches(ctx, target, count)
    if not pitches:
        return []
    events: list[NoteEvent] = []
    for index, midi in enumerate(pitches):
        if run:
            velocity = min(64, 56 + index * 4)
        else:
            velocity = _INNER
        event = _sixteenth(
            eighth,
            len(pitches),
            index,
            midi,
            ctx.epb,
            velocity,
            slur_start=index == 0,
        )
        if event is not None:
            events.append(event)
    return events


def _slur_leave(event: NoteEvent) -> NoteEvent:
    """The slur starts here, or keeps going if this note was its end."""
    if event.slur_stop:
        return replace(event, slur_stop=False)
    if event.slur_start:
        return event
    return replace(event, slur_start=True)


def _slur_arrive(event: NoteEvent) -> NoteEvent:
    """The slur ends here, unless this note already opens a later one.

    A note never carries both flags. `musicxml.py` writes `start` before `stop`
    on one slur number, so both flags on the middle note close an empty slur
    and leave the earlier one open.
    """
    if event.slur_start:
        return replace(event, slur_start=False)
    if event.slur_stop:
        return event
    return replace(event, slur_stop=True)


def _render_sonatina_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    epb = ctx.epb
    origin = bar * epb
    strong = [offset for offset in ctx.strong if offset < epb]
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    prev_midi = None
    prev_at: int | None = None
    prev_offset: int | None = None
    for offset in strong:
        eighth = origin + offset
        midi = _melody_at(ctx, eighth)
        velocity, accent = _lead_velocity(ctx, eighth, phrase, dance=False)
        event = _attack(eighth, midi, epb, velocity, accent=accent)
        # Both beats of this bar are sonatina. Block the slur only when the
        # earlier beat's phrase closes before this beat; one phrase may still join them.
        blocked = (
            prev_offset is not None
            and prev_midi is not None
            and offset > 0
            and _sonatina_slur_blocked(ctx, origin + prev_offset, eighth)
        )
        if prev_midi is not None and offset > 0 and not blocked:
            gap = abs(midi - prev_midi)
            at_apex = (
                phrase is not None
                and phrase.runs
                and phrase.apex.start <= eighth < phrase.apex.end
            )
            run = gap > 2 and phrase is not None and phrase.rise >= MIN_RISE and at_apex
            leap = gap > 2 and not run
            if run or leap:
                approaches = _into_strong(ctx, midi, eighth, phrase, run=run)
                if approaches:
                    lead.extend(approaches)
                    event = _slur_arrive(event)
            elif 1 <= gap <= 2 and prev_at is not None:
                lead[prev_at] = _slur_leave(lead[prev_at])
                event = _slur_arrive(event)
        prev_at = len(lead)
        lead.append(event)
        prev_midi = midi
        prev_offset = offset
    closing = _closing_offsets(ctx, bar)
    chord = ctx.chord(bar)
    for offset in strong:
        eighth = origin + offset
        midi = _melody_at(ctx, eighth)
        velocity = next(event.velocity or 64 for event in lead if event.voice == 1 and abs(event.beat - offset * 0.5) < 1e-6 and event.duration_beats >= 0.5)
        band = _attack_band(ctx, bar, offset, closing)
        _inner_vel, bass_vel = _bed(velocity, band)
        bass = _torroba_bass(ctx, chord, bar, midi)
        if bass is not None:
            low.append(_bass_event(eighth, bass, epb, bass_vel))
    inners = _thin(
        [offset for offset in range(epb) if offset not in set(ctx.strong)],
        ctx,
        bar,
    )
    prev = None
    for offset in inners:
        sung = _melody_at(ctx, origin + offset)
        bass = _torroba_bass(ctx, chord, bar, sung)
        if bass is None:
            continue
        inner = _torroba_inner(ctx, chord, sung, bass, allow_high=False, prev_lead=prev)
        prev = sung
        if inner is None:
            continue
        band = _attack_band(ctx, bar, offset, closing)
        support.append(_support_event(origin + offset, inner, epb, _bed(64, band)[0]))
    sixteenths = [event for event in lead if abs((event.duration_beats or 0) - 0.25) < 1e-6]
    if sixteenths:
        window_start = min(_start16(event, epb) for event in sixteenths)
        window_end = max(_start16(event, epb) + 1 for event in sixteenths)
        support = _clear_support(support, window_start, window_end, epb)
    lead.sort(key=lambda event: (event.beat, event.duration_beats))
    return lead, support, low


def _fandanguillo_melody(kind: str) -> tuple[int, ...]:
    if kind == "6/8":
        return (2, 3)
    if kind == "3/4":
        return (2, 4)
    return (2, 4, 6)


def _danza_chords(kind: str) -> tuple[int, ...]:
    if kind == "6/8":
        return (0, 3)
    return (0,)


def _danza_melody(kind: str) -> tuple[int, ...]:
    if kind == "6/8":
        return (1, 2, 4, 5)
    return (1, 2, 4)


def _block(
    ctx,
    bar: int,
    offset: int,
    phrase,
    *,
    staccato: bool,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    epb = ctx.epb
    eighth = bar * epb + offset
    midi = _melody_at(ctx, eighth)
    dance_strong = offset in ctx.strong
    ordinary = _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), phrase)
    velocity = max(ordinary, 68) if dance_strong else 64
    accent = dance_strong
    band = _attack_band(ctx, bar, offset, _closing_offsets(ctx, bar))
    inner_vel, bass_vel = _bed(velocity, band)
    bass = _torroba_bass(ctx, ctx.chord(bar), bar, midi)
    if bass is not None and not _playable([bass + ctx.semitones, midi + ctx.semitones]):
        bass = None
    lead = [_attack(eighth, midi, epb, velocity, accent=accent)]
    if staccato:
        lead = [replace(lead[0], staccato=True)]
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    if bass is not None:
        low.append(_bass_event(eighth, bass, epb, bass_vel, staccato=staccato))
        inner = _torroba_inner(ctx, ctx.chord(bar), midi, bass, allow_high=True)
        if inner is not None:
            support.append(_support_event(eighth, inner, epb, inner_vel, staccato=staccato))
    return lead, support, low


def _answer(ctx, bar: int, offset: int, phrase) -> NoteEvent:
    epb = ctx.epb
    eighth = bar * epb + offset
    midi = _melody_at(ctx, eighth)
    strong = offset in ctx.strong
    if strong:
        ordinary = _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), phrase)
        return _attack(eighth, midi, epb, max(ordinary, 68), accent=True)
    return _attack(eighth, midi, epb, 64, accent=False)


def _rasgueado_onsets(voices: list[int]) -> dict[int, float]:
    """Low-to-high onsets a twelfth apart. A missing voice closes the gap."""
    ordered = [voice for voice in (3, 2, 1) if voice in voices]
    return {voice: index / 12.0 for index, voice in enumerate(ordered)}


def _rasgueado_partition(
    lower: list[int],
    lead_s: int,
    bass_cap: int,
    support_cap: int,
) -> list[tuple[list[int], list[int]]]:
    """Split sounding pitches below the lead into bass then support.

    Pitches increase, so the cut is a single index. Bass stays at or below 53
    and support stays at or above 50, with every bass note under every support.
    """
    found: list[tuple[list[int], list[int]]] = []
    for cut in range(len(lower) + 1):
        bass = lower[:cut]
        support = lower[cut:]
        if len(bass) > bass_cap or len(support) > support_cap:
            continue
        if any(pitch > 53 for pitch in bass):
            continue
        if len(bass) == 2 and (bass[1] - bass[0]) not in {5, 7, 12}:
            continue
        if any(pitch < 50 or pitch >= lead_s for pitch in support):
            continue
        if bass and support and max(bass) >= min(support):
            continue
        found.append((bass, support))
    return found


def _rasgueado_voicing(
    ctx,
    bar: int,
    lead: int,
    max_notes: int,
) -> tuple[list[int], list[int], int]:
    """Written `(bass, support, lead)` for one rolled chord.

    Type 1 passes `max_notes=6` and keeps 5–6 strings when the hand allows.
    Type 2 passes `max_notes=4` and keeps 3–4. A unison or an unplayable bass
    falls back to two voices, or to the lead alone.
    """
    from app.sonify.guitar_patterns import _MAX_FRET, _OPENS, _playable

    semi = ctx.semitones
    lead_s = lead + semi
    chord = ctx.chord(bar)
    pcs = chord.pitch_classes
    root = chord.pitches[0] % 12
    raw_bass = _torroba_bass(ctx, chord, bar, lead)
    preferred = None if raw_bass is None else raw_bass + semi
    bass_cap = 2 if max_notes == 6 else 1
    support_cap = 3 if max_notes == 6 else 2
    lead_strings = [
        (string, lead_s - open_pitch)
        for string, open_pitch in enumerate(_OPENS)
        if 0 <= lead_s - open_pitch <= _MAX_FRET[string]
    ]
    best_key: tuple | None = None
    best: tuple[list[int], list[int]] | None = None

    def consider(chosen: list[tuple[int, int, int]]) -> None:
        nonlocal best_key, best
        pitches = [pitch for _string, pitch, _fret in chosen]
        frets = [fret for _string, _pitch, fret in chosen if fret > 0]
        if frets and max(frets) - min(frets) > 5:
            return
        if not _playable(pitches):
            return
        lower = pitches[:-1]
        partitions = _rasgueado_partition(lower, lead_s, bass_cap, support_cap)
        if lower and not partitions:
            return
        if not partitions:
            partitions = [([], [])]
        for bass, support in partitions:
            lowest = pitches[0]
            rootish = int(
                lowest % 12 == root or (preferred is not None and lowest == preferred)
            )
            key = (
                int(all(right - left >= 3 for left, right in zip(pitches, pitches[1:]))),
                len(chosen),
                int(bool(bass) and bool(support)),
                rootish,
                -(max(frets) if frets else 0),
                sum(pitches),
                tuple(pitches),
            )
            if best_key is None or key > best_key:
                best_key = key
                best = (bass, support)

    def search(start: int, chosen: list[tuple[int, int, int]], lead_string: int, lead_fret: int) -> None:
        if len(chosen) + 1 <= max_notes and (not chosen or chosen[-1][1] < lead_s):
            consider([*chosen, (lead_string, lead_s, lead_fret)])
        if max_notes - 1 - len(chosen) <= 0:
            return
        for string in range(start, lead_string):
            open_pitch = _OPENS[string]
            for fret in range(_MAX_FRET[string] + 1):
                pitch = open_pitch + fret
                if pitch >= lead_s:
                    break
                if pitch % 12 not in pcs:
                    continue
                if chosen and pitch <= chosen[-1][1]:
                    continue
                trial = [note[2] for note in chosen if note[2] > 0]
                if fret > 0:
                    trial.append(fret)
                if lead_fret > 0:
                    trial.append(lead_fret)
                if trial and max(trial) - min(trial) > 5:
                    continue
                chosen.append((string, pitch, fret))
                search(string + 1, chosen, lead_string, lead_fret)
                chosen.pop()

    for lead_string, lead_fret in lead_strings:
        search(0, [], lead_string, lead_fret)
    if best is None:
        return [], [], lead
    bass, support = best
    return [pitch - semi for pitch in bass], [pitch - semi for pitch in support], lead


def _stamp_rasgueado(
    bar: int,
    bass_notes: list[int],
    support_notes: list[int],
    lead_midi: int,
    *,
    bass_level: int,
    support_level: int,
    lead_level: int,
    lead_release: float,
    accent: bool,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Place a rolled chord. Two voices close the gap. A lone lead stays on the beat."""
    voices = [voice for voice, notes in ((3, bass_notes), (2, support_notes), (1, [lead_midi])) if notes]
    onsets = _rasgueado_onsets(voices)
    releases = {3: 0.5, 2: 0.5, 1: lead_release}
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for midi in bass_notes:
        beat = onsets[3]
        low.append(
            NoteEvent(
                bar=bar,
                beat=beat,
                midi=midi,
                duration_beats=releases[3] - beat,
                voice=3,
                velocity=bass_level,
            )
        )
    for midi in support_notes:
        beat = onsets[2]
        support.append(
            NoteEvent(
                bar=bar,
                beat=beat,
                midi=midi,
                duration_beats=releases[2] - beat,
                voice=2,
                velocity=support_level,
            )
        )
    beat = onsets[1]
    lead.append(
        NoteEvent(
            bar=bar,
            beat=beat,
            midi=lead_midi,
            duration_beats=releases[1] - beat,
            voice=1,
            velocity=lead_level,
            accent=accent,
        )
    )
    return lead, support, low


def _fandanguillo_rolls_bar(ctx, bar: int, phrase) -> bool:
    """Roll the opening of a multi-bar phrase (or a single-phrase fixture).

    One-bar phrases in a multi-phrase movement stay block chords so consecutive
    bars do not fire a 6-string rasgueado on every downbeat.
    """
    if phrase is None:
        return True
    bars = _bars_of(ctx, phrase)
    if not bars or bar != bars[0]:
        return False
    return len(bars) >= 2 or len(ctx.phrases) <= 1


def _render_fandanguillo_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    if _fandanguillo_rolls_bar(ctx, bar, phrase):
        eighth = bar * ctx.epb
        midi = _melody_at(ctx, eighth)
        ordinary = _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), phrase)
        velocity = max(ordinary, 68)
        band = _attack_band(ctx, bar, 0, _closing_offsets(ctx, bar))
        support_level, bass_level = _bed(velocity, band)
        bass_notes, support_notes, sung = _rasgueado_voicing(ctx, bar, midi, 6)
        lead, support, low = _stamp_rasgueado(
            bar,
            bass_notes,
            support_notes,
            sung,
            bass_level=bass_level,
            support_level=support_level,
            lead_level=velocity,
            lead_release=0.5,
            accent=True,
        )
    else:
        lead, support, low = _block(ctx, bar, 0, phrase, staccato=False)
    for offset in _fandanguillo_melody(ctx.kind):
        if offset < ctx.epb:
            lead.append(_answer(ctx, bar, offset, phrase))
    gaps = [
        offset
        for offset in range(ctx.epb)
        if offset != 0 and offset not in _fandanguillo_melody(ctx.kind)
    ]
    closing = _closing_offsets(ctx, bar)
    for offset in _thin(gaps, ctx, bar):
        inner = _gap_inner(ctx, ctx.chord(bar), bar)
        if inner is None:
            continue
        band = _attack_band(ctx, bar, offset, closing)
        support.append(_support_event(bar * ctx.epb + offset, inner, ctx.epb, _bed(64, band)[0]))
    return lead, support, low


def _render_danza_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    melody = set(_danza_melody(ctx.kind))
    for offset in _danza_chords(ctx.kind):
        if offset >= ctx.epb:
            continue
        part_lead, part_support, part_low = _block(ctx, bar, offset, phrase, staccato=True)
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)
    for offset in _danza_melody(ctx.kind):
        if offset < ctx.epb:
            lead.append(_answer(ctx, bar, offset, phrase))
    gaps = [offset for offset in range(ctx.epb) if offset not in _danza_chords(ctx.kind) and offset not in melody]
    closing = _closing_offsets(ctx, bar)
    for offset in _thin(gaps, ctx, bar):
        inner = _gap_inner(ctx, ctx.chord(bar), bar)
        if inner is None:
            continue
        band = _attack_band(ctx, bar, offset, closing)
        support.append(_support_event(bar * ctx.epb + offset, inner, ctx.epb, _bed(64, band)[0]))
    return lead, support, low


def _previous_strong(ctx, eighth: int) -> int | None:
    strong = {offset for offset in ctx.strong if offset < ctx.epb}
    for cursor in range(eighth - 1, -1, -1):
        if cursor % ctx.epb in strong:
            return cursor
    return None


def _phrase_at(ctx, eighth: int):
    for phrase in ctx.phrases:
        if phrase.start <= eighth < phrase.end and phrase.runs:
            return phrase
    return None


def _sonatina_slur_blocked(ctx, earlier: int, later: int) -> bool:
    """True when the earlier strong beat's phrase closes before `later`.

    The caller has already required both beats to be sonatina. One phrase that
    still contains the later beat may slur and pick up, even when that phrase
    `closes` at its own end. `held_over` is not the gate: `closes` is already
    false for it, and a castillo hold into sonatina is a different pattern.
    """
    phrase = _phrase_at(ctx, earlier)
    return phrase is not None and phrase.closes and later >= phrase.end


def _price_note(lead: list[NoteEvent], eighth: int, epb: int) -> int | None:
    """The strong-beat price, or the held note still sounding there."""
    when = eighth * 2
    attack = None
    cover = None
    cover_at = -1
    for index, event in enumerate(lead):
        if event.midi is None or event.duration_beats + 1e-9 < 0.5:
            continue
        begin = _start16(event, epb)
        if begin == when:
            attack = index
            continue
        if begin <= when < begin + _dur16(event) and begin >= cover_at:
            cover = index
            cover_at = begin
    return attack if attack is not None else cover


def _clear_support(support: list[NoteEvent], start: int, end: int, epb: int) -> list[NoteEvent]:
    """Drop or shorten an inner note that would sound under a pickup. Bass stays."""
    kept: list[NoteEvent] = []
    for event in support:
        if event.midi is None:
            kept.append(event)
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if finish <= start or begin >= end:
            kept.append(event)
            continue
        if begin < start:
            kept.extend(
                _spell16(begin, start - begin, event.midi, epb, event.voice, event.velocity, event.accent)
            )
    return kept


@dataclass(frozen=True)
class _Attack:
    beat: float
    midi: int
    duration: float
    voice: int
    written: int
    steps: int
    accent: bool = False
    staccato: bool = False
    slur_start: bool = False
    slur_stop: bool = False
    group: int | None = None


def _drop_level(written: int, steps: int) -> int:
    """Micro steps after the written velocity. The whole-bar extra is uniform, so the gap survives it."""
    if steps <= 0:
        return written
    return max(40, written - steps * _MICRO)


def _bars_of(ctx, phrase) -> list[int]:
    """Bars whose downbeat this phrase holds. A shared bar stays with that phrase."""
    if phrase.end <= phrase.start:
        return []
    first = (phrase.start + ctx.epb - 1) // ctx.epb
    if phrase.end <= first * ctx.epb:
        return []
    last = (phrase.end - 1) // ctx.epb
    if last < first:
        return []
    return list(range(first, last + 1))


def _body_phrase(ctx, phrase) -> bool:
    if phrase.end <= phrase.start or not phrase.runs:
        return False
    bar = phrase.start // ctx.epb
    return ctx.kind_at.get(bar, "phrase") not in _PEDAL_BARS


def _section_key(ctx, phrase):
    section = ctx.section(phrase.start // ctx.epb)
    if section is None:
        return None
    return (section.start, section.end)


def _span_type3(length: int) -> tuple[int, tuple[int, ...]]:
    if length >= 3:
        return 3, (length - 3, length - 2, length - 1)
    if length == 2:
        return 3, (0, 1)
    return 3, (0,)


def _span_sonatina(phrase, length: int, k: int) -> tuple[int | None, tuple[int, ...]]:
    if k % 3 == 0 and length >= 4:
        return 4, (0, 1)
    if k % 3 == 1 and phrase.rise >= MIN_RISE and length >= 2:
        start = max(0, length // 2 - 1)
        if start + 1 < length:
            return 2, (start, start + 1)
    if k % 3 == 2 and length >= 3:
        return 1, (1,)
    return None, ()


def _span_fandanguillo(phrase, length: int, k: int, closes: bool) -> tuple[int | None, tuple[int, ...]]:
    """Type 5 and type 2 never share a phrase, and neither one stands in for the other."""
    if phrase.rise < MIN_RISE:
        return None, ()
    room = length - 1 if closes else length
    if k % 2 == 0:
        if room >= 4:
            return 5, (0, 1, 2, 3)
        return None, ()
    if room < 2:
        return None, ()
    start = max(0, length // 2 - 1)
    if start + 1 >= (length - 1 if closes else length):
        return None, ()
    return 2, (start, start + 1)


def _span_danza(ctx, length: int, closes: bool) -> tuple[int | None, tuple[int, ...]]:
    # No 4/4 spelling. A 4/4 chapter never selects danza; the gate is here too.
    if ctx.kind not in {"3/4", "6/8"} or closes or length != 4:
        return None, ()
    return 6, (0, 1, 2, 3)


def _span_castillo(ctx, length: int, k: int) -> tuple[int | None, tuple[int, ...]]:
    if ctx.bpm > 72:
        return None, ()
    if k % 2 == 0:
        if length >= 5:
            return 7, tuple(range(5))
        if length in {2, 3, 4}:
            return 8, (0, 1)
        return None, ()
    if length >= 2:
        return 8, (0, 1)
    return None, ()


def select_torroba_figure(
    ctx,
    phrase,
    pattern: str,
    *,
    n: int | None,
    k: int | None,
    previous: int | None,
) -> tuple[int | None, tuple[int, ...]]:
    """One figure for a body phrase, or the base grid.

    `n` counts body phrases of this pattern in the section. A sonatina close
    does not take an `n`; it sings type 3. Odd `n` is the base grid. `k`
    counts even `n` from 0. The phrase after one that used the same figure
    id returns to the base grid.
    """
    if pattern not in _TORROBA_PATTERNS or phrase is None or phrase.end <= phrase.start:
        return None, ()
    length = len(_bars_of(ctx, phrase))
    if length <= 0:
        return None, ()
    closes = bool(phrase.closes)
    if pattern == "sonatina" and closes:
        figure, slots = _span_type3(length)
    elif n is None or n % 2 == 1:
        return None, ()
    elif pattern == "sonatina":
        figure, slots = _span_sonatina(phrase, length, 0 if k is None else k)
    elif pattern == "fandanguillo":
        figure, slots = _span_fandanguillo(phrase, length, 0 if k is None else k, closes)
    elif pattern == "danza":
        figure, slots = _span_danza(ctx, length, closes)
    else:
        figure, slots = _span_castillo(ctx, length, 0 if k is None else k)
    if figure is None or (previous is not None and previous == figure):
        return None, ()
    return figure, slots


def torroba_figure_plan(ctx, patterns: list[str]) -> dict[int, tuple[int, int, int]]:
    """Absolute bar → `(figure, index within the figure, figure length)`.

    Bars that stay on the base grid are absent. Pattern ids are unchanged.
    """
    if ctx.ensemble != "torroba":
        return {}
    grouped: dict[object, list[int]] = {}
    for index, phrase in enumerate(ctx.phrases):
        if index >= len(patterns) or patterns[index] not in _TORROBA_PATTERNS:
            continue
        if not _body_phrase(ctx, phrase):
            continue
        grouped.setdefault(_section_key(ctx, phrase), []).append(index)
    plan: dict[int, tuple[int, int, int]] = {}
    for indexes in grouped.values():
        counters: dict[str, int] = {}
        previous: int | None = None
        for index in indexes:
            phrase = ctx.phrases[index]
            pattern = patterns[index]
            if pattern == "sonatina" and phrase.closes:
                n: int | None = None
                k: int | None = None
            else:
                n = counters.get(pattern, 0)
                counters[pattern] = n + 1
                k = n // 2
            figure, slots = select_torroba_figure(
                ctx, phrase, pattern, n=n, k=k, previous=previous
            )
            if figure is None:
                previous = None
                continue
            bars = _bars_of(ctx, phrase)
            for slot_index, local in enumerate(slots):
                if 0 <= local < len(bars):
                    plan[bars[local]] = (figure, slot_index, len(slots))
            previous = figure
    return plan


def _realize(ctx, bar: int, attacks: list[_Attack]) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Bass and support take their steps. Lead steps go through `_micro_fits`.

    Repeated notes that share a group take the shortest step that still fits.
    """
    bar_beats = ctx.epb * 0.5
    heard: dict[int, int] = {}
    for index, attack in enumerate(attacks):
        if attack.voice != 1:
            heard[index] = _drop_level(attack.written, attack.steps)

    def covering(voice: int, beat: float) -> int | None:
        when = bar * bar_beats + beat
        found = None
        started = -1.0
        for index, attack in enumerate(attacks):
            if attack.voice != voice:
                continue
            start = bar * bar_beats + attack.beat
            if start <= when + 1e-9 < start + attack.duration and start >= started:
                found = heard[index]
                started = start
        return found

    groups: dict[int, list[int]] = {}
    fitted: dict[int, int] = {}
    for index, attack in enumerate(attacks):
        if attack.voice != 1:
            continue
        survived = _micro_fits(
            attack.written,
            covering(3, attack.beat),
            covering(2, attack.beat),
            attack.steps,
        )
        if attack.group is None:
            fitted[index] = survived
        else:
            groups.setdefault(attack.group, []).append(index)
            fitted[index] = survived
    for members in groups.values():
        shared = min(fitted[index] for index in members)
        for index in members:
            fitted[index] = shared
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for index, attack in enumerate(attacks):
        velocity = fitted[index] if attack.voice == 1 else heard[index]
        if attack.voice == 1:
            velocity = _drop_level(attack.written, velocity)
        event = NoteEvent(
            bar=bar,
            beat=attack.beat,
            midi=attack.midi,
            duration_beats=attack.duration,
            voice=attack.voice,
            velocity=velocity,
            accent=attack.accent,
            staccato=attack.staccato,
            slur_start=attack.slur_start,
            slur_stop=attack.slur_stop,
        )
        if attack.voice == 1:
            lead.append(event)
        elif attack.voice == 2:
            support.append(event)
        else:
            low.append(event)
    return lead, support, low


class _Pen:
    def __init__(self, ctx, bar: int, phrase, pattern: str, *, index: int, count: int, next_figure: int | None):
        self.ctx = ctx
        self.bar = bar
        self.phrase = phrase
        self.pattern = pattern
        self.index = index
        self.count = count
        self.next_figure = next_figure
        self.attacks: list[_Attack] = []
        self._groups = 0

    @property
    def epb(self) -> int:
        return self.ctx.epb

    @property
    def origin(self) -> int:
        return self.bar * self.ctx.epb

    @property
    def strong(self) -> set[int]:
        return {offset for offset in self.ctx.strong if offset < self.epb}

    @property
    def beats(self) -> float:
        return self.epb * 0.5

    def group(self) -> int:
        self._groups += 1
        return self._groups

    def mel(self, eighth: int) -> int:
        return _melody_at(self.ctx, self.origin + eighth)

    def _eighth_at(self, beat: float) -> int:
        return min(self.epb - 1, max(0, int(beat * 2 + 1e-9)))

    def _phrase_covering(self, eighth: int):
        """The sentence that owns this eighth, not only the downbeat's phrase.

        A bar can close one phrase and open the next. The new sentence starts
        at its own swell instead of continuing the phrase that held the downbeat.
        """
        found = _phrase_at(self.ctx, self.origin + eighth)
        return found if found is not None else self.phrase

    def _ordinary(self, eighth: int) -> int:
        phrase = self._phrase_covering(eighth)
        return _note_velocity(self.origin + eighth, 1, _apex_eighths(self.ctx.phrases), phrase)

    def lead_level(self, eighth: int, *, strong: bool) -> tuple[int, bool]:
        dance = self.pattern in {"fandanguillo", "danza"}
        ordinary = self._ordinary(eighth)
        if dance and strong:
            return max(ordinary, 68), True
        if strong:
            return ordinary, eighth in self.strong
        return ordinary, False

    def dance_written(self, eighth: int) -> int:
        """Strong-beat level of a dance, including an off-beat note the figure writes at 68."""
        return max(self._ordinary(eighth), 68)

    def beds(self, lead_written: int) -> tuple[int, int, int]:
        support, bass = _under_lead(lead_written, self.ctx.band(self.bar))
        return support, bass, max(40, bass - 4)

    def _local_lead(self, eighth: int, written: int, midi: int) -> int:
        """Keep a level that already belongs to this eighth. Move a borrowed one.

        A cell often captures the downbeat, or the last note of a scale, and
        stamps it on every attack. The sentence is `_note_velocity` at the
        attack's own eighth. A harmonic painted 48 stays a harmonic. A dance
        floor of 68 stays a dance floor, then follows this eighth once the
        sentence rises past it. Micro steps are applied afterwards, so the
        gap inside the cell survives the move.
        """
        if written == 48 and midi + self.ctx.semitones in _HARMONICS:
            return written
        local = self.lead_level(eighth, strong=eighth in self.strong)[0]
        danced = self.dance_written(eighth)
        if written in {local, danced}:
            return written
        if self.pattern in {"fandanguillo", "danza"} and written >= 68:
            return danced
        return local

    def _cadence_bed(self, eighth: int, beat: float, duration: float, voice: int, written: int) -> int:
        """A closing eighth sits on `p`. The role (support, bass, weak bass) stays.

        A note that already rings the whole bar follows `_bar_band`: `p` only
        when the close covers every eighth. Anything else keeps the caller's bed.
        """
        closing = _closing_offsets(self.ctx, self.bar)
        if not closing:
            return written
        if beat <= 1e-9 and duration + 1e-9 >= self.beats:
            band = _bar_band(self.ctx, self.bar, closing)
        else:
            band = _attack_band(self.ctx, self.bar, eighth, closing)
        if band == self.ctx.band(self.bar):
            return written
        leads = (
            self.lead_level(eighth, strong=eighth in self.strong)[0],
            self.dance_written(eighth),
            self.lead_level(0, strong=0 in self.strong)[0],
            self.dance_written(0),
            64,
            68,
        )
        for source in leads:
            support, bass = _under_lead(source, self.ctx.band(self.bar))
            weak = max(40, bass - 4)
            if voice == 2 and written == support:
                role = 0
            elif voice == 3 and written == bass:
                role = 1
            elif voice == 3 and written == weak:
                role = 2
            else:
                continue
            next_support, next_bass = _under_lead(source, band)
            return (next_support, next_bass, max(40, next_bass - 4))[role]
        return written

    def add(self, beat: float, midi: int | None, duration: float, voice: int, written: int, steps: int, **flags) -> None:
        if midi is None or duration <= 0:
            return
        eighth = self._eighth_at(beat)
        if voice == 1:
            written = self._local_lead(eighth, written, midi)
        elif voice in {2, 3}:
            written = self._cadence_bed(eighth, beat, duration, voice, written)
        self.attacks.append(
            _Attack(
                beat=beat,
                midi=midi,
                duration=duration,
                voice=voice,
                written=written,
                steps=steps,
                accent=flags.get("accent", False),
                staccato=flags.get("staccato", False),
                slur_start=flags.get("slur_start", False),
                slur_stop=flags.get("slur_stop", False),
                group=flags.get("group"),
            )
        )

    def _thin_cadence(self, support: list[NoteEvent]) -> list[NoteEvent]:
        """Drop the inner attacks a base-grid close would thin.

        The lead still sings the cadence. The inner voice breathes, the same
        way Castillo and the dances leave a closing tail thinner than the bar.
        """
        drop: set[int] = set()
        for tail in _breath_tails(self.ctx, self.bar):
            chosen = sorted(tail)
            if len(chosen) >= 2:
                drop.update(chosen[1::2])
            elif len(chosen) == 1:
                drop.add(chosen[0])
        if not drop:
            return support
        return [note for note in support if self._eighth_at(note.beat) not in drop]

    def finish(self):
        lead, support, low = _realize(self.ctx, self.bar, self.attacks)
        return lead, self._thin_cadence(support), low

    def bass_of(self, lead: int | None) -> int | None:
        return _torroba_bass(self.ctx, self.ctx.chord(self.bar), self.bar, lead)

    def support_of(self, lead: int, bass: int | None, *, capped: bool) -> int | None:
        if bass is None:
            return None
        return _torroba_inner(
            self.ctx,
            self.ctx.chord(self.bar),
            lead,
            bass,
            allow_high=not capped,
        )

    def chord(self, eighth: int, *, lead_steps: int, bass: bool = True, support: bool = True, weak_bass: bool = False, dance_lead: bool = False) -> None:
        strong = eighth in self.strong
        if dance_lead:
            written = self.dance_written(eighth)
            accent = strong and lead_steps == 0
        else:
            written, accent = self.lead_level(eighth, strong=strong)
            accent = accent and lead_steps == 0
        midi = self.mel(eighth)
        support_level, bass_level, weak = self.beds(written)
        low = self.bass_of(midi)
        inner = self.support_of(midi, low, capped=False)
        beat = eighth * 0.5
        self.add(beat, midi, 0.5, 1, written, lead_steps, accent=accent)
        if support and inner is not None:
            self.add(beat, inner, 0.5, 2, support_level, 0)
        if bass and low is not None:
            self.add(beat, low, 0.5, 3, weak if weak_bass else bass_level, 0)

    def rasgueado(self, members: list[tuple], releases: dict[int, float]) -> None:
        """Place a rolled chord. `members` are `(voice, midi, written, steps, flags)`."""
        present = [member for member in members if member[1] is not None]
        onsets = _rasgueado_onsets([member[0] for member in present])
        for voice, midi, written, steps, flags in present:
            beat = onsets[voice]
            self.add(beat, midi, releases[voice] - beat, voice, written, steps, **flags)

    def grace(self, principal: int, others: list[int]) -> tuple[int, int] | None:
        upper = _walk(principal, 1, self.ctx.mode, self.ctx.treble_floor, self.ctx.treble_top)
        if upper == principal:
            return None
        semi = self.ctx.semitones
        pair = [upper + semi, principal + semi]
        if not _position_ok(pair):
            return None
        ordered = sorted({upper, principal})
        if any(abs(left - right) > 4 for left, right in zip(ordered, ordered[1:])):
            return None
        others_s = [note + semi for note in others]
        if not _playable([upper + semi, *others_s]) or not _playable([principal + semi, *others_s]):
            return None
        return upper, principal

    def low_price(self, eighth: int) -> int:
        pitch = self.mel(eighth)
        while pitch > 52:
            pitch -= 12
        chord = self.ctx.chord(self.bar)
        if pitch < 40:
            found = self.bass_of(None)
            return 40 if found is None else found
        tones = [note for note in range(40, 53) if note % 12 in chord.pitch_classes]
        if not tones:
            found = self.bass_of(None)
            return max(40, min(52, pitch)) if found is None else found
        return min(tones, key=lambda note: (abs(note - pitch), note))

    def same_chord_ahead(self) -> bool:
        if self.bar + 1 >= self.ctx.bars:
            return False
        return self.ctx.chord(self.bar) == self.ctx.chord(self.bar + 1)


def _open_rasgueado(
    pen: _Pen,
    written: int,
    *,
    lead_release: float,
    max_notes: int,
    accent: bool,
    bed_steps: int,
) -> None:
    """Roll eighth 0 from bass up to lead.

    `max_notes=6` is the strong fan (5–6 strings, beds at step 0). `max_notes=4`
    is the soft fan (3–4 strings). Two sounding voices stand at `0` and `1/12`.
    A lone lead stays on the beat.
    """
    sung = pen.mel(0)
    support_level, bass_level, _weak = pen.beds(written)
    bass_notes, support_notes, lead_midi = _rasgueado_voicing(pen.ctx, pen.bar, sung, max_notes)
    voices = [voice for voice, notes in ((3, bass_notes), (2, support_notes), (1, [lead_midi])) if notes]
    onsets = _rasgueado_onsets(voices)
    releases = {3: 0.5, 2: 0.5, 1: lead_release}
    for midi in bass_notes:
        beat = onsets[3]
        pen.add(beat, midi, releases[3] - beat, 3, bass_level, bed_steps)
    for midi in support_notes:
        beat = onsets[2]
        pen.add(beat, midi, releases[2] - beat, 2, support_level, bed_steps)
    beat = onsets[1]
    pen.add(beat, lead_midi, releases[1] - beat, 1, written, 0, accent=accent)


def _render_type1(pen: _Pen):
    """Six sixteenths per cycle. The last bass rings only into another type-1 bar."""
    lead_ref = pen.mel(0)
    low = pen.bass_of(lead_ref)
    if low is None:
        return pen.finish()
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, _weak = pen.beds(written)
    higher, lower = _two_chord_tones(pen, lead_ref, low)
    cycles = [0.0, 1.5]
    for cycle_index, start in enumerate(cycles):
        eighth = int(round(start * 2))
        sung = pen.mel(eighth)
        level, _mark = pen.lead_level(eighth, strong=eighth in pen.strong)
        pen.add(start, sung, 0.25, 1, level, 0, accent=True)
        if higher is not None:
            pen.add(start + 0.25, higher, 0.25, 2, support_level, 1)
        if lower is not None:
            pen.add(start + 0.5, lower, 0.25, 2, support_level, 2)
        last = cycle_index == len(cycles) - 1
        if last:
            until_line = pen.beats - (start + 0.75)
            rings = pen.next_figure == 1 and pen.same_chord_ahead()
            duration = until_line + 0.75 if rings else until_line
        else:
            duration = 1.5
        pen.add(start + 0.75, low, duration, 3, bass_level, 0)
        if lower is not None:
            pen.add(start + 1.0, lower, 0.25, 2, support_level, 2)
        if higher is not None:
            pen.add(start + 1.25, higher, 0.25, 2, support_level, 1)
    if pen.epb >= 8:
        ceiling = pen.mel(3)
        inner = pen.support_of(ceiling, low, capped=True) or higher
        for eighth in (6, 7):
            pen.add(eighth * 0.5, inner, 0.5, 2, support_level, 1)
    return pen.finish()


def _two_chord_tones(pen: _Pen, lead: int, bass: int) -> tuple[int | None, int | None]:
    semi = pen.ctx.semitones
    chord = pen.ctx.chord(pen.bar)
    high = min(lead - 1, 65 - semi)
    found = []
    for note in range(bass + 1, high + 1):
        if note + semi < 50 or note % 12 not in chord.pitch_classes:
            continue
        if _playable([bass + semi, note + semi]):
            found.append(note)
    if not found:
        return None, None
    if len(found) == 1:
        return found[0], None
    return found[-1], found[-2]


def _render_type2(pen: _Pen):
    anchor = pen.mel(0)
    strong_written, _accent = pen.lead_level(0, strong=True)
    bass_level = pen.beds(strong_written)[1]
    if pen.index == 0:
        low = pen.bass_of(anchor)
        if pen.pattern == "fandanguillo":
            _open_rasgueado(
                pen, strong_written, lead_release=0.5, max_notes=6, accent=True, bed_steps=0
            )
        else:
            _open_rasgueado(
                pen, strong_written, lead_release=0.5, max_notes=4, accent=False, bed_steps=1
            )
        repeated = _rasgueado_pitch(pen, anchor)
        bundle = pen.group()
        if pen.ctx.kind == "4/4":
            clusters = (0.5, 2.5)
            bass_beat = 2.0
        else:
            clusters = (0.5, 2.0)
            bass_beat = 1.5
        for cluster in clusters:
            for step in range(4):
                pen.add(cluster + step * 0.25, repeated, 0.25, 1, strong_written, 1, group=bundle)
        if low is not None:
            pen.add(bass_beat, low, 0.5, 3, bass_level, 0)
        return pen.finish()
    for eighth in range(pen.epb):
        pen.chord(eighth, lead_steps=0 if eighth in pen.strong else 1)
    return pen.finish()


def _rasgueado_pitch(pen: _Pen, lead: int) -> int:
    chord = pen.ctx.chord(pen.bar)
    legal = [
        note
        for note in range(pen.ctx.treble_floor, lead)
        if note % 12 in chord.pitch_classes
    ]
    if not legal:
        return lead
    return max(legal)


def _render_type3(pen: _Pen):
    if pen.count == 1:
        role = "sustain"
    elif pen.count == 2:
        role = ("scale", "sustain")[pen.index]
    else:
        role = ("motif", "scale", "sustain")[pen.index]
    if role == "motif":
        return _type3_motif(pen)
    if role == "scale":
        return _type3_scale(pen)
    return _type3_sustain(pen)


def _type3_motif(pen: _Pen):
    written, _accent = pen.lead_level(0, strong=True)
    _open_rasgueado(pen, written, lead_release=0.5, max_notes=4, accent=False, bed_steps=1)
    repeated = pen.mel(1)
    bundle = pen.group()
    pen.add(0.5, repeated, 0.25, 1, written, 2, group=bundle)
    pen.add(0.75, repeated, 0.25, 1, written, 2, group=bundle)
    pen.add(1.0, repeated, 0.5, 1, written, 1)
    principal = pen.mel(3)
    neighbor = pen.grace(principal, [])
    if neighbor is None:
        pen.add(1.5, principal, 0.5, 1, written, 1)
    else:
        upper, body = neighbor
        pen.add(1.5, upper, 0.25, 1, written, 2, slur_start=True)
        pen.add(1.75, body, 0.25, 1, written, 1, slur_stop=True)
    for eighth in range(4, pen.epb):
        level, mark = pen.lead_level(eighth, strong=eighth in pen.strong)
        steps = 0 if eighth in pen.strong else 1
        pen.add(eighth * 0.5, pen.mel(eighth), 0.5, 1, level, steps, accent=mark and steps == 0)
    return pen.finish()


def _type3_scale(pen: _Pen):
    target = pen.mel(pen.epb - 1)
    written, _accent = pen.lead_level(pen.epb - 1, strong=pen.epb - 1 in pen.strong)
    line = _ascending(pen, target, pen.epb)
    for eighth, midi in enumerate(line):
        last = eighth == pen.epb - 1
        pen.add(
            eighth * 0.5,
            midi,
            0.5,
            1,
            written,
            0 if last else 1,
            accent=last and (pen.epb - 1) in pen.strong,
            staccato=True,
        )
    return pen.finish()


def _ascending(pen: _Pen, target: int, count: int) -> list[int]:
    low = pen.ctx.treble_floor
    target = max(low, min(pen.ctx.treble_top, target))
    scale = [pitch for pitch in range(low, target + 1) if _on_scale(pitch, pen.ctx.mode)]
    if target not in scale:
        scale.append(target)
        scale.sort()
    if not scale:
        return [target] * count
    if len(scale) >= count:
        return scale[-count:]
    return [scale[0]] * (count - len(scale)) + scale


def _type3_sustain(pen: _Pen):
    midi = pen.mel(0)
    ordinary, _accent = pen.lead_level(0, strong=True)
    duration = pen.beats
    velocity = _harmonic_velocity(pen.ctx, midi, duration, ordinary)
    _support_level, bass_level, _weak = pen.beds(ordinary)
    # A bell at 48 is not an accent: sonatina snap targets accented leads.
    pen.add(0.0, midi, duration, 1, velocity, 0, accent=velocity != 48)
    low = pen.bass_of(midi)
    pen.add(0.0, low, 0.5, 3, bass_level, 1)
    return pen.finish()


def _render_type4(pen: _Pen):
    if pen.index == 0:
        return _type4_call(pen)
    return _type4_answer(pen)


def _type4_call(pen: _Pen):
    reference = pen.mel(0)
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, weak_bass = pen.beds(written)
    low = pen.bass_of(reference)
    inner = pen.support_of(reference, low, capped=True)
    pen.add(0.0, low, 0.5, 3, bass_level, 0)
    pen.add(0.0, inner, 0.5, 2, support_level, 0)
    repeated = pen.mel(1)
    motif, _mark = pen.lead_level(1, strong=False)
    pen.add(0.5, repeated, 0.25, 1, motif, 1)
    pen.add(0.75, repeated, 0.25, 1, motif, 1)
    eighth_two, _mark = pen.lead_level(2, strong=False)
    pen.add(1.0, pen.mel(2), 0.5, 1, eighth_two, 1)
    principal = pen.mel(2)
    neighbor = pen.grace(principal, [])
    strong_resolution = pen.ctx.kind == "6/8"
    ornament, _mark = pen.lead_level(3, strong=False)
    resolution, resolve_mark = pen.lead_level(3, strong=strong_resolution)
    if neighbor is None:
        pen.add(
            1.5,
            principal,
            0.5,
            1,
            resolution,
            0 if strong_resolution else 1,
            accent=strong_resolution and resolve_mark,
        )
    else:
        upper, body = neighbor
        pen.add(1.5, upper, 0.25, 1, ornament, 1, slur_start=True)
        pen.add(
            1.75,
            body,
            0.25,
            1,
            resolution,
            0 if strong_resolution else 1,
            slur_stop=True,
            accent=strong_resolution and resolve_mark,
        )
    tail = range(4, pen.epb)
    for eighth in tail:
        sung = pen.mel(eighth)
        # 3/4 and 6/8 keep the weak lead at step 0. 4/4 drops eighths 5–7.
        # Eighth 4 of 4/4 reads its own eighth, not the downbeat captured above.
        if pen.ctx.kind == "4/4":
            lead_steps = 0 if eighth == 4 else 1
            level, mark = pen.lead_level(eighth, strong=(eighth == 4))
        else:
            lead_steps = 0
            level, _mark = pen.lead_level(eighth, strong=False)
            mark = False
        low_here = low if (pen.ctx.kind == "4/4" and eighth in {4, 7}) or (pen.ctx.kind != "4/4" and eighth == pen.epb - 1) else None
        weak = low_here is not None and not (pen.ctx.kind == "4/4" and eighth == 4)
        inner_here = pen.support_of(sung, low or sung - 5, capped=False)
        pen.add(eighth * 0.5, sung, 0.5, 1, level, lead_steps, accent=mark and lead_steps == 0)
        if inner_here is not None:
            pen.add(eighth * 0.5, inner_here, 0.5, 2, support_level, 1 if weak else 0)
        if low_here is not None:
            pen.add(eighth * 0.5, low_here, 0.5, 3, weak_bass if weak else bass_level, 0)
    return pen.finish()


def _type4_answer(pen: _Pen):
    sung = pen.mel(0)
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, weak_bass = pen.beds(written)
    low = pen.bass_of(sung)
    pen.add(0.0, sung, pen.beats, 1, written, 0, accent=True)
    pen.add(0.0, low, 0.5, 3, bass_level, 0)
    pair = _imitation_pair(pen, sung, low)
    if pair is not None:
        upper, lower = pair
        pen.add(0.5, upper, 0.25, 2, support_level, 1, slur_start=True)
        pen.add(0.75, lower, 0.25, 2, support_level, 1, slur_stop=True)
        pen.add(1.0, lower, 0.5, 2, support_level, 1)
        pen.add(1.5, upper, 0.25, 2, support_level, 1, slur_start=True)
        pen.add(1.75, lower, 0.25, 2, support_level, 1, slur_stop=True)
        pen.add(2.0, lower, 1.0, 2, support_level, 1)
    last = pen.epb - 1
    pen.add(last * 0.5, low, 0.5, 3, weak_bass, 0)
    return pen.finish()


def _imitation_pair(pen: _Pen, lead: int, bass: int | None) -> tuple[int, int] | None:
    semi = pen.ctx.semitones
    low = 50 - semi
    if bass is not None:
        low = max(low, bass + 1)
    high = min(lead - 1, 65 - semi)
    found = []
    for note in range(low, high + 1):
        if not _on_scale(note, pen.ctx.mode):
            continue
        sounding = [note + semi, lead + semi]
        if bass is not None:
            sounding.append(bass + semi)
        if _playable(sounding):
            found.append(note)
    if not found:
        return None
    if len(found) == 1:
        return found[0], found[0]
    for index in range(len(found) - 1, 0, -1):
        left, right = found[index - 1], found[index]
        if 1 <= right - left <= 2:
            return right, left
    return found[-1], found[-2]


def _render_type5(pen: _Pen):
    if pen.index == 0:
        return _type5_fan(pen)
    if pen.index == 1:
        return _type5_bass(pen)
    if pen.index == 2:
        return _type5_handoff(pen)
    return _type5_chords(pen)


def _type5_fan(pen: _Pen):
    written = pen.dance_written(0)
    bass_level = pen.beds(written)[1]
    _open_rasgueado(pen, written, lead_release=0.5, max_notes=6, accent=True, bed_steps=0)
    held = pen.low_price(1)
    bundle = pen.group()
    for offset, steps in enumerate((2, 2, 2)):
        pen.add((1 + offset) * 0.5, held, 0.5, 3, bass_level, steps, staccato=True, group=bundle)
    stepped = pen.low_price(4)
    room = pen.epb - 5
    pen.add(2.0, stepped, 0.5 * max(1, room + 1), 3, bass_level, 1)
    return pen.finish()


def _type5_bass(pen: _Pen):
    bass_level = pen.beds(pen.dance_written(0))[1]
    pen.add(0.0, pen.low_price(0), 0.5, 3, bass_level, 0)
    principal = pen.low_price(1)
    upper = _walk(principal, 1, pen.ctx.mode, 40, 52)
    pair = [upper + pen.ctx.semitones, principal + pen.ctx.semitones]
    if upper != principal and abs(upper - principal) <= 4 and _position_ok(pair):
        pen.add(0.5, upper, 0.25, 3, bass_level, 2, slur_start=True)
        pen.add(0.75, principal, 0.25, 3, bass_level, 1, slur_stop=True)
    else:
        pen.add(0.5, principal, 0.5, 3, bass_level, 1)
    pen.add(1.0, pen.low_price(2), 0.5, 3, bass_level, 1)
    pen.add(1.5, pen.low_price(3), 0.5, 3, bass_level, 1)
    pedal = pen.low_price(4)
    until_line = pen.beats - 2.0
    extra = pen.beats if pen.same_chord_ahead() and pen.bar + 1 < pen.ctx.bars else 0
    pen.add(2.0, pedal, until_line + extra, 3, bass_level, 1)
    return pen.finish()


def _type5_handoff(pen: _Pen):
    written = pen.dance_written(2)
    bundle = pen.group()
    steps = (2, 2, 1, 0)
    for offset, step in enumerate(steps):
        eighth = 2 + offset
        midi = pen.mel(2) if offset < 3 else pen.mel(eighth)
        group = bundle if step == 2 else None
        pen.add(eighth * 0.5, midi, 0.5, 1, written, step, accent=step == 0, group=group)
    return pen.finish()


def _type5_chords(pen: _Pen):
    if pen.ctx.kind == "6/8":
        points = ((0, 1.5), (3, 1.5))
    elif pen.ctx.kind == "3/4":
        points = ((0, 1.0), (2, 1.0), (4, 1.0))
    else:
        points = ((0, 1.0), (2, 1.0), (4, 1.0), (6, 1.0))
    for eighth, duration in points:
        sung = pen.mel(eighth)
        written = pen.dance_written(eighth)
        support_level, bass_level, _weak = pen.beds(written)
        low = pen.bass_of(sung)
        inner = pen.support_of(sung, low, capped=False)
        pen.add(eighth * 0.5, sung, duration, 1, written, 0, accent=True)
        if inner is not None:
            pen.add(eighth * 0.5, inner, duration, 2, support_level, 0)
        if low is not None:
            pen.add(eighth * 0.5, low, duration, 3, bass_level, 0)
    return pen.finish()


def _render_type6(pen: _Pen):
    if pen.index <= 1:
        return _type6_half_a(pen)
    if pen.index == 2:
        return _type6_half_b_open(pen)
    return _type6_half_b_follow(pen)


def _type6_half_a(pen: _Pen):
    written = pen.dance_written(0)
    support_level, bass_level, _weak = pen.beds(written)
    sung = pen.mel(0)
    low = pen.bass_of(sung)
    inner = pen.support_of(sung, low, capped=True)
    if pen.index == 0:
        duration = pen.beats if not pen.same_chord_ahead() else pen.beats * 2
        pen.add(0.0, low, duration, 3, bass_level, 0, accent=True)
        pen.add(0.0, inner, duration, 2, support_level, 0, accent=True)
    elif pen.bar > 0 and pen.ctx.chord(pen.bar) != pen.ctx.chord(pen.bar - 1):
        pen.add(0.0, low, pen.beats, 3, bass_level, 0, accent=True)
        pen.add(0.0, inner, pen.beats, 2, support_level, 0, accent=True)
    for half in (0, 1):
        group_index = pen.index * 2 + half
        start = half * 3
        first = pen.mel(start)
        if group_index == 0:
            bundle = pen.group()
            pen.add(start * 0.5, first, 0.5, 1, written, 0, accent=True)
            pen.add((start + 1) * 0.5, first, 0.5, 1, written, 2, group=bundle)
            pen.add((start + 2) * 0.5, first, 0.5, 1, written, 2, group=bundle)
            continue
        pen.add(start * 0.5, pen.mel(start), 0.5, 1, written, 1)
        middle = start + 1
        if group_index == 2:
            principal = pen.mel(middle)
            neighbor = pen.grace(principal, [note for note in (low, inner) if note is not None])
            if neighbor is None:
                pen.add(middle * 0.5, principal, 0.5, 1, written, 2)
            else:
                upper, body = neighbor
                pen.add(middle * 0.5, upper, 0.25, 1, written, 2, slur_start=True)
                pen.add(middle * 0.5 + 0.25, body, 0.25, 1, written, 2, slur_stop=True)
        else:
            pen.add(middle * 0.5, pen.mel(middle), 0.5, 1, written, 2)
        pen.add((start + 2) * 0.5, pen.mel(start + 2), 0.5, 1, written, 2)
    return pen.finish()


def _descend_into(pen: _Pen, target: int) -> list[int] | None:
    notes = [
        _walk(target, steps, pen.ctx.mode, pen.ctx.treble_floor, pen.ctx.treble_top)
        for steps in (3, 2, 1)
    ]
    if not (notes[0] > notes[1] > notes[2] > target):
        return None
    semi = pen.ctx.semitones
    if not _position_ok([note + semi for note in notes]):
        return None
    ordered = sorted(set(notes))
    if any(abs(left - right) > 4 for left, right in zip(ordered, ordered[1:])):
        return None
    return notes


def _type6_half_b_open(pen: _Pen):
    written = pen.dance_written(0)
    support_level, bass_level, _weak = pen.beds(written)
    destination = pen.mel(2)
    low = pen.bass_of(destination)
    inner = pen.support_of(destination, low, capped=True)
    # One staccato sixteenth. The three lead sixteenths take the rest of eighth 0 and all of eighth 1.
    pen.add(0.0, low, 0.25, 3, bass_level, 0, staccato=True)
    pen.add(0.0, inner, 0.25, 2, support_level, 0, staccato=True)
    descent = _descend_into(pen, destination)
    pitches = descent if descent is not None else [destination, destination, destination]
    bundle = pen.group() if descent is None else None
    for step, (beat, midi) in enumerate(zip((0.25, 0.5, 0.75), pitches)):
        steps = (2, 2, 1)[step]
        pen.add(
            beat,
            midi,
            0.25,
            1,
            written,
            steps,
            group=bundle if steps == 2 else None,
        )
    pen.add(1.0, destination, pen.beats * 2 - 1.0, 1, written, 0, accent=True)
    if inner is not None:
        pen.add(1.0, inner, 0.5, 2, support_level, 1)
    if low is not None:
        pen.add(1.5, low, 0.5, 3, bass_level, 2)
    if inner is not None:
        pen.add(2.0, inner, 0.5, 2, support_level, 1)
    return pen.finish()


def _type6_half_b_follow(pen: _Pen):
    written = pen.dance_written(0)
    support_level, bass_level, _weak = pen.beds(written)
    # The held lead started at eighth 2 of the previous half. Stay under that pitch.
    destination = _melody_at(pen.ctx, (pen.bar - 1) * pen.epb + 2) if pen.bar > 0 else pen.mel(0)
    low = pen.bass_of(destination)
    inner = pen.support_of(destination, low, capped=True)
    pen.add(0.0, low, 0.5, 3, bass_level, 2)
    pen.add(1.0, inner, 0.5, 2, support_level, 1)
    pen.add(2.5, low, 0.5, 3, bass_level, 2, staccato=True)
    return pen.finish()


def _render_type7(pen: _Pen):
    if pen.index == 0:
        return _type7_bar1(pen)
    if pen.index == 1:
        return _type7_bar2(pen)
    if pen.index == 2:
        return _type7_bar3(pen)
    if pen.index == 3:
        return _type7_bar4(pen)
    return _type7_bar5(pen)


def _type7_opening(pen: _Pen, *, resolution: str) -> None:
    """Dotted lead, the eighth arpeggio under it, and a two-sixteenth mordent."""
    sung = pen.mel(0)
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, _weak = pen.beds(written)
    low = pen.bass_of(sung)
    higher = pen.support_of(sung, low, capped=False)
    pen.add(0.0, sung, 1.5, 1, written, 0, accent=True)
    pen.add(0.0, higher, 0.5, 2, support_level, 0)
    pen.add(0.0, low, 0.5, 3, bass_level, 0)
    pen.add(0.5, low, 0.5, 3, bass_level, 1)
    pen.add(1.0, higher, 0.5, 2, support_level, 1)
    mordent_written = pen.lead_level(3, strong=False)[0]
    principal = pen.mel(4)
    neighbor = pen.grace(principal, [])
    if neighbor is None:
        pen.add(1.5, principal, 0.5, 1, mordent_written, 1)
    else:
        upper, body = neighbor
        pen.add(1.5, upper, 0.25, 1, mordent_written, 2, slur_start=True)
        pen.add(1.75, body, 0.25, 1, mordent_written, 1, slur_stop=True)
    resolved = pen.lead_level(4, strong=False)[0]
    if resolution == "half":
        pen.add(2.0, pen.mel(4), 2.0, 1, resolved, 0)
        pen.add(2.0, higher, 0.5, 2, support_level, 0)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pen.add(2.5, low, 0.5, 3, bass_level, 2)
        pen.add(3.0, higher, 0.5, 2, support_level, 1)
    elif resolution == "quarter":
        pen.add(2.0, pen.mel(4), 1.0, 1, resolved, 0)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pen.add(2.5, higher, 0.5, 2, support_level, 1)


def _type7_bar1(pen: _Pen):
    if pen.ctx.kind == "4/4":
        _type7_opening(pen, resolution="half")
    else:
        _type7_opening(pen, resolution="quarter")
    return pen.finish()


def _type7_bar2(pen: _Pen):
    sung = pen.mel(0)
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, _weak = pen.beds(written)
    low = pen.bass_of(sung)
    higher = pen.support_of(sung, low, capped=False)
    pen.add(0.0, sung, 1.5, 1, written, 0, accent=True)
    pen.add(0.0, higher, 0.5, 2, support_level, 0)
    pen.add(0.0, low, 0.5, 3, bass_level, 0)
    pen.add(0.5, low, 0.5, 3, bass_level, 1)
    pen.add(1.0, higher, 0.5, 2, support_level, 1)
    mordent_written = pen.lead_level(3, strong=False)[0]
    principal = pen.mel(4)
    neighbor = pen.grace(principal, [])
    if neighbor is None:
        pen.add(1.5, principal, 0.5, 1, mordent_written, 1)
    else:
        upper, body = neighbor
        pen.add(1.5, upper, 0.25, 1, mordent_written, 2, slur_start=True)
        pen.add(1.75, body, 0.25, 1, mordent_written, 1, slur_stop=True)
    held = pen.lead_level(4, strong=False)[0]
    if pen.ctx.kind == "4/4":
        pen.add(2.0, pen.mel(4), 1.5, 1, held, 1)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pen.add(2.5, low, 0.5, 3, bass_level, 1)
        pen.add(3.0, low, 0.5, 3, bass_level, 1)
        pickup = pen.lead_level(7, strong=False)[0]
        pen.add(3.5, pen.mel(7), 0.5, 1, pickup, 0, accent=True)
    else:
        pen.add(2.0, pen.mel(4), 0.5, 1, held, 1)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pickup = pen.lead_level(5, strong=False)[0]
        pen.add(2.5, pen.mel(5), 0.5, 1, pickup, 0, accent=True)
    return pen.finish()


def _type7_bar3(pen: _Pen):
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, _weak = pen.beds(written)
    low = pen.bass_of(pen.mel(0))
    pen.add(0.0, low, pen.beats, 3, bass_level, 0)
    pairs = pen.epb // 2
    for pair in range(pairs):
        even = pair * 2
        odd = even + 1
        sung = pen.mel(even)
        strong = even in pen.strong
        level, mark = pen.lead_level(even, strong=strong)
        steps = 0 if strong else 1
        inner = pen.support_of(sung, low, capped=not strong)
        grace_pair = pair % 2 == 0
        pen.add(even * 0.5, sung, 0.5, 1, level, steps, accent=mark and steps == 0)
        pen.add(even * 0.5, inner, 0.5, 2, support_level, steps)
        odd_pitch = pen.mel(odd)
        odd_written = pen.lead_level(odd, strong=False)[0]
        if grace_pair:
            others = [note for note in (low, inner) if note is not None]
            neighbor = pen.grace(sung, others)
            if neighbor is None:
                # The odd eighth keeps `p`, the even eighth's price.
                pen.add(odd * 0.5, sung, 0.5, 1, odd_written, 1)
            else:
                upper, body = neighbor
                # The upper neighbor ornaments `p`, the even eighth's price, then returns to it.
                pen.add(odd * 0.5, upper, 0.25, 1, odd_written, 1, slur_start=True)
                pen.add(odd * 0.5 + 0.25, body, 0.25, 1, odd_written, 1, slur_stop=True)
            pen.add(odd * 0.5, inner if inner is not None else pen.support_of(sung, low, capped=True), 0.5, 2, support_level, 1)
        else:
            odd_inner = pen.support_of(odd_pitch, low, capped=True)
            pen.add(odd * 0.5, odd_pitch, 0.5, 1, odd_written, 1)
            pen.add(odd * 0.5, odd_inner, 0.5, 2, support_level, 1)
    return pen.finish()


def _bass_answers(pen: _Pen, below: int) -> tuple[int | None, int | None]:
    chord = pen.ctx.chord(pen.bar)
    tones = [note for note in range(40, 53) if note % 12 in chord.pitch_classes and note < below]
    if len(tones) >= 2:
        return tones[-1], tones[0]
    if len(tones) == 1:
        return tones[0], tones[0]
    found = pen.bass_of(below)
    return found, found


def _type7_half(pen: _Pen, base: int, *, lead_steps: int, accent: bool) -> None:
    sung = pen.mel(base)
    written, _accent = pen.lead_level(base if lead_steps == 0 else 0, strong=True)
    if lead_steps:
        written = pen.lead_level(base, strong=False)[0]
    support_level, bass_level, _weak = pen.beds(pen.lead_level(0, strong=True)[0])
    high, deep = _bass_answers(pen, sung)
    floor = high if high is not None else deep
    inner = pen.support_of(sung, floor if floor is not None else sung - 5, capped=False)
    pen.add(base * 0.5, sung, 1.5, 1, written, lead_steps, accent=accent)
    pen.add(base * 0.5, inner, 1.5, 2, support_level, lead_steps)
    if high is not None:
        pen.add((base + 1) * 0.5, high, 0.5, 3, bass_level, 1)
    if deep is not None:
        pen.add((base + 2) * 0.5, deep, 0.5, 3, bass_level, 2)
    target = pen.mel(base + 3)
    neighbor = pen.grace(target, [])
    if neighbor is None:
        pen.add((base + 3) * 0.5, target, 0.5, 1, written, 1)
    else:
        upper, body = neighbor
        pen.add((base + 3) * 0.5, upper, 0.25, 1, written, 2, slur_start=True)
        pen.add((base + 3) * 0.5 + 0.25, body, 0.25, 1, written, 1, slur_stop=True)


def _type7_bar4(pen: _Pen):
    if pen.ctx.kind == "4/4":
        _type7_half(pen, 0, lead_steps=0, accent=True)
        _type7_half(pen, 4, lead_steps=1, accent=False)
        return pen.finish()
    _type7_half(pen, 0, lead_steps=0, accent=True)
    # The 3/4 and 6/8 bar keeps one cycle, then a quarter and an answering bass.
    sung = pen.mel(4)
    written = pen.lead_level(4, strong=False)[0]
    support_level, bass_level, _weak = pen.beds(pen.lead_level(0, strong=True)[0])
    high, deep = _bass_answers(pen, sung)
    floor = high if high is not None else deep
    inner = pen.support_of(sung, floor if floor is not None else sung - 5, capped=False)
    # Replace the grace the shared half wrote at eighth 3 only when this meter wants the quarter close.
    # `_type7_half` already wrote eighths 0–3, including the grace at 3. Eighths 4–5 follow.
    pen.add(2.0, sung, 1.0, 1, written, 1)
    pen.add(2.0, inner, 0.5, 2, support_level, 1)
    answer = deep if deep is not None else high
    pen.add(2.5, answer, 0.5, 3, bass_level, 2)
    return pen.finish()


def _root_in_bass(pen: _Pen) -> int:
    root = pen.ctx.chord(pen.bar).pitches[0] % 12
    tones = [note for note in range(40, 53) if note % 12 == root]
    if tones:
        return tones[0]
    found = pen.bass_of(None)
    return 48 if found is None else max(40, min(52, found))


def _scale_to_root(pen: _Pen, count: int, ceiling: int | None = None) -> list[int]:
    """Stepwise bass in 40–52, ending on the chord root.

    A degree the held lead cannot fret with is left out. The eighth rhythm
    stays one note per eighth. Open E2 still fits a high lead; F2 does not.
    """
    goal = _root_in_bass(pen)
    semi = pen.ctx.semitones

    def fits(pitch: int) -> bool:
        if ceiling is None:
            return True
        return _playable([pitch + semi, ceiling + semi])

    scale = [pitch for pitch in range(40, 53) if _on_scale(pitch, pen.ctx.mode) and fits(pitch)]
    if not scale:
        found = pen.bass_of(ceiling)
        fallback = 40 if found is None else max(40, min(52, found))
        return [fallback] * count
    if goal not in scale:
        root = goal % 12
        goal = min(scale, key=lambda pitch: (pitch % 12 != root, abs(pitch - goal), pitch))
    cursor = scale.index(goal)
    direction = -1 if cursor > 0 else 1
    path = [goal]
    while len(path) < count:
        nxt = cursor + direction
        if nxt < 0 or nxt >= len(scale):
            direction *= -1
            nxt = cursor + direction
            if nxt < 0 or nxt >= len(scale):
                path.append(scale[cursor])
                continue
        cursor = nxt
        path.append(scale[cursor])
    path.reverse()
    return path


def _type7_bar5(pen: _Pen):
    sung = pen.mel(0)
    written, _accent = pen.lead_level(0, strong=True)
    bass_level = pen.beds(written)[1]
    # Bass covers 2/12, so `_micro_fits` sees it. The lead step is 0 and stays 0.
    _open_rasgueado(
        pen, written, lead_release=pen.beats, max_notes=4, accent=True, bed_steps=1
    )
    if pen.ctx.kind == "4/4":
        steps = (1, 1, 1, 1, 2, 2, 1)
    else:
        steps = (1, 1, 2, 2, 1)
    line = _scale_to_root(pen, len(steps), sung)
    for offset, (step, midi) in enumerate(zip(steps, line), start=1):
        pen.add(offset * 0.5, midi, 0.5, 3, bass_level, step)
    return pen.finish()


def _render_type8(pen: _Pen):
    if pen.index == 0:
        return _type8_bar1(pen)
    return _type8_bar2(pen)


def _color_pair(pen: _Pen, lead: int) -> tuple[int | None, int | None]:
    """Two bass-register chord tones. A node, when the chord has one, is the eighth."""
    chord = pen.ctx.chord(pen.bar)
    semi = pen.ctx.semitones
    tones = [note for note in range(40, 53) if note % 12 in chord.pitch_classes and note < lead]
    if not tones:
        found = pen.bass_of(lead)
        return found, found
    nodes = [note for note in tones if (note + semi) in _HARMONICS]
    first = max(nodes) if nodes else max(tones)
    rest = [note for note in tones if note != first]
    second = max(rest) if rest else first
    return first, second


def _type8_bar1(pen: _Pen):
    sung = pen.mel(0)
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, _weak = pen.beds(written)
    first, second = _color_pair(pen, sung)
    floor = first if first is not None else second
    inner = pen.support_of(sung, floor if floor is not None else sung - 5, capped=False)
    if inner is not None and first is not None and not first < inner < sung:
        inner = pen.support_of(sung, first, capped=True)
    if inner is not None and second is not None and second >= inner:
        lower = [note for note in range(40, inner) if note % 12 in pen.ctx.chord(pen.bar).pitch_classes]
        if lower:
            second = max(lower)
    pen.add(0.0, sung, 1.5, 1, written, 0, accent=True)
    pen.add(0.0, inner, 1.5, 2, support_level, 0)
    # Shorter than two beats, and voice 3 stops at 53, so these stay at the bass bed.
    if first is not None:
        pen.add(0.5, first, 0.5, 3, bass_level, 1)
    if second is not None:
        pen.add(1.0, second, 1.0, 3, bass_level, 1)
    if pen.ctx.kind == "4/4":
        tail = ((3, 1, False), (4, 0, True), (5, 1, False), (6, 2, False), (7, 1, False))
    elif pen.ctx.kind == "6/8":
        tail = ((3, 0, True), (4, 1, False), (5, 1, False))
    else:
        tail = ((3, 1, False), (4, 1, False), (5, 1, False))
    for eighth, steps, accent in tail:
        level, mark = pen.lead_level(eighth, strong=accent)
        pen.add(eighth * 0.5, pen.mel(eighth), 0.5, 1, level, steps, accent=accent and mark)
    return pen.finish()


def _two_bar_close(pen: _Pen) -> bool:
    return bool(pen.phrase is not None and pen.phrase.closes) and len(_bars_of(pen.ctx, pen.phrase)) == 2


def _type8_bar2(pen: _Pen):
    written, _accent = pen.lead_level(0, strong=True)
    support_level, bass_level, _weak = pen.beds(written)
    weak_written = pen.lead_level(4 if pen.epb > 4 else 0, strong=False)[0]
    if pen.ctx.kind == "4/4":
        _type8_half(pen, 0, written, support_level, bass_level, lead_steps=0, accent=True)
        if _two_bar_close(pen):
            sung = pen.mel(4)
            low = pen.bass_of(sung)
            inner = pen.support_of(sung, low, capped=False)
            pen.add(2.0, sung, 2.0, 1, weak_written, 1)
            pen.add(2.0, inner, 1.5, 2, support_level, 1)
            pen.add(2.0, low, 2.0, 3, bass_level, 1)
            return pen.finish()
        _type8_half(pen, 4, weak_written, support_level, bass_level, lead_steps=1, accent=False)
        return pen.finish()
    sung = pen.mel(0)
    low = pen.bass_of(sung)
    covered = [pen.mel(eighth) for eighth in range(4)]
    inner = pen.support_of(min(covered), low, capped=True)
    pen.add(0.0, low, pen.beats, 3, bass_level, 0)
    pen.add(0.0, inner, 1.5, 2, support_level, 0)
    pen.add(0.0, sung, 0.5, 1, written, 0, accent=True)
    _type8_three(pen, 1, written, support_level)
    close = pen.mel(4)
    close_inner = pen.support_of(close, low, capped=True)
    pen.add(2.0, close, 1.0, 1, weak_written, 1)
    pen.add(2.0, close_inner, 0.5, 2, support_level, 1)
    return pen.finish()


def _type8_half(pen: _Pen, base: int, written: int, support_level: int, bass_level: int, *, lead_steps: int, accent: bool) -> None:
    sung = pen.mel(base)
    leads = [pen.mel(base + offset) for offset in range(4)]
    low = pen.bass_of(min(leads))
    inner = pen.support_of(min(leads), low, capped=True)
    pen.add(base * 0.5, low, 2.0, 3, bass_level, 0 if lead_steps == 0 else 1)
    pen.add(base * 0.5, inner, 1.5, 2, support_level, 0 if lead_steps == 0 else 1)
    pen.add(base * 0.5, sung, 0.5, 1, written, lead_steps, accent=accent)
    _type8_three(pen, base + 1, written, support_level)


def _type8_three(pen: _Pen, start: int, written: int, support_level: int) -> None:
    repeated = pen.mel(start)
    bundle = pen.group()
    goal = pen.mel(start + 2)
    pen.add(start * 0.5, repeated, 0.5, 1, written, 1, group=bundle)
    pen.add((start + 1) * 0.5, repeated, 0.5, 1, written, 1, slur_start=True, group=bundle)
    pen.add((start + 2) * 0.5, goal, 0.5, 1, written, 2, slur_stop=True)


_FIGURES = {
    1: _render_type1,
    2: _render_type2,
    3: _render_type3,
    4: _render_type4,
    5: _render_type5,
    6: _render_type6,
    7: _render_type7,
    8: _render_type8,
}


def render_torroba_figure(
    ctx,
    bar: int,
    phrase,
    pattern: str,
    figure: int,
    *,
    index: int = 0,
    count: int = 1,
    next_figure: int | None = None,
):
    """One bar of a Torroba figure. Micro steps are already on the attacks."""
    pen = _Pen(ctx, bar, phrase, pattern, index=index, count=count, next_figure=next_figure)
    return _FIGURES[figure](pen)


def apply_sonatina_downbeats(ctx, lead, support, patterns):
    """Leap, run, and step into a sonatina downbeat, written after frames.

    The sixteenth before offset 0 lives in the previous bar. `_resolve` then
    shortens a castillo or frame hold that would otherwise share the high voice.
    Castillo, fandanguillo, and danza do not grow a pickup.
    """
    from app.sonify.guitar_patterns import _bar_pattern

    epb = ctx.epb
    if 0 not in {offset for offset in ctx.strong if offset < epb}:
        return lead, support
    # Figure bars write their own slurs. A pickup is not planted on one, or into one.
    figure_bars = set(torroba_figure_plan(ctx, patterns))
    for bar in range(1, ctx.bars):
        if _bar_pattern(ctx, bar, patterns) != "sonatina":
            continue
        eighth = bar * epb
        previous = _previous_strong(ctx, eighth)
        if previous is None:
            continue
        if bar in figure_bars or previous // epb in figure_bars:
            continue
        # A castillo hold is not sonatina, so the sounding note can still grace
        # into this downbeat. The unsung close at eighth 4 is not consulted.
        if _bar_pattern(ctx, previous // epb, patterns) == "sonatina" and _sonatina_slur_blocked(
            ctx, previous, eighth
        ):
            continue
        target = _melody_at(ctx, eighth)
        # Castillo and a calm frame hold the downbeat price. Eighth 4's close
        # is not sounding, so the interval is the held note, not `_melody_at`.
        prev_index = _price_note(lead, previous, epb)
        if prev_index is not None:
            prev_pitch = lead[prev_index].midi
        else:
            prev_pitch = _melody_at(ctx, previous)
        gap = abs(target - prev_pitch)
        phrase = _phrase_at(ctx, eighth)
        at_apex = (
            phrase is not None
            and phrase.apex.start <= eighth < phrase.apex.end
        )
        run = gap > 2 and phrase is not None and phrase.rise >= MIN_RISE and at_apex
        leap = gap > 2 and not run
        if run or leap:
            approaches = _into_strong(ctx, target, eighth, phrase, run=run)
            if not approaches:
                continue
            arrival = _price_note(lead, eighth, epb)
            lead.extend(approaches)
            if arrival is not None:
                lead[arrival] = _slur_arrive(lead[arrival])
            start = min(_start16(event, epb) for event in approaches)
            end = max(_start16(event, epb) + 1 for event in approaches)
            support = _clear_support(support, start, end, epb)
            continue
        if 1 <= gap <= 2:
            arrival = _price_note(lead, eighth, epb)
            if prev_index is not None:
                lead[prev_index] = _slur_leave(lead[prev_index])
            if arrival is not None:
                lead[arrival] = _slur_arrive(lead[arrival])
    return lead, support


def _render_torroba_bar(ctx, bar: int, phrase, pattern: str):
    if pattern == "castillo":
        return _render_castillo_bar(ctx, bar, phrase)
    if pattern == "fandanguillo":
        return _render_fandanguillo_bar(ctx, bar, phrase)
    if pattern == "danza":
        return _render_danza_bar(ctx, bar, phrase)
    return _render_sonatina_bar(ctx, bar, phrase)


def torroba_scale_step(ctx, pitch: int, toward: int, *, low: int, high: int) -> int:
    """Diatonic step. The penultimate note into G may be Ab. Bb is not raised."""
    if toward == pitch:
        return pitch
    direction = 1 if toward > pitch else -1
    nxt = pitch + direction
    after = pitch + 2 * direction
    if ctx.mode == "minor" and low <= nxt <= high and nxt % 12 == 8 and after % 12 == 7:
        return nxt
    stepped = _walk(pitch, direction, ctx.mode, low, high)
    if pitch % 12 == 10 and stepped % 12 == 11:
        return pitch
    return stepped


def torroba_frame(ctx, bar: int) -> list[tuple]:
    """Calm and rally sing one price over an open bass. A dance mood strums once."""
    from app.sonify.guitar_frame import _frame_mood, _lead_hi, _lead_lo

    mood = _frame_mood(ctx, bar)
    edge = mood in {"volatile", "selloff"}
    origin_pitch = _melody_at(ctx, bar * ctx.epb)
    price = max(_lead_lo(ctx), min(_lead_hi(ctx), origin_pitch))
    beats = ctx.epb * 0.5
    if not edge:
        velocity = _harmonic_velocity(ctx, price, beats, 64)
        bass = _torroba_bass(ctx, ctx.chord(bar), bar, price)
        specs = [(0, ctx.epb, price, 1, velocity, {"accent": True})]
        if bass is not None:
            _inner, bass_vel = _bed(velocity, "mf")
            specs.insert(0, (0, ctx.epb, bass, 3, bass_vel, {}))
        return specs
    return _edge_frame(ctx, bar, price, mood)


def _edge_frame(ctx, bar: int, price: int, mood: str | None) -> list[tuple]:
    epb = ctx.epb
    velocity = 68
    bass = _torroba_bass(ctx, ctx.chord(bar), bar, price)
    inner_vel, bass_vel = _bed(velocity, "mf")
    specs = [(0, 1, price, 1, velocity, {"accent": True})]
    if bass is not None:
        specs.append((0, 1, bass, 3, bass_vel, {}))
        inner = _torroba_inner(ctx, ctx.chord(bar), price, bass, allow_high=True)
        if inner is not None:
            specs.append((0, 1, inner, 2, inner_vel, {}))
    if ctx.bpm <= 72 or (mood == "selloff" and ctx.kind == "6/8"):
        if epb > 1:
            specs.append((1, epb - 1, price, 1, 64, {}))
        return specs
    if mood == "selloff":
        for offset in ctx.strong:
            if 0 < offset < epb:
                sung = _melody_at(ctx, bar * epb + offset)
                specs.append((offset, 1, sung, 1, 64, {"accent": True}))
        return specs
    for offset in _fandanguillo_melody(ctx.kind):
        if 0 < offset < epb:
            sung = _melody_at(ctx, bar * epb + offset)
            strong = offset in ctx.strong
            specs.append((offset, 1, sung, 1, 68 if strong else 64, {"accent": True} if strong else {}))
    return specs


from app.sonify.guitar_patterns import (  # noqa: E402
    _INNER,
    _apex_eighths,
    _dur16,
    _eighth_event,
    _melody_at,
    _note_velocity,
    _on_scale,
    _playable,
    _spell16,
    _start16,
    _MICRO,
    _micro_fits,
    _position_ok,
    _under_lead,
    _walk,
    written,
)
