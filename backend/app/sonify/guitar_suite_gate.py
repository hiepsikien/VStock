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
from app.sonify.sentence_production import (
    SentenceVoices,
    bar_plan,
    has_pedal_bars,
    mark_trace,
    phrase_at,
)
from app.sonify.sentence_specs import SentenceSpec

FigureRenderer = Callable[[Any, int, Any, int], tuple[list, list, list]]


@dataclass(frozen=True)
class SuiteGate:
    """One promoted Suite movement as data plus its flag plumbing."""

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

    @property
    def key(self) -> tuple[str, str]:
        return (self.pattern, self.meter)

    @property
    def specs(self) -> tuple[SentenceSpec, ...]:
        return (self.spec,)

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


def eligible(gate: SuiteGate, ctx: Any) -> bool:
    """A whole Villa movement in the gate's meter with no pedal frame bar."""
    if ctx.ensemble != "villa" or ctx.kind != gate.meter:
        return False
    if ctx.bars < gate.min_bars:
        return False
    return not has_pedal_bars(ctx)


def _plan(
    gate: SuiteGate, ctx: Any
) -> tuple[dict[int, int], dict[int, Any]] | None:
    if not gate.enabled() or not eligible(gate, ctx):
        return None
    # The registry entry is deliberately lazy. An env-var audition never calls
    # the context manager, so this is the one place production installs it.
    ensure_registered(gate)
    planned = sentence_specs.plan_slots(
        gate.pattern,
        gate.meter,
        ctx.bars,
        0,
        closes=False,
        rise=0,
    )
    return bar_plan(planned, ctx.bars)


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
    figures, slot_contours = plan

    lead: list = []
    support: list = []
    low: list = []
    for bar in range(ctx.bars):
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
        if figure in FIGURE_CONTOURS
    }
    return SentenceVoices(
        lead, support, low, figures, contours, slot_contours=slot_contours
    )
