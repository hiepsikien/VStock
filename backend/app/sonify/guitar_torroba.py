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
# Juglar, Alcaniz, and Olite. Kept out of `_TORROBA_PATTERNS` so an even `n`
# is not spelled as a Castillo figure.
_CASTILLOS_PATTERNS = frozenset({"torroba_tremolo", "alcaniz", "olite"})
_DEGREE_I = 0
_DEGREE_V = 7
JUGLAR_THIN = 9
ALCANIZ_OPENING = 10
ALCANIZ_SOFT = 11
OLITE_THIN = 12
_TRIPLET = 4.0 / 12.0


def _torroba_primary(ctx, mood: str | None, *, framed_macro: bool = False) -> str:
    """One Torroba pattern for this meter and mood.

    `framed_macro` is ignored. The same table names a phrase and a section.
    On 4/4, calm is Sonatina. Every other cell is unchanged. A meter outside
    these three uses the 4/4 row. A mood outside the row uses that row's calm cell.
    """
    del framed_macro
    table = {
        "4/4": {
            "calm": "sonatina",
            "rally": "olite",
            "selloff": "castillo",
            "volatile": "olite",
        },
        "3/4": {
            "calm": "castillo",
            "rally": "torroba_tremolo",
            "selloff": "castillo",
            "volatile": "danza",
        },
        "6/8": {
            "calm": "danza",
            "rally": "alcaniz",
            "volatile": "fandanguillo",
            "selloff": "fandanguillo",
        },
    }
    row = table.get(ctx.kind, table["4/4"])
    if mood in row:
        return row[mood]
    return row["calm"]


def _torroba_contrast(ctx, primary: str, mood: str | None = None) -> str:
    """The other pattern in the same meter.

    `mood` is the opening section. Castillo in 3/4 answers with Juglar only
    when that mood is calm, and with Danza only when it is selloff. A cell
    with no row returns `primary`.
    """
    if mood is None:
        mood = ctx.character
    kind = ctx.kind
    if primary == "castillo" and kind == "4/4":
        return "olite"
    if primary == "castillo" and kind == "3/4":
        if mood == "calm":
            return "torroba_tremolo"
        if mood == "selloff":
            return "danza"
        return primary
    if primary == "olite" and kind == "4/4":
        return "sonatina"
    if primary == "sonatina" and kind == "4/4":
        return "castillo"
    if primary == "torroba_tremolo" and kind == "3/4":
        return "danza"
    if primary == "danza" and kind == "3/4":
        return "torroba_tremolo"
    if primary == "danza" and kind == "6/8":
        return "alcaniz"
    if primary == "alcaniz" and kind == "6/8":
        return "danza"
    if primary == "fandanguillo" and kind == "6/8":
        return "danza"
    return primary


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
    owner = _phrase_covering(ctx, eighth, phrase)
    ordinary = _note_velocity(eighth, 1, apex, owner)
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


def _raised_bed(lead_vel: int, band: str) -> tuple[int, int, int]:
    """Lift Torroba's bass by 4, then keep lead > bass > support, floor 40.

    The weak bass stays 4 under the strong bass. A sung note written 64 stops
    the strong bass at 62. A lead of 72 still allows bass 64.
    """
    support, bass = _under_lead(lead_vel, band)
    bass += 4
    bass = min(bass, max(42, lead_vel - 2))
    support = min(support, bass - 2)
    support = max(40, support)
    if bass < support + 2:
        bass = min(max(42, lead_vel - 2), max(support + 2, 42))
    if bass >= lead_vel:
        bass = max(42, lead_vel - 2)
        support = max(40, min(support, bass - 2))
    weak = max(40, bass - 4)
    return support, bass, weak


def _bed(lead_vel: int, band: str) -> tuple[int, int]:
    support, bass, _weak = _raised_bed(lead_vel, band)
    return support, bass


def _events_during(events: list[NoteEvent], bar: int, eighth: int) -> list[int]:
    """Pitches already sounding anywhere inside this eighth."""
    beat = eighth * 0.5
    stop = beat + 0.5
    found: list[int] = []
    for event in events:
        if event.midi is None or event.bar != bar:
            continue
        end = event.beat + event.duration_beats
        if event.beat < stop - 1e-9 and end > beat + 1e-9:
            found.append(event.midi)
    return found


def _sounding_at(events: list[NoteEvent], bar: int, beat: float) -> list[int]:
    """Pitches whose attack is still ringing at `beat`. Sequential notes are not stacked."""
    found: list[int] = []
    for event in events:
        if event.midi is None or event.bar != bar:
            continue
        if event.beat <= beat + 1e-9 < event.beat + event.duration_beats:
            found.append(event.midi)
    return found


def _bass_length_eighths(ctx, raw: int, bar: int, start: int, events: list[NoteEvent], *, limit: int) -> int | None:
    """Longest legal bass (4, 2, or 1 eighth) that still frets with every attack in the window.

    ``None`` when even the shortest option breaks the hand. The rejected
    length is not written.
    """
    semi = ctx.semitones
    opened = _open_bass_tone(ctx, raw)
    options = (4, 2) if opened else (4, 2, 1)
    options = tuple(length for length in options if length <= limit)

    def fits(length: int) -> bool:
        if start + length > ctx.epb:
            return False
        window_start = start * 0.5
        window_end = (start + length) * 0.5
        instants = [(start + offset) * 0.5 for offset in range(length)]
        for event in events:
            if event.midi is None or event.bar != bar:
                continue
            if window_start - 1e-9 <= event.beat < window_end - 1e-9:
                instants.append(event.beat)
        for beat in instants:
            pitches = _sounding_at(events, bar, beat)
            if not pitches:
                continue
            if raw >= min(pitches):
                return False
            if not _playable([raw + semi, *(pitch + semi for pitch in pitches)]):
                return False
        return True

    for length in options:
        if fits(length):
            return length
    return None


def _chord_bass_at(ctx, bar: int, eighth: int, events: list[NoteEvent]) -> int | None:
    """A chord bass that frets with each attack already sounding on this eighth."""
    start = eighth * 0.5
    instants = [start]
    for event in events:
        if event.midi is None or event.bar != bar:
            continue
        if start - 1e-9 <= event.beat < start + 0.5 - 1e-9:
            instants.append(event.beat)
    moments = [_sounding_at(events, bar, beat) for beat in instants]
    ceilings = [min(pitches) for pitches in moments if pitches]
    ceiling = min(ceilings) if ceilings else None
    raw = _torroba_bass(ctx, ctx.chord(bar), bar, ceiling)
    low, high = _bass_window(ctx)
    semi = ctx.semitones
    pool: list[int] = []
    if raw is not None:
        pool.append(raw)
    pcs = ctx.chord(bar).pitch_classes
    for note in range(low, high + 1):
        if note % 12 in pcs and note not in pool:
            pool.append(note)
    for note in pool:
        legal = True
        for pitches in moments:
            if not pitches:
                continue
            if note >= min(pitches) or not _playable([note + semi, *(pitch + semi for pitch in pitches)]):
                legal = False
                break
        if legal:
            return note
    return None


def _half_bass_events(
    ctx,
    bar: int,
    start: int,
    raw: int | None,
    velocity: int,
    events: list[NoteEvent],
) -> list[NoteEvent]:
    """One bass attack for a half bar, shortened when the hand cannot hold it.

    A fretted bass that breaks at eighth 2 or 6 (or the eighth after) is cut
    back to 1.0 or 0.5, and a new chord bass is placed on that eighth. The two
    half-bar attacks are never tied to each other.
    """
    if raw is None or start >= ctx.epb:
        return []
    limit = min(4, ctx.epb - start)
    length = _bass_length_eighths(ctx, raw, bar, start, events, limit=limit)
    if length is None:
        return []
    origin = bar * ctx.epb
    notes = [_bass_event(origin + start, raw, ctx.epb, velocity, length=length)]
    retreat_at = start + 2
    if length < limit and retreat_at < ctx.epb and start % 4 == 0:
        fresh = _chord_bass_at(ctx, bar, retreat_at, events)
        if fresh is not None:
            rest_limit = min(2, ctx.epb - retreat_at)
            rest = _bass_length_eighths(ctx, fresh, bar, retreat_at, events, limit=rest_limit)
            if rest is not None:
                notes.append(_bass_event(origin + retreat_at, fresh, ctx.epb, velocity, length=rest))
    return [replace(note, tie_start=False, tie_stop=False, voice=3, accent=False) for note in notes]


def _scale_step_into(ctx, left: int, right: int) -> bool:
    if left == right or abs(left - right) > 2:
        return False
    return _on_scale(left, ctx.mode) and _on_scale(right, ctx.mode)


def _grid_mordent(ctx, bar: int, beat: float, principal: int, velocity: int, others: list[int]) -> list[NoteEvent]:
    """E–F–E in one eighth when the hand fits. Otherwise one eighth of `principal`.

    The slur stays open. The note on the next strong eighth closes it.
    """
    upper = _walk(principal, 1, ctx.mode, ctx.treble_floor, ctx.treble_top)
    semi = ctx.semitones
    sounding = [principal + semi, upper + semi, *(note + semi for note in others)]
    if upper != principal and abs(upper - principal) <= 2 and _position_ok(sounding):
        sixth = 1.0 / 6.0
        return [
            NoteEvent(bar=bar, beat=beat, midi=principal, duration_beats=sixth, voice=1, velocity=velocity, slur_start=True),
            NoteEvent(bar=bar, beat=beat + sixth, midi=upper, duration_beats=sixth, voice=1, velocity=velocity),
            NoteEvent(bar=bar, beat=beat + 2.0 * sixth, midi=principal, duration_beats=sixth, voice=1, velocity=velocity),
        ]
    return [
        NoteEvent(bar=bar, beat=beat, midi=principal, duration_beats=0.5, voice=1, velocity=velocity, slur_start=True),
    ]


def _render_castillo_sustain(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Whole-bar lead. 4/4 still attacks the bass twice, at eighth 0 and eighth 4."""
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
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []
    if velocity != 48:
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
    if ctx.kind == "4/4" and bass is not None:
        low.extend(_half_bass_events(ctx, bar, 0, bass, bass_vel, [*lead, *support]))
        low.extend(_half_bass_events(ctx, bar, 4, bass, bass_vel, [*lead, *support]))
    elif bass is not None:
        low = written(origin, 2, bass, velocity=bass_vel)
        low = [replace(event, voice=3, accent=False) for event in low]
    return lead, support, low


def _render_castillo_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    if ctx.bpm <= 72 or ctx.kind != "4/4":
        return _render_castillo_sustain(ctx, bar, phrase)
    epb = ctx.epb
    origin = bar * epb
    closing = _closing_offsets(ctx, bar)
    second_half = set(range(4, epb))
    closes_half = second_half <= closing
    lead: list[NoteEvent] = []
    # First half: dotted quarter, then an eighth or a mordent into eighth 4.
    midi0 = _melody_at(ctx, origin)
    level0, _accent = _lead_velocity(ctx, origin, phrase, dance=False)
    lead.extend(written(origin, 3, midi0, accent=True, velocity=level0))
    midi3 = _melody_at(ctx, origin + 3)
    midi4 = _melody_at(ctx, origin + 4)
    level3, _mark = _lead_velocity(ctx, origin + 3, phrase, dance=False)
    bass_pitch = _torroba_bass(ctx, ctx.chord(bar), bar, min(midi0, midi3, midi4))
    others = [bass_pitch] if bass_pitch is not None else []
    if _scale_step_into(ctx, midi3, midi4):
        lead.extend(_grid_mordent(ctx, bar, 1.5, midi3, level3, others))
    else:
        connector = written(origin + 3, 1, midi3, velocity=level3, slur_start=True)
        lead.extend(connector)
    level4, _mark = _lead_velocity(ctx, origin + 4, phrase, dance=False)
    if closes_half:
        half_velocity = _harmonic_velocity(ctx, midi4, 2.0, level4)
        arrival = written(origin + 4, 4, midi4, velocity=half_velocity, slur_stop=True)
        lead.extend(arrival)
    else:
        lead.extend(
            written(
                origin + 4,
                3,
                midi4,
                accent=True,
                velocity=level4,
                slur_stop=True,
            )
        )
        midi7 = _melody_at(ctx, origin + 7)
        level7, _mark = _lead_velocity(ctx, origin + 7, phrase, dance=False)
        lead.extend(written(origin + 7, 1, midi7, velocity=level7))
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    # A harmonic bell (the closing half note) does not take an inner voice under it.
    harmonic_half = closes_half and any(
        note.velocity == 48 and abs(note.beat - 2.0) < 1e-6 for note in lead
    )
    kept = _thin([2, 6], ctx, bar)
    prev = None
    for offset in kept:
        if offset >= 4 and harmonic_half:
            continue
        cover = midi0 if offset < 4 else midi4
        sung = _melody_at(ctx, origin + offset)
        inner = None if bass_pitch is None else _torroba_inner(
            ctx, ctx.chord(bar), cover, bass_pitch, allow_high=True, prev_lead=prev
        )
        prev = sung
        if inner is None:
            continue
        band = _attack_band(ctx, bar, offset, closing)
        support.append(_support_event(origin + offset, inner, epb, _bed(level0, band)[0]))
    if bass_pitch is not None:
        band0 = _bar_band(ctx, bar, closing)
        _inner, bass_vel = _bed(level0, band0)
        sounding = [*lead, *support]
        low.extend(_half_bass_events(ctx, bar, 0, bass_pitch, bass_vel, sounding))
        low.extend(_half_bass_events(ctx, bar, 4, bass_pitch, bass_vel, sounding))
    return lead, support, low


def _approaches(ctx, target: int, count: int, chord=None) -> list[int]:
    """Scale steps into `target`. Into G they step onto Ab, and Ab is last.

    The notes before Ab are walked from Ab, not from the step under G with
    the final slot overwritten. A three-note pickup into G4 is F–G–Ab.
    """
    low = ctx.treble_floor
    high = ctx.treble_top
    ab = torroba_ab_approach(ctx, target, chord)
    if count >= 1 and ab is not None and low <= ab <= high:
        if count == 1:
            return [ab]
        found: list[int] = []
        cursor = ab
        for _step in range(count - 1):
            nxt = torroba_scale_step(ctx, cursor, -1, low=low, high=high)
            if nxt == cursor or nxt == ab:
                break
            found.append(nxt)
            cursor = nxt
        found.reverse()
        return found + [ab]
    found = []
    cursor = target
    for _step in range(count):
        nxt = torroba_scale_step(ctx, cursor, -1, low=low, high=high)
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
    pitches = _approaches(ctx, target, count, ctx.chord(eighth // ctx.epb))
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


def _sonatina_approach(ctx, earlier: int, later: int, earlier_pitch: int, later_pitch: int) -> str | None:
    """How the line reaches `later`: a grace, a step slur, or nothing."""
    if later < 0 or _sonatina_slur_blocked(ctx, earlier, later):
        return None
    gap = abs(later_pitch - earlier_pitch)
    if gap == 0:
        return None
    phrase = _phrase_covering(ctx, later, None)
    at_apex = phrase is not None and phrase.runs and phrase.apex.start <= later < phrase.apex.end
    if gap > 2 and phrase is not None and phrase.rise >= MIN_RISE and at_apex:
        return "run"
    if gap > 2:
        return "leap"
    if 1 <= gap <= 2:
        return "step"
    return None


def _render_sonatina_moving(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Quarter on each strong eighth, then two slurred eighths, unless a grace already leads in."""
    epb = ctx.epb
    origin = bar * epb
    lead: list[NoteEvent] = []
    # 4/4 is two halves. 3/4 keeps a quarter on eighth 4, which ends the bar.
    groups = [(0, 4)]
    if 4 < epb:
        groups.append((4, epb))
    pending_stop = False
    for base, arrival in groups:
        if base >= epb:
            continue
        eighth = origin + base
        midi = _melody_at(ctx, eighth)
        local = _phrase_covering(ctx, eighth, phrase)
        velocity, accent = _lead_velocity(ctx, eighth, local, dance=False)
        if ctx.kind != "4/4":
            accent = base in ctx.strong
        length = min(2, epb - base)
        lead.extend(written(eighth, length, midi, accent=accent, velocity=velocity, slur_stop=pending_stop))
        pending_stop = False
        arrival_eighth = origin + arrival
        if arrival_eighth >= len(ctx.melody):
            target = midi
            kind = None
        else:
            target = _melody_at(ctx, arrival_eighth)
            kind = _sonatina_approach(ctx, eighth, arrival_eighth, midi, target)
        if kind in {"leap", "run"}:
            if arrival < epb:
                owner = _phrase_covering(ctx, arrival_eighth, phrase)
                approaches = _into_strong(ctx, target, arrival_eighth, owner, run=kind == "run")
                if approaches:
                    lead.extend(approaches)
                    pending_stop = True
            continue
        first = base + 2
        second = base + 3
        if second >= epb:
            continue
        left = _melody_at(ctx, origin + first)
        right = _melody_at(ctx, origin + second)
        left_level = _lead_velocity(ctx, origin + first, _phrase_covering(ctx, origin + first, phrase), dance=False)[0]
        right_level = _lead_velocity(ctx, origin + second, _phrase_covering(ctx, origin + second, phrase), dance=False)[0]
        # A step slurs into the next strong beat. A repeated pitch, a blocked
        # close, and a grace (handled above) do not.
        slur = kind == "step" and not (left == right == target)
        lead.extend(written(origin + first, 1, left, velocity=left_level, slur_start=slur))
        lead.extend(written(origin + second, 1, right, velocity=right_level))
        if arrival < epb and slur:
            pending_stop = True
    closing = _closing_offsets(ctx, bar)
    chord = ctx.chord(bar)
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    strong = [0, 4] if ctx.kind == "4/4" else [offset for offset in (0, 4) if offset < epb]
    for offset in strong:
        if ctx.kind != "4/4" and offset not in ctx.strong and offset != 0:
            continue
        eighth = origin + offset
        midi = _melody_at(ctx, eighth)
        velocity = next(
            (
                event.velocity or 64
                for event in lead
                if event.voice == 1 and abs(event.beat - offset * 0.5) < 1e-6 and event.duration_beats >= 0.5
            ),
            64,
        )
        band = _attack_band(ctx, bar, offset, closing)
        _inner_vel, bass_vel = _bed(velocity, band)
        bass = _torroba_bass(ctx, chord, bar, midi)
        if ctx.kind == "4/4":
            continue
        if bass is not None:
            low.append(_bass_event(eighth, bass, epb, bass_vel))
    inners = [offset for offset in (1, 5) if offset < epb]
    prev = None
    for offset in _thin(inners, ctx, bar):
        # The quarter on the strong eighth is still ringing through this
        # eighth. The price written on the weak eighth has not been played.
        cover_beat = offset * 0.5
        sounding = next(
            (
                event
                for event in lead
                if event.midi is not None
                and event.beat <= cover_beat + 1e-9 < event.beat + event.duration_beats
            ),
            None,
        )
        cover = sounding.midi if sounding is not None else _melody_at(ctx, origin + offset)
        level = sounding.velocity if sounding is not None and sounding.velocity is not None else 64
        bass = _torroba_bass(ctx, chord, bar, cover)
        if bass is None:
            continue
        inner = _torroba_inner(ctx, chord, cover, bass, allow_high=False, prev_lead=prev)
        prev = cover
        if inner is None:
            continue
        band = _attack_band(ctx, bar, offset, closing)
        support.append(_support_event(origin + offset, inner, epb, _bed(level, band)[0]))
    if ctx.kind == "4/4":
        sounding = [*lead, *support]
        for offset in (0, 4):
            midi = _melody_at(ctx, origin + offset)
            velocity = next(
                (
                    event.velocity or 64
                    for event in lead
                    if event.voice == 1 and abs(event.beat - offset * 0.5) < 1e-6 and (event.duration_beats or 0) >= 0.5
                ),
                64,
            )
            band = _attack_band(ctx, bar, offset, closing)
            _inner_vel, bass_vel = _bed(velocity, band)
            raw = _torroba_bass(ctx, chord, bar, midi)
            low.extend(_half_bass_events(ctx, bar, offset, raw, bass_vel, sounding))
    sixteenths = [event for event in lead if abs((event.duration_beats or 0) - 0.25) < 1e-6]
    if sixteenths:
        window_start = min(_start16(event, epb) for event in sixteenths)
        window_end = max(_start16(event, epb) + 1 for event in sixteenths)
        support = _clear_support(support, window_start, window_end, epb)
    lead.sort(key=lambda event: (event.bar, event.beat, event.duration_beats))
    return lead, support, low


def _render_sonatina_bar(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    if ctx.kind in {"4/4", "3/4"}:
        return _render_sonatina_moving(ctx, bar, phrase)
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
        local_phrase = _phrase_covering(ctx, eighth, phrase)
        velocity, accent = _lead_velocity(ctx, eighth, local_phrase, dance=False)
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
                local_phrase is not None
                and local_phrase.runs
                and local_phrase.apex.start <= eighth < local_phrase.apex.end
            )
            run = gap > 2 and local_phrase is not None and local_phrase.rise >= MIN_RISE and at_apex
            leap = gap > 2 and not run
            if run or leap:
                approaches = _into_strong(ctx, midi, eighth, local_phrase, run=run)
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
    owner = _phrase_covering(ctx, eighth, phrase)
    ordinary = _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), owner)
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
        owner = _phrase_covering(ctx, eighth, phrase)
        ordinary = _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), owner)
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


def _phrase_covering(ctx, eighth: int, fallback=None):
    found = _phrase_at(ctx, eighth)
    return found if found is not None else fallback


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


def _soft_level(attack: _Attack, lead_written: int) -> int:
    """Weak bed under a lead that asks for two micro steps.

    Bass uses the weak value of `_raised_bed` (62 → 58 when the lead is 64).
    Support sits four under that weak bass (56 → 54) so lead > bass > support
    still holds after the lead drops two steps.
    """
    for band in ("mf", "mp", "p", "f"):
        support, bass, weak = _raised_bed(lead_written, band)
        if attack.voice == 3 and attack.written in {bass, weak}:
            return weak
        if attack.voice == 2 and attack.written == support:
            return max(40, min(support - _MICRO, weak - 2 * _MICRO))
    if attack.voice == 3:
        return max(40, attack.written - 2 * _MICRO)
    return max(40, attack.written - _MICRO)


def _attacks_overlap(left: _Attack, right: _Attack) -> bool:
    return left.beat < right.beat + right.duration - 1e-9 and right.beat < left.beat + left.duration - 1e-9


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


def _castillo_spans(length: int, n: int) -> list[tuple[int, tuple[int, ...]]]:
    """Locked castillo rows. Each span restarts its own slot index at 0."""
    if length <= 1:
        return []
    if length in {2, 3}:
        return [(8, (0, 1))]
    if length == 4:
        if n % 2 == 0:
            return [(8, (0, 1))]
        return [(8, (1, 2))]
    if length == 5:
        if n % 2 == 0:
            return [(7, (0, 1, 2, 3, 4))]
        return [(8, (0, 1)), (8, (3, 4))]
    if length == 6:
        if n % 2 == 0:
            return [(7, (0, 1, 2, 3, 4))]
        return [(8, (0, 1)), (8, (3, 4))]
    if length == 7:
        return [(7, (0, 1, 2, 3, 4))]
    if n % 2 == 0:
        return [(7, (0, 1, 2, 3, 4))]
    # L >= 8, the other turn: 5 of 8 bars. Two type-8 pairs plus one type-1 bar.
    return [(8, (0, 1)), (8, (4, 5)), (1, (2,))]


def _sonatina_open_spans(length: int, n: int) -> list[tuple[int, tuple[int, ...]]]:
    """Open sonatina. `n % 3` turns the short rows; longer rows lock one pair."""
    if length <= 1:
        return []
    turn = n % 3
    if length == 2:
        return ([(4, (0, 1))], [(2, (0, 1))], [(1, (0,))])[turn]
    if length == 3:
        return ([(4, (0, 1))], [(2, (1, 2))], [(1, (0, 1))])[turn]
    if length == 4:
        return (
            [(4, (0, 1)), (1, (3,))],
            [(2, (1, 2)), (1, (3,))],
            [(1, (0,)), (4, (2, 3))],
        )[turn]
    if length == 5:
        if n % 2 == 0:
            return [(4, (0, 1)), (1, (3,))]
        return [(4, (0, 1)), (2, (3, 4))]
    if length == 6:
        if n % 2 == 0:
            return [(4, (0, 1)), (2, (3, 4))]
        return [(2, (0, 1)), (4, (3, 4))]
    # L == 7 and L >= 8. Five sung bars; the rest stay on the cantabile grid.
    return [(4, (0, 1)), (1, (3,)), (2, (5, 6))]


def _sonatina_close_spans(length: int, n: int) -> list[tuple[int, tuple[int, ...]]]:
    """A close of four bars or more always ends on a 3-bar type 3."""
    del n
    if length <= 0:
        return []
    if length <= 3:
        return [(3, tuple(range(length)))]
    tail = (length - 3, length - 2, length - 1)
    if length == 4 or length == 5:
        return [(3, tail)]
    if length == 6:
        # The 2-bar type-3 alternative is not used. One opening bar keeps 4/6.
        return [(1, (0,)), (3, tail)]
    if length == 7:
        return [(4, (0, 1)), (3, tail)]
    return [(4, (0, 1)), (3, tail)]


def _fandanguillo_spans(phrase, length: int, n: int, closes: bool) -> list[tuple[int, tuple[int, ...]]]:
    """Type 5 and type 2 never share a phrase. A rise of 1 is enough to enter."""
    if phrase.rise < 1:
        return []
    room = length - 1 if closes else length
    if n % 2 == 0:
        if room >= 4:
            return [(5, (0, 1, 2, 3))]
        return []
    if room < 2:
        return []
    start = max(0, length // 2 - 1)
    if start + 1 >= (length - 1 if closes else length):
        return []
    return [(2, (start, start + 1))]


def _danza_spans(ctx, length: int, closes: bool) -> list[tuple[int, tuple[int, ...]]]:
    # No 4/4 spelling. A closing phrase of exactly four bars stays on the grid.
    if ctx.kind not in {"3/4", "6/8"} or length < 4:
        return []
    if closes and length == 4:
        return []
    return [(6, (0, 1, 2, 3))]


def _phrase_spans(ctx, phrase, pattern: str, n: int) -> list[tuple[int, tuple[int, ...]]]:
    length = len(_bars_of(ctx, phrase))
    closes = bool(phrase.closes)
    if pattern == "sonatina" and closes:
        return _sonatina_close_spans(length, n)
    if pattern == "sonatina":
        return _sonatina_open_spans(length, n)
    if pattern == "fandanguillo":
        return _fandanguillo_spans(phrase, length, n, closes)
    if pattern == "danza":
        return _danza_spans(ctx, length, closes)
    return _castillo_spans(length, n)


def select_torroba_spans(
    ctx,
    phrase,
    pattern: str,
    *,
    n: int,
    previous: int | None,
) -> list[tuple[int, tuple[int, ...]]]:
    """One or two figure spans for a body phrase.

    Every body phrase enters, including a closing sonatina and an odd `n`.
    When the first figure matches the previous phrase, `n` advances by one
    and the next figure in that family is used.
    """
    if pattern not in _TORROBA_PATTERNS or phrase is None or phrase.end <= phrase.start:
        return []
    if len(_bars_of(ctx, phrase)) <= 0:
        return []
    spans = _phrase_spans(ctx, phrase, pattern, n)
    if spans and previous is not None and spans[0][0] == previous:
        rotated = _phrase_spans(ctx, phrase, pattern, n + 1)
        if rotated:
            spans = rotated
    return spans


def select_torroba_figure(
    ctx,
    phrase,
    pattern: str,
    *,
    n: int | None,
    k: int | None,
    previous: int | None,
) -> tuple[int | None, tuple[int, ...]]:
    """The first span, for callers that still ask for one figure.

    `k` is ignored. `n` is the phrase number inside the pattern. An empty
    span list returns `(None, ())`.
    """
    del k
    spans = select_torroba_spans(ctx, phrase, pattern, n=0 if n is None else n, previous=previous)
    if not spans:
        return None, ()
    return spans[0]


def torroba_figure_plan(ctx, patterns: list[str]) -> dict[int, tuple[int, int, int]]:
    """Absolute bar → `(figure, index within the figure, figure length)`.

    Each span restarts `index` at 0, so two type-8 pairs in one phrase both
    sing `_type8_bar1`. Bars that stay on the base grid are absent.
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
            n = counters.get(pattern, 0)
            counters[pattern] = n + 1
            spans = select_torroba_spans(ctx, phrase, pattern, n=n, previous=previous)
            if not spans:
                previous = None
                continue
            bars = _bars_of(ctx, phrase)
            for figure, slots in spans:
                for slot_index, local in enumerate(slots):
                    if 0 <= local < len(bars):
                        plan[bars[local]] = (figure, slot_index, len(slots))
            previous = spans[-1][0]
    plan.update(_castillos_figure_plan(ctx, patterns))
    return plan


def _realize(ctx, bar: int, attacks: list[_Attack]) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Bass and support take their steps. Lead steps go through `_micro_fits`.

    Repeated notes that share a group take the shortest step that still fits.
    """
    bar_beats = ctx.epb * 0.5
    heard: dict[int, int] = {}
    leads = [attack for attack in attacks if attack.voice == 1]
    for index, attack in enumerate(attacks):
        if attack.voice == 1:
            continue
        covered = [lead for lead in leads if _attacks_overlap(attack, lead)]
        # A bass that also covers a steps-0 pillar keeps the full bed.
        # A bed that covers only a soft lead (steps >= 2) uses the weak level,
        # so `_micro_fits` can drop that lead by 4.
        if covered and min(lead.steps for lead in covered) >= 2:
            heard[index] = _soft_level(attack, max(lead.written for lead in covered))
        else:
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
        return _phrase_covering(self.ctx, self.origin + eighth, self.phrase)

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
        return _raised_bed(lead_written, self.ctx.band(self.bar))

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
            support, bass, weak = _raised_bed(source, self.ctx.band(self.bar))
            if voice == 2 and written == support:
                role = 0
            elif voice == 3 and written == bass:
                role = 1
            elif voice == 3 and written == weak:
                role = 2
            else:
                continue
            return _raised_bed(source, band)[role]
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
        A rolled chord keeps every string of the fan. With no bass the middle
        strings land on the beat, and that beat is still the chord.
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
        # Only a fan spaces a voice inside the first eighth. A block chord
        # stacks every voice on the beat, so its inner note still breathes.
        rolled = any(0.0 < attack.beat < 0.25 for attack in self.attacks)
        return [
            note
            for note in support
            if self._eighth_at(note.beat) not in drop
            or 0.0 < note.beat < 0.25
            or (rolled and note.beat <= 1e-9)
        ]

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

    def mordent_triplet(self, beat: float, principal: int, others: list[int], written: int, steps: int) -> bool:
        """Three 1/6 notes, principal–upper–principal, slurred. Falls back to a grace or an eighth."""
        upper = _walk(principal, 1, self.ctx.mode, self.ctx.treble_floor, self.ctx.treble_top)
        semi = self.ctx.semitones
        sounding = [principal + semi, upper + semi, *(note + semi for note in others)]
        if upper != principal and abs(upper - principal) <= 2 and _position_ok(sounding):
            sixth = 1.0 / 6.0
            self.add(beat, principal, sixth, 1, written, steps, slur_start=True)
            self.add(beat + sixth, upper, sixth, 1, written, steps + 1)
            self.add(beat + 2.0 * sixth, principal, sixth, 1, written, steps, slur_stop=True)
            return True
        neighbor = self.grace(principal, others)
        if neighbor is None:
            self.add(beat, principal, 0.5, 1, written, 1)
            return False
        grace_upper, body = neighbor
        self.add(beat, grace_upper, 0.25, 1, written, 2, slur_start=True)
        self.add(beat + 0.25, body, 0.25, 1, written, 1, slur_stop=True)
        return False

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
    pen.mordent_triplet(1.5, principal, [], written, 2)
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
        # Slur the first pair of each half. 4/4 also slurs eighths 4 → 5.
        # Fandanguillo and danza staccato are not written here.
        slur_start = eighth == 0 or (pen.ctx.kind == "4/4" and eighth == 4)
        slur_stop = eighth == 1 or (pen.ctx.kind == "4/4" and eighth == 5)
        if last:
            slur_start = False
        pen.add(
            eighth * 0.5,
            midi,
            0.5,
            1,
            written,
            0 if last else 1,
            accent=last and (pen.epb - 1) in pen.strong,
            slur_start=slur_start,
            slur_stop=slur_stop,
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
    low = pen.bass_of(midi)
    fast = pen.ctx.bpm > 72 and pen.ctx.kind == "4/4" and velocity != 48
    if not fast:
        # A bell at 48 is not an accent: sonatina snap targets accented leads.
        pen.add(0.0, midi, duration, 1, velocity, 0, accent=velocity != 48)
        pen.add(0.0, low, 0.5, 3, bass_level, 1)
        return pen.finish()
    # Two halves. The eighth at 1.5 slurs into the closing half note.
    eighth_level = pen.lead_level(3, strong=False)[0]
    close_level = pen.lead_level(4, strong=4 in pen.strong)[0]
    pen.add(0.0, midi, 1.5, 1, ordinary, 0, accent=True)
    pen.add(1.5, midi, 0.5, 1, eighth_level, 1, slur_start=True)
    pen.add(2.0, midi, 2.0, 1, close_level, 0, slur_stop=True)
    pen.add(0.0, low, 1.0, 3, bass_level, 0)
    pen.add(2.0, low, 1.0, 3, bass_level, 0)
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
    # The mordent sits on eighth 3 and spills into the arrival at beat 2.0.
    ornament, _mark = pen.lead_level(3, strong=False)
    pen.mordent_triplet(1.5, pen.mel(3), [], ornament, 2)
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
        tail_support, tail_bass, tail_weak = pen.beds(level)
        # Weak bass is 4 under the strong bass, and this eighth's inner voice
        # takes one micro step. A sentence that opens at 60 already holds the
        # strong bass at 58, so 58 - 4 meets the stepped inner voice. Keep the
        # weak bass one step above that voice: lead can then take its own step.
        if weak:
            stepped_support = max(40, tail_support - _MICRO)
            tail_weak = max(tail_weak, min(tail_bass, stepped_support + _MICRO))
        inner_here = pen.support_of(sung, low or sung - 5, capped=False)
        pen.add(eighth * 0.5, sung, 0.5, 1, level, lead_steps, accent=mark and lead_steps == 0)
        if inner_here is not None:
            pen.add(eighth * 0.5, inner_here, 0.5, 2, tail_support, 1 if weak else 0)
        if low_here is not None:
            pen.add(eighth * 0.5, low_here, 0.5, 3, tail_weak if weak else tail_bass, 0)
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
    pen.mordent_triplet(1.5, pen.mel(3), [], mordent_written, 2)
    resolved = pen.lead_level(4, strong=False)[0]
    if resolution == "half":
        pen.add(2.0, pen.mel(4), 2.0, 1, resolved, 0)
        pen.add(2.0, higher, 0.5, 2, support_level, 0)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pen.add(2.5, low, 0.5, 3, bass_level, 2)
        pen.add(3.0, higher, 0.5, 2, support_level, 1)
    elif resolution == "dotted":
        # The fast 4/4 second half matches bar 2: dotted quarter plus a leading eighth.
        pen.add(2.0, pen.mel(4), 1.5, 1, resolved, 1)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pen.add(2.5, low, 0.5, 3, bass_level, 1)
        pen.add(3.0, low, 0.5, 3, bass_level, 1)
        pickup = pen.lead_level(7, strong=False)[0]
        pen.add(3.5, pen.mel(7), 0.5, 1, pickup, 0, accent=True)
    elif resolution == "quarter":
        pen.add(2.0, pen.mel(4), 1.0, 1, resolved, 0)
        pen.add(2.0, low, 0.5, 3, bass_level, 1)
        pen.add(2.5, higher, 0.5, 2, support_level, 1)


def _type7_bar1(pen: _Pen):
    if pen.ctx.kind == "4/4" and pen.ctx.bpm > 72:
        _type7_opening(pen, resolution="dotted")
    elif pen.ctx.kind == "4/4":
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
    pen.mordent_triplet(1.5, pen.mel(3), [], mordent_written, 2)
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
                _drop_unfinished_eighth_slur(lead, previous // epb)
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
            # The moving eighths already opened the slur. Do not also open one
            # on the strong quarter.
            if _eighth_slur_open(lead, previous // epb):
                if arrival is not None:
                    lead[arrival] = _slur_arrive(lead[arrival])
            else:
                if prev_index is not None:
                    lead[prev_index] = _slur_leave(lead[prev_index])
                if arrival is not None:
                    lead[arrival] = _slur_arrive(lead[arrival])
            continue
        _drop_unfinished_eighth_slur(lead, previous // epb)
    _drop_dangling_eighth_slurs(lead)
    return lead, support


def _drop_dangling_eighth_slurs(lead: list[NoteEvent]) -> None:
    """An eighth slur that never reaches the next downbeat is not a slur."""
    for index, event in enumerate(lead):
        if event.midi is None or not event.slur_start or event.beat + 1e-9 < 3.0:
            continue
        closed = any(
            note.midi is not None and note.bar == event.bar + 1 and abs(note.beat) < 1e-6 and note.slur_stop
            for note in lead
        )
        if not closed:
            lead[index] = replace(event, slur_start=False)


def _eighth_slur_open(lead: list[NoteEvent], bar: int) -> bool:
    """True when eighths 6–7 already started a slur toward the next downbeat."""
    return any(
        event.bar == bar and event.midi is not None and event.slur_start and event.beat + 1e-9 >= 3.0
        for event in lead
    )


def _drop_unfinished_eighth_slur(lead: list[NoteEvent], bar: int) -> None:
    for index, event in enumerate(lead):
        if event.bar == bar and event.slur_start and event.beat + 1e-9 >= 3.0:
            lead[index] = replace(event, slur_start=False)


def _pattern_row(patterns, count: int, pattern: str) -> list[str]:
    if patterns is None:
        return [pattern] * count
    row = list(patterns)
    if len(row) < count:
        row.extend(["pedal"] * (count - len(row)))
    return row


def _grid_state(ctx, patterns: list[str]) -> dict[int, str]:
    """Body phrase index → `thin`, `pushed`, or `full`.

    Juglar is always `full`. A flat phrase and a close still sing triplets;
    the last bar of the region is chosen later, in `_render_juglar_bar`.
    Alcaniz and Olite keep the older grid. A closing phrase is thin. A
    `rise < 3` phrase is thin unless the previous body phrase of this pattern
    was thin for the same reason: that phrase sings the base-grid notes with
    no accent and no floor. The flag clears after a push, a full phrase, a
    close, another pattern, or a new section.
    """
    sections: dict[object, list[int]] = {}
    order: list[object] = []
    for index, phrase in enumerate(ctx.phrases):
        if index >= len(patterns) or not _body_phrase(ctx, phrase):
            continue
        key = _section_key(ctx, phrase)
        if key not in sections:
            sections[key] = []
            order.append(key)
        sections[key].append(index)
    state: dict[int, str] = {}
    for key in order:
        previous_thin = False
        previous_pattern = None
        for index in sections[key]:
            pattern = patterns[index]
            phrase = ctx.phrases[index]
            if pattern not in _CASTILLOS_PATTERNS:
                previous_thin = False
                previous_pattern = pattern
                continue
            if pattern != previous_pattern:
                previous_thin = False
            previous_pattern = pattern
            if pattern == "torroba_tremolo":
                state[index] = "full"
                previous_thin = False
                continue
            if phrase.closes:
                state[index] = "thin"
                previous_thin = False
            elif phrase.rise < MIN_RISE:
                if previous_thin:
                    state[index] = "pushed"
                    previous_thin = False
                else:
                    state[index] = "thin"
                    previous_thin = True
            else:
                state[index] = "full"
                previous_thin = False
    return state


def _castillos_n(ctx, patterns: list[str], index: int) -> int:
    """How many earlier body phrases of this pattern sit in the same section."""
    phrase = ctx.phrases[index]
    pattern = patterns[index]
    key = _section_key(ctx, phrase)
    count = 0
    for earlier in range(index):
        if patterns[earlier] != pattern or not _body_phrase(ctx, ctx.phrases[earlier]):
            continue
        if _section_key(ctx, ctx.phrases[earlier]) != key:
            continue
        count += 1
    return count


def _phrase_index(ctx, phrase) -> int | None:
    if phrase is None:
        return None
    for index, item in enumerate(ctx.phrases):
        if item is phrase:
            return index
    return None


def _lone_mode(phrase) -> str:
    if phrase is not None and phrase.runs and not phrase.closes and phrase.rise >= MIN_RISE:
        return "full"
    return "thin"


def _castillos_bar_mode(ctx, bar: int, phrase, pattern: str, patterns) -> tuple[str, int, bool]:
    """Density of this bar, the pattern's phrase number, and the Alcaniz opening."""
    row = _pattern_row(patterns, len(ctx.phrases), pattern)
    index = _phrase_index(ctx, phrase)
    if index is None or index >= len(row) or row[index] != pattern:
        mode = _lone_mode(phrase)
        n = 0
    else:
        mode = _grid_state(ctx, row).get(index, "thin")
        n = _castillos_n(ctx, row, index)
    local = 0
    if phrase is not None:
        bars = _bars_of(ctx, phrase)
        if bar in bars:
            local = bars.index(bar)
    opening = (
        pattern == "alcaniz"
        and mode == "full"
        and n == 0
        and local < 2
        and ctx.kind == "6/8"
    )
    return mode, n, opening


def castillos_wave_row(ctx, bar: int, patterns, pattern: str) -> str:
    """Wave profile id for one body bar.

    Juglar stays on the sonatina row. Alcaniz dance, opening, and a pushed
    dance stay on the danza row; a soft bar uses Castillo. Olite's full grid
    uses the danza row; a thin or pushed bar uses Castillo.
    """
    if pattern not in _CASTILLOS_PATTERNS:
        return pattern
    mode, _n, _opening = _castillos_bar_mode(ctx, bar, _phrase_at(ctx, bar * ctx.epb), pattern, patterns)
    if pattern == "torroba_tremolo":
        return "torroba_tremolo"
    if pattern == "alcaniz":
        return "castillo" if mode == "thin" else "alcaniz"
    return "olite" if mode == "full" else "castillo"


def _castillos_figure_plan(ctx, patterns: list[str]) -> dict[int, tuple[int, int, int]]:
    row = _pattern_row(patterns, len(ctx.phrases), "pedal")
    state = _grid_state(ctx, row)
    plan: dict[int, tuple[int, int, int]] = {}
    for index, phrase in enumerate(ctx.phrases):
        if index >= len(row) or not _body_phrase(ctx, phrase):
            continue
        pattern = row[index]
        if pattern not in _CASTILLOS_PATTERNS:
            continue
        mode = state.get(index, "thin")
        n = _castillos_n(ctx, row, index)
        bars = _bars_of(ctx, phrase)
        slots: list[int] = []
        figure: int | None = None
        if pattern == "torroba_tremolo":
            slots = [
                local
                for local, bar_no in enumerate(bars)
                if _juglar_region_last(ctx, bar_no, row)
            ]
            figure = JUGLAR_THIN if slots else None
        elif pattern == "alcaniz" and mode == "thin":
            figure = ALCANIZ_SOFT
            slots = list(range(len(bars)))
        elif pattern == "alcaniz" and mode == "full" and n == 0:
            figure = ALCANIZ_OPENING
            slots = list(range(min(2, len(bars))))
        elif pattern == "olite" and mode == "thin":
            figure = OLITE_THIN
            slots = list(range(len(bars)))
        if figure is None:
            continue
        for slot_index, local in enumerate(slots):
            if 0 <= local < len(bars):
                plan[bars[local]] = (figure, slot_index, len(slots))
    return plan


def _heard(bar: int, beat: float, midi: int, duration: float, voice: int, velocity: int, **flags) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=voice,
        velocity=velocity,
        **flags,
    )


def _lead_vel(ctx, eighth: int, phrase) -> int:
    """Swell of the sentence that owns this eighth.

    The phrase of the downbeat is only the fallback. A sentence that opens
    mid-bar takes its own swell from that eighth on. Accent and the floor
    stay with the bar's grid.
    """
    owner = _phrase_covering(ctx, eighth, phrase)
    return _note_velocity(eighth, 1, _apex_eighths(ctx.phrases), owner)


def _one_under(velocity: int, band: str) -> int:
    """One `_under_lead` step under the attack. Pitch stays put."""
    support, _bass = _under_lead(velocity, band)
    if support < velocity:
        return support
    return max(40, velocity - _MICRO)


def _sounding_bass(ctx, bar: int, lead: int) -> int | None:
    bass = _torroba_bass(ctx, ctx.chord(bar), bar, lead)
    if bass is None or not _open_bass_tone(ctx, bass):
        return None
    return bass


def _downbeat_only(ctx, bar: int, phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """A meter this pattern does not spell. One lead, and an open bass when there is one."""
    eighth = bar * ctx.epb
    midi = _melody_at(ctx, eighth)
    velocity = _lead_vel(ctx, eighth, phrase)
    lead = [_heard(bar, 0.0, midi, 0.5, 1, velocity)]
    low: list[NoteEvent] = []
    bass = _sounding_bass(ctx, bar, midi)
    if bass is not None:
        _inner, bass_vel = _bed(velocity, ctx.band(bar))
        low.append(_heard(bar, 0.0, bass, 0.5, 3, bass_vel))
    return lead, [], low


def _juglar_region_last(ctx, bar: int, patterns) -> bool:
    """True when the next bar is no longer Juglar.

    `patterns` is omitted by a one-bar grid test. That bar follows `mode`
    instead of becoming the region's last bar.
    """
    if not patterns:
        return False
    nxt = bar + 1
    if nxt >= ctx.bars:
        return True
    if ctx.kind_at.get(nxt, "phrase") in _PEDAL_BARS:
        return True
    from app.sonify.guitar_patterns import _bar_pattern

    return _bar_pattern(ctx, nxt, patterns) != "torroba_tremolo"


def _render_juglar_bar(ctx, bar: int, phrase, mode: str, patterns=None):
    """Eighth-note triplets in 3/4. Only attack 1 of eighth 0 can carry an accent.

    The last bar of a Juglar region is one note per beat. Every earlier bar
    is triplets, including a closing phrase. The bass is one beat at eighth 0.
    """
    if ctx.kind != "3/4":
        return _downbeat_only(ctx, bar, phrase)
    lead: list[NoteEvent] = []
    low: list[NoteEvent] = []
    band = ctx.band(bar)
    quarter_notes = mode == "thin" or _juglar_region_last(ctx, bar, patterns)
    for quarter, eighth in enumerate((0, 2, 4)):
        origin = bar * ctx.epb + eighth
        midi = _melody_at(ctx, origin)
        velocity = _lead_vel(ctx, origin, phrase)
        beat = float(quarter)
        accent = mode == "full" and eighth == 0 and not quarter_notes
        if quarter_notes:
            lead.append(_heard(bar, beat, midi, 1.0, 1, velocity))
        else:
            dropped = _one_under(velocity, band)
            lead.append(_heard(bar, beat, midi, _TRIPLET, 1, velocity, accent=accent))
            lead.append(_heard(bar, beat + _TRIPLET, midi, _TRIPLET, 1, dropped))
            lead.append(_heard(bar, beat + 2 * _TRIPLET, midi, _TRIPLET, 1, dropped))
    sung = _melody_at(ctx, bar * ctx.epb)
    bass = _sounding_bass(ctx, bar, sung)
    if bass is not None:
        _inner, bass_vel = _bed(_lead_vel(ctx, bar * ctx.epb, phrase), band)
        low.append(_heard(bar, 0.0, bass, 1.0, 3, bass_vel))
    return lead, [], low


def _scale_away(ctx, pitch: int, direction: int) -> int:
    toward = pitch + direction * 12
    low = min(ctx.treble_floor, pitch, toward)
    high = max(ctx.treble_top, pitch, toward)
    signed = 1 if direction >= 0 else -1
    stepped = torroba_scale_step(ctx, pitch, signed, low=low, high=high)
    if stepped == pitch:
        chromatic = pitch + signed
        if pitch % 12 == 10 and chromatic % 12 == 11:
            return pitch
        return chromatic
    return stepped


def _two_into(ctx, start: int, target: int, chord=None) -> tuple[int, int]:
    """Two scale steps that arrive on `target`. Equal pitches pull off from above.

    The second pitch is the note immediately before `target`. It is Ab when
    that destination is G and the bar's chord allows the approach.
    """
    away = -1 if start < target else 1
    ab = torroba_ab_approach(ctx, target, chord)
    if ab is not None:
        # The first pitch steps onto Ab. It is not the scale step under G.
        second = ab
        first = _scale_away(ctx, ab, away)
        return first, second
    second = _scale_away(ctx, target, away)
    first = _scale_away(ctx, second, away)
    return first, second


def _alcaniz_dance(ctx, bar: int, phrase, *, accented: bool):
    lead: list[NoteEvent] = []
    low: list[NoteEvent] = []
    band = ctx.band(bar)
    for eighth in (0, 3):
        origin = bar * ctx.epb + eighth
        midi = _melody_at(ctx, origin)
        ordinary = _lead_vel(ctx, origin, phrase)
        velocity = max(ordinary, 68) if accented else ordinary
        lead.append(_heard(bar, eighth * 0.5, midi, 0.5, 1, velocity, accent=accented))
        answer = eighth + 1
        bass = _sounding_bass(ctx, bar, midi)
        if bass is not None:
            _inner, bass_vel = _bed(ordinary, band)
            low.append(_heard(bar, answer * 0.5, bass, 0.5, 3, bass_vel))
    return lead, [], low


def _alcaniz_soft(ctx, bar: int, phrase):
    lead: list[NoteEvent] = []
    for eighth in (0, 3):
        origin = bar * ctx.epb + eighth
        midi = _melody_at(ctx, origin)
        velocity = _lead_vel(ctx, origin, phrase)
        lead.append(_heard(bar, eighth * 0.5, midi, 1.5, 1, velocity))
    low: list[NoteEvent] = []
    sung = _melody_at(ctx, bar * ctx.epb)
    bass = _sounding_bass(ctx, bar, sung)
    if bass is not None:
        _inner, bass_vel = _bed(_lead_vel(ctx, bar * ctx.epb, phrase), ctx.band(bar))
        low.append(_heard(bar, 0.0, bass, 0.5, 3, bass_vel))
    return lead, [], low


def _scale_degree_below(lead: int, steps: int, mode: str) -> int | None:
    """`steps` diatonic degrees under `lead`. Two degrees is a third; five is a sixth."""
    if steps <= 0 or not _on_scale(lead, mode):
        return None
    note = lead
    for _step in range(steps):
        note -= 1
        skipped = 0
        while not _on_scale(note, mode):
            note -= 1
            skipped += 1
            if skipped > 6:
                return None
    return note


def _alcaniz_under_lead(ctx, chord: Chord, lead: int, bass: int | None) -> int | None:
    """A diatonic third or sixth under the lead, inside the inner register.

    A chord tone on that interval wins. Otherwise the scale tone. The third
    wins when both intervals are the same kind of tone and both fit.
    """
    semi = ctx.semitones
    floor = max(ctx.mid_low, 50 - semi)
    if bass is not None:
        floor = max(floor, bass + 1)
    ceiling = min(ctx.mid_high, 65 - semi, lead - 1)
    if ceiling < floor:
        return None
    pcs = chord.pitch_classes

    def candidate(steps: int) -> int | None:
        note = _scale_degree_below(lead, steps, ctx.mode)
        if note is None or not floor <= note <= ceiling or not note < lead:
            return None
        if bass is not None and note <= bass:
            return None
        if lead - note not in {3, 4, 8, 9}:
            return None
        sounding = [note + semi, lead + semi]
        if bass is not None:
            sounding.insert(0, bass + semi)
        if not _playable(sounding):
            return None
        return note

    third = candidate(2)
    sixth = candidate(5)
    chord_tones = [note for note in (third, sixth) if note is not None and note % 12 in pcs]
    if chord_tones:
        return max(chord_tones)
    scale_tones = [note for note in (third, sixth) if note is not None]
    return max(scale_tones) if scale_tones else None


def _alcaniz_opening(ctx, bar: int, phrase):
    origin = bar * ctx.epb
    top = _melody_at(ctx, origin)
    ordinary = _lead_vel(ctx, origin, phrase)
    velocity = max(ordinary, 68)
    band = ctx.band(bar)
    inner_vel, bass_vel = _bed(velocity, band)
    raw = _torroba_bass(ctx, ctx.chord(bar), bar, top)
    lead = [_heard(bar, 0.0, top, 0.5, 1, velocity, accent=True)]
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    if raw is not None and _open_bass_tone(ctx, raw):
        low.append(_heard(bar, 0.0, raw, 0.5, 3, bass_vel))
    if raw is not None:
        inner = _torroba_inner(ctx, ctx.chord(bar), top, raw, allow_high=True)
        if inner is not None:
            support.append(_heard(bar, 0.0, inner, 0.5, 2, inner_vel))
    target = _melody_at(ctx, origin + 3)
    first, second = _two_into(ctx, top, target, ctx.chord(bar))
    lead.append(_heard(bar, 0.5, first, 0.5, 1, _lead_vel(ctx, origin + 1, phrase), slur_start=True))
    lead.append(_heard(bar, 1.0, second, 0.5, 1, _lead_vel(ctx, origin + 2, phrase)))
    arrival = _lead_vel(ctx, origin + 3, phrase)
    lead.append(
        _heard(bar, 1.5, target, 0.5, 1, max(arrival, 68), accent=True, slur_stop=True)
    )
    for eighth in (4, 5):
        sung = _melody_at(ctx, origin + eighth)
        level = _lead_vel(ctx, origin + eighth, phrase)
        lead.append(_heard(bar, eighth * 0.5, sung, 0.5, 1, level))
        inner = _alcaniz_under_lead(ctx, ctx.chord(bar), sung, raw)
        if inner is not None:
            support.append(_heard(bar, eighth * 0.5, inner, 0.5, 2, _bed(level, band)[0]))
    return lead, support, low


def _render_alcaniz_bar(ctx, bar: int, phrase, mode: str, *, opening: bool):
    if ctx.kind != "6/8":
        return _downbeat_only(ctx, bar, phrase)
    if mode == "thin":
        return _alcaniz_soft(ctx, bar, phrase)
    if opening:
        return _alcaniz_opening(ctx, bar, phrase)
    return _alcaniz_dance(ctx, bar, phrase, accented=mode == "full")


def _melody_here(ctx, eighth: int) -> int | None:
    if 0 <= eighth < len(ctx.melody):
        return ctx.melody[eighth]
    return None


def _scale_steps(ctx, start: int, target: int, chord=None) -> list[int]:
    """Diatonic steps from `start` to `target`, excluding `start` and including `target`.

    The penultimate note is Ab when `target` is G and the destination chord allows it.
    """
    if start == target:
        return []
    notes: list[int] = []
    cursor = start
    low = min(start, target) - 2
    high = max(start, target) + 2
    for _guard in range(24):
        if cursor == target:
            break
        direction = 1 if target > cursor else -1
        nxt = torroba_scale_step(ctx, cursor, direction, low=low, high=high)
        if nxt == cursor:
            notes.append(target)
            break
        notes.append(nxt)
        cursor = nxt
    if notes and notes[-1] != target:
        notes.append(target)
    ab = torroba_ab_approach(ctx, target, chord)
    if len(notes) == 1 and ab is not None and low <= ab <= high:
        direction = -1 if start < target else 1
        step = torroba_scale_step(ctx, ab, direction, low=low, high=high)
        return [step, ab, target]
    return _with_ab_before(ctx, notes, target, chord, low=low, high=high)


def _fit_walk(steps: list[int]) -> list[int] | None:
    """Three eighths. A short walk repeats the last pitch.

    A longer walk still ends on the target, and the eighth before that target
    is the penultimate scale step. That is Ab when the gate put it there.
    """
    if not steps:
        return None
    if len(steps) > 3:
        # Ab sits a semitone above G. Sound the scale step that walks onto
        # that Ab, not the opening of a long walk that then leaps.
        if steps[-1] % 12 == 7 and steps[-2] % 12 == 8 and steps[-2] == steps[-1] + 1:
            return [steps[-3], steps[-2], steps[-1]]
        return [steps[0], steps[-2], steps[-1]]
    return steps + [steps[-1]] * (3 - len(steps))


def _olite_chord(ctx, bar: int, eighth: int, phrase, *, accented: bool):
    """Strong-beat eighth plus inner voice. Bass is placed once per half bar later."""
    origin = bar * ctx.epb + eighth
    midi = _melody_at(ctx, origin)
    ordinary = _lead_vel(ctx, origin, phrase)
    velocity = max(ordinary, 68) if accented else ordinary
    lead = [_heard(bar, eighth * 0.5, midi, 0.5, 1, velocity, accent=accented)]
    support: list[NoteEvent] = []
    raw = _torroba_bass(ctx, ctx.chord(bar), bar, midi)
    if raw is None:
        return lead, support, []
    inner_vel, _bass_vel = _bed(velocity, ctx.band(bar))
    inner = _torroba_inner(ctx, ctx.chord(bar), midi, raw, allow_high=True)
    if inner is not None:
        support.append(_heard(bar, eighth * 0.5, inner, 0.5, 2, inner_vel))
    return lead, support, []


def _olite_upper_fits(ctx, start: int, others: list[int]) -> int | None:
    """Upper neighbor of `start` when principal, upper, and `others` share one position."""
    upper = _walk(start, 1, ctx.mode, ctx.treble_floor, ctx.treble_top)
    if upper == start or abs(upper - start) > 2:
        return None
    semi = ctx.semitones
    sounding = [start + semi, upper + semi, *(note + semi for note in others)]
    if not _position_ok(sounding):
        return None
    return upper


def _olite_grace_pair(ctx, start: int, upper: int, others: list[int]) -> bool:
    """Two sixteenths, upper then start, when each fits with the sounding bass."""
    semi = ctx.semitones
    pair = [upper + semi, start + semi]
    if not _position_ok(pair):
        return False
    ordered = sorted({upper, start})
    if any(abs(left - right) > 4 for left, right in zip(ordered, ordered[1:])):
        return False
    others_s = [note + semi for note in others]
    return _playable([upper + semi, *others_s]) and _playable([start + semi, *others_s])


def _olite_group(ctx, bar: int, eighths: tuple[int, int, int], start: int, target: int | None, phrase, chord=None):
    if target is None:
        return []
    if start != target:
        fitted = _fit_walk(_scale_steps(ctx, start, target, chord))
        if not fitted:
            return []
        notes: list[NoteEvent] = []
        for index, (eighth, midi) in enumerate(zip(eighths, fitted)):
            velocity = _lead_vel(ctx, bar * ctx.epb + eighth, phrase)
            notes.append(
                _heard(
                    bar,
                    eighth * 0.5,
                    midi,
                    0.5,
                    1,
                    velocity,
                    slur_start=index == 0,
                    slur_stop=index == 1,
                )
            )
        return notes
    return _olite_neighbor(ctx, bar, eighths, start, phrase, chord)


def _olite_neighbor(ctx, bar: int, eighths: tuple[int, int, int], start: int, phrase, chord) -> list[NoteEvent]:
    """Three eighths around a repeated pitch: mordent, lower neighbor, return."""
    owner = chord if chord is not None else ctx.chord(bar)
    bass = _torroba_bass(ctx, owner, bar, start)
    others = [bass] if bass is not None else []
    beat = eighths[0] * 0.5
    velocity = _lead_vel(ctx, bar * ctx.epb + eighths[0], phrase)
    notes: list[NoteEvent] = []
    upper = _olite_upper_fits(ctx, start, others)
    if upper is not None:
        sixth = 1.0 / 6.0
        notes.extend(
            [
                _heard(bar, beat, start, sixth, 1, velocity, slur_start=True),
                _heard(bar, beat + sixth, upper, sixth, 1, velocity),
                _heard(bar, beat + 2.0 * sixth, start, sixth, 1, velocity, slur_stop=True),
            ]
        )
    elif upper is None and _walk(start, 1, ctx.mode, ctx.treble_floor, ctx.treble_top) != start:
        climbed = _walk(start, 1, ctx.mode, ctx.treble_floor, ctx.treble_top)
        if abs(climbed - start) <= 2 and _olite_grace_pair(ctx, start, climbed, others):
            notes.append(_heard(bar, beat, climbed, 0.25, 1, velocity, slur_start=True))
            notes.append(_heard(bar, beat + 0.25, start, 0.25, 1, velocity, slur_stop=True))
        else:
            neighbor = torroba_scale_step(ctx, start, -1, low=ctx.treble_floor, high=ctx.treble_top)
            notes.append(_heard(bar, beat, neighbor, 0.5, 1, velocity))
    else:
        neighbor = torroba_scale_step(ctx, start, -1, low=ctx.treble_floor, high=ctx.treble_top)
        notes.append(_heard(bar, beat, neighbor, 0.5, 1, velocity))
    lower = torroba_scale_step(ctx, start, -1, low=ctx.treble_floor, high=ctx.treble_top)
    for eighth, midi in (
        (eighths[1], lower),
        (eighths[2], start),
    ):
        level = _lead_vel(ctx, bar * ctx.epb + eighth, phrase)
        notes.append(_heard(bar, eighth * 0.5, midi, 0.5, 1, level))
    return notes


def _olite_half_bass(ctx, bar: int, phrase, events: list[NoteEvent], ceiling: int) -> list[NoteEvent]:
    """Bass at eighth 0 and eighth 4. Fretted 40–53 stay; open and fretted both reattack."""
    raw = _torroba_bass(ctx, ctx.chord(bar), bar, ceiling)
    if raw is None:
        return []
    _inner, bass_vel = _bed(_lead_vel(ctx, bar * ctx.epb, phrase), ctx.band(bar))
    low: list[NoteEvent] = []
    low.extend(_half_bass_events(ctx, bar, 0, raw, bass_vel, events))
    low.extend(_half_bass_events(ctx, bar, 4, raw, bass_vel, events))
    return low


def _olite_vivace(ctx, bar: int, phrase, *, accented: bool):
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    for eighth in (0, 4):
        part_lead, part_support, _part_low = _olite_chord(ctx, bar, eighth, phrase, accented=accented)
        lead.extend(part_lead)
        support.extend(part_support)
    origin = bar * ctx.epb
    start = _melody_at(ctx, origin)
    middle = _melody_at(ctx, origin + 4)
    lead.extend(_olite_group(ctx, bar, (1, 2, 3), start, middle, phrase, ctx.chord(bar)))
    next_bar = bar + 1
    next_chord = ctx.chord(next_bar) if next_bar < ctx.bars else ctx.chord(bar)
    lead.extend(_olite_group(ctx, bar, (5, 6, 7), middle, _melody_here(ctx, origin + ctx.epb), phrase, next_chord))
    low = _olite_half_bass(ctx, bar, phrase, [*lead, *support], min(start, middle))
    return lead, support, low


def _olite_thin(ctx, bar: int, phrase):
    """Dotted quarters joined by a leading eighth. A closing half bar is one half note."""
    epb = ctx.epb
    origin = bar * epb
    closing = _closing_offsets(ctx, bar)
    closes_half = set(range(4, epb)) <= closing
    lead: list[NoteEvent] = []
    midi0 = _melody_at(ctx, origin)
    level0 = _lead_vel(ctx, origin, phrase)
    lead.extend(written(origin, 3, midi0, velocity=level0))
    midi3 = _melody_at(ctx, origin + 3)
    level3 = _lead_vel(ctx, origin + 3, phrase)
    lead.extend(written(origin + 3, 1, midi3, velocity=level3, slur_start=True))
    midi4 = _melody_at(ctx, origin + 4)
    level4 = _lead_vel(ctx, origin + 4, phrase)
    if closes_half:
        lead.extend(written(origin + 4, 4, midi4, velocity=level4, slur_stop=True))
    else:
        lead.extend(written(origin + 4, 3, midi4, velocity=level4, slur_stop=True))
        midi7 = _melody_at(ctx, origin + 7)
        level7 = _lead_vel(ctx, origin + 7, phrase)
        lead.extend(written(origin + 7, 1, midi7, velocity=level7))
    ceiling = min(note.midi for note in lead if note.midi is not None)
    low = _olite_half_bass(ctx, bar, phrase, lead, ceiling)
    return lead, [], low


def _render_olite_bar(ctx, bar: int, phrase, mode: str):
    if ctx.kind != "4/4":
        return _downbeat_only(ctx, bar, phrase)
    if mode == "thin":
        return _olite_thin(ctx, bar, phrase)
    return _olite_vivace(ctx, bar, phrase, accented=mode == "full")


def _pen_juglar_thin(pen: _Pen):
    return _render_juglar_bar(pen.ctx, pen.bar, pen.phrase, "thin")


def _pen_alcaniz_opening(pen: _Pen):
    return _render_alcaniz_bar(pen.ctx, pen.bar, pen.phrase, "full", opening=True)


def _pen_alcaniz_soft(pen: _Pen):
    return _render_alcaniz_bar(pen.ctx, pen.bar, pen.phrase, "thin", opening=False)


def _pen_olite_thin(pen: _Pen):
    return _render_olite_bar(pen.ctx, pen.bar, pen.phrase, "thin")


_FIGURES[JUGLAR_THIN] = _pen_juglar_thin
_FIGURES[ALCANIZ_OPENING] = _pen_alcaniz_opening
_FIGURES[ALCANIZ_SOFT] = _pen_alcaniz_soft
_FIGURES[OLITE_THIN] = _pen_olite_thin


def _render_torroba_bar(ctx, bar: int, phrase, pattern: str, patterns=None):
    if pattern == "torroba_tremolo":
        mode, _n, _opening = _castillos_bar_mode(ctx, bar, phrase, pattern, patterns)
        return _render_juglar_bar(ctx, bar, phrase, mode, patterns)
    if pattern == "alcaniz":
        mode, _n, opening = _castillos_bar_mode(ctx, bar, phrase, pattern, patterns)
        return _render_alcaniz_bar(ctx, bar, phrase, mode, opening=opening)
    if pattern == "olite":
        mode, _n, _opening = _castillos_bar_mode(ctx, bar, phrase, pattern, patterns)
        return _render_olite_bar(ctx, bar, phrase, mode)
    if pattern == "castillo":
        return _render_castillo_bar(ctx, bar, phrase)
    if pattern == "fandanguillo":
        return _render_fandanguillo_bar(ctx, bar, phrase)
    if pattern == "danza":
        return _render_danza_bar(ctx, bar, phrase)
    return _render_sonatina_bar(ctx, bar, phrase)


_G_PCS = frozenset({2, 7, 11})
_G7_PCS = frozenset({2, 5, 7, 11})
_SUNG_ARCH = frozenset({"castillo", "sonatina", "torroba_tremolo"})


def _chord_allows_ab(chord) -> bool:
    """G or G7 allows the approach. No chord means the destination pitch decides."""
    if chord is None:
        return True
    name = getattr(chord, "name", None)
    if name is not None:
        return name in {"G", "G7"}
    if isinstance(chord, frozenset):
        return chord == _G_PCS or chord == _G7_PCS
    return False


def torroba_ab_approach(ctx, destination: int, chord=None) -> int | None:
    """Ab a semitone above `destination` when that note is G.

    A supplied chord must be G or G7. A chord on its own never inserts Ab,
    and a run that lands on D or B keeps its diatonic approach.
    """
    if getattr(ctx, "mode", None) != "minor" or destination % 12 != 7:
        return None
    if not _chord_allows_ab(chord):
        return None
    return destination + 1


def _step_onto(ctx, pitch: int, coming_from: int, *, low: int, high: int) -> int:
    """The scale note that steps onto `pitch` from the side `coming_from` is on."""
    direction = -1 if coming_from <= pitch else 1
    return torroba_scale_step(ctx, pitch, direction, low=low, high=high)


def rewrite_torroba_approach(ctx, notes: list[int], chord, *, low: int, high: int) -> list[int]:
    """Ab immediately before G, reached by a scale step.

    The first pitch stays put. A rewrite that would leap, or that would move
    that first pitch, is declined and the diatonic line stands.
    """
    if getattr(ctx, "ensemble", None) != "torroba" or len(notes) < 2:
        return list(notes)
    end = notes[-1]
    ab = torroba_ab_approach(ctx, end, chord)
    if ab is None or not low <= ab <= high:
        return list(notes)
    if notes[-2] == ab and (len(notes) < 3 or abs(notes[-3] - ab) <= 2):
        return list(notes)
    # Two pitches with the opening already beside Ab become opening–Ab–G.
    # Replacing the opening would delete the note that steps onto Ab.
    if len(notes) == 2 and abs(notes[0] - ab) <= 2 and notes[0] != ab:
        return [notes[0], ab, notes[-1]]
    updated = list(notes)
    updated[-2] = ab
    if len(updated) >= 3 and abs(notes[-3] - ab) > 2:
        updated[-3] = _step_onto(ctx, ab, notes[-3], low=low, high=high)
    if updated[0] != notes[0]:
        return list(notes)
    if any(not low <= note <= high for note in updated):
        return list(notes)
    if any(abs(right - left) > 2 for left, right in zip(updated, updated[1:])):
        return list(notes)
    return updated


def _with_ab_before(ctx, notes: list[int], target: int, chord, *, low: int, high: int) -> list[int]:
    """Ab before G. The note before that Ab is the scale step onto it."""
    ab = torroba_ab_approach(ctx, target, chord)
    if ab is None or not notes or notes[-1] != target or not low <= ab <= high:
        return notes
    if len(notes) >= 2 and notes[-2] == ab and (len(notes) < 3 or abs(notes[-3] - ab) <= 2):
        return notes
    if len(notes) == 1:
        return [ab, target]
    if len(notes) == 2:
        return [_step_onto(ctx, ab, notes[0], low=low, high=high), ab, target]
    updated = list(notes)
    updated[-2] = ab
    if abs(notes[-3] - ab) > 2:
        updated[-3] = _step_onto(ctx, ab, notes[-3], low=low, high=high)
    return updated


def torroba_scale_step(ctx, pitch: int, toward: int, *, low: int, high: int) -> int:
    """One diatonic step. `toward >= 0` climbs, as in `classic_scale_step`.

    Bb is not raised to B. Ab is not chosen here: the walkers that know the
    destination place it only on the note immediately before G.
    """
    direction = 1 if toward >= 0 else -1
    stepped = _walk(pitch, direction, ctx.mode, low, high)
    if pitch % 12 == 10 and stepped % 12 == 11:
        return pitch
    return stepped


def _sung_attack(pattern: str, event: NoteEvent) -> bool:
    """The note that sings. Sixteenth pickups and a harmonic bell stay put."""
    if event.midi is None or event.velocity is None or event.velocity == 48:
        return False
    if pattern == "torroba_tremolo":
        return abs(event.beat - round(event.beat)) < 1e-6
    return event.duration_beats + 1e-9 >= 0.5


def _arch_curve(onsets: list[float], apex: float) -> list[int]:
    """Rise toward the note in front of the apex. The arrival releases.

    Two sung notes span 6. A longer phrase spans 8. Both sit inside 6–8.
    """
    count = len(onsets)
    span = 8 if count >= 3 else 6
    amounts = [0] * count
    if count == 0 or onsets[-1] == onsets[0]:
        if count:
            amounts[0] = span
        return amounts
    arrival = next((index for index, onset in enumerate(onsets) if onset + 1e-9 >= apex), count - 1)
    if arrival == 0:
        width = onsets[-1] - onsets[0]
        for index, onset in enumerate(onsets):
            amounts[index] = int(round(span * (1.0 - (onset - onsets[0]) / width)))
        amounts[0] = span
        amounts[-1] = 0
        return amounts
    peak = arrival - 1
    rise = onsets[peak] - onsets[0]
    for index in range(peak + 1):
        if rise <= 1e-9:
            amounts[index] = span
        else:
            amounts[index] = int(round(span * (onsets[index] - onsets[0]) / rise))
    amounts[peak] = span
    release = max(0, span - 5)
    tail = onsets[-1] - onsets[arrival]
    for index in range(arrival, count):
        if tail <= 1e-9:
            amounts[index] = release
        else:
            amounts[index] = int(round(release * (1.0 - (onsets[index] - onsets[arrival]) / tail)))
    amounts[arrival] = release
    return amounts


def _tenuto_gaps(amounts: list[int], bars: list[int]) -> None:
    """The crest of each bar sits 4–6 above the other sung notes in that bar."""
    grouped: dict[int, list[int]] = {}
    for index, bar in enumerate(bars):
        grouped.setdefault(bar, []).append(index)
    for indexes in grouped.values():
        if len(indexes) < 2:
            continue
        crest = max(indexes, key=lambda index: (amounts[index], -index))
        quiet = min(amounts[index] for index in indexes if index != crest)
        gap = amounts[crest] - quiet
        if gap > 6:
            amounts[crest] = quiet + 6
        elif gap < 4:
            amounts[crest] = quiet + 5


def _clamp_arch(amounts: list[int]) -> None:
    if not amounts:
        return
    low = min(amounts)
    if low < 0:
        for index in range(len(amounts)):
            amounts[index] -= low
    high = max(amounts)
    low = min(amounts)
    width = high - low
    if width > 8 and width > 0:
        for index, amount in enumerate(amounts):
            amounts[index] = low + int(round((amount - low) * 8 / width))
        peak = max(range(len(amounts)), key=lambda index: amounts[index])
        amounts[peak] = min(amounts) + 8
    elif width < 6:
        peak = max(range(len(amounts)), key=lambda index: amounts[index])
        amounts[peak] += 6 - width


def apply_torroba_sung_arch(ctx, lead, patterns):
    """Phrase arch on the sung Torroba lead, written before the volume wave.

    Dance patterns keep the strong-beat floor. Bass and support are not passed
    through here, so they do not take the same addition. The written result
    stays at or under 72 when the ordinary note is 64.
    """
    if getattr(ctx, "ensemble", None) != "torroba":
        return list(lead)
    from app.sonify.guitar_patterns import _bar_pattern

    events = list(lead)
    for phrase in getattr(ctx, "phrases", ()) or ():
        chosen: list[tuple[float, int, int]] = []
        for index, event in enumerate(events):
            onset = event.bar * ctx.epb + float(event.beat) * 2.0
            if not phrase.start <= onset < phrase.end:
                continue
            pattern = _bar_pattern(ctx, event.bar, patterns)
            if pattern not in _SUNG_ARCH or not _sung_attack(pattern, event):
                continue
            chosen.append((onset, event.bar, index))
        if len(chosen) < 2:
            continue
        chosen.sort()
        onsets = [item[0] for item in chosen]
        bars = [item[1] for item in chosen]
        amounts = _arch_curve(onsets, float(phrase.apex.start))
        _tenuto_gaps(amounts, bars)
        _clamp_arch(amounts)
        for (_onset, _bar, index), amount in zip(chosen, amounts):
            event = events[index]
            room = 72 - int(event.velocity or 0)
            applied = min(amount, room) if room > 0 else 0
            if applied > 0:
                events[index] = replace(event, velocity=int(event.velocity) + applied)
    return events


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
