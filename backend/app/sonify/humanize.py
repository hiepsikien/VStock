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
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from app.sonify.model import NoteEvent, Phrase, Score, TempoEvent

CAP = 2
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
# Ambient breathes on a long note: two quarters, four eighths.
_LONG_EIGHTHS = 4

OffsetAt = Callable[[str, str, str, int, float], int]


def chosen_offset(variant: str, ensemble: str, field: str, bar: int, beat: float) -> int:
    """Stable mix of the group key. Python's hash() changes between processes."""
    tick = int(round(float(beat) * _TICKS))
    raw = f"{variant}|{ensemble}|{field}|{bar}|{tick}".encode()
    value = 2166136261
    for byte in raw:
        value ^= byte
        value = (value * 16777619) & 0xFFFFFFFF
    return _CHOICES[value % 5]


def humanize(score: Score, *, offset_at: OffsetAt = chosen_offset) -> Score:
    """Return a new score. Written pitches, durations, and printed dynamics stay."""
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
            for note in run:
                key = _group(field, note)
                offsets.setdefault(
                    key,
                    _clamp_offset(offset_at(score.variant, score.ensemble, field, note.bar, note.beat)),
                )
    _repair(hits, offsets, bar_beats)
    updated: dict[str, tuple[NoteEvent, ...]] = {}
    for field in _FIELDS:
        notes = getattr(score, field)
        heard = _apply(field, notes, offsets)
        if score.variant == "guitar":
            heard = _clamp_guitar(notes, heard, score.ensemble)
        updated[field] = tuple(_copy_ties(notes, heard))
    return replace(score, **updated, tempos=_tempo_clock(score))


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
    if previous and previous[0].velocity is not None and abs(previous[0].velocity - velocity) <= CAP:
        return False
    if following and following[0].velocity is not None and abs(following[0].velocity - velocity) <= CAP:
        return False
    return True


def _clamp_offset(value: int) -> int:
    return max(-CAP, min(CAP, int(value)))


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
    for Bach and Sor, and 69..79 for the other guitar ensembles.
    """
    ceiling = 73 if ensemble in {"bach", "classic"} else 79
    clamped: list[NoteEvent] = []
    for note, heard_note in zip(original, heard):
        written = note.velocity
        current = heard_note.velocity
        if written is None or current is None or not _is_attack(note):
            clamped.append(heard_note)
            continue
        if note.hairpin:
            # A reprinted scale or swarm hairpin already has its velocity.
            # The snap window would fold every step above 64 onto one ceiling.
            velocity = written
        elif written <= 64:
            velocity = min(64, current)
        else:
            velocity = max(69, min(ceiling, current))
        clamped.append(heard_note if velocity == current else replace(heard_note, velocity=velocity))
    return clamped


def _apply(field: str, notes: tuple[NoteEvent, ...], offsets: dict[tuple[str, int, int, int], int]) -> list[NoteEvent]:
    heard: list[NoteEvent] = []
    for note in notes:
        if not _is_attack(note):
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


def _tempo_clock(score: Score) -> tuple[TempoEvent, ...]:
    """Phrase breath on one clock. The end yields the time the opening took."""
    delta = _TEMPO_DELTA.get(score.variant, 0.01)
    if delta <= 0 or not score.phrases:
        return ()
    bar_beats = float(score.bar_beats)
    if bar_beats <= 0:
        return ()
    nominal = float(score.bpm)
    piece_end = score.bars * bar_beats
    divisions = score.divisions if score.divisions > 0 else 2
    raw: list[tuple[float, float, int]] = []
    order = 0
    for phrase in score.phrases:
        if score.variant == "ambient" and not _long_note(phrase):
            continue
        start = phrase.start / 2.0
        end = min(phrase.end / 2.0, piece_end)
        if end - start < _MIN_PHRASE_BEATS - 1e-9:
            continue
        for beat, bpm in _phrase_tempos(start, end, nominal, delta, divisions):
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


def _place(beat: float, bar_beats: float) -> tuple[int, float]:
    bar = int(math.floor((beat + 1e-9) / bar_beats))
    local = round(beat - bar * bar_beats, 4)
    if local >= bar_beats - 1e-4:
        return bar + 1, 0.0
    return bar, local
