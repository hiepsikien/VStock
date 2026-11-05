"""Feature-gated production home for the Barrios Cathedral period.

The Studio pilot (`app.studio.barrios_preview`) proved that an authored
`SentenceSpec` can drive the real per-bar Barrios figure renderers. This module
promotes that period into the production renderer behind an explicit flag.

Flag
----
`VSTOCK_BARRIOS_PERIOD` is read at call time. Only `1`, `true`, `yes`, and `on`
(the usual case-insensitive spellings) turn it on. Missing, empty, `0`, `false`,
`no`, `off`, `rollback`, and every unknown value keep it off. The default is
therefore the old Barrios path, byte for byte.

When the flag is on, the period is registered in the production sentence
registry as `("preludio", "4/4")` with `valid_figures=BARRIOS_FIGURES`. The
registration is lazy: importing this module never mutates `SENTENCE_SPECS`, so a
process that never enables the flag cannot see the candidate. `use_barrios_period`
is the deterministic test/audition context manager; it removes exactly the entry
it added on exit.

Eligibility
-----------
The period is a 12-bar 4/4 movement: the authored tile is exact, so only a whole
movement of that length can carry it. A movement with any pedal frame bar
(warm-up, intro, outro, cool-down) is left to the existing path, and a plan with
no spans (or one that does not cover all twelve bars) also falls back. The
existing renderer remains the fallback in every one of those cases.

Render
------
`render_period` builds the same bounded context the preview does, but from the
production melody and chords. It calls `sentence_specs.plan_sentence` and then
`guitar_barrios_figures.render_barrios_figure` for each planned bar. The result
is voiced and filled on the same grids the production renderer uses, so callers
receive the same `(lead, support, low, divisions)` shape.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import replace
from typing import Any

from app.sonify import sentence_specs
from app.sonify.guitar import _PEDAL
from app.sonify.guitar_barrios_figures import (
    BARRIOS_FIGURES,
    BARRIOS_PRELUDIO,
    BARRIOS_TREMOLO,
    BarriosFigurePen,
    BarriosFigureState,
    figure_pattern,
    render_barrios_figure,
)
from app.sonify.model import NoteEvent, Phrase, Run
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

BARRIOS_PERIOD_ENV = "VSTOCK_BARRIOS_PERIOD"
BARRIOS_PERIOD_PATTERN = "preludio"
BARRIOS_PERIOD_METER = "4/4"
BARRIOS_PERIOD_BARS = 12
BARRIOS_CATHEDRAL_PERIOD_ID = "barrios_cathedral_period"

_TRUE = frozenset({"1", "true", "yes", "on"})

# The authored period. Preludio Saudade -> the tremolo apex -> the opening frame
# again. This is the code twin of `app/studio/candidates/barrios_cathedral.json`;
# the candidate module re-exports it so authoring and production cannot drift.
BARRIOS_CATHEDRAL_PERIOD = SentenceSpec(
    id=BARRIOS_CATHEDRAL_PERIOD_ID,
    pattern=BARRIOS_PERIOD_PATTERN,
    meter=BARRIOS_PERIOD_METER,
    select=Select(length_min=12, length_max=12),
    span=Span(tile=12, exact=True, remainder="exact"),
    slots=(
        Slot(start=0, bars=4, figure=BARRIOS_PRELUDIO),
        Slot(start=4, bars=4, figure=BARRIOS_TREMOLO),
        Slot(start=8, bars=4, figure=BARRIOS_PRELUDIO),
    ),
)
BARRIOS_PERIOD_SPECS = (BARRIOS_CATHEDRAL_PERIOD,)
BARRIOS_PERIOD_KEY = (BARRIOS_PERIOD_PATTERN, BARRIOS_PERIOD_METER)

_OVERRIDE: ContextVar[bool | None] = ContextVar(
    "barrios_period_enabled", default=None
)


def barrios_period_enabled() -> bool:
    """The flag, with a ContextVar override for tests and auditions."""
    override = _OVERRIDE.get()
    if override is not None:
        return override
    raw = os.environ.get(BARRIOS_PERIOD_ENV)
    if raw is None:
        return False
    return raw.strip().lower() in _TRUE


def ensure_registered() -> bool:
    """Register the period if the table does not already hold it.

    Returns True when this call added the entry. A different value at the same
    key raises, so a future production archetype cannot be shadowed silently.
    """
    existing = sentence_specs.SENTENCE_SPECS.get(BARRIOS_PERIOD_KEY)
    if existing is not None:
        if existing == BARRIOS_PERIOD_SPECS:
            return False
        raise ValueError(
            f"{BARRIOS_PERIOD_KEY} already registers {existing!r}; "
            "the Barrios period would replace it"
        )
    sentence_specs.register(
        BARRIOS_PERIOD_PATTERN,
        BARRIOS_PERIOD_METER,
        *BARRIOS_PERIOD_SPECS,
        valid_figures=frozenset(BARRIOS_FIGURES),
    )
    return True


def unregister() -> bool:
    """Remove exactly the period this module owns, leaving anything else alone."""
    if sentence_specs.SENTENCE_SPECS.get(BARRIOS_PERIOD_KEY) != BARRIOS_PERIOD_SPECS:
        return False
    del sentence_specs.SENTENCE_SPECS[BARRIOS_PERIOD_KEY]
    return True


@contextmanager
def use_barrios_period(enabled: bool = True) -> Iterator[None]:
    """Enable/disable the flag and own the registry entry for the context."""
    token = _OVERRIDE.set(bool(enabled))
    added = False
    try:
        if enabled:
            added = ensure_registered()
        yield
    finally:
        _OVERRIDE.reset(token)
        if added:
            unregister()


def _eligible(ctx: Any) -> bool:
    if ctx.ensemble != "barrios":
        return False
    if ctx.kind != BARRIOS_PERIOD_METER or ctx.bars != BARRIOS_PERIOD_BARS:
        return False
    return all(
        ctx.kind_at.get(bar, "phrase") not in _PEDAL
        for bar in range(BARRIOS_PERIOD_BARS)
    )


def _joined(start: int, pitches: list[int]) -> Phrase:
    """One phrase from an eighth run, the same shape the preview builds."""
    runs: list[Run] = []
    index = 0
    while index < len(pitches):
        nxt = index + 1
        while nxt < len(pitches) and pitches[nxt] == pitches[index]:
            nxt += 1
        runs.append(Run(start + index, nxt - index, pitches[index]))
        index = nxt
    return Phrase(start, start + len(pitches), tuple(runs), False)


def _plan(ctx: Any) -> list[tuple[int, tuple[int, ...]]] | None:
    if not _eligible(ctx):
        return None
    # The registry entry is deliberately lazy. An env-var audition never calls
    # the context manager, so this is the one place production can install it.
    ensure_registered()
    planned = sentence_specs.plan_sentence(
        BARRIOS_PERIOD_PATTERN,
        BARRIOS_PERIOD_METER,
        ctx.bars,
        0,
        closes=False,
        rise=0,
    )
    if not planned:
        return None
    covered: list[int] = []
    for _figure, bars in planned:
        covered.extend(bars)
    if sorted(covered) != list(range(BARRIOS_PERIOD_BARS)):
        return None
    return planned


def _shape(
    lead: list[NoteEvent],
    support: list[NoteEvent],
    low: list[NoteEvent],
    ctx: Any,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], int]:
    """Voicing and rest filling, matching the production renderer's tail."""
    from app.sonify.guitar_patterns import (
        _ScaleLead,
        _fill,
        _fill_voices,
        _needs_sixteenths,
        _needs_twelfths,
        _resolve,
        _resolve_voices,
    )

    bars = ctx.bars
    epb = ctx.epb
    lead = _resolve(
        [replace(event, voice=1) for event in lead if event.midi is not None],
        epb,
        1,
    )
    support = _resolve_voices(
        [replace(event, voice=2) for event in support if event.midi is not None],
        epb,
        2,
    )
    low = _resolve(
        [replace(event, voice=3) for event in low if event.midi is not None],
        epb,
        3,
    )
    events = [*lead, *support, *low]
    if _needs_twelfths(events):
        divisions = 12
    elif _needs_sixteenths(events):
        divisions = 4
    else:
        divisions = 2
    return (
        _ScaleLead(_fill(lead, bars, epb, 1)),
        _fill_voices(support, bars, epb, 2),
        _fill(low, bars, epb, 3),
        divisions,
    )


def render_period(
    ctx: Any,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], int] | None:
    """Render the period for an eligible movement, or return None to fall back."""
    planned = _plan(ctx)
    if planned is None:
        return None

    ordered = sorted(planned, key=lambda item: item[1][0])
    patterns = [figure_pattern(figure) for figure, _bars in ordered]
    slots: list[tuple[int, int, int, int]] = []
    phrases: list[Phrase] = []
    for figure, bars in ordered:
        start = bars[0]
        count = len(bars)
        slots.append((start, count, figure, len(phrases)))
        phrases.append(
            _joined(
                start * ctx.epb,
                list(ctx.melody[start * ctx.epb : (start + count) * ctx.epb]),
            )
        )

    period_ctx = replace(ctx, phrases=tuple(phrases))
    state = BarriosFigureState.build(period_ctx, patterns)
    bar_slot = {
        bar: (index, figure, start, count)
        for start, count, figure, index in slots
        for bar in range(start, start + count)
    }

    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for bar in range(ctx.bars):
        index, figure, start, count = bar_slot[bar]
        pen = BarriosFigurePen(
            state=state,
            bar=bar,
            phrase=phrases[index],
            index=bar - start,
            count=count,
        )
        part_lead, part_support, part_low = render_barrios_figure(pen, figure)
        lead.extend(part_lead)
        support.extend(part_support)
        low.extend(part_low)

    from app.sonify.guitar_patterns import _TRACE_LINE, _TRACE_PRICE_LINE

    _TRACE_LINE.set(list(ctx.melody))
    _TRACE_PRICE_LINE.set(list(ctx.melody))
    return _shape(lead, support, low, ctx)
