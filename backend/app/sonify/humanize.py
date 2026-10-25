"""Nudge only flat runs, after the score is already written.

A plateau is a run of attacks in one Score field that share a velocity.
The run moves only when the nearest different attack on each side, if it
exists, is more than CAP away. A step of 1 or 2 freezes the whole run, which
keeps the Etude arches and any other landing whose neighbor is that close.
`tie_stop` is not an attack. It copies the attack it continues.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from app.sonify.model import NoteEvent, Score

CAP = 2
_CHOICES = (-2, -1, 0, 1, 2)
_FIELDS = ("high", "lead", "support", "comp", "low")
_TICKS = 480

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
        updated[field] = tuple(_copy_ties(notes, heard))
    return replace(score, **updated)


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
    """A tied continuation keeps the attack's heard velocity, not the written one."""
    order = sorted(range(len(original)), key=lambda index: _attack_key(original[index]))
    chain: dict[int, int] = {}
    for index in order:
        note = original[index]
        if note.midi is None or note.velocity is None:
            continue
        if _is_attack(note):
            velocity = heard[index].velocity
            if note.tie_start and velocity is not None:
                chain[note.midi] = velocity
            else:
                chain.pop(note.midi, None)
            continue
        if not note.tie_stop:
            continue
        source = chain.get(note.midi)
        if source is None:
            continue
        if heard[index].velocity != source:
            heard[index] = replace(heard[index], velocity=source)
        if note.tie_start:
            chain[note.midi] = source
        else:
            chain.pop(note.midi, None)
    return heard
