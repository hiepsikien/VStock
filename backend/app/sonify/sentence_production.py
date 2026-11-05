"""Shared pieces for the feature-gated production sentences.

The Barrios Cathedral period proved the shape: plan one `SentenceSpec`, render
one bar at a time through the owner's existing figure table, then hand the raw
voices back to the production renderer. The Villa, Suite, and Brouwer modules
stay about their own spec and their own figures; the shared renderer runs the
same wave/dynamics/bells/transitions/scale/micro-velocity tail for them as it
does for the historical bar loop.

Nothing here reads a flag or registers a sentence. Every caller is already
inside a gated branch, and importing this module renders nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from app.sonify.model import NoteEvent

# A planned span as `plan_sentence` returns it: `(figure, bar indexes)`.
PlannedSpans = Iterable[tuple[int, tuple[int, ...]]]


@dataclass(frozen=True)
class SentenceVoices:
    """Raw bar-written voices plus the plan that produced them.

    A gated sentence returns this instead of a finished render. The shared
    renderer then applies the default figure contours here and runs the same
    post-wave tail as the historical per-bar path. `figures` is bar -> figure
    id; `contours` is bar -> extracted contour id for the figures that own one
    (today the two Villa étude figures). An empty `contours` map is the zero-diff
    path.
    """

    lead: list[NoteEvent]
    support: list[NoteEvent]
    low: list[NoteEvent]
    figures: dict[int, int]
    contours: dict[int, str] = field(default_factory=dict)


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


def _bar_events(events: Sequence[NoteEvent], bar: int) -> list[NoteEvent]:
    """The events of one bar, order preserved."""
    return [event for event in events if event.bar == bar]


def _replace_bar(
    events: Sequence[NoteEvent], bar: int, updated: Sequence[NoteEvent]
) -> list[NoteEvent]:
    """Swap one bar's events for their rewritten copy, order preserved."""
    result = list(events)
    positions = [index for index, event in enumerate(result) if event.bar == bar]
    if len(positions) != len(updated):
        raise ValueError(
            f"bar {bar} contour changed the event count "
            f"({len(positions)} -> {len(updated)})"
        )
    for index, event in zip(positions, updated):
        result[index] = event
    return result


def apply_default_contours(
    ctx: Any,
    voices: SentenceVoices,
    *,
    enabled: bool,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """Apply extracted figure contours before the volume wave.

    This mirrors the historical per-bar branches: Étude No. 1 and Étude No. 11
    rewrite the middle voice on the 4/4 grid. Other figures either have no
    extracted contour or are not used by the current gated plans. `enabled` is
    the `VSTOCK_MICRO_VELOCITY_WRITERS` gate, so the flag off path returns the
    untouched voices.
    """
    if not enabled or not voices.contours:
        return voices.lead, voices.support, voices.low

    from app.sonify.guitar_patterns import _etude11_hairpin_at
    from app.sonify.micro_velocity_writer import apply_etude1, apply_etude11

    lead = list(voices.lead)
    support = list(voices.support)
    low = list(voices.low)
    for bar, contour in sorted(voices.contours.items()):
        if ctx.kind != "4/4":
            continue
        if contour == "etude1":
            support = _replace_bar(
                support,
                bar,
                apply_etude1(_bar_events(support, bar), origin_bar=bar),
            )
        elif contour == "etude11":
            lead_at = _bar_events(lead, bar)
            support = _replace_bar(
                support,
                bar,
                apply_etude11(
                    _bar_events(support, bar),
                    origin_bar=bar,
                    hairpin_at=_etude11_hairpin_at(lead_at),
                    band_at=lambda event: ctx.band(event.bar),
                ),
            )
    return lead, support, low


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
