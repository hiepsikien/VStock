"""Render a Studio figure arrangement through the existing guitar renderer.

A :class:`StudioPiece` is the renderer-facing half of the Studio render plan
(``docs/studio-render-piece-plan.md`` §6). It names one pattern/meter, the
authored texture cells those figures resolve to, and one ``ArrangementBar``
per absolute bar of the piece. The renderer only needs to know which cell bar
to read at each target bar; the cell itself already owns pitches, voices and
notation.

The module is deliberately narrow:

* :class:`StudioPiece` is frozen data. Importing it reads no registry and
  mutates no render state.
* :func:`render_studio_arrangement` loops the arrangement by absolute bar and
  concatenates the ``(lead, support, low)`` voices returned by
  :func:`app.sonify.texture_figure.render_texture_bar`.
* ``figure`` arrangement entries are accepted by the schema so Phase B can add
  a close/cadence figure without migrating stored pieces, but Phase A has no
  figure renderer and raises :class:`NotImplementedError`.

No global ``TEXTURE_CELLS`` lookup happens here: the caller supplies the cell
mapping on the piece, so two arrangements cannot collide through a shared
registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal, NamedTuple

from app.sonify.texture_figure import render_texture_bar
from app.studio.texture_spec import TextureSpec

__all__ = [
    "ARRANGEMENT_KINDS",
    "ArrangementBar",
    "StudioPiece",
    "StudioProductionOptions",
    "render_studio_arrangement",
]

#: Kinds an arrangement entry may name. Phase A renders ``cell`` only.
ARRANGEMENT_KINDS = ("cell", "figure", "compressed", "cadence")

ArrangementKind = Literal["cell", "figure", "compressed", "cadence"]


class ArrangementBar(NamedTuple):
    """One absolute bar of a Studio arrangement.

    ``kind`` selects the source namespace:

    * ``"cell"`` reads ``source_id`` from :attr:`StudioPiece.cells` and renders
      ``source_bar`` (the 0-based bar inside that cell).
    * ``"figure"`` is reserved for a future cadence renderer. ``source_id`` is
      a figure id and ``source_bar`` is the figure-local bar.
    * ``"compressed"`` mirrors the production one-bar frame: the first half of
      cell bar ``source_bar`` plus the first half of ``source_bar + 1`` shifted
      into the second half of the target bar.
    * ``"cadence"`` renders the built-in ``VILLA_CADENCE`` figure for that bar;
      ``source_id`` is only a label.

    It is a real tuple, so a stored plan may write
    ``("cell", cell_id, cell_bar)`` (or ``("figure", figure_id, bar)``)
    directly and :class:`StudioPiece` normalizes it to this type. The shorter
    ``(cell_id, cell_bar)`` form from the original sketch is accepted too.
    """

    kind: ArrangementKind
    source_id: str
    source_bar: int

    @classmethod
    def cell(cls, cell_id: str, cell_bar: int) -> "ArrangementBar":
        return cls("cell", cell_id, cell_bar)

    @classmethod
    def figure(cls, figure_id: str, bar: int) -> "ArrangementBar":
        return cls("figure", figure_id, bar)

    @property
    def cell_id(self) -> str:
        return self.source_id

    @property
    def cell_bar(self) -> int:
        return self.source_bar

    @property
    def figure_id(self) -> str:
        return self.source_id

    @property
    def bar(self) -> int:
        return self.source_bar


def _coerce_arrangement_bar(entry: Any, index: int) -> ArrangementBar:
    """Normalize one arrangement entry, keeping bad data visible in ``validate``."""
    if isinstance(entry, ArrangementBar):
        return entry
    if isinstance(entry, (tuple, list)) and len(entry) == 3:
        kind, source_id, source_bar = entry
        return ArrangementBar(kind, source_id, source_bar)  # type: ignore[arg-type]
    if isinstance(entry, (tuple, list)) and len(entry) == 2:
        # The original §6.1 sketch wrote one (cell_id, cell_bar) pair per bar.
        cell_id, cell_bar = entry
        return ArrangementBar.cell(cell_id, cell_bar)
    raise TypeError(
        "arrangement entries must be ArrangementBar, "
        "(kind, source_id, source_bar), or (cell_id, cell_bar); "
        f"got {entry!r} at index {index}"
    )


@dataclass(frozen=True)
class StudioProductionOptions:
    """Optional production passes for a StudioPiece.

    All default off: the authored cell owns every note. Turning one on asks
    the shared renderer to run the same production pass it would run for a
    historical pattern. Some passes may rewrite authored notes; the UI labels
    them as production extras.
    """

    preludio_bass: bool = False
    campanella: bool = False
    bells: bool = False
    fanfares: bool = False
    transitions: bool = False
    caesuras: bool = False
    rest_fill: bool = False
    # "off", "safe" (fill lead rests), or "pipeline" (original scale engine;
    # can overwrite authored lead eighths and is experimental).
    scales: str = "off"


@dataclass(frozen=True)
class StudioPiece:
    """A complete Figure Studio render plan for the existing guitar renderer.

    ``arrangement`` is one entry per absolute bar. ``cells`` holds only
    ``TextureSpec`` values; a figure id never lives in the cell mapping
    (``docs/studio-render-piece-plan.md`` W7).
    """

    pattern: str
    meter: str
    cells: Mapping[str, TextureSpec]
    arrangement: tuple[ArrangementBar, ...] = field(default_factory=tuple)
    production: StudioProductionOptions = field(
        default_factory=StudioProductionOptions
    )
    # "off", "auto", "force": pattern-layer neighbor variation for the lead.
    variation: str = "off"
    # Studio lead sits slightly lower than the default guitar treble window.
    lead_shift: int = -2

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", dict(self.cells))
        object.__setattr__(
            self,
            "arrangement",
            tuple(
                _coerce_arrangement_bar(entry, index)
                for index, entry in enumerate(self.arrangement)
            ),
        )
        if not isinstance(self.production, StudioProductionOptions):
            object.__setattr__(self, "production", StudioProductionOptions())
        if self.variation not in ("off", "auto", "force"):
            object.__setattr__(self, "variation", "off")
        if (
            isinstance(self.lead_shift, bool)
            or not isinstance(self.lead_shift, int)
            or not -12 <= self.lead_shift <= 12
        ):
            object.__setattr__(self, "lead_shift", 0)

    def validate(self) -> tuple[str, ...]:
        """Return every structural problem. An empty tuple means the piece is renderable."""
        errors: list[str] = []
        if not isinstance(self.pattern, str) or not self.pattern.strip():
            errors.append("pattern must be a non-empty string")
        if not isinstance(self.meter, str) or not self.meter.strip():
            errors.append("meter must be a non-empty string")
        if not self.arrangement:
            errors.append("arrangement must contain at least one bar")
        for index, entry in enumerate(self.arrangement):
            if entry.kind not in ARRANGEMENT_KINDS:
                errors.append(
                    f"arrangement[{index}].kind must be one of "
                    f"{ARRANGEMENT_KINDS}, got {entry.kind!r}"
                )
                continue
            if not isinstance(entry.source_id, str) or not entry.source_id:
                errors.append(
                    f"arrangement[{index}].source_id must be a non-empty string"
                )
            if (
                not isinstance(entry.source_bar, int)
                or isinstance(entry.source_bar, bool)
                or entry.source_bar < 0
            ):
                errors.append(
                    f"arrangement[{index}].source_bar must be an integer >= 0"
                )
            if entry.kind == "cell" and entry.source_id not in self.cells:
                errors.append(
                    f"arrangement[{index}] names unknown cell {entry.source_id!r}"
                )
            if entry.kind == "cadence":
                continue
            if entry.kind == "compressed":
                texture = self.cells.get(entry.source_id)
                if texture is None:
                    errors.append(
                        f"arrangement[{index}] names unknown cell {entry.source_id!r}"
                    )
                else:
                    authored_bars = {
                        event.bar for event in texture.authored
                    }
                    if entry.source_bar not in authored_bars or (
                        entry.source_bar + 1
                    ) not in authored_bars:
                        errors.append(
                            f"arrangement[{index}] compressed cell "
                            f"{entry.source_id!r} needs authored bars "
                            f"{entry.source_bar} and {entry.source_bar + 1}"
                        )
        return tuple(errors)

    def __repr__(self) -> str:  # keep a huge cell body out of failure messages
        return (
            f"StudioPiece(pattern={self.pattern!r}, meter={self.meter!r}, "
            f"cells={list(self.cells)!r}, arrangement={self.arrangement!r})"
        )


def _compressed_voices(
    texture: TextureSpec,
    ctx: Any,
    target_bar: int,
    first_bar: int,
) -> tuple[list, list, list]:
    """Mirror guitar_frame._compressed: first half of bar N, first half of N+1."""
    bar_beats = float(getattr(ctx, "bar_beats", ctx.epb / 2))
    cut = bar_beats / 2.0
    # The second half is placed at ``cut`` but must read the melody at that
    # same offset. Without this, both halves resolve the opening melody.
    cut_eighths = int(round(cut * 2))
    first = render_texture_bar(
        texture,
        ctx,
        target_bar,
        cell_bar=first_bar,
        max_beat=cut,
        clip_beats=cut,
    )
    second = render_texture_bar(
        texture,
        ctx,
        target_bar,
        cell_bar=first_bar + 1,
        pitch_eighth_offset=cut_eighths,
        max_beat=cut,
        clip_beats=cut,
        starts_cell=True,
    )
    lead: list = []
    support: list = []
    low: list = []
    for source, shift in ((first, 0.0), (second, cut)):
        source_lead, source_support, source_low = source
        for target, events in (
            (lead, source_lead),
            (support, source_support),
            (low, source_low),
        ):
            for event in events:
                if event.beat >= cut:
                    continue
                duration = min(event.duration_beats, cut - event.beat)
                if duration <= 0:
                    continue
                target.append(
                    replace(
                        event,
                        beat=event.beat + shift,
                        duration_beats=duration,
                        bar=target_bar,
                    )
                )
    return lead, support, low


def render_studio_arrangement(
    ctx: Any,
    piece: StudioPiece,
) -> tuple[list, list, list]:
    """Render ``piece.arrangement`` one absolute bar at a time.

    Returns the concatenated ``(lead, support, low)`` voices. Clipping and
    tie/slur endpoints at cell edges stay in
    :func:`app.sonify.texture_figure.render_texture_bar`; this function only
    chooses the cell bar and concatenates.
    """
    errors = piece.validate()
    if errors:
        raise ValueError("invalid StudioPiece: " + "; ".join(errors))

    lead: list = []
    support: list = []
    low: list = []
    for target_bar, entry in enumerate(piece.arrangement):
        if entry.kind == "cell":
            texture = piece.cells[entry.source_id]
            cell_lead, cell_support, cell_low = render_texture_bar(
                texture,
                ctx,
                target_bar,
                cell_bar=entry.source_bar,
            )
        elif entry.kind == "compressed":
            texture = piece.cells[entry.source_id]
            cell_lead, cell_support, cell_low = _compressed_voices(
                texture, ctx, target_bar, entry.source_bar
            )
        elif entry.kind == "cadence":
            from app.sonify.guitar_villa_figures import (
                VILLA_CADENCE,
                render_villa_figure,
            )

            cell_lead, cell_support, cell_low = render_villa_figure(
                ctx, target_bar, None, VILLA_CADENCE
            )
        elif entry.kind == "figure":
            # Phase A has no figure renderer. The arrangement schema keeps the
            # slot so Phase B can add VILLA_CADENCE without rewriting stored data.
            raise NotImplementedError(
                "Studio arrangement figure entries are reserved for Phase B; "
                f"got figure {entry.source_id!r} at bar {target_bar}"
            )
        else:  # validate() already rejected this, kept for a clear runtime error.
            raise ValueError(f"unknown arrangement kind {entry.kind!r}")
        lead.extend(cell_lead)
        support.extend(cell_support)
        low.extend(cell_low)
    return lead, support, low
