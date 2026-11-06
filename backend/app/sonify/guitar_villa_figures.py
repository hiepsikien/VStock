"""Villa bar-level figure registry for the sentence pilot.

This is an adapter table, not a new renderer. Each entry wraps a bar renderer
that already exists in `guitar_villa.py` (or the `chord_melody` branch of
`guitar_patterns.render_patterned_voices`) and returns the same
``(lead, support, low)`` shape the Torroba figures return, so a sentence can
ask for "one bar of figure N" without knowing which Villa texture it is.

Nothing here registers a sentence and no production module imports this file.
`guitar_patterns` still chooses `villa_pattern`, `chord_melody`, `etude1`, and
`etude11` per phrase; this table only gives the Studio pilot a figure id for
the same bar writers.

`_render_villa_bar` returns support/bass and leaves the sung line to the caller,
which is exactly what the production `villa_pattern` branch does. The adapter
therefore adds the sustained melody with `_sustain`, matching that branch.
`chord_melody` is the `_chord_grid` + `_render_block_bar(inner="color")` pair
from the production branch, again with the sustained lead.
"""

from __future__ import annotations

from collections.abc import Callable

from app.sonify.guitar import _apex_eighths
from app.sonify.guitar_patterns import (
    _Ctx,
    _render_block_bar,
    _sustain,
)
from app.sonify.guitar_villa import (
    _chord_grid,
    _render_etude1_bar,
    _render_etude11_bar,
    _render_villa_bar,
)
from app.sonify.model import NoteEvent, Phrase

VILLA_ARPEGGIO = 1
VILLA_CHORD_MELODY = 2
VILLA_ETUDE1 = 3
VILLA_ETUDE11 = 4

VILLA_FIGURE_NAMES: dict[int, str] = {
    VILLA_ARPEGGIO: "villa_arpeggio",
    VILLA_CHORD_MELODY: "villa_chord_melody",
    VILLA_ETUDE1: "villa_etude1",
    VILLA_ETUDE11: "villa_etude11",
}

# Default extracted contour per figure. The arpeggio and chord_melody writers
# still own their velocities; only the two étude figures have a contour that
# the micro-velocity writer can reproduce. A figure absent here has no default.
FIGURE_CONTOURS: dict[int, str] = {
    VILLA_ETUDE1: "etude1",
    VILLA_ETUDE11: "etude11",
}

FigureNotes = tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]
VillaFigure = Callable[[_Ctx, int, Phrase | None], FigureNotes]


def _arpeggio_bar(ctx: _Ctx, bar: int, phrase: Phrase | None) -> FigureNotes:
    """One `villa_pattern` bar: thumb on the strong beats, i/m roll between.

    The sentence pilot has no next-bar context, so the approach tone stays off.
    """
    support, low = _render_villa_bar(ctx, bar, False)
    lead = _sustain(
        ctx.melody,
        bar * ctx.epb,
        (bar + 1) * ctx.epb,
        ctx.epb,
        _apex_eighths(ctx.phrases),
        phrase=phrase,
    )
    return lead, support, low


def _chord_melody_bar(ctx: _Ctx, bar: int, phrase: Phrase | None) -> FigureNotes:
    """One `chord_melody` bar: the block grid plus its sustained sung line."""
    points, spans = _chord_grid(ctx, bar, phrase)
    support, low = _render_block_bar(
        ctx, bar, points, spans, inner="color", phrase=phrase
    )
    lead = _sustain(
        ctx.melody,
        bar * ctx.epb,
        (bar + 1) * ctx.epb,
        ctx.epb,
        _apex_eighths(ctx.phrases),
        {bar * ctx.epb + point for point in points},
        phrase,
    )
    return lead, support, low


def _etude1_bar(ctx: _Ctx, bar: int, phrase: Phrase | None) -> FigureNotes:
    """One Étude No. 1 bar. A sentence bar never breathes the last beat away."""
    return _render_etude1_bar(ctx, bar, phrase, False)


def _etude11_bar(ctx: _Ctx, bar: int, phrase: Phrase | None) -> FigureNotes:
    """One Étude No. 11 bar, same no-breathe rule as figure 3."""
    return _render_etude11_bar(ctx, bar, phrase, False)


VILLA_FIGURES: dict[int, VillaFigure] = {
    VILLA_ARPEGGIO: _arpeggio_bar,
    VILLA_CHORD_MELODY: _chord_melody_bar,
    VILLA_ETUDE1: _etude1_bar,
    VILLA_ETUDE11: _etude11_bar,
}


def render_villa_figure(
    ctx: _Ctx,
    bar: int,
    phrase: Phrase | None,
    figure: int,
) -> FigureNotes:
    """One bar of a Villa figure. Unknown ids raise instead of rendering silence."""
    try:
        render = VILLA_FIGURES[figure]
    except KeyError:
        raise KeyError(f"unknown Villa figure {figure!r}") from None
    return render(ctx, bar, phrase)
