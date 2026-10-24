"""Phase 3 guitar patterns, phrase overlays, and the playability check.

`assert_playable` only reports. The renderer repairs voicings before they
are written, and the tremolo grid itself stays in `guitar._tremolo`.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, replace

from app.sonify.chords import C, Chord
from app.sonify.form import active_meter
from app.sonify.guitar import (
    BARRIOS_TREMOLO_MIN_BPM,
    _BASS,
    _INNER,
    _MELODY,
    _MELODY_APEX,
    _PEDAL,
    _apex_eighths,
    _clamp,
    _compress_monotone,
    _fit,
    _hit,
    _melody_scale,
    _overflow,
    _pool,
    _slur,
    _span_velocity,
    _tremolo,
    _tresillo_bars,
)
from app.sonify.keys import C_KEY, KeySpec
from app.sonify.model import NoteEvent, Phrase, Score
from app.sonify.phrasing import MIN_RISE, bell_budget, quantize_strong_beats, swell, written
from app.sonify.quantize import C_MAJOR_PCS, C_NATURAL_MINOR_PCS

# Sounding open strings, string 6 → 1, and the highest fret each string allows.
_OPENS = (40, 45, 50, 55, 59, 64)
_MAX_FRET = (12, 12, 12, 17, 19, 19)
_LEGAL_16 = (24, 16, 12, 8, 6, 4, 3, 2, 1)
_CHORALE = frozenset({"andante", "chord_melody", "elegiaque", "cantabile"})
_DANCE = frozenset({"choro", "polca", "hemiola", "vals"})
_ARPEGGIO = frozenset({"study", "villa_pattern", "preludio"})
_FAMILY = {
    "study": "arpeggio",
    "villa_pattern": "arpeggio",
    "preludio": "arpeggio",
    "pedal": "pedal",
    "andante": "chorale",
    "chord_melody": "chorale",
    "elegiaque": "chorale",
    "cantabile": "chorale",
    "thumb_cantabile": "chorale",
    "tremolo": "tremolo",
    "choro": "dance",
    "polca": "dance",
    "hemiola": "dance",
    "vals": "dance",
}
_PROFILE = {
    "study": "study",
    "pedal": "study",
    "elegiaque": "elegiaque",
    "cantabile": "cantabile",
    "villa_pattern": "villa_pattern",
    "chord_melody": "villa_chord",
    "thumb_cantabile": "thumb_cantabile",
    "preludio": "barrios_preludio",
    "tremolo": "barrios_tremolo",
    "andante": "barrios_chorale",
    "choro": "barrios_dance",
    "polca": "barrios_dance",
    "hemiola": "barrios_dance",
    "vals": "barrios_dance",
}


class Unplayable(ValueError):
    """A guitar score breaks a register, string, or profile rule."""


@dataclass
class _Ctx:
    melody: list[int]
    raw: list[int]
    chord_at: dict[int, Chord]
    kind_at: dict[int, str]
    band_at: dict[int, str]
    phrases: tuple[Phrase, ...]
    bars: int
    bpm: int
    ensemble: str
    mode: str
    character: str | None
    character_at: tuple | list | None
    sections: tuple
    rel_span: float
    semitones: int
    bass_low: int
    bass_high: int
    mid_low: int
    mid_high: int
    treble_floor: int
    treble_top: int
    ceiling: int
    epb: int
    kind: str
    strong: tuple[int, ...]
    bar_beats: float
    elegy_prev: dict = field(default_factory=dict)

    def chord(self, bar: int) -> Chord:
        if bar in self.chord_at:
            return self.chord_at[bar]
        earlier = [key for key in self.chord_at if key <= bar]
        return self.chord_at[max(earlier)] if earlier else C

    def band(self, bar: int) -> str:
        return self.band_at.get(bar, "mf")

    def mood(self, bar: int) -> str | None:
        if self.character_at is not None and bar < len(self.character_at):
            marked = self.character_at[bar]
            if marked is not None:
                return marked
        return self.character

    def section(self, bar: int):
        for section in self.sections:
            if section.start <= bar < section.end:
                return section
        return None


def _classes(mode: str) -> tuple[int, ...]:
    return tuple(sorted(C_NATURAL_MINOR_PCS if mode == "minor" else C_MAJOR_PCS))


def _degree(note: int, mode: str) -> int:
    return _classes(mode).index(note % 12)


def _on_scale(note: int, mode: str) -> bool:
    return note % 12 in _classes(mode)


def _nearest(note: int, mode: str, low: int, high: int) -> int:
    scale = [pitch for pitch in range(low, high + 1) if _on_scale(pitch, mode)]
    if not scale:
        return max(low, min(high, note))
    return min(scale, key=lambda pitch: (abs(pitch - note), pitch))


def _walk(note: int, steps: int, mode: str, low: int, high: int) -> int:
    scale = [pitch for pitch in range(low, high + 1) if _on_scale(pitch, mode)]
    if not scale:
        return max(low, min(high, note))
    anchor = min(scale, key=lambda pitch: (abs(pitch - note), pitch))
    index = max(0, min(len(scale) - 1, scale.index(anchor) + steps))
    return scale[index]


def _meter_kind(meter) -> str:
    if meter.eighths_per_bar == 8:
        return "4/4"
    if meter.eighths_per_bar == 6 and meter.beat_type == 8:
        return "6/8"
    if meter.eighths_per_bar == 6:
        return "3/4"
    return "other"


def _start16(event: NoteEvent, epb: int) -> int:
    return event.bar * epb * 2 + int(math.floor(event.beat * 4 + 1e-9))


def _dur16(event: NoteEvent) -> int:
    return max(1, int(math.floor(event.duration_beats * 4 + 1e-9)))


def _spell16(
    start: int,
    length: int,
    midi: int | None,
    epb: int,
    voice: int,
    velocity: int | None = None,
    accent: bool = False,
    tie_in: bool = False,
    tie_out: bool = False,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    cursor = start
    left = length
    first = start
    while left > 0:
        bar_len = epb * 2
        room = bar_len - (cursor % bar_len)
        take = max(size for size in _LEGAL_16 if size <= left and size <= room)
        bar = cursor // bar_len
        beat = (cursor % bar_len) / 4.0
        events.append(
            NoteEvent(
                bar=bar,
                beat=beat,
                midi=midi,
                duration_beats=take / 4.0,
                voice=voice,
                velocity=None if midi is None else velocity,
                accent=accent and cursor == first,
                tie_start=midi is not None and (left > take or (left <= take and tie_out)),
                tie_stop=midi is not None and (cursor != first or (cursor == first and tie_in)),
            )
        )
        cursor += take
        left -= take
    return events


def _eighth_event(eighth: int, length: int, midi: int | None, epb: int, voice: int, velocity: int, accent: bool = False) -> list[NoteEvent]:
    if length <= 0 or midi is None:
        return []
    return _spell16(eighth * 2, length * 2, midi, epb, voice, velocity, accent)


def _string_options(sounding: int) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for index, open_pitch in enumerate(_OPENS):
        fret = sounding - open_pitch
        if 0 <= fret <= _MAX_FRET[index]:
            found.append((index, fret))
    return found


def _playable(sounding: list[int]) -> bool:
    if not sounding:
        return True
    options = []
    for pitch in sounding:
        choices = _string_options(pitch)
        if not choices:
            return False
        options.append(choices)
    for combo in itertools.product(*options):
        strings = [string for string, _fret in combo]
        if len(set(strings)) != len(strings):
            continue
        frets = [fret for _string, fret in combo if fret > 0]
        if frets and max(frets) - min(frets) > 5:
            continue
        return True
    return False


def _position_ok(sounding: list[int]) -> bool:
    """One hand position: some string choice keeps fretted notes inside five frets."""
    if len(sounding) <= 1:
        return all(_string_options(pitch) for pitch in sounding)
    return _playable(sounding)


def _uses_color(chord: Chord) -> bool:
    return chord.kind_text in {"sus2", "sus4", "add9", "madd9", "7sus4"} or chord.quality_group == "suspended"


def _ordered_pool(chord: Chord, color: bool) -> list[int]:
    """Trimmed chord tones. A four-note chord keeps the 3rd and the 7th/F♯.

    `Ab+6` loses E♭ (`pitches[2]`) inside `_pool` and stays A♭–C–F♯. F♯ is
    `pitches[3]`, the same slot as a seventh, and stays a legal inner tone.
    """
    pool = _pool(chord)
    third = chord.pitches[1] % 12 if len(chord.pitches) > 1 else None
    kept = chord.pitches[3] % 12 if len(chord.pitches) >= 4 else None
    ordered: list[int] = []
    for pc in (third, kept, *pool):
        if pc is not None and pc in pool and pc not in ordered:
            ordered.append(pc)
    if not color or not _uses_color(chord):
        return ordered or pool
    root = chord.pitches[0] % 12
    steps = {"sus2": (2,), "add9": (2,), "madd9": (2,), "sus4": (5,), "7sus4": (5, 10)}.get(chord.kind_text, ())
    front = [pc for pc in (((root + step) % 12) for step in steps) if pc in pool]
    return front + [pc for pc in ordered if pc not in front]


def _stored_bass(chord: Chord, degree: int, low: int, high: int) -> int:
    """Fold the stored chord pitch into the written bass window, highest octave first."""
    index = min(degree, len(chord.pitches) - 1)
    return _clamp(chord.pitches[index], low, high)


def _choose_bass(chord: Chord, degree: int, lead: int | None, low: int, high: int, semitones: int) -> int:
    note = _stored_bass(chord, degree, low, high)
    if lead is not None and note >= lead and note - 12 >= low:
        note -= 12
    return note


def _choose_inner(
    chord: Chord,
    lead: int,
    bass: int,
    low: int,
    high: int,
    semitones: int,
    color: bool,
    index: int = 0,
) -> int | None:
    pool = _ordered_pool(chord, color)
    if not pool:
        return None
    found: list[int] = []
    for shift, pc in enumerate(pool):
        if shift < index:
            continue
        for note in range(low, high + 1):
            if note % 12 == pc and bass < note < lead:
                found.append(note)
        if found and shift == index:
            break
    if not found:
        for pc in pool:
            for note in range(low, high + 1):
                if note % 12 == pc and bass < note < lead:
                    found.append(note)
    playable = [
        note
        for note in found
        if _playable([bass + semitones, note + semitones, lead + semitones])
    ]
    choices = playable or found
    if not choices:
        return None
    # Prefer the pool order, then the pitch closest under the melody.
    return max(choices)


# Liquidity shapes the bed. A rising phrase still sings 60 → 68 → 72 → 62
# on the melody, and these beds stay under that line (lead > bass > inner).
_BAND_SUPPORT = {"p": 50, "mp": 54, "mf": _INNER, "f": 60}
_BAND_BASS = {"p": 54, "mp": 58, "mf": _BASS, "f": 64}
_SWELL_OPEN = 60
_SWELL_MID = 68
_SWELL_CLOSE = 62


def _rises(phrase: Phrase | None) -> bool:
    return bool(phrase and phrase.runs and phrase.rise >= MIN_RISE)


def _phrase_at(ctx: _Ctx, eighth: int) -> Phrase | None:
    for phrase in ctx.phrases:
        if phrase.start <= eighth < phrase.end:
            return phrase
    return None


def _melody_swell(phrase: Phrase, eighth: int) -> int:
    """60 at the opening, 68 halfway up, 72 on the apex, 62 at the close."""
    if phrase.apex.start <= eighth < phrase.apex.end:
        return _MELODY_APEX
    amount = swell(phrase, min(max(eighth, phrase.start), phrase.end - 1))
    if eighth < phrase.apex.start:
        if amount <= 0.5:
            value = _SWELL_OPEN + (_SWELL_MID - _SWELL_OPEN) * (amount / 0.5)
        else:
            value = _SWELL_MID + (_MELODY_APEX - _SWELL_MID) * ((amount - 0.5) / 0.5)
    else:
        value = _SWELL_CLOSE + (_MELODY_APEX - _SWELL_CLOSE) * amount
    return int(round(value))


def _note_velocity(start: int, length: int, apex: set[int], phrase: Phrase | None) -> int:
    """Flat phrases keep the locked 64/72 span. A real rise follows the swell."""
    if not _rises(phrase) or length <= 0:
        return _span_velocity(start, length, apex)
    if any(phrase.apex.start <= eighth < phrase.apex.end for eighth in range(start, start + length)):
        return _MELODY_APEX
    return _melody_swell(phrase, start)


def _swell_band(amount: float) -> str:
    """Block chords on a rising phrase open at p and arrive at f."""
    if amount >= 0.8:
        return "f"
    if amount >= 0.35:
        return "mf"
    return "p"


def _under_lead(lead_vel: int, band: str) -> tuple[int, int]:
    """Support and bass for one attack, with lead > bass > support."""
    support = _BAND_SUPPORT.get(band, _INNER)
    bass = _BAND_BASS.get(band, _BASS)
    bass = min(bass, lead_vel - 2)
    support = min(support, bass - 2, lead_vel - 4)
    support = max(40, support)
    bass = max(support + 2, bass)
    if bass >= lead_vel:
        bass = max(42, lead_vel - 2)
        support = max(40, min(support, bass - 2))
    return support, bass


def _covering_melody_velocity(ctx: _Ctx, eighth: int, breaks: set[int] | None = None) -> int:
    """Velocity of the melody note that is already sounding at this eighth."""
    phrase = _phrase_at(ctx, eighth)
    apex = _apex_eighths(ctx.phrases)
    cuts = breaks or set()
    bar_start = (eighth // ctx.epb) * ctx.epb
    bar_end = min(len(ctx.melody), bar_start + ctx.epb)
    attack = eighth
    while (
        attack > bar_start
        and attack not in cuts
        and attack - 1 < len(ctx.melody)
        and ctx.melody[attack - 1] == ctx.melody[eighth]
    ):
        attack -= 1
    end = min(bar_end, eighth + 1)
    while end < bar_end and end not in cuts and ctx.melody[end] == ctx.melody[eighth]:
        end += 1
    return _note_velocity(attack, max(1, end - attack), apex, phrase)


def _inner_choices(
    chord: Chord,
    lead: int,
    bass: int,
    low: int,
    high: int,
    semitones: int,
    color: bool,
) -> list[int]:
    """Distinct chord tones strictly between the bass and the melody, low to high."""
    if lead <= bass + 1:
        return []
    found: list[int] = []
    for pc in _ordered_pool(chord, color):
        for note in range(max(low, bass + 1), min(high, lead - 1) + 1):
            if note % 12 == pc and note not in found:
                found.append(note)
    playable = [
        note
        for note in found
        if _playable([bass + semitones, note + semitones, lead + semitones])
    ]
    return sorted(playable or found)


def _study_pair(chord: Chord, tones: list[int]) -> list[int]:
    """Index then middle: a third against a fifth, seventh, or root."""
    if len(tones) < 2:
        return list(tones)
    third_pc = chord.pitches[1] % 12 if len(chord.pitches) > 1 else None
    fifth_pc = chord.pitches[2] % 12 if len(chord.pitches) > 2 else None
    seventh_pc = chord.pitches[3] % 12 if len(chord.pitches) >= 4 else None
    root_pc = chord.pitches[0] % 12
    thirds = [tone for tone in tones if third_pc is not None and tone % 12 == third_pc]
    others: list[int] = []
    for pc in (fifth_pc, seventh_pc, root_pc):
        if pc is None or pc == third_pc:
            continue
        matches = [tone for tone in tones if tone % 12 == pc]
        if matches:
            others = matches
            break
    if thirds and others:
        lower, upper = min(thirds), max(others)
        if lower == upper:
            lower, upper = tones[0], tones[-1]
        if lower > upper:
            lower, upper = upper, lower
        if lower != upper:
            return [lower, upper]
    if tones[0] != tones[-1]:
        return [tones[0], tones[-1]]
    return [tones[0]]


def _wave_index(count: int, step: int) -> int:
    if count <= 1:
        return 0
    cycle = count * 2 - 2
    pos = step % cycle
    if pos < count:
        return pos
    return cycle - pos


def _wave_tone(tones: list[int], step: int, previous: int | None) -> int:
    if len(tones) == 1:
        return tones[0]
    for shift in range(len(tones) * 2):
        choice = tones[_wave_index(len(tones), step + shift)]
        if previous is None or choice != previous:
            return choice
    return tones[_wave_index(len(tones), step)]


def _contour_tone(chord: Chord, tones: list[int], step: int, previous: int | None) -> int:
    """Low-mid, upper-mid, a colour tone, then low-mid again."""
    if len(tones) == 1:
        return tones[0]
    low = tones[0]
    upper = tones[-1]
    root = chord.pitches[0] % 12
    color_pcs = {(root + interval) % 12 for interval in (2, 3, 4, 5, 9, 10, 11)}
    colors = [tone for tone in tones if tone % 12 in color_pcs and tone not in {low, upper}]
    if not colors:
        colors = [tones[len(tones) // 2]]
    returning = tones[1] if len(tones) > 2 else low
    pattern = [low, upper, colors[step % len(colors)], returning]
    choice = pattern[step % 4]
    if previous is not None and choice == previous:
        for tone in tones:
            if tone != previous:
                return tone
    return choice


def _strings_differ(left: int, right: int, semitones: int) -> bool:
    first = _string_options(left + semitones)
    second = _string_options(right + semitones)
    return any(left_string != right_string for left_string, _fret in first for right_string, _fret in second)


def _shape_line(
    ctx: _Ctx,
    events: list[NoteEvent],
    role: str,
    breaks: set[int] | None = None,
    soften: set[int] | None = None,
    band_at=None,
    ceiling: dict[int, int] | None = None,
) -> list[NoteEvent]:
    """One velocity per attack. Tied continuations keep the attack's level."""
    shaped: list[NoteEvent] = []
    carried: int | None = None
    for event in events:
        if event.midi is None or event.velocity is None:
            shaped.append(event)
            continue
        if event.tie_stop and carried is not None:
            velocity = carried
        else:
            eighth = _start16(event, ctx.epb) // 2
            lead_vel = _covering_melody_velocity(ctx, eighth, breaks)
            band = band_at(eighth) if band_at is not None else ctx.band(event.bar)
            support_vel, bass_vel = _under_lead(lead_vel, band)
            velocity = bass_vel if role == "bass" else support_vel
            if role == "support" and soften and eighth in soften:
                velocity = max(40, velocity - 4)
            if ceiling is not None and eighth in ceiling:
                velocity = min(velocity, ceiling[eighth])
            velocity = max(40, velocity)
            carried = velocity
        shaped.append(event if event.velocity == velocity else replace(event, velocity=velocity))
    return shaped


def _bass_ceiling(ctx: _Ctx, low: list[NoteEvent]) -> dict[int, int]:
    ceiling: dict[int, int] = {}
    for event in low:
        if event.midi is None or event.velocity is None:
            continue
        begin = _start16(event, ctx.epb) // 2
        length = max(1, _dur16(event) // 2)
        for eighth in range(begin, begin + length):
            ceiling[eighth] = event.velocity - 2
    return ceiling


def _shape_accompaniment(
    ctx: _Ctx,
    support: list[NoteEvent],
    low: list[NoteEvent],
    breaks: set[int] | None = None,
    soften: set[int] | None = None,
    band_at=None,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    low = _shape_line(ctx, low, "bass", breaks, band_at=band_at)
    support = _shape_line(
        ctx,
        support,
        "support",
        breaks,
        soften,
        band_at=band_at,
        ceiling=_bass_ceiling(ctx, low),
    )
    return support, low


def _sustain(
    melody: list[int],
    start: int,
    end: int,
    epb: int,
    apex: set[int],
    breaks: set[int] | None = None,
    phrase: Phrase | None = None,
) -> list[NoteEvent]:
    cuts = breaks or set()
    events: list[NoteEvent] = []
    cursor = start
    while cursor < end:
        bar_end = min(end, (cursor // epb + 1) * epb)
        index = cursor
        while index < bar_end:
            nxt = index + 1
            while nxt < bar_end and melody[nxt] == melody[index] and nxt not in cuts:
                nxt += 1
            events.extend(
                written(
                    index,
                    nxt - index,
                    melody[index],
                    velocity=_note_velocity(index, nxt - index, apex, phrase),
                )
            )
            index = nxt
        cursor = bar_end
    return events


def _runs(melody: list[int], start: int, end: int) -> list[tuple[int, int, int]]:
    found: list[tuple[int, int, int]] = []
    index = start
    while index < end:
        nxt = index + 1
        while nxt < end and melody[nxt] == melody[index]:
            nxt += 1
        found.append((index, nxt - index, melody[index]))
        index = nxt
    return found


def _has_hold(melody: list[int], phrase: Phrase) -> bool:
    return any(length >= 4 for _start, length, _midi in _runs(melody, phrase.start, phrase.end))


def _running(melody: list[int], phrase: Phrase) -> bool:
    runs = _runs(melody, phrase.start, phrase.end)
    return bool(runs) and all(length < 4 for _start, length, _midi in runs)


def _peak(melody: list[int], phrase: Phrase) -> int:
    return max(melody[phrase.start : phrase.end])


def _select_body(
    ctx: _Ctx,
    phrase: Phrase,
    *,
    first_body: bool,
    previous: list[str],
    section,
) -> str:
    hold = _has_hold(ctx.melody, phrase)
    running = _running(ctx.melody, phrase)
    apex_bar = min(ctx.bars - 1, phrase.apex.start // ctx.epb)
    band = ctx.band(apex_bar)
    mood = ctx.mood(apex_bar)
    trio = bool(section is not None and section.trio)
    bridge = bool(section is not None and section.bridge)
    minor = ctx.mode == "minor"
    if ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM and first_body:
        return {"classic": "study", "villa": "villa_pattern"}.get(ctx.ensemble, "preludio")
    if (
        ctx.ensemble == "barrios"
        and hold
        and BARRIOS_TREMOLO_MIN_BPM <= ctx.bpm <= 140
    ):
        if len(previous) >= 2 and previous[-1] == "tremolo" and previous[-2] == "tremolo":
            return "thumb_cantabile" if (trio or bridge) else "andante"
        return "tremolo"
    if ctx.ensemble == "barrios" and ctx.bpm < BARRIOS_TREMOLO_MIN_BPM:
        return "thumb_cantabile" if bridge else "andante"
    if ctx.ensemble == "barrios" and running and mood == "calm" and trio and ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM:
        return "thumb_cantabile"
    if ctx.ensemble == "classic":
        elegiaque = ctx.bpm <= 72 or mood == "selloff" or (trio and minor)
        if elegiaque:
            return "elegiaque"
        if mood == "calm" and ctx.bpm > 72:
            return "cantabile"
    if ctx.ensemble == "villa":
        if trio or bridge:
            return "thumb_cantabile"
        if ctx.bpm <= 72 or band == "p" or mood == "calm":
            return "chord_melody"
        return "villa_pattern"
    if (
        ctx.ensemble == "barrios"
        and running
        and mood is not None
        and mood != "calm"
        and ctx.bpm > 100
        and ctx.kind in {"4/4", "6/8"}
    ):
        if ctx.kind == "4/4":
            return "choro"
        if trio:
            return "vals"
        return "hemiola" if band == "f" else "polca"
    return {"classic": "study", "villa": "villa_pattern"}.get(ctx.ensemble, "preludio")


def _patterns(ctx: _Ctx) -> list[str]:
    chosen = ["pedal"] * len(ctx.phrases)
    body: list[int] = []
    for index, phrase in enumerate(ctx.phrases):
        if phrase.end <= phrase.start:
            continue
        bar = min(ctx.bars - 1, phrase.start // ctx.epb)
        if ctx.kind_at.get(bar) in _PEDAL:
            continue
        body.append(index)
    previous: list[str] = []
    for ordinal, index in enumerate(body):
        phrase = ctx.phrases[index]
        bar = min(ctx.bars - 1, phrase.start // ctx.epb)
        pattern = _select_body(
            ctx,
            phrase,
            first_body=ordinal == 0,
            previous=previous,
            section=ctx.section(bar),
        )
        chosen[index] = pattern
        previous.append(pattern)
    return chosen


def _bar_pattern(ctx: _Ctx, bar: int, patterns: list[str]) -> str:
    kind = ctx.kind_at.get(bar, "phrase")
    if kind in _PEDAL:
        return "pedal"
    eighth = bar * ctx.epb
    for index, phrase in enumerate(ctx.phrases):
        if phrase.start <= eighth < phrase.end:
            return patterns[index]
    for index, phrase in enumerate(ctx.phrases):
        if phrase.start < (bar + 1) * ctx.epb and phrase.end > eighth:
            return patterns[index]
    return {"classic": "study", "villa": "villa_pattern"}.get(ctx.ensemble, "preludio")


def _melody_at(ctx: _Ctx, eighth: int) -> int:
    if 0 <= eighth < len(ctx.melody):
        return ctx.melody[eighth]
    return ctx.melody[-1] if ctx.melody else 64


def _support_eighths(kind: str, band: str, rolling: bool, level: int) -> set[int]:
    if kind == "4/4":
        if level >= 1 or band in {"mf", "f"}:
            return {2, 3, 6, 7}
        if band == "mp":
            return {2, 6}
        return {4}
    if kind == "6/8":
        if level >= 1 or band in {"mf", "f"}:
            return {1, 2, 4, 5}
        if band == "mp":
            return {2, 5}
        return {3}
    if level >= 1 or band in {"mf", "f"}:
        return {2, 3, 5}
    if band == "mp":
        return {2}
    return {4}


def _inner_eighths(epb: int, strong: set[int], band: str) -> set[int]:
    """Quiet bars pluck one inner note. mp keeps every other weak eighth."""
    candidates = [eighth for eighth in range(epb) if eighth not in strong]
    if not candidates:
        return set()
    if band == "p":
        return {candidates[0]}
    if band == "mp":
        return set(candidates[::2])
    return set(candidates)


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


def _villa_wave(ctx: _Ctx, bar: int, low: list[NoteEvent], offsets: list[int]) -> list[NoteEvent]:
    """Thumb keeps root and fifth. i and m roll up and down the inner chord."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    support: list[NoteEvent] = []
    previous: int | None = None
    step = 0
    for offset in offsets:
        sung = _melody_at(ctx, start + offset)
        bass = _sounding_midi(low, start + offset, ctx.epb) or _choose_bass(
            chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones
        )
        tones = _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True)
        if len(tones) >= 2 and previous is not None:
            crossed = [tone for tone in tones if tone != previous and _strings_differ(previous, tone, ctx.semitones)]
            if len(crossed) >= 2:
                tones = crossed
        if not tones:
            tone = _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True, offset)
        else:
            tone = _wave_tone(sorted(tones), step, previous)
            step += 1
        if tone is None:
            continue
        previous = tone
        support.extend(_eighth_event(start + offset, 1, tone, ctx.epb, 2, _INNER))
    return support


def _render_villa_bar(ctx: _Ctx, bar: int, approach: bool) -> tuple[list[NoteEvent], list[NoteEvent]]:
    support, low = _render_study_bar(ctx, bar, level=1 if ctx.band(bar) in {"mf", "f"} else 0, color=True)
    band = ctx.band(bar)
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    if band in {"mf", "f"} and ctx.kind == "4/4":
        # Full roll on every eighth the thumb does not open. The bass eighths
        # stay empty so the previous inner note can ring across them (campanella).
        occupied = {(_start16(event, epb) // 2) - start for event in low if event.midi is not None}
        offsets = [offset for offset in range(epb) if offset not in occupied]
    else:
        offsets = sorted({(_start16(event, epb) // 2) - start for event in support if event.midi is not None})
    support = _villa_wave(ctx, bar, low, offsets)
    if approach and band == "f":
        nxt = ctx.chord(bar + 1)
        target = _choose_bass(nxt, 0, _melody_at(ctx, (bar + 1) * epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
        leading = target - 1
        if leading < ctx.bass_low or leading > ctx.bass_high:
            leading = _fit((target - 1) % 12, ctx.bass_low, ctx.bass_high)
        last = start + epb - 1
        low = _cut_before(low, last, epb)
        low.extend(_eighth_event(last, 1, leading, epb, 3, _INNER))
        support = [event for event in support if _start16(event, epb) // 2 != last]
    accents = set()
    tresillo = _tresillo_bars(ctx.bars, ctx.epb, ctx.band_at, ctx.character, ctx.character_at)
    if bar in tresillo and ctx.kind == "4/4":
        accents = {0, 3, 6}
    elif ctx.kind == "6/8" and band in {"mf", "f"}:
        accents = {0, 3}
    elif ctx.kind == "3/4" and band == "f":
        accents = {0, 3}
    support, low = _shape_accompaniment(ctx, support, low)
    if accents:
        support = [_accent_at(event, start, accents, epb) for event in support]
        low = [_accent_at(event, start, accents, epb) for event in low]
    return support, low


def _accent_at(event: NoteEvent, start: int, accents: set[int], epb: int) -> NoteEvent:
    eighth = _start16(event, epb) // 2 - start
    if eighth in accents and event.midi is not None:
        return replace(event, accent=True)
    return event


def _sounding_midi(events: list[NoteEvent], eighth: int, epb: int) -> int | None:
    for event in events:
        if event.midi is None:
            continue
        begin = _start16(event, epb) // 2
        end = begin + max(1, _dur16(event) // 2)
        if begin <= eighth < end:
            return event.midi
    return None


def _cut_before(events: list[NoteEvent], eighth: int, epb: int) -> list[NoteEvent]:
    """Drop or shorten low notes so `eighth` is free for a new attack."""
    kept: list[NoteEvent] = []
    cut = eighth * 2
    for event in events:
        start = _start16(event, epb)
        end = start + _dur16(event)
        if end <= cut or start >= cut:
            if start < cut:
                kept.append(event)
            continue
        if start < cut:
            kept.extend(
                _spell16(start, cut - start, event.midi, epb, event.voice, event.velocity, event.accent)
            )
    return kept


def _color_note(ctx: _Ctx, chord: Chord, sung: int, bass: int) -> int | None:
    """Suspended colours are 2/5/10. Tertian inner notes are thirds and sevenths."""
    suspended = chord.quality_group == "suspended" or chord.kind_text in {"sus2", "sus4", "7sus4", "add9", "madd9"}
    allowed = _COLOR_SUSPENDED if suspended else _COLOR_TERTIAN
    found = [
        note
        for note in range(ctx.mid_high, ctx.mid_low - 1, -1)
        if note % 12 in allowed and bass < note < sung
    ]
    for note in found:
        if _playable([bass + ctx.semitones, note + ctx.semitones, sung + ctx.semitones]):
            return note
    return found[0] if found else None


def _block_tone(
    ctx: _Ctx,
    chord: Chord,
    sung: int,
    bass: int,
    previous: int | None,
    melody_delta: int,
    inner: str,
) -> int | None:
    """Move the inner voice with the melody instead of parking it on one pitch."""
    if inner == "color":
        suspended = chord.quality_group == "suspended" or chord.kind_text in {"sus2", "sus4", "7sus4", "add9", "madd9"}
        allowed = _COLOR_SUSPENDED if suspended else _COLOR_TERTIAN
        tones = [
            tone
            for tone in _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True)
            if tone % 12 in allowed
        ]
        fallback = _color_note(ctx, chord, sung, bass)
    elif inner == "third":
        tones = _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        fallback = _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False, 1)
    else:
        parallel = _parallel(sung, bass, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, previous)
        tones = _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if parallel is not None and (not tones or parallel in tones or previous is not None):
            return parallel
        fallback = _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False, 0)
    pool = tones or ([fallback] if fallback is not None else [])
    if not pool:
        return None
    if previous is None:
        return max(pool)
    if melody_delta > 0:
        higher = [tone for tone in pool if tone > previous]
        if higher:
            return min(higher)
    elif melody_delta < 0:
        lower = [tone for tone in pool if tone < previous]
        if lower:
            return max(lower)
    different = [tone for tone in pool if tone != previous]
    if different:
        return min(different, key=lambda tone: (abs(tone - previous), -tone))
    return previous


def _render_block_bar(
    ctx: _Ctx,
    bar: int,
    points: list[int],
    spans: list[int],
    *,
    inner: str,
    phrase: Phrase | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []
    breaks = {start + point for point in points}
    previous: int | None = None
    previous_sung: int | None = None
    for offset, span in zip(points, spans):
        eighth = start + offset
        sung = _melody_at(ctx, eighth)
        root = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
        melody_delta = 0 if previous_sung is None else sung - previous_sung
        tone = _block_tone(ctx, chord, sung, root, previous, melody_delta, inner)
        band = ctx.band(bar)
        if _rises(phrase):
            band = _swell_band(swell(phrase, min(eighth, phrase.end - 1)))
        lead_vel = _covering_melody_velocity(ctx, eighth, breaks)
        support_vel, bass_vel = _under_lead(lead_vel, band)
        low.extend(_eighth_event(start + offset, span, root, ctx.epb, 3, bass_vel))
        if tone is not None:
            support.extend(_eighth_event(start + offset, span, tone, ctx.epb, 2, support_vel))
            previous = tone
        previous_sung = sung
    return support, low


def _andante_grid(ctx: _Ctx, bar: int, phrase: Phrase | None) -> tuple[list[int], list[int]]:
    if ctx.kind == "4/4":
        return [0, 4], [4, 4]
    if ctx.kind == "6/8":
        return [0, 3], [3, 3]
    points, spans = [0], [ctx.epb]
    special = False
    if phrase is not None:
        apex_bar = phrase.apex.start // ctx.epb
        end_bar = (phrase.end - 1) // ctx.epb
        special = bar == apex_bar or (phrase.closes and bar == end_bar)
    if special:
        return [0, 4], [4, 2]
    return points, spans


def _chord_grid(ctx: _Ctx, bar: int, phrase: Phrase | None) -> tuple[list[int], list[int]]:
    rise = phrase is not None and _peak(ctx.melody, phrase) - min(ctx.melody[phrase.start : phrase.end]) >= MIN_RISE
    if ctx.kind == "4/4":
        if phrase is not None and rise and bar <= phrase.apex.start // ctx.epb:
            return [0, 2, 4, 6], [2, 2, 2, 2]
        return [0, 4], [4, 4]
    if ctx.kind == "6/8":
        if phrase is not None and rise:
            apex_bar = phrase.apex.start // ctx.epb
            if bar == apex_bar or bar == apex_bar - 1 and phrase.start <= bar * ctx.epb:
                return [0, 3], [3, 3]
        return [0], [ctx.epb]
    points, spans = [0], [ctx.epb]
    if phrase is None:
        return points, spans
    apex_bar = phrase.apex.start // ctx.epb
    end_bar = (phrase.end - 1) // ctx.epb
    if (rise and phrase.start <= bar * ctx.epb <= phrase.apex.start) or bar == apex_bar or (phrase.closes and bar == end_bar):
        return [0, 4], [4, 2]
    return points, spans


_SPARSER = {"f": "mf", "mf": "mp", "mp": "p", "p": "p"}
_COLOR_SUSPENDED = frozenset({2, 5, 10})
_COLOR_TERTIAN = frozenset({3, 4, 10, 11})


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


def _parallel(
    lead: int,
    bass: int,
    mode: str,
    low: int,
    high: int,
    semitones: int = 0,
    previous: int | None = None,
) -> int | None:
    """A third under the melody, or a sixth when the third leaves the hand."""
    if not _on_scale(lead, mode):
        lead = _nearest(lead, mode, low, high + 12)
    classes = _classes(mode)
    try:
        lead_degree = classes.index(lead % 12)
    except ValueError:
        return None

    def options(steps: int) -> list[int]:
        want = classes[(lead_degree - steps) % len(classes)]
        return [note for note in range(high, low - 1, -1) if note % 12 == want and bass < note < lead]

    def playable(notes: list[int]) -> list[int]:
        return [note for note in notes if _playable([bass + semitones, note + semitones, lead + semitones])]

    thirds = playable(options(2))
    sixths = playable(options(5))
    pool = thirds or sixths or options(2) or options(5)
    if not pool:
        return None
    if previous is None:
        return pool[0]
    return min(pool, key=lambda note: (abs(note - previous), -note))


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


def _place_thumb(ctx: _Ctx, phrase: Phrase) -> list[int]:
    floor = 48 - ctx.semitones
    top = 64 - ctx.semitones
    window = list(ctx.raw[phrase.start : phrase.end])
    if ctx.mode == "minor":
        window = [note - 1 if note % 12 == 11 else note for note in window]
    scale = _melody_scale(ctx.mode)
    degree = {note: index for index, note in enumerate(scale)}
    snapped = []
    for note in window:
        snapped.append(note if note in degree else _nearest(note, ctx.mode, 24, 120))
    found: list[tuple[int, int, list[int]]] = []
    for shift in (-12, -24):
        shifted = [note + shift for note in snapped]
        if any(note not in degree for note in shifted):
            continue
        overflow = _overflow(shifted, floor, top)
        line = list(shifted) if overflow == 0 else _compress_monotone(shifted, floor, top, degree, scale)
        found.append((overflow, abs(shift), line))
    if found:
        line = min(found, key=lambda item: (item[0], item[1]))[2]
    else:
        line = [max(floor, min(top, note)) for note in snapped]
    pad = [line[0]] * phrase.start + line
    window_scale = tuple(note for note in scale if floor <= note <= top)
    if window_scale and ctx.chord_at:
        pad = quantize_strong_beats(pad, ctx.chord_at, window_scale, ctx.mode)
        line = pad[phrase.start : phrase.end]
    return [max(floor, min(top, note)) for note in line]


def _upper_dyad(ctx: _Ctx, chord: Chord, floor_pitch: int) -> tuple[int, int] | None:
    pool = _pool(chord)
    notes = [
        note
        for pc in pool
        for note in range(max(ctx.mid_low, floor_pitch + 1), ctx.treble_top + 1)
        if note % 12 == pc and note > floor_pitch
    ]
    best: tuple[int, int] | None = None
    for lower in notes:
        for higher in notes:
            if higher <= lower:
                continue
            if lower > ctx.mid_high and not (higher >= 80 and higher - lower <= 12):
                if lower > ctx.treble_top:
                    continue
            if not _playable([floor_pitch + ctx.semitones, lower + ctx.semitones, higher + ctx.semitones]):
                continue
            if best is None or (lower, higher) < best:
                best = (lower, higher)
    return best


def _thumb_offsets(ctx: _Ctx, band: str) -> tuple[int, ...]:
    if ctx.kind == "3/4":
        return (2, 4)
    if ctx.kind == "6/8":
        return (1, 2, 4, 5) if band in {"mf", "f"} else (2, 5)
    return (2, 6)


def _render_thumb(ctx: _Ctx, phrase: Phrase) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    line = _place_thumb(ctx, phrase)
    peak = max(line) if line else 0
    low = _sustain(
        [0] * phrase.start + line,
        phrase.start,
        phrase.end,
        ctx.epb,
        {phrase.start + offset for offset, note in enumerate(line) if note == peak},
    )
    for index, event in enumerate(low):
        if event.midi is None:
            continue
        eighth = _start16(event, ctx.epb) // 2
        if _rises(phrase):
            # The thumb sings from the written melody level up to the apex.
            if phrase.apex.start <= eighth < phrase.apex.end:
                velocity = _MELODY_APEX
            else:
                amount = swell(phrase, min(max(eighth, phrase.start), phrase.end - 1))
                velocity = int(round(_MELODY + (_MELODY_APEX - _MELODY) * amount))
        else:
            velocity = _MELODY_APEX if event.midi == peak else _MELODY
        low[index] = replace(event, velocity=velocity, voice=3)
    support: list[NoteEvent] = []
    lead: list[NoteEvent] = []
    for bar in range(phrase.start // ctx.epb, (phrase.end - 1) // ctx.epb + 1):
        for offset in _thumb_offsets(ctx, ctx.band(bar)):
            eighth = bar * ctx.epb + offset
            if not phrase.start <= eighth < phrase.end:
                continue
            sung = _sounding_midi(low, eighth, ctx.epb)
            if sung is None and 0 <= eighth - phrase.start < len(line):
                sung = line[eighth - phrase.start]
            if sung is None:
                continue
            dyad = _upper_dyad(ctx, ctx.chord(bar), sung)
            if dyad is None:
                continue
            lower, higher = dyad
            thumb_vel = _INNER
            for event in low:
                if event.midi is not None and _covers(event, eighth * 2, ctx.epb) and event.velocity is not None:
                    thumb_vel = event.velocity
                    break
            amount = swell(phrase, min(eighth, phrase.end - 1)) if _rises(phrase) else 0.0
            # Both dyad notes stay in the bell window [_INNER - 4, _INNER],
            # and the lower one is the softer of the pair when the window allows.
            upper_vel = int(round((_INNER - 4) + 4 * amount))
            upper_vel = min(_INNER, max(_INNER - 4, upper_vel), thumb_vel - 2)
            lower_vel = min(upper_vel - 2, _INNER - 2)
            lower_vel = max(_INNER - 4, lower_vel)
            if lower_vel > upper_vel:
                lower_vel = upper_vel
            support.extend(_eighth_event(eighth, 1, lower, ctx.epb, 2, lower_vel))
            lead.extend(_eighth_event(eighth, 1, higher, ctx.epb, 1, upper_vel))
    return lead, support, low


def _lead_attacks(melody: list[int], start: int, end: int) -> set[int]:
    attacks = {start}
    for eighth in range(start + 1, end):
        if melody[eighth] != melody[eighth - 1]:
            attacks.add(eighth)
    return attacks


def _tone_below(chord: Chord, sung: int, mid_low: int, mid_high: int, prefer: str) -> int | None:
    """Third, then the kept seventh or augmented-sixth tone, then the rest of the pool."""
    third = chord.pitches[1] % 12 if len(chord.pitches) > 1 else chord.pitches[0] % 12
    seventh = chord.pitches[3] % 12 if len(chord.pitches) >= 4 else None
    if prefer == "seventh":
        order = [tone for tone in (seventh, third, *_pool(chord)) if tone is not None]
    else:
        order = [tone for tone in (third, seventh, *_pool(chord)) if tone is not None]
    seen: list[int] = []
    for pitch_class in order:
        if pitch_class in seen:
            continue
        seen.append(pitch_class)
        tone = _fit(pitch_class, mid_low, mid_high)
        while tone >= sung and tone - 12 >= mid_low:
            tone -= 12
        if tone < sung:
            return tone
    return None


def _approach_pitch(ctx: _Ctx, chord: Chord) -> int:
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    note = root - 1
    if ctx.bass_low <= note <= ctx.bass_high:
        return note
    return _fit(note % 12, ctx.bass_low, ctx.bass_high)


def _lead_bar(ctx: _Ctx, bar: int, breath: int | None, apex: set[int]) -> list[NoteEvent]:
    """Melody on the eighth grid. A pattern-change breath is one eighth of rest."""
    start = bar * ctx.epb
    end = start + ctx.epb
    phrase = _phrase_at(ctx, start)
    events: list[NoteEvent] = []
    eighth = start
    while eighth < end:
        if breath is not None and eighth == breath:
            eighth += 1
            continue
        pitch = _melody_at(ctx, eighth)
        nxt = eighth + 1
        while nxt < end and nxt != breath and _melody_at(ctx, nxt) == pitch:
            nxt += 1
        events.extend(
            _eighth_event(eighth, nxt - eighth, pitch, ctx.epb, 1, _note_velocity(eighth, nxt - eighth, apex, phrase))
        )
        eighth = nxt
    return events


def _dance_exit(ctx: _Ctx, bar: int, patterns: list[str]) -> tuple[bool, int | None, bool]:
    """Leaving a dance drops the approach and breathes; a continued dance may approach."""
    owner = _owner(ctx, bar)
    phrase = ctx.phrases[owner] if owner is not None else None
    ends = phrase is not None and bar == (phrase.end - 1) // ctx.epb
    following = None
    if owner is not None:
        for index in range(owner + 1, len(patterns)):
            start_bar = ctx.phrases[index].start // ctx.epb
            if ctx.kind_at.get(start_bar, "phrase") in _PEDAL:
                continue
            following = patterns[index]
            break
    leaving = bool(ends and following not in _DANCE)
    breath = None
    if (
        leaving
        and following is not None
        and phrase is not None
        and phrase.end - phrase.start >= 4
    ):
        breath = phrase.end - 1
    approach = False
    if not leaving and bar + 1 < ctx.bars and _fifth_down(ctx, bar):
        nxt = _bar_pattern(ctx, bar + 1, patterns)
        if nxt in _DANCE:
            approach = True
    return leaving, breath, approach


def _finish_dance_grid(
    low: list[tuple[int | None, int | None]],
    support: list[tuple[int | None, int | None]],
    *,
    leaving: bool,
    approach: int | None,
    breath: int | None,
    bar: int,
    epb: int,
) -> None:
    last = len(low) - 1
    if leaving:
        low[last] = (None, None)
        support[last] = (None, None)
        for index in range(max(0, len(support) - 4), len(support)):
            if index % 2 == 1:
                support[index] = (None, None)
    elif approach is not None:
        support[last] = (None, None)
        low[last] = (approach, _BASS)
    if breath is not None and bar * epb <= breath < (bar + 1) * epb:
        local = (breath - bar * epb) * 2
        if 0 <= local < len(support):
            support[local] = (None, None)
        if 0 <= local + 1 < len(support):
            support[local + 1] = (None, None)


def _events_from_slots(
    bar: int,
    slots: list[tuple[int | None, int | None]],
    voice: int,
    accents: set[int] | None = None,
) -> list[NoteEvent]:
    marked = accents or set()
    events: list[NoteEvent] = []
    for index, (midi, velocity) in enumerate(slots):
        if midi is None:
            continue
        event = _hit(bar, index * 0.25, 0.25, midi, voice, velocity if velocity is not None else _INNER)
        if index in marked:
            event = replace(event, accent=True)
        events.append(event)
    return events


def _dance_ranked(chord: Chord, sung: int, low: int, high: int) -> list[int]:
    """Third, then seventh or sixth, then the rest of the chord."""
    third = chord.pitches[1] % 12 if len(chord.pitches) > 1 else chord.pitches[0] % 12
    seventh = chord.pitches[3] % 12 if len(chord.pitches) >= 4 else None
    sixth = (chord.pitches[0] + 9) % 12
    fifth = chord.pitches[2] % 12 if len(chord.pitches) > 2 else None
    found: list[int] = []
    seen: set[int] = set()
    for pc in (third, seventh, sixth, fifth, *_pool(chord)):
        if pc is None or pc in seen:
            continue
        seen.add(pc)
        tone = _fit(pc, low, high)
        while tone >= sung and tone - 12 >= low:
            tone -= 12
        if low <= tone < sung and tone not in found:
            found.append(tone)
    return found


def _dance_velocity(ctx: _Ctx, eighth: int, role: str, *, sync: bool) -> int:
    lead_vel = _covering_melody_velocity(ctx, eighth)
    support_vel, bass_vel = _under_lead(lead_vel, ctx.band(eighth // ctx.epb))
    velocity = bass_vel if role == "bass" else support_vel
    if sync:
        bumped = velocity + 4
        limit = lead_vel - 2 if role == "bass" else min(lead_vel - 4, bass_vel - 2)
        if bumped < limit:
            velocity = bumped
    return max(40, velocity)


def _render_vals_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    leaving, breath, do_approach = _dance_exit(ctx, bar, patterns)
    start = bar * ctx.epb
    chord = ctx.chord(bar)
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    fifth = _clamp(chord.pitches[2], ctx.bass_low, ctx.bass_high) if len(chord.pitches) >= 3 else root
    passing = _clamp(chord.pitches[1], ctx.bass_low, ctx.bass_high) if len(chord.pitches) > 1 else root
    lead = _lead_bar(ctx, bar, breath, apex)
    support: list[NoteEvent] = []
    low = [
        _hit(bar, 0.0, 0.5, root, 3, _dance_velocity(ctx, start, "bass", sync=False)),
        _hit(bar, 1.5, 0.5, fifth, 3, _dance_velocity(ctx, start + 3, "bass", sync=False)),
        replace(
            _hit(bar, 2.0, 0.25, passing, 3, _dance_velocity(ctx, start + 4, "bass", sync=True)),
            accent=True,
        ),
    ]
    previous: int | None = None
    step = 0
    for eighth in (1, 2, 4, 5):
        melody = _melody_at(ctx, start + eighth)
        legacy = _tone_below(chord, melody, ctx.mid_low, ctx.mid_high, "third")
        ranked = [
            tone
            for tone in _dance_ranked(chord, melody, ctx.mid_low, ctx.mid_high)
            if root < tone < melody and _playable([tone + ctx.semitones, melody + ctx.semitones])
        ]
        if len(ranked) >= 2:
            tone = ranked[step % 2]
            if previous is not None and tone == previous:
                tone = ranked[(step + 1) % len(ranked)]
            step += 1
        else:
            tone = legacy
        if tone is None or not root < tone < melody:
            continue
        previous = tone
        # Eighth 4 is beat 2, where 6/8 and 3/4 cross.
        sync = eighth == 4
        event = _hit(bar, eighth * 0.5, 0.25, tone, 2, _dance_velocity(ctx, start + eighth, "support", sync=sync))
        if sync:
            event = replace(event, accent=True)
        support.append(event)
    if do_approach and bar + 1 < ctx.bars:
        low.append(_hit(bar, ctx.bar_beats - 0.25, 0.25, _approach_pitch(ctx, ctx.chord(bar + 1)), 3, _BASS))
    if leaving:
        support = [
            event
            for event in support
            if not (
                int(round(event.beat * 4)) >= (ctx.epb * 2 - 4)
                and int(round(event.beat * 4)) % 2 == 1
            )
        ]
        if breath is not None and bar * ctx.epb <= breath < (bar + 1) * ctx.epb:
            local = (breath - bar * ctx.epb) * 0.5
            support = [event for event in support if not local <= event.beat < local + 0.5]
    return lead, support, low


def _slot_dance(
    ctx: _Ctx,
    bar: int,
    patterns: list[str],
    apex: set[int],
    *,
    kind: str,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    leaving, breath, do_approach = _dance_exit(ctx, bar, patterns)
    chord = ctx.chord(bar)
    sixteenths = ctx.epb * 2
    low: list[tuple[int | None, int | None]] = [(None, None)] * sixteenths
    support: list[tuple[int | None, int | None]] = [(None, None)] * sixteenths
    root = _clamp(chord.pitches[0], ctx.bass_low, ctx.bass_high)
    fifth = _clamp(chord.pitches[2], ctx.bass_low, ctx.bass_high) if len(chord.pitches) >= 3 else root

    low_accents: set[int] = set()
    support_accents: set[int] = set()
    step = 0
    previous: int | None = None

    def sung(index: int) -> int:
        return _melody_at(ctx, bar * ctx.epb + index // 2)

    def place_low(index: int, midi: int, *, sync: bool = False) -> None:
        eighth = bar * ctx.epb + index // 2
        low[index] = (midi, _dance_velocity(ctx, eighth, "bass", sync=sync))
        if sync:
            low_accents.add(index)

    def support_at(index: int, prefer: str, *, sync: bool = False) -> None:
        nonlocal step, previous
        del prefer
        melody = sung(index)
        legacy = _tone_below(chord, melody, ctx.mid_low, ctx.mid_high, "third" if not sync else "seventh")
        ranked = [
            tone
            for tone in _dance_ranked(chord, melody, ctx.mid_low, ctx.mid_high)
            if root < tone < melody and _playable([tone + ctx.semitones, melody + ctx.semitones])
        ]
        if len(ranked) >= 2:
            tone = ranked[step % 2]
            if previous is not None and tone == previous:
                tone = ranked[(step + 1) % len(ranked)]
            step += 1
        else:
            tone = legacy
        if tone is None:
            return
        previous = tone
        eighth = bar * ctx.epb + index // 2
        support[index] = (tone, _dance_velocity(ctx, eighth, "support", sync=sync))
        if sync:
            support_accents.add(index)

    if kind == "hemiola":
        place_low(0, root)
        place_low(4, fifth, sync=True)
        place_low(8, root, sync=True)
        for index in (0, 4, 8):
            support_at(index, "third", sync=index in {4, 8})
    elif kind == "polca":
        place_low(0, root)
        place_low(6, fifth, sync=True)
        for index in (2, 4, 8, 10):
            support_at(index, "third", sync=index in {4, 10})
    else:
        for origin in (0, 8):
            place_low(origin, root)
            place_low(origin + 4, fifth)
            support_at(origin + 3, "third")
            support_at(origin + 6, "seventh", sync=True)
            support_at(origin + 7, "third", sync=True)
    leading = _approach_pitch(ctx, ctx.chord(bar + 1)) if do_approach and bar + 1 < ctx.bars else None
    _finish_dance_grid(
        low,
        support,
        leaving=leaving,
        approach=leading,
        breath=breath,
        bar=bar,
        epb=ctx.epb,
    )
    if leading is not None and not leaving:
        last = len(low) - 1
        if low[last][0] == leading:
            eighth = bar * ctx.epb + last // 2
            low[last] = (leading, _dance_velocity(ctx, eighth, "bass", sync=False))
    return (
        _lead_bar(ctx, bar, breath, apex),
        _events_from_slots(bar, support, 2, support_accents),
        _events_from_slots(bar, low, 3, low_accents),
    )


def _render_hemiola_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _slot_dance(ctx, bar, patterns, apex, kind="hemiola")


def _render_polca_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _slot_dance(ctx, bar, patterns, apex, kind="polca")


def _render_choro_bar(
    ctx: _Ctx, bar: int, patterns: list[str], apex: set[int]
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _slot_dance(ctx, bar, patterns, apex, kind="choro")


def _fifth_down(ctx: _Ctx, bar: int) -> bool:
    if bar + 1 >= ctx.bars:
        return False
    current = ctx.chord(bar).pitches[0] % 12
    nxt = ctx.chord(bar + 1).pitches[0] % 12
    return (current - nxt) % 12 == 7


def _same_phrase(ctx: _Ctx, bar: int, nxt: int) -> bool:
    for phrase in ctx.phrases:
        if phrase.start <= bar * ctx.epb and nxt * ctx.epb < phrase.end:
            return True
    return False


def _apply_campanella(
    ctx: _Ctx,
    support: list[NoteEvent],
    lead: list[NoteEvent],
    villa_bars: set[int] | None = None,
) -> list[NoteEvent]:
    lead_at: dict[int, int] = {}
    for event in lead:
        if event.midi is None:
            continue
        lead_at.setdefault(_start16(event, ctx.epb) // 2, event.midi)
    # A sustained lead note covers later eighths too.
    covered: dict[int, int] = {}
    for event in lead:
        if event.midi is None:
            continue
        begin = _start16(event, ctx.epb) // 2
        span = max(1, _dur16(event) // 2)
        for eighth in range(begin, begin + span):
            covered.setdefault(eighth, event.midi)
    onsets = sorted({_start16(event, ctx.epb) // 2 for event in support if event.midi is not None})
    nxt = {left: right for left, right in zip(onsets, onsets[1:])}
    updated: list[NoteEvent] = []
    for event in support:
        if event.midi is None or (villa_bars is not None and event.bar not in villa_bars):
            updated.append(event)
            continue
        eighth = _start16(event, ctx.epb) // 2
        following = nxt.get(eighth)
        if following is not None and following <= eighth + 1:
            updated.append(event)
            continue
        sung = covered.get(eighth + 1) or lead_at.get(eighth + 1) or covered.get(eighth)
        if sung is None:
            updated.append(event)
            continue
        if (eighth + 1) // ctx.epb != eighth // ctx.epb:
            updated.append(event)
            continue
        begin16 = _start16(event, ctx.epb)
        if begin16 + _dur16(event) + 2 > (event.bar + 1) * ctx.epb * 2:
            updated.append(event)
            continue
        pair = [event.midi + ctx.semitones, sung + ctx.semitones]
        if event.midi == sung or not _playable(pair):
            updated.append(event)
            continue
        longer = _dur16(event) + 2
        updated.extend(_spell16(_start16(event, ctx.epb), longer, event.midi, ctx.epb, 2, event.velocity, event.accent))
    return updated


def _bell_pitch(pc: int, ctx: _Ctx, above: int) -> int | None:
    floor = 76 - ctx.semitones
    best = None
    for note in range(floor, ctx.ceiling + 1):
        if note % 12 == pc and note > above:
            best = note
    return best


def _bell_groups(ctx: _Ctx, enabled_bars: set[int]) -> list[tuple[int | None, list[int]]]:
    """1D keeps the default cap. A long-form section caps at 15% of its eighths."""
    order: list[tuple] = []
    found: dict[tuple, list] = {}
    for bar in sorted(enabled_bars):
        section = ctx.section(bar) if ctx.sections else None
        if not ctx.sections or section is None:
            key = ("plain",)
            cap = None
        else:
            key = (section.start, section.end)
            cap = round(0.15 * (section.end - section.start) * ctx.epb)
        if key not in found:
            found[key] = [cap, []]
            order.append(key)
        found[key][1].append(bar)
    return [(found[key][0], found[key][1]) for key in order]


def _bell_slot(ctx: _Ctx, bar: int) -> tuple[int, int] | None:
    """One unaccented eighth: the second eighth of a hold, or the first weak eighth."""
    start = bar * ctx.epb
    end = min(len(ctx.melody), start + ctx.epb)
    eighth = start
    while eighth < end:
        nxt = eighth + 1
        limit = min(len(ctx.melody), (bar + 1) * ctx.epb if eighth // ctx.epb == bar else len(ctx.melody))
        while nxt < len(ctx.melody) and ctx.melody[nxt] == ctx.melody[eighth]:
            nxt += 1
        if nxt - eighth >= 2:
            candidate = eighth + 1
            if start <= candidate < end and candidate % ctx.epb not in ctx.strong:
                return candidate, ctx.melody[eighth]
        eighth = max(nxt, eighth + 1)
    for candidate in range(start, end):
        if candidate % ctx.epb not in ctx.strong:
            return candidate, ctx.melody[candidate]
    return None


def _insert_bells(ctx: _Ctx, lead: list[NoteEvent], support: list[NoteEvent], enabled_bars: set[int]) -> tuple[list[NoteEvent], list[NoteEvent]]:
    if not enabled_bars or ctx.rel_span <= 0.005:
        return lead, support
    bells: list[tuple[int, int, int]] = []
    for cap, bars in _bell_groups(ctx, enabled_bars):
        budget = bell_budget(ctx.rel_span) if cap is None else bell_budget(ctx.rel_span, cap)
        placed: list[int] = []
        for bar in bars:
            if budget <= 0:
                break
            if placed and bar < placed[-1] + 2:
                continue
            found = _bell_slot(ctx, bar)
            if found is None:
                continue
            slot, sung = found
            window = ctx.melody[bar * ctx.epb : (bar + 1) * ctx.epb] or [sung]
            pcs = [max(window) % 12, *sorted(ctx.chord(bar).pitch_classes, reverse=True)]
            pitch = None
            for pc in pcs:
                pitch = _bell_pitch(pc, ctx, max(sung, ctx.melody[slot]))
                if pitch is not None:
                    break
            if pitch is None:
                continue
            bells.append((slot, 1, pitch))
            placed.append(bar)
            budget -= 1
    if not bells:
        return lead, support
    for eighth, dur, pitch in bells:
        start16 = eighth * 2
        end16 = (eighth + dur) * 2
        rewritten: list[NoteEvent] = []
        for event in lead:
            if event.midi is None:
                rewritten.append(event)
                continue
            begin = _start16(event, ctx.epb)
            finish = begin + _dur16(event)
            if finish <= start16 or begin >= end16:
                rewritten.append(event)
                continue
            if begin < start16:
                rewritten.extend(_spell16(begin, start16 - begin, event.midi, ctx.epb, 1, event.velocity))
            if finish > end16:
                rewritten.extend(_spell16(end16, finish - end16, event.midi, ctx.epb, 1, event.velocity))
        # The bell replaces the held tail. Voice 1 stays monophonic, so no <chord/>.
        rewritten.extend(_spell16(start16, end16 - start16, pitch, ctx.epb, 1, _MELODY_APEX))
        lead = rewritten
    return lead, support


def _drop_overlap(events: list[NoteEvent], start: int, end: int, epb: int) -> list[NoteEvent]:
    kept: list[NoteEvent] = []
    for event in events:
        if event.midi is None:
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if finish <= start or begin >= end:
            kept.append(event)
            continue
        if begin < start:
            kept.extend(_spell16(begin, start - begin, event.midi, epb, event.voice, event.velocity, event.accent))
    return kept


def _silence(events: list[NoteEvent], eighth: int, epb: int) -> list[NoteEvent]:
    return _drop_overlap(events, eighth * 2, eighth * 2 + 2, epb)


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


def _scale_line(target: int, steps: int, ascending: bool, mode: str, low: int, high: int, chromatic: bool) -> list[int]:
    start = target
    moved = 0
    for _ in range(steps):
        nxt = _walk(start, -1 if ascending else 1, mode, low, high)
        if nxt == start or not low <= nxt <= high:
            break
        start = nxt
        moved += 1
    if moved < 1:
        return [target]
    line = [start]
    cursor = start
    for _ in range(moved):
        nxt = _walk(cursor, 1 if ascending else -1, mode, low, high)
        line.append(nxt)
        cursor = nxt
    line[-1] = target
    if chromatic and len(line) >= 2:
        neighbour = target - 1 if ascending else target + 1
        if low <= neighbour <= high:
            line[-2] = neighbour
    return line


def _run_slots(target: int, epb: int, strong: tuple[int, ...], sixteenths: bool, phrase: Phrase) -> list[int]:
    previous = None
    for eighth in range(target - 1, max(phrase.start, target - epb) - 1, -1):
        if eighth < phrase.start:
            break
        if eighth % epb in strong:
            previous = eighth
            break
    if sixteenths:
        begin = phrase.start * 2 if previous is None else previous * 2 + 1
        slots = list(range(begin, target * 2 + 1))
        slots = [slot for slot in slots if slot // 2 // epb == target // epb or slot // 2 >= phrase.start]
        slots = [slot for slot in slots if phrase.start * 2 <= slot <= (phrase.end * 2 - 1)]
        want = 6 if len(slots) >= 6 else (4 if len(slots) >= 4 else len(slots))
        return slots[-want:]
    begin = phrase.start if previous is None else previous + 1
    slots = list(range(max(phrase.start, begin), target + 1))
    if len(slots) > 4:
        slots = slots[-4:]
    return slots


def _target_eighth(ctx: _Ctx, phrase: Phrase, ascent: bool) -> int | None:
    segment = ctx.melody[phrase.start : phrase.end]
    if not segment:
        return None
    if ascent:
        peak = max(segment)
        for eighth in range(phrase.start, phrase.end):
            if ctx.melody[eighth] == peak and eighth % ctx.epb in ctx.strong:
                return eighth
        for eighth in range(phrase.start, phrase.end):
            if ctx.melody[eighth] != peak:
                continue
            for strong in ctx.strong:
                pos = (eighth // ctx.epb) * ctx.epb + strong
                if eighth <= pos < phrase.end and ctx.melody[pos] == peak:
                    return pos
        return None
    # Descending close: last strong eighth of the phrase.
    for eighth in range(phrase.end - 1, phrase.start - 1, -1):
        if eighth % ctx.epb in ctx.strong:
            return eighth
    return None


def _apply_scale_run(
    ctx: _Ctx,
    lead: list[NoteEvent],
    support: list[NoteEvent],
    low: list[NoteEvent],
    phrase: Phrase,
    target: int,
    ascending: bool,
    chromatic: bool,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], set[int]]:
    sixteenths = ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM
    slots = _run_slots(target, ctx.epb, ctx.strong, sixteenths, phrase)
    if len(slots) < 2:
        return lead, support, low, set()
    steps = min(5, max(3, len(slots) - 1))
    line = _scale_line(ctx.melody[target], steps, ascending, ctx.mode, ctx.treble_floor, ctx.treble_top, chromatic)
    if len(line) > len(slots):
        line = line[-len(slots) :]
    slots = slots[-len(line) :]
    line[-1] = ctx.melody[target]
    for index, slot in enumerate(slots):
        eighth = slot // 2 if sixteenths else slot
        strong = eighth % ctx.epb in ctx.strong and (not sixteenths or slot % 2 == 0)
        if strong:
            line[index] = ctx.melody[eighth]
    if sixteenths:
        start16, end16 = slots[0], slots[-1] + 1
        fresh = []
        for slot, pitch in zip(slots, line):
            fresh.extend(_spell16(slot, 1, pitch, ctx.epb, 1, _MELODY_APEX if slot == slots[-1] else _MELODY))
    else:
        start16, end16 = slots[0] * 2, slots[-1] * 2 + 2
        fresh = []
        for slot, pitch in zip(slots, line):
            fresh.extend(_eighth_event(slot, 1, pitch, ctx.epb, 1, _MELODY_APEX if slot == target else _MELODY))
    lead = _splice(lead, start16, end16, fresh, ctx.epb)
    support = _drop_overlap(support, start16, end16, ctx.epb)
    bars = {slot // 2 // ctx.epb if sixteenths else slot // ctx.epb for slot in slots}
    if ctx.ensemble == "barrios":
        low = _pulse_bass(ctx, low, bars)
    return lead, support, low, bars


def _splice(events: list[NoteEvent], start: int, end: int, fresh: list[NoteEvent], epb: int) -> list[NoteEvent]:
    kept: list[NoteEvent] = []
    for event in events:
        if event.midi is None:
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if finish <= start or begin >= end:
            kept.append(event)
            continue
        if begin < start:
            kept.extend(_spell16(begin, start - begin, event.midi, epb, event.voice, event.velocity))
        if finish > end:
            kept.extend(_spell16(end, finish - end, event.midi, epb, event.voice, event.velocity))
    kept.extend(fresh)
    return kept


def _pulse_bass(ctx: _Ctx, low: list[NoteEvent], bars: set[int]) -> list[NoteEvent]:
    kept = [event for event in low if event.bar not in bars]
    points = (0, 3) if ctx.kind == "6/8" else (0, 4)
    span = 3 if ctx.kind == "6/8" else (4 if ctx.kind == "4/4" else 4)
    for bar in sorted(bars):
        root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * ctx.epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
        for offset in points:
            if offset < ctx.epb:
                length = min(span, ctx.epb - offset)
                kept.extend(_eighth_event(bar * ctx.epb + offset, length, root, ctx.epb, 3, _BASS))
    return kept


def _held_bars(ctx: _Ctx, phrase: Phrase) -> list[int]:
    found = []
    for bar in range(phrase.start // ctx.epb, (phrase.end - 1) // ctx.epb + 1):
        eighths = range(max(phrase.start, bar * ctx.epb), min(phrase.end, (bar + 1) * ctx.epb))
        pitches = [ctx.melody[eighth] for eighth in eighths]
        if pitches and len(set(pitches)) == 1 and len(pitches) == ctx.epb:
            found.append(bar)
    return found


def _perpetual_bars(ctx: _Ctx, phrase: Phrase, limit: int) -> list[int]:
    if ctx.ensemble != "barrios" or ctx.bpm < BARRIOS_TREMOLO_MIN_BPM or limit <= 0:
        return []
    apex_bar = min(ctx.bars - 1, phrase.apex.start // ctx.epb)
    if ctx.band(apex_bar) != "f" or ctx.mood(apex_bar) != "volatile":
        return []
    held = [bar for bar in _held_bars(ctx, phrase) if ctx.band(bar) == "f"]
    if not held:
        return []
    run = [held[0]]
    for bar in held[1:]:
        if bar == run[-1] + 1 and len(run) < 2:
            run.append(bar)
        else:
            break
    return run[:limit]


def _apply_perpetual(ctx: _Ctx, lead, support, low, bars: list[int]) -> tuple[list, list, list]:
    if not bars:
        return lead, support, low
    drop = set(bars)
    lead = [event for event in lead if event.bar not in drop]
    support = [event for event in support if event.bar not in drop]
    low = _pulse_bass(ctx, [event for event in low if event.bar not in drop], drop)
    for bar in bars:
        start = bar * ctx.epb
        held = ctx.melody[start]
        beats = ctx.epb // 2
        for beat in range(beats):
            direction = 1 if beat % 2 == 0 else -1
            step = _walk(held, direction, ctx.mode, ctx.treble_floor, ctx.treble_top)
            moving = _walk(held, 2 * direction, ctx.mode, ctx.treble_floor, ctx.treble_top)
            if moving == held:
                moving = _walk(held, -direction, ctx.mode, ctx.treble_floor, ctx.treble_top)
            if step == held:
                step = moving
            pitches = [held, step, moving, held]
            origin = (start + beat * 2) * 2
            for offset, pitch in enumerate(pitches):
                lead.extend(_spell16(origin + offset, 1, pitch, ctx.epb, 1, _MELODY))
    return lead, support, low


def _allocate_overlays(ctx: _Ctx, patterns: list[str], levels: dict[int, int]) -> tuple[dict[int, tuple], dict[int, list[int]]]:
    """Return phrase → scale plan, and phrase → perpetual bars."""
    by_section: dict[tuple, list[int]] = {}
    for index, phrase in enumerate(ctx.phrases):
        if patterns[index] in {"pedal"}:
            continue
        bar = phrase.start // ctx.epb
        if ctx.kind_at.get(bar, "phrase") in _PEDAL:
            continue
        section = ctx.section(bar)
        key = (0, ctx.bars) if section is None else (section.start, section.end)
        by_section.setdefault(key, []).append(index)
    scale_plans: dict[int, tuple] = {}
    perpetual: dict[int, list[int]] = {}
    for (begin, end), indexes in by_section.items():
        limit = int((end - begin) * 0.15 + 1e-9)
        if len(indexes) < 2 or limit <= 0:
            continue
        ranked: list[tuple[int, int, str]] = []
        for index in indexes:
            phrase = ctx.phrases[index]
            if patterns[index] == "tremolo":
                bars = _perpetual_bars(ctx, phrase, min(2, limit))
                if bars:
                    ranked.append((0, index, "perpetual"))
                    continue
            rise = _peak(ctx.melody, phrase) - min(ctx.melody[phrase.start : phrase.end])
            band = ctx.band(phrase.apex.start // ctx.epb)
            mood = ctx.mood(phrase.apex.start // ctx.epb)
            if levels.get(index, -1) == 2 and rise >= MIN_RISE and band in {"mf", "f"}:
                if _target_eighth(ctx, phrase, True) is not None:
                    ranked.append((1, index, "ascent"))
                    continue
            # Sor runs only as Grand Solo level 2. Villa needs a volatile forte
            # breakout. Barrios runs on a real rise at mf/f, or a descending close.
            if (
                ctx.ensemble == "villa"
                and mood == "volatile"
                and band == "f"
                and rise >= MIN_RISE
                and _target_eighth(ctx, phrase, True) is not None
            ):
                ranked.append((2, index, "ascent"))
            elif (
                ctx.ensemble == "barrios"
                and rise >= MIN_RISE
                and band in {"mf", "f"}
                and _target_eighth(ctx, phrase, True) is not None
            ):
                ranked.append((2, index, "ascent"))
            elif ctx.ensemble == "barrios" and phrase.closes and _target_eighth(ctx, phrase, False) is not None:
                ranked.append((3, index, "descent"))
        ranked.sort()
        used_bars = 0
        used_phrases: set[int] = set()
        for _priority, index, kind in ranked:
            if len(used_phrases) >= len(indexes) - 1:
                break
            if kind == "perpetual":
                bars = _perpetual_bars(ctx, ctx.phrases[index], min(2, limit - used_bars))
                if not bars:
                    continue
                perpetual[index] = bars
                used_bars += len(bars)
                used_phrases.add(index)
                continue
            ascent = kind == "ascent"
            target = _target_eighth(ctx, ctx.phrases[index], ascent)
            if target is None:
                continue
            slots = _run_slots(target, ctx.epb, ctx.strong, ctx.bpm >= 90, ctx.phrases[index])
            touched = {(slot // 2 if ctx.bpm >= 90 else slot) // ctx.epb for slot in slots}
            if not touched or used_bars + len(touched) > limit:
                continue
            scale_plans[index] = (target, ascent, ctx.ensemble == "barrios")
            used_bars += len(touched)
            used_phrases.add(index)
    return scale_plans, perpetual


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


def _resolve(events: list[NoteEvent], epb: int, voice: int) -> list[NoteEvent]:
    timed = []
    for event in events:
        if event.midi is None:
            continue
        timed.append((_start16(event, epb), _dur16(event), replace(event, voice=voice, slur_start=False, slur_stop=False)))
    timed.sort(key=lambda item: (item[0], -item[1]))
    groups: list[list[tuple[int, int, NoteEvent]]] = []
    for start, dur, event in timed:
        if groups and groups[-1][0][0] == start:
            groups[-1].append((start, dur, event))
        else:
            groups.append([(start, dur, event)])
    resolved: list[NoteEvent] = []
    for index, group in enumerate(groups):
        nxt = groups[index + 1][0][0] if index + 1 < len(groups) else None
        for start, dur, event in group:
            if nxt is not None and start + dur > nxt:
                dur = nxt - start
            if dur <= 0:
                continue
            resolved.extend(
                _spell16(
                    start,
                    dur,
                    event.midi,
                    epb,
                    voice,
                    event.velocity,
                    event.accent,
                    tie_in=event.tie_stop,
                    tie_out=event.tie_start,
                )
            )
    return resolved


def _fill(events: list[NoteEvent], bars: int, epb: int, voice: int) -> list[NoteEvent]:
    total = bars * epb * 2
    timed = sorted(
        ((_start16(event, epb), _dur16(event), index, event) for index, event in enumerate(events)),
        key=lambda item: (item[0], -item[1], item[2]),
    )
    output: list[NoteEvent] = []
    cursor = 0
    index = 0
    while cursor < total:
        if index < len(timed) and timed[index][0] < cursor:
            index += 1
            continue
        if index < len(timed) and timed[index][0] == cursor:
            start = timed[index][0]
            group = []
            while index < len(timed) and timed[index][0] == start:
                group.append(timed[index])
                index += 1
            for _start, dur, _order, event in group:
                output.append(event)
            cursor = max(item[0] + item[1] for item in group)
            continue
        nxt = timed[index][0] if index < len(timed) else total
        if nxt > cursor:
            output.extend(_spell16(cursor, nxt - cursor, None, epb, voice))
        cursor = nxt
    return output


def _needs_sixteenths(events: list[NoteEvent]) -> bool:
    for event in events:
        start = event.beat * 4
        dur = event.duration_beats * 4
        if abs(start - round(start)) > 1e-6 or abs(dur - round(dur)) > 1e-6:
            return True
        if int(round(start)) % 2 or int(round(dur)) % 2:
            return True
    return False


def _repair(ctx: _Ctx, lead: list[NoteEvent], support: list[NoteEvent], low: list[NoteEvent]) -> tuple[list, list, list]:
    """Shift or drop an inner note that cannot share a hand position with the melody."""
    repaired: list[NoteEvent] = []
    for event in support:
        if event.midi is None:
            continue
        when = _start16(event, ctx.epb)
        sounding = [event.midi]
        for other in (*lead, *low):
            if other.midi is None:
                continue
            begin = _start16(other, ctx.epb)
            if begin <= when < begin + _dur16(other):
                sounding.append(other.midi)
        pitches = [note + ctx.semitones for note in sounding]
        if _playable(pitches) and _ordered(sounding, event, lead, low, ctx):
            repaired.append(event)
            continue
        bass = _sounding_midi(low, when // 2, ctx.epb) or ctx.bass_low
        sung = _sounding_midi(lead, when // 2, ctx.epb) or ctx.treble_top
        tone = _choose_inner(ctx.chord(event.bar), sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False, 0)
        if tone is not None and tone != event.midi:
            repaired.append(replace(event, midi=tone))
    return lead, repaired, low


def _ordered(support_and_more: list[int], event: NoteEvent, lead, low, ctx: _Ctx) -> bool:
    when = _start16(event, ctx.epb)
    bass = [note.midi for note in low if note.midi is not None and _covers(note, when, ctx.epb)]
    highs = [note.midi for note in lead if note.midi is not None and _covers(note, when, ctx.epb)]
    if bass and event.midi is not None and max(bass) >= event.midi:
        return False
    if highs and event.midi is not None and event.midi >= min(highs):
        return False
    return True


def _covers(event: NoteEvent, when: int, epb: int) -> bool:
    begin = _start16(event, epb)
    return begin <= when < begin + _dur16(event)


def _tremolo_boost(ctx: _Ctx, bar: int) -> int:
    """Later bars of a rising tremolo breathe. The first bar stays locked."""
    phrase = _phrase_at(ctx, bar * ctx.epb)
    if phrase is None or not _rises(phrase) or phrase.end - phrase.start < ctx.epb * 2:
        return 0
    if bar <= phrase.start // ctx.epb:
        return 0
    eighth = min(phrase.end - 1, bar * ctx.epb + ctx.epb // 2)
    amount = swell(phrase, eighth)
    if amount < 0.5:
        return 0
    return 4 if amount >= 0.85 else 2


def _boost(events: list[NoteEvent], amount: int) -> list[NoteEvent]:
    if amount <= 0:
        return list(events)
    boosted: list[NoteEvent] = []
    for event in events:
        if event.velocity is None:
            boosted.append(event)
        else:
            boosted.append(replace(event, velocity=event.velocity + amount))
    return boosted


def render_patterned_voices(
    *,
    melody: list[int],
    raw_pitches: list[int],
    phrases: tuple[Phrase, ...],
    chord_at: dict[int, Chord],
    kind_at: dict[int, str],
    band_at: dict[int, str],
    musical_bars: int,
    total_eighths: int,
    bpm: int,
    ensemble: str,
    mode: str,
    character,
    character_at,
    sections,
    rel_span: float,
    register,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], int]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    need = musical_bars * epb
    if len(melody) < need:
        pad = melody[-1] if melody else 64
        melody = [*melody, *([pad] * (need - len(melody)))]
    if len(raw_pitches) < need:
        pad = raw_pitches[-1] if raw_pitches else melody[0]
        raw_pitches = [*raw_pitches, *([pad] * (need - len(raw_pitches)))]
    ctx = _Ctx(
        melody=list(melody),
        raw=list(raw_pitches),
        chord_at=dict(chord_at),
        kind_at=dict(kind_at),
        band_at=dict(band_at),
        phrases=phrases,
        bars=musical_bars,
        bpm=bpm,
        ensemble=ensemble,
        mode=mode,
        character=character,
        character_at=character_at,
        sections=tuple(sections or ()),
        rel_span=rel_span,
        semitones=40 - register.guitar_floor,
        bass_low=register.guitar_floor,
        bass_high=register.guitar_bass_top,
        mid_low=register.guitar_mid_low,
        mid_high=register.guitar_mid_high,
        treble_floor=register.guitar_treble_floor,
        treble_top=register.guitar_treble_top,
        ceiling=register.guitar_ceiling,
        epb=epb,
        kind=_meter_kind(meter),
        strong=tuple(meter.strong_eighths),
        bar_beats=meter.quarter_beats,
    )
    patterns = _patterns(ctx) if phrases else []
    levels = _grand_levels(ctx, patterns)
    plans, perpetual = _allocate_overlays(ctx, patterns, levels)
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    apex = _apex_eighths(phrases)
    tremolo_bars = {bar for bar in range(musical_bars) if _bar_pattern(ctx, bar, patterns) == "tremolo"}
    if tremolo_bars:
        trem_lead, trem_inner, trem_bass = _tremolo(
            ctx.melody,
            ctx.chord_at,
            {bar: "phrase" for bar in range(musical_bars)},
            musical_bars,
            bpm,
            ctx.bass_low,
            ctx.bass_high,
            ctx.mid_low,
            ctx.mid_high,
            phrases,
        )
    else:
        trem_lead, trem_inner, trem_bass = (), (), ()
    rendered: set[int] = set()
    for index, phrase in enumerate(phrases):
        pattern = patterns[index] if index < len(patterns) else "study"
        if pattern in {"cantabile"}:
            part_lead, part_support, part_low = _render_cantabile(ctx, phrase)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
            rendered.update(range(phrase.start // epb, (phrase.end - 1) // epb + 1))
        elif pattern == "thumb_cantabile":
            part_lead, part_support, part_low = _render_thumb(ctx, phrase)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
            rendered.update(range(phrase.start // epb, (phrase.end - 1) // epb + 1))
    attacks_by_phrase = {
        index: _lead_attacks(ctx.melody, phrase.start, phrase.end) for index, phrase in enumerate(phrases)
    }
    ornaments = {
        index: _phrase_appoggiatura(ctx, phrase)
        for index, phrase in enumerate(phrases)
        if patterns[index] == "elegiaque"
    }
    for bar in range(musical_bars):
        if bar in rendered:
            continue
        pattern = _bar_pattern(ctx, bar, patterns)
        owner = _owner(ctx, bar)
        attacks = attacks_by_phrase.get(owner, set()) if owner is not None else set()
        allow_approach = _allow_approach(ctx, bar, patterns)
        phrase_here = phrases[owner] if owner is not None else _phrase_at(ctx, bar * epb)
        if pattern == "tremolo" and bar in tremolo_bars:
            boost = _tremolo_boost(ctx, bar)
            lead.extend(_boost([event for event in trem_lead if event.bar == bar and event.midi is not None], boost))
            support.extend(_boost([event for event in trem_inner if event.bar == bar and event.midi is not None], boost))
            low.extend(_boost([event for event in trem_bass if event.bar == bar and event.midi is not None], boost))
        elif pattern == "pedal":
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
            low.extend(_eighth_event(bar * epb, epb, root, epb, 3, _BASS))
        elif pattern == "preludio":
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            support.extend(_preludio_inner(ctx, bar, patterns))
        elif pattern == "study":
            level = levels.get(owner, 0) if owner is not None else 0
            part_support, part_low = _render_study_bar(ctx, bar, level, False)
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "villa_pattern":
            part_support, part_low = _render_villa_bar(ctx, bar, allow_approach)
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "andante":
            phrase = phrase_here
            points, spans = _andante_grid(ctx, bar, phrase)
            part_support, part_low = _render_block_bar(ctx, bar, points, spans, inner="chord", phrase=phrase)
            lead.extend(
                _sustain(
                    ctx.melody,
                    bar * epb,
                    (bar + 1) * epb,
                    epb,
                    apex,
                    {bar * epb + point for point in points},
                    phrase,
                )
            )
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "chord_melody":
            phrase = phrase_here
            points, spans = _chord_grid(ctx, bar, phrase)
            part_support, part_low = _render_block_bar(ctx, bar, points, spans, inner="color", phrase=phrase)
            lead.extend(
                _sustain(
                    ctx.melody,
                    bar * epb,
                    (bar + 1) * epb,
                    epb,
                    apex,
                    {bar * epb + point for point in points},
                    phrase,
                )
            )
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "elegiaque":
            phrase = phrase_here
            # The short bass of the dotted group always steps down one scale degree.
            descend = True
            part_support, part_low = _render_elegiaque_bar(ctx, bar, phrase, descend)
            part_lead = _sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase)
            if owner is not None and owner in ornaments and any(
                bar * epb <= eighth < (bar + 1) * epb for eighth in ornaments[owner]
            ):
                part_lead = _apply_appoggiatura(ctx, part_lead, ornaments[owner])
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "vals":
            part_lead, part_support, part_low = _render_vals_bar(ctx, bar, patterns, apex)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "hemiola":
            part_lead, part_support, part_low = _render_hemiola_bar(ctx, bar, patterns, apex)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "polca":
            part_lead, part_support, part_low = _render_polca_bar(ctx, bar, patterns, apex)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "choro":
            part_lead, part_support, part_low = _render_choro_bar(ctx, bar, patterns, apex)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        else:
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
    # Preludio bass rings for two bars, counted from each contiguous region.
    low.extend(_preludio_bass(ctx, patterns))
    villa_bars = {
        bar for bar in range(musical_bars) if _bar_pattern(ctx, bar, patterns) == "villa_pattern"
    }
    if villa_bars:
        support = _apply_campanella(ctx, support, lead, villa_bars)
    for index, phrase in enumerate(phrases):
        following = None
        for later in range(index + 1, len(patterns)):
            start_bar = phrases[later].start // epb
            if ctx.kind_at.get(start_bar, "phrase") in _PEDAL:
                continue
            following = patterns[later]
            break
        if (
            patterns[index] == "tremolo"
            and index not in perpetual
            and phrase.end - phrase.start >= 8
            and following is not None
            and (phrase.closes or following != "tremolo")
        ):
            lead, support, low = _taper(ctx, lead, support, low, phrase)
    bell_bars = {
        bar
        for bar in range(musical_bars)
        if ctx.kind_at.get(bar, "phrase") in {"intro", "warmup"}
        or (_bar_pattern(ctx, bar, patterns) == "preludio" and _bells_here(ctx, bar, patterns))
    }
    lead, support = _insert_bells(ctx, lead, support, bell_bars)
    for index, (target, ascent, chromatic) in plans.items():
        lead, support, low, _bars = _apply_scale_run(
            ctx, lead, support, low, phrases[index], target, ascent, chromatic
        )
    for index, bars in perpetual.items():
        lead, support, low = _apply_perpetual(ctx, lead, support, low, bars)
    for bar in _fanfare_bars(ctx, levels):
        lead, support, low = _apply_fanfare(ctx, lead, support, low, bar)
    lead, support, low = _transitions(ctx, patterns, levels, lead, support, low)
    for eighth in _caesura_eighths(ctx, levels):
        lead = _silence(lead, eighth, epb)
        support = _silence(support, eighth, epb)
        low = _silence(low, eighth, epb)
    lead, support, low = _repair(ctx, lead, support, low)
    lead = _resolve(lead, epb, 1)
    support = _resolve(support, epb, 2)
    low = _resolve(low, epb, 3)
    lead = _slur(lead, phrases)
    divisions = 4 if _needs_sixteenths([*lead, *support, *low]) else 2
    # Phase 2 engraves every fast Barrios movement on the sixteenth grid once a
    # character is set, even when the line itself stays in eighths.
    if (
        divisions == 2
        and ctx.ensemble == "barrios"
        and ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM
        and ctx.character is not None
    ):
        divisions = 4
    return (
        _fill(lead, musical_bars, epb, 1),
        _fill(support, musical_bars, epb, 2),
        _fill(low, musical_bars, epb, 3),
        divisions,
    )


def _owner(ctx: _Ctx, bar: int) -> int | None:
    eighth = bar * ctx.epb
    for index, phrase in enumerate(ctx.phrases):
        if phrase.start <= eighth < phrase.end:
            return index
    return None


def _allow_approach(ctx: _Ctx, bar: int, patterns: list[str]) -> bool:
    if bar + 1 >= ctx.bars:
        return False
    owner = _owner(ctx, bar)
    nxt = _owner(ctx, bar + 1)
    if owner is None:
        return False
    if nxt is not None and nxt != owner and _FAMILY.get(patterns[nxt], "") != "dance":
        if patterns[owner] in _DANCE:
            return False
    if patterns[owner] in _DANCE and nxt is not None and patterns[nxt] not in _DANCE:
        return False
    if not _same_phrase(ctx, bar, bar + 1) and patterns[owner] in _DANCE:
        return False
    return True


def _bells_here(ctx: _Ctx, bar: int, patterns: list[str]) -> bool:
    kind = ctx.kind_at.get(bar, "phrase")
    if kind in {"intro", "warmup"}:
        return True
    first = None
    for index, phrase in enumerate(ctx.phrases):
        start_bar = phrase.start // ctx.epb
        if ctx.kind_at.get(start_bar, "phrase") in _PEDAL:
            continue
        first = index
        break
    owner = _owner(ctx, bar)
    return owner is not None and owner == first and patterns[owner] == "preludio"


def _preludio_anchor(ctx: _Ctx, bar: int, patterns: list[str]) -> int:
    """The bar whose pedal attack rings under this preludio bar."""
    region = bar
    while region > 0 and _bar_pattern(ctx, region - 1, patterns) == "preludio":
        region -= 1
    end = bar
    while end + 1 < ctx.bars and _bar_pattern(ctx, end + 1, patterns) == "preludio":
        end += 1
    if end == region:
        return bar
    anchor = region + ((bar - region) // 2) * 2
    if anchor + 1 > end:
        return bar
    return anchor


def _preludio_inner(ctx: _Ctx, bar: int, patterns: list[str]) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    anchor = _preludio_anchor(ctx, bar, patterns)
    anchor_lead = _covering_melody_velocity(ctx, anchor * ctx.epb)
    _support_vel, bass_vel = _under_lead(anchor_lead, ctx.band(anchor))
    strong = set(ctx.strong)
    midpoints = {ctx.epb // 2}
    if ctx.epb >= 4:
        midpoints |= {ctx.epb // 4, (3 * ctx.epb) // 4}
    previous: int | None = None
    for offset in range(ctx.epb):
        sung = _melody_at(ctx, start + offset)
        bass_guess = _choose_bass(chord, 0, sung, ctx.bass_low, ctx.bass_high, ctx.semitones)
        tones = _inner_choices(chord, sung, bass_guess, ctx.mid_low, ctx.mid_high, ctx.semitones, False)
        if tones:
            tone = _contour_tone(chord, tones, offset, previous)
        else:
            tone = _choose_inner(chord, sung, bass_guess, ctx.mid_low, ctx.mid_high, ctx.semitones, False, offset)
        if tone is None:
            continue
        previous = tone
        lead_vel = _covering_melody_velocity(ctx, start + offset)
        support_vel, _bass = _under_lead(lead_vel, ctx.band(bar))
        if offset not in strong and offset not in midpoints:
            support_vel = max(40, support_vel - 4)
        support_vel = min(support_vel, bass_vel - 2, lead_vel - 4)
        events.extend(_eighth_event(start + offset, 1, tone, ctx.epb, 2, max(40, support_vel)))
    return events


def _preludio_bass(ctx: _Ctx, patterns: list[str]) -> list[NoteEvent]:
    bars = [bar for bar in range(ctx.bars) if _bar_pattern(ctx, bar, patterns) == "preludio"]
    events: list[NoteEvent] = []
    index = 0
    while index < len(bars):
        run = [bars[index]]
        while index + 1 < len(bars) and bars[index + 1] == run[-1] + 1:
            index += 1
            run.append(bars[index])
        index += 1
        cursor = 0
        while cursor < len(run):
            span = 2 if cursor + 1 < len(run) else 1
            # A one-bar section rings for one bar; a longer region pairs bars.
            if len(run) == 1:
                span = 1
            bar = run[cursor]
            root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * ctx.epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
            _support_vel, bass_vel = _under_lead(_covering_melody_velocity(ctx, bar * ctx.epb), ctx.band(bar))
            if span == 1:
                # A one-bar opening keeps the strong-beat arpeggio, not a whole-note pedal.
                strong = [offset for offset in ctx.strong if offset < ctx.epb] or [0]
                bounds = [*strong, ctx.epb]
                for left, right in zip(bounds, bounds[1:]):
                    if right > left:
                        events.extend(_eighth_event(bar * ctx.epb + left, right - left, root, ctx.epb, 3, bass_vel))
            else:
                length = span * ctx.epb
                events.extend(_eighth_event(bar * ctx.epb, length, root, ctx.epb, 3, bass_vel))
            cursor += span
    return events


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


def _transitions(ctx, patterns, levels, lead, support, low):
    body = [
        index
        for index, phrase in enumerate(ctx.phrases)
        if ctx.kind_at.get(phrase.start // ctx.epb, "phrase") not in _PEDAL
    ]
    for left, right in zip(body, body[1:]):
        if patterns[left] == patterns[right]:
            continue
        phrase = ctx.phrases[left]
        if phrase.end - phrase.start < 1:
            continue
        eighth = phrase.end - 1
        runs = _runs(ctx.melody, phrase.start, phrase.end)
        held_ending = bool(runs) and runs[-1][1] >= 2
        running_ending = bool(runs) and all(length < 4 for _s, length, _m in runs)
        different_family = _FAMILY.get(patterns[left]) != _FAMILY.get(patterns[right])
        if held_ending or (running_ending and different_family and phrase.end - phrase.start >= 4):
            lead = _silence(lead, eighth, ctx.epb)
            support = _silence(support, eighth, ctx.epb)
        high = patterns[right] in {"tremolo", *_DANCE} or (
            patterns[right] == "study" and right in levels
        )
        if patterns[left] in _CHORALE and high and eighth not in _caesura_eighths(ctx, levels):
            low = _silence(low, eighth, ctx.epb)
            target = ctx.chord(ctx.phrases[right].start // ctx.epb)
            root = _choose_bass(target, 0, _melody_at(ctx, ctx.phrases[right].start), ctx.bass_low, ctx.bass_high, ctx.semitones)
            pickup = _step_below(root, ctx.mode, ctx.bass_low) or _choose_bass(target, 2, root, ctx.bass_low, ctx.bass_high, ctx.semitones)
            low.extend(_eighth_event(eighth, 1, pickup, ctx.epb, 3, _INNER))
        if patterns[left] in _DANCE and patterns[right] not in _DANCE:
            low = _drop_approach(low, phrase, ctx)
    return lead, support, low


def _taper(ctx, lead, support, low, phrase: Phrase):
    """Last four eighths become an arpeggio: one root, and it rings through the breath."""
    start = max(phrase.start, phrase.end - 4)
    lead = _drop_overlap(lead, start * 2, phrase.end * 2, ctx.epb)
    support = _drop_overlap(support, start * 2, phrase.end * 2, ctx.epb)
    low = _drop_overlap(low, start * 2, phrase.end * 2, ctx.epb)
    lead.extend(_sustain(ctx.melody, start, phrase.end, ctx.epb, _apex_eighths((phrase,)), phrase=phrase))
    eighth = start
    while eighth < phrase.end:
        anchor = eighth % ctx.epb in ctx.strong or eighth == start
        if not anchor:
            eighth += 1
            continue
        nxt = eighth + 1
        while nxt < phrase.end and nxt % ctx.epb not in ctx.strong:
            nxt += 1
        root = _clamp(ctx.chord(eighth // ctx.epb).pitches[0], ctx.bass_low, ctx.bass_high)
        low.extend(_eighth_event(eighth, nxt - eighth, root, ctx.epb, 3, _BASS))
        pool = _pool(ctx.chord(eighth // ctx.epb))
        for inner in range(eighth + 1, nxt):
            if inner % ctx.epb in ctx.strong:
                continue
            sung = ctx.melody[inner]
            tone = _fit(pool[inner % len(pool)], ctx.mid_low, ctx.mid_high)
            while tone >= sung and tone - 12 >= ctx.mid_low:
                tone -= 12
            if tone >= sung or tone <= root:
                continue
            support.extend(_eighth_event(inner, 1, tone, ctx.epb, 2, _INNER))
        eighth = nxt
    return lead, support, low


def _drop_approach(low: list[NoteEvent], phrase: Phrase, ctx: _Ctx) -> list[NoteEvent]:
    end_bar = (phrase.end - 1) // ctx.epb
    last = (end_bar + 1) * ctx.bar_beats - 0.25
    return [event for event in low if not (event.bar == end_bar and abs(event.beat - last) < 1e-6)]


def _profile_at(score: Score, profiles) -> dict[int, str]:
    if isinstance(profiles, str):
        return {bar: profiles for bar in range(score.bars)}
    if isinstance(profiles, dict):
        return {bar: profiles.get(bar, "study") for bar in range(score.bars)}
    return {bar: profiles[bar] for bar in range(score.bars)}


def _chords(score: Score) -> dict[int, Chord]:
    found: dict[int, Chord] = {}
    for slot in score.slots:
        for bar in slot.bars():
            found[bar] = slot.chord
    return found


def _is_approach(event: NoteEvent, score: Score, semitones: int, chords: dict[int, Chord]) -> bool:
    if event.midi is None or event.voice != 3 or event.duration_beats > 0.5 + 1e-6:
        return False
    end = event.beat + event.duration_beats
    if abs(end - score.bar_beats) > 1e-6:
        return False
    nxt = chords.get(event.bar + 1)
    if nxt is None:
        return False
    return (event.midi + semitones) % 12 == (nxt.pitches[0] - 1) % 12


def _is_lament(event: NoteEvent, previous: NoteEvent | None) -> bool:
    if event.midi is None or previous is None or previous.midi is None:
        return False
    if event.duration_beats > 0.5 + 1e-6 or previous.duration_beats < 1.0 - 1e-6:
        return False
    return previous.midi - event.midi in {1, 2}


def assert_playable(score: Score, key: KeySpec = C_KEY, profiles: str | dict | tuple | list = "study") -> None:
    """Raise `Unplayable` when a score breaks register, hand, or profile rules."""
    semitones = key.semitones
    profile_at = _profile_at(score, profiles)
    epb = int(round(score.bar_beats * 2))
    chords = _chords(score)
    voices = {
        1: [replace(event, voice=1) for event in score.lead],
        2: [replace(event, voice=2) for event in score.support],
        3: [replace(event, voice=3) for event in score.low],
    }
    previous_bass: NoteEvent | None = None
    bass_events = sorted(
        (event for event in voices[3] if event.midi is not None),
        key=lambda event: (event.bar, event.beat),
    )
    for event in bass_events:
        profile = profile_at.get(event.bar, "study")
        sounding = event.midi + semitones
        approach = _is_approach(event, score, semitones, chords)
        lament = _is_lament(event, previous_bass)
        if sounding < 40 or sounding > 83:
            raise Unplayable(f"bass {sounding} is outside the guitar")
        if sounding > 53 and not (profile == "thumb_cantabile" and sounding <= 64):
            raise Unplayable(f"profile {profile} rejects bass melody {sounding}")
        if profile in {"study", "grand"} and (approach or lament):
            raise Unplayable(f"profile {profile} rejects {'approach' if approach else 'lament'} bass")
        if profile == "elegiaque" and approach and not lament:
            raise Unplayable("elegiaque rejects a chromatic approach")
        if profile not in {"villa_pattern", "barrios_dance", "elegiaque", "grand", "study"} and approach:
            raise Unplayable(f"profile {profile} rejects a chromatic approach")
        if profile == "villa_pattern" and lament and not approach:
            raise Unplayable("villa pattern rejects an elegiaque lament")
        previous_bass = event
    for voice, events in voices.items():
        for event in events:
            if event.midi is None:
                continue
            profile = profile_at.get(event.bar, "study")
            sounding = event.midi + semitones
            if voice == 1:
                ceiling = 83 if profile == "barrios_preludio" else 81
                if sounding > ceiling or sounding < 59:
                    raise Unplayable(f"lead {sounding} is outside profile {profile}")
            if voice == 2 and sounding < 50:
                raise Unplayable(f"inner voice {sounding} is below the middle register")
    times: set[int] = set()
    for events in voices.values():
        for event in events:
            if event.midi is not None:
                times.add(_start16(event, epb))
    for when in sorted(times):
        bar = when // (epb * 2)
        profile = profile_at.get(bar, "study")
        sounding_notes: list[tuple[int, int]] = []
        for voice, events in voices.items():
            for event in events:
                if event.midi is not None and _covers(event, when, epb):
                    sounding_notes.append((voice, event.midi + semitones))
        if not sounding_notes:
            continue
        lows = [pitch for voice, pitch in sounding_notes if voice == 3]
        mids = [pitch for voice, pitch in sounding_notes if voice == 2]
        highs = [pitch for voice, pitch in sounding_notes if voice == 1]
        if len(highs) > 1:
            raise Unplayable("two notes in the high voice")
        if len(mids) > 1:
            raise Unplayable("too many notes in one voice")
        if len(lows) > 1 and profile != "barrios_tremolo":
            raise Unplayable("two bass notes are the tremolo exception")
        if len(sounding_notes) > 4 or (len(sounding_notes) > 3 and profile != "barrios_tremolo"):
            raise Unplayable("too many simultaneous pitches")
        if lows and mids and max(lows) >= min(mids):
            tremolo_ok = profile == "barrios_tremolo" and min(lows) < min(mids) and max(lows) <= 53
            if not tremolo_ok:
                raise Unplayable("bass is not below the inner voice")
        if mids and highs and max(mids) >= min(highs):
            raise Unplayable("inner voice is not below the melody")
        if lows and highs and not mids and max(lows) >= min(highs):
            raise Unplayable("bass is not below the melody")
        for voice, pitch in sounding_notes:
            if voice == 2 and pitch > 65:
                high_block = bool(highs) and min(highs) >= 80 and pitch < min(highs)
                thumb = profile == "thumb_cantabile" and (not lows or pitch > max(lows)) and (not highs or pitch < min(highs))
                if not high_block and not thumb:
                    raise Unplayable(f"inner voice {pitch} is above the middle register")
        if not _playable([pitch for _voice, pitch in sounding_notes]):
            raise Unplayable("no string assignment fits this sonority")
    _assert_scale_positions(voices[1], epb)


def _assert_scale_positions(lead: list[NoteEvent], epb: int) -> None:
    grouped: dict[int, list[int]] = {}
    for event in lead:
        if event.midi is None or event.duration_beats > 0.25 + 1e-6:
            continue
        grouped.setdefault(_start16(event, epb) // 4, []).append(event.midi)
    for pitches in grouped.values():
        ordered = sorted(set(pitches))
        if len(ordered) < 2:
            continue
        if any(abs(left - right) > 4 for left, right in zip(ordered, ordered[1:])):
            continue
        if not _position_ok(ordered):
            raise Unplayable("a scale group does not fit one hand position")
