"""Feature-gated production home for Villa-Lobos's Mazurka-Choro.

The Studio candidate `suite_mazurka_arpeggio_aaba` is a four-bar 3/4 sentence:
two bars of the Villa roll, one bar of block chords, then the roll again. This
module promotes it from the preview-only candidate to a production pattern.

Registration
------------
The pattern id is `suite_mazurka`; its meter is `3/4`, its printed title is
`Mazurka-Choro`, and its registry level is `topic` (a dance that names itself).
The sentence is registered as `("suite_mazurka", "3/4")` with
`valid_figures=VILLA_FIGURES` only when the flag is on. Importing this module
never mutates `SENTENCE_SPECS`.

Flag
----
`VSTOCK_SUITE_MAZURKA` is read through :mod:`app.sonify.production_flags` at
call time. Missing, empty, falsy, unknown, and rollback values keep the
historical Villa path byte for byte, and selection never returns
`suite_mazurka`.

Eligibility
-----------
A Villa movement must be 3/4, at least four bars long, and free of pedal frame
bars. Selection and render share the same predicate, so a movement that the
renderer would decline can never be painted with this pattern.

Render
------
`render_sentence` plans the AABA, then calls
`guitar_villa_figures.render_villa_figure` once per bar. It returns the raw bar
voices and the plan, not a finished render: the shared renderer then runs the
same post-wave tail as the historical bar loop.
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
from app.sonify.pattern_registry import PatternMeta
from app.sonify.production_flags import (
    suite_mazurka_enabled,
    use_suite_mazurka,
)
from app.sonify.sentence_production import (
    SentenceVoices,
    bar_plan,
    has_pedal_bars,
    mark_trace,
    phrase_at,
)
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

SUITE_MAZURKA_PATTERN = "suite_mazurka"
SUITE_MAZURKA_METER = "3/4"
SUITE_MAZURKA_MIN_BARS = 4
SUITE_MAZURKA_AABA_ID = "suite_mazurka_arpeggio_aaba"
SUITE_MAZURKA_TITLE = "Mazurka-Choro"
SUITE_MAZURKA_LEVEL = "topic"
SUITE_MAZURKA_NAME_SOURCE = "dance"

# The taxonomy record the global `pattern_registry.PATTERN_META` carries. Kept
# here as well so the owner can assert its own claim without reading the table.
SUITE_MAZURKA_META = PatternMeta(
    SUITE_MAZURKA_PATTERN,
    SUITE_MAZURKA_LEVEL,
    SUITE_MAZURKA_NAME_SOURCE,
)

# The code twin of `app/studio/candidates/suite_mazurka.json`, re-keyed to the
# production pattern id. A test compares the slot geometry with the JSON.
SUITE_MAZURKA_AABA = SentenceSpec(
    id=SUITE_MAZURKA_AABA_ID,
    pattern=SUITE_MAZURKA_PATTERN,
    meter=SUITE_MAZURKA_METER,
    select=Select(length_min=SUITE_MAZURKA_MIN_BARS),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
    ),
)
SUITE_MAZURKA_SPECS = (SUITE_MAZURKA_AABA,)
SUITE_MAZURKA_KEY = (SUITE_MAZURKA_PATTERN, SUITE_MAZURKA_METER)


def enabled() -> bool:
    """The production flag, read at call time."""
    return suite_mazurka_enabled()


def ensure_registered() -> bool:
    """Register the AABA if the table does not already hold it."""
    existing = sentence_specs.SENTENCE_SPECS.get(SUITE_MAZURKA_KEY)
    if existing is not None:
        if existing == SUITE_MAZURKA_SPECS:
            return False
        raise ValueError(
            f"{SUITE_MAZURKA_KEY} already registers {existing!r}; "
            "the Suite Mazurka would replace it"
        )
    sentence_specs.register(
        SUITE_MAZURKA_PATTERN,
        SUITE_MAZURKA_METER,
        *SUITE_MAZURKA_SPECS,
        valid_figures=frozenset(VILLA_FIGURES),
    )
    return True


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    if sentence_specs.SENTENCE_SPECS.get(SUITE_MAZURKA_KEY) != SUITE_MAZURKA_SPECS:
        return False
    del sentence_specs.SENTENCE_SPECS[SUITE_MAZURKA_KEY]
    return True


@contextmanager
def use_suite_mazurka_aba(enabled: bool = True) -> Iterator[None]:
    """Pin the flag and own this module's registry entry for the context."""
    with use_suite_mazurka(enabled):
        added = ensure_registered() if enabled else False
        try:
            yield
        finally:
            if added:
                unregister()


def eligible(ctx: Any) -> bool:
    """A whole 3/4 Villa movement with no pedal frame bar."""
    if ctx.ensemble != "villa" or ctx.kind != SUITE_MAZURKA_METER:
        return False
    if ctx.bars < SUITE_MAZURKA_MIN_BARS:
        return False
    return not has_pedal_bars(ctx)


def _plan(
    ctx: Any,
) -> tuple[dict[int, int], dict[int, Any]] | None:
    if not enabled() or not eligible(ctx):
        return None
    # The registry entry is deliberately lazy. An env-var audition never calls
    # the context manager, so this is the one place production installs it.
    ensure_registered()
    planned = sentence_specs.plan_slots(
        SUITE_MAZURKA_PATTERN,
        SUITE_MAZURKA_METER,
        ctx.bars,
        0,
        closes=False,
        rise=0,
    )
    return bar_plan(planned, ctx.bars)


def selectable(ctx: Any) -> bool:
    """Whether selection may return `suite_mazurka` for this movement.

    This is the same predicate the renderer uses, plus the plan check. A caller
    that only reads the chooser can never paint a pattern the render gate would
    then decline.
    """
    if not enabled():
        return False
    return _plan(ctx) is not None


def render_sentence(ctx: Any) -> SentenceVoices | None:
    """Render the AABA for an eligible movement, or return None to fall back."""
    plan = _plan(ctx)
    if plan is None:
        return None
    figures, slot_contours = plan

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
    return SentenceVoices(
        lead, support, low, figures, contours, slot_contours=slot_contours
    )
