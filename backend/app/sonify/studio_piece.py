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
from dataclasses import dataclass, field
from typing import Any, Literal, NamedTuple

from app.sonify.texture_figure import render_texture_bar
from app.studio.texture_spec import TextureSpec

__all__ = [
    "ARRANGEMENT_KINDS",
    "ArrangementBar",
    "StudioPiece",
    "render_studio_arrangement",
]

#: Kinds an arrangement entry may name. Phase A renders ``cell`` only.
ARRANGEMENT_KINDS = ("cell", "figure")

ArrangementKind = Literal["cell", "figure"]


class ArrangementBar(NamedTuple):
    """One absolute bar of a Studio arrangement.

    ``kind`` selects the source namespace:

    * ``"cell"`` reads ``source_id`` from :attr:`StudioPiece.cells` and renders
      ``source_bar`` (the 0-based bar inside that cell).
    * ``"figure"`` is reserved for Phase B. ``source_id`` is a figure id and
      ``source_bar`` is the figure-local bar.

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
        return tuple(errors)

    def __repr__(self) -> str:  # keep a huge cell body out of failure messages
        return (
            f"StudioPiece(pattern={self.pattern!r}, meter={self.meter!r}, "
            f"cells={list(self.cells)!r}, arrangement={self.arrangement!r})"
        )


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
