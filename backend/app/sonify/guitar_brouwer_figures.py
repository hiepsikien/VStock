"""Brouwer bar-level figure registry for the Studio sentence pilot.

This is an adapter table, not a new renderer. Each entry wraps a bar writer
that already exists in `guitar_brouwer.py` and returns the same
``(lead, support, low)`` shape the Villa and Barrios figure tables return, so a
`SentenceSpec` can ask for "one bar of figure N" without knowing which Brouwer
texture it is.

The lead is built exactly the way the production `render_patterned_voices`
branches build it: `noviembre` and `brouwer_etude` sustain the canto, `elogio`
lifts the Bartók slap, and `sarabande` splices its modal swarm into the canto.
The bar writers themselves are unchanged.

Preview-only
------------
`guitar_patterns` does not import this module. A sentence is authored and
previewed through `app.studio.brouwer_preview`; production planning still
selects Brouwer textures from mood and the phrase ladder. The figure ids are
authoring ids, not a second production table.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.sonify.guitar import _apex_eighths
from app.sonify.guitar_brouwer import (
    _render_elogio_bar,
    _render_etude_bar,
    _render_noviembre_bar,
    _render_sarabande_bar,
)
from app.sonify.guitar_patterns import (
    _Ctx,
    _punch,
    _splice,
    _start16,
    _sustain,
)
from app.sonify.model import NoteEvent, Phrase

BROUWER_ETUDE = 1
BROUWER_NOVIEMBRE = 2
BROUWER_ELOGIO = 3
BROUWER_SARABANDE = 4

# The row label each figure sings. These are the production pattern names, so
# a preview row can be compared with a planner row without a translation table.
BROUWER_FIGURE_NAMES: dict[int, str] = {
    BROUWER_ETUDE: "brouwer_etude",
    BROUWER_NOVIEMBRE: "noviembre",
    BROUWER_ELOGIO: "elogio_pizz",
    BROUWER_SARABANDE: "sarabande",
}

BROUWER_PATTERNS = frozenset(BROUWER_FIGURE_NAMES.values())

FigureNotes = tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]


@dataclass
class BrouwerFigureState:
    """Per-render state shared by every bar of one sentence."""

    ctx: _Ctx
    apex: set[int] = field(default_factory=set)

    @classmethod
    def build(cls, ctx: _Ctx) -> "BrouwerFigureState":
        return cls(ctx=ctx, apex=_apex_eighths(ctx.phrases))


@dataclass(frozen=True)
class BrouwerFigurePen:
    """One bar to realize, with the lead already sounding before it.

    `prior_lead` is the canto collected from earlier bars. The sarabande writer
    reads it to open a swarm hairpin from the line that is already sounding;
    the other textures ignore it.
    """

    state: BrouwerFigureState
    bar: int
    phrase: Phrase | None = None
    index: int = 0
    count: int = 1
    prior_lead: tuple[NoteEvent, ...] = ()

    @property
    def ctx(self) -> _Ctx:
        return self.state.ctx

    @property
    def apex(self) -> set[int]:
        return self.state.apex


def _canto(pen: BrouwerFigurePen) -> list[NoteEvent]:
    """The sustained sung line the production branches add for this bar."""
    ctx = pen.ctx
    return _sustain(
        ctx.melody,
        pen.bar * ctx.epb,
        (pen.bar + 1) * ctx.epb,
        ctx.epb,
        pen.apex,
        phrase=pen.phrase,
    )


def _etude(pen: BrouwerFigurePen) -> FigureNotes:
    """The Afro-Cuban tumbao plus its sustained canto."""
    support, low = _render_etude_bar(pen.ctx, pen.bar)
    return _canto(pen), support, low


def _noviembre(pen: BrouwerFigurePen) -> FigureNotes:
    """The ballad pulse plus its sustained canto."""
    support, low = _render_noviembre_bar(pen.ctx, pen.bar)
    return _canto(pen), support, low


def _elogio(pen: BrouwerFigurePen) -> FigureNotes:
    """The staccato ostinato, with the Bartók slap cut and punched in the lead."""
    ctx = pen.ctx
    support, low, slap = _render_elogio_bar(ctx, pen.bar)
    cuts = {slap, slap + 1} if slap is not None else None
    lead = _sustain(
        ctx.melody,
        pen.bar * ctx.epb,
        (pen.bar + 1) * ctx.epb,
        ctx.epb,
        pen.apex,
        cuts,
        pen.phrase,
    )
    if slap is not None:
        lead = _punch(lead, slap, ctx.epb, staccato=True, amount=12)
    return lead, support, low


def _sarabande(pen: BrouwerFigurePen) -> FigureNotes:
    """The heavy chord plus the modal swarm spliced into the canto."""
    ctx = pen.ctx
    support, low, accent_at, figure = _render_sarabande_bar(
        ctx, pen.bar, pen.phrase, list(pen.prior_lead)
    )
    cuts = {pen.bar * ctx.epb + accent_at}
    if figure:
        cuts.add(_start16(figure[0], ctx.epb) // 2)
    lead = _sustain(
        ctx.melody,
        pen.bar * ctx.epb,
        (pen.bar + 1) * ctx.epb,
        ctx.epb,
        pen.apex,
        cuts,
        pen.phrase,
    )
    if figure:
        lead = _splice(
            lead,
            _start16(figure[0], ctx.epb),
            (pen.bar + 1) * ctx.epb * 2,
            figure,
            ctx.epb,
        )
    accent_eighth = pen.bar * ctx.epb + accent_at
    # A swarm attack on the accent is a hairpin step; only a held accent punches.
    if not figure or _start16(figure[0], ctx.epb) > accent_eighth * 2:
        lead = _punch(lead, accent_eighth, ctx.epb, amount=8)
    return lead, support, low


BROUWER_FIGURES = {
    BROUWER_ETUDE: _etude,
    BROUWER_NOVIEMBRE: _noviembre,
    BROUWER_ELOGIO: _elogio,
    BROUWER_SARABANDE: _sarabande,
}


def figure_pattern(figure: int) -> str:
    """The row label for one authored figure id."""
    return BROUWER_FIGURE_NAMES[figure]


def figure_id(pattern: str) -> int:
    """The authored figure id for a production pattern name."""
    for figure, name in BROUWER_FIGURE_NAMES.items():
        if name == pattern:
            return figure
    raise KeyError(f"unknown Brouwer figure name {pattern!r}")


def render_brouwer_figure(pen: BrouwerFigurePen, figure: int) -> FigureNotes:
    """One bar of a Brouwer texture, through the existing bar writer."""
    return BROUWER_FIGURES[figure](pen)
