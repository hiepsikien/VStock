"""Nudge only flat runs, after the score is already written.

A plateau is a run of attacks in one Score field that share a velocity.
The run moves only when the nearest different attack on each side, if it
exists, is more than CAP away. A step of 1 or 2 freezes the whole run, which
keeps the Etude arches and any other landing whose neighbor is that close.
`tie_stop` is not an attack. It copies the attack it continues only when
both were written at the same velocity. A swell peak keeps its own number.

The shared clock is a `<sound tempo>` curve on `score.tempos`. Each phrase
starts slightly fast and ends slightly slow, so the beat-weighted BPM
deviation inside the phrase is 0. Every step sits on the score's division
grid: a division centered on a step takes the mean of the two sides.

Guitar Torroba keeps that one grid and adds a bar lean and an eighth-slot
lilt. Each tier sums to 0 inside the phrase. The three move together, and
the whole phrase scales only when their sum passes 10%.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from app.sonify.dynamics import contrast_velocity
from app.sonify.model import NoteEvent, Phrase, Score, TempoEvent
from app.sonify.params import active_params

CAP = 2
# The plateau gate is a musical decision, not the offset ceiling. Keeping it
# separate lets the humanize knob grow without rewriting the freeze structure.
FREEZE_GAP = 2
_CHOICES = (-2, -1, 0, 1, 2)
_FIELDS = ("high", "lead", "support", "comp", "low")
_TICKS = 480
# Fraction of the written BPM. Jazz stays small beside swing. Minimalist stays
# under 1%. A phrase shorter than two quarters has no room for the pair.
_TEMPO_DELTA = {
    "symphony": 0.01,
    "guitar": 0.01,
    "jazz": 0.0025,
    "minimalist": 0.005,
    "ambient": 0.01,
}
_RAMP_BEATS = 3.0
_MIN_PHRASE_BEATS = 2.0
# Torroba's phrase breath is wider than the other guitars. A closing phrase
# is still the same symmetric pair, not a deeper ritard. The bar lean and the
# lilt are separate zero-sum tiers on that grid. Past ±10% the phrase scales.
_TORROBA_OPEN_DELTA = 0.035
_TORROBA_CLOSE_DELTA = 0.050
_TEMPO_CAP = 0.10
_LILT_DELTA = 0.04
# A rasgueado fan strikes on 1/12 or 2/12. The downbeat itself is not a fan.
_FAN_LIMIT = 0.25 - 1e-6
_ONSET_TOL = 1e-4
# Ambient breathes on a long note: two quarters, four eighths.
_LONG_EIGHTHS = 4

OffsetAt = Callable[[str, str, str, int, float], int]


def _stable_unit(value: int) -> float:
    """A deterministic fraction in [0, 1) from the FNV value.

    Never Python's hash(): it is randomized per process, and the same params
    must give the same offset in every worker.
    """
    return ((value >> 8) & 0xFFFF) / 65536.0


def chosen_offset(
    variant: str,
    ensemble: str,
    field: str,
    bar: int,
    beat: float,
    humanize: float = 1.0,
) -> int:
    """Stable mix of the group key. Python's hash() changes between processes."""
    tick = int(round(float(beat) * _TICKS))
    raw = f"{variant}|{ensemble}|{field}|{bar}|{tick}".encode()
    value = 2166136261
    for byte in raw:
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    base = _CHOICES[value % 5]
    target = base * humanize
    magnitude = abs(target)
    whole = int(magnitude)
    if whole < magnitude and _stable_unit(value) < magnitude - whole:
        whole += 1
    offset = whole if target >= 0 else -whole
    return max(-3, min(3, offset))


def humanize(
    score: Score,
    *,
    offset_at: OffsetAt | None = None,
    fan_hold: bool = True,
    params=None,
) -> Score:
    """Return a new score. Written pitches, durations, and printed dynamics stay."""
    values = active_params() if params is None else params
    humanize_factor = float(values.get("humanize", 1.0))
    breath_factor = float(values.get("breath", 1.0))
    if humanize_factor == 0.0 and breath_factor == 0.0:
        # The legacy `_nh` file skipped this function entirely.
        return score
    chooser = offset_at or (
        lambda variant, ensemble, field, bar, beat: chosen_offset(
            variant, ensemble, field, bar, beat, humanize_factor
        )
    )
    bar_beats = score.bar_beats
    offsets: dict[tuple[str, int, int, int], int] = {}
    hits: list[_Hit] = []
    for field in _FIELDS:
        notes = getattr(score, field)
        attacks = [note for note in notes if _is_attack(note)]
        for note in attacks:
            hits.append(_Hit(field, note, _group(field, note)))
        ordered = sorted(attacks, key=_attack_key)
        runs = _runs(ordered)
        for index, run in enumerate(runs):
            previous = runs[index - 1] if index else None
            following = runs[index + 1] if index + 1 < len(runs) else None
            if not _movable(run, previous, following):
                continue
            if humanize_factor == 0.0:
                continue
            for note in run:
                key = _group(field, note)
                offsets.setdefault(
                    key,
                    _clamp_offset(chooser(score.variant, score.ensemble, field, note.bar, note.beat)),
                )
    _repair(hits, offsets, bar_beats)
    updated: dict[str, tuple[NoteEvent, ...]] = {}
    # Default keeps the old guitar fold even when a score has no movable run.
    # A zero-humanize profile must not fold: its offsets are all zero.
    clamp_guitar = score.variant == "guitar" and (
        humanize_factor != 0.0 or any(offsets.values())
    )
    for field in _FIELDS:
        notes = getattr(score, field)
        heard = _apply(field, notes, offsets)
        if clamp_guitar:
            heard = _clamp_guitar(notes, heard, score.ensemble)
        updated[field] = tuple(_copy_ties(notes, heard))
    return replace(
        score,
        **updated,
        tempos=_tempo_clock(score, fan_hold=fan_hold, breath=breath_factor),
    )


@dataclass(frozen=True)
class _Hit:
    field: str
    note: NoteEvent
    key: tuple[str, int, int, int]


def _is_attack(note: NoteEvent) -> bool:
    return note.midi is not None and note.velocity is not None and not note.tie_stop


def _attack_key(note: NoteEvent) -> tuple[int, int, int]:
    return note.bar, _tick(note.beat), note.midi or 0


def _tick(beat: float) -> int:
    return int(round(float(beat) * _TICKS))


def _group(field: str, note: NoteEvent) -> tuple[str, int, int, int]:
    return field, note.bar, _tick(note.beat), note.velocity or 0


def _runs(ordered: list[NoteEvent]) -> list[list[NoteEvent]]:
    runs: list[list[NoteEvent]] = []
    current: list[NoteEvent] = []
    for note in ordered:
        if current and note.velocity != current[0].velocity:
            runs.append(current)
            current = []
        current.append(note)
    if current:
        runs.append(current)
    return runs


def _movable(run: list[NoteEvent], previous: list[NoteEvent] | None, following: list[NoteEvent] | None) -> bool:
    """One attack is not a plateau. A neighbor within CAP freezes the run."""
    if len(run) < 2 or run[0].velocity is None:
        return False
    velocity = run[0].velocity
    if previous and previous[0].velocity is not None and abs(previous[0].velocity - velocity) <= FREEZE_GAP:
        return False
    if following and following[0].velocity is not None and abs(following[0].velocity - velocity) <= FREEZE_GAP:
        return False
    return True


def _clamp_offset(value: int) -> int:
    # `chosen_offset` already rounded; the ceiling belongs to the knob, not CAP.
    return max(-3, min(3, int(value)))


def _clamp_velocity(value: int) -> int:
    return max(1, min(127, value))


def _heard(hit: _Hit, offsets: dict[tuple[str, int, int, int], int]) -> int:
    written = hit.note.velocity or 0
    return _clamp_velocity(written + offsets.get(hit.key, 0))


def _start(hit: _Hit, bar_beats: float) -> float:
    return hit.note.bar * bar_beats + hit.note.beat


def _overlaps(left: _Hit, right: _Hit, bar_beats: float) -> bool:
    left_start = _start(left, bar_beats)
    right_start = _start(right, bar_beats)
    return left_start < right_start + right.note.duration_beats and right_start < left_start + left.note.duration_beats


def _repair(hits: list[_Hit], offsets: dict[tuple[str, int, int, int], int], bar_beats: float) -> None:
    """Shrink a chosen offset toward 0 until the written order still holds.

    The sign stays. Flipping it would make the same score render two ways.
    Consecutive attacks in one field are included: ±2 on both sides of a
    step of 3 or 4 would otherwise erase that step.
    """
    pairs = _pairs(hits, bar_beats)
    stuck: set[tuple[str, int, int, int]] = set()
    budget = sum(abs(value) for value in offsets.values()) + 1
    for _ in range(budget):
        found: tuple[_Hit, _Hit, tuple[str, int, int, int]] | None = None
        for left, right in pairs:
            higher, lower = (left, right) if (left.note.velocity or 0) > (right.note.velocity or 0) else (right, left)
            if _heard(higher, offsets) > _heard(lower, offsets):
                continue
            choice = _shrink_choice(higher, lower, offsets, stuck)
            if choice is None:
                continue
            found = (higher, lower, choice)
            break
        if found is None:
            return
        higher, lower, choice = found
        before_higher = _heard(higher, offsets)
        before_lower = _heard(lower, offsets)
        current = offsets[choice]
        offsets[choice] = current - 1 if current > 0 else current + 1
        if _heard(higher, offsets) == before_higher and _heard(lower, offsets) == before_lower:
            offsets[choice] = current
            stuck.add(choice)


def _pairs(hits: list[_Hit], bar_beats: float) -> list[tuple[_Hit, _Hit]]:
    pairs: list[tuple[_Hit, _Hit]] = []
    by_field: dict[str, list[_Hit]] = {}
    for hit in hits:
        by_field.setdefault(hit.field, []).append(hit)
    for field_hits in by_field.values():
        ordered = sorted(field_hits, key=lambda hit: _attack_key(hit.note))
        for left, right in zip(ordered, ordered[1:]):
            if left.note.velocity != right.note.velocity:
                pairs.append((left, right))
    ordered_hits = sorted(hits, key=lambda hit: (hit.field, _attack_key(hit.note)))
    if bar_beats > 0 and ordered_hits:
        # Overlap only reaches across bars whose starts are within the longest
        # note of the hits. Bucket by start bar, then walk each left's window in
        # index order so the pair list stays identical to the full scan.
        starts = [_start(hit, bar_beats) for hit in ordered_hits]
        start_bars = [int(math.floor(start / bar_beats)) for start in starts]
        buckets: dict[int, list[int]] = {}
        for index, bar in enumerate(start_bars):
            buckets.setdefault(bar, []).append(index)
        lowest, highest = min(start_bars), max(start_bars)
        longest = max(max(0.0, hit.note.duration_beats) for hit in ordered_hits)
        lookback = int(math.ceil(longest / bar_beats)) + 1
        for index, left in enumerate(ordered_hits):
            start = starts[index]
            finish = start + left.note.duration_beats
            first_bar = max(lowest, start_bars[index] - lookback)
            last_bar = (
                int(math.floor(finish / bar_beats)) if finish > start else start_bars[index]
            )
            last_bar = min(highest, last_bar)
            candidates: list[int] = []
            for bar in range(first_bar, last_bar + 1):
                candidates.extend(buckets.get(bar, ()))
            candidates.sort()
            for other in candidates:
                if other <= index:
                    continue
                right = ordered_hits[other]
                if left.field == right.field or left.note.velocity == right.note.velocity:
                    continue
                if _overlaps(left, right, bar_beats):
                    pairs.append((left, right))
    else:
        for index, left in enumerate(ordered_hits):
            for right in ordered_hits[index + 1 :]:
                if left.field == right.field or left.note.velocity == right.note.velocity:
                    continue
                if _overlaps(left, right, bar_beats):
                    pairs.append((left, right))
    pairs.sort(
        key=lambda pair: (
            min(_start(pair[0], bar_beats), _start(pair[1], bar_beats)),
            pair[0].field,
            pair[1].field,
            pair[0].note.bar,
            _tick(pair[0].note.beat),
            pair[1].note.bar,
            _tick(pair[1].note.beat),
            pair[0].note.midi or 0,
            pair[1].note.midi or 0,
        )
    )
    return pairs


def _shrink_choice(
    higher: _Hit,
    lower: _Hit,
    offsets: dict[tuple[str, int, int, int], int],
    stuck: set[tuple[str, int, int, int]],
) -> tuple[str, int, int, int] | None:
    options: list[tuple[str, int, int, int]] = []
    if higher.key not in stuck and offsets.get(higher.key, 0) < 0:
        options.append(higher.key)
    if lower.key not in stuck and offsets.get(lower.key, 0) > 0:
        options.append(lower.key)
    if not options:
        return None
    return max(options, key=lambda key: (abs(offsets.get(key, 0)), key))


def _clamp_guitar(original: tuple[NoteEvent, ...], heard: list[NoteEvent], ensemble: str) -> list[NoteEvent]:
    """Warm notes stay nylon. A written snap stays inside the nail layer.

    A written note at or under 64 stays at or under 64. Snaps sit in 69..73
    for Bach, Sor, and Torroba, and 69..79 for the other guitar ensembles at
    Default. Both ends follow the dynamics knob, so lowering contrast keeps
    the snap ladder rather than folding every step onto 69.
    """
    ceiling = contrast_velocity(73 if ensemble in {"bach", "classic", "torroba"} else 79)
    floor_velocity = contrast_velocity(69)
    clamped: list[NoteEvent] = []
    for note, heard_note in zip(original, heard):
        written = note.velocity
        current = heard_note.velocity
        if written is None or current is None or not _is_attack(note):
            clamped.append(heard_note)
            continue
        if note.hairpin or note.pinned:
            # A reprinted scale or swarm hairpin already has its velocity.
            # The snap window would fold every step above 64 onto one ceiling.
            # A pinned rasgueado was decided by the dynamic layer before us.
            velocity = written
        elif written <= 64:
            velocity = min(64, current)
        else:
            velocity = max(floor_velocity, min(ceiling, current))
        clamped.append(heard_note if velocity == current else replace(heard_note, velocity=velocity))
    return clamped


def _apply(field: str, notes: tuple[NoteEvent, ...], offsets: dict[tuple[str, int, int, int], int]) -> list[NoteEvent]:
    heard: list[NoteEvent] = []
    for note in notes:
        if not _is_attack(note):
            heard.append(note)
            continue
        if note.pinned:
            heard.append(note)
            continue
        offset = offsets.get(_group(field, note), 0)
        velocity = _clamp_velocity((note.velocity or 0) + offset)
        heard.append(note if velocity == note.velocity else replace(note, velocity=velocity))
    return heard


def _copy_ties(original: tuple[NoteEvent, ...], heard: list[NoteEvent]) -> list[NoteEvent]:
    """Copy the heard attack only when the tie was written at that same velocity.

    A swell opens at 49 and peaks at 64 or 80 on the tied half. That peak is a
    written change, so it stays. A tie that repeats the attack's number takes
    the humanized one.
    """
    order = sorted(range(len(original)), key=lambda index: _attack_key(original[index]))
    chain: dict[int, tuple[int, int]] = {}
    for index in order:
        note = original[index]
        if note.midi is None or note.velocity is None:
            continue
        if _is_attack(note):
            velocity = heard[index].velocity
            if note.tie_start and velocity is not None:
                chain[note.midi] = (note.velocity, velocity)
            else:
                chain.pop(note.midi, None)
            continue
        if not note.tie_stop:
            continue
        source = chain.get(note.midi)
        if source is None:
            continue
        written, lifted = source
        if note.velocity == written and heard[index].velocity != lifted:
            heard[index] = replace(heard[index], velocity=lifted)
        if not note.tie_start:
            chain.pop(note.midi, None)
    return heard


def _tempo_clock(score: Score, *, fan_hold: bool = True, breath: float = 1.0) -> tuple[TempoEvent, ...]:
    """Phrase breath on one clock. The end yields the time the opening took.

    Torroba guitar samples the same phrase arc, then adds the bar lean and
    the lilt before the change-detection pass. A following short phrase still
    finds the nominal tempo waiting at this phrase's end.
    """
    delta = _TEMPO_DELTA.get(score.variant, 0.01) * breath
    if delta <= 0 or not score.phrases:
        return ()
    bar_beats = float(score.bar_beats)
    if bar_beats <= 0:
        return ()
    nominal = float(score.bpm)
    piece_end = score.bars * bar_beats
    divisions = score.divisions if score.divisions > 0 else 2
    torroba = _torroba_clock(score, divisions)
    raw: list[tuple[float, float, int]] = []
    order = 0
    for phrase in score.phrases:
        if score.variant == "ambient" and not _long_note(phrase):
            continue
        start = phrase.start / 2.0
        end = min(phrase.end / 2.0, piece_end)
        if end - start < _MIN_PHRASE_BEATS - 1e-9:
            continue
        if torroba:
            series = _torroba_phrase_tempos(
                score, phrase, start, end, nominal, divisions, fan_hold=fan_hold, breath=breath
            )
        else:
            series = _phrase_tempos(start, end, nominal, delta, divisions)
        for beat, bpm in series:
            if 0 <= beat < piece_end - 1e-9:
                raw.append((round(beat, 4), bpm, order))
                order += 1
        if end < piece_end - 1e-9:
            raw.append((round(end, 4), nominal, order))
            order += 1
    raw.sort(key=lambda item: (item[0], item[2]))
    collapsed: list[tuple[float, float]] = []
    for beat, bpm, _order in raw:
        if collapsed and abs(collapsed[-1][0] - beat) <= 1e-4:
            collapsed[-1] = (beat, bpm)
            continue
        collapsed.append((beat, bpm))
    emitted: list[tuple[float, float]] = []
    for beat, bpm in collapsed:
        if emitted and abs(emitted[-1][1] - bpm) < 0.001:
            continue
        emitted.append((beat, bpm))
    tempos: list[TempoEvent] = []
    for beat, bpm in emitted:
        bar, local = _place(beat, bar_beats)
        if bar < 0 or bar >= score.bars:
            continue
        tempos.append(TempoEvent(bar, local, bpm))
    return tuple(tempos)


def _long_note(phrase: Phrase) -> bool:
    return any(run.length >= _LONG_EIGHTHS for run in phrase.runs)


def _phrase_tempos(
    start: float, end: float, nominal: float, delta: float, divisions: int
):
    """Fast hold, then a centered ramp, then the matching slow hold.

    A phrase of four quarters or fewer is the pair itself: the midpoint is the
    step. A longer phrase spreads that step across three quarters, and each
    ramp segment uses the tempo at its own center so the deviations cancel.
    The clock only moves on a division. Each division takes the tempo at its
    center, and a division sitting on a step takes the mean of the two sides.
    """
    regions = _tempo_regions(start, end, delta)
    start_units = int(round(start * divisions))
    end_units = int(round(end * divisions))
    previous: float | None = None
    for unit in range(start_units, end_units):
        factor = _tempo_factor((unit + 0.5) / divisions, regions)
        bpm = round(nominal * factor, 2)
        if previous is not None and abs(previous - bpm) < 0.001:
            continue
        yield round(unit / divisions, 4), bpm
        previous = bpm


def _tempo_regions(
    start: float, end: float, delta: float
) -> tuple[tuple[float, float, float], ...]:
    """`(left, right, factor)` spans. The right edge of one span is the next step."""
    mid = (start + end) / 2.0
    if end - start <= 4.0 + 1e-9:
        return (
            (start, mid, 1.0 + delta),
            (mid, end, 1.0 - delta),
        )
    ramp_start = mid - _RAMP_BEATS / 2.0
    regions = [(start, ramp_start, 1.0 + delta)]
    for index in range(int(_RAMP_BEATS)):
        left = ramp_start + index
        mix = ((left + 0.5) - ramp_start) / _RAMP_BEATS
        factor = (1.0 + delta) * (1.0 - mix) + (1.0 - delta) * mix
        regions.append((left, left + 1.0, factor))
    regions.append((ramp_start + _RAMP_BEATS, end, 1.0 - delta))
    return tuple(span for span in regions if span[1] - span[0] > 1e-9)


def _tempo_factor(
    beat: float, regions: tuple[tuple[float, float, float], ...]
) -> float:
    for index, (left, right, factor) in enumerate(regions):
        if index and abs(beat - left) <= 1e-6:
            return (regions[index - 1][2] + factor) / 2.0
        if left - 1e-9 <= beat < right - 1e-9:
            return factor
    return regions[-1][2]


def _torroba_clock(score: Score, divisions: int) -> bool:
    """The three-tier clock is guitar Torroba on an even division grid."""
    return (
        score.variant == "guitar"
        and score.ensemble == "torroba"
        and divisions >= 2
        and divisions % 2 == 0
    )


def _torroba_phrase_tempos(
    score: Score,
    phrase: Phrase,
    start: float,
    end: float,
    nominal: float,
    divisions: int,
    *,
    fan_hold: bool = True,
    breath: float = 1.0,
):
    """Phrase arc, bar lean, and lilt, sampled on the division grid.

    Each tier sums to 0 across the phrase's units. When the stacked delta
    passes ±10%, the whole phrase scales by the same factor. One unit is
    never clamped on its own.
    """
    breath_delta = (
        _TORROBA_CLOSE_DELTA if phrase.closes else _TORROBA_OPEN_DELTA
    ) * breath
    regions = _tempo_regions(start, end, breath_delta)
    start_units = int(round(start * divisions))
    end_units = int(round(end * divisions))
    count = end_units - start_units
    if count <= 0:
        return
    bar_delta = _bar_deltas(score, start, end, divisions, start_units, count)
    lilt_delta = _lilt_deltas(score, start, end, divisions, start_units, count, breath=breath)
    combined: list[float] = []
    for offset in range(count):
        unit = start_units + offset
        phrase_delta = _tempo_factor((unit + 0.5) / divisions, regions) - 1.0
        combined.append(phrase_delta + bar_delta[offset] + lilt_delta[offset])
    peak = max(abs(value) for value in combined)
    scale = _TEMPO_CAP / peak if peak > _TEMPO_CAP else 1.0
    base_bpm = [nominal * (1.0 + scale * value) for value in combined]
    fan_mult = (
        _fan_hold_multipliers(score, phrase, start, end, divisions, start_units, count, base_bpm)
        if fan_hold
        else [1.0] * count
    )
    previous: float | None = None
    for offset, value in enumerate(combined):
        bpm = base_bpm[offset] * fan_mult[offset]
        bpm = round(max(nominal * 0.60, min(nominal * 1.40, bpm)), 2)
        if previous is not None and abs(previous - bpm) < 0.001:
            continue
        yield round((start_units + offset) / divisions, 4), bpm
        previous = bpm


def _bar_deltas(
    score: Score,
    start: float,
    end: float,
    divisions: int,
    start_units: int,
    count: int,
) -> list[float]:
    """Lean on bars that sit wholly inside the phrase. A cut bar stays 0."""
    deltas = [0.0] * count
    bar_beats = float(score.bar_beats)
    for bar in range(score.bars):
        bar_start = bar * bar_beats
        bar_end = bar_start + bar_beats
        if bar_start < start - 1e-9 or bar_end > end + 1e-9:
            continue
        lean = _bar_lean(score, _is_rasgueado(score, bar))
        if lean is None:
            continue
        window, first_delta, second_delta = lean
        first = int(round(bar_start * divisions))
        split = int(round((bar_start + window) * divisions))
        last = int(round(bar_end * divisions))
        for unit in range(first, last):
            index = unit - start_units
            if 0 <= index < count:
                deltas[index] = first_delta if unit < split else second_delta
    return deltas


def _bar_lean(score: Score, fan: bool) -> tuple[float, float, float] | None:
    """`(window_beats, delta_before, delta_after)`. A fan replaces the plain bar.

    6/8 leans across the two dotted quarters. 3/4 leans across beat 1 and the
    two beats after it. Plain 4/4 does not lean; only its fan does.
    """
    if score.beats == 6 and score.beat_type == 8:
        return (1.5, -0.04, 0.04) if fan else (1.5, -0.02, 0.02)
    if score.beats == 3 and score.beat_type == 4:
        return (1.0, -0.04, 0.02) if fan else (1.0, -0.02, 0.01)
    if score.beats == 4 and score.beat_type == 4 and fan:
        return (1.0, -0.045, 0.015)
    return None


def _is_rasgueado(score: Score, bar: int) -> bool:
    """A fan onset sits strictly between the downbeat and the next sixteenth."""
    for field in ("lead", "support"):
        notes = getattr(score, field)
        for note in notes:
            if note.bar == bar and 0.0 < note.beat < _FAN_LIMIT:
                return True
    return False


def _lilt_deltas(
    score: Score,
    start: float,
    end: float,
    divisions: int,
    start_units: int,
    count: int,
    *,
    breath: float = 1.0,
) -> list[float]:
    """Non-overlapping eighth pairs. E–S slows then hurries; S–E does the reverse.

    A pair is taken only when both slots lie inside the phrase, then the walk
    steps over both. E–S–E therefore leaves the last eighth unpaired.
    """
    deltas = [0.0] * count
    lilt = _LILT_DELTA * breath
    bar_beats = float(score.bar_beats)
    slot_count = int(round(bar_beats * 2.0))
    if slot_count <= 0:
        return deltas
    by_bar: dict[int, list[NoteEvent]] = {}
    for note in score.lead:
        if _is_attack(note):
            by_bar.setdefault(note.bar, []).append(note)
    for bar in range(score.bars):
        attacks = by_bar.get(bar, [])
        kinds = [_slot_kind(attacks, slot) for slot in range(slot_count)]
        slot = 0
        while slot < slot_count:
            nxt = slot + 1
            pair = (kinds[slot], kinds[nxt]) if nxt < slot_count else None
            inside = nxt < slot_count and _slots_inside(bar, slot, bar_beats, start, end)
            if inside and pair == ("E", "S"):
                _paint_slot(deltas, bar, slot, -lilt, bar_beats, divisions, start_units)
                _paint_slot(deltas, bar, nxt, lilt, bar_beats, divisions, start_units)
                slot += 2
                continue
            if inside and pair == ("S", "E"):
                _paint_slot(deltas, bar, slot, lilt, bar_beats, divisions, start_units)
                _paint_slot(deltas, bar, nxt, -lilt, bar_beats, divisions, start_units)
                slot += 2
                continue
            slot += 1
    return deltas


def _slots_inside(bar: int, slot: int, bar_beats: float, start: float, end: float) -> bool:
    """Both this eighth and the next one sit inside `[start, end)`."""
    left = bar * bar_beats + slot * 0.5
    right = left + 1.0
    return left >= start - 1e-9 and right <= end + 1e-9


def _fan_hold_multipliers(
    score: Score,
    phrase: Phrase,
    start: float,
    end: float,
    divisions: int,
    start_units: int,
    count: int,
    base_bpm: list[float],
) -> list[float]:
    """Multiplicative BPM factors that delay only the note after a fan.

    Slow `[anchor, next)` by `f` and speed `[next, bar_end)` by `g` so the
    added time is exactly `D` beats and the bar keeps its length. `D` is
    `1/12` of a quarter for a strong fan and `1/24` for a soft one. A short
    span (`< 3D`) is skipped so the dip never becomes a hiccup.
    """
    del phrase
    multipliers = [1.0] * count
    bar_beats = float(score.bar_beats)
    if bar_beats <= 0 or count <= 0:
        return multipliers
    for bar in range(score.bars):
        bar_start = bar * bar_beats
        bar_end = bar_start + bar_beats
        if bar_start < start - 1e-9 or bar_end > end + 1e-9:
            continue
        fan = [
            note
            for note in (*score.lead, *score.support, *score.low)
            if note.bar == bar and note.midi is not None and 0.0 <= note.beat < 0.25
        ]
        if not any(note.beat > 0.0 for note in fan):
            continue
        anchor = max(note.beat for note in fan)
        strong = len({note.midi for note in fan}) >= 5
        delay = (1.0 / 12.0) if strong else (1.0 / 24.0)
        later = sorted(
            (
                note
                for note in (*score.lead, *score.support, *score.low)
                if note.bar == bar
                and note.midi is not None
                and note.velocity is not None
                and not note.tie_stop
                and note.beat > anchor + 1e-9
            ),
            key=lambda note: note.beat,
        )
        if not later:
            continue
        next_beat = later[0].beat
        span = next_beat - anchor
        comp = bar_beats - next_beat
        if span <= 0.0 or span < 3.0 * delay or comp <= delay:
            continue
        first = max(int(round((bar_start + anchor) * divisions)), start_units)
        split = int(round((bar_start + next_beat) * divisions))
        last = min(int(round(bar_end * divisions)), start_units + count)
        split = min(split, last)
        if first >= split:
            continue
        slow = sum(
            60.0 / (base_bpm[unit - start_units] * 12.0) for unit in range(first, split)
        )
        fast = sum(
            60.0 / (base_bpm[unit - start_units] * 12.0) for unit in range(split, last)
        )
        delay_seconds = delay * 60.0 / base_bpm[first - start_units]
        if slow <= 0.0 or fast <= delay_seconds:
            continue
        f = min(delay_seconds / (slow + delay_seconds), 0.25)
        extra = slow * f / (1.0 - f)
        g = extra / (fast - extra) if fast > extra else 0.25
        if g > 0.25:
            g = 0.25
            extra = fast * g / (1.0 + g)
            f = extra / (slow + extra)
        for unit in range(first, split):
            multipliers[unit - start_units] *= 1.0 - f
        for unit in range(split, last):
            multipliers[unit - start_units] *= 1.0 + g
    return multipliers


def _paint_slot(
    deltas: list[float],
    bar: int,
    slot: int,
    value: float,
    bar_beats: float,
    divisions: int,
    start_units: int,
) -> None:
    left = bar * bar_beats + slot * 0.5
    first = int(round(left * divisions))
    last = int(round((left + 0.5) * divisions))
    for unit in range(first, last):
        index = unit - start_units
        if 0 <= index < len(deltas):
            deltas[index] = value


def _slot_kind(attacks: list[NoteEvent], slot: int) -> str | None:
    """`E` is one eighth. `S` is two sixteenths or three notes of 1/6.

    Four sixteenths on the grid are S–S, so the pair walk skips them. A grace
    at 1.75 is a single offbeat sixteenth. A 3-sixteenth run at 1.25..1.75
    spills into the next eighth and must not become S there.
    """
    left = slot * 0.5
    right = left + 0.5
    inside = [note for note in attacks if left - 1e-9 <= note.beat < right - 1e-9]
    if len(inside) == 1:
        note = inside[0]
        if abs(note.beat - left) <= _ONSET_TOL and abs(note.duration_beats - 0.5) <= _ONSET_TOL:
            return "E"
        return None
    if _two_sixteenths(inside, left) and not _continues_pickup(attacks, left):
        return "S"
    if _three_sixths(inside, left):
        return "S"
    return None


def _two_sixteenths(notes: list[NoteEvent], left: float) -> bool:
    if len(notes) != 2:
        return False
    ordered = sorted(notes, key=lambda note: note.beat)
    targets = (left, left + 0.25)
    return all(
        abs(note.beat - target) <= _ONSET_TOL and abs(note.duration_beats - 0.25) <= _ONSET_TOL
        for note, target in zip(ordered, targets)
    )


def _three_sixths(notes: list[NoteEvent], left: float) -> bool:
    if len(notes) != 3:
        return False
    sixth = 1.0 / 6.0
    ordered = sorted(notes, key=lambda note: note.beat)
    targets = (left, left + sixth, left + 2.0 * sixth)
    return all(
        abs(note.beat - target) <= _ONSET_TOL and abs(note.duration_beats - sixth) <= _ONSET_TOL
        for note, target in zip(ordered, targets)
    )


def _continues_pickup(attacks: list[NoteEvent], slot_start: float) -> bool:
    """True when this sixteenth pair is the tail of a run that began off the eighth.

    The note a quarter-beat earlier poisons the slot unless that note is itself
    the back half of a sixteenth pair already sitting on the previous eighth.
    Four grid sixteenths stay S–S. The run 1.25, 1.50, 1.75 does not.
    """
    pickup = slot_start - 0.25
    pair_start = slot_start - 0.5
    if not _sixteenth_at(attacks, pickup):
        return False
    return not _sixteenth_at(attacks, pair_start)


def _sixteenth_at(attacks: list[NoteEvent], beat: float) -> bool:
    return any(
        abs(note.beat - beat) <= _ONSET_TOL and abs(note.duration_beats - 0.25) <= _ONSET_TOL
        for note in attacks
    )


def _place(beat: float, bar_beats: float) -> tuple[int, float]:
    bar = int(math.floor((beat + 1e-9) / bar_beats))
    local = round(beat - bar * bar_beats, 4)
    if local >= bar_beats - 1e-4:
        return bar + 1, 0.0
    return bar, local
