"""Raw-price impulse detector for classical-guitar scale runs.

The detector reads `raw_pitches` (one MIDI pitch per eighth) and emits
waves that can later become scale passages. It does not allocate those
passages or realize notes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.sonify.model import PERIOD, PriceImpulse

# Sixteenth-note scale runs are allowed from this tempo up. Kept separate
# from BARRIOS_TREMOLO_MIN_BPM so Sor at 88 BPM can scale without turning
# on Grand Solo, fanfare, perpetual, or tremolo.
SCALE_SIXTEENTH_MIN_BPM = 88

_Direction = Literal["up", "down"]
_Kind = Literal["up", "down", "flat"]


@dataclass(frozen=True)
class _Leg:
    start: int
    end: int
    kind: _Kind


@dataclass(frozen=True)
class _Wave:
    direction: _Direction
    legs: tuple[_Leg, ...]


def detect_price_impulses(
    raw_pitches: Sequence[int],
    section_starts: tuple[int, ...],
    *,
    epb: int,
    strong_eighths: tuple[int, ...],
    pedal_bars: frozenset[int] = frozenset(),
) -> tuple[PriceImpulse, ...]:
    """Detect up/down price waves inside each non-pedal body span.

    `section_starts` are eighth indexes. `pedal_bars` are bar numbers
    (intro, outro, warmup, cooldown); every eighth of those bars is
    skipped. `strong_eighths` is the meter's strong-beat set and has no
    default. Impulses are returned in time order.
    """
    if epb <= 0 or len(raw_pitches) < 2:
        return ()
    strong = frozenset(strong_eighths)
    found: list[PriceImpulse] = []
    for lo, hi in _body_spans(len(raw_pitches), section_starts, epb, pedal_bars):
        for wave in _coalesce(_legs(raw_pitches, lo, hi), raw_pitches):
            impulse = _best_window(raw_pitches, wave, hi, epb, strong)
            if impulse is not None:
                found.append(impulse)
    found.sort(key=lambda impulse: (impulse.start, impulse.target))
    return tuple(found)


def _body_spans(
    total: int,
    section_starts: tuple[int, ...],
    epb: int,
    pedal_bars: frozenset[int],
) -> list[tuple[int, int]]:
    """Half-open eighth spans inside each section, with pedal bars removed."""
    bounds = sorted({0, *(start for start in section_starts if 0 < start < total)})
    bounds.append(total)
    spans: list[tuple[int, int]] = []
    for left, right in zip(bounds, bounds[1:]):
        eighth = left
        while eighth < right:
            if eighth // epb in pedal_bars:
                eighth += 1
                continue
            run = eighth
            while eighth < right and eighth // epb not in pedal_bars:
                eighth += 1
            if eighth - run >= 2:
                spans.append((run, eighth))
    return spans


def _legs(raw: Sequence[int], lo: int, hi: int) -> list[_Leg]:
    """Split [lo, hi) into up-legs, down-legs, and flat-holds.

    A flat-hold is a constant pitch lasting at least PERIOD eighths
    (PERIOD samples, the same count `Phrase` uses for a held note).
    Shorter plateaus stay inside the surrounding directional leg.
    """
    if hi - lo < 2:
        return []
    last = hi - 1
    flats: list[tuple[int, int]] = []
    index = lo
    while index <= last:
        end = index
        while end < last and raw[end + 1] == raw[index]:
            end += 1
        if end - index + 1 >= PERIOD:
            flats.append((index, end))
        index = end + 1

    legs: list[_Leg] = []
    cursor = lo
    for flat_start, flat_end in flats:
        if flat_start > cursor:
            legs.extend(_directional_legs(raw, cursor, flat_start))
        legs.append(_Leg(flat_start, flat_end, "flat"))
        cursor = flat_end
    if cursor < last:
        legs.extend(_directional_legs(raw, cursor, last))
    return legs


def _directional_legs(raw: Sequence[int], start: int, end: int) -> list[_Leg]:
    """Up and down legs over inclusive eighths [start, end]. No flat-hold inside."""
    legs: list[_Leg] = []
    index = start
    while index < end:
        probe = index + 1
        while probe <= end and raw[probe] == raw[index]:
            probe += 1
        if probe > end:
            break
        kind: _Direction = "up" if raw[probe] > raw[index] else "down"
        cursor = probe
        while cursor < end:
            delta = raw[cursor + 1] - raw[cursor]
            if kind == "up" and delta < 0:
                break
            if kind == "down" and delta > 0:
                break
            cursor += 1
        legs.append(_Leg(index, cursor, kind))
        index = cursor
    return legs


def _coalesce(legs: list[_Leg], raw: Sequence[int]) -> list[_Wave]:
    """Join Impulse–Retreat–Impulse, plus at most one more retreat pair."""
    waves: list[_Wave] = []
    index = 0
    while index < len(legs):
        leg = legs[index]
        if leg.kind == "up":
            direction: _Direction = "up"
        elif leg.kind == "down":
            direction = "down"
        else:
            index += 1
            continue
        group = [leg]
        retreat_kind: _Direction = "down" if direction == "up" else "up"
        cursor = index
        added = 0
        while added < 2 and cursor + 2 < len(legs):
            retreat = legs[cursor + 1]
            follow = legs[cursor + 2]
            if retreat.kind != retreat_kind or follow.kind != direction:
                break
            if not _retreat_ok(raw, group[0], group[-1], retreat, follow):
                break
            group.append(retreat)
            group.append(follow)
            added += 1
            cursor += 2
        waves.append(_Wave(direction, tuple(group)))
        index = cursor + 1
    return waves


def _retreat_ok(
    raw: Sequence[int],
    wave_start: _Leg,
    before: _Leg,
    retreat: _Leg,
    follow: _Leg,
) -> bool:
    """Local retreat rules from plan section 2.3 step 2. The 50% test is inclusive."""
    retreat_len = retreat.end - retreat.start
    before_len = before.end - before.start
    if not 1 <= retreat_len <= 3 or retreat_len > before_len:
        return False
    retreat_delta = abs(raw[retreat.end] - raw[retreat.start])
    before_delta = abs(raw[before.end] - raw[before.start])
    if retreat_delta * 2 > before_delta:
        return False
    prices = [raw[index] for index in range(retreat.start, retreat.end + 1)]
    origin = raw[wave_start.start]
    if before.kind == "up":
        if min(prices) <= origin:
            return False
        peak = max(raw[index] for index in range(before.start, before.end + 1))
        return raw[follow.end] > peak
    if max(prices) >= origin:
        return False
    trough = min(raw[index] for index in range(before.start, before.end + 1))
    return raw[follow.end] < trough


def _best_window(
    raw: Sequence[int],
    wave: _Wave,
    span_hi: int,
    epb: int,
    strong: frozenset[int],
) -> PriceImpulse | None:
    start, target = _trim(raw, wave)
    length = target - start
    if length > 4 * epb:
        windows = _subwindows(raw, wave, start, epb)
    elif length >= 2:
        windows = [(start, target)]
    else:
        return None

    best: PriceImpulse | None = None
    seen: set[tuple[int, int]] = set()
    for window_start, window_target in windows:
        if (window_start, window_target) in seen:
            continue
        seen.add((window_start, window_target))
        chosen = _with_snap(raw, wave, window_start, window_target, span_hi, epb, strong)
        if chosen is None:
            continue
        if best is None or _rank(chosen) > _rank(best):
            best = chosen
    return best


def _rank(impulse: PriceImpulse) -> tuple[float, int, int]:
    """Higher score wins. Equal scores keep the longer, then earlier, window."""
    return (impulse.score, impulse.target - impulse.start, -impulse.start)


def _trim(raw: Sequence[int], wave: _Wave) -> tuple[int, int]:
    """Drop a flat prefix and end on the first eighth of the wave's extreme."""
    start = wave.legs[0].start
    end = wave.legs[-1].end
    while start < end and raw[start] == raw[start + 1]:
        start += 1
    if wave.direction == "up":
        extreme = max(raw[index] for index in range(start, end + 1))
    else:
        extreme = min(raw[index] for index in range(start, end + 1))
    target = start
    while target < end and raw[target] != extreme:
        target += 1
    return start, target


def _subwindows(
    raw: Sequence[int],
    wave: _Wave,
    trimmed_start: int,
    epb: int,
) -> list[tuple[int, int]]:
    """Windows of at most four bars from an impulse open to an impulse extreme."""
    impulses = [leg for leg in wave.legs if leg.kind == wave.direction]
    windows: list[tuple[int, int]] = []
    limit = 4 * epb
    for index, left in enumerate(impulses):
        open_at = left.start
        if index == 0 and left.start <= trimmed_start <= left.end:
            open_at = trimmed_start
        for right in impulses[index:]:
            extreme = _leg_extreme(raw, right, wave.direction)
            if extreme <= open_at:
                continue
            start = open_at
            while start < extreme and raw[start] == raw[start + 1]:
                start += 1
            if 2 <= extreme - start <= limit:
                windows.append((start, extreme))
    return windows


def _leg_extreme(raw: Sequence[int], leg: _Leg, direction: _Direction) -> int:
    if direction == "up":
        value = max(raw[index] for index in range(leg.start, leg.end + 1))
    else:
        value = min(raw[index] for index in range(leg.start, leg.end + 1))
    for index in range(leg.start, leg.end + 1):
        if raw[index] == value:
            return index
    return leg.end


def _with_snap(
    raw: Sequence[int],
    wave: _Wave,
    start: int,
    raw_target: int,
    span_hi: int,
    epb: int,
    strong: frozenset[int],
) -> PriceImpulse | None:
    """Try the nearest later strong beat on the same pitch. Keep the raw extreme if it fails."""
    snapped = _snap_target(raw, raw_target, span_hi, epb, strong)
    if snapped is not None:
        accepted = _make(raw, wave, start, snapped, epb)
        if accepted is not None:
            return accepted
    return _make(raw, wave, start, raw_target, epb)


def _snap_target(
    raw: Sequence[int],
    target: int,
    span_hi: int,
    epb: int,
    strong: frozenset[int],
) -> int | None:
    if target % epb in strong:
        return None
    cursor = target
    while cursor + 1 < span_hi and raw[cursor + 1] == raw[target]:
        cursor += 1
        if cursor % epb in strong:
            return cursor
    return None


def _make(
    raw: Sequence[int],
    wave: _Wave,
    start: int,
    target: int,
    epb: int,
) -> PriceImpulse | None:
    length = target - start
    if length < 2:
        return None
    if wave.direction == "up" and raw[target] <= raw[start]:
        return None
    if wave.direction == "down" and raw[target] >= raw[start]:
        return None
    net = abs(raw[target] - raw[start])
    path = sum(abs(raw[index + 1] - raw[index]) for index in range(start, target))
    spans = _retreats_inside(wave, start, target)
    lengths = tuple(end - begin for begin, end in spans)
    if not _passes(length, lengths, net, path, epb):
        return None
    depth = sum(abs(raw[end] - raw[begin]) for begin, end in spans)
    numer = net + 2 * depth
    adjusted = 1.0 if path > 0 and numer >= path else (numer / path if path else 0.0)
    multiplier = 1.15 if spans else 1.0
    score = net * (1.0 + 0.5 * (net / length)) * adjusted * multiplier
    return PriceImpulse(
        start=start,
        target=target,
        direction=wave.direction,
        net_span=net,
        adjusted_efficiency=adjusted,
        score=score,
        retreat_spans=spans,
        sub_bar=length < epb,
    )


def _retreats_inside(wave: _Wave, start: int, target: int) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    for leg in wave.legs:
        if leg.kind == wave.direction or leg.kind == "flat":
            continue
        if leg.start >= start and leg.end <= target:
            spans.append((leg.start, leg.end))
    return tuple(spans)


def _passes(
    length: int,
    retreats: tuple[int, ...],
    net: int,
    path: int,
    epb: int,
) -> bool:
    """Disjoint invariant table from plan section 2.3. Length is target - start."""
    if path <= 0 or length < 2 or length > 4 * epb:
        return False
    count = len(retreats)
    longest = max(retreats, default=0)
    total = sum(retreats)
    if length <= 3:
        return count == 0 and net >= max(4, length) and net == path
    if length < epb:
        return (
            count <= 1
            and longest <= 1
            and total <= 1
            and net >= max(4, length)
            and net * 2 >= path
        )
    budget = (length * 30) // 100
    if length <= 2 * epb:
        return (
            count <= 1
            and longest <= 2
            and total <= budget
            and net >= 5
            and net * 20 >= path * 9
        )
    return (
        count <= 2
        and longest <= 3
        and total <= budget
        and net >= 6
        and net * 20 >= path * 9
    )
