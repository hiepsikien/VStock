"""Scale-passage allocation and realization for the classical guitar.

The price detector and the octave lock live elsewhere. This module reads
`ctx.impulses` and spends the 30% body budget: passages, then perpetual
motion, then group-2 tier-1 descents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

try:
    from app.sonify.guitar_scales import SCALE_SIXTEENTH_MIN_BPM
except ImportError:  # the detector module lands separately
    SCALE_SIXTEENTH_MIN_BPM = 88

from app.sonify.guitar_bach import (
    _bach_keep_bass_below,
    _chaconne_bass_slots,
    _gigue_plan,
    _quarter_ok,
    bach_group2_intrinsic_eighths,
    bach_group2_window,
    bach_scale_step,
)
from app.sonify.guitar_barrios import (
    _apply_perpetual,
    _catedral_preludio,
    _perpetual_bars,
    barrios_chromatic_approach,
    barrios_scale_step,
)
from app.sonify.guitar_brouwer import (
    brouwer_group2_intrinsic_eighths,
    brouwer_group2_window,
    brouwer_scale_step,
)
from app.sonify.guitar_patterns import (
    _BASS,
    _INNER,
    _MELODY,
    _MELODY_APEX,
    _PEDAL,
    _Ctx,
    _bar_pattern,
    _choose_inner,
    _dur16,
    _eighth_event,
    _playable,
    _position_ok,
    _sounding_midi,
    _spell16,
    _splice,
    _start16,
)
from app.sonify.guitar_sor import classic_scale_step
from app.sonify.guitar_villa import villa_open_candidates, villa_scale_step
from app.sonify.model import NoteEvent

_GROUP1 = frozenset({"tremolo", "etude1", "etude11", "thumb_cantabile"})
_BACH_GROUP2 = frozenset({"bach_chaconne", "bach_gigue", "bach_sarabande"})


@dataclass(frozen=True)
class ScalePassage:
    """One accepted run. `tier` is `passage` or `tier1`."""

    start: int
    target: int
    direction: str
    net_span: int
    score: float
    retreat_spans: tuple[tuple[int, int], ...]
    sub_bar: bool
    passage_eighths: int
    replaced_base_intrinsic_eighths: int
    tier: str = "passage"


@dataclass(frozen=True)
class ScalePlan:
    body_eighths: int
    base_intrinsic_eighths: int
    max_scale_eighths: int
    room: int
    passages: tuple[ScalePassage, ...]
    perpetual_bars: tuple[int, ...]
    tier1: tuple[ScalePassage, ...]
    room_after: int

    @property
    def scale_eighths(self) -> frozenset[int]:
        found: set[int] = set()
        for passage in (*self.passages, *self.tier1):
            found.update(range(passage.start, passage.target + 1))
        return frozenset(found)


@dataclass
class _Impulse:
    start: int
    target: int
    direction: str
    net_span: int
    adjusted_efficiency: float
    score: float
    retreat_spans: tuple[tuple[int, int], ...]
    sub_bar: bool


@dataclass
class _Slot:
    eighth: int
    sub: int
    dur16: int
    anchor: bool
    retreat: bool


def _is_group2(pattern: str) -> bool:
    return pattern in _BACH_GROUP2 or pattern == "sarabande"


def _body_eighths(ctx: _Ctx) -> int:
    total = 0
    for bar in range(ctx.bars):
        if ctx.kind_at.get(bar, "phrase") not in _PEDAL:
            total += ctx.epb
    return total


def _intrinsic_eighths(ctx: _Ctx, patterns: list[str]) -> set[int]:
    found: set[int] = set()
    for bar in range(ctx.bars):
        if ctx.kind_at.get(bar, "phrase") in _PEDAL:
            continue
        pattern = _bar_pattern(ctx, bar, patterns)
        if pattern in _BACH_GROUP2:
            found |= bach_group2_intrinsic_eighths(ctx, bar, pattern)
        elif pattern == "sarabande":
            found |= brouwer_group2_intrinsic_eighths(ctx, bar)
    return found


def _clip_window(ctx: _Ctx, bar: int, pattern: str) -> tuple[int, int] | None:
    if pattern in _BACH_GROUP2:
        return bach_group2_window(ctx, bar, pattern)
    if pattern == "sarabande":
        return brouwer_group2_window(ctx, bar)
    return None


def _normalize(raw: object, epb: int) -> _Impulse | None:
    start = int(getattr(raw, "start"))
    target = int(getattr(raw, "target"))
    if target <= start:
        return None
    length = target - start
    if length < 2 or length > 4 * epb:
        return None
    direction = getattr(raw, "direction")
    if direction not in {"up", "down"}:
        return None
    spans = tuple((int(lo), int(hi)) for lo, hi in (getattr(raw, "retreat_spans", ()) or ()))
    return _Impulse(
        start=start,
        target=target,
        direction=direction,
        net_span=int(getattr(raw, "net_span", 0)),
        adjusted_efficiency=float(getattr(raw, "adjusted_efficiency", 1.0)),
        score=float(getattr(raw, "score", 0.0)),
        retreat_spans=spans,
        sub_bar=bool(getattr(raw, "sub_bar", length < epb)),
    )


def _touched_bars(start: int, target: int, epb: int) -> range:
    return range(start // epb, target // epb + 1)


def _touches_excluded(ctx: _Ctx, patterns: list[str], start: int, target: int) -> bool:
    framed_preludio = _catedral_preludio(ctx)
    for bar in _touched_bars(start, target, ctx.epb):
        if bar < 0 or bar >= ctx.bars:
            return True
        if ctx.kind_at.get(bar, "phrase") in _PEDAL:
            return True
        pattern = _bar_pattern(ctx, bar, patterns)
        if pattern in _GROUP1:
            return True
        if pattern == "preludio" and framed_preludio:
            return True
    return False


def _major_bridge(impulse: _Impulse, epb: int) -> bool:
    return impulse.target - impulse.start >= epb and impulse.net_span >= 6


def _covers_group2_opening(ctx: _Ctx, patterns: list[str], start: int, target: int) -> bool:
    """True when the run covers the first bar of a group-2 pattern."""
    if start >= target:
        return True
    first = start // ctx.epb
    last = (target - 1) // ctx.epb
    for bar in range(first, last + 1):
        pattern = _bar_pattern(ctx, bar, patterns)
        if not _is_group2(pattern):
            continue
        origin = bar
        while origin > 0 and _bar_pattern(ctx, origin - 1, patterns) == pattern:
            origin -= 1
        if bar <= origin:
            return True
    return False


def _overlaps_group2(ctx: _Ctx, patterns: list[str], start: int, target: int) -> bool:
    if start >= target:
        return False
    first = start // ctx.epb
    last = (target - 1) // ctx.epb
    return any(_is_group2(_bar_pattern(ctx, bar, patterns)) for bar in range(first, last + 1))


def _passage_allowed(ctx: _Ctx, patterns: list[str], impulse: _Impulse) -> bool:
    if _touches_excluded(ctx, patterns, impulse.start, impulse.target):
        return False
    if _overlaps_group2(ctx, patterns, impulse.start, impulse.target):
        if not _major_bridge(impulse, ctx.epb):
            return False
        if _covers_group2_opening(ctx, patterns, impulse.start, impulse.target):
            return False
    return True


def _gap_ok(start: int, target: int, accepted: list[ScalePassage], epb: int) -> bool:
    for other in accepted:
        if start >= other.target:
            if start - other.target < epb:
                return False
        elif other.start >= target:
            if other.start - target < epb:
                return False
        else:
            return False
    return True


def _bar_overlaps(bar: int, passages: list[ScalePassage], epb: int) -> bool:
    lo = bar * epb
    hi = lo + epb
    for passage in passages:
        if passage.start < hi and lo < passage.target:
            return True
    return False


def _tier1_clips(ctx: _Ctx, patterns: list[str], impulses: list[_Impulse]) -> list[_Impulse]:
    clips: list[_Impulse] = []
    seen: set[tuple[int, int]] = set()
    for impulse in impulses:
        if impulse.direction != "down":
            continue
        if _major_bridge(impulse, ctx.epb):
            continue
        length = impulse.target - impulse.start
        if not (length < ctx.epb or impulse.net_span < 6):
            continue
        first = impulse.start // ctx.epb
        last = max(first, (impulse.target - 1) // ctx.epb)
        for bar in range(max(0, first), min(ctx.bars, last + 1)):
            pattern = _bar_pattern(ctx, bar, patterns)
            window = _clip_window(ctx, bar, pattern)
            if window is None:
                continue
            lo, hi = window
            start = max(impulse.start, lo)
            target = min(impulse.target, hi)
            if target - start < 2:
                continue
            key = (start, target)
            if key in seen:
                continue
            seen.add(key)
            overlaps = tuple((lo_r, hi_r) for lo_r, hi_r in impulse.retreat_spans if hi_r > start and lo_r < target)
            clips.append(
                _Impulse(
                    start=start,
                    target=target,
                    direction="down",
                    net_span=impulse.net_span,
                    adjusted_efficiency=impulse.adjusted_efficiency,
                    score=impulse.score,
                    retreat_spans=overlaps,
                    sub_bar=True,
                )
            )
    return clips


def _as_passage(impulse: _Impulse, intrinsic: set[int], tier: str) -> ScalePassage:
    replaced = sum(1 for eighth in range(impulse.start, impulse.target) if eighth in intrinsic)
    return ScalePassage(
        start=impulse.start,
        target=impulse.target,
        direction=impulse.direction,
        net_span=impulse.net_span,
        score=impulse.score,
        retreat_spans=impulse.retreat_spans,
        sub_bar=impulse.sub_bar,
        passage_eighths=impulse.target - impulse.start,
        replaced_base_intrinsic_eighths=replaced if tier == "passage" else 0,
        tier=tier,
    )


def select_scale_plan(
    ctx: _Ctx,
    patterns: list[str],
    *,
    accept_passage,
    accept_tier1,
) -> ScalePlan:
    """One forward budget pass. `accept_*` returns false when realization aborts."""
    body = _body_eighths(ctx)
    intrinsic = _intrinsic_eighths(ctx, patterns)
    maximum = (30 * body) // 100
    room = max(0, maximum - len(intrinsic))
    empty = ScalePlan(body, len(intrinsic), maximum, room, (), (), (), room)
    if room <= 0:
        return empty
    raw_impulses = [item for item in (_normalize(raw, ctx.epb) for raw in (ctx.impulses or ())) if item is not None]
    raw_impulses.sort(key=lambda item: (-item.score, item.start, item.target))
    accepted: list[ScalePassage] = []
    for impulse in raw_impulses:
        if not _passage_allowed(ctx, patterns, impulse):
            continue
        passage = _as_passage(impulse, intrinsic, "passage")
        delta = passage.passage_eighths - passage.replaced_base_intrinsic_eighths
        if delta > room or not _gap_ok(passage.start, passage.target, accepted, ctx.epb):
            continue
        if not accept_passage(passage):
            continue
        accepted.append(passage)
        room -= delta
    perpetual: list[int] = []
    for bar in _perpetual_candidate_bars(ctx, patterns):
        if _bar_overlaps(bar, accepted, ctx.epb):
            continue
        if ctx.epb > room:
            continue
        perpetual.append(bar)
        room -= ctx.epb
    occupied: set[int] = set()
    for passage in accepted:
        occupied.update(range(passage.start, passage.target + 1))
    tier1: list[ScalePassage] = []
    clips = _tier1_clips(ctx, patterns, raw_impulses)
    clips.sort(key=lambda item: (-item.score, item.start, item.target))
    for clip in clips:
        if any(eighth in occupied for eighth in range(clip.start, clip.target + 1)):
            continue
        passage = _as_passage(clip, intrinsic, "tier1")
        cost = passage.passage_eighths
        if cost > room:
            continue
        if not accept_tier1(passage):
            continue
        tier1.append(passage)
        occupied.update(range(passage.start, passage.target + 1))
        room -= cost
    return ScalePlan(
        body,
        len(intrinsic),
        maximum,
        max(0, maximum - len(intrinsic)),
        tuple(accepted),
        tuple(perpetual),
        tuple(tier1),
        room,
    )


def plan_scale_budget(ctx: _Ctx, patterns: list[str]) -> ScalePlan:
    """Budget outcome assuming every candidate can be realized."""
    return select_scale_plan(ctx, patterns, accept_passage=lambda _passage: True, accept_tier1=lambda _passage: True)


def _perpetual_candidate_bars(ctx: _Ctx, patterns: list[str]) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()
    for index, phrase in enumerate(ctx.phrases):
        if index >= len(patterns) or patterns[index] != "tremolo":
            continue
        for bar in _perpetual_bars(ctx, phrase, 2):
            if bar not in seen:
                seen.add(bar)
                found.append(bar)
    found.sort()
    return found


def _is_strong(ctx: _Ctx, eighth: int) -> bool:
    return eighth % ctx.epb in ctx.strong


def _in_retreat(eighth: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= eighth < hi for lo, hi in spans)


def _flat_into(ctx: _Ctx, eighth: int) -> bool:
    if eighth <= 0 or eighth >= len(ctx.raw):
        return False
    return ctx.raw[eighth] == ctx.raw[eighth - 1]


def _use_sixteenths(ctx: _Ctx, length: int, offset: int) -> bool:
    """Sixteenths from 88 BPM, except a fast 6/8 run longer than one bar.

    A run longer than two bars keeps eighths until its last bar.
    """
    if ctx.bpm < SCALE_SIXTEENTH_MIN_BPM:
        return False
    if ctx.kind == "6/8" and ctx.bpm > 116 and length > ctx.epb:
        return False
    if length > 2 * ctx.epb:
        return offset >= length - ctx.epb
    return True


def _regions(ctx: _Ctx, passage: ScalePassage) -> dict[int, str]:
    length = passage.target - passage.start
    region: dict[int, str] = {}
    for offset in range(length):
        eighth = passage.start + offset
        region[eighth] = "sixteenth" if _use_sixteenths(ctx, length, offset) else "eighth"
    for eighth, kind in list(region.items()):
        if kind != "eighth" or eighth + 1 >= len(ctx.melody):
            continue
        if abs(ctx.melody[eighth + 1] - ctx.melody[eighth]) >= 3:
            region[eighth] = "sixteenth"
    return region


def _dodged(ctx: _Ctx, patterns: list[str], passage: ScalePassage, eighth: int) -> bool:
    if passage.passage_eighths >= ctx.epb or passage.tier == "tier1":
        return False
    if eighth % ctx.epb != 3:
        return False
    return _bar_pattern(ctx, eighth // ctx.epb, patterns) == "elogio_pizz"


def _slots(ctx: _Ctx, patterns: list[str], passage: ScalePassage) -> list[_Slot]:
    region = _regions(ctx, passage)
    slots: list[_Slot] = []
    for eighth in range(passage.start, passage.target):
        if _dodged(ctx, patterns, passage, eighth):
            continue
        retreat = _in_retreat(eighth, passage.retreat_spans)
        if region[eighth] == "sixteenth":
            for sub in (0, 1):
                anchor = sub == 0 and (_is_strong(ctx, eighth) or (not retreat and _flat_into(ctx, eighth)))
                slots.append(_Slot(eighth, sub, 1, anchor, retreat))
        else:
            anchor = _is_strong(ctx, eighth) or (not retreat and _flat_into(ctx, eighth))
            slots.append(_Slot(eighth, 0, 2, anchor, retreat))
    slots.append(_Slot(passage.target, 0, 2, True, False))
    return slots


def _melody_pitch(ctx: _Ctx, eighth: int) -> int:
    if 0 <= eighth < len(ctx.melody):
        return ctx.melody[eighth]
    return ctx.melody[-1] if ctx.melody else 64


def _step_pitch(
    ctx: _Ctx,
    pitch: int,
    toward: int,
    impulse_direction: str,
    approaching: bool,
) -> int:
    if toward == 0:
        return pitch
    if ctx.ensemble == "bach":
        nxt = bach_scale_step(
            ctx,
            pitch,
            toward,
            impulse_direction=impulse_direction,
            approaching_tonic=approaching,
        )
    elif ctx.ensemble == "villa":
        nxt = villa_scale_step(ctx, pitch, toward)
    elif ctx.ensemble == "barrios":
        nxt = barrios_scale_step(ctx, pitch, toward)
    elif ctx.ensemble == "brouwer":
        nxt = brouwer_scale_step(ctx, pitch, toward)
    else:
        nxt = classic_scale_step(ctx, pitch, toward)
    if nxt == pitch or (nxt - pitch) * toward <= 0:
        nxt = pitch + toward
    if abs(nxt - pitch) > 2:
        nxt = pitch + (2 if toward > 0 else -2)
    high = min(ctx.treble_top, ctx.ceiling)
    if nxt < ctx.treble_floor or nxt > high:
        return pitch
    return nxt


def _monotone(
    start: int,
    end: int,
    count: int,
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
) -> list[int] | None:
    """`count` pitches, the first equal to `start` and the last equal to `end`."""
    if count <= 0:
        return None
    if count == 1:
        return [start] if start == end else None
    if abs(end - start) > 2 * (count - 1):
        return None
    notes = [start]
    for index in range(1, count - 1):
        left_after = count - 1 - index
        current = notes[-1]
        gap = end - current
        if abs(gap) > 2 * (left_after + 1):
            return None
        if gap == 0:
            notes.append(current)
            continue
        toward = 1 if gap > 0 else -1
        stepped = _step_pitch(ctx, current, toward, impulse_direction, approaching)
        if toward > 0:
            stepped = min(stepped, end)
        else:
            stepped = max(stepped, end)
        if abs(end - stepped) > 2 * left_after or abs(stepped - current) > 2:
            need = max(1, abs(gap) - 2 * left_after)
            forced = current + toward * min(2, need)
            if toward > 0:
                forced = min(forced, end)
            else:
                forced = max(forced, end)
            if abs(forced - current) > 2 or abs(end - forced) > 2 * left_after:
                forced = current
            stepped = forced
        notes.append(stepped)
    if abs(end - notes[-1]) > 2:
        return None
    notes.append(end)
    if any(abs(right - left) > 2 for left, right in zip(notes, notes[1:])):
        return None
    return notes


def _with_retreat(
    start: int,
    end: int,
    count: int,
    retreat_at: list[int],
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
) -> list[int] | None:
    active = [index for index, flag in enumerate(retreat_at) if flag and index > 0]
    if not active:
        return _monotone(start, end, count, ctx, impulse_direction, approaching)
    last = max(active)
    against = -1 if impulse_direction == "up" else 1
    for depth in (4, 3, 2, 1):
        dip = start
        moved = 0
        for _ in range(depth):
            nxt = _step_pitch(ctx, dip, against, impulse_direction, approaching)
            if nxt == dip or (nxt - dip) * against <= 0:
                break
            dip = nxt
            moved += 1
        if moved < 1:
            continue
        left = _monotone(start, dip, last + 1, ctx, impulse_direction, approaching)
        right = None if left is None else _monotone(dip, end, count - last, ctx, impulse_direction, approaching)
        if left is None or right is None:
            continue
        line = left[:-1] + right
        if len(line) != count:
            continue
        first = min(active)
        if (line[first] - line[first - 1]) * against <= 0:
            continue
        return line
    return None


def _assign(ctx: _Ctx, passage: ScalePassage, slots: list[_Slot]) -> list[int] | None:
    if len(slots) < 2:
        return None
    pitches: list[int | None] = [None] * len(slots)
    for index, slot in enumerate(slots):
        if slot.anchor:
            pitches[index] = _melody_pitch(ctx, slot.eighth)
    anchors = [index for index, slot in enumerate(slots) if slot.anchor]
    if not anchors or anchors[-1] != len(slots) - 1 or pitches[-1] is None:
        return None
    previous = _melody_pitch(ctx, passage.start - 1) if passage.start > 0 else pitches[anchors[0]]
    if anchors[0] == 0:
        if passage.start > 0 and abs(int(pitches[0]) - int(previous)) > 2:
            return None
    else:
        end_pitch = int(pitches[anchors[0]])
        count = anchors[0] + 2
        flags = [False, *(slots[index].retreat for index in range(anchors[0] + 1))]
        approaching = end_pitch % 12 == 0
        line = _with_retreat(int(previous), end_pitch, count, flags, ctx, passage.direction, approaching)
        if line is None:
            return None
        for offset, pitch in enumerate(line[1:]):
            pitches[offset] = pitch
    for left, right in zip(anchors, anchors[1:]):
        if pitches[left] is None or pitches[right] is None:
            return None
        count = right - left + 1
        flags = [slots[left + offset].retreat for offset in range(count)]
        end_pitch = int(pitches[right])
        approaching = end_pitch % 12 == 0
        line = _with_retreat(int(pitches[left]), end_pitch, count, flags, ctx, passage.direction, approaching)
        if line is None:
            return None
        for offset, pitch in enumerate(line):
            pitches[left + offset] = pitch
    if any(pitch is None for pitch in pitches):
        return None
    concrete = [int(pitch) for pitch in pitches]
    if passage.start > 0 and abs(concrete[0] - int(previous)) > 2:
        return None
    if any(abs(right - left) > 2 for left, right in zip(concrete, concrete[1:])):
        return None
    return concrete


def _color_line(ctx: _Ctx, passage: ScalePassage, slots: list[_Slot], pitches: list[int]) -> list[int]:
    colored = list(pitches)
    if ctx.ensemble == "barrios":
        anchors = [index for index, slot in enumerate(slots) if slot.anchor]
        for anchor in anchors:
            if anchor <= 0:
                continue
            approach = anchor - 1
            if slots[approach].anchor:
                continue
            before = colored[approach - 1] if approach > 0 else colored[approach]
            ascending = colored[anchor] >= before
            chromatic = barrios_chromatic_approach(colored[anchor], ascending)
            if abs(chromatic - colored[anchor]) != 1:
                continue
            if approach > 0 and abs(chromatic - colored[approach - 1]) > 2:
                continue
            colored[approach] = chromatic
    if ctx.ensemble == "villa":
        stopped = list(colored)
        for index, slot in enumerate(slots):
            if slot.anchor or index == 0 or index + 1 >= len(colored):
                continue
            toward = 1 if colored[index + 1] >= colored[index - 1] else -1
            for open_pitch in villa_open_candidates(ctx, colored[index - 1], toward):
                if abs(open_pitch - colored[index + 1]) > 2 or abs(open_pitch - colored[index - 1]) > 2:
                    continue
                trial = list(colored)
                trial[index] = open_pitch
                if _groups_ok(slots, trial, ctx.semitones):
                    colored = trial
                    break
        if not _groups_ok(slots, colored, ctx.semitones):
            colored = stopped
    return colored


def _groups_ok(slots: list[_Slot], pitches: list[int], semitones: int) -> bool:
    sounding: dict[int, list[int]] = {}
    written: dict[int, list[int]] = {}
    for slot, pitch in zip(slots, pitches):
        if slot.dur16 != 1:
            continue
        key = (slot.eighth * 2 + slot.sub) // 4
        sounding.setdefault(key, []).append(pitch + semitones)
        written.setdefault(key, []).append(pitch)
    for key, group in sounding.items():
        if not _quarter_ok(group):
            return False
        ordered = sorted(set(written[key]))
        if len(ordered) >= 2 and all(abs(right - left) <= 4 for left, right in zip(ordered, ordered[1:])):
            if not _position_ok(ordered):
                return False
    return True


def _lead_ok(ctx: _Ctx, pitches: list[int]) -> bool:
    for pitch in pitches:
        sounding = pitch + ctx.semitones
        if sounding < 59 or sounding > 81:
            return False
    return True


def _line(ctx: _Ctx, patterns: list[str], passage: ScalePassage) -> tuple[list[_Slot], list[int]] | None:
    slots = _slots(ctx, patterns, passage)
    pitches = _assign(ctx, passage, slots)
    if pitches is None:
        return None
    pitches = _color_line(ctx, passage, slots, pitches)
    if any(abs(right - left) > 2 for left, right in zip(pitches, pitches[1:])):
        return None
    if not _groups_ok(slots, pitches, ctx.semitones) or not _lead_ok(ctx, pitches):
        return None
    return slots, pitches


def _velocity_before(lead: list[NoteEvent], start: int, epb: int) -> int:
    if start <= 0:
        return _MELODY
    when = (start - 1) * 2
    found = None
    found_at = -1
    for event in lead:
        if event.midi is None or event.velocity is None:
            continue
        begin = _start16(event, epb)
        if begin <= when < begin + _dur16(event) and begin >= found_at:
            found = event.velocity
            found_at = begin
    return found if found is not None else _MELODY


def _velocity_curve(count: int, opening: int, arrival: int, ascending: bool) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [arrival]
    raw = [int(round(opening + (arrival - opening) * index / (count - 1))) for index in range(count)]
    if not ascending:
        return raw
    shaped: list[int] = []
    last = raw[0]
    for value in raw:
        last = max(last, value)
        shaped.append(last)
    shaped[-1] = arrival
    return shaped


def _curve(passage: ScalePassage, count: int, previous: int) -> list[int]:
    if passage.direction == "up":
        opening = min(previous, _MELODY_APEX - 6)
        return _velocity_curve(count, opening, _MELODY_APEX, True)
    opening = min(max(previous, _MELODY), _MELODY_APEX)
    return _velocity_curve(count, opening, _MELODY, False)


def _drop_region(events: list[NoteEvent], start: int, end: int, epb: int) -> list[NoteEvent]:
    """Remove sounding time in `[start, end)` without inventing an onset at `end`."""
    lo = start * 2
    hi = end * 2
    kept: list[NoteEvent] = []
    for event in events:
        if event.midi is None:
            kept.append(event)
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if finish <= lo or begin >= hi:
            kept.append(event)
            continue
        if begin < lo:
            kept.extend(
                _spell16(begin, lo - begin, event.midi, epb, event.voice, event.velocity or _BASS, event.accent)
            )
    return kept


def _install_lead(
    lead: list[NoteEvent],
    slots: list[_Slot],
    pitches: list[int],
    velocities: list[int],
    epb: int,
) -> list[NoteEvent]:
    body = list(zip(slots[:-1], pitches[:-1], velocities[:-1]))
    if body:
        runs: list[list[tuple[_Slot, int, int]]] = [[body[0]]]
        for slot, pitch, velocity in body[1:]:
            previous = runs[-1][-1][0]
            previous_end = previous.eighth * 2 + previous.sub + previous.dur16
            this_start = slot.eighth * 2 + slot.sub
            if this_start == previous_end:
                runs[-1].append((slot, pitch, velocity))
            else:
                runs.append([(slot, pitch, velocity)])
        for run in runs:
            fresh: list[NoteEvent] = []
            for slot, pitch, velocity in run:
                fresh.extend(_spell16(slot.eighth * 2 + slot.sub, slot.dur16, pitch, epb, 1, velocity))
            start16 = run[0][0].eighth * 2 + run[0][0].sub
            end16 = run[-1][0].eighth * 2 + run[-1][0].sub + run[-1][0].dur16
            lead = _splice(lead, start16, end16, fresh, epb)
    return _stamp_arrival(lead, slots[-1].eighth, pitches[-1], velocities[-1], epb)


def _stamp_arrival(lead: list[NoteEvent], target: int, pitch: int, velocity: int, epb: int) -> list[NoteEvent]:
    when = target * 2
    rewritten: list[NoteEvent] = []
    stamped = False
    for event in lead:
        if event.midi is None:
            rewritten.append(event)
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if not begin <= when < finish:
            rewritten.append(event)
            continue
        if begin < when:
            rewritten.extend(_spell16(begin, when - begin, event.midi, epb, 1, event.velocity or _MELODY, event.accent))
        rewritten.extend(_spell16(when, finish - when, pitch, epb, 1, velocity, event.accent))
        stamped = True
    if not stamped:
        rewritten.extend(_eighth_event(target, 1, pitch, epb, 1, velocity))
    return rewritten


def _next_onset(events: list[NoteEvent], eighth: int, epb: int) -> int | None:
    found = [
        _start16(event, epb) // 2
        for event in events
        if event.midi is not None and _start16(event, epb) // 2 >= eighth
    ]
    return min(found) if found else None


def _bass_under_slices(ctx: _Ctx, bar: int, slices: list[list[int]]) -> int | None:
    """A root or fifth that stays playable under each eighth, not under their union."""
    if not slices:
        return None
    chord = ctx.chord(bar)
    root = chord.pitches[0] % 12
    fifth = chord.pitches[2] % 12 if len(chord.pitches) > 2 else (root + 7) % 12
    for pc in (root, fifth):
        for note in range(ctx.bass_high, ctx.bass_low - 1, -1):
            if note % 12 != pc:
                continue
            if any(note >= lead for group in slices for lead in group):
                continue
            sounding_bass = note + ctx.semitones
            if all(
                _playable([sounding_bass, *(lead + ctx.semitones for lead in group)])
                for group in slices
            ):
                return note
    return None


def _bass_onsets(ctx: _Ctx, pattern: str, bar: int, start: int, target: int) -> list[int]:
    epb = ctx.epb
    origin = bar * epb

    def inside(eighth: int) -> bool:
        return start <= eighth < target and origin <= eighth < origin + epb

    if pattern == "bach_fuga":
        return []
    if pattern == "bach_chaconne":
        return [origin + slot // 2 for slot in _chaconne_bass_slots(ctx) if inside(origin + slot // 2)]
    if pattern in {"bach_sarabande", "sarabande"}:
        accent = 3 if ctx.kind == "6/8" else min(2, epb - 1)
        return [eighth for eighth in (origin, origin + accent) if inside(eighth)]
    if pattern == "bach_gigue":
        return [origin + offset for offset, _length in _gigue_plan(ctx)["bass"] if inside(origin + offset)]
    return [origin + offset for offset in ctx.strong if inside(origin + offset)]


def _bass_accent(ctx: _Ctx, pattern: str, eighth: int) -> bool:
    local = eighth % ctx.epb
    if pattern == "bach_gigue":
        return local in _gigue_plan(ctx)["down"]
    if pattern in {"bach_sarabande", "sarabande"}:
        accent = 3 if ctx.kind == "6/8" else min(2, ctx.epb - 1)
        return local == accent
    return local == 0


def _leads_at(slots: list[_Slot], pitches: list[int]) -> dict[int, list[int]]:
    found: dict[int, list[int]] = {}
    for slot, pitch in zip(slots, pitches):
        found.setdefault(slot.eighth, []).append(pitch)
    return found


def _rewrite_bass(
    ctx: _Ctx,
    patterns: list[str],
    passage: ScalePassage,
    slots: list[_Slot],
    pitches: list[int],
    lead: list[NoteEvent],
    low: list[NoteEvent],
) -> list[NoteEvent]:
    start, target = passage.start, passage.target
    low = _drop_region(low, start, target, ctx.epb)
    leads = _leads_at(slots, pitches)
    first = start // ctx.epb
    last = max(first, (target - 1) // ctx.epb)
    for bar in range(first, min(ctx.bars, last + 1)):
        pattern = _bar_pattern(ctx, bar, patterns)
        if pattern == "bach_fuga":
            continue
        onsets = _bass_onsets(ctx, pattern, bar, start, target)
        for index, eighth in enumerate(onsets):
            following = onsets[index + 1] if index + 1 < len(onsets) else None
            kept = _next_onset(low, eighth + 1, ctx.epb)
            stops = [item for item in (following, kept) if item is not None]
            if following is None:
                ring = target
                if target % ctx.epb not in ctx.strong:
                    cursor = target + 1
                    limit = min(len(ctx.melody), (bar + 2) * ctx.epb)
                    while cursor < limit and cursor % ctx.epb not in ctx.strong:
                        cursor += 1
                    ring = cursor
                stops.append(ring)
            stop = min(stops) if stops else eighth + 1
            if stop <= eighth:
                continue
            slices: list[list[int]] = []
            for cursor in range(eighth, min(stop, target + 1)):
                group = leads.get(cursor)
                if group:
                    slices.append(group)
            if not slices:
                slices = [[_melody_pitch(ctx, eighth)]]
            pitch = _bass_under_slices(ctx, bar, slices)
            if pitch is None:
                continue
            low.extend(
                _eighth_event(
                    eighth,
                    stop - eighth,
                    pitch,
                    ctx.epb,
                    3,
                    _BASS,
                    accent=_bass_accent(ctx, pattern, eighth),
                )
            )
    if any(_bar_pattern(ctx, bar, patterns) == "bach_fuga" for bar in range(first, min(ctx.bars, last + 1))):
        low = _bach_keep_bass_below(ctx, lead, low)
    return low


def _support_tone(ctx: _Ctx, bar: int, lead_pitch: int, bass: int) -> int | None:
    if not bass < lead_pitch:
        return None
    tone = _choose_inner(
        ctx.chord(bar),
        lead_pitch,
        bass,
        ctx.mid_low,
        ctx.mid_high,
        ctx.semitones,
        ctx.ensemble == "villa",
    )
    if tone is None or not bass < tone < lead_pitch:
        return None
    if not _playable([bass + ctx.semitones, tone + ctx.semitones, lead_pitch + ctx.semitones]):
        return None
    return tone


def _rewrite_support(
    ctx: _Ctx,
    passage: ScalePassage,
    slots: list[_Slot],
    pitches: list[int],
    support: list[NoteEvent],
    low: list[NoteEvent],
) -> list[NoteEvent]:
    support = _drop_region(support, passage.start, passage.target, ctx.epb)
    leads = _leads_at(slots, pitches)
    sixteenth = {slot.eighth for slot in slots if slot.dur16 == 1 and slot.eighth < passage.target}
    plain = {slot.eighth for slot in slots if slot.dur16 == 2 and slot.eighth < passage.target}
    wanted: list[int] = []
    if passage.start in sixteenth and _is_strong(ctx, passage.start):
        wanted.append(passage.start)
    wanted.extend(eighth for eighth in sorted(plain) if _is_strong(ctx, eighth))
    for eighth in wanted:
        group = leads.get(eighth) or [_melody_pitch(ctx, eighth)]
        lead_pitch = min(group)
        bass = _sounding_midi(low, eighth, ctx.epb)
        if bass is None:
            continue
        tone = _support_tone(ctx, eighth // ctx.epb, lead_pitch, bass)
        if tone is None:
            continue
        support.extend(_eighth_event(eighth, 1, tone, ctx.epb, 2, _INNER))
    return support


def realize_scale_passage(
    ctx: _Ctx,
    passage: ScalePassage,
    patterns: list[str],
    lead: list[NoteEvent],
    support: list[NoteEvent],
    low: list[NoteEvent],
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]] | None:
    """Waypoint realization. Returns none when the line cannot stay stepwise and playable."""
    built = _line(ctx, patterns, passage)
    if built is None:
        return None
    slots, pitches = built
    previous = _velocity_before(lead, passage.start, ctx.epb)
    velocities = _curve(passage, len(slots), previous)
    if len(velocities) != len(slots):
        return None
    lead = _install_lead(lead, slots, pitches, velocities, ctx.epb)
    low = _rewrite_bass(ctx, patterns, passage, slots, pitches, lead, low)
    support = _rewrite_support(ctx, passage, slots, pitches, support, low)
    return lead, support, low


def apply_scale_passages(
    ctx: _Ctx,
    patterns: list[str],
    lead: list[NoteEvent],
    support: list[NoteEvent],
    low: list[NoteEvent],
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], ScalePlan]:
    """Realize passages, then perpetual motion, then tier-1 windows that still fit."""
    state = {"lead": list(lead), "support": list(support), "low": list(low)}

    def _accept(passage: ScalePassage) -> bool:
        realized = realize_scale_passage(ctx, passage, patterns, state["lead"], state["support"], state["low"])
        if realized is None:
            return False
        state["lead"], state["support"], state["low"] = realized
        return True

    plan = select_scale_plan(ctx, patterns, accept_passage=_accept, accept_tier1=_accept)
    if plan.perpetual_bars:
        state["lead"], state["support"], state["low"] = _apply_perpetual(
            ctx, state["lead"], state["support"], state["low"], list(plan.perpetual_bars)
        )
    return state["lead"], state["support"], state["low"], plan


def clear_scale_slurs(events: list[NoteEvent], eighths: set[int], epb: int) -> list[NoteEvent]:
    """Keep a scale attack plucked. A hammer would rewrite the arrival."""
    if not eighths:
        return events
    cleaned: list[NoteEvent] = []
    for event in events:
        eighth = event.bar * epb + int(math.floor(event.beat * 2 + 1e-9))
        if eighth in eighths and (event.slur_start or event.slur_stop):
            cleaned.append(replace_slur(event))
        else:
            cleaned.append(event)
    return cleaned


def replace_slur(event: NoteEvent) -> NoteEvent:
    from dataclasses import replace

    return replace(event, slur_start=False, slur_stop=False)
