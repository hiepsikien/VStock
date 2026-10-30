"""Federico Moreno Torroba: castillo, sonatina, fandanguillo, and danza.

The Andalucian loop lives in the dialect. These patterns only read the placed
price. A leap into a strong beat is one sixteenth before that beat. A short
run into the apex is the same idea stretched to three approaches. Neither one
replaces the price note, and neither one is recorded as a scale passage.
"""

from __future__ import annotations

from dataclasses import replace

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
    if ctx.kind == "6/8" and ctx.bpm > 72:
        if primary in {"danza", "fandanguillo"}:
            return "castillo"
        return "sonatina"
    if primary == "castillo":
        return "sonatina"
    return "castillo"


def _breath(bar: int) -> bool:
    return bar % 4 == 3


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


def _thin(eighths: list[int], bar: int) -> list[int]:
    if not _breath(bar) or len(eighths) < 2:
        return eighths
    return eighths[::2]


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
    band = "p" if _breath(bar) else ctx.band(bar)
    _inner_vel, bass_vel = _bed(velocity, band)
    bass = _torroba_bass(ctx, ctx.chord(bar), bar, midi)
    low = []
    if bass is not None:
        low = written(origin, epb, bass, velocity=bass_vel)
        low = [replace(event, voice=3, accent=False) for event in low]
    support: list[NoteEvent] = []
    if velocity == 48:
        return lead, support, low
    offsets = {2, 6} if ctx.kind == "4/4" else {2, 5} if ctx.kind == "6/8" else {2, 4}
    kept = _thin(sorted(offset for offset in offsets if offset < epb), bar)
    prev = None
    for offset in kept:
        sung = _melody_at(ctx, origin + offset)
        inner = None if bass is None else _torroba_inner(
            ctx, ctx.chord(bar), midi, bass, allow_high=True, prev_lead=prev
        )
        prev = sung
        if inner is None:
            continue
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


def _render_sonatina_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    epb = ctx.epb
    origin = bar * epb
    strong = [offset for offset in ctx.strong if offset < epb]
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    blocked: set[int] = set()
    prev_midi = None
    prev_at: int | None = None
    for offset in strong:
        eighth = origin + offset
        midi = _melody_at(ctx, eighth)
        velocity, accent = _lead_velocity(ctx, eighth, phrase, dance=False)
        event = _attack(eighth, midi, epb, velocity, accent=accent)
        if prev_midi is not None and offset > 0:
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
                    event = replace(event, slur_stop=True)
                    blocked.add(offset - 1)
                    if run and offset >= 2:
                        blocked.add(offset - 2)
            elif gap <= 2 and prev_at is not None:
                lead[prev_at] = replace(lead[prev_at], slur_start=True)
                event = replace(event, slur_stop=True)
        prev_at = len(lead)
        lead.append(event)
        prev_midi = midi
    band = "p" if _breath(bar) else ctx.band(bar)
    chord = ctx.chord(bar)
    for offset in strong:
        eighth = origin + offset
        midi = _melody_at(ctx, eighth)
        velocity = next(event.velocity or 64 for event in lead if event.voice == 1 and abs(event.beat - offset * 0.5) < 1e-6 and event.duration_beats >= 0.5)
        _inner_vel, bass_vel = _bed(velocity, band)
        bass = _torroba_bass(ctx, chord, bar, midi)
        if bass is not None:
            low.append(_bass_event(eighth, bass, epb, bass_vel))
    inners = _thin(
        [offset for offset in range(epb) if offset not in set(ctx.strong) and offset not in blocked],
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
        support.append(_support_event(origin + offset, inner, epb, _bed(64, band)[0]))
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
    band = "p" if _breath(bar) else ctx.band(bar)
    inner_vel, bass_vel = _bed(velocity, band)
    bass = _torroba_bass(ctx, ctx.chord(bar), bar, midi)
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


def _render_fandanguillo_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    lead, support, low = _block(ctx, bar, 0, phrase, staccato=False)
    for offset in _fandanguillo_melody(ctx.kind):
        if offset < ctx.epb:
            lead.append(_answer(ctx, bar, offset, phrase))
    gaps = [
        offset
        for offset in range(ctx.epb)
        if offset != 0 and offset not in _fandanguillo_melody(ctx.kind)
    ]
    for offset in _thin(gaps, bar):
        inner = _gap_inner(ctx, ctx.chord(bar), bar)
        if inner is None:
            continue
        band = "p" if _breath(bar) else ctx.band(bar)
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
    for offset in _thin(gaps, bar):
        inner = _gap_inner(ctx, ctx.chord(bar), bar)
        if inner is None:
            continue
        band = "p" if _breath(bar) else ctx.band(bar)
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
    for bar in range(1, ctx.bars):
        if _bar_pattern(ctx, bar, patterns) != "sonatina":
            continue
        eighth = bar * epb
        previous = _previous_strong(ctx, eighth)
        if previous is None:
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
                lead[arrival] = replace(lead[arrival], slur_stop=True)
            start = min(_start16(event, epb) for event in approaches)
            end = max(_start16(event, epb) + 1 for event in approaches)
            support = _clear_support(support, start, end, epb)
            continue
        if gap <= 2:
            arrival = _price_note(lead, eighth, epb)
            if prev_index is not None:
                lead[prev_index] = replace(lead[prev_index], slur_start=True)
            if arrival is not None:
                lead[arrival] = replace(lead[arrival], slur_stop=True)
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
    _under_lead,
    _walk,
    written,
)
