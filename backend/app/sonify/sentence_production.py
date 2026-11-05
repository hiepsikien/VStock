"""Shared tail for the feature-gated production sentences.

The Barrios Cathedral period proved the shape: plan one `SentenceSpec`, render
one bar at a time through the owner's existing figure table, then voice and
fill the result on the same grids the production renderer uses. This module
holds the small pieces that do not depend on the owner, so the Villa, Suite,
and Brouwer modules can stay about their own spec and their own figures.

Nothing here reads a flag or registers a sentence. Every caller is already
inside a gated branch, and importing this module renders nothing.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from app.sonify.model import NoteEvent

# A planned span as `plan_sentence` returns it: `(figure, bar indexes)`.
PlannedSpans = Iterable[tuple[int, tuple[int, ...]]]


def bar_figures(planned: PlannedSpans | None, bars: int) -> dict[int, int] | None:
    """One figure per bar, or `None` when the plan does not cover the movement.

    A partial plan must fall back instead of leaving bars to a texture the
    production loop no longer knows how to render.
    """
    if not planned:
        return None
    found: dict[int, int] = {}
    for figure, span_bars in planned:
        for bar in span_bars:
            if 0 <= bar < bars:
                found[bar] = figure
    if sorted(found) != list(range(bars)):
        return None
    return found


def shape_voices(
    ctx: Any,
    lead: list[NoteEvent],
    support: list[NoteEvent],
    low: list[NoteEvent],
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent], int]:
    """Resolve and fill the three voices, matching `render_patterned_voices`.

    This is the same tail the Barrios period uses. The bar writers already own
    pitch and velocity; this pass only resolves overlaps, stamps voices, fills
    rests, and picks the engraving division.
    """
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


def mark_trace(ctx: Any) -> None:
    """Publish the melody the gated sentence actually sang."""
    from app.sonify.guitar_patterns import _TRACE_LINE, _TRACE_PRICE_LINE

    _TRACE_LINE.set(list(ctx.melody))
    _TRACE_PRICE_LINE.set(list(ctx.melody))


def phrase_at(ctx: Any, bar: int):
    """The production phrase holding this bar, or `None` for a bare fixture."""
    from app.sonify.guitar_patterns import _phrase_at

    return _phrase_at(ctx, bar * ctx.epb)


def has_pedal_bars(ctx: Any) -> bool:
    """True when any bar belongs to a pedal frame."""
    from app.sonify.guitar import _PEDAL

    return any(
        ctx.kind_at.get(bar, "phrase") in _PEDAL for bar in range(ctx.bars)
    )
