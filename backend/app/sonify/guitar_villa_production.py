"""Feature-gated production home for the Villa A-B-A arpeggio sentence.

The Studio candidate `villa_arpeggio_aba` is a three-bar sentence: one
`villa_pattern` roll, one `chord_melody` block bar, then the roll again. This
module promotes that sentence into the production renderer behind an explicit
flag.

Flag
----
`VSTOCK_VILLA_PRODUCTION` is read through
:mod:`app.sonify.production_flags` at call time. Missing, empty, falsy, unknown,
and rollback values keep the historical Villa path byte for byte.

When the flag is on, the sentence is registered in the production registry as
`("villa_pattern", "4/4")` with `valid_figures=VILLA_FIGURES`. The registration
is lazy: importing this module never mutates `SENTENCE_SPECS`. `use_villa_aba`
pins the flag and removes exactly the entry it added.

Eligibility
-----------
A Villa movement must be 4/4, at least three bars long, and free of pedal frame
bars. Every other movement, and every flag-off render, falls back to
`_render_villa_bar` through the existing loop.

Render
------
`render_sentence` plans the candidate, then calls
`guitar_villa_figures.render_villa_figure` once per bar. It returns the raw
bar voices and the plan, not a finished render: the shared renderer then runs
the same wave/dynamics/bells/transitions/scale/micro-velocity tail as the
historical bar loop.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.sonify import sentence_specs
from app.sonify.guitar_villa_figures import (
    FIGURE_CONTOURS,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_FIGURES,
    render_villa_figure,
)
from app.sonify.production_flags import (
    use_villa_production,
    villa_production_enabled,
)
from app.sonify.sentence_production import (
    SentenceVoices,
    bar_figures,
    has_pedal_bars,
    mark_trace,
    phrase_at,
)
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

VILLA_PATTERN = "villa_pattern"
VILLA_METER = "4/4"
VILLA_MIN_BARS = 3
VILLA_ABA_ID = "villa_arpeggio_aba"

# The code twin of `app/studio/candidates/villa_arpeggio.json`. The candidate
# JSON stays the authored source; a test compares the two so they cannot drift.
VILLA_ABA = SentenceSpec(
    id=VILLA_ABA_ID,
    pattern=VILLA_PATTERN,
    meter=VILLA_METER,
    select=Select(length_min=VILLA_MIN_BARS),
    span=Span(tile=3, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=2, bars=1, figure=VILLA_ARPEGGIO),
    ),
)
VILLA_PRODUCTION_SPECS = (VILLA_ABA,)
VILLA_KEY = (VILLA_PATTERN, VILLA_METER)


def enabled() -> bool:
    """The production flag, read at call time."""
    return villa_production_enabled()


def ensure_registered() -> bool:
    """Register the ABA if the table does not already hold it.

    Returns True when this call added the entry. A different value at the same
    key raises, so a future production archetype cannot be shadowed silently.
    """
    existing = sentence_specs.SENTENCE_SPECS.get(VILLA_KEY)
    if existing is not None:
        if existing == VILLA_PRODUCTION_SPECS:
            return False
        raise ValueError(
            f"{VILLA_KEY} already registers {existing!r}; "
            "the Villa ABA would replace it"
        )
    sentence_specs.register(
        VILLA_PATTERN,
        VILLA_METER,
        *VILLA_PRODUCTION_SPECS,
        valid_figures=frozenset(VILLA_FIGURES),
    )
    return True


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    if sentence_specs.SENTENCE_SPECS.get(VILLA_KEY) != VILLA_PRODUCTION_SPECS:
        return False
    del sentence_specs.SENTENCE_SPECS[VILLA_KEY]
    return True


@contextmanager
def use_villa_aba(enabled: bool = True) -> Iterator[None]:
    """Pin the flag and own this module's registry entry for the context."""
    with use_villa_production(enabled):
        added = ensure_registered() if enabled else False
        try:
            yield
        finally:
            if added:
                unregister()


def eligible(ctx: Any) -> bool:
    """A whole 4/4 Villa movement with no pedal frame bar."""
    if ctx.ensemble != "villa" or ctx.kind != VILLA_METER:
        return False
    if ctx.bars < VILLA_MIN_BARS:
        return False
    return not has_pedal_bars(ctx)


def _plan(ctx: Any) -> dict[int, int] | None:
    if not enabled() or not eligible(ctx):
        return None
    # The registry entry is deliberately lazy. An env-var audition never calls
    # the context manager, so this is the one place production installs it.
    ensure_registered()
    planned = sentence_specs.plan_sentence(
        VILLA_PATTERN,
        VILLA_METER,
        ctx.bars,
        0,
        closes=False,
        rise=0,
    )
    return bar_figures(planned, ctx.bars)


def render_sentence(ctx: Any) -> SentenceVoices | None:
    """Render the ABA for an eligible movement, or return None to fall back."""
    figures = _plan(ctx)
    if figures is None:
        return None

    lead: list = []
    support: list = []
    low: list = []
    for bar in range(ctx.bars):
        part_lead, part_support, part_low = render_villa_figure(
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
    return SentenceVoices(lead, support, low, figures, contours)
