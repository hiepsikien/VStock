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
_ARPEGGIO = frozenset({"study", "villa_pattern", "preludio", "galop", "mozart_var"})
_FAMILY = {
    "study": "arpeggio",
    "villa_pattern": "arpeggio",
    "preludio": "arpeggio",
    "galop": "arpeggio",
    "mozart_var": "arpeggio",
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
    "noviembre": "brouwer",
    "brouwer_etude": "brouwer",
    "elogio_pizz": "brouwer",
    "sarabande": "brouwer",
    "bach_fuga": "bach",
    "bach_bourree": "bach",
    "bach_gavotte": "bach",
    "bach_sarabande": "bach",
    "bach_gigue": "bach",
    "bach_chaconne": "bach",
}
_PROFILE = {
    "study": "study",
    "galop": "study",
    "mozart_var": "study",
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
    "noviembre": "brouwer",
    "brouwer_etude": "brouwer",
    "elogio_pizz": "brouwer",
    "sarabande": "brouwer",
    "bach_fuga": "bach",
    "bach_bourree": "bach",
    "bach_gavotte": "bach",
    "bach_sarabande": "bach",
    "bach_gigue": "bach",
    "bach_chaconne": "bach",
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
    if ctx.ensemble == "brouwer":
        primary = _brouwer_primary(ctx, mood)
        if trio or bridge:
            return _brouwer_contrast(primary)
        return primary
    if ctx.ensemble == "bach":
        bar = min(ctx.bars - 1, phrase.apex.start // ctx.epb)
        primary = _bach_primary(ctx, [phrase], [bar], mood)
        if trio or bridge:
            return _bach_contrast(ctx, primary, mood)
        return primary
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
    return {"classic": "study", "villa": "villa_pattern", "brouwer": "brouwer_etude", "bach": "bach_bourree"}.get(
        ctx.ensemble, "preludio"
    )


def _brouwer_primary(ctx: _Ctx, mood: str | None) -> str:
    """One Brouwer texture for a phrase, a section, or a daily session."""
    if mood == "calm":
        return "noviembre"
    if mood == "selloff" or ctx.bpm <= 72:
        return "sarabande"
    if mood == "volatile":
        return "elogio_pizz"
    return "brouwer_etude"


def _brouwer_contrast(primary: str) -> str:
    """The lyrical ballad answers the motor, and the motor answers the ballad."""
    if primary in {"noviembre", "sarabande"}:
        return "brouwer_etude"
    return "noviembre"


def _bach_primary(ctx: _Ctx, phrases: list[Phrase], bars: list[int], mood: str | None) -> str:
    """One Bach dance for a body, a section, or a single phrase."""
    if not bars and not phrases and mood is None and ctx.kind not in {"4/4", "3/4", "6/8"}:
        return "bach_bourree"
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
    if mood == "rally":
        if _is_suite_finale(ctx):
            return "bach_chaconne"
        return "bach_bourree"
    return "bach_bourree"


def _bach_contrast(ctx: _Ctx, primary: str, mood: str | None) -> str:
    """Trio and bridge: the other Baroque texture, then the dance returns."""
    if ctx.kind == "6/8" or primary == "bach_gigue":
        return "bach_bourree" if mood == "calm" else "bach_fuga"
    if ctx.kind == "3/4" or primary == "bach_sarabande":
        return "bach_chaconne"
    if primary in {"bach_bourree", "bach_gavotte"}:
        return "bach_fuga"
    if primary in {"bach_fuga", "bach_chaconne"}:
        return "bach_bourree" if mood == "rally" else "bach_gavotte"
    return "bach_bourree"


def _framed(ctx: _Ctx) -> bool:
    """A real movement carries intro or outro sections.

    Synthetic pattern tests pass a trio or a phrase and no pedal, and the
    one-bar pedal fixture passes kinds without sections. Both keep the
    per-phrase selector. `render` always sends the form's sections.
    """
    return any(getattr(section, "kind", None) in _PEDAL for section in ctx.sections)


def _catedral_preludio(ctx: _Ctx) -> bool:
    """Authentic *La Catedral* sixteenths, not the Phase 1 eighth-note arpeggio.

    Every real movement is framed (`1D`, `1W`, `1M`, `3M`, `1Y`). A score that
    already carries sections is the same texture. Empty-section fixtures keep
    the older flowing eighths.
    """
    return _framed(ctx) or bool(ctx.sections)


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
    if _framed(ctx):
        return _assign_macro(ctx, chosen, body)
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


def _body_bars(ctx: _Ctx) -> list[int]:
    return [bar for bar in range(ctx.bars) if ctx.kind_at.get(bar, "phrase") not in _PEDAL]


def _phrase_bars(ctx: _Ctx, indexes: list[int]) -> list[int]:
    found: list[int] = []
    for index in indexes:
        phrase = ctx.phrases[index]
        start = phrase.start // ctx.epb
        end = max(start + 1, (max(phrase.end, phrase.start + 1) - 1) // ctx.epb + 1)
        for bar in range(start, min(ctx.bars, end)):
            if ctx.kind_at.get(bar, "phrase") in _PEDAL or bar in found:
                continue
            found.append(bar)
    return found


def _majority_mood(ctx: _Ctx, bars: list[int]) -> str | None:
    counts: dict[str, int] = {}
    for bar in bars:
        mood = ctx.mood(bar)
        if mood is None:
            continue
        counts[mood] = counts.get(mood, 0) + 1
    if not counts:
        return ctx.character
    return max(counts, key=lambda key: (counts[key], key))


def _has_contrast_section(ctx: _Ctx) -> bool:
    return any(
        (getattr(section, "trio", False) or getattr(section, "bridge", False))
        and getattr(section, "kind", None) not in _PEDAL
        for section in ctx.sections
    )


def _raw_activity(ctx: _Ctx, bars: list[int]) -> float:
    """Fraction of eighths whose raw pitch changes. Holds after quantize do not count."""
    if not bars or not ctx.raw:
        return 0.0
    changes = 0
    total = 0
    for bar in bars:
        start = bar * ctx.epb
        end = min(len(ctx.raw), (bar + 1) * ctx.epb)
        for eighth in range(max(start, 1), end):
            total += 1
            if ctx.raw[eighth] != ctx.raw[eighth - 1]:
                changes += 1
    if total <= 0:
        return 0.0
    return changes / total


def _region_marked(ctx: _Ctx, bars: list[int], mood: str) -> bool:
    if not ctx.character_at or not bars:
        return False
    seen = 0
    hits = 0
    for bar in bars:
        if bar < len(ctx.character_at) and ctx.character_at[bar] is not None:
            seen += 1
            if ctx.character_at[bar] == mood:
                hits += 1
    return seen > 0 and hits * 2 >= seen


def _trailing_pedal_length(ctx: _Ctx) -> int:
    _leading, trailing = _pedal_regions(ctx)
    return len(trailing)


def _is_suite_finale(ctx: _Ctx) -> bool:
    """Movement IV closes on a long finale pedal."""
    return _trailing_pedal_length(ctx) >= 10


def _forte_majority(ctx: _Ctx, bars: list[int]) -> bool:
    if not bars:
        return False
    return sum(1 for bar in bars if ctx.band(bar) == "f") * 2 > len(bars)


def _classic_macro(ctx: _Ctx, mood: str | None, bars: list[int]) -> str:
    if mood == "selloff" or ctx.bpm <= 72:
        return "elegiaque"
    if mood == "calm":
        return "cantabile"
    if mood == "volatile":
        return "mozart_var"
    if mood == "rally":
        # `character is None` is the plain daily study. An explicit rally, a
        # per-bar rally, or an energetic span is Galop Op. 32 No. 6.
        if ctx.character is None and not _region_marked(ctx, bars, "rally"):
            return "study"
        if ctx.character == "rally" or _region_marked(ctx, bars, "rally") or ctx.rel_span >= 0.012:
            return "galop"
        return "study"
    return "study"


def _daily_barrios_pattern(ctx: _Ctx, mood: str | None, phrases: list[Phrase], bars: list[int]) -> str:
    """1D at 120 BPM. Moderate days sing Preludio; a flat synthetic line still tremolos."""
    activity = _raw_activity(ctx, bars)
    if mood == "volatile":
        return "choro" if activity >= 0.35 else "tremolo"
    if mood in {"rally", "selloff"}:
        if 0 < ctx.rel_span < 0.014 and activity >= 0.05:
            return "preludio"
        return "tremolo"
    holds = sum(1 for phrase in phrases if _has_hold(ctx.melody, phrase))
    if phrases and holds / len(phrases) >= 0.3:
        return "tremolo"
    return "preludio"


def _dominant_pattern(ctx: _Ctx, phrases: list[Phrase], bars: list[int]) -> str:
    """One pattern for a whole body, a formal section, or one weekly session."""
    mood = _majority_mood(ctx, bars)
    if ctx.ensemble == "brouwer":
        return _brouwer_primary(ctx, mood)
    if ctx.ensemble == "bach":
        return _bach_primary(ctx, phrases, bars, mood)
    if ctx.ensemble == "classic":
        return _classic_macro(ctx, mood, bars)
    if ctx.ensemble == "villa":
        # Slow 3/4 movements sing Étude No. 11. The bridge answers with the thumb.
        if ctx.bpm <= 72:
            return "chord_melody"
        quiet = sum(1 for bar in bars if ctx.band(bar) == "p")
        if mood == "calm" or (bars and quiet * 2 > len(bars)):
            return "chord_melody"
        return "villa_pattern"
    if ctx.bpm < BARRIOS_TREMOLO_MIN_BPM:
        return "preludio" if mood == "calm" else "andante"
    if mood == "calm":
        return "preludio"
    if _framed(ctx) and ctx.kind == "4/4" and 90 <= ctx.bpm <= 100:
        # Opening moderato (1M/3M I, 1W, 1Y opener) is La Catedral. The finale
        # pedal, or a volatile wide span at the same tempo, is Ultimo Tremolo.
        if _is_suite_finale(ctx) or (mood == "volatile" and ctx.rel_span >= 0.016):
            return "tremolo"
        return "preludio"
    if (
        _framed(ctx)
        and ctx.kind == "6/8"
        and ctx.bpm > 100
        and ctx.bars > 40
        and mood != "calm"
    ):
        return "hemiola" if _forte_majority(ctx, bars) else "polca"
    if ctx.bpm == 120 and ctx.bars == 34 and ctx.kind == "4/4":
        return _daily_barrios_pattern(ctx, mood, phrases, bars)
    holds = sum(1 for phrase in phrases if _has_hold(ctx.melody, phrase))
    running = sum(1 for phrase in phrases if _running(ctx.melody, phrase))
    if phrases and (
        holds / len(phrases) >= 0.3 or (mood in {"rally", "selloff"} and holds > 0)
    ):
        return "tremolo"
    if (
        ctx.bpm > 100
        and mood in {"rally", "volatile"}
        and phrases
        and running * 2 >= len(phrases)
    ):
        if ctx.kind == "6/8":
            return "polca"
        return "choro" if ctx.kind == "4/4" else "preludio"
    if holds:
        return "tremolo"
    return "preludio"


def _contrast_pattern(ctx: _Ctx, primary: str, phrases: list[Phrase], bars: list[int]) -> str:
    """The other formal area: one contrasting pattern, then the piece returns."""
    mood = _majority_mood(ctx, bars)
    if ctx.ensemble == "brouwer":
        return _brouwer_contrast(primary)
    if ctx.ensemble == "bach":
        return _bach_contrast(ctx, primary, mood)
    if ctx.ensemble == "classic":
        choice = "elegiaque" if ctx.mode == "minor" or mood == "selloff" else "cantabile"
        if choice != primary:
            return choice
        return "cantabile" if primary == "elegiaque" else "study"
    if ctx.ensemble == "villa":
        return "chord_melody" if primary == "thumb_cantabile" else "thumb_cantabile"
    if ctx.bpm < BARRIOS_TREMOLO_MIN_BPM:
        return "andante" if primary == "thumb_cantabile" else "thumb_cantabile"
    if (
        ctx.kind == "6/8"
        and ctx.bpm > 100
        and _framed(ctx)
        and ctx.bars > 40
        and mood != "calm"
        and primary in {"polca", "hemiola"}
    ):
        return "vals"
    running = sum(1 for phrase in phrases if _running(ctx.melody, phrase))
    if ctx.kind == "6/8" and phrases and running * 2 >= len(phrases):
        return "preludio" if primary == "vals" else "vals"
    return "andante" if primary == "thumb_cantabile" else "thumb_cantabile"


def _assign_macro(ctx: _Ctx, chosen: list[str], body: list[int]) -> list[str]:
    """Lock the body to one pattern, to A–B–A, or to one pattern per session."""
    if not body:
        return chosen
    if ctx.bars <= 40 and not _has_contrast_section(ctx):
        pattern = _dominant_pattern(ctx, [ctx.phrases[index] for index in body], _body_bars(ctx))
        for index in body:
            chosen[index] = pattern
        return chosen
    if _has_contrast_section(ctx):
        groups: dict[str, list[int]] = {"A": [], "B": []}
        for index in body:
            bar = min(ctx.bars - 1, ctx.phrases[index].start // ctx.epb)
            section = ctx.section(bar)
            key = "B" if section is not None and (section.trio or section.bridge) else "A"
            groups[key].append(index)
        primary_bars = _phrase_bars(ctx, groups["A"]) or _body_bars(ctx)
        primary = _dominant_pattern(
            ctx,
            [ctx.phrases[index] for index in groups["A"]] or [ctx.phrases[index] for index in body],
            primary_bars,
        )
        contrast = _contrast_pattern(
            ctx,
            primary,
            [ctx.phrases[index] for index in groups["B"]],
            _phrase_bars(ctx, groups["B"]),
        )
        for index in groups["A"]:
            chosen[index] = primary
        for index in groups["B"]:
            chosen[index] = contrast
        return chosen
    buckets: dict[int, list[int]] = {}
    for index in body:
        bar = min(ctx.bars - 1, ctx.phrases[index].start // ctx.epb)
        section = ctx.section(bar)
        slot = 0 if section is None else section.regime_slot
        buckets.setdefault(slot, []).append(index)
    for indexes in buckets.values():
        pattern = _dominant_pattern(
            ctx,
            [ctx.phrases[index] for index in indexes],
            _phrase_bars(ctx, indexes),
        )
        for index in indexes:
            chosen[index] = pattern
    return chosen


def _cap_accents(ctx: _Ctx, plans: dict, perpetual: dict, limit: int = 2) -> tuple[dict, dict]:
    """A short framed movement keeps at most two scale or perpetual breaks."""
    ranked: list[tuple[int, int, str, object]] = []
    for index, plan in plans.items():
        rise = ctx.phrases[index].rise if index < len(ctx.phrases) else 0
        ranked.append((rise, 1, index, "scale", plan))
    for index, bars in perpetual.items():
        rise = ctx.phrases[index].rise if index < len(ctx.phrases) else 0
        ranked.append((rise, 0, index, "perpetual", bars))
    ranked.sort(reverse=True)
    kept_plans: dict = {}
    kept_perpetual: dict = {}
    for _rise, _prefer, index, kind, payload in ranked[:limit]:
        if kind == "scale":
            kept_plans[index] = payload
        else:
            kept_perpetual[index] = payload
    return kept_plans, kept_perpetual


def _bar_pattern(ctx: _Ctx, bar: int, patterns: list[str]) -> str:
    kind = ctx.kind_at.get(bar, "phrase")
    if kind in _PEDAL:
        return "pedal"
    pattern = _owning_pattern(ctx, bar, patterns)
    if pattern == "pedal" and _framed(ctx):
        return _fallback_body_pattern(ctx, bar, patterns)
    return pattern


def _owning_pattern(ctx: _Ctx, bar: int, patterns: list[str]) -> str:
    eighth = bar * ctx.epb
    for index, phrase in enumerate(ctx.phrases):
        if phrase.start <= eighth < phrase.end:
            return patterns[index] if index < len(patterns) else "pedal"
    for index, phrase in enumerate(ctx.phrases):
        if phrase.start < (bar + 1) * ctx.epb and phrase.end > eighth:
            return patterns[index] if index < len(patterns) else "pedal"
    return {"classic": "study", "villa": "villa_pattern", "brouwer": "brouwer_etude", "bach": "bach_bourree"}.get(
        ctx.ensemble, "preludio"
    )


def _fallback_body_pattern(ctx: _Ctx, bar: int, patterns: list[str]) -> str:
    """A pedal phrase that spills a few eighths into the body keeps the body pattern."""
    eighth = bar * ctx.epb
    for index, phrase in enumerate(ctx.phrases):
        if index < len(patterns) and patterns[index] != "pedal" and phrase.end > eighth:
            return patterns[index]
    for pattern in reversed(patterns):
        if pattern != "pedal":
            return pattern
    return {"classic": "study", "villa": "villa_pattern", "brouwer": "brouwer_etude", "bach": "bach_bourree"}.get(
        ctx.ensemble, "preludio"
    )


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


def _galop_bass_points(ctx: _Ctx) -> tuple[int, ...]:
    if ctx.kind == "6/8":
        return (0, 3)
    return (0, 4)


def _galop_inner_offsets(ctx: _Ctx) -> tuple[int, ...]:
    if ctx.kind == "4/4":
        return (1, 2, 5, 6)
    if ctx.kind == "6/8":
        return (1, 2, 4, 5)
    return (1, 2, 5)


def _stamp(events: list[NoteEvent], **flags) -> list[NoteEvent]:
    if not events:
        return events
    return [replace(events[0], **flags), *events[1:]]


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


def _render_galop_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Galop Op. 32 No. 6: bouncing root/fifth, off-beat chords, a sparkling melody."""
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


def _mozart_bass_plan(ctx: _Ctx, root: int, fifth: int) -> tuple[tuple[int, int, int], ...]:
    if ctx.kind == "6/8":
        return ((0, 3, root), (3, 3, fifth))
    if ctx.kind == "3/4":
        return ((0, 4, root), (4, max(1, ctx.epb - 4), fifth))
    return ((0, 4, root), (4, 4, fifth))


def _mozart_inner(ctx: _Ctx, chord: Chord, sung: int, bass: int, previous: int | None) -> int | None:
    """A stepwise third or sixth under the melody. Skips fall back to the nearest chord tone."""
    parallel = _parallel(sung, bass, ctx.mode, ctx.mid_low, ctx.mid_high, ctx.semitones, previous)
    pool = [
        note
        for note in range(max(ctx.mid_low, bass + 1), min(ctx.mid_high, sung - 1) + 1)
        if _on_scale(note, ctx.mode)
        and _playable([bass + ctx.semitones, note + ctx.semitones, sung + ctx.semitones])
    ]
    if not pool:
        return parallel
    if previous is None:
        if parallel is not None and parallel in pool:
            return parallel
        return parallel or pool[len(pool) // 2]
    stepped = [tone for tone in pool if 0 < abs(tone - previous) <= 2]
    if stepped:
        return min(stepped, key=lambda tone: (abs(tone - previous), tone))
    if parallel is not None:
        return parallel
    return min(pool, key=lambda tone: (abs(tone - previous), tone))


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
    for offset, length, pitch in _mozart_bass_plan(ctx, root, fifth):
        if offset >= ctx.epb or length <= 0:
            continue
        low.extend(_eighth_event(start + offset, min(length, ctx.epb - offset), pitch, ctx.epb, 3, _BASS))
    support: list[NoteEvent] = []
    previous: int | None = None
    for offset in _mozart_offsets(ctx):
        if offset >= ctx.epb:
            continue
        melody = _melody_at(ctx, start + offset)
        bass = _sounding_midi(low, start + offset, ctx.epb) or root
        tone = _mozart_inner(ctx, chord, melody, bass, previous)
        if tone is None:
            continue
        if (
            previous is not None
            and abs(tone - previous) >= 3
            and support
            and abs(support[-1].duration_beats - 0.5) < 1e-6
            and support[-1].midi is not None
        ):
            direction = 1 if tone > previous else -1
            passing = _walk(previous, direction, ctx.mode, ctx.mid_low, ctx.mid_high)
            held_eighth = start + int(round(support[-1].beat * 2))
            sung_then = _melody_at(ctx, held_eighth)
            bass_then = _sounding_midi(low, held_eighth, ctx.epb) or bass
            if (
                bass_then < passing < sung_then
                and passing not in {tone, previous}
                and _playable(
                    [bass_then + ctx.semitones, passing + ctx.semitones, sung_then + ctx.semitones]
                )
            ):
                held = support[-1]
                support[-1] = replace(held, duration_beats=0.25)
                support.append(
                    replace(
                        held,
                        beat=held.beat + 0.25,
                        duration_beats=0.25,
                        midi=passing,
                        tie_start=False,
                        tie_stop=False,
                    )
                )
        support.extend(_eighth_event(start + offset, 1, tone, ctx.epb, 2, _INNER))
        previous = tone
    support, low = _shape_accompaniment(ctx, support, low)
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
    low: list[NoteEvent] | None = None,
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
        bass = _sounding_midi(low, eighth + 1, ctx.epb) if low else None
        if bass is not None:
            if not bass < event.midi < sung:
                updated.append(event)
                continue
            pair = [bass + ctx.semitones, *pair]
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
            spelled = _spell16(
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
            if spelled and (event.staccato or event.tenuto):
                spelled[0] = replace(
                    spelled[0],
                    staccato=event.staccato or spelled[0].staccato,
                    tenuto=event.tenuto or spelled[0].tenuto,
                )
            resolved.extend(spelled)
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
    if ctx.ensemble == "bach":
        low = _bach_keep_bass_below(ctx, lead, low)
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
        if ctx.ensemble == "bach":
            if tone is None:
                continue
            others = [note + ctx.semitones for note in sounding if note != event.midi]
            if _playable([*others, tone + ctx.semitones]) and bass < tone < sung:
                repaired.append(replace(event, midi=tone))
            continue
        if tone is not None and (
            tone != event.midi or not _playable([bass + ctx.semitones, sung + ctx.semitones])
        ):
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


def _punch(
    events: list[NoteEvent],
    eighth: int,
    epb: int,
    *,
    staccato: bool = False,
    amount: int = 8,
) -> list[NoteEvent]:
    """Accent one attack and lift it. A Bartók slap also shortens the note."""
    punched: list[NoteEvent] = []
    for event in events:
        if event.midi is None or _start16(event, epb) // 2 != eighth:
            punched.append(event)
            continue
        velocity = min(88, (event.velocity or _MELODY) + amount)
        punched.append(
            replace(
                event,
                accent=True,
                velocity=velocity,
                staccato=staccato or event.staccato,
            )
        )
    return punched


def _soften_attack(events: list[NoteEvent], eighth: int, epb: int, amount: int = 6) -> list[NoteEvent]:
    softened: list[NoteEvent] = []
    for event in events:
        if event.midi is None or event.velocity is None or _start16(event, epb) // 2 != eighth:
            softened.append(event)
            continue
        softened.append(replace(event, velocity=max(40, event.velocity - amount)))
    return softened


def _mark(events: list[NoteEvent], **flags) -> list[NoteEvent]:
    if not events:
        return events
    return [replace(events[0], **flags), *events[1:]]


def _bass_at(ctx: _Ctx, chord: Chord, degree: int, eighth: int) -> int:
    """A chord bass under this melody. A fifth that will not fret falls back."""
    sung = _melody_at(ctx, eighth)
    low, high = ctx.bass_low, ctx.bass_high

    def fits(note: int) -> bool:
        return note < sung and _playable([note + ctx.semitones, sung + ctx.semitones])

    preferred = _choose_bass(chord, degree, sung, low, high, ctx.semitones)
    if fits(preferred):
        return preferred
    root = _choose_bass(chord, 0, sung, low, high, ctx.semitones)
    if fits(root):
        return root
    wanted = chord.pitches[min(degree, len(chord.pitches) - 1)] % 12
    pcs = {pitch % 12 for pitch in chord.pitches}
    found = [note for note in range(low, high + 1) if fits(note)]
    if not found:
        return preferred if preferred < sung else low
    found.sort(key=lambda note: (note % 12 != wanted, note % 12 not in pcs, note + ctx.semitones not in {40, 45, 50}, note))
    return found[0]


def _root_changes(ctx: _Ctx, bar: int) -> bool:
    if bar + 1 >= ctx.bars:
        return False
    return ctx.chord(bar).pitches[0] % 12 != ctx.chord(bar + 1).pitches[0] % 12


def _toward_next(ctx: _Ctx, bar: int, origin: int, eighth: int) -> int | None:
    """One scale step from `origin` toward the next chord's root."""
    if not _root_changes(ctx, bar):
        return None
    target = _bass_at(ctx, ctx.chord(bar + 1), 0, min(len(ctx.melody) - 1, (bar + 1) * ctx.epb))
    while target - origin > 5 and target - 12 >= ctx.bass_low:
        target -= 12
    while origin - target > 5 and target + 12 <= ctx.bass_high:
        target += 12
    if target == origin:
        return None
    direction = 1 if target > origin else -1
    step = _walk(origin, direction, ctx.mode, ctx.bass_low, ctx.bass_high)
    if step == origin:
        nudged = origin + direction
        if ctx.bass_low <= nudged <= ctx.bass_high:
            step = nudged
        else:
            return None
    sung = _melody_at(ctx, eighth)
    if step < sung and _playable([step + ctx.semitones, sung + ctx.semitones]):
        return step
    root = _bass_at(ctx, ctx.chord(bar), 0, eighth)
    if root != origin and root < sung and _playable([root + ctx.semitones, sung + ctx.semitones]):
        return root
    return None


def _color_inner(ctx: _Ctx, chord: Chord, sung: int, bass: int, step: int, previous: int | None) -> int | None:
    """A 3rd, 7th, or sus/add9 color that sits above every legal bass note."""
    tones = [
        tone
        for tone in _inner_choices(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True)
        if tone > ctx.bass_high
    ]
    if not tones:
        return _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, True, step)
    root = chord.pitches[0] % 12
    rich = {(root + interval) % 12 for interval in (2, 3, 4, 10, 11)}
    if _uses_color(chord):
        rich.update(_ordered_pool(chord, True)[:2])
    preferred = [tone for tone in tones if tone % 12 in rich] or tones
    choices = preferred
    if previous is not None:
        crossed = [
            tone
            for tone in preferred
            if tone != previous and _strings_differ(previous, tone, ctx.semitones)
        ]
        if crossed:
            choices = crossed
    tone = _wave_tone(sorted(choices), step, previous)
    if bass < tone < sung:
        return tone
    return None


def _brouwer_wave(ctx: _Ctx, bar: int, low: list[NoteEvent], offsets: list[int]) -> list[NoteEvent]:
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    support: list[NoteEvent] = []
    previous: int | None = None
    for step, offset in enumerate(offsets):
        eighth = start + offset
        sung = _melody_at(ctx, eighth)
        bass = _sounding_midi(low, eighth, ctx.epb) or _bass_at(ctx, chord, 0, eighth)
        tone = _color_inner(ctx, chord, sung, bass, step, previous)
        if tone is None:
            continue
        previous = tone
        support.extend(_eighth_event(eighth, 1, tone, ctx.epb, 2, _INNER))
    return support


def _render_noviembre_bar(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Two-beat ballad pulse, a walking pickup, and a color arpeggio."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    pulses = [0, 3] if ctx.kind == "6/8" else ([0, 4] if epb > 4 else [0])
    pulses = [offset for offset in pulses if offset < epb]
    root = _bass_at(ctx, chord, 0, start)
    fifth = _bass_at(ctx, chord, 2, start + pulses[-1])
    last = epb - 1
    pickup = _toward_next(ctx, bar, fifth if len(pulses) > 1 else root, start + last)
    low: list[NoteEvent] = []
    for index, offset in enumerate(pulses):
        end = pulses[index + 1] if index + 1 < len(pulses) else epb
        if pickup is not None and end == epb:
            end = last
        length = end - offset
        if length <= 0:
            continue
        pitch = root if index == 0 else fifth
        low.extend(_eighth_event(start + offset, length, pitch, epb, 3, _BASS))
    if pickup is not None:
        low.extend(_eighth_event(start + last, 1, pickup, epb, 3, _BASS))
    wanted = (1, 2, 3, 5, 6) if ctx.kind == "4/4" else (1, 2, 4, 5)
    support = _brouwer_wave(ctx, bar, low, [offset for offset in wanted if offset < epb])
    support, low = _shape_accompaniment(ctx, support, low)
    if pickup is not None:
        low = _soften_attack(low, start + last, epb)
    return support, low


def _etude_cells(ctx: _Ctx) -> list[tuple[int, int, int, bool]]:
    """Thumb cells: offset, length, chord degree, and whether the cell may walk."""
    epb = ctx.epb
    if ctx.kind == "6/8":
        cells = [(0, 2, 0, False), (2, 2, 2, False), (4, 2, 0, True)]
    elif ctx.kind == "3/4":
        cells = [(0, 3, 0, False), (3, 3, 2, False)]
    elif epb >= 8:
        cells = [(0, 3, 0, False), (3, 3, 2, False), (6, 2, 0, True)]
    else:
        cells = [(0, max(1, epb // 2), 0, False)]
        if epb > cells[0][1]:
            cells.append((cells[0][1], epb - cells[0][1], 2, False))
    clipped: list[tuple[int, int, int, bool]] = []
    for offset, length, degree, approach in cells:
        if offset >= epb or length <= 0:
            continue
        clipped.append((offset, min(length, epb - offset), degree, approach))
    return clipped


def _render_etude_bar(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Afro-Cuban tumbao: 3+3+2 in 4/4, with the inner voice on the off-eighths."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    low: list[NoteEvent] = []
    occupied: set[int] = set()
    previous = _bass_at(ctx, chord, 0, start)
    for offset, length, degree, approach in _etude_cells(ctx):
        eighth = start + offset
        pitch = _bass_at(ctx, chord, degree, eighth)
        if approach:
            stepped = _toward_next(ctx, bar, previous, eighth)
            if stepped is not None:
                pitch = stepped
        low.extend(_eighth_event(eighth, length, pitch, epb, 3, _BASS, accent=offset == 0))
        occupied.add(offset)
        previous = pitch
    support = _brouwer_wave(ctx, bar, low, [offset for offset in range(epb) if offset not in occupied])
    support, low = _shape_accompaniment(ctx, support, low)
    low = _punch(low, start, epb, amount=4)
    return support, low


def _elogio_offsets(ctx: _Ctx) -> list[int]:
    wanted = (0, 2, 3, 5, 6) if ctx.kind == "4/4" or ctx.epb >= 8 else (0, 2, 3, 5)
    return [offset for offset in wanted if offset < ctx.epb]


def _render_elogio_bar(ctx: _Ctx, bar: int) -> tuple[list[NoteEvent], list[NoteEvent], int | None]:
    """Staccato ostinato. Eighth 3 is the Bartók slap when it falls in the bar."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    offsets = _elogio_offsets(ctx)
    low: list[NoteEvent] = []
    support: list[NoteEvent] = []
    for index, offset in enumerate(offsets):
        eighth = start + offset
        sung = _melody_at(ctx, eighth)
        bass = _bass_at(ctx, chord, 0 if index % 2 == 0 else 2, eighth)
        low.extend(_mark(_eighth_event(eighth, 1, bass, epb, 3, _BASS), staccato=True))
        tone = _color_inner(ctx, chord, sung, bass, index, None)
        if tone is None:
            tone = _color_note(ctx, chord, sung, bass)
            if tone is not None and not bass < tone < sung:
                tone = None
        if tone is not None:
            support.extend(_mark(_eighth_event(eighth, 1, tone, epb, 2, _INNER), staccato=True))
    support, low = _shape_accompaniment(ctx, support, low)
    slap = start + 3 if 3 in offsets else None
    if slap is not None:
        low = _punch(low, slap, epb, staccato=True, amount=12)
        support = _punch(support, slap, epb, staccato=True, amount=12)
    return support, low, slap


def _sarabande_points(ctx: _Ctx) -> tuple[int, int]:
    epb = ctx.epb
    accent = 3 if ctx.kind == "6/8" else min(2, epb - 1)
    figure = max(epb // 2, accent + 1)
    if figure > epb:
        figure = epb
    return accent, figure


def _modal_figure(
    ctx: _Ctx,
    bar: int,
    figure_at: int,
    bass_midi: int,
    phrase: Phrase | None,
) -> list[NoteEvent]:
    """Stepwise swarm in the second half. Selloff bars move by semitone."""
    epb = ctx.epb
    begin = bar * epb + figure_at
    end = (bar + 1) * epb
    if begin >= end:
        return []
    lo = max(ctx.treble_floor, bass_midi + 7)
    hi = min(ctx.treble_top, ctx.ceiling)
    if lo > hi:
        lo = ctx.treble_floor
    seed = max(lo, min(hi, _melody_at(ctx, min(begin, len(ctx.melody) - 1))))
    descend = phrase is not None and begin >= phrase.apex.start
    direction = -1 if descend else 1
    chromatic = ctx.mood(bar) == "selloff"
    cursor = seed
    events: list[NoteEvent] = []
    level = _MELODY
    for offset in range(end - begin):
        events.extend(_eighth_event(begin + offset, 1, cursor, epb, 1, level))
        level = max(48, level - 1) if descend else min(_MELODY_APEX, level + 1)
        nxt = cursor + direction if chromatic else _walk(cursor, direction, ctx.mode, lo, hi)
        if nxt < lo or nxt > hi or nxt == cursor:
            nxt = cursor - direction
            if nxt < lo or nxt > hi:
                nxt = cursor
        cursor = nxt
    return events


def _render_sarabande_bar(
    ctx: _Ctx,
    bar: int,
    phrase: Phrase | None,
) -> tuple[list[NoteEvent], list[NoteEvent], int, list[NoteEvent]]:
    """Beat 2 carries the heavy chord. A rising phrase then swarms."""
    chord = ctx.chord(bar)
    start = bar * ctx.epb
    epb = ctx.epb
    accent, figure = _sarabande_points(ctx)
    figure_at = figure if _rises(phrase) and figure < epb else epb
    root = _bass_at(ctx, chord, 0, start)
    fifth = _bass_at(ctx, chord, 2, start + accent)
    low: list[NoteEvent] = []
    if accent > 0:
        low.extend(_eighth_event(start, accent, root, epb, 3, _BASS))
    low.extend(_eighth_event(start + accent, max(1, figure_at - accent), fifth, epb, 3, _BASS))
    if figure_at < epb:
        low.extend(_eighth_event(start + figure_at, epb - figure_at, root, epb, 3, _BASS))
    sung = _melody_at(ctx, start + accent)
    tone = _color_inner(ctx, chord, sung, fifth, 0, None)
    support: list[NoteEvent] = []
    if tone is not None:
        support.extend(_eighth_event(start + accent, max(1, figure_at - accent), tone, epb, 2, _INNER))
    support, low = _shape_accompaniment(ctx, support, low)
    low = _punch(low, start + accent, epb, amount=8)
    support = _punch(support, start + accent, epb, amount=8)
    figure_events = _modal_figure(ctx, bar, figure_at, root, phrase) if figure_at < epb else []
    return support, low, accent, figure_events


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


def _render_bach_fuga_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Soprano sings the price now. The bass answers two bars later, 1:1, on this chord."""
    epb = ctx.epb
    start = bar * epb
    lead = _sustain(ctx.melody, start, start + epb, epb, apex, phrase=phrase)
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
    if src == bar and low:
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


def _render_bach_gavotte_bar(
    ctx: _Ctx, bar: int, apex: set[int], phrase: Phrase | None
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Gavotte: quarter-quarter, then four eighths in parallel thirds or sixths."""
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
    target = _melody_at(ctx, min(len(ctx.melody) - 1, (bar + 1) * epb if bar + 1 < ctx.bars else start))
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
    if _framed(ctx) and ctx.bars <= 40:
        plans, perpetual = _cap_accents(ctx, plans, perpetual)
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
            # Framed movements replace this held close with a composer entrance.
            if not _framed(ctx):
                lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
                root = _choose_bass(ctx.chord(bar), 0, _melody_at(ctx, bar * epb), ctx.bass_low, ctx.bass_high, ctx.semitones)
                low.extend(_eighth_event(bar * epb, epb, root, epb, 3, _BASS))
        elif pattern == "preludio":
            if _catedral_preludio(ctx):
                part_lead, part_support = _render_catedral_preludio_bar(
                    ctx, bar, patterns, apex, phrase_here
                )
                lead.extend(part_lead)
                support.extend(part_support)
            else:
                lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
                support.extend(_preludio_inner(ctx, bar, patterns))
        elif pattern == "study":
            level = levels.get(owner, 0) if owner is not None else 0
            part_support, part_low = _render_study_bar(ctx, bar, level, False)
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "galop":
            part_lead, part_support, part_low = _render_galop_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "mozart_var":
            part_lead, part_support, part_low = _render_mozart_var_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
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
        elif pattern == "noviembre":
            part_support, part_low = _render_noviembre_bar(ctx, bar)
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "brouwer_etude":
            part_support, part_low = _render_etude_bar(ctx, bar)
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "elogio_pizz":
            part_support, part_low, slap = _render_elogio_bar(ctx, bar)
            cuts = {slap, slap + 1} if slap is not None else None
            part_lead = _sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, cuts, phrase_here)
            if slap is not None:
                part_lead = _punch(part_lead, slap, epb, staccato=True, amount=12)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "sarabande":
            part_support, part_low, accent_at, figure = _render_sarabande_bar(ctx, bar, phrase_here)
            cuts = {bar * epb + accent_at}
            if figure:
                cuts.add(_start16(figure[0], epb) // 2)
            part_lead = _sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, cuts, phrase_here)
            part_lead = _punch(part_lead, bar * epb + accent_at, epb, amount=8)
            if figure:
                figure_eighth = _start16(figure[0], epb) // 2
                part_lead = _splice(part_lead, figure_eighth * 2, (bar + 1) * epb * 2, figure, epb)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "bach_fuga":
            part_lead, part_support, part_low = _render_bach_fuga_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "bach_bourree":
            part_lead, part_support, part_low = _render_bach_bourree_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "bach_gavotte":
            part_lead, part_support, part_low = _render_bach_gavotte_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "bach_sarabande":
            part_lead, part_support, part_low = _render_bach_sarabande_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "bach_gigue":
            part_lead, part_support, part_low = _render_bach_gigue_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "bach_chaconne":
            part_lead, part_support, part_low = _render_bach_chaconne_bar(ctx, bar, apex, phrase_here)
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        else:
            lead.extend(_sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase_here))
    # Preludio bass rings for two bars, counted from each contiguous region.
    low.extend(_preludio_bass(ctx, patterns))
    ringing = {
        bar
        for bar in range(musical_bars)
        if _bar_pattern(ctx, bar, patterns) in {"villa_pattern", "brouwer_etude"}
    }
    if ringing:
        support = _apply_campanella(ctx, support, lead, ringing, low if ctx.ensemble == "brouwer" else None)
    if not _framed(ctx):
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
    # *La Catedral* already sings the canto on beats 0, 1.5, 2, and 3.5.
    # A bell would cut that dotted quarter. Legacy eighth Preludio still blooms.
    authentic = _catedral_preludio(ctx)
    bell_bars = {
        bar
        for bar in range(musical_bars)
        if (not _framed(ctx) and ctx.kind_at.get(bar, "phrase") in {"intro", "warmup"})
        or (
            not authentic
            and _bar_pattern(ctx, bar, patterns) == "preludio"
            and _bells_here(ctx, bar, patterns)
        )
    }
    if _framed(ctx) and ctx.bars <= 40 and len(bell_bars) > 2:
        ranked_bells = sorted(
            bell_bars,
            key=lambda bar: max(ctx.melody[bar * epb : (bar + 1) * epb] or [0]),
            reverse=True,
        )
        bell_bars = set(ranked_bells[:2])
    lead, support = _insert_bells(ctx, lead, support, bell_bars)
    for index, (target, ascent, chromatic) in plans.items():
        # The canto is the Preludio. A scale run would cut the dotted quarters.
        if (
            _catedral_preludio(ctx)
            and _framed(ctx)
            and index < len(patterns)
            and patterns[index] == "preludio"
        ):
            continue
        lead, support, low, _bars = _apply_scale_run(
            ctx, lead, support, low, phrases[index], target, ascent, chromatic
        )
    for index, bars in perpetual.items():
        lead, support, low = _apply_perpetual(ctx, lead, support, low, bars)
    for bar in _fanfare_bars(ctx, levels):
        lead, support, low = _apply_fanfare(ctx, lead, support, low, bar)
    relaxed: set[int] = set()
    if _framed(ctx):
        lead, support, low = _strip_pedal(ctx, lead, support, low)
        lead, support, low = _paint_frames(ctx, lead, support, low)
        lead, support, low, relaxed = _smooth_boundaries(ctx, patterns, lead, support, low)
    else:
        lead, support, low = _transitions(ctx, patterns, levels, lead, support, low)
    for eighth in _caesura_eighths(ctx, levels):
        lead = _silence(lead, eighth, epb)
        support = _silence(support, eighth, epb)
        low = _silence(low, eighth, epb)
    lead, support, low = _repair(ctx, lead, support, low)
    lead = _resolve(lead, epb, 1)
    support = _resolve(support, epb, 2)
    low = _resolve(low, epb, 3)
    # A guitar slur is a left-hand hammer. On Preludio it clips the canto attack.
    plucked = None
    if _catedral_preludio(ctx):
        plucked = {
            bar
            for bar in range(musical_bars)
            if _bar_pattern(ctx, bar, patterns) == "preludio"
        }
    lead = _slur(lead, phrases, skip_bars=plucked)
    if _framed(ctx):
        lead, support, low = _shape_dynamics(ctx, lead, support, low, relaxed, patterns)
    divisions = 4 if _needs_sixteenths([*lead, *support, *low]) else 2
    # Bach's mordent, bariolage, and scale runs are sixteenth figures. When any
    # voice asks for that grid, the engraving stays at division 4.
    if ctx.ensemble == "bach" and _needs_sixteenths([*lead, *support, *low]):
        divisions = 4
    # Fast Barrios stays on the sixteenth grid once a character is set, and a
    # long suite movement does too, so Preludio still engraves at the tremolo
    # division when the line itself is in eighths.
    if (
        divisions == 2
        and ctx.ensemble == "barrios"
        and ctx.bpm >= BARRIOS_TREMOLO_MIN_BPM
        and (ctx.character is not None or ctx.bars > 40)
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


def _catedral_bass(ctx: _Ctx, bar: int, patterns: list[str]) -> int:
    """The pedal pitch `_preludio_bass` will hold under this bar."""
    anchor = _preludio_anchor(ctx, bar, patterns)
    return _choose_bass(
        ctx.chord(anchor),
        0,
        _melody_at(ctx, anchor * ctx.epb),
        ctx.bass_low,
        ctx.bass_high,
        ctx.semitones,
    )


def _catedral_open(ctx: _Ctx, tone: int) -> bool:
    """Open 4th, 3rd, 2nd, or 1st string: D3, G3, B3, E4."""
    return (tone + ctx.semitones) in {50, 55, 59, 64}


def _catedral_canto_ceiling(ctx: _Ctx) -> int:
    return min(ctx.treble_top, 79 - ctx.semitones)


def _catedral_canto_pitch(ctx: _Ctx, pitch: int) -> int:
    """Lift a dull canto note onto the singing 1st string.

    Notes already at F4 and above stay put, so a line that is already
    `[72, 74, 76, 72]` is not moved. A C4–E4 canto steps up by octaves until
    it rings at G4 or higher, and never past the glass ceiling.
    """
    ceiling = _catedral_canto_ceiling(ctx)
    shimmer = 65 - ctx.semitones
    lifted = pitch
    while lifted < shimmer and lifted + 12 <= ceiling:
        lifted += 12
    return lifted


def _catedral_canto_pair(ctx: _Ctx, pitch_a: int, pitch_b: int) -> tuple[int, int]:
    """Lift a low cell by the same octave so the two canto notes keep their shape."""
    lifted_a = _catedral_canto_pitch(ctx, pitch_a)
    lifted_b = _catedral_canto_pitch(ctx, pitch_b)
    glass = 66 - ctx.semitones
    if pitch_a < glass and pitch_b < glass:
        shift = max(lifted_a - pitch_a, lifted_b - pitch_b)
        ceiling = _catedral_canto_ceiling(ctx)
        if shift and pitch_a + shift <= ceiling and pitch_b + shift <= ceiling:
            return pitch_a + shift, pitch_b + shift
    return lifted_a, lifted_b


def _catedral_glass_tones(ctx: _Ctx, tones: list[int], lead: int) -> list[int]:
    """Three inner tones. Prefer an open string as the top of the wave.

    The open string sits on a different string from the fretted canto, so the
    two ring together. When nothing is open, the highest three stay.
    """
    ordered = sorted(tones)
    if len(ordered) <= 3:
        return ordered
    best: tuple[int, ...] | None = None
    best_key: tuple[int, ...] | None = None
    for combo in itertools.combinations(ordered, 3):
        low, mid, upper = combo
        opens = sum(_catedral_open(ctx, tone) for tone in combo)
        upper_open = int(_catedral_open(ctx, upper))
        distinct = sum(_strings_differ(tone, lead, ctx.semitones) for tone in combo)
        spread = (
            int(_strings_differ(low, mid, ctx.semitones))
            + int(_strings_differ(mid, upper, ctx.semitones))
            + int(_strings_differ(low, upper, ctx.semitones))
        )
        key = (upper_open, opens, upper, distinct, spread)
        if best_key is None or key > best_key:
            best_key = key
            best = combo
    return list(best if best is not None else tones[-3:])


def _catedral_rank_glass(ctx: _Ctx, tones: list[int], lead: int) -> list[int]:
    """Keep every legal tone, with the campanella triple at the end."""
    if len(tones) <= 3:
        return list(tones)
    glass = _catedral_glass_tones(ctx, tones, lead)
    chosen = set(glass)
    return [tone for tone in tones if tone not in chosen] + glass


def _catedral_whisper(pitches: list[int | None], base_vel: int = 52) -> list[int]:
    """Warm inner wave (~50..55), ~2 steps gentler at the bottom of the V."""
    sounding = [pitch for pitch in pitches if pitch is not None]
    bottom = min(sounding) if sounding else None
    levels: list[int] = []
    for pitch in pitches:
        level = base_vel - 2 if pitch is not None and pitch == bottom else base_vel
        levels.append(max(48, min(55, level)))
    return levels


def _catedral_playable_tones(ctx: _Ctx, chord: Chord, bass: int, lead: int) -> list[int]:
    """Chord tones strictly between the bass and this canto note, low to high.

    Each one has to share a hand with the bass and the note that is actually
    ringing, so `_repair` has nothing to drop. Open strings under the canto
    are kept and floated into the campanella triple.
    """
    if lead <= bass + 1:
        return []
    tones = _inner_choices(chord, lead, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False)

    def fits(note: int) -> bool:
        return bass < note < lead and _playable(
            [bass + ctx.semitones, note + ctx.semitones, lead + ctx.semitones]
        )

    playable = [tone for tone in tones if fits(tone)]
    if playable:
        return _catedral_rank_glass(ctx, playable, lead)
    # No chord tone frets. A scale tone in the same window keeps the sixteenths moving.
    found: list[int] = []
    low = max(ctx.mid_low, bass + 1)
    high = min(ctx.mid_high, lead - 1)
    for note in range(low, high + 1):
        if _on_scale(note, ctx.mode) and fits(note):
            found.append(note)
    return _catedral_rank_glass(ctx, found, lead)


def _catedral_lead_note(
    start: int,
    length: int,
    midi: int,
    epb: int,
    velocity: int,
    *,
    tenuto: bool = False,
) -> list[NoteEvent]:
    events = _spell16(start, length, midi, epb, 1, velocity)
    if tenuto and events:
        events[0] = replace(events[0], tenuto=True)
    return events


def _catedral_wave(ctx: _Ctx, tones: list[int], pitch_b: int, lead: int) -> list[int]:
    """Six inner pitches for sixteenths 1, 2, 3, 4, 5, and 7 of one 2-beat cell."""
    chosen = _catedral_glass_tones(ctx, tones, lead)
    if len(chosen) >= 3:
        low_mid, mid, upper_mid = chosen[-3:]
        last = upper_mid if upper_mid < pitch_b else mid
        return [upper_mid, mid, low_mid, mid, upper_mid, last]
    if len(chosen) == 2:
        lower, higher = chosen
        # Neighbours change pitch. The second example in the spec.
        return [higher, lower, higher, lower, higher, lower]
    return [chosen[0]] * 6


def _catedral_descend(ctx: _Ctx, tones: list[int], count: int, lead: int) -> list[int]:
    """`upper_mid, mid, low_mid` across the leftover beat of a 3/4 or 6/8 bar."""
    chosen = _catedral_glass_tones(ctx, tones, lead)
    if count <= 0 or not chosen:
        return []
    if len(chosen) >= 3:
        low_mid, mid, upper_mid = chosen[-3:]
        pattern = [upper_mid, mid, low_mid]
    elif len(chosen) == 2:
        lower, higher = chosen
        pattern = [higher, lower, lower]
    else:
        pattern = [chosen[0]]
    if count <= len(pattern):
        return pattern[:count]
    return [*pattern, *([pattern[-1]] * (count - len(pattern)))]


def _catedral_schedule(ctx: _Ctx, chord: Chord, bass: int, pitch_a: int, pitch_b: int) -> list[int | None]:
    """Inner pitches for sixteenths 1, 2, 3, 4, 5, 7, each playable under the canto then sounding."""
    under_a = _catedral_playable_tones(ctx, chord, bass, pitch_a)
    under_b = _catedral_playable_tones(ctx, chord, bass, pitch_b)
    shared = [tone for tone in under_a if tone in set(under_b)]
    source = shared or under_a or under_b
    canto = max(pitch_a, pitch_b)
    planned = _catedral_wave(ctx, source, pitch_b, canto) if source else [None] * 6
    pools = (under_a, under_a, under_a, under_a, under_a, under_b)
    resolved: list[int | None] = []
    previous: int | None = None
    for planned_tone, pool in zip(planned, pools):
        tone = planned_tone if pool and planned_tone in pool else None
        if tone is None and pool:
            choices = list(reversed(pool))
            if previous is not None and len(pool) > 1:
                different = [item for item in choices if item != previous]
                choices = different or choices
            tone = choices[0]
        resolved.append(tone)
        if tone is not None:
            previous = tone
    return resolved


def _catedral_emit_support(
    events: list[NoteEvent],
    start16: int,
    slots: tuple[int, ...] | list[int],
    pitches: list[int | None],
    epb: int,
    velocities: list[int],
) -> None:
    for slot, pitch, velocity in zip(slots, pitches, velocities):
        if pitch is None:
            continue
        events.extend(_spell16(start16 + slot, 1, pitch, epb, 2, max(48, min(55, velocity))))


def _catedral_cell(
    ctx: _Ctx,
    bar: int,
    eighth: int,
    bass: int,
    apex: set[int],
    phrase: Phrase | None,
    _patterns: list[str],
    lead: list[NoteEvent],
    support: list[NoteEvent],
) -> None:
    """One 2-beat *La Catedral* cell: dotted quarter, V-wave, eighth, closing inner note."""
    pitch_a = _melody_at(ctx, eighth)
    pitch_b = _melody_at(ctx, eighth + 3)
    start16 = eighth * 2
    # Keep canto under the harsh MS Basic nail-snap threshold (65): warm 56..63 range.
    raw_vel = _note_velocity(eighth, 3, apex, phrase)
    vel_a = min(63, max(56, raw_vel - 4))
    vel_b = max(54, vel_a - 2)
    lead.extend(_catedral_lead_note(start16, 6, pitch_a, ctx.epb, vel_a, tenuto=False))
    lead.extend(_catedral_lead_note(start16 + 6, 2, pitch_b, ctx.epb, vel_b, tenuto=False))
    slots = (1, 2, 3, 4, 5, 7)
    pitches = _catedral_schedule(ctx, ctx.chord(bar), bass, pitch_a, pitch_b)
    base_sup = {"p": 50, "mp": 52, "mf": 53, "f": 55}.get(ctx.band(bar), 52)
    levels = _catedral_whisper(pitches, min(base_sup, min(vel_a, vel_b) - 4))
    # Sixteenths 1..5 ring under the dotted quarter. Sixteenth 7 rings under the eighth.
    _catedral_emit_support(support, start16, slots[:5], pitches[:5], ctx.epb, levels[:5])
    _catedral_emit_support(support, start16, slots[5:], pitches[5:], ctx.epb, levels[5:])


def _catedral_tail(
    ctx: _Ctx,
    bar: int,
    eighth: int,
    eighths: int,
    bass: int,
    apex: set[int],
    phrase: Phrase | None,
    _patterns: list[str],
    lead: list[NoteEvent],
    support: list[NoteEvent],
) -> None:
    """The leftover beat of 3/4 or 6/8: one melody note, then a descending inner group."""
    if eighths <= 0:
        return
    pitch = _melody_at(ctx, eighth)
    start16 = eighth * 2
    length16 = eighths * 2
    raw_vel = _note_velocity(eighth, eighths, apex, phrase)
    velocity = min(63, max(56, raw_vel - 4))
    lead.extend(_catedral_lead_note(start16, length16, pitch, ctx.epb, velocity, tenuto=False))
    tones = _catedral_playable_tones(ctx, ctx.chord(bar), bass, pitch)
    descending = _catedral_descend(ctx, tones, length16 - 1, pitch)
    base_sup = {"p": 50, "mp": 52, "mf": 53, "f": 55}.get(ctx.band(bar), 52)
    _catedral_emit_support(
        support,
        start16,
        list(range(1, length16)),
        descending,
        ctx.epb,
        _catedral_whisper(descending, min(base_sup, velocity - 4)),
    )


def _render_catedral_preludio_bar(
    ctx: _Ctx,
    bar: int,
    patterns: list[str],
    apex: set[int],
    phrase: Phrase | None,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Voice 1 and voice 2 for one bar of *La Catedral — Preludio (Saudade)*."""
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    bass = _catedral_bass(ctx, bar, patterns)
    eighth = bar * ctx.epb
    end = eighth + ctx.epb
    while eighth + 4 <= end:
        _catedral_cell(ctx, bar, eighth, bass, apex, phrase, patterns, lead, support)
        eighth += 4
    if eighth < end:
        _catedral_tail(ctx, bar, eighth, end - eighth, bass, apex, phrase, patterns, lead, support)
    return lead, support


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


def _pedal_regions(ctx: _Ctx) -> tuple[list[int], list[int]]:
    leading: list[int] = []
    bar = 0
    while bar < ctx.bars and ctx.kind_at.get(bar, "phrase") in _PEDAL:
        leading.append(bar)
        bar += 1
    trailing: list[int] = []
    bar = ctx.bars - 1
    while bar >= 0 and bar not in leading and ctx.kind_at.get(bar, "phrase") in _PEDAL:
        trailing.append(bar)
        bar -= 1
    trailing.reverse()
    return leading, trailing


def _strip_pedal(ctx: _Ctx, lead, support, low):
    leading, trailing = _pedal_regions(ctx)
    drop = set(leading) | set(trailing)
    if not drop:
        return lead, support, low
    return (
        [event for event in lead if event.bar not in drop],
        [event for event in support if event.bar not in drop],
        [event for event in low if event.bar not in drop],
    )


def _paint_frames(ctx: _Ctx, lead, support, low):
    from app.sonify.guitar_frame import render_intro, render_outro

    leading, trailing = _pedal_regions(ctx)
    if leading:
        part_lead, part_support, part_low = render_intro(ctx, leading)
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)
    if trailing:
        part_lead, part_support, part_low = render_outro(ctx, trailing)
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)
    return lead, support, low


def _boundary_bars(ctx: _Ctx, patterns: list[str]) -> list[int]:
    """Last bar before intro yields to the body, A yields to B, or the body yields to the outro."""
    found: list[int] = []
    leading, trailing = _pedal_regions(ctx)
    if leading:
        nxt = leading[-1] + 1
        if nxt < ctx.bars and ctx.kind_at.get(nxt, "phrase") not in _PEDAL:
            found.append(leading[-1])
    if trailing:
        prev = trailing[0] - 1
        if prev >= 0 and ctx.kind_at.get(prev, "phrase") not in _PEDAL:
            found.append(prev)
    for bar in range(ctx.bars - 1):
        if ctx.kind_at.get(bar, "phrase") in _PEDAL or ctx.kind_at.get(bar + 1, "phrase") in _PEDAL:
            continue
        left = ctx.section(bar)
        right = ctx.section(bar + 1)
        if left is None or right is None or left is right:
            continue
        crosses = bool(left.trio or left.bridge or right.trio or right.bridge)
        if crosses or _bar_pattern(ctx, bar, patterns) != _bar_pattern(ctx, bar + 1, patterns):
            found.append(bar)
    ordered: list[int] = []
    for bar in found:
        if bar not in ordered:
            ordered.append(bar)
    return ordered


def _event_covers(event: NoteEvent, eighth: int, epb: int) -> bool:
    if event.midi is None:
        return False
    start = _start16(event, epb)
    return start <= eighth * 2 < start + _dur16(event)


def _previous_bass(low: list[NoteEvent], eighth: int, epb: int) -> NoteEvent | None:
    when = eighth * 2
    best: NoteEvent | None = None
    best_at = -1
    for event in low:
        if event.midi is None:
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if finish <= when and begin >= best_at:
            best = event
            best_at = begin
    return best


def _upper_ceiling(ctx: _Ctx, support, lead, eighth: int) -> int | None:
    pitches = [
        event.midi
        for event in (*support, *lead)
        if _event_covers(event, eighth, ctx.epb) and event.midi is not None
    ]
    if not pitches:
        return None
    return min(pitches)


def _fold_bass(ctx: _Ctx, pc: int) -> int:
    high = min(ctx.bass_high, 53 - ctx.semitones)
    return _clamp(pc + 48, ctx.bass_low, max(ctx.bass_low, high))


def _eighth_pitches(ctx: _Ctx, events, eighth: int, *, cover_eighth: bool) -> list[int]:
    """Pitches sounding at the eighth's attack, or anywhere inside that eighth."""
    if not cover_eighth:
        return [
            event.midi
            for event in events
            if _event_covers(event, eighth, ctx.epb) and event.midi is not None
        ]
    start = eighth * 2
    end = start + 2
    found: list[int] = []
    for event in events:
        if event.midi is None:
            continue
        begin = _start16(event, ctx.epb)
        if begin < end and begin + _dur16(event) > start:
            found.append(event.midi)
    return found


def _safe_pickup(ctx: _Ctx, bar: int, support, lead, low, *, cover_eighth: bool = False) -> int:
    """Root or fifth of the next bar, never a chromatic approach or a short lament."""
    nxt = min(ctx.bars - 1, bar + 1)
    root_pc = ctx.chord(nxt).pitches[0] % 12
    fifth_pc = (root_pc + 7) % 12
    eighth = (bar + 1) * ctx.epb - 1
    upper = _eighth_pitches(ctx, [*support, *lead], eighth, cover_eighth=cover_eighth)
    ceiling = min(upper) if upper else None
    high = min(ctx.bass_high, 53 - ctx.semitones)
    if ceiling is not None:
        high = min(high, ceiling - 1)
    if high < ctx.bass_low:
        high = ctx.bass_low
    previous = _previous_bass(low, eighth, ctx.epb)
    candidates: list[int] = []
    for pc in (root_pc, fifth_pc):
        for sounding in (40, 45, 50):
            written_pitch = sounding - ctx.semitones
            if ctx.bass_low <= written_pitch <= high and written_pitch % 12 == pc:
                candidates.append(written_pitch)
        folded = _fold_bass(ctx, pc)
        if ctx.bass_low <= folded <= high:
            candidates.append(folded)
    if previous is not None and previous.midi is not None and ctx.bass_low <= previous.midi <= high:
        candidates.append(previous.midi)
    for note in candidates:
        if (note + ctx.semitones) % 12 == (root_pc - 1) % 12:
            continue
        if (
            previous is not None
            and previous.midi is not None
            and previous.duration_beats >= 1.0 - 1e-6
            and previous.midi - note in {1, 2}
        ):
            continue
        sounding = [note + ctx.semitones, *(pitch + ctx.semitones for pitch in upper)]
        if _playable(sounding) and (ceiling is None or note < ceiling):
            return note
    if previous is not None and previous.midi is not None and (ceiling is None or previous.midi < ceiling):
        return previous.midi
    return _clamp(ctx.chord(nxt).pitches[0], ctx.bass_low, max(ctx.bass_low, high))


def _relax_texture(ctx: _Ctx, lead, support, low, bar: int):
    """Last half-bar of a tremolo or dance eases to eighths and a decrescendo."""
    half = max(1, ctx.epb // 2)
    start = (bar + 1) * ctx.epb - half
    end = (bar + 1) * ctx.epb
    lead = _drop_overlap(lead, start * 2, end * 2, ctx.epb)
    support = _drop_overlap(support, start * 2, end * 2, ctx.epb)
    low = _drop_overlap(low, start * 2, end * 2, ctx.epb)
    span = end - start
    top, bottom = 58, 46
    for offset in range(span):
        level = bottom if span == 1 else round(top - (top - bottom) * offset / (span - 1))
        eighth = start + offset
        lead.extend(_eighth_event(eighth, 1, _melody_at(ctx, eighth), ctx.epb, 1, level))
    if span > 1:
        root = _clamp(ctx.chord(bar).pitches[0], ctx.bass_low, ctx.bass_high)
        low.extend(_eighth_event(start, span - 1, root, ctx.epb, 3, top))
    return lead, support, low, set(range(start, end))


def _plant_pickup(ctx: _Ctx, lead, support, low, bar: int, *, cover_eighth: bool = False):
    eighth = (bar + 1) * ctx.epb - 1
    low = _silence(low, eighth, ctx.epb)
    pitch = _safe_pickup(ctx, bar, support, lead, low, cover_eighth=cover_eighth)
    low.extend(_eighth_event(eighth, 1, pitch, ctx.epb, 3, 50))
    return lead, support, low


def _smooth_boundaries(ctx: _Ctx, patterns, lead, support, low):
    relaxed: set[int] = set()
    for bar in _boundary_bars(ctx, patterns):
        pattern = _bar_pattern(ctx, bar, patterns)
        if ctx.kind_at.get(bar, "phrase") not in _PEDAL and (pattern == "tremolo" or pattern in _DANCE):
            lead, support, low, window = _relax_texture(ctx, lead, support, low, bar)
            relaxed.update(window)
        # The last sixteenth of *La Catedral* is an inner note. The pickup bass
        # has to share a hand with that note, not only with the canto attack.
        cover = _catedral_preludio(ctx) and pattern == "preludio"
        lead, support, low = _plant_pickup(ctx, lead, support, low, bar, cover_eighth=cover)
    return lead, support, low, relaxed


_BAND_DELTA = {"p": -12, "mp": -6, "mf": 0, "f": 4}


def _shape_dynamics(ctx: _Ctx, lead, support, low, relaxed: set[int], patterns: list[str] | None = None):
    """Liquidity and the phrase swell move the dynamic inside a locked pattern.

    *La Catedral* keeps the canto in the singing window and the inner wave in
    a whisper. A `p` or `mp` band must not close that gap.
    """
    pedal = set(_pedal_regions(ctx)[0]) | set(_pedal_regions(ctx)[1])
    preludio_bars: set[int] = set()
    if patterns is not None and _catedral_preludio(ctx):
        preludio_bars = {
            bar for bar in range(ctx.bars) if _bar_pattern(ctx, bar, patterns) == "preludio"
        }

    def phrase_at(eighth: int) -> Phrase | None:
        for phrase in ctx.phrases:
            if phrase.start <= eighth < phrase.end and phrase.rise > 0:
                return phrase
        return None

    def shape(events: list[NoteEvent], voice: str) -> list[NoteEvent]:
        shaped: list[NoteEvent] = []
        for event in events:
            if event.midi is None or event.velocity is None or event.bar in pedal:
                shaped.append(event)
                continue
            eighth = event.bar * ctx.epb + int(math.floor(event.beat * 2 + 1e-9))
            if eighth in relaxed:
                shaped.append(event)
                continue
            extra = 0
            phrase = phrase_at(eighth)
            if phrase is not None:
                extra = round(4 * swell(phrase, min(max(eighth, phrase.start), phrase.end - 1)))
            delta = _BAND_DELTA.get(ctx.band(event.bar), 0)
            if event.bar in preludio_bars and voice == "lead":
                # Keep canto in the warm nylon layer (54..64), under the harsh 65+ nail snap.
                canto_delta = {"p": -3, "mp": -1, "mf": 1, "f": 2}.get(ctx.band(event.bar), 0)
                velocity = max(54, min(64, event.velocity + canto_delta + (extra // 2)))
                shaped.append(replace(event, velocity=velocity))
                continue
            if event.bar in preludio_bars and voice == "support":
                sup_delta = {"p": -2, "mp": -1, "mf": 0, "f": 1}.get(ctx.band(event.bar), 0)
                velocity = max(48, min(55, event.velocity + sup_delta + (extra // 3)))
                shaped.append(replace(event, velocity=velocity))
                continue
            if event.velocity >= _MELODY_APEX:
                shaped.append(event)
                continue
            velocity = max(44, min(78, event.velocity + delta + extra))
            shaped.append(replace(event, velocity=velocity))
        return shaped

    return shape(lead, "lead"), shape(support, "support"), shape(low, "low")


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
        if profile not in {"villa_pattern", "barrios_dance", "elegiaque", "grand", "study", "brouwer", "bach"} and approach:
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
