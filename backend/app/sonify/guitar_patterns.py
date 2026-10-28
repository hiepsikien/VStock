"""Phase 3 guitar patterns, phrase overlays, and the playability check.

`assert_playable` only reports. The renderer repairs voicings before they
are written, and the tremolo grid itself stays in `guitar._tremolo`.
"""

from __future__ import annotations

import itertools
import math
from contextvars import ContextVar
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
    "etude1": "arpeggio",
    "etude11": "arpeggio",
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
    "etude1": "villa_etude1",
    "etude11": "villa_etude11",
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


# Set by the chart namer. The renderer appends the body pattern it actually chose.
_HEADLINE: ContextVar[list[str] | None] = ContextVar("vstock_guitar_headline", default=None)
# One id, or primary / contrast / primary when a trio or bridge uses another pattern.
_FORM: ContextVar[list[list[str]] | None] = ContextVar("vstock_guitar_form", default=None)
# The namer skips the voice grid. Playback leaves this false.
_SKIP_VOICES: ContextVar[bool] = ContextVar("vstock_guitar_skip_voices", default=False)


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
    bar_volumes: list[float] | None = None
    section_rel_spans: dict | None = None
    impulses: tuple = ()

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
    # A door may aim at a sixteenth with a half-eighth offset. Floor division of
    # a float would store the bar as 0.0, which cannot index a measure list.
    cursor = int(round(start))
    left = int(round(length))
    if left <= 0:
        return events
    first = cursor
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
    if not sounding:
        return True
    options = []
    for pitch in sounding:
        choices = _string_options(pitch)
        if not choices:
            return False
        options.append(choices)
    for combo in itertools.product(*options):
        frets = [fret for _string, fret in combo if fret > 0]
        if frets and max(frets) - min(frets) > 5:
            continue
        return True
    return False


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
        if mood == "volatile":
            return "mozart_var"
    if ctx.ensemble == "villa":
        if trio or bridge or mood == "selloff":
            return "thumb_cantabile"
        if ctx.bpm <= 72 or band == "p" or mood == "calm":
            return "chord_melody"
        # The opening body phrase stays the eighth-note roll. The etudes begin
        # on the next phrase, and only in 4/4 above the slow-movement floor.
        if not first_body and ctx.kind == "4/4" and ctx.bpm > 72:
            if mood == "rally":
                return "etude1"
            if mood == "volatile":
                return "etude11"
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


def _framed(ctx: _Ctx) -> bool:
    """A real movement carries intro or outro sections.

    Synthetic pattern tests pass a trio or a phrase and no pedal, and the
    one-bar pedal fixture passes kinds without sections. Both keep the
    per-phrase selector. `render` always sends the form's sections.
    """
    return any(getattr(section, "kind", None) in _PEDAL for section in ctx.sections)


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
        _slot_contrast(section)[1] and getattr(section, "kind", None) not in _PEDAL
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


def _melody_activity(ctx: _Ctx, bars: list[int]) -> float:
    """Fraction of eighths whose placed melody pitch changes."""
    if not bars or not ctx.melody:
        return 0.0
    changes = 0
    total = 0
    for bar in bars:
        start = bar * ctx.epb
        end = min(len(ctx.melody), (bar + 1) * ctx.epb)
        for eighth in range(max(start, 1), end):
            total += 1
            if ctx.melody[eighth] != ctx.melody[eighth - 1]:
                changes += 1
    if total <= 0:
        return 0.0
    return changes / total


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
        # Selloff sings Prélude No. 1 on the thumb. A bridge or trio still answers
        # through `_contrast_pattern`, which is unchanged.
        if mood == "selloff":
            return "thumb_cantabile"
        # Slow movements and calm or quiet sessions keep the block-chord pattern.
        if ctx.bpm <= 72:
            return "chord_melody"
        quiet = sum(1 for bar in bars if ctx.band(bar) == "p")
        if mood == "calm" or (bars and quiet * 2 > len(bars)):
            return "chord_melody"
        # 6/8 stays the eighth-note roll for every mood. 4/4 rally and volatile
        # lock the etudes across the whole body, including the opening phrase.
        if ctx.kind == "6/8":
            return "villa_pattern"
        if ctx.kind == "4/4" and ctx.bpm > 72:
            if mood == "rally":
                return "etude1"
            if mood == "volatile":
                return "etude11"
        return "villa_pattern"
    if ctx.bpm < BARRIOS_TREMOLO_MIN_BPM:
        return "andante"
    if _framed(ctx) and ctx.kind == "4/4" and 90 <= ctx.bpm <= 100:
        # Opening moderato (1M/3M I, 1Y opener) is La Catedral on rally/calm.
        # The finale pedal, or a selloff/volatile session, is Ultimo Tremolo.
        if _is_suite_finale(ctx) or mood in {"selloff", "volatile"}:
            return "tremolo"
        return "preludio"
    if mood == "calm":
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


def _slot_contrast(section) -> tuple[int, bool]:
    """Regime slot, and whether the section is the trio or bridge."""
    if section is None:
        return 0, False
    return section.regime_slot, bool(section.trio or section.bridge)


def _phrase_bar(ctx: _Ctx, index: int) -> int:
    return min(ctx.bars - 1, ctx.phrases[index].start // max(ctx.epb, 1))


def _group_slots(ctx: _Ctx, indexes: list[int]) -> list[tuple[list[int], bool]]:
    """Body phrases grouped by `(regime slot, trio-or-bridge)`, in score order."""
    regions: list[tuple[list[int], bool]] = []
    previous: tuple[int, bool] | None = None
    for index in indexes:
        key = _slot_contrast(ctx.section(_phrase_bar(ctx, index)))
        if key != previous:
            regions.append(([], key[1]))
            previous = key
        regions[-1][0].append(index)
    return regions


def _barrios_palette(ctx: _Ctx, primary: str) -> tuple[str, ...]:
    """Meter row. The opening pattern is the only mood decision.

    `_dominant_pattern` reads the first region's character and passes it as
    `primary`. Later slots do not read mood again. They walk the guests in
    this row. A movement of two parts ends on the first guest. From three
    parts on, the last part reprises `primary`.
    """
    if ctx.bpm < BARRIOS_TREMOLO_MIN_BPM:
        row = ("andante", "thumb_cantabile")
    elif ctx.kind == "6/8" and ctx.bpm > 100:
        if primary == "hemiola":
            row = ("hemiola", "vals", "polca", "tremolo")
        elif primary == "preludio":
            row = ("preludio", "thumb_cantabile", "vals")
        else:
            row = ("polca", "vals", "hemiola", "tremolo")
    elif ctx.kind == "4/4" and ctx.bpm > 100:
        if primary == "tremolo":
            row = ("tremolo", "choro", "preludio", "thumb_cantabile")
        elif primary == "choro":
            row = ("choro", "tremolo", "preludio", "thumb_cantabile")
        else:
            row = ("preludio", "choro", "tremolo", "thumb_cantabile")
    elif primary == "tremolo":
        row = ("tremolo", "preludio", "andante")
    else:
        row = ("preludio", "andante", "tremolo")
    if primary not in row:
        return (primary, *[name for name in row if name != primary])
    start = row.index(primary)
    return row[start:] + row[:start]


def _region_pattern_ids(ctx: _Ctx, patterns: list[str]) -> list[str]:
    """One pattern per formal slot, including the reprise of the opening."""
    indexes: list[int] = []
    for index, pattern in enumerate(patterns):
        if pattern == "pedal" or index >= len(ctx.phrases) or ctx.phrases[index].end <= ctx.phrases[index].start:
            continue
        if ctx.kind_at.get(_phrase_bar(ctx, index), "phrase") in _PEDAL:
            continue
        indexes.append(index)
    return [patterns[group[0]] for group, _contrast in _group_slots(ctx, indexes)]


def _barrios_region_patterns(palette: tuple[str, ...], count: int) -> list[str]:
    """Opening, one guest per middle part, and a reprise from the third part.

    A trio or bridge is just another middle part: it takes the next guest
    instead of restarting the guest row. The last part returns to the opening
    once there are at least three parts, even when that part is marked as a
    trio, so it does not repeat the guest in front of it. Two parts have
    nowhere to return to, and stay opening then guest. A row with a single
    guest repeats that guest in every middle part.
    """
    if count <= 0:
        return []
    guests = palette[1:] or palette[:1]
    chosen: list[str] = []
    episode = 0
    for index in range(count):
        if index == 0 or (count >= 3 and index == count - 1):
            chosen.append(palette[0])
            continue
        chosen.append(guests[episode % len(guests)])
        episode += 1
    return chosen


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
    if ctx.kind == "6/8" and mood != "calm" and phrases and running * 2 >= len(phrases):
        return "preludio" if primary == "vals" else "vals"
    return "andante" if primary == "thumb_cantabile" else "thumb_cantabile"


def _assign_macro(ctx: _Ctx, chosen: list[str], body: list[int]) -> list[str]:
    """Lock the body to one pattern, to A–B–A, or to one pattern per session.

    A long Barrios movement leaves the opening texture for the row that fits
    the meter. Two parts end on the first guest. Three or more reprise the
    opening. `bars` includes warm-up and cool-down, so a short body can still
    take this path once the frame is attached.
    """
    if not body:
        return chosen
    if ctx.ensemble == "barrios" and ctx.bars > 40:
        regions = _group_slots(ctx, body)
        if len(regions) >= 2:
            opening = regions[0][0]
            primary = _dominant_pattern(
                ctx,
                [ctx.phrases[index] for index in opening],
                _phrase_bars(ctx, opening),
            )
            palette = _barrios_palette(ctx, primary)
            row = _barrios_region_patterns(palette, len(regions))
            for (indexes, _contrast), pattern in zip(regions, row):
                for index in indexes:
                    chosen[index] = pattern
            return chosen
    if ctx.bars <= 40 and not _has_contrast_section(ctx):
        pattern = _dominant_pattern(ctx, [ctx.phrases[index] for index in body], _body_bars(ctx))
        for index in body:
            chosen[index] = pattern
        return _settle_galop(ctx, chosen, body)
    if _has_contrast_section(ctx):
        groups: dict[str, list[int]] = {"A": [], "B": []}
        for index in body:
            _slot, contrast = _slot_contrast(ctx.section(_phrase_bar(ctx, index)))
            groups["B" if contrast else "A"].append(index)
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
        return _settle_galop(ctx, chosen, body)
    buckets: dict[int, list[int]] = {}
    for index in body:
        slot, _contrast = _slot_contrast(ctx.section(_phrase_bar(ctx, index)))
        buckets.setdefault(slot, []).append(index)
    for indexes in buckets.values():
        pattern = _dominant_pattern(
            ctx,
            [ctx.phrases[index] for index in indexes],
            _phrase_bars(ctx, indexes),
        )
        for index in indexes:
            chosen[index] = pattern
    return _settle_galop(ctx, chosen, body)


def _body_regions(ctx: _Ctx, body: list[int]) -> list[tuple[bool, list[int]]]:
    """Body phrases in score order, split when the formal slot or the contrast flag changes."""
    regions: list[tuple[bool, list[int]]] = []
    previous: tuple[int, bool] | None = None
    for index in body:
        bar = min(ctx.bars - 1, ctx.phrases[index].start // max(ctx.epb, 1))
        section = ctx.section(bar)
        slot = 0 if section is None else section.regime_slot
        contrast = section is not None and bool(section.trio or section.bridge)
        key = (slot, contrast)
        if key != previous:
            regions.append((contrast, []))
            previous = key
        regions[-1][1].append(index)
    return regions


def _paint(chosen: list[str], indexes: list[int], pattern: str) -> None:
    for index in indexes:
        chosen[index] = pattern


def _galop_centers(count: int) -> set[int]:
    """The middle region, or both regions that share the midpoint when the count is even."""
    if count % 2 == 1:
        return {count // 2}
    mid = count // 2
    return {mid - 1, mid}


def _settle_galop(ctx: _Ctx, chosen: list[str], body: list[int]) -> list[str]:
    """Galop fills a day. A longer movement that is only galop keeps the dance in the middle.

    A one-phrase fixture still renders the dance. A body that already mixes
    galop with other patterns is left alone: the dance is already one part.
    A trio whose outer sections are galop becomes study–galop–study. An even
    run of sessions puts the dance across the boundary of the two middle ones.
    """
    if ctx.ensemble != "classic" or not body:
        return chosen
    if not any(chosen[index] == "galop" for index in body):
        return chosen
    if ctx.bars == 34 or len(body) == 1:
        return chosen
    regions = _body_regions(ctx, body)
    if _has_contrast_section(ctx):
        outer = [index for contrast, indexes in regions if not contrast for index in indexes]
        if outer and all(chosen[index] == "galop" for index in outer):
            for contrast, indexes in regions:
                _paint(chosen, indexes, "galop" if contrast else "study")
        return chosen
    if not all(chosen[index] == "galop" for index in body):
        return chosen
    if len(regions) >= 3:
        centers = _galop_centers(len(regions))
        if len(regions) % 2 == 0:
            _paint_galop_across(chosen, regions, centers)
        else:
            for position, (_contrast, indexes) in enumerate(regions):
                _paint(chosen, indexes, "galop" if position in centers else "study")
        return chosen
    if len(body) == 2:
        chosen[body[0]] = "study"
        chosen[body[1]] = "galop"
        return chosen
    count = len(body)
    opening = max(1, count // 3)
    closing = max(1, count // 3)
    while opening + closing >= count:
        if opening >= closing and opening > 1:
            opening -= 1
        elif closing > 1:
            closing -= 1
        else:
            break
    for offset, index in enumerate(body):
        chosen[index] = "galop" if opening <= offset < count - closing else "study"
    return chosen


def _paint_galop_across(chosen: list[str], regions: list[tuple[bool, list[int]]], centers: set[int]) -> None:
    """Galop straddles the two middle regions. Outer regions stay study."""
    left, right = min(centers), max(centers)
    for position, (_contrast, indexes) in enumerate(regions):
        if position not in centers:
            _paint(chosen, indexes, "study")
            continue
        if len(indexes) < 2:
            _paint(chosen, indexes, "galop")
            continue
        cut = len(indexes) // 2
        if position == left:
            _paint(chosen, indexes[:cut], "study")
            _paint(chosen, indexes[cut:], "galop")
        elif position == right:
            _paint(chosen, indexes[:cut], "galop")
            _paint(chosen, indexes[cut:], "study")


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


def _stamp(events: list[NoteEvent], **flags) -> list[NoteEvent]:
    if not events:
        return events
    return [replace(events[0], **flags), *events[1:]]


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


_SPARSER = {"f": "mf", "mf": "mp", "mp": "p", "p": "p"}
_COLOR_SUSPENDED = frozenset({2, 5, 10})
_COLOR_TERTIAN = frozenset({3, 4, 10, 11})


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
            kept.extend(
                _spell16(
                    begin,
                    start - begin,
                    event.midi,
                    epb,
                    event.voice,
                    event.velocity,
                    tie_in=event.tie_stop,
                )
            )
        if finish > end:
            kept.extend(
                _spell16(
                    end,
                    finish - end,
                    event.midi,
                    epb,
                    event.voice,
                    event.velocity,
                    tie_out=event.tie_start,
                )
            )
    kept.extend(fresh)
    return kept


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
            # Étude No. 1 and Étude No. 11 do not take the Étude No. 7 scale.
            if patterns[index] in {"etude1", "etude11"}:
                continue
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


def _on_sixteenth_grid(event: NoteEvent) -> bool:
    start = event.beat * 4
    dur = event.duration_beats * 4
    return abs(start - round(start)) <= 1e-6 and abs(dur - round(dur)) <= 1e-6


def _resolve(events: list[NoteEvent], epb: int, voice: int) -> list[NoteEvent]:
    timed = []
    odd: list[NoteEvent] = []
    for event in events:
        if event.midi is None:
            continue
        stamped = replace(event, voice=voice, slur_start=False, slur_stop=False)
        # A sextuplet sixth is not an integer on the sixteenth playhead.
        if not _on_sixteenth_grid(event):
            odd.append(stamped)
            continue
        timed.append((_start16(event, epb), _dur16(event), stamped))
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
    resolved.extend(odd)
    return resolved


def _fill(events: list[NoteEvent], bars: int, epb: int, voice: int) -> list[NoteEvent]:
    if any(not _on_sixteenth_grid(event) for event in events):
        return _fill_twelfths(events, bars, epb, voice)
    return _fill_sixteenths(events, bars, epb, voice)


def _fill_sixteenths(events: list[NoteEvent], bars: int, epb: int, voice: int) -> list[NoteEvent]:
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


def _fill_twelfths(events: list[NoteEvent], bars: int, epb: int, voice: int) -> list[NoteEvent]:
    """Fill a voice that contains sextuplet sixths.

    A sixth is two units when a quarter is twelve. Rests of that length stay
    one note. A gap that lands on the sixteenth grid still uses the old speller,
    so an eighth or a quarter rest is not chopped into sixteenths either.
    """
    per_bar = epb * 6
    total = bars * per_bar
    timed = sorted(
        (
            (
                event.bar * per_bar + int(round(event.beat * 12)),
                max(1, int(round(event.duration_beats * 12))),
                index,
                event,
            )
            for index, event in enumerate(events)
        ),
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
            output.extend(_rest_twelfths(cursor, nxt - cursor, epb, voice))
        cursor = nxt
    return output


def _rest_twelfths(start: int, length: int, epb: int, voice: int) -> list[NoteEvent]:
    per_bar = epb * 6
    events: list[NoteEvent] = []
    cursor = start
    left = length
    while left > 0:
        room = per_bar - (cursor % per_bar)
        take = min(left, room)
        if take >= 3 and cursor % 3 == 0 and take % 3 == 0:
            events.extend(_spell16(cursor // 3, take // 3, None, epb, voice))
            cursor += take
            left -= take
            continue
        step = 2 if take >= 2 else take
        if step <= 0:
            break
        bar = cursor // per_bar
        beat = (cursor % per_bar) / 12.0
        events.append(
            NoteEvent(
                bar=bar,
                beat=beat,
                midi=None,
                duration_beats=step / 12.0,
                voice=voice,
            )
        )
        cursor += step
        left -= step
    return events


def _needs_sixteenths(events: list[NoteEvent]) -> bool:
    for event in events:
        start = event.beat * 4
        dur = event.duration_beats * 4
        if abs(start - round(start)) > 1e-6 or abs(dur - round(dur)) > 1e-6:
            return True
        if int(round(start)) % 2 or int(round(dur)) % 2:
            return True
    return False


def _step_playable_and_ordered(
    pitch: int,
    step16: int,
    lead: list[NoteEvent],
    low: list[NoteEvent],
    ctx: _Ctx,
) -> bool:
    bass = [note.midi for note in low if note.midi is not None and _covers(note, step16, ctx.epb)]
    highs = [note.midi for note in lead if note.midi is not None and _covers(note, step16, ctx.epb)]
    if bass and max(bass) >= pitch:
        return False
    if highs and pitch >= min(highs):
        return False
    sounding = [pitch, *bass, *highs]
    return _playable([note + ctx.semitones for note in sounding])


def _valid_prefix_dur(
    pitch: int,
    when: int,
    dur: int,
    lead: list[NoteEvent],
    low: list[NoteEvent],
    ctx: _Ctx,
) -> int:
    valid = 0
    for step in range(when, when + dur):
        if not _step_playable_and_ordered(pitch, step, lead, low, ctx):
            break
        valid += 1
    if valid < dur and valid >= 2 and when % 2 == 0 and dur % 2 == 0:
        valid = (valid // 2) * 2
    return valid


def _fallback_inner(
    ctx: _Ctx,
    chord: Chord,
    sung: int,
    bass: int,
) -> int | None:
    for step_idx in range(4):
        cand = _choose_inner(chord, sung, bass, ctx.mid_low, ctx.mid_high, ctx.semitones, False, step_idx)
        if cand is not None and bass < cand < sung and _playable(
            [bass + ctx.semitones, cand + ctx.semitones, sung + ctx.semitones]
        ):
            return cand
    for open_pitch in (64, 59, 55, 50):
        written = open_pitch - ctx.semitones
        if (
            ctx.mid_low <= written <= ctx.mid_high
            and bass < written < sung
            and _playable([bass + ctx.semitones, written + ctx.semitones, sung + ctx.semitones])
        ):
            return written
    for note in range(min(ctx.mid_high, sung - 1), max(ctx.mid_low, bass + 1) - 1, -1):
        if _on_scale(note, ctx.mode) and _playable(
            [bass + ctx.semitones, note + ctx.semitones, sung + ctx.semitones]
        ):
            return note
    return None


def _repair(ctx: _Ctx, lead: list[NoteEvent], support: list[NoteEvent], low: list[NoteEvent]) -> tuple[list, list, list]:
    """Shift, trim, or drop an inner note that cannot share a hand position with bass and melody."""
    if ctx.ensemble == "bach":
        low = _bach_keep_bass_below(ctx, lead, low)
    repaired: list[NoteEvent] = []
    for event in support:
        if event.midi is None:
            continue
        if not _on_sixteenth_grid(event):
            repaired.append(event)
            continue
        when = _start16(event, ctx.epb)
        dur = max(1, _dur16(event))
        valid_dur = _valid_prefix_dur(event.midi, when, dur, lead, low, ctx)
        if valid_dur == dur:
            repaired.append(event)
            continue
        if valid_dur >= 2:
            repaired.extend(_spell16(when, valid_dur, event.midi, ctx.epb, 2, event.velocity, event.accent))
            continue
        bass = _sounding_midi(low, when // 2, ctx.epb) or ctx.bass_low
        sung = _sounding_midi(lead, when // 2, ctx.epb) or ctx.treble_top
        tone = _fallback_inner(ctx, ctx.chord(event.bar), sung, bass)
        if ctx.ensemble == "bach":
            if tone is not None and _valid_prefix_dur(tone, when, dur, lead, low, ctx) == dur:
                repaired.append(replace(event, midi=tone))
            elif valid_dur > 0:
                repaired.extend(_spell16(when, valid_dur, event.midi, ctx.epb, 2, event.velocity, event.accent))
            continue
        if tone is not None:
            tone_dur = _valid_prefix_dur(tone, when, dur, lead, low, ctx)
            if tone_dur == dur:
                repaired.append(replace(event, midi=tone))
                continue
            if tone_dur > 0:
                repaired.extend(_spell16(when, tone_dur, tone, ctx.epb, 2, event.velocity, event.accent))
                continue
        if valid_dur > 0:
            repaired.extend(_spell16(when, valid_dur, event.midi, ctx.epb, 2, event.velocity, event.accent))
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


def _tremolo_region_arch(bars: set[int], bar: int) -> int:
    """Slow arch across one contiguous tremolo run. Both ends add 0."""
    start = bar
    while start - 1 in bars:
        start -= 1
    end = bar
    while end + 1 in bars:
        end += 1
    count = end - start + 1
    if count <= 1:
        return 0
    position = (bar - start) / (count - 1)
    return round(6 * math.sin(math.pi * position))


def _tremolo_shift(ctx: _Ctx, bars: set[int], bar: int, thumbs: list[NoteEvent]) -> int:
    """Region arch plus band, clamped so every thumb in the bar stays in 44–72."""
    shift = _tremolo_region_arch(bars, bar) + _TREMOLO_BAND.get(ctx.band(bar), 0)
    levels = [event.velocity for event in thumbs if event.velocity is not None]
    if not levels:
        return shift
    return min(max(shift, 44 - min(levels)), 72 - max(levels))


def _shift_velocity(events: list[NoteEvent], amount: int) -> list[NoteEvent]:
    if amount == 0:
        return list(events)
    shifted: list[NoteEvent] = []
    for event in events:
        if event.velocity is None:
            shifted.append(event)
        else:
            shifted.append(replace(event, velocity=event.velocity + amount))
    return shifted


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
        if event.midi is None or _start16(event, epb) != eighth * 2:
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


def contrast_id(ctx: _Ctx, patterns: list[str]) -> str:
    """The pattern written in the trio or bridge. Empty when that section is absent."""
    for index, pattern in enumerate(patterns):
        if pattern == "pedal" or index >= len(ctx.phrases):
            continue
        bar = min(ctx.bars - 1, ctx.phrases[index].start // max(ctx.epb, 1))
        section = ctx.section(bar)
        if section is None or getattr(section, "kind", None) in _PEDAL:
            continue
        _slot, contrast = _slot_contrast(section)
        if contrast:
            return pattern
    return ""


def form_pattern_ids(ctx: _Ctx, patterns: list[str]) -> list[str]:
    """One written pattern, or the slot row of a framed long Barrios movement.

    `_assign_macro` writes that row only when the score has a frame. An
    unframed movement longer than 40 bars still chose each phrase on its own,
    so the title must not group those phrases. A row of one id falls back to
    the headline instead of repeating that id.
    """
    if not patterns:
        return []
    if ctx.ensemble == "barrios" and ctx.bars > 40 and _framed(ctx):
        successive = _region_pattern_ids(ctx, patterns)
        if len(successive) >= 2 and len(set(successive)) >= 2:
            return successive
    primary = headline_id(ctx, patterns)
    if not primary or primary == "pedal":
        return []
    if not _has_contrast_section(ctx):
        return [primary]
    contrast = contrast_id(ctx, patterns)
    if not contrast or contrast == primary or contrast == "pedal":
        return [primary]
    return [primary, contrast, primary]


def headline_id(ctx: _Ctx, patterns: list[str]) -> str:
    """The pattern a movement is named for: the main body, not its contrast."""
    fallback = {"classic": "study", "villa": "villa_pattern", "brouwer": "brouwer_etude", "bach": "bach_bourree"}.get(
        ctx.ensemble, "preludio"
    )
    if not patterns:
        return fallback
    if _has_contrast_section(ctx):
        for index, pattern in enumerate(patterns):
            if pattern == "pedal" or index >= len(ctx.phrases):
                continue
            _slot, contrast = _slot_contrast(ctx.section(_phrase_bar(ctx, index)))
            if contrast:
                continue
            return pattern
    counts: dict[str, int] = {}
    first: str | None = None
    for bar in range(ctx.bars):
        if ctx.kind_at.get(bar, "phrase") in _PEDAL:
            continue
        name = _bar_pattern(ctx, bar, patterns)
        if name == "pedal":
            continue
        if first is None:
            first = name
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return first or fallback
    return max(counts, key=lambda name: (counts[name], name == first))


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
    bar_volumes: list[float] | None = None,
    section_rel_spans: dict | None = None,
    impulses: tuple = (),
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
        bar_volumes=None if bar_volumes is None else list(bar_volumes),
        section_rel_spans=None if section_rel_spans is None else dict(section_rel_spans),
        impulses=tuple(impulses or ()),
    )
    patterns = _patterns(ctx) if phrases else []
    headline = _HEADLINE.get()
    if headline is not None:
        headline.append(headline_id(ctx, patterns))
    form = _FORM.get()
    if form is not None:
        form.append(form_pattern_ids(ctx, patterns))
    if _SKIP_VOICES.get():
        return [], [], [], 2
    _fit_elegiaque_melody(ctx, patterns)
    levels = _grand_levels(ctx, patterns)
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
            bar_low = [event for event in trem_bass if event.bar == bar and event.midi is not None]
            shift = _tremolo_shift(ctx, tremolo_bars, bar, bar_low)
            lead.extend(_shift_velocity([event for event in trem_lead if event.bar == bar and event.midi is not None], shift))
            support.extend(_shift_velocity([event for event in trem_inner if event.bar == bar and event.midi is not None], shift))
            low.extend(_shift_velocity(bar_low, shift))
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
        elif pattern == "etude1":
            part_lead, part_support, part_low = _render_etude1_bar(
                ctx, bar, phrase_here, _leaving_pattern(ctx, bar, patterns)
            )
            lead.extend(part_lead)
            support.extend(part_support)
            low.extend(part_low)
        elif pattern == "etude11":
            part_lead, part_support, part_low = _render_etude11_bar(
                ctx, bar, phrase_here, _leaving_pattern(ctx, bar, patterns)
            )
            lead.extend(part_lead)
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
            bar_ornaments = ornaments.get(owner) if owner is not None else None
            part_support, part_low = _render_elegiaque_bar(
                ctx, bar, phrase, descend, ornaments=bar_ornaments
            )
            part_lead = _sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, phrase=phrase)
            if bar_ornaments and any(
                bar * epb <= eighth < (bar + 1) * epb for eighth in bar_ornaments
            ):
                part_lead = _apply_appoggiatura(ctx, part_lead, bar_ornaments)
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
            part_support, part_low, accent_at, figure = _render_sarabande_bar(
                ctx, bar, phrase_here, lead
            )
            cuts = {bar * epb + accent_at}
            if figure:
                cuts.add(_start16(figure[0], epb) // 2)
            part_lead = _sustain(ctx.melody, bar * epb, (bar + 1) * epb, epb, apex, cuts, phrase_here)
            if figure:
                part_lead = _splice(part_lead, _start16(figure[0], epb), (bar + 1) * epb * 2, figure, epb)
            accent_eighth = bar * epb + accent_at
            # A swarm attack on the accent is a hairpin step. Bass and inner
            # punches stay inside `_render_sarabande_bar`.
            if not figure or _start16(figure[0], epb) > accent_eighth * 2:
                part_lead = _punch(part_lead, accent_eighth, epb, amount=8)
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
        support = _apply_campanella(ctx, support, lead, ringing, low)
    from app.sonify.guitar_scale_passages import (
        apply_scale_passages,
        clear_scale_slurs,
        sounding_swarm_eighths,
    )

    lead, support, low, scale_plan = apply_scale_passages(ctx, patterns, lead, support, low)
    scale_eighths = set(scale_plan.scale_eighths)
    perpetual_bars = set(scale_plan.perpetual_bars)
    perpetual_indexes: set[int] = set()
    for index, phrase in enumerate(phrases):
        if phrase.end <= phrase.start:
            continue
        first_bar = phrase.start // epb
        last_bar = max(phrase.end - 1, phrase.start) // epb
        if any(bar in perpetual_bars for bar in range(first_bar, last_bar + 1)):
            perpetual_indexes.add(index)
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
                and index not in perpetual_indexes
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
    bell_bars -= {eighth // epb for eighth in scale_eighths}
    lead, support = _insert_bells(ctx, lead, support, bell_bars)
    for bar in _fanfare_bars(ctx, levels):
        lead, support, low = _apply_fanfare(ctx, lead, support, low, bar)
    relaxed: set[int] = set()
    if _framed(ctx):
        lead, support, low = _strip_pedal(ctx, lead, support, low)
        lead, support, low = _paint_frames(ctx, patterns, lead, support, low)
        lead, support, low, relaxed = _smooth_boundaries(
            ctx, patterns, lead, support, low, scale_eighths
        )
    else:
        lead, support, low = _transitions(ctx, patterns, levels, lead, support, low, scale_eighths)
    for eighth in _caesura_eighths(ctx, levels):
        if eighth in scale_eighths:
            continue
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
    # Boundary pickups and caesuras already ran against passage eighths only.
    # Swarm eighths join the slur and dynamics sets now, and stay out of bell_bars.
    protected_eighths = set(scale_eighths) | sounding_swarm_eighths(ctx, patterns, scale_eighths)
    lead = clear_scale_slurs(lead, protected_eighths, epb)
    lead, support, low = _shape_dynamics(
        ctx, lead, support, low, relaxed, patterns, protected_eighths
    )
    written_lead = list(lead)
    from app.sonify.guitar_wave import apply_guitar_wave

    lead, support, low = apply_guitar_wave(ctx, lead, support, low, patterns, relaxed)
    from app.sonify.guitar_scale_passages import restamp_passage_hairpins

    lead = _restamp_swarm_hairpins(ctx, patterns, lead, written_lead)
    lead = restamp_passage_hairpins(ctx, patterns, scale_plan, lead, written_lead)
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
    # A movement with any Étude No. 11 phrase engraves on the twelfth grid.
    # A sixteenth of Étude No. 1 is then three units, and a sextuplet sixth is two.
    if "etude11" in patterns:
        divisions = 12
    return (
        _fill(lead, musical_bars, epb, 1),
        _fill(support, musical_bars, epb, 2),
        _fill(low, musical_bars, epb, 3),
        divisions,
    )


def _leaving_pattern(ctx: _Ctx, bar: int, patterns: list[str]) -> bool:
    """The last bar of a phrase breathes when the next phrase is a different pattern."""
    owner = _owner(ctx, bar)
    if owner is None or owner >= len(patterns):
        return False
    phrase = ctx.phrases[owner]
    if bar != (max(phrase.end - 1, phrase.start) // ctx.epb):
        return False
    for later in range(owner + 1, len(patterns)):
        return patterns[later] != patterns[owner]
    return False


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


def _joined_body_pattern(ctx: _Ctx, bar: int, patterns: list[str]) -> tuple[str, int | None]:
    """Pattern of the body bar joined to a pedal region, else the movement headline."""
    if 0 <= bar < ctx.bars and ctx.kind_at.get(bar, "phrase") not in _PEDAL:
        name = _bar_pattern(ctx, bar, patterns)
        if name != "pedal":
            return name, bar
        return headline_id(ctx, patterns), bar
    return headline_id(ctx, patterns), None


_PEDAL_DOOR_PROFILE = {
    "thumb_cantabile": "thumb_cantabile",
    "elegiaque": "elegiaque",
    "choro": "barrios_dance",
}


def profiles_for(ctx: _Ctx, patterns: list[str]) -> dict[int, str]:
    """Playability profile of every bar. Pedal bars take the joined door, not `"pedal"`."""
    leading, trailing = _pedal_regions(ctx)
    intro_name = _joined_body_pattern(ctx, leading[-1] + 1, patterns)[0] if leading else "study"
    outro_name = _joined_body_pattern(ctx, trailing[0] - 1, patterns)[0] if trailing else "study"
    intro_profile = _PEDAL_DOOR_PROFILE.get(intro_name, "study")
    outro_profile = _PEDAL_DOOR_PROFILE.get(outro_name, "study")
    opening = set(leading)
    closing = set(trailing)
    found: dict[int, str] = {}
    for bar in range(ctx.bars):
        if bar in opening:
            found[bar] = intro_profile
        elif bar in closing:
            found[bar] = outro_profile
        else:
            found[bar] = _PROFILE.get(_bar_pattern(ctx, bar, patterns), "study")
    return found


def _restamp_swarm_hairpins(ctx: _Ctx, patterns, lead, written_lead):
    """Reprint each sarabande swarm after the volume wave.

    The curve is taken from the pre-wave lead, so a hat that opened at 72
    is not left on the sarabande ceiling.
    """
    for bar in range(ctx.bars):
        if _bar_pattern(ctx, bar, patterns) != "sarabande":
            continue
        owner = _owner(ctx, bar)
        phrase = ctx.phrases[owner] if owner is not None else None
        _support, _low, _accent, figure = _render_sarabande_bar(ctx, bar, phrase, written_lead)
        if not figure:
            continue
        figure = [replace(event, hairpin=True) if event.midi is not None else event for event in figure]
        lead = _splice(lead, _start16(figure[0], ctx.epb), (bar + 1) * ctx.epb * 2, figure, ctx.epb)
    return lead


def _paint_frames(ctx: _Ctx, patterns, lead, support, low):
    from app.sonify.guitar_frame import render_intro, render_outro

    leading, trailing = _pedal_regions(ctx)
    if leading:
        intro_pattern, _body = _joined_body_pattern(ctx, leading[-1] + 1, patterns)
        part_lead, part_support, part_low = render_intro(ctx, leading, intro_pattern)
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)
    if trailing:
        outro_pattern, _body = _joined_body_pattern(ctx, trailing[0] - 1, patterns)
        part_lead, part_support, part_low = render_outro(ctx, trailing, outro_pattern)
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


def _plant_pickup(
    ctx: _Ctx,
    lead,
    support,
    low,
    bar: int,
    *,
    cover_eighth: bool = False,
    keep_approach: bool = False,
):
    eighth = (bar + 1) * ctx.epb - 1
    if keep_approach and bar + 1 < ctx.bars:
        nxt_root_pc = ctx.chord(bar + 1).pitches[0] % 12
        upper = _eighth_pitches(ctx, [*support, *lead], eighth, cover_eighth=cover_eighth)
        ceiling = min(upper) if upper else None
        for event in low:
            if (
                event.midi is not None
                and _start16(event, ctx.epb) == eighth * 2
                and (event.midi + ctx.semitones) % 12 == (nxt_root_pc - 1) % 12
                and (ceiling is None or event.midi < ceiling)
                and _playable([event.midi + ctx.semitones, *(pitch + ctx.semitones for pitch in upper)])
            ):
                return lead, support, low
    low = _silence(low, eighth, ctx.epb)
    pitch = _safe_pickup(ctx, bar, support, lead, low, cover_eighth=cover_eighth)
    low.extend(_eighth_event(eighth, 1, pitch, ctx.epb, 3, 50))
    return lead, support, low


def _smooth_boundaries(ctx: _Ctx, patterns, lead, support, low, scale_eighths: set[int] | None = None):
    relaxed: set[int] = set()
    protected = scale_eighths or set()
    for bar in _boundary_bars(ctx, patterns):
        pattern = _bar_pattern(ctx, bar, patterns)
        half = max(1, ctx.epb // 2)
        window = range((bar + 1) * ctx.epb - half, (bar + 1) * ctx.epb)
        if (
            ctx.kind_at.get(bar, "phrase") not in _PEDAL
            and (pattern == "tremolo" or pattern in _DANCE)
            and not protected.intersection(window)
        ):
            lead, support, low, eased = _relax_texture(ctx, lead, support, low, bar)
            relaxed.update(eased)
        # The last sixteenth of *La Catedral* is an inner note. The pickup bass
        # has to share a hand with that note, not only with the canto attack.
        cover = _catedral_preludio(ctx) and pattern == "preludio"
        keep_approach = pattern == "villa_pattern" and ctx.band(bar) == "f"
        # The etudes already breathe on the last beat. A pickup would cut that bass.
        # Pedal bars keep the frame's own anacrusis. A scale arrival on the last
        # eighth keeps its own bass. The last body bar before the outro still
        # relaxes and takes the pickup.
        if (
            pattern not in {"etude1", "etude11"}
            and ctx.kind_at.get(bar, "phrase") not in _PEDAL
            and (bar + 1) * ctx.epb - 1 not in protected
        ):
            lead, support, low = _plant_pickup(
                ctx, lead, support, low, bar, cover_eighth=cover, keep_approach=keep_approach
            )
    return lead, support, low, relaxed


# Tremolo's quarter arch already includes one band step. Do not add another
# on the way into the volume wave.
_TREMOLO_BAND = {"p": -6, "mp": -3, "mf": 0, "f": 3}


def _shape_dynamics(
    ctx: _Ctx,
    lead,
    support,
    low,
    relaxed: set[int],
    patterns: list[str] | None = None,
    scale_eighths: set[int] | None = None,
):
    """Add the phrase's extra (0..+4) and leave the written offsets in place.

    The printed band is not added here. The volume wave owns that tide, so a
    `p` bar and an `f` bar with the same center produce the same shift.
    Etude cells and tremolo already carry their own arch; a second extra or
    band step would move those offsets before the affine reads them.
    Lead attacks on a scale passage or a sarabande swarm keep the hairpin.
    """
    protected = scale_eighths or set()
    pedal = set(_pedal_regions(ctx)[0]) | set(_pedal_regions(ctx)[1])

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
            if voice == "lead" and eighth in protected:
                shaped.append(event)
                continue
            if eighth in relaxed:
                shaped.append(event)
                continue
            if patterns is not None and _bar_pattern(ctx, event.bar, patterns) in {"etude1", "etude11", "tremolo"}:
                shaped.append(event)
                continue
            phrase = phrase_at(eighth)
            if phrase is None:
                shaped.append(event)
                continue
            extra = round(4 * swell(phrase, min(max(eighth, phrase.start), phrase.end - 1)))
            if extra == 0:
                shaped.append(event)
                continue
            shaped.append(replace(event, velocity=event.velocity + extra))
        return shaped

    return shape(lead, "lead"), shape(support, "support"), shape(low, "low")


def _transitions(ctx, patterns, levels, lead, support, low, scale_eighths: set[int] | None = None):
    protected = scale_eighths or set()
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
        # The etudes breathe inside the bar: the last beat keeps its bass, and
        # Étude No. 11 also keeps the melody of that last sextuplet.
        if (
            eighth not in protected
            and patterns[left] not in {"etude1", "etude11"}
            and (held_ending or (running_ending and different_family and phrase.end - phrase.start >= 4))
        ):
            lead = _silence(lead, eighth, ctx.epb)
            support = _silence(support, eighth, ctx.epb)
        high = patterns[right] in {"tremolo", *_DANCE} or (
            patterns[right] == "study" and right in levels
        )
        if (
            eighth not in protected
            and patterns[left] in _CHORALE
            and high
            and eighth not in _caesura_eighths(ctx, levels)
        ):
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
            if voice == 2 and sounding < 50 and profile not in {"villa_etude1", "villa_etude11"}:
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
                etude = profile in {"villa_etude1", "villa_etude11"}
                if not high_block and not thumb and not etude:
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


# Composer-specific pattern modules
from app.sonify.guitar_bach import (  # noqa: E402
    _approach_eighths,
    _bach_bass,
    _bach_bass_high,
    _bach_contrast,
    _bach_keep_bass_below,
    _bach_lag_bar,
    _bach_lead_high,
    _bach_opens,
    _bach_primary,
    _bariolage_pair,
    _bourree_cells,
    _chaconne_bass_slots,
    _chaconne_beats,
    _covers_upper,
    _fitting_scale,
    _fuga_bass_ok,
    _fuga_motif,
    _fuga_pitch,
    _gavotte_tail_bass,
    _gigue_plan,
    _hold_at,
    _lead_during,
    _mordent_events,
    _ornament_neighbor,
    _quarter_ok,
    _render_bach_bourree_bar,
    _render_bach_chaconne_bar,
    _render_bach_fuga_bar,
    _render_bach_gavotte_bar,
    _render_bach_gigue_bar,
    _render_bach_sarabande_bar,
    _sarabande_ornament,
    _sarabande_passes,
    _sarabande_pitch,
    _scale_cell,
    _treble_step,
)
from app.sonify.guitar_sor import (  # noqa: E402
    _apply_appoggiatura,
    _apply_fanfare,
    _caesura_eighths,
    _classic_macro,
    _dotted_pair,
    _fanfare_bars,
    _fit_elegiaque_melody,
    _galop_bass_points,
    _galop_inner_offsets,
    _galop_leap,
    _galop_sparkle,
    _grand_levels,
    _march_grid,
    _mozart_bass_plan,
    _mozart_bridge_notes,
    _mozart_inner,
    _mozart_offsets,
    _mozart_pool,
    _mozart_valid_bridge,
    _phrase_appoggiatura,
    _render_cantabile,
    _render_elegiaque_bar,
    _render_galop_bar,
    _render_mozart_var_bar,
    _render_plain_arpeggio,
    _render_study_bar,
    _replace_eighth,
    _same_family,
    _short_pair,
    _signature,
    _step_below,
    _step_down,
)
from app.sonify.guitar_barrios import (  # noqa: E402
    _andante_grid,
    _apply_perpetual,
    _approach_pitch,
    _bell_groups,
    _bell_pitch,
    _bell_slot,
    _bells_here,
    _catedral_bass,
    _catedral_canto_ceiling,
    _catedral_canto_pair,
    _catedral_canto_pitch,
    _catedral_cell,
    _catedral_descend,
    _catedral_emit_support,
    _catedral_glass_tones,
    _catedral_lead_note,
    _catedral_open,
    _catedral_playable_tones,
    _catedral_preludio,
    _catedral_rank_glass,
    _catedral_schedule,
    _catedral_tail,
    _catedral_wave,
    _catedral_whisper,
    _daily_barrios_pattern,
    _dance_exit,
    _dance_ranked,
    _dance_velocity,
    _events_from_slots,
    _fifth_down,
    _finish_dance_grid,
    _held_bars,
    _insert_bells,
    _lead_attacks,
    _lead_bar,
    _perpetual_bars,
    _preludio_anchor,
    _preludio_bass,
    _preludio_inner,
    _pulse_bass,
    _render_catedral_preludio_bar,
    _render_choro_bar,
    _render_hemiola_bar,
    _render_polca_bar,
    _render_vals_bar,
    _slot_dance,
    _tone_below,
)
from app.sonify.guitar_villa import (  # noqa: E402
    _accent_at,
    _chord_grid,
    _place_thumb,
    _render_etude1_bar,
    _render_etude11_bar,
    _render_thumb,
    _render_villa_bar,
    _thumb_offsets,
    _upper_dyad,
    _villa_bass,
    _villa_wave,
)
from app.sonify.guitar_brouwer import (  # noqa: E402
    _brouwer_contrast,
    _brouwer_open_tones,
    _brouwer_primary,
    _brouwer_wave,
    _color_inner,
    _elogio_offsets,
    _etude_cells,
    _modal_figure,
    _render_elogio_bar,
    _render_etude_bar,
    _render_noviembre_bar,
    _render_sarabande_bar,
    _sarabande_points,
    _sarabande_swarms,
    _swarm_line,
)
