"""One nylon guitar, three voices.

The price is the top voice. A phrase locks one right-hand pattern: an opening
arpeggio, Barrios tremolo, or that composer's chorale (Andante, chord-melody,
Élégiaque). Pedal bars stay a ringing root under the melody. All three voices
read the written guitar bounds from the active register, so a transposed key
stays inside the same sounding range.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from app.sonify.chords import Chord
from app.sonify.form import FormSection, active_meter
from app.sonify.keys import MovementCharacter, active_register
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import MIN_RISE, Phrase, quantize_strong_beats, written
from app.sonify.quantize import C_MAJOR_PCS, C_NATURAL_MINOR_PCS, scale_from_classes

GUITAR_BPM = {"classic": 88, "villa": 100, "barrios": 120}
# Listening tests: a tremolo only reads as a sung line from 90 BPM up, sits
# best around 120, and can run to 140. A Barrios movement under that floor
# is not sped up and gets no tremolo at all: it keeps its slow tempo and
# sings the Andante chorale. The daily tempo is the 120 middle of the range.
BARRIOS_TREMOLO_MIN_BPM = 90
BARRIOS_TREMOLO_MAX_BPM = 140
# Last two quarter-notes of a long tremolo phrase, in eighths.
_TAIL_EIGHTHS = 4
_FAMILY = {
    "arpeggio": "arpeggio",
    "tremolo": "tremolo",
    "andante": "chorale",
    "chord_melody": "chorale",
    "elegiaque": "chorale",
}
# Élégiaque plucks one study-density step fewer inner notes.
_SPARSER = {"f": "mf", "mf": "mp", "mp": "p", "p": "p"}
_THIRDS_AND_SEVENTHS = frozenset({3, 4, 10, 11})
_SUSPENDED_COLORS = frozenset({2, 5, 10})
_PEDAL = frozenset({"intro", "outro", "warmup", "cooldown"})
# 64 is mp on the nylon voice, still under the bright nail layer. The apex
# alone lifts. The thumb stays under the line so the downbeat is not the attack.
_MELODY = 64
_MELODY_APEX = 72
_INNER = 56
_BASS = 60
_SHIFTS = (0, -12, 12, -24)
_OVERFLOW_COST = 50
_REVERSAL_COST = 80
_LARGE_LEAP_COST = 400
_LARGE_LEAP = 9
# Cap on melody attacks the nylon voice may play as a hammer-on. A hammer is
# an exception for a stressed note, never a texture: keep it under 5%.
_HAMMER_SHARE = 0.04
# Inside one p-a-m-i cluster the fingers sit at a=52, m=55, i=54 (the fourth
# sixteenth is a again), under the thumb at 58, the strongest attack.
_TREMOLO_FILL_PATTERN = (52, 55, 54, 52)
# The thumb strikes every cluster (root and fifth together) and rings the
# whole quarter, so the bass line stays focused under the fill instead of
# scattering between sparse, soft attacks.
_TREMOLO_THUMB = 58
# The fill repeats sing around mp, back at the written melody velocity.
# The distribution inside the cluster stays as approved; only the level
# moves.
# One tremolo cluster is one quarter note: four sixteenth repeats of a single
# melody pitch, with the thumb ringing underneath for the whole quarter.
_TREMOLO_CLUSTER = 4


def render_guitar_score(
    *,
    title: str,
    chosen: tuple,
    sample_indexes: tuple[int, ...] | None,
    slots: tuple,
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    dynamics: tuple[DynamicEvent, ...],
    bands: list[str],
    band_at: dict[int, str],
    musical_bars: int,
    total_eighths: int,
    bpm: int,
    ensemble: str,
    harmonies: tuple[HarmonyEvent, ...],
    mode: str = "major",
    character: MovementCharacter | None = None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None = None,
    sections: tuple[FormSection, ...] = (),
) -> Score:
    meter = active_meter()
    register = active_register()
    epb = meter.eighths_per_bar
    chord_at = {bar: slot.chord for slot in slots for bar in slot.bars()}
    kind_at = {bar: slot.section for slot in slots for bar in slot.bars()}
    melody = _place_melody(
        pitches,
        phrases,
        register.guitar_treble_floor,
        register.guitar_treble_top,
        chord_at,
        mode,
    )
    pattern_of, tail_at = _phrase_patterns(
        phrases,
        melody,
        kind_at,
        band_at,
        character,
        character_at,
        bpm,
        ensemble,
        mode,
        _trio_bars(sections),
        epb,
    )
    rolling = ensemble == "villa"
    tresillo = (
        _tresillo_bars(musical_bars, epb, band_at, character, character_at) if rolling else set()
    )
    lead_tones: list[_Tone] = []
    support_tones: list[_Tone] = []
    bass_tones: list[_Tone] = []
    lead_sixteenths: list[NoteEvent] = []
    # Tremolo thumb notes are already quarter-length attacks. Engraving them
    # again would split the 6/8 cluster that crosses the dotted-quarter break.
    bass_clusters: list[NoteEvent] = []
    ornaments = {
        index: _appoggiatura(phrase, melody, mode)
        for index, phrase in enumerate(phrases)
        if pattern_of.get(index) == "elegiaque"
    }
    elegy_prev: dict[int, int | None] = {}
    bounds = (
        register.guitar_floor,
        register.guitar_bass_top,
        register.guitar_mid_low,
        register.guitar_mid_high,
    )
    for bar in range(musical_bars):
        bar_start = bar * epb
        bar_end = min(bar_start + epb, total_eighths)
        if bar_end <= bar_start:
            continue
        if kind_at.get(bar, "phrase") in _PEDAL:
            lead_tones.extend(_melody_tones(melody, bar_start, bar_end, phrases))
            if bar in chord_at:
                bass_tones.append(
                    _Tone(bar_start, bar_end - bar_start, _root(chord_at[bar], bounds[0], bounds[1]), _BASS)
                )
            continue
        cursor = bar_start
        while cursor < bar_end:
            index = _phrase_index(phrases, cursor)
            if index is None:
                stop = bar_end
                for phrase in phrases:
                    if cursor < phrase.start < stop:
                        stop = phrase.start
                if stop <= cursor:
                    break
                _lay_arpeggio(
                    cursor,
                    stop,
                    melody,
                    phrases,
                    chord_at,
                    band_at,
                    rolling,
                    tresillo,
                    bounds,
                    lead_tones,
                    support_tones,
                    bass_tones,
                    anchor=False,
                )
                cursor = stop
                continue
            phrase = phrases[index]
            stop = min(bar_end, phrase.end)
            if stop <= cursor:
                break
            pattern = pattern_of.get(index, "arpeggio")
            tail = tail_at.get(index)
            if pattern == "tremolo" and tail is not None and cursor < tail < stop:
                _lay_tremolo(
                    cursor,
                    tail,
                    melody,
                    chord_at,
                    bounds,
                    lead_sixteenths,
                    support_tones,
                    bass_clusters,
                )
                cursor = tail
                continue
            region = "tremolo_tail" if pattern == "tremolo" and tail is not None and cursor >= tail else pattern
            if region == "tremolo":
                _lay_tremolo(
                    cursor,
                    stop,
                    melody,
                    chord_at,
                    bounds,
                    lead_sixteenths,
                    support_tones,
                    bass_clusters,
                )
            elif region == "tremolo_tail":
                _lay_arpeggio(
                    cursor,
                    stop,
                    melody,
                    phrases,
                    chord_at,
                    band_at,
                    False,
                    set(),
                    bounds,
                    lead_tones,
                    support_tones,
                    bass_tones,
                    anchor=True,
                )
            elif region in {"andante", "chord_melody"}:
                _lay_chorale(
                    cursor,
                    stop,
                    region,
                    phrase,
                    melody,
                    phrases,
                    chord_at,
                    bounds,
                    lead_tones,
                    support_tones,
                    bass_tones,
                )
            elif region == "elegiaque":
                _lay_elegiaque(
                    cursor,
                    stop,
                    index,
                    phrase,
                    melody,
                    phrases,
                    ornaments.get(index, {}),
                    chord_at,
                    band_at,
                    mode,
                    bounds,
                    elegy_prev,
                    lead_tones,
                    support_tones,
                    bass_tones,
                )
            else:
                _lay_arpeggio(
                    cursor,
                    stop,
                    melody,
                    phrases,
                    chord_at,
                    band_at,
                    rolling,
                    tresillo,
                    bounds,
                    lead_tones,
                    support_tones,
                    bass_tones,
                    anchor=False,
                )
            cursor = stop
    for eighth in _breath_eighths(phrases, melody, pattern_of, kind_at, epb):
        lead_tones = _cut_tones(lead_tones, eighth)
        support_tones = _cut_tones(support_tones, eighth)
        lead_sixteenths = _cut_sixteenths(lead_sixteenths, eighth, epb)
    lead = _slur([*_engrave(lead_tones), *lead_sixteenths], phrases)
    support = _engrave(support_tones)
    low = [*_engrave(bass_tones), *bass_clusters]
    lead = _fill_voice(lead, total_eighths, epb)
    support = _fill_voice(support, total_eighths, epb)
    low = _fill_voice(low, total_eighths, epb)
    # One divisions value for the movement: sixteenths anywhere (a Barrios
    # tremolo at 90–140, including a phrase that only tremolos before its tail)
    # put the pedal, arpeggio, chorale, and tail on that same grid.
    divisions = 4 if lead_sixteenths else 2
    return Score(
        title=title,
        bpm=bpm,
        bars=musical_bars,
        regimes=chosen,  # type: ignore[arg-type]
        regime_samples=sample_indexes if sample_indexes is None else tuple(sample_indexes[:3]),  # type: ignore[arg-type]
        slots=slots,
        high=(),
        lead=_voice(lead, 1),
        support=_voice(support, 2),
        comp=(),
        low=_voice(low, 3),
        dynamics=dynamics,
        harmonies=harmonies,
        liquidity=tuple(bands),
        phrases=phrases,
        lead_wedges=(),
        support_wedges=(),
        lead_dynamics=(),
        support_dynamics=(),
        variant="guitar",
        ensemble=ensemble,  # type: ignore[arg-type]
        mode=mode,  # type: ignore[arg-type]
        divisions=divisions,
        beats=meter.beats,
        beat_type=meter.beat_type,
        bar_beats=meter.quarter_beats,
    )


def _place_melody(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    floor: int,
    top: int,
    chord_at: dict[int, Chord],
    mode: str,
) -> list[int]:
    """Shift each phrase by octaves, then compress whatever still sticks out.

    Folding a leftover note by itself reverses the price. The compression maps
    scale degrees in order, so a rise stays a rise. A phrase already inside
    the window stays put: shift 0 wins a tie with +12.
    """
    if mode == "minor":
        # The line arrives with its leading tone raised (B natural over the
        # dominant), but the guitar scale here is natural minor. Flatten the
        # leading tone back before placing; the strong-beat quantize below
        # raises it again exactly where the dominant chord wants it. Without
        # this, a phrase carrying B natural fits no shift candidate and the
        # quantize lookup crashes on the off-scale note.
        pitches = [note - 1 if note % 12 == 11 else note for note in pitches]
    scale = _melody_scale(mode)
    degree = {note: index for index, note in enumerate(scale)}
    usable = [phrase for phrase in phrases if phrase.end > phrase.start]
    chosen = _choose_shifts(pitches, tuple(usable), floor, top, degree, scale)
    placed = list(pitches)
    covered: set[int] = set()
    for phrase, line in chosen:
        for offset, note in enumerate(line):
            placed[phrase.start + offset] = note
            covered.add(phrase.start + offset)
    for index, note in enumerate(placed):
        if index not in covered:
            placed[index] = _clamp(note, floor, top)
    window = tuple(note for note in scale if floor <= note <= top)
    if window and chord_at and placed:
        placed = quantize_strong_beats(placed, chord_at, window, mode)
    return placed


def _melody_scale(mode: str) -> tuple[int, ...]:
    classes = C_NATURAL_MINOR_PCS if mode == "minor" else C_MAJOR_PCS
    return scale_from_classes(24, 120, classes)


def _choose_shifts(
    pitches: list[int],
    phrases: tuple[Phrase, ...],
    floor: int,
    top: int,
    degree: dict[int, int],
    scale: tuple[int, ...],
) -> list[tuple[Phrase, list[int]]]:
    if not phrases:
        return []
    candidates = [
        _phrase_candidates(pitches[phrase.start : phrase.end], floor, top, degree, scale)
        for phrase in phrases
    ]
    pick = [0] * len(phrases)
    arrival: list[dict[int, tuple[float, int]]] = [{} for _ in phrases]
    for index, (base, _shift, _line, _exact) in enumerate(candidates[0]):
        arrival[0][index] = (base, -1)
    for index in range(1, len(phrases)):
        prev_phrase = phrases[index - 1]
        curr_phrase = phrases[index]
        raw_dir = pitches[curr_phrase.start] - pitches[prev_phrase.end - 1]
        for curr_index, (base, _shift, line, _exact) in enumerate(candidates[index]):
            best_cost = None
            best_prev = 0
            for prev_index, (_prev_base, _prev_shift, prev_line, _prev_exact) in enumerate(candidates[index - 1]):
                if prev_index not in arrival[index - 1]:
                    continue
                placed_dir = line[0] - prev_line[-1]
                total = arrival[index - 1][prev_index][0] + base + _boundary_cost(raw_dir, placed_dir)
                if best_cost is None or total < best_cost:
                    best_cost = total
                    best_prev = prev_index
            if best_cost is not None:
                arrival[index][curr_index] = (best_cost, best_prev)
    cursor = min(arrival[-1], key=lambda item: arrival[-1][item])
    for index in range(len(phrases) - 1, -1, -1):
        pick[index] = cursor
        cursor = arrival[index][cursor][1]
    return [(phrase, candidates[index][pick[index]][2]) for index, phrase in enumerate(phrases)]


def _phrase_candidates(
    window: list[int],
    floor: int,
    top: int,
    degree: dict[int, int],
    scale: tuple[int, ...],
) -> list[tuple[float, int, list[int], bool]]:
    found: list[tuple[float, int, list[int], bool]] = []
    for shift in _SHIFTS:
        shifted = [note + shift for note in window]
        if any(note not in degree for note in shifted):
            continue
        overflow = _overflow(shifted, floor, top)
        exact = overflow == 0
        line = list(shifted) if exact else _compress_monotone(shifted, floor, top, degree, scale)
        found.append((overflow * _OVERFLOW_COST + abs(shift), shift, line, exact))
    if found:
        return found
    folded = [_clamp(note, floor, top) for note in window]
    return [(10_000, 0, folded, False)]


def _overflow(notes: list[int], floor: int, top: int) -> int:
    total = 0
    for note in notes:
        if note < floor:
            total += floor - note
        elif note > top:
            total += note - top
    return total


def _compress_monotone(
    shifted: list[int],
    floor: int,
    top: int,
    degree: dict[int, int],
    scale: tuple[int, ...],
) -> list[int]:
    """Map the shifted phrase onto scale degrees inside the window, in order."""
    window_idx = [index for index, note in enumerate(scale) if floor <= note <= top]
    floor_idx = window_idx[0]
    ceil_idx = window_idx[-1]
    bot = min(shifted)
    hi = max(shifted)
    bot_idx = degree[bot]
    hi_idx = degree[hi]
    span = hi_idx - bot_idx
    if hi >= top:
        target_top = ceil_idx
    elif hi <= floor:
        target_top = floor_idx
    else:
        target_top = degree[hi]
    target_bot = max(floor_idx, min(target_top, target_top - span))
    span_idx = max(1, span)
    out: list[int] = []
    for note in shifted:
        rel = (degree[note] - bot_idx) / span_idx
        mapped = round(target_bot + rel * (target_top - target_bot))
        mapped = max(floor_idx, min(ceil_idx, mapped))
        out.append(scale[mapped])
    return out


def _boundary_cost(raw_dir: int, placed_dir: int) -> int:
    reversal = (
        (raw_dir > 0 and placed_dir < 0)
        or (raw_dir < 0 and placed_dir > 0)
        or (raw_dir == 0 and placed_dir != 0)
    )
    if reversal and abs(placed_dir) >= _LARGE_LEAP:
        return _LARGE_LEAP_COST
    if reversal:
        return _REVERSAL_COST
    return 0


def _melody_line(pitches: list[int], phrases: tuple[Phrase, ...], bars: int) -> list[NoteEvent]:
    epb = active_meter().eighths_per_bar
    apex = _apex_eighths(phrases)
    events: list[NoteEvent] = []
    for bar in range(bars):
        start = bar * epb
        index = start
        end = start + epb
        while index < end:
            nxt = index + 1
            while nxt < end and pitches[nxt] == pitches[index]:
                nxt += 1
            events.extend(
                written(index, nxt - index, pitches[index], velocity=_span_velocity(index, nxt - index, apex))
            )
            index = nxt
    return _slur(events, phrases)


def _arpeggio(
    melody: list[int],
    chord_at: dict[int, Chord],
    kind_at: dict[int, str],
    band_at: dict[int, str],
    bars: int,
    *,
    rolling: bool,
    character: MovementCharacter | None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    strong = set(meter.strong_eighths)
    tresillo = _tresillo_bars(bars, epb, band_at, character, character_at) if rolling else set()
    inner: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    for bar in range(bars):
        chord = chord_at[bar]
        root = _clamp(chord.pitches[0], bass_low, bass_high)
        start = bar * epb
        if kind_at.get(bar) in _PEDAL:
            bass.extend(written(start, epb, root, velocity=_BASS))
            continue
        points = [point for point in meter.strong_eighths if point < epb]
        edges = [*points, epb]
        for left, right in zip(edges, edges[1:]):
            bass.extend(written(start + left, right - left, root, velocity=_BASS))
        pool = _pool(chord)
        played = _inner_eighths(epb, strong, rolling, band_at.get(bar, "mf"))
        for eighth in range(epb):
            if eighth not in played:
                continue
            tone = _fit(pool[eighth % len(pool)], mid_low, mid_high)
            while tone >= melody[start + eighth] and tone - 12 >= mid_low:
                tone -= 12
            if tone >= melody[start + eighth] or tone <= root:
                continue
            accent = bar in tresillo and eighth in {0, 3, 6}
            inner.extend(
                written(
                    start + eighth,
                    1,
                    tone,
                    velocity=_INNER + (8 if accent else 0),
                    accent=accent,
                )
            )
    return inner, bass


@dataclass(frozen=True)
class _Tone:
    """One sounding attack on the eighth grid, engraved after the breath."""

    start: int
    length: int
    midi: int
    velocity: int
    accent: bool = False


def _phrase_patterns(
    phrases: tuple[Phrase, ...],
    melody: list[int],
    kind_at: dict[int, str],
    band_at: dict[int, str],
    character: MovementCharacter | None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None,
    bpm: int,
    ensemble: str,
    mode: str,
    trio_bars: set[int],
    epb: int,
) -> tuple[dict[int, str], dict[int, int]]:
    """Lock one pattern per body phrase, and the tremolo tail start when it tapers.

    Pedal bars are not phrases. The first body phrase of a movement at 90 BPM
    or above is always the opening arpeggio; slower movements walk into the
    chorale from that first phrase.
    """
    patterns: dict[int, str] = {}
    previous: list[str] = []
    body: list[int] = []
    for index, phrase in enumerate(phrases):
        if not _is_body(phrase, kind_at, epb):
            continue
        body.append(index)
        apex_bar = phrase.apex.start // epb
        mood = character
        if character_at is not None and 0 <= apex_bar < len(character_at) and character_at[apex_bar] is not None:
            mood = character_at[apex_bar]
        pattern = _choose_pattern(
            phrase,
            melody,
            opening=len(body) == 1,
            bpm=bpm,
            ensemble=ensemble,
            mode=mode,
            band=band_at.get(apex_bar, "mf"),
            mood=mood,
            in_trio=apex_bar in trio_bars,
            previous=previous,
        )
        patterns[index] = pattern
        previous.append(pattern)
    tails: dict[int, int] = {}
    for position, index in enumerate(body):
        phrase = phrases[index]
        if patterns[index] != "tremolo" or phrase.end - phrase.start < 8:
            continue
        nxt = patterns[body[position + 1]] if position + 1 < len(body) else None
        if phrase.closes or (nxt is not None and nxt != "tremolo"):
            tails[index] = phrase.end - _TAIL_EIGHTHS
    return patterns, tails


def _is_body(phrase: Phrase, kind_at: dict[int, str], epb: int) -> bool:
    if phrase.end <= phrase.start or not phrase.runs:
        return False
    return any(kind_at.get(eighth // epb, "phrase") not in _PEDAL for eighth in range(phrase.start, phrase.end))


def _choose_pattern(
    phrase: Phrase,
    melody: list[int],
    *,
    opening: bool,
    bpm: int,
    ensemble: str,
    mode: str,
    band: str,
    mood: MovementCharacter | None,
    in_trio: bool,
    previous: list[str],
) -> str:
    if opening and bpm >= BARRIOS_TREMOLO_MIN_BPM:
        return "arpeggio"
    tremolo_window = BARRIOS_TREMOLO_MIN_BPM <= bpm <= BARRIOS_TREMOLO_MAX_BPM
    if ensemble == "barrios" and tremolo_window and _phrase_holds(phrase, melody):
        if len(previous) >= 2 and previous[-1] == "tremolo" and previous[-2] == "tremolo":
            return "andante"
        return "tremolo"
    if ensemble == "barrios" and bpm < BARRIOS_TREMOLO_MIN_BPM:
        return "andante"
    if ensemble == "classic" and (bpm <= 72 or mood == "selloff" or (in_trio and mode == "minor")):
        return "elegiaque"
    if ensemble == "villa" and (bpm <= 72 or band == "p" or mood == "calm"):
        return "chord_melody"
    return "arpeggio"


def _phrase_holds(phrase: Phrase, melody: list[int]) -> bool:
    """A melody note of at least two quarter beats, on the phrase or the placed line."""
    if any(run.length >= 4 for run in phrase.runs):
        return True
    index = phrase.start
    limit = min(phrase.end, len(melody))
    while index < limit:
        nxt = index + 1
        while nxt < limit and melody[nxt] == melody[index]:
            nxt += 1
        if nxt - index >= 4:
            return True
        index = nxt
    return False


def _ending_hold(melody: list[int], phrase: Phrase) -> int:
    if phrase.end <= phrase.start or phrase.end > len(melody):
        return 0
    pitch = melody[phrase.end - 1]
    length = 1
    index = phrase.end - 2
    while index >= phrase.start and melody[index] == pitch:
        length += 1
        index -= 1
    return length


def _trio_bars(sections: tuple[FormSection, ...]) -> set[int]:
    found: set[int] = set()
    for section in sections:
        if section.trio:
            found.update(range(section.start, section.end))
    return found


def _phrase_index(phrases: tuple[Phrase, ...], eighth: int) -> int | None:
    for index, phrase in enumerate(phrases):
        if phrase.start <= eighth < phrase.end:
            return index
    return None


def _breath_eighths(
    phrases: tuple[Phrase, ...],
    melody: list[int],
    patterns: dict[int, str],
    kind_at: dict[int, str],
    epb: int,
) -> list[int]:
    """The last eighth of a body phrase rests in the lead and the middle voice when the pattern changes."""
    body = [index for index in range(len(phrases)) if index in patterns]
    breaths: list[int] = []
    for position, index in enumerate(body[:-1]):
        nxt = body[position + 1]
        if patterns[index] == patterns[nxt]:
            continue
        phrase = phrases[index]
        if phrase.end <= phrase.start:
            continue
        last = phrase.end - 1
        if kind_at.get(last // epb, "phrase") in _PEDAL:
            continue
        hold = _ending_hold(melody, phrase)
        length = phrase.end - phrase.start
        family_changes = _FAMILY.get(patterns[index]) != _FAMILY.get(patterns[nxt])
        if hold >= 2 or (hold < 2 and family_changes and length >= 4):
            breaths.append(last)
    return breaths


def _melody_tones(
    melody: list[int],
    start: int,
    end: int,
    phrases: tuple[Phrase, ...],
    blocks: set[int] | None = None,
    overrides: dict[int, tuple[int, bool]] | None = None,
) -> list[_Tone]:
    attacks = blocks or set()
    ornaments = overrides or {}
    apex = _apex_eighths(phrases)
    tones: list[_Tone] = []
    index = start
    limit = min(end, len(melody))
    while index < limit:
        if index in ornaments:
            pitch, _accent = ornaments[index]
            tones.append(_Tone(index, 1, pitch, _span_velocity(index, 1, apex), True))
            index += 1
            continue
        pitch = melody[index]
        nxt = index + 1
        while nxt < limit and nxt not in attacks and nxt not in ornaments and melody[nxt] == pitch:
            nxt += 1
        tones.append(_Tone(index, nxt - index, pitch, _span_velocity(index, nxt - index, apex), False))
        index = nxt
    return tones


def _lay_arpeggio(
    start: int,
    end: int,
    melody: list[int],
    phrases: tuple[Phrase, ...],
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
    rolling: bool,
    tresillo: set[int],
    bounds: tuple[int, int, int, int],
    lead: list[_Tone],
    support: list[_Tone],
    bass: list[_Tone],
    *,
    anchor: bool,
) -> None:
    lead.extend(_melody_tones(melody, start, end, phrases))
    if end <= start:
        return
    meter = active_meter()
    epb = meter.eighths_per_bar
    bass_low, bass_high, mid_low, mid_high = bounds
    strong = set(meter.strong_eighths)
    for bar in range(start // epb, (end - 1) // epb + 1):
        if bar not in chord_at:
            continue
        bar_start = bar * epb
        seg_start = max(start, bar_start)
        seg_end = min(end, bar_start + epb)
        if seg_end <= seg_start:
            continue
        root = _root(chord_at[bar], bass_low, bass_high)
        points = [bar_start + local for local in sorted(strong) if seg_start <= bar_start + local < seg_end]
        if anchor and seg_start not in points:
            points.insert(0, seg_start)
        for left, right in zip(points, [*points[1:], seg_end]):
            if right > left:
                bass.append(_Tone(left, right - left, root, _BASS))
        pool = _pool(chord_at[bar])
        played = _inner_eighths(epb, strong, rolling, band_at.get(bar, "mf"))
        for local in played:
            eighth = bar_start + local
            if not seg_start <= eighth < seg_end or eighth >= len(melody):
                continue
            tone = _fit(pool[local % len(pool)], mid_low, mid_high)
            while tone >= melody[eighth] and tone - 12 >= mid_low:
                tone -= 12
            if tone >= melody[eighth] or tone <= root:
                continue
            accent = bar in tresillo and local in {0, 3, 6}
            support.append(_Tone(eighth, 1, tone, _INNER + (8 if accent else 0), accent))


def _lay_tremolo(
    start: int,
    end: int,
    melody: list[int],
    chord_at: dict[int, Chord],
    bounds: tuple[int, int, int, int],
    lead: list[NoteEvent],
    support: list[_Tone],
    bass: list[NoteEvent],
) -> None:
    """Sixteenth repeats for every eighth in ``[start, end)``, clustered by the quarter."""
    if end <= start or not melody:
        return
    meter = active_meter()
    epb = meter.eighths_per_bar
    bass_low, bass_high, mid_low, mid_high = bounds
    for bar in range(start // epb, (end - 1) // epb + 1):
        if bar not in chord_at:
            continue
        chord = chord_at[bar]
        root = _root(chord, bass_low, bass_high)
        fifth = _chord_fifth(chord, bass_low, bass_high)
        changed = bar == 0 or chord_at.get(bar - 1) != chord
        bar_start = bar * epb
        for local in range(0, epb, 2):
            cluster = bar_start + local
            ov0 = max(cluster, start)
            ov1 = min(cluster + 2, end)
            if ov0 >= ov1:
                continue
            pitch_at = cluster if start <= cluster < len(melody) else min(ov0, len(melody) - 1)
            pitch = melody[pitch_at]
            for eighth in range(ov0, ov1):
                local_e = eighth - bar_start
                base = local_e * 0.5
                finger = (local_e % 2) * 2
                for repeat in range(2):
                    lead.append(
                        _hit(
                            bar,
                            base + repeat * 0.25,
                            0.25,
                            pitch,
                            1,
                            _TREMOLO_FILL_PATTERN[finger + repeat],
                        )
                    )
            beat = (ov0 - bar_start) * 0.5
            duration = (ov1 - ov0) * 0.5
            bass.append(_hit(bar, beat, duration, root, 3, _TREMOLO_THUMB))
            if fifth != root:
                bass.append(_hit(bar, beat, duration, fifth, 3, _TREMOLO_THUMB))
            if local == 0 and changed and ov0 == cluster:
                color = _color_below(chord, melody[min(cluster, len(melody) - 1)], mid_low, mid_high, bass_low)
                if color is not None:
                    support.append(_Tone(ov0, ov1 - ov0, color, _TREMOLO_THUMB))


def _lay_chorale(
    start: int,
    end: int,
    pattern: str,
    phrase: Phrase,
    melody: list[int],
    phrases: tuple[Phrase, ...],
    chord_at: dict[int, Chord],
    bounds: tuple[int, int, int, int],
    lead: list[_Tone],
    support: list[_Tone],
    bass: list[_Tone],
) -> None:
    meter = active_meter()
    epb = meter.eighths_per_bar
    bass_low, bass_high, mid_low, mid_high = bounds
    bar = start // epb
    hits = [hit for hit in _chord_hits(pattern, meter, phrase, bar) if start <= bar * epb + hit < end]
    lead.extend(_melody_tones(melody, start, end, phrases, blocks={bar * epb + hit for hit in hits}))
    if bar not in chord_at or not hits:
        return
    chord = chord_at[bar]
    root = _root(chord, bass_low, bass_high)
    allowed = _color_intervals(chord) if pattern == "chord_melody" else None
    ordered = sorted(hits)
    for position, hit in enumerate(ordered):
        eighth = bar * epb + hit
        nxt = ordered[position + 1] if position + 1 < len(ordered) else epb
        ring_end = min(bar * epb + nxt, end)
        length = ring_end - eighth
        if length <= 0:
            continue
        bass.append(_Tone(eighth, length, root, _BASS))
        color = _support_tone(chord, root, _min_melody(melody, eighth, length), mid_low, mid_high, allowed)
        if color is not None:
            support.append(_Tone(eighth, length, color, _INNER))


def _chord_hits(pattern: str, meter, phrase: Phrase, bar: int) -> list[int]:
    epb = meter.eighths_per_bar
    apex_bar = phrase.apex.start // epb
    start_bar = phrase.start // epb
    last_bar = (phrase.end - 1) // epb
    rising = phrase.rise >= MIN_RISE
    if epb == 8:
        if pattern == "chord_melody" and rising and start_bar <= bar <= apex_bar:
            return [0, 2, 4, 6]
        return [0, 4]
    if meter.beat_type == 8:
        if pattern == "andante":
            return [0, 3]
        previous = apex_bar - 1
        if rising and (bar == apex_bar or (bar == previous and previous >= start_bar)):
            return [0, 3]
        return [0]
    extra = bar == apex_bar or (phrase.closes and bar == last_bar)
    if pattern == "chord_melody":
        extra = extra or (rising and start_bar <= bar <= apex_bar)
    return [0, 4] if extra else [0]


def _lay_elegiaque(
    start: int,
    end: int,
    index: int,
    phrase: Phrase,
    melody: list[int],
    phrases: tuple[Phrase, ...],
    overrides: dict[int, tuple[int, bool]],
    chord_at: dict[int, Chord],
    band_at: dict[int, str],
    mode: str,
    bounds: tuple[int, int, int, int],
    elegy_prev: dict[int, int | None],
    lead: list[_Tone],
    support: list[_Tone],
    bass: list[_Tone],
) -> None:
    meter = active_meter()
    epb = meter.eighths_per_bar
    bass_low, bass_high, mid_low, mid_high = bounds
    classes = C_NATURAL_MINOR_PCS if mode == "minor" else C_MAJOR_PCS
    lead.extend(_melody_tones(melody, start, end, phrases, overrides=overrides))
    bar = start // epb
    if bar not in chord_at:
        return
    chord = chord_at[bar]
    root = _root(chord, bass_low, bass_high)
    fifth = _chord_fifth(chord, bass_low, bass_high)
    start_bar = phrase.start // epb
    last_bar = (phrase.end - 1) // epb
    lament = mode == "minor" and phrase.closes and bar >= max(start_bar, last_bar - 1)
    sustain = epb == 6 and meter.beat_type == 4 and phrase.closes and bar == last_bar
    prev = elegy_prev.get(index)
    region: list[_Tone] = []
    if sustain:
        origin = bar * epb
        audible = max(origin, start)
        stop = min((bar + 1) * epb, end)
        if stop > audible:
            region.append(_Tone(audible, stop - audible, root, _BASS))
            prev = root
    else:
        for local, length, role in _march(meter):
            eighth = bar * epb + local
            note_end = eighth + length
            if note_end <= start or eighth >= end:
                continue
            if lament:
                pitch = root if prev is None else _step_down(prev, classes, bass_low, bass_high)
            elif role == "fifth":
                pitch = fifth
            elif role == "step":
                pitch = _step_down(root if prev is None else prev, classes, bass_low, bass_high)
            else:
                pitch = root
            audible = max(eighth, start)
            stop = min(note_end, end)
            if stop > audible:
                region.append(_Tone(audible, stop - audible, pitch, _BASS))
            prev = pitch
    elegy_prev[index] = prev
    bass.extend(region)
    sounding = {tone.start + offset: tone.midi for tone in region for offset in range(tone.length)}
    played = _inner_eighths(
        epb,
        set(meter.strong_eighths),
        False,
        _SPARSER.get(band_at.get(bar, "mf"), "mp"),
    )
    pool = _pool(chord)
    for local in played:
        eighth = bar * epb + local
        if not start <= eighth < end or eighth >= len(melody):
            continue
        lead_pitch = overrides[eighth][0] if eighth in overrides else melody[eighth]
        tone = _fit(pool[local % len(pool)], mid_low, mid_high)
        while tone >= lead_pitch and tone - 12 >= mid_low:
            tone -= 12
        if tone >= lead_pitch or tone <= sounding.get(eighth, root):
            continue
        support.append(_Tone(eighth, 1, tone, _INNER))


def _march(meter) -> list[tuple[int, int, str]]:
    if meter.eighths_per_bar == 8:
        return [(0, 3, "root"), (3, 1, "step"), (4, 3, "fifth"), (7, 1, "step")]
    if meter.beat_type == 8:
        return [(0, 2, "root"), (2, 1, "step"), (3, 2, "fifth"), (5, 1, "step")]
    return [(0, 3, "root"), (3, 1, "step"), (4, 2, "fifth")]


def _appoggiatura(phrase: Phrase, melody: list[int], mode: str) -> dict[int, tuple[int, bool]]:
    """At most one accented neighbor, resolving to the strong-beat melody note."""
    scale = _melody_scale(mode)
    degree = {note: index for index, note in enumerate(scale)}
    meter = active_meter()
    strong = set(meter.strong_eighths)
    epb = meter.eighths_per_bar
    spans: list[tuple[int, int, int]] = []
    index = phrase.start
    limit = min(phrase.end, len(melody))
    while index < limit:
        nxt = index + 1
        while nxt < limit and melody[nxt] == melody[index]:
            nxt += 1
        spans.append((index, nxt, melody[index]))
        index = nxt
    for position, (start, end, pitch) in enumerate(spans):
        if start % epb not in strong or end - start < 2 or position + 1 >= len(spans):
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


def _color_intervals(chord: Chord) -> frozenset[int]:
    if chord.quality_group == "suspended":
        return _SUSPENDED_COLORS
    return _THIRDS_AND_SEVENTHS


def _support_tone(
    chord: Chord,
    bass: int,
    lead: int,
    mid_low: int,
    mid_high: int,
    allowed: frozenset[int] | None,
) -> int | None:
    """Highest chord tone strictly between the bass and the melody."""
    root_pc = chord.pitches[0] % 12
    best: int | None = None
    seen: set[int] = set()
    for pitch in chord.pitches:
        pc = pitch % 12
        if pc in seen:
            continue
        seen.add(pc)
        interval = (pc - root_pc) % 12
        if interval == 0 or (allowed is not None and interval not in allowed):
            continue
        tone = _fit(pc, mid_low, mid_high)
        while tone + 12 < lead and tone + 12 <= mid_high:
            tone += 12
        while tone >= lead and tone - 12 >= mid_low:
            tone -= 12
        if tone < mid_low or tone > mid_high or tone >= lead or tone <= bass:
            continue
        if best is None or tone > best:
            best = tone
    return best


def _min_melody(melody: list[int], start: int, length: int) -> int:
    window = melody[start : start + length]
    return min(window) if window else 127


def _root(chord: Chord, low: int, high: int) -> int:
    return _clamp(chord.pitches[0], low, high)


def _chord_fifth(chord: Chord, low: int, high: int) -> int:
    if len(chord.pitches) < 3:
        return _root(chord, low, high)
    return _clamp(chord.pitches[2], low, high)


def _step_down(note: int, classes: frozenset[int], low: int, high: int) -> int:
    for shift in range(1, 12):
        candidate = note - shift
        if candidate % 12 in classes:
            return _clamp(candidate, low, high)
    return _clamp(note - 1, low, high)


def _cut_tones(tones: list[_Tone], eighth: int) -> list[_Tone]:
    kept: list[_Tone] = []
    for tone in tones:
        end = tone.start + tone.length
        if end <= eighth or tone.start > eighth:
            kept.append(tone)
        elif tone.start < eighth:
            kept.append(replace(tone, length=eighth - tone.start))
    return kept


def _cut_sixteenths(events: list[NoteEvent], eighth: int, epb: int) -> list[NoteEvent]:
    spb = epb * 2
    breath = eighth * 2
    return [event for event in events if not breath <= _start16(event, spb) < breath + 2]


def _engrave(tones: list[_Tone]) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    for tone in tones:
        if tone.length <= 0:
            continue
        events.extend(written(tone.start, tone.length, tone.midi, velocity=tone.velocity, accent=tone.accent))
    return events


def _start16(event: NoteEvent, sixteenths_per_bar: int) -> int:
    return event.bar * sixteenths_per_bar + int(math.floor(event.beat * 4 + 1e-9))


def _dur16(event: NoteEvent) -> int:
    return int(round(event.duration_beats * 4))


def _fill_voice(events: list[NoteEvent], total_eighths: int, epb: int) -> list[NoteEvent]:
    """Rest-fill one voice so every measure is covered once, chords sharing an onset."""
    spb = epb * 2
    total = total_eighths * 2
    filled: list[NoteEvent] = []
    cursor = 0
    for event in sorted(events, key=lambda item: (_start16(item, spb), -_dur16(item))):
        dur = _dur16(event)
        if dur <= 0:
            continue
        start = _start16(event, spb)
        if start > cursor:
            filled.extend(_rests_between(cursor, start, epb))
        filled.append(event)
        cursor = max(cursor, start + dur)
    if cursor < total:
        filled.extend(_rests_between(cursor, total, epb))
    return filled


_REST_SIXTEENTHS = (16, 12, 8, 6, 4, 3, 2, 1)


def _rests_between(start16: int, end16: int, epb: int) -> list[NoteEvent]:
    if start16 >= end16:
        return []
    if start16 % 2 == 0 and (end16 - start16) % 2 == 0:
        return written(start16 // 2, (end16 - start16) // 2, None)
    events: list[NoteEvent] = []
    cursor = start16
    spb = epb * 2
    while cursor < end16:
        stop = min(end16, (cursor // spb + 1) * spb)
        left = stop - cursor
        while left > 0:
            take = next(size for size in _REST_SIXTEENTHS if size <= left)
            events.append(
                NoteEvent(
                    bar=cursor // spb,
                    beat=(cursor % spb) * 0.25,
                    midi=None,
                    duration_beats=take * 0.25,
                    voice=1,
                )
            )
            cursor += take
            left -= take
    return events


def _tremolo(
    melody: list[int],
    chord_at: dict[int, Chord],
    kind_at: dict[int, str],
    bars: int,
    bpm: int,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
    phrases: tuple[Phrase, ...],
) -> tuple[tuple[NoteEvent, ...], tuple[NoteEvent, ...], tuple[NoteEvent, ...]]:
    """One tremolo cluster per quarter note, filled with four sixteenths.

    At the score tempo (120 BPM for Barrios) each cluster lasts one quarter
    and carries one melody pitch through all four sixteenth repeats, so the
    clusters join into a sung melody line instead of changing pitch every
    two sixteenths. The thumb is its own voice and the strongest attack at
    58: it strikes the root and fifth together on each quarter and rings
    through it, never yielding the downbeat of a chord change, so the bass
    stays dark, full, and steady. Inside the fill, a=52, m=55, i=54.
    """
    meter = active_meter()
    epb = meter.eighths_per_bar
    apex = _apex_eighths(phrases)
    line: list[NoteEvent] = []
    inner: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    grain = 2
    duration = 0.25
    for bar in range(bars):
        chord = chord_at[bar]
        root = _clamp(chord.pitches[0], bass_low, bass_high)
        changed = bar == 0 or chord_at.get(bar - 1) != chord
        if kind_at.get(bar) in _PEDAL:
            start = bar * epb
            index = start
            end = start + epb
            while index < end:
                nxt = index + 1
                while nxt < end and melody[nxt] == melody[index]:
                    nxt += 1
                line.extend(
                    written(index, nxt - index, melody[index], velocity=_span_velocity(index, nxt - index, apex))
                )
                index = nxt
            bass.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=root,
                    duration_beats=meter.quarter_beats,
                    voice=3,
                    velocity=_BASS,
                )
            )
            inner.append(
                NoteEvent(
                    bar=bar,
                    beat=0.0,
                    midi=None,
                    duration_beats=meter.quarter_beats,
                    voice=2,
                )
            )
            continue
        cluster_beats = _TREMOLO_CLUSTER * duration  # one quarter note
        for cluster_index, cluster in enumerate(range(0, epb * grain, _TREMOLO_CLUSTER)):
            eighth = cluster // grain
            beat = cluster * duration
            sung = melody[bar * epb + eighth]
            if cluster_index == 0 and changed:
                # The colour joins the downbeat, but the thumb keeps the root:
                # yielding it left chord-change bars with no bass at all.
                color = _color_below(chord, sung, mid_low, mid_high, bass_low)
                inner.append(_hit(bar, beat, cluster_beats, color, 2, _TREMOLO_THUMB))
            else:
                inner.append(_hit(bar, beat, cluster_beats, None, 2, _INNER))
            bass.append(_hit(bar, beat, cluster_beats, root, 3, _TREMOLO_THUMB))
            if len(chord.pitches) >= 3:
                fifth = _clamp(chord.pitches[2], bass_low, bass_high)
                if fifth != root:
                    bass.append(_hit(bar, beat, cluster_beats, fifth, 3, _TREMOLO_THUMB))
            for repeat in range(_TREMOLO_CLUSTER):
                line.append(
                    _hit(
                        bar,
                        beat + repeat * duration,
                        duration,
                        sung,
                        1,
                        _TREMOLO_FILL_PATTERN[repeat],
                    )
                )
    return tuple(_slur(line, phrases)), tuple(inner), tuple(bass)


def _color_below(chord: Chord, sung: int, mid_low: int, mid_high: int, lowest: int) -> int | None:
    """Place the inner tone under the melody, dropping an octave when the fit sits on it."""
    pool = _pool(chord)
    color = _fit(pool[min(1, len(pool) - 1)], mid_low, mid_high)
    while color >= sung and color - 12 >= lowest:
        color -= 12
    if color >= sung:
        return None
    return color


def _tresillo_bars(
    bars: int,
    eighths_per_bar: int,
    band_at: dict[int, str],
    character: MovementCharacter | None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None,
) -> set[int]:
    """3+3+2 accents on 4/4, only for volatile mf/f, and never three bars in a row."""
    if eighths_per_bar != 8:
        return set()
    chosen: set[int] = set()
    streak = 0
    for bar in range(bars):
        mood = character
        if character_at is not None and bar < len(character_at) and character_at[bar] is not None:
            mood = character_at[bar]
        qualifies = mood == "volatile" and band_at.get(bar) in {"mf", "f"}
        if qualifies and streak < 2:
            chosen.add(bar)
            streak += 1
        else:
            streak = 0
    return chosen


def _hit(bar: int, beat: float, duration: float, midi: int | None, voice: int, velocity: int) -> NoteEvent:
    return NoteEvent(
        bar=bar,
        beat=beat,
        midi=midi,
        duration_beats=duration,
        voice=voice,
        velocity=None if midi is None else velocity,
    )


def _pool(chord: Chord) -> list[int]:
    pitches = list(chord.pitches)
    if len(pitches) >= 4:
        del pitches[2]
    found: list[int] = []
    for pitch in pitches:
        pc = pitch % 12
        if pc not in found:
            found.append(pc)
    return found or [chord.pitches[0] % 12]


def _fit(pitch_class: int, low: int, high: int) -> int:
    note = low + (pitch_class - low) % 12
    while note > high:
        note -= 12
    while note < low:
        note += 12
    return note


def _clamp(note: int, low: int, high: int) -> int:
    while note > high:
        note -= 12
    while note < low:
        note += 12
    return note


def _voice(notes: tuple[NoteEvent, ...] | list[NoteEvent], voice: int) -> tuple[NoteEvent, ...]:
    return tuple(replace(note, voice=voice) for note in notes)


def _apex_eighths(phrases: tuple[Phrase, ...]) -> set[int]:
    eighths: set[int] = set()
    for phrase in phrases:
        if not phrase.runs:
            continue
        apex = phrase.apex
        eighths.update(range(apex.start, apex.end))
    return eighths


def _eighth_velocity(eighth: int, apex: set[int]) -> int:
    return _MELODY_APEX if eighth in apex else _MELODY


def _span_velocity(start: int, length: int, apex: set[int]) -> int:
    if any(eighth in apex for eighth in range(start, start + length)):
        return _MELODY_APEX
    return _MELODY


def _inner_eighths(epb: int, strong: set[int], rolling: bool, band: str) -> set[int]:
    """A quiet bar plucks one inner note. mp keeps every other. mf and f keep the pattern."""
    candidates = [eighth for eighth in range(epb) if rolling or eighth not in strong]
    if not candidates:
        return set()
    if band == "p":
        return {candidates[0]}
    if band == "mp":
        return set(candidates[::2])
    return set(candidates)


def _attack_eighth(event: NoteEvent) -> int:
    """Eighth index of an attack. Floor, so a sixteenth at beat 0.75 stays in its eighth."""
    epb = active_meter().eighths_per_bar
    return event.bar * epb + math.floor(event.beat * 2 + 1e-9)


def _hammer_count(notes: int) -> int:
    if notes <= 0:
        return 0
    return int(notes * _HAMMER_SHARE + 0.5)


def _spread(count: int, want: int) -> list[int]:
    """Indexes spread through ``count`` items. Short of ``want`` when there are not enough."""
    if want <= 0 or count <= 0:
        return []
    kept = min(want, count)
    if kept == count:
        return list(range(count))
    step = count / kept
    return [min(count - 1, int((index + 0.5) * step)) for index in range(kept)]


def _slur(events: list[NoteEvent], phrases: tuple[Phrase, ...]) -> list[NoteEvent]:
    """Hammer rarely, and only onto a stressed note after the opening phrase.

    The nylon voice plays a slur as a left-hand hammer. A leap, a rest, a new
    phrase, an unstressed step, a tremolo sixteenth, and anything in the first
    phrase stay plucked. A stress is the phrase apex (or an accented attack
    already carrying the apex velocity). The kept steps are spread through
    the eligible stresses, capped under one attack in twenty.
    """
    result = list(events)
    apex = _apex_eighths(phrases)

    def position(event: NoteEvent) -> float:
        return event.bar * active_meter().quarter_beats + event.beat

    def phrase_of(event: NoteEvent) -> int | None:
        eighth = _attack_eighth(event)
        for index, phrase in enumerate(phrases):
            if phrase.start <= eighth < phrase.end:
                return index
        return None

    sounding = [index for index, event in enumerate(result) if event.midi is not None]
    sounding.sort(key=lambda index: (result[index].bar, result[index].beat, index))
    chains: list[list[int]] = []
    for index in sounding:
        event = result[index]
        if event.tie_stop and chains:
            previous = result[chains[-1][-1]]
            continues = previous.midi == event.midi and abs(
                position(previous) + previous.duration_beats - position(event)
            ) < 1e-6
            if continues:
                chains[-1].append(index)
                continue
        chains.append([index])

    pairs: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(chains) - 1:
        left = chains[cursor]
        right = chains[cursor + 1]
        left_last = result[left[-1]]
        right_first = result[right[0]]
        interval = abs((left_last.midi or 0) - (right_first.midi or 0))
        touches = abs(position(left_last) + left_last.duration_beats - position(right_first)) < 1e-6
        target_phrase = phrase_of(right_first)
        same_phrase = target_phrase is not None and phrase_of(result[left[0]]) == target_phrase
        stressed = (
            _attack_eighth(right_first) in apex
            or right_first.accent
            or (right_first.velocity or 0) >= _MELODY_APEX
        )
        held_step = left_last.duration_beats >= 0.5 and right_first.duration_beats >= 0.5
        if (
            same_phrase
            and target_phrase != 0
            and stressed
            and held_step
            and 1 <= interval <= 2
            and touches
        ):
            pairs.append((left[0], right[0]))
            cursor += 2
        else:
            cursor += 1
    for pair_index in _spread(len(pairs), _hammer_count(len(chains))):
        start, stop = pairs[pair_index]
        result[start] = replace(result[start], slur_start=True)
        result[stop] = replace(result[stop], slur_stop=True)
    return result
