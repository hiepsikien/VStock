"""Barrios figure registry: figure id -> one bar of an existing texture.

Barrios has no `_FIGURES` table today. `render_patterned_voices` dispatches
`preludio`, `tremolo`, `andante`, and the dances inline, and the tremolo grid
is a whole-span function in `guitar`. This module adapts those renderers to the
same pen shape Torroba uses (`render_torroba_figure`), so a `SentenceSpec` can
name a Barrios texture without changing the renderer or the production
dispatch.

Preview-only
------------
`guitar_patterns` does not import this module. A period is authored and
previewed through `app.studio.barrios_preview`; production planning still
selects Barrios textures from mood and the meter row. The figure ids are
authoring ids, not a second production table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sonify.guitar import _apex_eighths, _tremolo
from app.sonify.guitar_patterns import (
    _Ctx,
    _bar_pattern,
    _render_block_bar,
    _shift_velocity,
    _sustain,
    _tremolo_shift,
)
from app.sonify.guitar_barrios import (
    _andante_grid,
    _preludio_bass,
    _render_catedral_preludio_bar,
    _render_choro_bar,
    _render_hemiola_bar,
    _render_polca_bar,
    _render_vals_bar,
)
from app.sonify.model import NoteEvent, Phrase

BARRIOS_PRELUDIO = 1
BARRIOS_TREMOLO = 2
BARRIOS_ANDANTE = 3
BARRIOS_CHORO = 4
BARRIOS_POLCA = 5
BARRIOS_HEMIOLA = 6
BARRIOS_VALS = 7

# The row label each figure sings. A period's `row` is the pattern of the
# figure placed on each bar, not the spec's `pattern` field, because a Barrios
# period reprises the opening texture around a guest (La Catedral's frame).
BARRIOS_FIGURE_PATTERNS: dict[int, str] = {
    BARRIOS_PRELUDIO: "preludio",
    BARRIOS_TREMOLO: "tremolo",
    BARRIOS_ANDANTE: "andante",
    BARRIOS_CHORO: "choro",
    BARRIOS_POLCA: "polca",
    BARRIOS_HEMIOLA: "hemiola",
    BARRIOS_VALS: "vals",
}

# Preview dynamic marking per texture. It only drives velocity, never pitch or
# selection, so a deterministic fixture can pin it.
BARRIOS_FIGURE_BANDS: dict[int, str] = {
    BARRIOS_PRELUDIO: "mp",
    BARRIOS_TREMOLO: "f",
    BARRIOS_ANDANTE: "mp",
    BARRIOS_CHORO: "mf",
    BARRIOS_POLCA: "mf",
    BARRIOS_HEMIOLA: "mf",
    BARRIOS_VALS: "mf",
}

BARRIOS_PATTERNS = frozenset(BARRIOS_FIGURE_PATTERNS.values())


@dataclass
class BarriosFigureState:
    """Per-render state shared by every bar of one period.

    `tremolo` is the only whole-span result. `guitar._tremolo` writes the sung
    line, fill, and thumb for all bars at once, so the first tremolo bar
    computes it and later bars slice their own events.
    """

    ctx: _Ctx
    patterns: list[str]
    apex: set[int]
    tremolo: tuple[
        tuple[NoteEvent, ...], tuple[NoteEvent, ...], tuple[NoteEvent, ...]
    ] | None = field(default=None, repr=False)

    @classmethod
    def build(cls, ctx: _Ctx, patterns: list[str]) -> "BarriosFigureState":
        return cls(ctx=ctx, patterns=list(patterns), apex=_apex_eighths(ctx.phrases))


@dataclass(frozen=True)
class BarriosFigurePen:
    """One bar to realize. Mirrors Torroba's `_Pen` fields a figure may read."""

    state: BarriosFigureState
    bar: int
    phrase: Phrase | None = None
    index: int = 0
    count: int = 1

    @property
    def ctx(self) -> _Ctx:
        return self.state.ctx

    @property
    def patterns(self) -> list[str]:
        return self.state.patterns

    @property
    def apex(self) -> set[int]:
        return self.state.apex


def _preludio(pen: BarriosFigurePen) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """The authentic Cathedral preludio bar, plus its ringing pedal.

    Production appends `_preludio_bass` once for the whole movement. Here the
    realizer is bar-local, so it slices the same result; a two-bar pedal still
    splits into a tie segment per bar and the pair keeps one attack.
    """
    lead, support = _render_catedral_preludio_bar(
        pen.ctx, pen.bar, pen.patterns, pen.apex, pen.phrase
    )
    low = [event for event in _preludio_bass(pen.ctx, pen.patterns) if event.bar == pen.bar]
    return lead, support, low


def _tremolo_bar(
    pen: BarriosFigurePen,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """One bar of the `guitar._tremolo` grid, shifted by its region arch."""
    state = pen.state
    ctx = state.ctx
    if state.tremolo is None:
        state.tremolo = _tremolo(
            ctx.melody,
            ctx.chord_at,
            {bar: "phrase" for bar in range(ctx.bars)},
            ctx.bars,
            ctx.bpm,
            ctx.bass_low,
            ctx.bass_high,
            ctx.mid_low,
            ctx.mid_high,
            ctx.phrases,
        )
    lead, inner, low = state.tremolo
    bars = {
        bar
        for bar in range(ctx.bars)
        if _bar_pattern(ctx, bar, state.patterns) == "tremolo"
    }
    bar_low = [event for event in low if event.bar == pen.bar and event.midi is not None]
    shift = _tremolo_shift(ctx, bars, pen.bar, bar_low)
    return (
        _shift_velocity(
            [event for event in lead if event.bar == pen.bar and event.midi is not None],
            shift,
        ),
        _shift_velocity(
            [event for event in inner if event.bar == pen.bar and event.midi is not None],
            shift,
        ),
        _shift_velocity(bar_low, shift),
    )


def _andante(
    pen: BarriosFigurePen,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """The chorale bar: a sustained canto over block chords."""
    ctx = pen.ctx
    points, spans = _andante_grid(ctx, pen.bar, pen.phrase)
    support, low = _render_block_bar(
        ctx, pen.bar, points, spans, inner="chord", phrase=pen.phrase
    )
    cuts = {pen.bar * ctx.epb + point for point in points}
    lead = _sustain(
        ctx.melody,
        pen.bar * ctx.epb,
        (pen.bar + 1) * ctx.epb,
        ctx.epb,
        pen.apex,
        cuts,
        pen.phrase,
    )
    return lead, support, low


def _choro(pen: BarriosFigurePen) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _render_choro_bar(pen.ctx, pen.bar, pen.patterns, pen.apex)


def _polca(pen: BarriosFigurePen) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _render_polca_bar(pen.ctx, pen.bar, pen.patterns, pen.apex)


def _hemiola(pen: BarriosFigurePen) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _render_hemiola_bar(pen.ctx, pen.bar, pen.patterns, pen.apex)


def _vals(pen: BarriosFigurePen) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    return _render_vals_bar(pen.ctx, pen.bar, pen.patterns, pen.apex)


BARRIOS_FIGURES = {
    BARRIOS_PRELUDIO: _preludio,
    BARRIOS_TREMOLO: _tremolo_bar,
    BARRIOS_ANDANTE: _andante,
    BARRIOS_CHORO: _choro,
    BARRIOS_POLCA: _polca,
    BARRIOS_HEMIOLA: _hemiola,
    BARRIOS_VALS: _vals,
}


def figure_pattern(figure: int) -> str:
    """The row label for one authored figure id."""
    return BARRIOS_FIGURE_PATTERNS[figure]


def figure_band(figure: int) -> str:
    """The preview dynamic marking for one authored figure id."""
    return BARRIOS_FIGURE_BANDS[figure]


def render_barrios_figure(
    pen: BarriosFigurePen, figure: int
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """One bar of a Barrios texture, through the existing renderer."""
    return BARRIOS_FIGURES[figure](pen)
