"""Shared machinery for the feature-gated Suite Popular Brasileira movements.

Each movement module owns its data: the production pattern id, meter, printed
title, candidate `SentenceSpec`, caveat, and flag reader. This module owns the
registration, eligibility, plan, and render steps once, so Valsa, Gavotta,
Schottish, and Choros No. 1 cannot drift from the Mazurka shape.

Registration
------------
`ensure_registered` installs exactly the gate's sentence under
`(pattern, meter)` with `valid_figures=VILLA_FIGURES`, and only when called.
`unregister` removes exactly that value. Importing any movement module or this
one never mutates `SENTENCE_SPECS`.

Render
------
`render_sentence` plans the movement's tile, then calls the supplied figure
renderer once per bar. It returns raw bar voices and the plan, not a finished
render: `guitar_patterns._render_sentence_tail` then runs the same post-wave
tail as the historical bar loop.

Eligibility
-----------
A movement is eligible only for a whole Villa body in its engine meter, at
least `min_bars` long, with no pedal frame bar. Selection and render share the
predicate, so the chooser cannot paint a pattern the render gate would decline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any

from app.sonify import sentence_specs
from app.sonify.guitar_villa_figures import FIGURE_CONTOURS, VILLA_FIGURES
from app.sonify.pattern_registry import PatternMeta
from app.sonify.sentence_plan import (
    AutoAABA,
    PhraseView,
    PlanPolicy,
    build_plan,
)
from app.sonify.sentence_production import (
    SentenceVoices,
    bar_plan_cells,
    has_pedal_bars,
    mark_trace,
    phrase_at,
)
from app.sonify.sentence_specs import SentenceSpec

FigureRenderer = Callable[[Any, int, Any, int], tuple[list, list, list]]
CellRenderer = Callable[
    [Any, int, Any, str, int], tuple[list, list, list] | None
]


@dataclass(frozen=True)
class SuiteGate:
    """One promoted Suite movement as data plus its flag plumbing.

    ``partial`` opts into the body/door merge: door and pedal bars are allowed,
    and only the body bars have to reach ``min_bars``. The default stays the
    historical whole-movement predicate, byte for byte.

    ``extra_specs`` opt into the phrase-level plan seam. A gate with more than
    one spec plans every body phrase through `build_plan`, using ``policy``
    when supplied and `AutoAABA` otherwise. A single-spec gate keeps the old
    one-tile plan.
    """

    pattern: str
    meter: str
    title: str
    name_source: str
    min_bars: int
    sentence_id: str
    spec: SentenceSpec
    caveat: str
    enabled: Callable[[], bool]
    use_flag: Callable[..., AbstractContextManager[None]]
    level: str = "topic"
    partial: bool = False
    extra_specs: tuple[SentenceSpec, ...] = ()
    policy: PlanPolicy | None = None
    # Optional Phase 4 texture-cell realizer. A gate without one keeps the
    # figure-only contract; a plan that needs a cell falls back instead of
    # rendering silence. Signature:
    # `(ctx, bar, phrase, cell_id, cell_bar) -> (lead, support, low) | None`.
    render_cell: CellRenderer | None = None
    # Cell ids the owner's registry holds. Passed to `register` when set, so a
    # typo in a tile spec cannot register. `None` keeps the historical
    # figure-only gate unchanged.
    valid_cells: frozenset[str] | None = None
    # Opt-in movement scope. When set, a gate answers only a movement whose
    # (span, index) pair is in the set. A direct/legacy render carries neither
    # field, so it can never silently satisfy a scoped gate.
    movement_scopes: frozenset[tuple[str, int]] | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.pattern, self.meter)

    @property
    def specs(self) -> tuple[SentenceSpec, ...]:
        # `register` stores specs sorted by (length_min, id); return the same
        # order so `ensure_registered`/`unregister` compare equal tuples.
        return tuple(
            sorted(
                (self.spec, *self.extra_specs),
                key=lambda spec: (spec.select.length_min, spec.id),
            )
        )

    @property
    def meta(self) -> PatternMeta:
        return PatternMeta(self.pattern, self.level, self.name_source)


def ensure_registered(gate: SuiteGate) -> bool:
    """Register the gate's sentence if the table does not already hold it."""
    existing = sentence_specs.SENTENCE_SPECS.get(gate.key)
    if existing is not None:
        if existing == gate.specs:
            return False
        raise ValueError(
            f"{gate.key} already registers {existing!r}; "
            f"the Suite {gate.title} would replace it"
        )
    sentence_specs.register(
        gate.pattern,
        gate.meter,
        *gate.specs,
        valid_figures=frozenset(VILLA_FIGURES),
        valid_cells=gate.valid_cells,
    )
    return True


def unregister(gate: SuiteGate) -> bool:
    """Remove exactly the spec this gate owns, leaving anything else alone."""
    if sentence_specs.SENTENCE_SPECS.get(gate.key) != gate.specs:
        return False
    del sentence_specs.SENTENCE_SPECS[gate.key]
    return True


@contextmanager
def use_gate(gate: SuiteGate, enabled: bool = True) -> Iterator[None]:
    """Pin the gate's flag and own its registry entry for the context."""
    with gate.use_flag(enabled):
        added = ensure_registered(gate) if enabled else False
        try:
            yield
        finally:
            if added:
                unregister(gate)


def _body_bars(ctx: Any) -> list[int]:
    """Body bars: every bar whose kind is not a frame/pedal kind."""
    from app.sonify.guitar import _PEDAL

    return [
        bar
        for bar in range(ctx.bars)
        if ctx.kind_at.get(bar, "phrase") not in _PEDAL
    ]


def _contiguous_runs(bars: list[int]) -> list[list[int]]:
    runs: list[list[int]] = []
    for bar in bars:
        if runs and bar == runs[-1][-1] + 1:
            runs[-1].append(bar)
        else:
            runs.append([bar])
    return runs


def _phrase_views(ctx: Any) -> tuple[PhraseView, ...]:
    """Body phrases as bar views with bridge/trio metadata and offset."""
    from app.sonify.guitar import _PEDAL

    epb = max(1, ctx.epb)
    rows: list[PhraseView] = []
    for phrase in ctx.phrases:
        start_bar = max(0, phrase.start // epb)
        if start_bar >= ctx.bars:
            continue
        if ctx.kind_at.get(start_bar, "phrase") in _PEDAL:
            continue
        end_bar = max(
            start_bar + 1,
            (max(phrase.end, phrase.start + 1) - 1) // epb + 1,
        )
        bars = min(ctx.bars, end_bar) - start_bar
        if bars < 1:
            continue
        section = ctx.section(min(ctx.bars - 1, start_bar))
        kind = "phrase"
        if section is not None and getattr(section, "trio", False):
            kind = "trio"
        elif section is not None and getattr(section, "bridge", False):
            kind = "bridge"
        try:
            closes = bool(phrase.closes)
        except (IndexError, ValueError):
            closes = False
        try:
            rise = int(phrase.rise)
        except (IndexError, ValueError):
            rise = 0
        rows.append(
            PhraseView(
                index=len(rows),
                count=0,
                start_bar=start_bar,
                bars=bars,
                closes=closes,
                rise=rise,
                kind=kind,
            )
        )
    count = len(rows)
    return tuple(
        PhraseView(
            index=row.index,
            count=count,
            start_bar=row.start_bar,
            bars=row.bars,
            closes=row.closes,
            rise=row.rise,
            kind=row.kind,
        )
        for row in rows
    )


def eligible(gate: SuiteGate, ctx: Any) -> bool:
    """A Villa movement in the gate's meter with enough body bars.

    The historical predicate additionally requires no pedal/frame bar. A
    ``partial`` gate allows those bars and only measures the body.
    """
    if ctx.ensemble != "villa" or ctx.kind != gate.meter:
        return False
    if gate.movement_scopes is not None:
        span = getattr(ctx, "movement_span", None)
        index = getattr(ctx, "movement_index", None)
        if span is None or index is None:
            return False
        if (span, index) not in gate.movement_scopes:
            return False
    if gate.partial:
        return len(_body_bars(ctx)) >= gate.min_bars
    if ctx.bars < gate.min_bars:
        return False
    return not has_pedal_bars(ctx)


Plan = tuple[
    dict[int, int],
    dict[int, tuple[str, int]],
    dict[int, Any],
    frozenset[int] | None,
]


def _cell_positions(
    planned: list,
) -> dict[int, tuple[str, int]]:
    """Bar -> (cell id, cell-local bar) for every cell slot occurrence."""
    positions: dict[int, tuple[str, int]] = {}
    for slot in planned:
        if slot.cell is None or not slot.bars:
            continue
        origin = slot.bars[0]
        for bar in slot.bars:
            positions[bar] = (slot.cell, bar - origin)
    return positions


def _single_spec_plan(gate: SuiteGate, ctx: Any) -> Plan | None:
    if not gate.partial:
        planned = sentence_specs.plan_slots(
            gate.pattern,
            gate.meter,
            ctx.bars,
            0,
            closes=False,
            rise=0,
        )
        found = bar_plan_cells(planned, ctx.bars)
        if found is None:
            return None
        figures, cells, contours = found
        if cells and gate.render_cell is None:
            return None
        return figures, _cell_positions(planned or []), contours, None

    body = _body_bars(ctx)
    if len(body) < gate.min_bars:
        return None
    planned: list = []
    for run in _contiguous_runs(body):
        slots = sentence_specs.plan_slots(
            gate.pattern,
            gate.meter,
            len(run),
            0,
            closes=False,
            rise=0,
            offset=run[0],
        )
        if slots is None:
            return None
        planned.extend(slots)
    found = bar_plan_cells(planned, ctx.bars, require_full=False)
    if found is None:
        return None
    figures, cells, contours = found
    if cells and gate.render_cell is None:
        return None
    if any(bar not in figures and bar not in cells for bar in body):
        return None
    covered = frozenset(figures) | frozenset(cells)
    return figures, _cell_positions(planned), contours, covered


def _phrase_plan(gate: SuiteGate, ctx: Any) -> Plan | None:
    views = _phrase_views(ctx)
    if not views:
        return None
    plan = build_plan(
        gate.pattern,
        gate.meter,
        views,
        policy=gate.policy or AutoAABA(),
        registry=None,
    )
    found = bar_plan_cells(
        plan.slots,
        ctx.bars,
        require_full=not gate.partial,
    )
    if found is None:
        return None
    figures, cells, contours = found
    if cells and gate.render_cell is None:
        return None
    covered = frozenset(bar for slot in plan.slots for bar in slot.bars)
    if gate.partial:
        body = set(_body_bars(ctx))
        if any(bar not in figures and bar not in cells for bar in body):
            return None
        covered &= frozenset(body)
    else:
        covered = None
    return figures, _cell_positions(plan.slots), contours, covered


def _plan(gate: SuiteGate, ctx: Any) -> Plan | None:
    if not gate.enabled() or not eligible(gate, ctx):
        return None
    # The registry entry is deliberately lazy. An env-var audition never calls
    # the context manager, so this is the one place production installs it.
    ensure_registered(gate)
    if len(gate.specs) > 1:
        return _phrase_plan(gate, ctx)
    return _single_spec_plan(gate, ctx)


def selectable(gate: SuiteGate, ctx: Any) -> bool:
    """Whether selection may return this pattern for the movement.

    This is the same predicate the renderer uses, plus the plan check. A caller
    that only reads the chooser can never paint a pattern the render gate would
    then decline.
    """
    return gate.enabled() and _plan(gate, ctx) is not None


def render_sentence(
    gate: SuiteGate,
    ctx: Any,
    render_figure: FigureRenderer,
) -> SentenceVoices | None:
    """Render the gate's tile for an eligible movement, or None to fall back."""
    plan = _plan(gate, ctx)
    if plan is None:
        return None
    figures, cell_at, slot_contours, covered = plan

    lead: list = []
    support: list = []
    low: list = []
    for bar in sorted(set(figures) | set(cell_at)):
        if covered is not None and bar not in covered:
            continue
        if bar in cell_at:
            cell_id, cell_bar = cell_at[bar]
            # `_plan` already rejected a cell plan with no renderer; this guard
            # keeps a hand-built gate from crashing if it is bypassed.
            if gate.render_cell is None:
                return None
            part = gate.render_cell(
                ctx, bar, phrase_at(ctx, bar), cell_id, cell_bar
            )
            if part is None:
                return None
            part_lead, part_support, part_low = part
        else:
            part_lead, part_support, part_low = render_figure(
                ctx, bar, phrase_at(ctx, bar), figures[bar]
            )
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)

    mark_trace(ctx)
    contours = {
        bar: FIGURE_CONTOURS[figure]
        for bar, figure in figures.items()
        if figure in FIGURE_CONTOURS and (covered is None or bar in covered)
    }
    return SentenceVoices(
        lead,
        support,
        low,
        figures,
        contours,
        slot_contours=slot_contours,
        covered=covered,
        pattern=gate.pattern,
    )
