"""Pure promote plan for a tagged Studio figure pool (Phase 4).

:func:`promote_figures` validates a complete five-tag pool and returns a
:class:`PromotionPlan`: the derived body ``SentenceSpec``, the compiled door
callable, the cell map, and the tag map. It is deliberately pure: nothing is
written to ``TEXTURE_CELLS``, ``SENTENCE_SPECS``, or the door registry.

:func:`apply_promotion` performs the explicit registration step. It registers
the plan's texture cells and door, then returns the body sentence for the
caller to register (the caller owns ``SENTENCE_SPECS``). Removing the promotion
again is :func:`unapply_promotion`; both are idempotent.

The Studio request path must not call these helpers. They are for an explicit
promote/flag path only, so a normal preview/export never mutates global tables.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.sonify.pattern_doors import (
    STUDIO_DOORS,
    compile_figure_doors,
    register_studio_door,
    unregister_studio_door,
)
from app.sonify.pattern_figures import (
    FIGURE_TAGS,
    REQUIRED_FIGURE_TAGS,
    PatternFigure,
    derive_body_sentence,
    missing_figure_tags,
    validate_figures,
)
from app.sonify.sentence_specs import (
    SentenceSpec,
    register as register_sentence_specs,
)
from app.sonify.texture_figure import (
    TEXTURE_CELLS,
    register_texture_cell,
    unregister_texture_cell,
)
from app.studio.texture_spec import TextureSpec

__all__ = [
    "PromotionPlan",
    "apply_promotion",
    "promote_figures",
    "register_body_sentence",
    "unapply_promotion",
]


@dataclass(frozen=True)
class PromotionPlan:
    """Everything an explicit promote needs, with no global side effect yet.

    ``cells`` maps a ``cell_id`` to the authored ``TextureSpec`` the caller
    wants registered. ``tags`` maps a figure tag to its single owner. ``body``
    is the body sentence derived from the ``key`` figure; the caller registers
    it (or uses :func:`register_body_sentence`) after ``apply_promotion``.
    """

    pattern: str
    meter: str
    body: SentenceSpec
    door: Callable[..., list[tuple]]
    cells: Mapping[str, TextureSpec]
    tags: Mapping[str, PatternFigure]
    figures: tuple[PatternFigure, ...]
    ensemble: str = "villa"

    @property
    def body_sentence(self) -> SentenceSpec:
        """Alias used by callers that name the field explicitly."""
        return self.body

    @property
    def sentence(self) -> SentenceSpec:
        """Short alias for the body ``SentenceSpec``."""
        return self.body

    @property
    def cell_map(self) -> Mapping[str, TextureSpec]:
        return self.cells

    @property
    def tag_map(self) -> Mapping[str, PatternFigure]:
        return self.tags

    @property
    def key(self) -> PatternFigure:
        return self.tags["key"]

    @property
    def cell_ids(self) -> Mapping[str, str]:
        """``tag -> cellId`` projection, useful for export/preview."""
        return {tag: figure.cell_id for tag, figure in self.tags.items()}

    @property
    def cells_by_tag(self) -> Mapping[str, TextureSpec]:
        """``tag -> TextureSpec`` for the figures whose cell is resolvable."""
        return {
            tag: self.cells[figure.cell_id]
            for tag, figure in self.tags.items()
            if figure.cell_id in self.cells
        }

    @property
    def textures(self) -> Mapping[str, TextureSpec]:
        """Alias for the ``cell_id -> TextureSpec`` map."""
        return self.cells


def _non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _mapping_figure(item: Mapping[str, Any]) -> tuple[PatternFigure, Any]:
    """Build a figure from a Studio-draft-shaped mapping."""
    raw_id = item.get("id")
    raw_cell = item.get("cell_id", item.get("cellId", raw_id))
    raw_bars = item.get("bars")
    raw_tags = item.get("tags", ())
    if not isinstance(raw_tags, (tuple, list)):
        raise ValueError("figure tags must be a sequence")
    figure = PatternFigure(
        id=_non_empty_string(raw_id, "figure id"),
        cell_id=raw_cell if isinstance(raw_cell, str) else "",
        bars=raw_bars if isinstance(raw_bars, int) else -1,
        tags=tuple(raw_tags),
    )
    texture = item.get("texture", item.get("spec"))
    return figure, texture


def _normalise_figures(
    pattern: str,
    meter: str,
    figures: Sequence[Any],
) -> tuple[tuple[PatternFigure, ...], dict[str, TextureSpec]]:
    """Accept figures, ``(figure, texture)`` pairs, or draft-like objects."""
    normalised: list[PatternFigure] = []
    cells: dict[str, TextureSpec] = {}

    for item in figures:
        if isinstance(item, PatternFigure):
            figure = item
            texture = None
        elif (
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], PatternFigure)
        ):
            figure, texture = item
        elif isinstance(item, Mapping):
            figure, texture = _mapping_figure(item)
        else:
            figure = getattr(item, "figure", None)
            if figure is None:
                figure = getattr(item, "pattern_figure", None)
            texture = getattr(item, "texture", None)
            if texture is None:
                texture = getattr(item, "spec", None)
            if figure is None and all(
                hasattr(item, name) for name in ("id", "cell_id", "bars", "tags")
            ):
                figure = PatternFigure(
                    id=item.id,
                    cell_id=item.cell_id,
                    bars=item.bars,
                    tags=tuple(item.tags),
                )
            if figure is None:
                raise ValueError(
                    "each figure must be a PatternFigure, a "
                    "(PatternFigure, TextureSpec) pair, or a draft-like object"
                )

        if not isinstance(figure, PatternFigure):
            raise ValueError("figure must be a PatternFigure")
        if texture is not None and not isinstance(texture, TextureSpec):
            raise ValueError(f"{figure.id}: texture must be a TextureSpec")

        if texture is None:
            texture = TEXTURE_CELLS.get((pattern, meter), {}).get(figure.cell_id)
        if texture is not None:
            previous = cells.get(figure.cell_id)
            if previous is not None and previous != texture:
                raise ValueError(
                    f"cell {figure.cell_id!r} is mapped to two different textures"
                )
            cells[figure.cell_id] = texture
        normalised.append(figure)

    return tuple(normalised), cells


def promote_figures(
    pattern: str,
    meter: str,
    figures: Sequence[Any],
    existing_sentences: Sequence[SentenceSpec] = (),
    *,
    ensemble: str = "villa",
) -> PromotionPlan:
    """Validate a complete pool and return a pure promotion plan.

    ``figures`` may hold plain :class:`PatternFigure` values (their textures
    are then read from ``TEXTURE_CELLS``), ``(figure, texture)`` pairs, or
    draft-like objects/mappings carrying a ``texture``/``spec``. Passing the
    texture explicitly is the intended promote path; the registry read keeps
    already-authored code cells usable.

    Raises ``ValueError`` unless all five tags are present exactly once, every
    figure has a non-empty ``cell_id``, and the body sentence is derivable from
    the key figure. It never registers anything.
    """
    pattern = _non_empty_string(pattern, "pattern")
    meter = _non_empty_string(meter, "meter")
    ensemble = _non_empty_string(ensemble, "ensemble")
    if not isinstance(figures, Sequence) or isinstance(figures, (str, bytes)):
        raise ValueError("figures must be a sequence")

    pool, cells = _normalise_figures(pattern, meter, figures)
    errors = validate_figures(pool)
    if errors:
        raise ValueError("; ".join(errors))

    for figure in pool:
        if not figure.cell_id:
            raise ValueError(f"{figure.id}: cell_id must be non-empty")

    missing = missing_figure_tags(pool)
    if missing:
        raise ValueError("missing figure tags: " + ", ".join(missing))

    tags: dict[str, PatternFigure] = {}
    for figure in pool:
        for tag in figure.tags:
            if tag in FIGURE_TAGS:
                tags[tag] = figure

    # `validate_figures` rejects duplicate owners and `missing` is empty, so
    # every required tag is present exactly once here.
    if set(tags) != set(REQUIRED_FIGURE_TAGS):
        raise ValueError("figure pool must cover exactly the five required tags")

    # A slot names a cell, never a figure id. Rejecting this early keeps a
    # draft that confused the two from silently deriving a second body.
    by_cell = {figure.cell_id for figure in pool}
    for spec in existing_sentences:
        if spec.pattern != pattern or spec.meter != meter:
            continue
        for slot in spec.slots:
            if slot.cell in {figure.id for figure in pool} and slot.cell not in by_cell:
                owner = next(
                    figure for figure in pool if figure.id == slot.cell
                )
                raise ValueError(
                    f"{spec.id}: slot cell {slot.cell!r} is a figure id; "
                    f"use the figure's cell_id {owner.cell_id!r}"
                )

    body = derive_body_sentence(
        pattern, meter, tags["key"], existing=existing_sentences
    )
    door = compile_figure_doors(
        pattern,
        meter,
        tags["intro.short"],
        tags["intro.long"],
        tags["outro.short"],
        tags["outro.long"],
    )
    return PromotionPlan(
        pattern=pattern,
        meter=meter,
        body=body,
        door=door,
        cells=cells,
        tags=tags,
        figures=pool,
        ensemble=ensemble,
    )


def apply_promotion(plan: PromotionPlan) -> SentenceSpec:
    """Register the plan's cells and door; return the body for the caller.

    The body sentence is intentionally **not** registered here: this module
    does not own ``SENTENCE_SPECS``. Use :func:`register_body_sentence` or the
    caller's own registry helper.
    """
    if not isinstance(plan, PromotionPlan):
        raise TypeError("plan must be a PromotionPlan")
    for cell_id, texture in plan.cells.items():
        register_texture_cell(plan.pattern, plan.meter, cell_id, texture)
    register_studio_door(plan.ensemble, plan.pattern, plan.door)
    return plan.body


def unapply_promotion(plan: PromotionPlan) -> None:
    """Undo :func:`apply_promotion`; safe to call more than once.

    A cell or door that was replaced after apply is left in place: unapply only
    removes the exact values this plan registered.
    """
    if not isinstance(plan, PromotionPlan):
        raise TypeError("plan must be a PromotionPlan")
    table = TEXTURE_CELLS.get((plan.pattern, plan.meter))
    for cell_id, texture in plan.cells.items():
        current = table.get(cell_id) if table else None
        if current is not None and (current is texture or current == texture):
            unregister_texture_cell(plan.pattern, plan.meter, cell_id)
    key = (plan.ensemble, plan.pattern)
    if STUDIO_DOORS.get(key) is plan.door:
        unregister_studio_door(plan.ensemble, plan.pattern)


def register_body_sentence(
    plan_or_spec: PromotionPlan | SentenceSpec,
    *,
    replace: bool = False,
) -> SentenceSpec:
    """Explicitly register a body sentence; never called by ``apply``.

    Accepts either the plan or its ``body`` sentence. This is the one place a
    promote caller may write ``SENTENCE_SPECS``; it stays opt-in.
    """
    body = (
        plan_or_spec.body
        if isinstance(plan_or_spec, PromotionPlan)
        else plan_or_spec
    )
    if not isinstance(body, SentenceSpec):
        raise TypeError("expected a PromotionPlan or SentenceSpec")
    register_sentence_specs(body.pattern, body.meter, body, replace=replace)
    return body
