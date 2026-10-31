"""Scale-passage allocation and realization for the classical guitar.

The price detector and the octave lock live elsewhere. This module reads
`ctx.impulses` and spends the 30% body budget: passages, then perpetual
motion, then group-2 tier-1 descents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

try:
    from app.sonify.guitar_scales import SCALE_SIXTEENTH_MIN_BPM
except ImportError:  # the detector module lands separately
    SCALE_SIXTEENTH_MIN_BPM = 88

from app.sonify.guitar_bach import (
    _allemande_bass_plan,
    _allemande_passes,
    _bach_keep_bass_below,
    _chaconne_bass_slots,
    _fuga_bass_under_lead,
    _gigue_plan,
    _quarter_ok,
    bach_group2_intrinsic_eighths,
    bach_group2_window,
    bach_scale_classes,
    bach_scale_step,
)
from app.sonify.guitar_barrios import (
    _apply_perpetual,
    _catedral_preludio,
    _perpetual_bars,
    _preludio_anchor,
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
    _classes,
    _on_sixteenth_grid,
    _playable,
    _sounding_midi,
    _spell16,
    _splice,
    _start16,
)
from app.sonify.guitar_sor import classic_scale_step
from app.sonify.guitar_villa import villa_open_candidates, villa_scale_step
from app.sonify.model import NoteEvent

_GROUP1 = frozenset({"tremolo"})
_HOST = frozenset({"etude1", "etude11", "thumb_cantabile", "preludio"})
_BACH_GROUP2 = frozenset({"bach_chaconne", "bach_gigue", "bach_sarabande", "bach_courante"})


def _phrase_covering(ctx: _Ctx, bar: int):
    eighth = bar * ctx.epb
    for phrase in ctx.phrases:
        if phrase.start <= eighth < phrase.end:
            return phrase
    return None


def _courante_closes(ctx: _Ctx, bar: int) -> bool:
    """The cadence bar of a phrase that closes. 3/4 and 6/8 share ``epb``."""
    phrase = _phrase_covering(ctx, bar)
    if phrase is None or not phrase.closes:
        return False
    return bar == (phrase.end - 1) // ctx.epb


def _courante_pair(ctx: _Ctx) -> tuple[int, int] | None:
    """Inclusive tirata eighths: the rhythm half through its penultimate price.

    The last eighth of the bar steps toward the next bar, so it stays outside.
    """
    kind = getattr(ctx, "kind", None)
    if kind in {"3/4", "6/8"}:
        return 3, 4
    if kind == "4/4":
        return 4, 6
    return None


def _courante_window(ctx: _Ctx, bar: int) -> tuple[int, int] | None:
    """Inclusive tirata eighths. A closing bar sings those prices as eighths."""
    if _courante_closes(ctx, bar):
        return None
    pair = _courante_pair(ctx)
    if pair is None:
        return None
    lo, hi = pair
    if hi >= ctx.epb:
        return None
    origin = bar * ctx.epb
    return origin + lo, origin + hi


def _courante_intrinsic_eighths(ctx: _Ctx, bar: int) -> set[int]:
    """Tirata eighths this bar already draws. Empty when the cadence sings eighths."""
    window = _courante_window(ctx, bar)
    if window is None:
        return set()
    lo, hi = window
    return set(range(lo, hi + 1))


def _courante_bass_spans(ctx: _Ctx, bar: int) -> tuple[tuple[int, int], ...]:
    """One bass at eighth 0 rings for the whole bar. No mid-bar attack."""
    del bar
    if ctx.epb <= 0:
        return ()
    return ((0, ctx.epb),)


def _courante_bass_offsets(ctx: _Ctx, bar: int) -> tuple[int, ...]:
    """Body bass attacks. Not the group-3 strong-beat roots."""
    return tuple(offset for offset, _duration in _courante_bass_spans(ctx, bar))


def _written_bass_spans(ctx: _Ctx, pattern: str, bar: int) -> tuple[tuple[int, int], ...] | None:
    """`(offset, eighths)` when the dance stops before the next bass attack.

    Prelude keeps the half-bar pedal, so it stays on the next-onset rule.
    """
    if pattern == "bach_courante":
        return _courante_bass_spans(ctx, bar)
    if pattern == "bach_allemande":
        origin = bar * ctx.epb
        passes = _allemande_passes(ctx, bar, origin, ctx.epb)
        return tuple(
            (offset, duration) for offset, _degree, duration in _allemande_bass_plan(ctx, passes)
        )
    return None


def _half_bar_bass_offsets(ctx: _Ctx, pattern: str) -> tuple[int, ...]:
    """Prelude pedal halves, or the allemande root and second bass, not ``ctx.strong``."""
    epb = ctx.epb
    kind = getattr(ctx, "kind", None)
    if pattern == "bach_allemande" or pattern == "allemande":
        second = 3 if kind == "6/8" else 4
    else:
        second = 3 if kind in {"3/4", "6/8"} else max(1, epb // 2)
    return tuple(offset for offset in (0, second) if offset < epb)


def _courante_bass_accent(ctx: _Ctx, eighth: int) -> bool:
    return eighth % ctx.epb == 0


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
        if pattern == "bach_courante":
            found |= _courante_intrinsic_eighths(ctx, bar)
        elif pattern in _BACH_GROUP2:
            found |= bach_group2_intrinsic_eighths(ctx, bar, pattern)
        elif pattern == "sarabande":
            found |= brouwer_group2_intrinsic_eighths(ctx, bar)
    return found


def _clip_window(ctx: _Ctx, bar: int, pattern: str) -> tuple[int, int] | None:
    if pattern == "bach_courante":
        return _courante_window(ctx, bar)
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


def _occupied_bars(start: int, target: int, epb: int) -> range:
    """Bars with an eighth in `[start, target)`.

    A target on a barline is only the arrival eighth, so the next bar is not
    occupied. `_touched_bars` (`range(start // epb, target // epb + 1)`) would
    swallow that bar while snapping host stretches to whole bars.
    """
    if start >= target or epb <= 0:
        return range(0)
    return range(start // epb, (target - 1) // epb + 1)


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


def _grids_yield(impulse: _Impulse, epb: int) -> bool:
    """Whether tremolo and the four hosts may give bars to this impulse.

    The two numbers are `_major_bridge`, measured on the original impulse
    before any clip. Failing them peels those grids off the ends and keeps a
    group-3 remainder. A failed grid strictly inside the span drops the passage.
    """
    return _major_bridge(impulse, epb)


def _framed_host(ctx: _Ctx, pattern: str) -> bool:
    if pattern not in _HOST:
        return False
    return pattern != "preludio" or _catedral_preludio(ctx)


def _edge_blocked(ctx: _Ctx, patterns: list[str], bar: int, *, yield_grids: bool) -> bool:
    """Pedal is always cut. Tremolo and hosts are cut only when the gate failed."""
    if bar < 0 or bar >= ctx.bars:
        return True
    if ctx.kind_at.get(bar, "phrase") in _PEDAL:
        return True
    if yield_grids:
        return False
    pattern = _bar_pattern(ctx, bar, patterns)
    if pattern in _GROUP1:
        return True
    return _framed_host(ctx, pattern)


def _host_pattern(ctx: _Ctx, patterns: list[str], bar: int) -> str | None:
    """A grid that yields whole bars to a real scale line. Unframed preludio does not."""
    if bar < 0 or bar >= ctx.bars:
        return None
    if ctx.kind_at.get(bar, "phrase") in _PEDAL:
        return None
    pattern = _bar_pattern(ctx, bar, patterns)
    if pattern not in _HOST:
        return None
    if pattern == "preludio" and not _catedral_preludio(ctx):
        return None
    return pattern


def _yielding_pattern(ctx: _Ctx, patterns: list[str], bar: int, *, yield_grids: bool) -> str | None:
    """A bar that may leave its grid once the original impulse cleared the gate.

    Tremolo joins the four hosts only on that path. Unframed preludio never
    yields. The span is not grown past the impulse.
    """
    if not yield_grids or bar < 0 or bar >= ctx.bars:
        return None
    if ctx.kind_at.get(bar, "phrase") in _PEDAL:
        return None
    pattern = _bar_pattern(ctx, bar, patterns)
    if pattern in _GROUP1 or _framed_host(ctx, pattern):
        return pattern
    return None


def _region_origin(
    ctx: _Ctx,
    patterns: list[str],
    bar: int,
    pattern: str,
    *,
    yield_grids: bool,
) -> int:
    origin = bar
    while origin > 0 and _yielding_pattern(ctx, patterns, origin - 1, yield_grids=yield_grids) == pattern:
        origin -= 1
    return origin


def _clip_blocked_ends(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    *,
    yield_grids: bool,
) -> tuple[int, int]:
    """Step 1. Peel pedal, and peel tremolo or hosts when the gate failed."""
    epb = ctx.epb
    while start < target:
        moved = False
        if _edge_blocked(ctx, patterns, start // epb, yield_grids=yield_grids):
            start = (start // epb + 1) * epb
            moved = True
        if start < target and _edge_blocked(ctx, patterns, (target - 1) // epb, yield_grids=yield_grids):
            target = ((target - 1) // epb) * epb
            moved = True
        if not moved:
            break
    return start, target


def _snap_host_edges(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    *,
    yield_grids: bool,
) -> tuple[int, int]:
    """Step 3. Drop a yielded fragment shorter than one bar at either end.

    Snapping inward never pulls the next bar in, and it never opens a hole in
    a sixteenth cycle, a sextuplet group, or a canto frame.
    """
    epb = ctx.epb
    if start >= target:
        return start, target
    if start % epb != 0 and _yielding_pattern(ctx, patterns, start // epb, yield_grids=yield_grids):
        start = (start // epb + 1) * epb
    if start < target and target % epb != 0 and _yielding_pattern(
        ctx, patterns, (target - 1) // epb, yield_grids=yield_grids
    ):
        target = ((target - 1) // epb) * epb
    return start, target


def _opening_inside(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    *,
    yield_grids: bool,
) -> int | None:
    for bar in _occupied_bars(start, target, ctx.epb):
        if bar < 0 or bar >= ctx.bars:
            continue
        pattern = _yielding_pattern(ctx, patterns, bar, yield_grids=yield_grids)
        if pattern is None:
            continue
        if _region_origin(ctx, patterns, bar, pattern, yield_grids=yield_grids) == bar:
            return bar
    return None


def _exclude_opening(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    *,
    yield_grids: bool,
) -> tuple[int, int] | None:
    """Step 4. The first bar of a host region stays outside this passage.

    An opening in the middle keeps the front when it has two eighths, otherwise
    the back. An opening on an edge only shrinks that edge. Group 2 is not
    handled here.
    """
    bar = _opening_inside(ctx, patterns, start, target, yield_grids=yield_grids)
    if bar is None:
        return start, target
    epb = ctx.epb
    bar_lo = bar * epb
    bar_hi = bar_lo + epb
    if start < bar_lo and bar_hi < target:
        front = bar_lo - start
        back = target - bar_hi
        if front >= 2:
            return start, bar_lo
        if back >= 2:
            return bar_hi, target
        return None
    if start < bar_lo:
        return start, bar_lo
    return bar_hi, target


def _blocked_inside(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    *,
    yield_grids: bool,
) -> bool:
    """Step 5. A blocked bar strictly between the end bars drops the passage.

    A tremolo bar yielded after its region opening is not blocked, so it does
    not cancel the passage. Pedal still does.
    """
    bars = [bar for bar in _occupied_bars(start, target, ctx.epb) if 0 <= bar < ctx.bars]
    if len(bars) < 3:
        return False
    return any(_edge_blocked(ctx, patterns, bar, yield_grids=yield_grids) for bar in bars[1:-1])


def _clip_span(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    *,
    yield_grids: bool,
) -> tuple[int, int] | None:
    """Clip `[start, target)` before a passage is built, gapped, or budgeted."""
    start, target = _clip_blocked_ends(ctx, patterns, start, target, yield_grids=yield_grids)
    if target <= start:
        return None
    start, target = _snap_host_edges(ctx, patterns, start, target, yield_grids=yield_grids)
    if target <= start:
        return None
    seen: set[tuple[int, int]] = set()
    while True:
        state = (start, target)
        if state in seen:
            return None
        seen.add(state)
        opened = _exclude_opening(ctx, patterns, start, target, yield_grids=yield_grids)
        if opened is None:
            return None
        start, target = opened
        if target <= start:
            return None
        start, target = _clip_blocked_ends(ctx, patterns, start, target, yield_grids=yield_grids)
        if target <= start:
            return None
        if _blocked_inside(ctx, patterns, start, target, yield_grids=yield_grids):
            return None
        if (start, target) == state:
            break
    if target - start < 2:
        return None
    return start, target


def _clip_retreats(
    spans: tuple[tuple[int, int], ...],
    start: int,
    target: int,
) -> tuple[tuple[int, int], ...]:
    clipped: list[tuple[int, int]] = []
    for lo, hi in spans:
        left = max(int(lo), start)
        right = min(int(hi), target)
        if right > left:
            clipped.append((left, right))
    return tuple(clipped)


def _prepare_impulse(ctx: _Ctx, patterns: list[str], impulse: _Impulse) -> _Impulse | None:
    """Clip first. A group-2 opening still rejects the whole remaining span.

    A major bridge is judged on the original impulse, before this clip.
    """
    clipped = _clip_span(
        ctx,
        patterns,
        impulse.start,
        impulse.target,
        yield_grids=_grids_yield(impulse, ctx.epb),
    )
    if clipped is None:
        return None
    start, target = clipped
    if _overlaps_group2(ctx, patterns, start, target):
        if not _major_bridge(impulse, ctx.epb):
            return None
        if _covers_group2_opening(ctx, patterns, start, target):
            return None
    return _Impulse(
        start=start,
        target=target,
        direction=impulse.direction,
        net_span=impulse.net_span,
        adjusted_efficiency=impulse.adjusted_efficiency,
        score=impulse.score,
        retreat_spans=_clip_retreats(impulse.retreat_spans, start, target),
        sub_bar=(target - start) < ctx.epb,
    )


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
            # Group-2 windows are inclusive, and the clip stops before `hi`
            # so the last eighth stays off the next passage. Courante's pair
            # already ends on the arrival eighth. The step into the next bar
            # is the eighth after `hi`, so the clip runs through `hi`.
            exclusive = hi + 1 if pattern == "bach_courante" else hi
            start = max(impulse.start, lo)
            target = min(impulse.target, exclusive)
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
        prepared = _prepare_impulse(ctx, patterns, impulse)
        if prepared is None:
            continue
        passage = _as_passage(prepared, intrinsic, "passage")
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


_VILLA_COLOR = frozenset({2, 5, 10})
_BROUWER_PCS = frozenset({0, 1, 2, 3, 5, 7, 8, 9, 10})


def _compass(ctx: _Ctx, passage: ScalePassage | None) -> tuple[int, int]:
    """Written `[floor, ceiling]` for section 2.3.

    A short passage may leave sounding 59..81 by one neighbor step (57..83).
    A passage of at least one bar opens to 52..83, or 40..83 for Villa and Brouwer.
    """
    semi = ctx.semitones
    top = min(83 - semi, ctx.ceiling)
    standard_floor = 59 - semi
    long = passage is not None and passage.passage_eighths >= ctx.epb
    if long and ctx.ensemble in {"villa", "brouwer"}:
        floor = 40 - semi
    elif long:
        floor = 52 - semi
    else:
        floor = 57 - semi
    if ctx.treble_floor > standard_floor:
        floor = max(floor, ctx.treble_floor)
    if floor > top:
        floor = top
    return floor, top


def _resolve_limits(ctx: _Ctx, low: int | None, high: int | None) -> tuple[int, int]:
    floor, top = _compass(ctx, None)
    return floor if low is None else low, top if high is None else high


def _pitch_classes(ctx: _Ctx, impulse_direction: str, approaching: bool) -> frozenset[int]:
    if ctx.ensemble == "bach":
        return bach_scale_classes(ctx, impulse_direction, approaching)
    if ctx.ensemble == "brouwer":
        return _BROUWER_PCS
    if ctx.ensemble == "torroba":
        return frozenset(_classes(ctx.mode))
    if ctx.ensemble == "villa":
        return frozenset(_classes(ctx.mode)) | _VILLA_COLOR
    return frozenset(_classes(ctx.mode))


def _composer_step(
    ctx: _Ctx,
    pitch: int,
    toward: int,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
) -> int:
    if toward == 0:
        return pitch
    if ctx.ensemble == "bach":
        return bach_scale_step(
            ctx,
            pitch,
            toward,
            impulse_direction=impulse_direction,
            approaching_tonic=approaching,
            low=low,
            high=high,
        )
    if ctx.ensemble == "villa":
        return villa_scale_step(ctx, pitch, toward, low=low, high=high)
    if ctx.ensemble == "barrios":
        return barrios_scale_step(ctx, pitch, toward, low=low, high=high)
    if ctx.ensemble == "brouwer":
        return brouwer_scale_step(ctx, pitch, toward, low=low, high=high)
    if ctx.ensemble == "torroba":
        from app.sonify.guitar_torroba import torroba_scale_step

        return torroba_scale_step(ctx, pitch, toward, low=low, high=high)
    return classic_scale_step(ctx, pitch, toward, low=low, high=high)


def _scale_need(
    ctx: _Ctx,
    cursor: int,
    end: int,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
) -> int:
    """In-set steps from `cursor` to `end`.

    Each step is the composer's next scale degree, at most 2 semitones, without
    passing `end`. E4 to C5 in C major is 8 semitones (`room_steps` 4) and 5
    degrees, because E–F and B–C are semitones and cannot be skipped.
    """
    if cursor == end:
        return 0
    path = _trace_scale(ctx, cursor, end, impulse_direction, approaching, low, high, color=False)
    if path is None:
        return math.ceil(abs(end - cursor) / 2)
    return max(0, len(path) - 1)


def _villa_efficient_step(ctx: _Ctx, current: int, toward: int, end: int, low: int, high: int) -> int | None:
    """Largest Villa step that stays in the set and does not pass `end`.

    The nearest color tone can sit between two degrees (A–Bb–B). Skipping it
    is what `scale_need` counts. The color walk takes it when the bar still fits.
    """
    classes = _pitch_classes(ctx, "up", False)
    for size in (2, 1):
        nxt = current + toward * size
        if not low <= nxt <= high or (nxt - current) * toward <= 0:
            continue
        if (end - nxt) * toward < 0:
            continue
        if nxt != end and nxt % 12 not in classes:
            continue
        return nxt
    return None


def _villa_color_step(ctx: _Ctx, current: int, toward: int, end: int, low: int, high: int) -> int | None:
    """Nearest color tone `{2, 5, 10}` within 2 semitones that does not pass `end`."""
    classes = _pitch_classes(ctx, "up", False)
    for size in (1, 2):
        nxt = current + toward * size
        if not low <= nxt <= high:
            continue
        if (end - nxt) * toward < 0:
            continue
        if nxt != end and nxt % 12 not in classes:
            continue
        if nxt % 12 in _VILLA_COLOR:
            return nxt
    return None


def _trace_ab(ctx: _Ctx, notes: list[int], end: int, low: int, high: int, chord) -> list[int]:
    """Ab immediately before `end` when that destination is G. Other landings stay diatonic.

    The approach replaces the pitch already in that slot. A path that is only
    the destination has no slot to replace, and the length never grows.
    """
    if ctx.ensemble != "torroba" or not notes or notes[-1] != end or len(notes) < 2:
        return notes
    from app.sonify.guitar_torroba import torroba_ab_approach

    ab = torroba_ab_approach(ctx, end, chord)
    if ab is None or not low <= ab <= high:
        return notes
    if notes[-2] % 12 == 8 and abs(notes[-2] - end) == 1:
        return notes
    updated = list(notes)
    updated[-2] = ab
    return updated


def _trace_scale(
    ctx: _Ctx,
    start: int,
    end: int,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
    *,
    color: bool = False,
    chord=None,
) -> list[int] | None:
    """Walk in-set degrees from `start` to `end`. Villa may prefer a color tone."""
    if start < low or start > high or end < low or end > high:
        return None
    notes = [start]
    current = start
    for _ in range(64):
        if current == end:
            return _trace_ab(ctx, notes, end, low, high, chord)
        toward = 1 if end > current else -1
        nxt = _composer_step(ctx, current, toward, impulse_direction, approaching, low, high)
        if ctx.ensemble == "villa":
            if color:
                alt = _villa_color_step(ctx, current, toward, end, low, high)
            else:
                alt = _villa_efficient_step(ctx, current, toward, end, low, high)
            if alt is not None:
                nxt = alt
        moved = nxt != current and (nxt - current) * toward > 0 and abs(nxt - current) <= 2
        if not moved or (end - nxt) * toward < 0 or not low <= nxt <= high:
            if 0 < (end - current) * toward <= 2 and low <= end <= high:
                notes.append(end)
                return _trace_ab(ctx, notes, end, low, high, chord)
            return None
        notes.append(nxt)
        current = nxt
    return None if current != end else _trace_ab(ctx, notes, end, low, high, chord)


def _fast_line(
    ctx: _Ctx,
    start: int,
    end: int,
    count: int,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
) -> list[int] | None:
    """Arrive in `count` notes when the scale itself needs more degrees than remain.

    An out-of-set ±1 or ±2 is used only when no in-set step can still reach `end`.
    """
    steps = count - 1
    if steps < 1 or abs(end - start) > 2 * steps:
        return None
    if start < low or start > high or end < low or end > high:
        return None
    classes = _pitch_classes(ctx, impulse_direction, approaching)
    notes = [start]
    current = start
    for index in range(1, count - 1):
        steps_after = count - 1 - index
        toward = 1 if end > current else -1
        if toward == 0:
            return None
        need = max(1, abs(end - current) - 2 * steps_after)
        if need > 2:
            return None
        chosen = None
        for size in (need, 2, 1):
            if size < need or size > 2:
                continue
            nxt = current + toward * size
            # The anchor is the last note. An earlier arrival would repeat it
            # through the notes that are still left.
            if steps_after > 0 and nxt == end:
                continue
            if (end - nxt) * toward < 0:
                continue
            if not low <= nxt <= high or abs(nxt - current) > 2 or (nxt - current) * toward <= 0:
                continue
            if nxt != end and nxt % 12 not in classes:
                continue
            if abs(end - nxt) > 2 * steps_after:
                continue
            chosen = nxt
            break
        if chosen is None:
            if current != end and abs(end - current) <= 2 * steps_after:
                notes.append(current)
                continue
            size = min(2, need)
            nxt = current + toward * size
            if steps_after > 0 and nxt == end:
                return None
            if (end - nxt) * toward < 0 or abs(nxt - current) > 2 or not low <= nxt <= high:
                return None
            if abs(end - nxt) > 2 * steps_after:
                return None
            chosen = nxt
        notes.append(chosen)
        current = chosen
    if abs(end - notes[-1]) > 2:
        return None
    notes.append(end)
    if any(abs(right - left) > 2 for left, right in zip(notes, notes[1:])):
        return None
    return notes


def _insert_repeat(notes: list[int]) -> list[int]:
    """Hold the closing anchor. A cadence already on the end stays the last figure.

    One neighbor costs two steps. Further spare steps sit on ``end``, just
    before that cadence, instead of doubling the first pitch.
    """
    if not notes:
        return notes
    end = notes[-1]
    if (
        len(notes) >= 3
        and notes[-3] == end
        and notes[-2] != end
        and abs(notes[-2] - end) <= 2
    ):
        return notes[:-3] + [end, *notes[-3:]]
    return notes[:-1] + [end, notes[-1]]


def _start_neighbor(
    notes: list[int],
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
) -> list[int] | None:
    start, end = notes[0], notes[-1]
    order = (-1, 1) if end < start else (1, -1)
    for toward in order:
        if ctx.ensemble == "villa":
            color = _villa_color_step(ctx, start, toward, start + toward * 2, low, high)
            if (
                color is not None
                and (color - start) * toward > 0
                and abs(color - start) <= 2
                and low <= color <= high
            ):
                return [start, color, start, *notes[1:]]
        nxt = _composer_step(ctx, start, toward, impulse_direction, approaching, low, high)
        if nxt == start or (nxt - start) * toward <= 0:
            continue
        if abs(nxt - start) > 2 or not low <= nxt <= high:
            continue
        return [start, nxt, start, *notes[1:]]
    return None


def _upper_neighbor(
    ctx: _Ctx,
    end: int,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
) -> int | None:
    if ctx.ensemble == "villa":
        color = _villa_color_step(ctx, end, 1, end + 2, low, high)
        if color is not None and color != end and abs(color - end) <= 2:
            return color
    nxt = _composer_step(ctx, end, 1, impulse_direction, approaching, low, high)
    if nxt == end or abs(nxt - end) > 2 or not low <= nxt <= high:
        return None
    if ctx.ensemble in {"classic", "sor"} and nxt == end - 1:
        return None
    return nxt


def _spare_turn(
    notes: list[int],
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
    chord_pcs: frozenset[int] | None,
) -> list[int] | None:
    """Spend two spare steps on the composer's neighbor, then land on `end`."""
    start, end = notes[0], notes[-1]
    ascending = end > start
    if ctx.ensemble == "bach" and ascending:
        lead = end - 1
        # prev is the arrival itself: the descent into the leading tone is a semitone.
        if low <= lead <= high and abs(end - lead) <= 2 and (end - lead) != 3:
            return notes + [lead, end]
        return _start_neighbor(notes, ctx, impulse_direction, approaching, low, high)
    if ctx.ensemble == "bach":
        upper = bach_scale_step(
            ctx,
            end,
            1,
            impulse_direction=impulse_direction,
            approaching_tonic=approaching,
            low=low,
            high=high,
        )
        if upper != end and abs(upper - end) <= 2 and low <= upper <= high:
            return notes + [upper, end]
        return _start_neighbor(notes, ctx, impulse_direction, approaching, low, high)
    if ctx.ensemble == "brouwer":
        classes = _BROUWER_PCS
        options: list[int] = []
        for toward in (1, -1):
            for size in (2, 1):
                nxt = end + toward * size
                if low <= nxt <= high and nxt % 12 in classes:
                    options.append(nxt)
        if not options:
            return _start_neighbor(notes, ctx, impulse_direction, approaching, low, high)
        avoid = chord_pcs or frozenset()

        def rank(note: int) -> tuple[int, int, int]:
            outside = 0 if avoid and note % 12 not in avoid else 1
            return (0 if abs(note - end) == 2 else 1, outside, 0 if note > end else 1)

        return notes + [min(options, key=rank), end]
    if ascending:
        upper = _upper_neighbor(ctx, end, impulse_direction, approaching, low, high)
        if upper is not None:
            return notes + [upper, end]
    return _start_neighbor(notes, ctx, impulse_direction, approaching, low, high)


def _fit_bach_leading(notes: list[int], extra: int, low: int, high: int) -> tuple[list[int], int]:
    """Put the leading tone on the last weak note when the previous pitch allows it."""
    if extra < 0 or len(notes) < 2 or notes[-1] <= notes[0]:
        return notes, extra
    end = notes[-1]
    lead = end - 1
    if not low <= lead <= high or notes[-2] == lead:
        return notes, extra
    prev = notes[-2]
    if extra >= 1 and abs(prev - lead) <= 2 and (prev - lead) != 3:
        return notes[:-1] + [lead, end], extra - 1
    if extra == 0 and len(notes) >= 3:
        earlier = notes[-3]
        if abs(earlier - lead) <= 2 and (earlier - lead) != 3:
            return notes[:-2] + [lead, end], extra
    return notes, extra


def _insert_legal_semitone(
    notes: list[int],
    classes: frozenset[int],
    low: int,
    high: int,
    ensemble: str,
) -> list[int] | None:
    """One leftover step: a semitone between the endpoints, within 2 of each."""
    start, end = notes[0], notes[-1]
    if len(notes) < 2 or abs(end - start) < 2 or abs(end - start) > 4:
        return None
    lo, hi = min(start, end), max(start, end)
    prev = notes[-2]
    chosen = None
    for pitch in range(lo + 1, hi):
        if abs(pitch - start) > 2 or abs(pitch - end) > 2 or not low <= pitch <= high:
            continue
        if abs(pitch - prev) > 2 or min(abs(pitch - start), abs(pitch - end)) != 1:
            continue
        in_set = pitch % 12 in classes
        if ensemble == "brouwer" and not in_set:
            continue
        if ensemble == "bach" and not in_set and pitch != (end - 1 if end > start else end + 1):
            continue
        if ensemble in {"classic", "sor"} and not in_set:
            continue
        chosen = pitch
        if ensemble == "bach" and end > start and pitch == end - 1:
            break
    if chosen is None:
        return None
    return notes[:-1] + [chosen, end]


def _connector_ok(note: int, chromatic: int, classes: frozenset[int], low: int, high: int) -> bool:
    return (
        low <= note <= high
        and note != chromatic
        and note % 12 in classes
        and abs(note - chromatic) in {1, 2}
    )


def _barrios_tail(
    notes: list[int],
    extra: int,
    classes: frozenset[int],
    low: int,
    high: int,
) -> tuple[list[int], int]:
    """Aim `anchor - 2` at a diatonic degree 1 or 2 semitones from the chromatic approach."""
    if len(notes) < 2 or extra < 0:
        return notes, 0
    end = notes[-1]
    ascending = end >= notes[0]
    chromatic = end - 1 if ascending else end + 1
    if not low <= chromatic <= high:
        return notes, 0
    if extra >= 2 and _connector_ok(end, chromatic, classes, low, high):
        return notes + [chromatic, end], 2
    if len(notes) < 3:
        # One leftover step can still be the chromatic approach when it sits
        # between the endpoints and within 2 semitones of each.
        if (
            extra >= 1
            and min(notes[-2], end) < chromatic < max(notes[-2], end)
            and abs(chromatic - notes[-2]) <= 2
            and abs(chromatic - end) == 1
        ):
            return notes[:-1] + [chromatic, end], 1
        return notes, 0
    anchor2 = len(notes) - 3

    def place(connector: int) -> list[int] | None:
        updated = list(notes)
        updated[anchor2] = connector
        updated[-2] = chromatic
        if any(abs(right - left) > 2 for left, right in zip(updated, updated[1:])):
            return None
        return updated

    if _connector_ok(notes[anchor2], chromatic, classes, low, high):
        placed = place(notes[anchor2])
        if placed is not None:
            return placed, 0
    if anchor2 == 0:
        return notes, 0
    prev = notes[anchor2 - 1]
    side = -1 if ascending else 1
    found: list[tuple[tuple[int, int], int]] = []
    for dist in (1, 2):
        for sign in (side, -side):
            note = chromatic + sign * dist
            if _connector_ok(note, chromatic, classes, low, high) and abs(note - prev) <= 2:
                found.append(((0 if sign == side else 1, dist), note))
    for _rank, note in sorted(found):
        placed = place(note)
        if placed is not None:
            return placed, 0
    if extra >= 1:
        for _rank, note in sorted(found):
            updated = notes[:anchor2] + [notes[anchor2], note, chromatic, end]
            if all(abs(right - left) <= 2 for left, right in zip(updated, updated[1:])):
                return updated, 1
    return notes, 0


def _embellish(
    path: list[int],
    count: int,
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
    chord_pcs: frozenset[int] | None,
) -> list[int] | None:
    if len(path) > count:
        return None
    notes = list(path)
    classes = _pitch_classes(ctx, impulse_direction, approaching)
    if ctx.ensemble == "barrios" and notes[0] != notes[-1]:
        updated, _spent = _barrios_tail(notes, count - len(notes), classes, low, high)
        if len(updated) <= count:
            notes = updated
        while len(notes) + 2 <= count:
            turned = _start_neighbor(notes, ctx, impulse_direction, approaching, low, high)
            if turned is None or len(turned) > count:
                break
            notes = turned
    elif len(notes) + 2 <= count and notes[0] != notes[-1]:
        turned = _spare_turn(notes, ctx, impulse_direction, approaching, low, high, chord_pcs)
        if turned is not None and len(turned) <= count:
            notes = turned
    extra = count - len(notes)
    if ctx.ensemble == "bach" and notes[-1] > notes[0] and (len(notes) < 2 or notes[-2] != notes[-1] - 1):
        fitted, _extra = _fit_bach_leading(notes, extra, low, high)
        if len(fitted) <= count:
            notes = fitted
            extra = count - len(notes)
    if (
        extra == 1
        and ctx.ensemble in {"bach", "brouwer"}
        and len(notes) + 1 <= count
        and (ctx.ensemble != "bach" or notes[-2] != notes[-1] - 1)
    ):
        inserted = _insert_legal_semitone(notes, classes, low, high, ctx.ensemble)
        if inserted is not None and len(inserted) <= count:
            notes = inserted
    while len(notes) < count:
        grown = _insert_repeat(notes)
        if len(grown) <= len(notes):
            return None
        notes = grown
    if len(notes) != count or notes[0] != path[0] or notes[-1] != path[-1]:
        return None
    if ctx.ensemble == "torroba" and len(notes) >= 2:
        from app.sonify.guitar_torroba import torroba_ab_approach

        ab = torroba_ab_approach(ctx, notes[-1], chord_pcs)
        if ab is not None and low <= ab <= high:
            notes[-2] = ab
    if any(note < low or note > high for note in notes):
        return None
    if any(abs(right - left) > 2 for left, right in zip(notes, notes[1:])):
        return None
    return notes


def _step_pitch(
    ctx: _Ctx,
    pitch: int,
    toward: int,
    impulse_direction: str,
    approaching: bool,
    *,
    low: int | None = None,
    high: int | None = None,
    end: int | None = None,
    steps_after: int | None = None,
) -> int:
    """One step toward `toward`. Leave the set only when no in-set step can still arrive."""
    if toward == 0:
        return pitch
    low, high = _resolve_limits(ctx, low, high)
    classes = _pitch_classes(ctx, impulse_direction, approaching)
    nxt = _composer_step(ctx, pitch, toward, impulse_direction, approaching, low, high)

    def legal(note: int, *, in_set: bool) -> bool:
        if note == pitch or (note - pitch) * toward <= 0:
            return False
        if abs(note - pitch) > 2 or not low <= note <= high:
            return False
        if end is not None and steps_after is not None and abs(end - note) > 2 * steps_after:
            return False
        if in_set and note != end and note % 12 not in classes:
            return False
        return True

    if legal(nxt, in_set=True):
        return nxt
    if end is None or steps_after is None:
        forced_size = 1
    else:
        forced_size = min(2, max(1, abs(end - pitch) - 2 * max(steps_after, 0)))
    forced = pitch + toward * forced_size
    if end is not None and (forced - end) * toward > 0:
        forced = end
    if legal(forced, in_set=False):
        return forced
    smaller = pitch + toward
    if legal(smaller, in_set=False):
        return smaller
    return pitch


def _ornamental_neighbor(
    ctx: _Ctx,
    current: int,
    end: int,
    left_after: int,
    impulse_direction: str,
    approaching: bool,
    *,
    low: int | None = None,
    high: int | None = None,
) -> int:
    """One scale step off a flat price, on the weak half of the beat.

    The next anchor is `end` and has to be reachable. If neither direction
    fits, the pitch stays put rather than aborting the passage.
    """
    if left_after < 1:
        return current
    primary = 1 if impulse_direction == "up" else -1
    for toward in (primary, -primary):
        neighbor = _step_pitch(
            ctx,
            current,
            toward,
            impulse_direction,
            approaching,
            low=low,
            high=high,
            end=end,
            steps_after=left_after,
        )
        moved = abs(neighbor - current)
        if (neighbor - current) * toward <= 0 or not 1 <= moved <= 2:
            continue
        if abs(end - neighbor) > 2 * left_after:
            continue
        return neighbor
    return current


def _raw_held(ctx: _Ctx, start_eighth: int, end_eighth: int) -> bool:
    """True when `raw` does not move from `start_eighth` through `end_eighth`."""
    if end_eighth <= start_eighth or start_eighth < 0 or end_eighth >= len(ctx.raw):
        return False
    opening = ctx.raw[start_eighth]
    return all(ctx.raw[eighth] == opening for eighth in range(start_eighth + 1, end_eighth + 1))


def _moving_line(
    start: int,
    end: int,
    count: int,
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
    low: int,
    high: int,
    chord_pcs: frozenset[int] | None,
) -> list[int] | None:
    room_steps = math.ceil(abs(end - start) / 2)
    if count - 1 < room_steps:
        return None
    # Villa may replace the diatonic walk with color tones when that walk still
    # fits. A neighbor turn is added later, and only when two steps remain.
    path = _trace_scale(ctx, start, end, impulse_direction, approaching, low, high, color=False, chord=chord_pcs)
    if path is None:
        return _fast_line(ctx, start, end, count, impulse_direction, approaching, low, high)
    if ctx.ensemble == "villa":
        colored = _trace_scale(ctx, start, end, impulse_direction, approaching, low, high, color=True)
        if colored is not None and len(colored) <= count:
            path = colored
    if len(path) > count:
        return _fast_line(ctx, start, end, count, impulse_direction, approaching, low, high)
    return _embellish(path, count, ctx, impulse_direction, approaching, low, high, chord_pcs)


def _monotone(
    start: int,
    end: int,
    count: int,
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
    ornament: bool = False,
    *,
    low: int | None = None,
    high: int | None = None,
    chord_pcs: frozenset[int] | None = None,
) -> list[int] | None:
    """`count` pitches. The first is `start`, the last is `end`, and only the interior moves.

    `room_steps` is the hard bound (no step wider than 2). Spare in-set steps,
    when `left_after > scale_need`, may pass the anchor by one degree or open a
    neighbor turn. The line still lands on `end`.
    """
    if count <= 0:
        return None
    low, high = _resolve_limits(ctx, low, high)
    if count == 1:
        return [start] if start == end else None
    if abs(end - start) > 2 * (count - 1):
        return None
    if start == end:
        # Two anchors with nothing between them have no weak note to ornament.
        if not ornament or count < 3:
            return [start] * count
        notes = [start]
        neighbor = _ornamental_neighbor(
            ctx,
            start,
            end,
            max(1, count - 2),
            impulse_direction,
            approaching,
            low=low,
            high=high,
        )
        notes.append(neighbor)
        current = neighbor
        toward = 1 if end > current else -1 if end < current else 0
        for index in range(2, count - 1):
            if current == end or toward == 0:
                notes.append(end)
                current = end
                continue
            stepped = _step_pitch(
                ctx,
                current,
                toward,
                impulse_direction,
                approaching,
                low=low,
                high=high,
                end=end,
                steps_after=count - 1 - index,
            )
            if abs(stepped - current) > 2:
                stepped = current
            notes.append(stepped)
            current = stepped
        notes.append(end)
        if any(abs(right - left) > 2 for left, right in zip(notes, notes[1:])):
            return [start] * count
        return notes
    return _moving_line(start, end, count, ctx, impulse_direction, approaching, low, high, chord_pcs)


def _retreat_flag(retreat_at: list[int], index: int) -> bool:
    return bool(retreat_at[index]) if 0 <= index < len(retreat_at) else False


def _directed_step(
    ctx: _Ctx,
    current: int,
    direction: int,
    end: int,
    left_after: int,
    impulse_direction: str,
    approaching: bool,
    *,
    low: int | None = None,
    high: int | None = None,
) -> int | None:
    """One step of `direction` that can still reach `end` in `left_after` steps."""
    low, high = _resolve_limits(ctx, low, high)
    stepped = _step_pitch(
        ctx,
        current,
        direction,
        impulse_direction,
        approaching,
        low=low,
        high=high,
        end=end,
        steps_after=left_after,
    )
    if (stepped - current) * direction <= 0 or abs(stepped - current) > 2:
        return None
    if stepped < low or stepped > high:
        return None
    if abs(end - stepped) > 2 * left_after:
        return None
    return stepped


def _with_retreat(
    start: int,
    end: int,
    count: int,
    retreat_at: list[int],
    ctx: _Ctx,
    impulse_direction: str,
    approaching: bool,
    ornament: bool = False,
    *,
    low: int | None = None,
    high: int | None = None,
    chord_pcs: frozenset[int] | None = None,
) -> list[int] | None:
    """Weak beats follow the impulse, and reverse only on `retreat_at`.

    An up-retreat-up run rises into the retreat, dips there, then rises again.
    The last pitch is the melody anchor even when that last step changes direction.
    `ornament` is a flat price between two equal melody anchors: the offbeat
    may take one neighbor, then the next anchor returns to the melody.
    """
    low, high = _resolve_limits(ctx, low, high)
    interior = any(_retreat_flag(retreat_at, index) for index in range(1, count - 1))
    if not interior:
        return _monotone(
            start,
            end,
            count,
            ctx,
            impulse_direction,
            approaching,
            ornament,
            low=low,
            high=high,
            chord_pcs=chord_pcs,
        )
    toward = 1 if impulse_direction == "up" else -1
    against = -toward
    notes = [start]
    for index in range(1, count - 1):
        direction = against if _retreat_flag(retreat_at, index) else toward
        stepped = _directed_step(
            ctx,
            notes[-1],
            direction,
            end,
            count - 1 - index,
            impulse_direction,
            approaching,
            low=low,
            high=high,
        )
        if stepped is None:
            return None
        notes.append(stepped)
    if abs(end - notes[-1]) > 2:
        return None
    notes.append(end)
    for index in range(1, count - 1):
        direction = against if _retreat_flag(retreat_at, index) else toward
        if (notes[index] - notes[index - 1]) * direction <= 0:
            return None
    if any(abs(right - left) > 2 for left, right in zip(notes, notes[1:])):
        return None
    if any(note < low or note > high for note in notes):
        return None
    return notes


def _assign(ctx: _Ctx, passage: ScalePassage, slots: list[_Slot]) -> list[int] | None:
    if len(slots) < 2:
        return None
    low, high = _compass(ctx, passage)
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
        pcs = ctx.chord(slots[anchors[0]].eighth // ctx.epb).pitch_classes
        line = _with_retreat(
            int(previous),
            end_pitch,
            count,
            flags,
            ctx,
            passage.direction,
            approaching,
            low=low,
            high=high,
            chord_pcs=pcs,
        )
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
        flat = int(pitches[left]) == end_pitch and _raw_held(
            ctx, slots[left].eighth, slots[right].eighth
        )
        pcs = ctx.chord(slots[right].eighth // ctx.epb).pitch_classes
        line = _with_retreat(
            int(pitches[left]),
            end_pitch,
            count,
            flags,
            ctx,
            passage.direction,
            approaching,
            ornament=flat,
            low=low,
            high=high,
            chord_pcs=pcs,
        )
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


def _ascending_into(pitches: list[int], anchor: int, passage: ScalePassage) -> bool:
    target = pitches[anchor]
    for index in range(anchor - 1, -1, -1):
        if pitches[index] != target:
            return target > pitches[index]
    return passage.direction != "down"


def _color_line(ctx: _Ctx, passage: ScalePassage, slots: list[_Slot], pitches: list[int]) -> list[int]:
    colored = list(pitches)
    low, high = _compass(ctx, passage)
    if ctx.ensemble == "barrios":
        classes = frozenset(_classes(ctx.mode))
        anchors = [index for index, slot in enumerate(slots) if slot.anchor]
        for anchor in anchors:
            if anchor <= 0:
                continue
            approach = anchor - 1
            if slots[approach].anchor:
                continue
            chromatic = barrios_chromatic_approach(colored[anchor], _ascending_into(colored, anchor, passage))
            if abs(chromatic - colored[anchor]) != 1 or not low <= chromatic <= high:
                continue
            if approach > 0 and abs(chromatic - colored[approach - 1]) > 2:
                index = approach - 1
                if index == 0 or slots[index].anchor:
                    continue
                prev = colored[index - 1]
                replacement = None
                for dist in (1, 2):
                    for sign in (-1, 1):
                        note = chromatic + sign * dist
                        if (
                            low <= note <= high
                            and note % 12 in classes
                            and abs(note - prev) <= 2
                            and abs(note - chromatic) in {1, 2}
                        ):
                            replacement = note
                            break
                    if replacement is not None:
                        break
                if replacement is None:
                    continue
                colored[index] = replacement
            trial = list(colored)
            trial[approach] = chromatic
            if any(abs(right - left) > 2 for left, right in zip(trial, trial[1:])):
                continue
            colored = trial
    if ctx.ensemble == "villa" and ctx.bpm >= SCALE_SIXTEENTH_MIN_BPM:
        stopped = list(colored)
        for index, slot in enumerate(slots):
            # Eighth-note body slots are invisible to _groups_ok, so an open
            # string tried there would stick. Only a sixteenth slot may take one.
            if slot.dur16 != 1 or slot.anchor or index == 0 or index + 1 >= len(colored):
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
    """Hand position of a four-sixteenth group, on sounding pitches.

    Written pitches have not had `semitones` added, so a position check there
    rejects real open strings in D, Eb, A, and Bb.
    """
    sounding: dict[int, list[int]] = {}
    for slot, pitch in zip(slots, pitches):
        if slot.dur16 != 1:
            continue
        key = (slot.eighth * 2 + slot.sub) // 4
        sounding.setdefault(key, []).append(pitch + semitones)
    return all(_quarter_ok(group) for group in sounding.values())


def _lead_ok(
    ctx: _Ctx,
    pitches: list[int],
    *,
    low: int | None = None,
    high: int | None = None,
) -> bool:
    low, high = _resolve_limits(ctx, low, high)
    return all(low <= pitch <= high for pitch in pitches)


def _line(ctx: _Ctx, patterns: list[str], passage: ScalePassage) -> tuple[list[_Slot], list[int]] | None:
    slots = _slots(ctx, patterns, passage)
    pitches = _assign(ctx, passage, slots)
    if pitches is None:
        return None
    pitches = _color_line(ctx, passage, slots, pitches)
    if any(abs(right - left) > 2 for left, right in zip(pitches, pitches[1:])):
        return None
    low, high = _compass(ctx, passage)
    if not _groups_ok(slots, pitches, ctx.semitones) or not _lead_ok(ctx, pitches, low=low, high=high):
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


_HAIRPIN_SHIFT = {"p": -8, "mp": -4, "mf": 0, "f": 4}
_HAT_PATTERNS = frozenset(
    {
        "bach_sarabande",
        "sarabande",
        "elegiaque",
        "cantabile",
        "andante",
        "noviembre",
        "chord_melody",
        "preludio",
        "bach_fuga",
        "thumb_cantabile",
        "bach_allemande",
        "castillo",
        "sonatina",
        "torroba_tremolo",
    }
)
_BAROQUE_PATTERNS = frozenset({"bach_bourree", "bach_gavotte", "bach_gigue", "bach_prelude"})
_KINETIC_PATTERNS = frozenset(
    {
        "study",
        "galop",
        "mozart_var",
        "villa_pattern",
        "choro",
        "polca",
        "hemiola",
        "vals",
        "brouwer_etude",
        "etude1",
        "etude11",
        "fandanguillo",
        "danza",
        "alcaniz",
        "olite",
    }
)
_LOUD_DOWN_PATTERNS = _KINETIC_PATTERNS | frozenset({"elogio_pizz", "bach_chaconne"})
# Brouwer keeps the absolute window. Every other listed id is a narrowed row:
# (entry step on a descent, span, ceiling). The key is the pattern id.
_NARROW_ROWS: dict[str, tuple[int, int, int]] = {
    **{name: (6, 24, 80) for name in ("villa_pattern", "etude1", "etude11", "chord_melody", "thumb_cantabile")},
    **{name: (4, 18, 76) for name in ("preludio", "andante", "tremolo", "choro", "vals", "polca", "hemiola", "fandanguillo", "danza", "alcaniz", "olite")},
    **{name: (4, 16, 76) for name in ("study", "galop", "mozart_var", "cantabile", "elegiaque", "castillo", "sonatina", "torroba_tremolo")},
    **{
        name: (4, 12, 74)
        for name in (
            "bach_sarabande",
            "bach_fuga",
            "bach_allemande",
            "bach_courante",
            "bach_bourree",
            "bach_gavotte",
            "bach_gigue",
        )
    },
    "bach_chaconne": (6, 18, 80),
    "bach_prelude": (2, 6, 72),
}
_NARROW_FLOOR = 40


def _base_window(pattern: str) -> tuple[int, int]:
    """Soft/loud before the band shift. An unlisted pattern sings in the Hát window."""
    windows = {
        **{name: (52, 82) for name in _HAT_PATTERNS},
        **{name: (54, 84) for name in _BAROQUE_PATTERNS},
        **{name: (46, 90) for name in _KINETIC_PATTERNS},
        "bach_chaconne": (52, 88),
        "elogio_pizz": (44, 92),
    }
    return windows.get(pattern, (52, 82))


def _pattern_window(pattern: str, band: str) -> tuple[int, int]:
    """Section 2.6.A window, then the 2.6.B shift, clamped one end at a time."""
    soft, loud = _base_window(pattern)
    shift = _HAIRPIN_SHIFT.get(band, 0)
    return max(40, soft + shift), min(96, loud + shift)


def _hairpin_open(
    direction: str,
    prev: int,
    soft: int,
    loud: int,
    pattern: str,
    on_strong: bool,
) -> tuple[int, int]:
    """`(open, arrival)` for the ramp. A downward arrival is `soft` until a pillar floor replaces it."""
    if direction == "up":
        return min(prev, soft), loud
    if pattern in _LOUD_DOWN_PATTERNS and on_strong:
        return loud, soft
    return min(loud, max(prev + 8, _MELODY_APEX)), soft


def _landing_floor(soft: int) -> int:
    """A held arrival sits two above the bass velocity the passage actually writes.

    Composer modules assign `_BASS = 56` and then rebind that name to
    `guitar._BASS` (60). The scale bass uses the rebound value.
    """
    return max(soft, _BASS + 2)


def _monotonic(values: list[int], ascending: bool) -> list[int]:
    if not values:
        return []
    shaped = [values[0]]
    for value in values[1:]:
        previous = shaped[-1]
        shaped.append(max(previous, value) if ascending else min(previous, value))
    return shaped


def _ramp_attacks(
    count: int,
    open_v: int,
    arrival: int,
    exponent: float,
    *,
    pull: bool,
) -> list[int]:
    """One ramp. `count < 2` is the caller's zero-divisor case and is not divided here."""
    if count <= 0:
        return []
    if count == 1:
        return [arrival]
    span = arrival - open_v
    ascending = span >= 0
    raw: list[int] = []
    for index in range(count):
        t = index / (count - 1)
        curved = t ** exponent
        raw.append(int(round(open_v + span * curved)))
    shaped = _monotonic(raw, ascending)
    shaped[0] = open_v
    shaped[-1] = arrival
    shaped = _monotonic(shaped, ascending)
    shaped[-1] = arrival
    if pull and any(value == arrival for value in shaped[:-1]):
        lo, hi = (open_v, arrival) if open_v <= arrival else (arrival, open_v)
        step = -1 if ascending else 1
        pulled: list[int] = []
        for value in shaped[:-1]:
            if value == arrival:
                pulled.append(min(hi, max(lo, arrival + step)))
            else:
                pulled.append(value)
        pulled.append(arrival)
        shaped = _monotonic(pulled, ascending)
        shaped[-1] = arrival
    return shaped


def _narrow_ends(direction: str, heard: int, pattern: str) -> tuple[int, int]:
    """`(open, dest)` for a narrowed row. The floor of 40 binds a descent only."""
    step, span, ceiling = _NARROW_ROWS[pattern]
    if direction == "up":
        open_v = min(ceiling, heard)
        return open_v, min(ceiling, open_v + span)
    open_v = min(ceiling, max(_NARROW_FLOOR, heard + step))
    return open_v, min(open_v, max(_NARROW_FLOOR, open_v - span))


def _apply_retreat(
    values: list[int],
    retreats: list[bool],
    direction: str,
    low: int,
    high: int,
) -> list[int]:
    """Nudge retreat attacks against the hairpin. The target, the last value, stays put."""
    if not values:
        return []
    out = list(values)
    step = -3 if direction == "up" else 3
    last = len(out) - 1
    for index, flag in enumerate(retreats[:last]):
        if not flag:
            continue
        out[index] = min(high, max(low, out[index] + step))
    return out


def _majority_pattern(ctx: _Ctx, patterns: list[str], passage: ScalePassage) -> str:
    counts: dict[str, int] = {}
    order: list[str] = []
    for eighth in range(passage.start, passage.target):
        name = _bar_pattern(ctx, eighth // ctx.epb, patterns)
        if name not in counts:
            order.append(name)
            counts[name] = 0
        counts[name] += 1
    if not counts:
        return _bar_pattern(ctx, max(0, passage.start) // ctx.epb, patterns)
    best = max(counts.values())
    winners = [name for name in order if counts[name] == best]
    if len(winners) == 1:
        return winners[0]
    start_name = _bar_pattern(ctx, max(0, passage.start) // ctx.epb, patterns)
    if start_name in winners:
        return start_name
    return winners[0]


def _holds_pitch(melody: list[int], eighth: int) -> int:
    """How many eighths `melody` keeps `melody[eighth]`, counting `eighth` itself."""
    if eighth < 0 or eighth >= len(melody):
        return 0
    pitch = melody[eighth]
    count = 0
    while eighth + count < len(melody) and melody[eighth + count] == pitch:
        count += 1
    return count


def _target_is_pillar(ctx: _Ctx, passage: ScalePassage) -> bool:
    if passage.target % ctx.epb in ctx.strong:
        return True
    return _holds_pitch(ctx.melody, passage.target) >= 2


def hairpin_velocities(
    count: int,
    *,
    direction: str,
    pattern: str,
    band: str,
    prev: int,
    on_strong: bool,
    length: int,
    epb: int,
    pillar: bool,
    retreats: list[bool] | None = None,
) -> list[int]:
    """Velocities for `count` lead attacks, the last of which is the target.

    Brouwer and Elogio keep section 2.6.C. A narrowed pattern treats `prev`
    as the post-wave note and clamps a retreat inside the ramp.
    """
    if count <= 0:
        return []
    flags = list(retreats or [])
    if len(flags) < count:
        flags.extend([False] * (count - len(flags)))
    exponent = 1.0 if length <= epb else 1.3
    if pattern in _NARROW_ROWS:
        open_v, dest = _narrow_ends(direction, prev, pattern)
        values = [dest] if count == 1 else _ramp_attacks(count, open_v, dest, exponent, pull=True)
        low, high = (open_v, dest) if open_v <= dest else (dest, open_v)
        return _apply_retreat(values, flags, direction, low, high)
    soft, loud = _pattern_window(pattern, band)
    open_v, _arrival = _hairpin_open(direction, prev, soft, loud, pattern, on_strong)
    if direction == "up":
        values = [loud] if count == 1 else _ramp_attacks(count, open_v, loud, exponent, pull=True)
    elif pillar:
        pre = count - 1
        if pre < 2:
            values = [open_v] * max(0, pre)
        else:
            values = _ramp_attacks(pre, open_v, soft, exponent, pull=False)
        values.append(_landing_floor(soft))
    else:
        values = [soft] if count == 1 else _ramp_attacks(count, open_v, soft, exponent, pull=True)
    return _apply_retreat(values, flags, direction, soft, loud)


def _curve(
    ctx: _Ctx,
    patterns: list[str],
    passage: ScalePassage,
    slots: list[_Slot],
    previous: int,
) -> list[int]:
    pattern = _majority_pattern(ctx, patterns, passage)
    length = passage.passage_eighths or (passage.target - passage.start)
    return hairpin_velocities(
        len(slots),
        direction=passage.direction,
        pattern=pattern,
        band=ctx.band(passage.start // ctx.epb) if ctx.bars else "mf",
        prev=previous,
        on_strong=passage.start % ctx.epb in ctx.strong,
        length=length,
        epb=ctx.epb,
        pillar=passage.direction == "down" and _target_is_pillar(ctx, passage),
        retreats=[slot.retreat for slot in slots],
    )


def _slap_eighths(ctx: _Ctx, patterns: list[str], passage: ScalePassage) -> set[int]:
    """Eighth 3 of a sub-bar Elogio run. A long run is allowed to replace the slap."""
    if passage.tier == "tier1" or passage.passage_eighths >= ctx.epb:
        return set()
    found: set[int] = set()
    for eighth in range(passage.start, passage.target):
        if eighth % ctx.epb != 3:
            continue
        if _bar_pattern(ctx, eighth // ctx.epb, patterns) == "elogio_pizz":
            found.add(eighth)
    return found


def _drop_region(
    events: list[NoteEvent],
    start: int,
    end: int,
    epb: int,
    preserve: set[int] | None = None,
) -> list[NoteEvent]:
    """Remove sounding time in `[start, end)` without inventing an onset at `end`.

    `preserve` keeps the attack that starts on those eighths, so a Bartók slap
    at eighth 3 survives a sub-bar scale.
    """
    keep_onsets = preserve or set()
    lo = start * 2
    hi = end * 2
    kept: list[NoteEvent] = []
    for event in events:
        if event.midi is None:
            kept.append(event)
            continue
        begin = _start16(event, epb)
        if begin // 2 in keep_onsets:
            kept.append(event)
            continue
        finish = begin + _dur16(event)
        if finish <= lo or begin >= hi:
            if begin >= hi and event.tie_stop and not _tie_opens_at(kept, begin, event.midi, epb):
                event = replace(event, tie_stop=False)
            kept.append(event)
            continue
        if begin < lo:
            kept.extend(
                _spell16(
                    begin,
                    lo - begin,
                    event.midi,
                    epb,
                    event.voice,
                    event.velocity or _BASS,
                    event.accent,
                    tie_in=event.tie_stop,
                )
            )
    return kept


def _tie_opens_at(events: list[NoteEvent], begin: int, midi: int, epb: int) -> bool:
    """True when the last kept note ties into `begin` on `midi`."""
    for event in reversed(events):
        if event.midi is None:
            continue
        start = _start16(event, epb)
        return event.tie_start and event.midi == midi and start + _dur16(event) == begin
    return False


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
    """Land on `pitch` at `target` without breaking a sustain that continues past it.

    A melody note longer than one legal duration is already a tie. Rewriting only
    the chunk that covers `target` used to drop `tie_start`, leaving the later
    chunk with `tie_stop` and the old velocity.
    """
    when = target * 2
    rewritten: list[NoteEvent] = []
    index = 0
    stamped = False
    while index < len(lead):
        event = lead[index]
        if event.midi is None:
            rewritten.append(event)
            index += 1
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        if stamped or not (begin <= when < finish):
            rewritten.append(event)
            index += 1
            continue
        if begin < when:
            rewritten.extend(
                _spell16(
                    begin,
                    when - begin,
                    event.midi,
                    epb,
                    1,
                    event.velocity or _MELODY,
                    event.accent,
                    tie_in=event.tie_stop,
                )
            )
        if begin == when and not _on_sixteenth_grid(event):
            rewritten.append(replace(event, midi=pitch))
            stamped = True
            index += 1
            continue
        carry = bool(event.tie_start and event.midi == pitch)
        rewritten.extend(
            _spell16(
                when,
                finish - when,
                pitch,
                epb,
                1,
                velocity,
                event.accent,
                tie_out=carry,
            )
        )
        stamped = True
        index += 1
        if not event.tie_start:
            continue
        cursor = finish
        while index < len(lead):
            nxt = lead[index]
            if nxt.midi is None:
                break
            nxt_begin = _start16(nxt, epb)
            if nxt_begin != cursor or not nxt.tie_stop or nxt.midi != event.midi:
                break
            if carry:
                rewritten.append(replace(nxt, velocity=velocity))
            else:
                rewritten.append(replace(nxt, tie_stop=False))
            cursor = nxt_begin + _dur16(nxt)
            index += 1
            if not nxt.tie_start:
                break
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


def _bass_under_slices(
    ctx: _Ctx,
    bar: int,
    slices: list[list[int]],
    *,
    sounding_low: int | None = None,
    sounding_high: int | None = None,
) -> int | None:
    """A root or fifth that stays playable under each eighth, not under their union.

    `sounding_low` and `sounding_high` bound the sounding pitch. Thumb roots
    use 48..64. The ordinary bass ceiling sounds at 53, so a thumb search
    continues up to the written pitch of that window. A guitar-floor note at
    40..47 can still be playable and is not a thumb root.
    """
    if not slices:
        return None
    chord = ctx.chord(bar)
    root = chord.pitches[0] % 12
    fifth = chord.pitches[2] % 12 if len(chord.pitches) > 2 else (root + 7) % 12
    high = ctx.bass_high
    if sounding_high is not None:
        high = max(high, sounding_high - ctx.semitones)
    for pc in (root, fifth):
        for note in range(high, ctx.bass_low - 1, -1):
            if note % 12 != pc:
                continue
            sounding_bass = note + ctx.semitones
            if sounding_low is not None and sounding_bass < sounding_low:
                continue
            if sounding_high is not None and sounding_bass > sounding_high:
                continue
            if any(note >= lead for group in slices for lead in group):
                continue
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
    if pattern == "bach_courante":
        return [origin + offset for offset in _courante_bass_offsets(ctx, bar) if inside(origin + offset)]
    if pattern == "bach_prelude":
        return [origin + offset for offset in _half_bar_bass_offsets(ctx, "prelude") if inside(origin + offset)]
    if pattern == "bach_allemande":
        return [origin + offset for offset in _half_bar_bass_offsets(ctx, "allemande") if inside(origin + offset)]
    return [origin + offset for offset in ctx.strong if inside(origin + offset)]


def _bass_accent(ctx: _Ctx, pattern: str, eighth: int) -> bool:
    local = eighth % ctx.epb
    if pattern == "bach_courante":
        return _courante_bass_accent(ctx, eighth)
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


def _bar_covered(bar: int, start: int, target: int, epb: int) -> bool:
    lo = bar * epb
    return start <= lo and lo + epb <= target


def _preludio_pair(ctx: _Ctx, patterns: list[str], bar: int) -> tuple[int, int | None]:
    anchor = _preludio_anchor(ctx, bar, patterns)
    partner = anchor + 1
    if (
        partner < ctx.bars
        and _bar_pattern(ctx, partner, patterns) == "preludio"
        and _preludio_anchor(ctx, partner, patterns) == anchor
    ):
        return anchor, partner
    return anchor, None


def _slices_between(
    leads: dict[int, list[int]],
    eighth: int,
    stop: int,
    fallback: int,
) -> list[list[int]]:
    slices: list[list[int]] = []
    for cursor in range(eighth, stop):
        group = leads.get(cursor)
        if group:
            slices.append(group)
    if not slices:
        slices = [[fallback]]
    return slices


def _host_attacks(ctx: _Ctx, pattern: str, bar: int, start: int, target: int) -> list[tuple[int, int]]:
    """`(eighth, stop)` bass attacks for one yielded host bar."""
    epb = ctx.epb
    origin = bar * epb
    if pattern == "etude11":
        found: list[tuple[int, int]] = []
        for offset in (0, 2, 4, 6):
            if offset >= epb:
                break
            eighth = origin + offset
            if start <= eighth < target:
                found.append((eighth, eighth + 2))
        return found
    if pattern in {"etude1", "thumb_cantabile"} and start <= origin < target:
        return [(origin, origin + epb)]
    return []


def _low_scale_lead(ctx: _Ctx, slices: list[list[int]]) -> bool:
    """True when the scale is already in the register below the treble window."""
    sounding = [lead + ctx.semitones for group in slices for lead in group]
    return bool(sounding) and min(sounding) < 59


def _plant_attacks(
    ctx: _Ctx,
    pattern: str,
    bar: int,
    attacks: list[tuple[int, int]],
    leads: dict[int, list[int]],
    *,
    sounding_low: int | None = None,
    sounding_high: int | None = None,
    allow_rest: bool = False,
) -> list[NoteEvent] | None:
    """Plant every attack. One missing root or fifth rejects the passage.

    `allow_rest` lets a long Villa or Brouwer scale keep the low string when
    no chord root or fifth fits under the lead. An empty list is that rest.
    """
    if not attacks:
        return None
    events: list[NoteEvent] = []
    for eighth, stop in attacks:
        if stop <= eighth:
            return None
        slices = _slices_between(leads, eighth, stop, _melody_pitch(ctx, eighth))
        pitch = _bass_under_slices(
            ctx,
            bar,
            slices,
            sounding_low=sounding_low,
            sounding_high=sounding_high,
        )
        if pitch is None:
            if allow_rest and _low_scale_lead(ctx, slices):
                continue
            return None
        events.extend(
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
    return events


def _release_split_ties(
    ctx: _Ctx,
    patterns: list[str],
    start: int,
    target: int,
    low: list[NoteEvent],
) -> list[NoteEvent]:
    """A split preludio pair keeps the outside half, without a tie into the scale bar."""
    epb = ctx.epb
    released: list[NoteEvent] = []
    for event in low:
        if event.midi is None or not (event.tie_start or event.tie_stop):
            released.append(event)
            continue
        begin = _start16(event, epb)
        finish = begin + _dur16(event)
        bar = (begin // 2) // epb
        if _host_pattern(ctx, patterns, bar) != "preludio":
            released.append(event)
            continue
        anchor, partner = _preludio_pair(ctx, patterns, bar)
        if partner is None:
            released.append(event)
            continue
        anchor_in = _bar_covered(anchor, start, target, epb)
        partner_in = _bar_covered(partner, start, target, epb)
        if anchor_in == partner_in:
            released.append(event)
            continue
        if event.tie_start and finish <= start * 2:
            event = replace(event, tie_start=False)
        if event.tie_stop and begin >= target * 2:
            event = replace(event, tie_stop=False)
        released.append(event)
    return released


def _plant_preludio(
    ctx: _Ctx,
    patterns: list[str],
    bar: int,
    start: int,
    target: int,
    leads: dict[int, list[int]],
    done: set[int],
) -> list[NoteEvent] | None:
    """Bass for one framed-preludio bar. An empty list means the pair was already planted."""
    anchor, partner = _preludio_pair(ctx, patterns, bar)
    epb = ctx.epb
    both = partner is not None and _bar_covered(anchor, start, target, epb) and _bar_covered(partner, start, target, epb)
    if both:
        if anchor in done:
            return []
        done.add(anchor)
        origin = anchor * epb
        stop = origin + 2 * epb
        slices = _slices_between(leads, origin, stop, _melody_pitch(ctx, origin))
        pitch = _bass_under_slices(ctx, anchor, slices)
        if pitch is None:
            return None
        return _eighth_event(origin, 2 * epb, pitch, epb, 3, _BASS, accent=True)
    origin = bar * epb
    strong = [offset for offset in ctx.strong if offset < epb]
    attacks: list[tuple[int, int]] = []
    for index, offset in enumerate(strong):
        eighth = origin + offset
        if not start <= eighth < target:
            continue
        nxt = origin + strong[index + 1] if index + 1 < len(strong) else origin + epb
        attacks.append((eighth, min(nxt, origin + epb)))
    return _plant_attacks(ctx, "preludio", bar, attacks, leads)


def _rewrite_bass(
    ctx: _Ctx,
    patterns: list[str],
    passage: ScalePassage,
    slots: list[_Slot],
    pitches: list[int],
    lead: list[NoteEvent],
    low: list[NoteEvent],
) -> list[NoteEvent] | None:
    start, target = passage.start, passage.target
    slap = _slap_eighths(ctx, patterns, passage)
    low = _drop_region(low, start, target, ctx.epb, slap)
    low = _release_split_ties(ctx, patterns, start, target, low)
    leads = _leads_at(slots, pitches)
    first = start // ctx.epb
    last = max(first, (target - 1) // ctx.epb)
    fuga_bars = [
        bar
        for bar in range(first, min(ctx.bars, last + 1))
        if _bar_pattern(ctx, bar, patterns) == "bach_fuga"
    ]
    done_pairs: set[int] = set()
    for bar in range(first, min(ctx.bars, last + 1)):
        pattern = _bar_pattern(ctx, bar, patterns)
        if pattern == "bach_fuga":
            continue
        host = _host_pattern(ctx, patterns, bar)
        if host == "preludio":
            planted = _plant_preludio(ctx, patterns, bar, start, target, leads, done_pairs)
            if planted is None:
                return None
            low.extend(planted)
            continue
        if host in {"etude1", "etude11", "thumb_cantabile"}:
            window = (48, 64) if host == "thumb_cantabile" else (None, None)
            # A long Villa or Brouwer run may take the low E string. Bach, Sor,
            # and Barrios stop at 52 and still need a bass under the line.
            allow_rest = passage.passage_eighths >= ctx.epb and ctx.ensemble in {"villa", "brouwer"}
            planted = _plant_attacks(
                ctx,
                host,
                bar,
                _host_attacks(ctx, host, bar, start, target),
                leads,
                sounding_low=window[0],
                sounding_high=window[1],
                allow_rest=allow_rest,
            )
            if planted is None:
                return None
            low.extend(planted)
            continue
        written = _written_bass_spans(ctx, pattern, bar)
        if written is not None:
            origin = bar * ctx.epb
            attacks = []
            for offset, duration in written:
                eighth = origin + offset
                stop = min(eighth + duration, origin + ctx.epb, target)
                if eighth in slap or not start <= eighth < target or stop <= eighth:
                    continue
                attacks.append((eighth, stop))
        else:
            onsets = [eighth for eighth in _bass_onsets(ctx, pattern, bar, start, target) if eighth not in slap]
            attacks = []
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
                if stop > eighth:
                    attacks.append((eighth, stop))
        for eighth, stop in attacks:
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
    if fuga_bars:
        covered = set(fuga_bars)
        low = [event for event in low if event.midi is None or event.bar not in covered]
        for bar in fuga_bars:
            low.extend(_fuga_bass_under_lead(ctx, bar, lead))
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
    patterns: list[str],
    passage: ScalePassage,
    slots: list[_Slot],
    pitches: list[int],
    support: list[NoteEvent],
    low: list[NoteEvent],
) -> list[NoteEvent]:
    support = _drop_region(
        support, passage.start, passage.target, ctx.epb, _slap_eighths(ctx, patterns, passage)
    )
    leads = _leads_at(slots, pitches)
    sixteenth = {slot.eighth for slot in slots if slot.dur16 == 1 and slot.eighth < passage.target}
    plain = {slot.eighth for slot in slots if slot.dur16 == 2 and slot.eighth < passage.target}
    wanted: list[int] = []
    if passage.start in sixteenth and _is_strong(ctx, passage.start):
        wanted.append(passage.start)
    wanted.extend(eighth for eighth in sorted(plain) if _is_strong(ctx, eighth))
    for eighth in wanted:
        # Host grids leave the inner voice empty, including below 88 BPM,
        # where an eighth-note run would otherwise keep one strong-beat note.
        if _host_pattern(ctx, patterns, eighth // ctx.epb):
            continue
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
    velocities = _curve(ctx, patterns, passage, slots, previous)
    if len(velocities) != len(slots):
        return None
    lead = _install_lead(lead, slots, pitches, velocities, ctx.epb)
    rewritten = _rewrite_bass(ctx, patterns, passage, slots, pitches, lead, low)
    if rewritten is None:
        return None
    low = rewritten
    support = _rewrite_support(ctx, patterns, passage, slots, pitches, support, low)
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


def restamp_passage_hairpins(ctx: _Ctx, patterns: list[str], plan: ScalePlan, lead, written_lead):
    """Reprint passage and tier-1 hairpins onto the lead after the volume wave.

    Brouwer and Elogio still read `written_lead`, the line before the wave.
    A narrowed row reads the lead being overwritten, so a later passage sees
    the hairpin the previous one just printed. `plan.passages` run first.
    """
    for passage in (*plan.passages, *plan.tier1):
        built = _line(ctx, patterns, passage)
        if built is None:
            continue
        slots, pitches = built
        pattern = _majority_pattern(ctx, patterns, passage)
        source = written_lead if pattern not in _NARROW_ROWS else lead
        previous = _velocity_before(source, passage.start, ctx.epb)
        velocities = _curve(ctx, patterns, passage, slots, previous)
        if len(velocities) != len(slots):
            continue
        lead = _install_lead(lead, slots, pitches, velocities, ctx.epb)
        starts = {slot.eighth * 2 + slot.sub for slot in slots}
        lead = [
            replace(event, hairpin=True)
            if event.midi is not None and _start16(event, ctx.epb) in starts
            else event
            for event in lead
        ]
    return lead


def sounding_swarm_eighths(ctx: _Ctx, patterns: list[str], covered: set[int]) -> set[int]:
    """Sarabande swarm eighths that a passage or tier-1 window did not replace.

    Kept out of `ScalePlan.scale_eighths` so boundary pickups and caesuras still
    see only passage eighths. Callers union this in after those two passes.
    """
    found: set[int] = set()
    for bar in range(ctx.bars):
        if _bar_pattern(ctx, bar, patterns) != "sarabande":
            continue
        found |= brouwer_group2_intrinsic_eighths(ctx, bar)
    return found - set(covered)


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
