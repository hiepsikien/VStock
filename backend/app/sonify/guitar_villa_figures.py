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

import logging
from collections.abc import Callable

from app.sonify.chords import Chord
from app.sonify.guitar import _apex_eighths
from app.sonify.guitar_patterns import (
    _Ctx,
    _choose_bass,
    _choose_inner,
    _eighth_event,
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

logger = logging.getLogger(__name__)

VILLA_ARPEGGIO = 1
VILLA_CHORD_MELODY = 2
VILLA_ETUDE1 = 3
VILLA_ETUDE11 = 4
VILLA_CADENCE = 5

# One sustained attack at beat 0. The cadence is a chord, not an arpeggio:
# lead root, inner chord tone, bass root all ring for the whole bar.
_CADENCE_VEL = 50

VILLA_FIGURE_NAMES: dict[int, str] = {
    VILLA_ARPEGGIO: "villa_arpeggio",
    VILLA_CHORD_MELODY: "villa_chord_melody",
    VILLA_ETUDE1: "villa_etude1",
    VILLA_ETUDE11: "villa_etude11",
    VILLA_CADENCE: "villa_cadence",
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


def _nearest_chord_root(
    ctx: _Ctx,
    chord: Chord,
    start: int,
    low: int,
    high: int,
) -> int | None:
    """Chord root pitch class nearest the previous melody note.

    The previous note is clamped into `ctx.melody`; an empty melody has no
    anchor, so the cadence stays silent instead of guessing.
    """
    if not ctx.melody:
        return None
    previous = ctx.melody[min(max(0, start - 1), len(ctx.melody) - 1)]
    root_pc = chord.pitches[0] % 12
    candidates = [
        note for note in range(low, high + 1) if note % 12 == root_pc
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda note: abs(note - previous))


def is_half_cadence(ctx: _Ctx, bar: int) -> bool:
    """True when the final chord is not the movement's opening root."""
    if ctx.bars < 1:
        return False
    closing = ctx.chord(bar).pitches[0] % 12
    opening = ctx.chord(0).pitches[0] % 12
    return closing != opening


def _cadence_bar(ctx: _Ctx, bar: int, phrase: Phrase | None) -> FigureNotes:
    """One sustained tonic chord: lead root, inner tone, bass root.

    `VILLA_CADENCE` is deliberately not an arpeggio and does not use
    `_chord_grid`, so 2/4 and 4/4 each get exactly one attack at beat 0 and a
    sustain through the bar.
    """
    start = bar * ctx.epb
    chord = ctx.chord(bar)
    lead = _nearest_chord_root(
        ctx, chord, start, ctx.treble_floor, ctx.treble_top
    )
    if lead is None:
        return [], [], []
    bass = _choose_bass(
        chord, 0, None, ctx.bass_low, ctx.bass_high, ctx.semitones
    )
    support = _choose_inner(
        chord,
        lead,
        bass,
        ctx.mid_low,
        ctx.mid_high,
        ctx.semitones,
        False,
        0,
    )
    if bar == ctx.bars - 1 and is_half_cadence(ctx, bar):
        logger.warning(
            "VILLA_CADENCE half cadence at bar %s: "
            "closing root %s != opening root %s",
            bar,
            chord.name,
            ctx.chord(0).name,
        )
    high = _eighth_event(start, ctx.epb, lead, ctx.epb, 1, _CADENCE_VEL)
    mid = (
        []
        if support is None
        else _eighth_event(start, ctx.epb, support, ctx.epb, 2, _CADENCE_VEL)
    )
    low = _eighth_event(start, ctx.epb, bass, ctx.epb, 3, _CADENCE_VEL)
    return high, mid, low


VILLA_FIGURES: dict[int, VillaFigure] = {
    VILLA_ARPEGGIO: _arpeggio_bar,
    VILLA_CHORD_MELODY: _chord_melody_bar,
    VILLA_ETUDE1: _etude1_bar,
    VILLA_ETUDE11: _etude11_bar,
    VILLA_CADENCE: _cadence_bar,
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
