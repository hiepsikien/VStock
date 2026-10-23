"""One nylon guitar, three voices.

Sor keeps a study texture: the price is the top voice, chord tones fill the
weak eighths, and the root sits on the strong beats. Villa-Lobos rolls a
chord-tone pattern under that line. Barrios chooses per phrase: arpeggio on
the first body phrase from 90 BPM, tremolo when a note is held, andante under
90, and a dance (choro, polca, or hemiola) when the line is running above 100
BPM. All three read the written guitar bounds from the active register, so a
transposed key stays inside the same sounding range.
"""

from __future__ import annotations

import math
from dataclasses import replace

from app.sonify.chords import Chord
from app.sonify.form import active_meter
from app.sonify.keys import MovementCharacter, active_register
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import Phrase, quantize_strong_beats, with_rests, written
from app.sonify.quantize import C_MAJOR_PCS, C_NATURAL_MINOR_PCS, scale_from_classes

GUITAR_BPM = {"classic": 88, "villa": 100, "barrios": 120}
# Listening tests: a tremolo only reads as a sung line from 90 BPM up, sits
# best around 120, and can run to 140. A Barrios movement under that floor
# is not sped up and gets no tremolo at all: it keeps its slow tempo and
# sings as arpeggio instead. The daily tempo is the 120 middle of the range.
BARRIOS_TREMOLO_MIN_BPM = 90
BARRIOS_TREMOLO_MAX_BPM = 140
# Dance is strictly faster than 100. 100 itself stays on arpeggio.
BARRIOS_DANCE_MIN_BPM = 100
# A held melody note is two quarter-notes: four eighths on the data grid.
_HELD_EIGHTHS = 4
_PRINTABLE_SIXTEENTHS = (16, 12, 8, 6, 4, 3, 2, 1)
_PRINTABLE_EIGHTHS = (8, 6, 4, 3, 2, 1)
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
) -> Score:
    meter = active_meter()
    register = active_register()
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
    if ensemble == "barrios":
        lead, support, low, divisions = _render_barrios(
            melody,
            chord_at,
            kind_at,
            band_at,
            phrases,
            musical_bars,
            total_eighths,
            bpm,
            character,
            character_at,
            register.guitar_floor,
            register.guitar_bass_top,
            register.guitar_mid_low,
            register.guitar_mid_high,
        )
    else:
        lead = _melody_line(melody, phrases, musical_bars)
        support, low = _arpeggio(
            melody,
            chord_at,
            kind_at,
            band_at,
            musical_bars,
            rolling=ensemble == "villa",
            character=character,
            character_at=character_at,
            bass_low=register.guitar_floor,
            bass_high=register.guitar_bass_top,
            mid_low=register.guitar_mid_low,
            mid_high=register.guitar_mid_high,
        )
        lead = with_rests(lead, total_eighths)
        support = with_rests(list(support), total_eighths)
        low = with_rests(list(low), total_eighths)
        divisions = 2
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
    only: set[int] | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    strong = set(meter.strong_eighths)
    tresillo = _tresillo_bars(bars, epb, band_at, character, character_at) if rolling else set()
    inner: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    for bar in range(bars):
        if only is not None and bar not in only:
            continue
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
    only: set[int] | None = None,
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
        if only is not None and bar not in only:
            continue
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


def guard_chromatic_approach(midi: int, next_root_pc: int, *, profile: str) -> None:
    """A semitone under the next root belongs to `barrios_dance`.

    `study` rejects that bass note. `barrios_dance` accepts it and stays quiet.
    Any other pitch is outside this check.
    """
    if midi % 12 != (next_root_pc - 1) % 12:
        return
    if profile == "barrios_dance":
        return
    raise ValueError(f"{profile} rejects a chromatic approach into the next root")


def _split_count(count: int, sizes: tuple[int, ...]) -> list[int]:
    pieces: list[int] = []
    left = count
    while left > 0:
        take = next(size for size in sizes if size <= left)
        pieces.append(take)
        left -= take
    return pieces


def _held_phrase(phrase: Phrase) -> bool:
    return any(run.length >= _HELD_EIGHTHS for run in phrase.runs)


def _running_phrase(phrase: Phrase) -> bool:
    return bool(phrase.runs) and all(run.length < _HELD_EIGHTHS for run in phrase.runs)


def _phrase_mood(
    phrase: Phrase,
    character: MovementCharacter | None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None,
    eighths_per_bar: int,
) -> MovementCharacter | None:
    if phrase.runs and character_at is not None:
        apex_bar = phrase.apex.start // eighths_per_bar
        if apex_bar < len(character_at) and character_at[apex_bar] is not None:
            return character_at[apex_bar]
    return character


def _phrase_band(phrase: Phrase, band_at: dict[int, str], eighths_per_bar: int) -> str:
    if not phrase.runs:
        return "mf"
    return band_at.get(phrase.apex.start // eighths_per_bar, "mf")


def _is_body(phrase: Phrase, kind_at: dict[int, str], eighths_per_bar: int) -> bool:
    return any(
        kind_at.get(eighth // eighths_per_bar, "phrase") not in _PEDAL
        for eighth in range(phrase.start, phrase.end)
    )


def _choose_barrios_pattern(
    phrase: Phrase,
    *,
    first_body: bool,
    tremolo_run: int,
    bpm: int,
    meter_key: tuple[int, int],
    mood: MovementCharacter | None,
) -> str:
    """Selector steps 1–5 for one body phrase. Pedal bars are assigned aside."""
    if first_body and bpm >= BARRIOS_TREMOLO_MIN_BPM:
        return "arpeggio"
    if _held_phrase(phrase) and BARRIOS_TREMOLO_MIN_BPM <= bpm <= BARRIOS_TREMOLO_MAX_BPM:
        if tremolo_run >= 2:
            return "andante"
        return "tremolo"
    if bpm < BARRIOS_TREMOLO_MIN_BPM:
        return "andante"
    if (
        _running_phrase(phrase)
        and mood != "calm"
        and bpm > BARRIOS_DANCE_MIN_BPM
        and meter_key in {(4, 4), (6, 8)}
    ):
        return "dance"
    return "arpeggio"


def _assign_barrios(
    phrases: tuple[Phrase, ...],
    kind_at: dict[int, str],
    band_at: dict[int, str],
    musical_bars: int,
    bpm: int,
    character: MovementCharacter | None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None,
) -> tuple[dict[int, tuple[str, str, Phrase | None]], list[tuple[Phrase, str, str]]]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    plans: dict[int, tuple[str, str, Phrase | None]] = {}
    for bar in range(musical_bars):
        if kind_at.get(bar) in _PEDAL:
            plans[bar] = ("pedal", band_at.get(bar, "mf"), None)
    choices: list[tuple[Phrase, str, str]] = []
    tremolo_run = 0
    first_body = True
    meter_key = (meter.beats, meter.beat_type)
    for phrase in phrases:
        if phrase.end <= phrase.start or not _is_body(phrase, kind_at, epb):
            continue
        mood = _phrase_mood(phrase, character, character_at, epb)
        pattern = _choose_barrios_pattern(
            phrase,
            first_body=first_body,
            tremolo_run=tremolo_run,
            bpm=bpm,
            meter_key=meter_key,
            mood=mood,
        )
        band = _phrase_band(phrase, band_at, epb)
        choices.append((phrase, pattern, band))
        tremolo_run = tremolo_run + 1 if pattern == "tremolo" else 0
        first_body = False
        for eighth in range(phrase.start, phrase.end):
            if eighth % epb != 0:
                continue
            bar = eighth // epb
            if bar >= musical_bars or plans.get(bar, ("", "", None))[0] == "pedal":
                continue
            plans[bar] = (pattern, band, phrase)
    for bar in range(musical_bars):
        plans.setdefault(bar, ("arpeggio", band_at.get(bar, "mf"), None))
    return plans, choices


def _following_pattern(
    phrase: Phrase | None, choices: list[tuple[Phrase, str, str]]
) -> str | None:
    if phrase is None:
        return None
    for index, (candidate, pattern, _band) in enumerate(choices):
        if candidate is phrase:
            if index + 1 < len(choices):
                return choices[index + 1][1]
            return None
    return None


def _fill_one_eighth_bar(events: list[NoteEvent], bar: int, epb: int) -> list[NoteEvent]:
    def position(event: NoteEvent) -> int:
        return int(round(event.beat * 2))

    def duration(event: NoteEvent) -> int:
        return int(round(event.duration_beats * 2))

    filled: list[NoteEvent] = []
    cursor = 0
    for event in sorted(events, key=lambda item: (position(item), -duration(item))):
        start = position(event)
        if start > cursor:
            filled.extend(written(bar * epb + cursor, start - cursor, None))
        filled.append(event)
        cursor = max(cursor, start + duration(event))
    if cursor < epb:
        filled.extend(written(bar * epb + cursor, epb - cursor, None))
    return filled


def _fill_eighth_bars(events: list[NoteEvent], bars: set[int], epb: int) -> list[NoteEvent]:
    grouped: dict[int, list[NoteEvent]] = {bar: [] for bar in bars}
    for event in events:
        if event.bar in grouped:
            grouped[event.bar].append(event)
    filled: list[NoteEvent] = []
    for bar in sorted(grouped):
        filled.extend(_fill_one_eighth_bar(grouped[bar], bar, epb))
    return filled


def _andante_attacks(epb: int, beats: int, marked: bool) -> list[tuple[int, int]]:
    """(eighth, length in eighths) for one bar. Lengths sum to the bar."""
    if epb == 8:
        return [(0, 4), (4, 4)]
    if epb == 6 and beats == 6:
        return [(0, 3), (3, 3)]
    if epb == 6 and marked:
        return [(0, 4), (4, 2)]
    if epb == 6:
        return [(0, 6)]
    return [(0, epb)]


def _marked_andante_bars(phrases: tuple[Phrase, ...], epb: int) -> set[int]:
    marked: set[int] = set()
    for phrase in phrases:
        if not phrase.runs or phrase.end <= phrase.start:
            continue
        marked.add(phrase.apex.start // epb)
        if phrase.closes:
            marked.add((phrase.end - 1) // epb)
    return marked


def _andante(
    melody: list[int],
    chord_at: dict[int, Chord],
    phrases: tuple[Phrase, ...],
    bars: int,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
    only: set[int],
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    marked = _marked_andante_bars(phrases, epb)
    inner: list[NoteEvent] = []
    bass: list[NoteEvent] = []
    for bar in sorted(only):
        if bar >= bars:
            continue
        chord = chord_at[bar]
        root = _clamp(chord.pitches[0], bass_low, bass_high)
        start = bar * epb
        for eighth, length in _andante_attacks(epb, meter.beats, bar in marked):
            sung = melody[start + eighth]
            tone = _tone_below(chord, sung, mid_low, mid_high, "third")
            bass.extend(written(start + eighth, length, root, velocity=_BASS))
            if tone is not None and root < tone < sung:
                inner.extend(written(start + eighth, length, tone, velocity=_INNER))
    return inner, bass


def _tone_below(
    chord: Chord,
    sung: int,
    mid_low: int,
    mid_high: int,
    prefer: str,
) -> int | None:
    """One trimmed chord tone strictly under the lead, inside the middle register."""
    third = chord.pitches[1] % 12
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


def _approach_pitch(chord: Chord, bass_low: int, bass_high: int) -> int:
    root = _clamp(chord.pitches[0], bass_low, bass_high)
    note = root - 1
    if bass_low <= note <= bass_high:
        return note
    return _fit(note % 12, bass_low, bass_high)


def _falls_a_fifth(current: Chord, nxt: Chord) -> bool:
    return (current.pitches[0] - nxt.pitches[0]) % 12 == 7


def _events_from_slots(
    bar: int,
    slots: list[tuple[int | None, int | None]],
    voice: int,
) -> list[NoteEvent]:
    events: list[NoteEvent] = []
    index = 0
    total = len(slots)
    while index < total:
        midi, velocity = slots[index]
        if midi is None:
            end = index + 1
            while end < total and slots[end][0] is None:
                end += 1
            cursor = index
            for length in _split_count(end - index, _PRINTABLE_SIXTEENTHS):
                events.append(_hit(bar, cursor * 0.25, length * 0.25, None, voice, 0))
                cursor += length
            index = end
            continue
        events.append(_hit(bar, index * 0.25, 0.25, midi, voice, velocity if velocity is not None else _INNER))
        index += 1
    return events


def _place_slot(
    grid: list[tuple[int | None, int | None]],
    index: int,
    midi: int | None,
    velocity: int,
) -> None:
    if midi is None or index < 0 or index >= len(grid):
        return
    grid[index] = (midi, velocity)


def _clear_slot(grid: list[tuple[int | None, int | None]], index: int) -> None:
    if 0 <= index < len(grid):
        grid[index] = (None, None)


def _lead_bar(
    bar: int,
    melody: list[int],
    epb: int,
    breath_eighth: int | None,
    apex: set[int],
) -> list[NoteEvent]:
    """Melody on the eighth grid. A pattern-change breath is one eighth of rest."""
    start = bar * epb
    end = start + epb
    events: list[NoteEvent] = []
    eighth = start
    while eighth < end:
        if breath_eighth is not None and eighth == breath_eighth:
            events.append(_hit(bar, (eighth - start) * 0.5, 0.5, None, 1, 0))
            eighth += 1
            continue
        pitch = melody[eighth]
        nxt = eighth + 1
        while nxt < end and nxt != breath_eighth and melody[nxt] == pitch:
            nxt += 1
        cursor = eighth
        for piece in _split_count(nxt - eighth, _PRINTABLE_EIGHTHS):
            events.append(
                _hit(
                    bar,
                    (cursor - start) * 0.5,
                    piece * 0.5,
                    pitch,
                    1,
                    _span_velocity(cursor, piece, apex),
                )
            )
            cursor += piece
        eighth = nxt
    return events


def _dance_bar(
    bar: int,
    *,
    chord: Chord,
    melody: list[int],
    epb: int,
    band: str,
    beats: int,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
    approach: int | None,
    leaving: bool,
    breath_eighth: int | None,
    apex: set[int],
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    sixteenths = epb * 2
    low: list[tuple[int | None, int | None]] = [(None, None)] * sixteenths
    support: list[tuple[int | None, int | None]] = [(None, None)] * sixteenths
    root = _clamp(chord.pitches[0], bass_low, bass_high)
    fifth = _clamp(chord.pitches[2], bass_low, bass_high) if len(chord.pitches) >= 3 else root

    def sung(index: int) -> int:
        return melody[bar * epb + index // 2]

    def support_at(index: int, prefer: str) -> None:
        _place_slot(
            support,
            index,
            _tone_below(chord, sung(index), mid_low, mid_high, prefer),
            _INNER,
        )

    if beats == 6 and epb == 6 and band == "f":
        _place_slot(low, 0, root, _BASS)
        _place_slot(low, 4, fifth, _BASS)
        _place_slot(low, 8, root, _BASS)
    elif beats == 6 and epb == 6:
        _place_slot(low, 0, root, _BASS)
        _place_slot(low, 6, fifth, _BASS)
        for index, prefer in ((2, "third"), (4, "third"), (8, "third"), (10, "third")):
            support_at(index, prefer)
    else:
        for origin in (0, 8):
            _place_slot(low, origin, root, _BASS)
            _place_slot(low, origin + 4, fifth, _BASS)
            support_at(origin + 3, "third")
            support_at(origin + 6, "seventh")
            support_at(origin + 7, "third")

    last = sixteenths - 1
    if leaving:
        _clear_slot(low, last)
        _clear_slot(support, last)
        for index in range(max(0, sixteenths - 4), sixteenths):
            if index % 2 == 1:
                _clear_slot(support, index)
    elif approach is not None:
        _clear_slot(support, last)
        _place_slot(low, last, approach, _BASS)
    if breath_eighth is not None and bar * epb <= breath_eighth < (bar + 1) * epb:
        local = breath_eighth - bar * epb
        _clear_slot(support, local * 2)
        _clear_slot(support, local * 2 + 1)
    return (
        _lead_bar(bar, melody, epb, breath_eighth if _breath_in_bar(breath_eighth, bar, epb) else None, apex),
        _events_from_slots(bar, support, 2),
        _events_from_slots(bar, low, 3),
    )


def _breath_in_bar(breath_eighth: int | None, bar: int, epb: int) -> bool:
    return breath_eighth is not None and bar * epb <= breath_eighth < (bar + 1) * epb


def _dance(
    melody: list[int],
    chord_at: dict[int, Chord],
    plans: dict[int, tuple[str, str, Phrase | None]],
    choices: list[tuple[Phrase, str, str]],
    musical_bars: int,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
    phrases: tuple[Phrase, ...],
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    apex = _apex_eighths(phrases)
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for bar, (pattern, band, phrase) in plans.items():
        if pattern != "dance" or bar >= musical_bars:
            continue
        chord = chord_at[bar]
        nxt = chord_at.get(bar + 1)
        next_pattern = plans[bar + 1][0] if bar + 1 < musical_bars else None
        ends_phrase = phrase is not None and bar == (phrase.end - 1) // epb
        following = _following_pattern(phrase, choices)
        leaving = ends_phrase and following != "dance"
        breath = None
        if (
            leaving
            and following is not None
            and phrase is not None
            and phrase.end - phrase.start >= _HELD_EIGHTHS
        ):
            breath = phrase.end - 1
        approach = None
        if (
            not leaving
            and next_pattern == "dance"
            and nxt is not None
            and _falls_a_fifth(chord, nxt)
        ):
            approach = _approach_pitch(nxt, bass_low, bass_high)
        bar_lead, bar_support, bar_low = _dance_bar(
            bar,
            chord=chord,
            melody=melody,
            epb=epb,
            band=band,
            beats=meter.beats,
            bass_low=bass_low,
            bass_high=bass_high,
            mid_low=mid_low,
            mid_high=mid_high,
            approach=approach,
            leaving=leaving,
            breath_eighth=breath,
            apex=apex,
        )
        lead.extend(bar_lead)
        support.extend(bar_support)
        low.extend(bar_low)
    return lead, support, low


def _render_barrios(
    melody: list[int],
    chord_at: dict[int, Chord],
    kind_at: dict[int, str],
    band_at: dict[int, str],
    phrases: tuple[Phrase, ...],
    musical_bars: int,
    total_eighths: int,
    bpm: int,
    character: MovementCharacter | None,
    character_at: tuple[MovementCharacter | None, ...] | list[MovementCharacter | None] | None,
    bass_low: int,
    bass_high: int,
    mid_low: int,
    mid_high: int,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], int]:
    meter = active_meter()
    epb = meter.eighths_per_bar
    plans, choices = _assign_barrios(
        phrases, kind_at, band_at, musical_bars, bpm, character, character_at
    )

    def selected(name: str) -> set[int]:
        return {bar for bar, plan in plans.items() if plan[0] == name}

    pedal = selected("pedal")
    arpeggio = selected("arpeggio")
    tremolo = selected("tremolo")
    andante = selected("andante")
    dance = selected("dance")
    fast = bpm >= BARRIOS_TREMOLO_MIN_BPM
    line = _melody_line(melody, phrases, musical_bars)
    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    eighth_bars = pedal | arpeggio | andante
    if eighth_bars:
        lead.extend(
            _fill_eighth_bars([event for event in line if event.bar in eighth_bars], eighth_bars, epb)
        )
    for bar in sorted(pedal):
        root = _clamp(chord_at[bar].pitches[0], bass_low, bass_high)
        low.append(_hit(bar, 0.0, meter.quarter_beats, root, 3, _BASS))
        support.append(_hit(bar, 0.0, meter.quarter_beats, None, 2, 0))
    if arpeggio:
        inner, bass = _arpeggio(
            melody,
            chord_at,
            kind_at,
            band_at,
            musical_bars,
            rolling=False,
            character=character,
            character_at=character_at,
            bass_low=bass_low,
            bass_high=bass_high,
            mid_low=mid_low,
            mid_high=mid_high,
            only=arpeggio,
        )
        support.extend(_fill_eighth_bars(inner, arpeggio, epb))
        low.extend(_fill_eighth_bars(bass, arpeggio, epb))
    if andante:
        inner, bass = _andante(
            melody,
            chord_at,
            phrases,
            musical_bars,
            bass_low,
            bass_high,
            mid_low,
            mid_high,
            andante,
        )
        support.extend(_fill_eighth_bars(inner, andante, epb))
        low.extend(_fill_eighth_bars(bass, andante, epb))
    if tremolo:
        tremolo_lead, tremolo_inner, tremolo_bass = _tremolo(
            melody,
            chord_at,
            kind_at,
            musical_bars,
            bpm,
            bass_low,
            bass_high,
            mid_low,
            mid_high,
            phrases,
            only=tremolo,
        )
        lead.extend(tremolo_lead)
        support.extend(tremolo_inner)
        low.extend(tremolo_bass)
    if dance:
        dance_lead, dance_support, dance_low = _dance(
            melody,
            chord_at,
            plans,
            choices,
            musical_bars,
            bass_low,
            bass_high,
            mid_low,
            mid_high,
            phrases,
        )
        lead.extend(dance_lead)
        support.extend(dance_support)
        low.extend(dance_low)
    if not fast:
        return (
            list(with_rests(lead, total_eighths)),
            list(with_rests(support, total_eighths)),
            list(with_rests(low, total_eighths)),
            2,
        )
    return lead, support, low, 4
