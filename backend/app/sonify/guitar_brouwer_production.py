"""Feature-gated production home for the Brouwer etude / November A-B-A.

The Studio candidate `brouwer_etude_noviembre_aba` is a three-bar sentence:
the Afro-Cuban etude motor, the November ballad, then the motor again. This
module promotes that sentence into the production renderer behind an explicit
flag.

Flag
----
`VSTOCK_BROUWER_PRODUCTION` is read through
:mod:`app.sonify.production_flags` at call time. Missing, empty, falsy, unknown,
and rollback values keep the historical Brouwer etude writer byte for byte.

When the flag is on, the sentence is registered in the production registry as
`("brouwer_etude", "4/4")` with `valid_figures=BROUWER_FIGURES`. The
registration is lazy: importing this module never mutates `SENTENCE_SPECS`.
`use_brouwer_aba` pins the flag and removes exactly the entry it added.

Eligibility
-----------
A Brouwer movement must be 4/4, at least three bars long, and free of pedal
frame bars. Every other movement, and every flag-off render, falls back to the
existing etude dispatch.

Render
------
`render_sentence` plans the candidate, then calls
`guitar_brouwer_figures.render_brouwer_figure` once per bar. The figure pen
carries the canto already sung, so the Sarabande writer keeps its existing
contract even though the ABA itself never asks for it. It returns the raw bar
voices and the plan; the shared renderer runs the same post-wave tail as the
historical bar loop.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.sonify import sentence_specs
from app.sonify.guitar_brouwer_figures import (
    BROUWER_ETUDE,
    BROUWER_FIGURES,
    BROUWER_NOVIEMBRE,
    BrouwerFigurePen,
    BrouwerFigureState,
    render_brouwer_figure,
)
from app.sonify.production_flags import (
    brouwer_production_enabled,
    use_brouwer_production,
)
from app.sonify.sentence_production import (
    SentenceVoices,
    bar_plan,
    has_pedal_bars,
    mark_trace,
    phrase_at,
)
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

BROUWER_PATTERN = "brouwer_etude"
BROUWER_METER = "4/4"
BROUWER_MIN_BARS = 3
BROUWER_ABA_ID = "brouwer_etude_noviembre_aba"

# The code twin of `app/studio/candidates/brouwer_aba.json`. The candidate JSON
# stays the authored source; a test compares the two so they cannot drift.
BROUWER_ABA = SentenceSpec(
    id=BROUWER_ABA_ID,
    pattern=BROUWER_PATTERN,
    meter=BROUWER_METER,
    select=Select(length_min=BROUWER_MIN_BARS),
    span=Span(tile=3, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=BROUWER_ETUDE),
        Slot(start=1, bars=1, figure=BROUWER_NOVIEMBRE),
        Slot(start=2, bars=1, figure=BROUWER_ETUDE),
    ),
)
BROUWER_PRODUCTION_SPECS = (BROUWER_ABA,)
BROUWER_KEY = (BROUWER_PATTERN, BROUWER_METER)


def enabled() -> bool:
    """The production flag, read at call time."""
    return brouwer_production_enabled()


def ensure_registered() -> bool:
    """Register the ABA if the table does not already hold it."""
    existing = sentence_specs.SENTENCE_SPECS.get(BROUWER_KEY)
    if existing is not None:
        if existing == BROUWER_PRODUCTION_SPECS:
            return False
        raise ValueError(
            f"{BROUWER_KEY} already registers {existing!r}; "
            "the Brouwer ABA would replace it"
        )
    sentence_specs.register(
        BROUWER_PATTERN,
        BROUWER_METER,
        *BROUWER_PRODUCTION_SPECS,
        valid_figures=frozenset(BROUWER_FIGURES),
    )
    return True


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    if sentence_specs.SENTENCE_SPECS.get(BROUWER_KEY) != BROUWER_PRODUCTION_SPECS:
        return False
    del sentence_specs.SENTENCE_SPECS[BROUWER_KEY]
    return True


@contextmanager
def use_brouwer_aba(enabled: bool = True) -> Iterator[None]:
    """Pin the flag and own this module's registry entry for the context."""
    with use_brouwer_production(enabled):
        added = ensure_registered() if enabled else False
        try:
            yield
        finally:
            if added:
                unregister()


def eligible(ctx: Any) -> bool:
    """A whole 4/4 Brouwer movement with no pedal frame bar."""
    if ctx.ensemble != "brouwer" or ctx.kind != BROUWER_METER:
        return False
    if ctx.bars < BROUWER_MIN_BARS:
        return False
    return not has_pedal_bars(ctx)


def _plan(
    ctx: Any,
) -> tuple[dict[int, int], dict[int, Any]] | None:
    if not enabled() or not eligible(ctx):
        return None
    ensure_registered()
    planned = sentence_specs.plan_slots(
        BROUWER_PATTERN,
        BROUWER_METER,
        ctx.bars,
        0,
        closes=False,
        rise=0,
    )
    return bar_plan(planned, ctx.bars)


def render_sentence(ctx: Any) -> SentenceVoices | None:
    """Render the ABA for an eligible movement, or return None to fall back."""
    plan = _plan(ctx)
    if plan is None:
        return None
    figures, slot_contours = plan

    state = BrouwerFigureState.build(ctx)
    lead: list = []
    support: list = []
    low: list = []
    for bar in range(ctx.bars):
        pen = BrouwerFigurePen(
            state=state,
            bar=bar,
            phrase=phrase_at(ctx, bar),
            index=bar,
            count=ctx.bars,
            prior_lead=tuple(lead),
        )
        part_lead, part_support, part_low = render_brouwer_figure(
            pen, figures[bar]
        )
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)

    mark_trace(ctx)
    return SentenceVoices(
        lead, support, low, figures, slot_contours=slot_contours
    )
