"""One nylon guitar, three voices.

Sor keeps a study texture: the price is the top voice, chord tones fill the
weak eighths, and the root sits on the strong beats. Villa-Lobos rolls a
chord-tone pattern under that line. Barrios repeats the melody as a tremolo
and puts the thumb on the beat. Brouwer writes the modern row: a lyrical
ballad, a Cuban tumbao, a staccato ostinato, or a sarabande accent. Bach is
the Baroque row at 96. Each row reads the written guitar bounds from the
active register, so a transposed key stays inside the same sounding range.
"""

from __future__ import annotations

import math
from dataclasses import replace

from app.sonify.chords import Chord
from app.sonify.form import active_meter
from app.sonify.keys import C_KEY, MovementCharacter, active_register
from app.sonify.model import DynamicEvent, HarmonyEvent, NoteEvent, Score
from app.sonify.phrasing import Phrase, quantize_strong_beats, written
from app.sonify.quantize import C_MAJOR_PCS, C_NATURAL_MINOR_PCS, scale_from_classes

GUITAR_BPM = {"bach": 96, "classic": 88, "villa": 100, "barrios": 120, "brouwer": 108}
# Listening tests: a tremolo only reads as a sung line from 90 BPM up, sits
# best around 120, and can run to 140. A Barrios movement under that floor
# is not sped up and gets no tremolo at all: it keeps its slow tempo and
# sings Andante Religioso (with Julia Florida thumb_cantabile in the bridge).
BARRIOS_TREMOLO_MIN_BPM = 90


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
# Inside one p-a-m-i cluster the fingers sit 6, 3, 4, 6 under the quarter's
# thumb. At thumb 58 that is a=52, m=55, i=54, a=52.
_TREMOLO_FILL_OFFSETS = (-6, -3, -4, -6)
_TREMOLO_FILL_PATTERN = tuple(58 + offset for offset in _TREMOLO_FILL_OFFSETS)
# Reference thumb. The quarter arch in `_tremolo_quarter` moves around it.
_TREMOLO_THUMB = 58
# Four quarters: 54, 58, 62, 59. Three quarters: 54, 62, 58.
_TREMOLO_QUARTER_OFFSETS = {4: (-4, 0, 4, 1), 3: (-4, 4, 0)}
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
    sections: tuple | None = None,
    rel_span: float = 1.0,
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
    from app.sonify.guitar_patterns import render_patterned_voices

    lead, support, low, divisions = render_patterned_voices(
        melody=melody,
        raw_pitches=list(pitches),
        phrases=phrases,
        chord_at=chord_at,
        kind_at=kind_at,
        band_at=band_at,
        musical_bars=musical_bars,
        total_eighths=total_eighths,
        bpm=bpm,
        ensemble=ensemble,
        mode=mode,
        character=character,
        character_at=character_at,
        sections=sections,
        rel_span=rel_span,
        register=register,
    )
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


def assert_playable(score: Score, key=C_KEY, profiles: str | dict | tuple | list = "study"):
    """Report an unplayable guitar voicing. Does not rewrite the score."""
    from app.sonify.guitar_patterns import assert_playable as _assert_playable

    return _assert_playable(score, key=key, profiles=profiles)


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


def _tremolo_quarter(index: int, quarters: int) -> int:
    """Thumb level for one quarter, before band and the region arch."""
    offsets = _TREMOLO_QUARTER_OFFSETS.get(4 if quarters >= 4 else 3)
    return _TREMOLO_THUMB + offsets[min(index, len(offsets) - 1)]


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
    two sixteenths. The thumb is its own voice. It strikes the root and fifth
    together on each quarter and rings through it, never yielding the downbeat
    of a chord change. Its level walks 54, 58, 62, 59 across a 4/4 bar, and
    54, 62, 58 across three quarters. The fill sits 6, 3, 4, 6 under that
    level, so the beat at 58 is still a=52, m=55, i=54. The colour on a chord
    change uses the same level as the thumb of that beat.
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
        quarters = max(1, epb // 2)
        for cluster_index, cluster in enumerate(range(0, epb * grain, _TREMOLO_CLUSTER)):
            eighth = cluster // grain
            beat = cluster * duration
            sung = melody[bar * epb + eighth]
            level = _tremolo_quarter(cluster_index, quarters)
            if cluster_index == 0 and changed:
                # The colour joins the downbeat, but the thumb keeps the root:
                # yielding it left chord-change bars with no bass at all.
                # It takes this beat's level, or it would outsing a soft thumb.
                color = _color_below(chord, sung, mid_low, mid_high, bass_low)
                inner.append(_hit(bar, beat, cluster_beats, color, 2, level))
            else:
                inner.append(_hit(bar, beat, cluster_beats, None, 2, _INNER))
            bass.append(_hit(bar, beat, cluster_beats, root, 3, level))
            if len(chord.pitches) >= 3:
                fifth = _clamp(chord.pitches[2], bass_low, bass_high)
                if fifth != root:
                    bass.append(_hit(bar, beat, cluster_beats, fifth, 3, level))
            for repeat in range(_TREMOLO_CLUSTER):
                line.append(
                    _hit(
                        bar,
                        beat + repeat * duration,
                        duration,
                        sung,
                        1,
                        level + _TREMOLO_FILL_OFFSETS[repeat],
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
    """Eighths of a real melodic peak.

    A flat phrase has one pitch, so its apex is the whole run. Marking that
    run used to hammer every intro and outro eighth at ``_MELODY_APEX``. A
    phrase contributes a peak only when it actually moves.
    """
    eighths: set[int] = set()
    for phrase in phrases:
        if not phrase.runs:
            continue
        distinct = {run.midi for run in phrase.runs}
        if phrase.rise <= 0 or len(distinct) <= 1:
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


def _slur(
    events: list[NoteEvent],
    phrases: tuple[Phrase, ...],
    *,
    skip_bars: set[int] | None = None,
) -> list[NoteEvent]:
    """Hammer rarely, and only onto a stressed note after the opening phrase.

    The nylon voice plays a slur as a left-hand hammer. A leap, a rest, a new
    phrase, an unstressed step, a tremolo sixteenth, and anything in the first
    phrase stay plucked. A stress is the phrase apex (or an accented attack
    already carrying the apex velocity). The kept steps are spread through
    the eligible stresses, capped under one attack in twenty. Notes in
    `skip_bars` stay plucked too: a Preludio canto is never a hammer-on.
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
        blocked = bool(skip_bars) and any(
            result[index].bar in skip_bars for index in (*left, *right)
        )
        if (
            same_phrase
            and target_phrase != 0
            and stressed
            and held_step
            and 1 <= interval <= 2
            and touches
            and not blocked
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
