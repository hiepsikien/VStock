"""Pure promote plan for a tagged Studio figure pool (Phase 4).

:func:`promote_figures` validates a complete five-required-tag pool (optional
``contrast``/``close`` figures may also be present) and returns a
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
    STUDIO_DOOR_METERS,
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
    SENTENCE_SPECS,
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


@dataclass
class _Snapshot:
    """Previous registry state captured by one explicit apply."""

    plan: PromotionPlan
    cells: Mapping[str, TextureSpec | None]
    door: Callable[..., list[tuple]] | None
    door_meter: str | None = None
    sentences: tuple[SentenceSpec, ...] | None = None
    body_added: bool = False


def _promotion_key(plan: PromotionPlan) -> tuple[str, str, str]:
    return (plan.ensemble, plan.pattern, plan.meter)


# One stack per pattern/meter so a failed re-promote can restore the previous
# promotion instead of deleting cells that already existed.
_APPLIED: dict[tuple[str, str, str], list[_Snapshot]] = {}


def reset_promotions() -> None:
    """Drop promote snapshots; tests and process resets use this explicitly."""
    _APPLIED.clear()


def unapply_promotion_by_key(
    ensemble: str,
    pattern: str,
    meter: str,
) -> bool:
    """Revert the latest promotion for one pattern/meter without a draft.

    ``/unpromote`` must work even if the Studio draft is incomplete or edited;
    this helper only needs the registry key. Returns whether a snapshot was
    restored.
    """
    stack = _APPLIED.get((ensemble, pattern, meter))
    if not stack:
        return False
    unapply_promotion(stack[-1].plan, force=True)
    return True


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
        if texture is None:
            raise ValueError(
                f"{figure.id}: no texture for cell {figure.cell_id!r}; "
                "pass (figure, texture) or register the cell first"
            )
        previous = cells.get(figure.cell_id)
        if previous is not None and previous != texture:
            raise ValueError(
                f"cell {figure.cell_id!r} is mapped to two different textures"
            )
        cells[figure.cell_id] = texture
        normalised.append(figure)

    return tuple(normalised), cells


def _literal_pitch_error(cells: Mapping[str, TextureSpec]) -> str | None:
    """Production promotion rejects absolute MusicXML MIDI."""
    for cell_id, texture in cells.items():
        for index, event in enumerate(texture.authored):
            if event.pitch.kind == "literal_midi":
                return (
                    f"cell {cell_id!r} authored.events[{index}].pitch: "
                    "literal_midi is preview-only; use scale_step, "
                    "chord_degree, or chord_root for production"
                )
    return None


def promote_figures(
    pattern: str,
    meter: str,
    figures: Sequence[Any],
    existing_sentences: Sequence[SentenceSpec] = (),
    *,
    ensemble: str = "villa",
    allow_literal: bool = False,
) -> PromotionPlan:
    """Validate a complete pool and return a pure promotion plan.

    ``figures`` may hold plain :class:`PatternFigure` values (their textures
    are then read from ``TEXTURE_CELLS``), ``(figure, texture)`` pairs, or
    draft-like objects/mappings carrying a ``texture``/``spec``. Passing the
    texture explicitly is the intended promote path; the registry read keeps
    already-authored code cells usable.

    Raises ``ValueError`` unless all five required tags are present exactly
    once, every figure has a non-empty ``cell_id``, and the body sentence is
    derivable from the key figure. Optional ``contrast``/``close`` figures may
    be present, must be unambiguous, and never replace a required tag. It never
    registers anything.
    """
    pattern = _non_empty_string(pattern, "pattern")
    meter = _non_empty_string(meter, "meter")
    ensemble = _non_empty_string(ensemble, "ensemble")
    if not isinstance(figures, Sequence) or isinstance(figures, (str, bytes)):
        raise ValueError("figures must be a sequence")

    pool, cells = _normalise_figures(pattern, meter, figures)
    if not allow_literal:
        literal_error = _literal_pitch_error(cells)
        if literal_error is not None:
            raise ValueError(literal_error)
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
    # every required tag is present exactly once here. Optional tags may be
    # absent; when present they only extend the tag map.
    absent_required = [
        tag for tag in REQUIRED_FIGURE_TAGS if tag not in tags
    ]
    if absent_required:
        raise ValueError(
            "missing figure tags: " + ", ".join(absent_required)
        )

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

    Re-applying the same pattern upserts the cells and door. The previous
    values are snapshotted so :func:`unapply_promotion` can restore them
    instead of deleting pre-existing production cells.
    """
    if not isinstance(plan, PromotionPlan):
        raise TypeError("plan must be a PromotionPlan")
    key = _promotion_key(plan)
    stack = _APPLIED.get(key)
    if stack and stack[-1].plan is plan:
        # Re-applying the same plan is a no-op. Pushing a second snapshot
        # would make one unapply restore this same promotion and leave cells
        # behind.
        return plan.body
    if stack is None and len(_APPLIED) >= 64:
        raise ValueError("too many active figure promotions; unpromote one first")
    if stack is not None and len(stack) >= 8:
        raise ValueError("too many stacked promotions for this pattern; unpromote first")
    table = TEXTURE_CELLS.get((plan.pattern, plan.meter), {})
    snapshot = _Snapshot(
        plan=plan,
        cells=dict(table),
        door=STUDIO_DOORS.get((plan.ensemble, plan.pattern)),
        door_meter=STUDIO_DOOR_METERS.get((plan.ensemble, plan.pattern)),
        sentences=SENTENCE_SPECS.get((plan.pattern, plan.meter)),
    )
    _APPLIED.setdefault(key, []).append(snapshot)
    try:
        for cell_id, texture in plan.cells.items():
            register_texture_cell(
                plan.pattern,
                plan.meter,
                cell_id,
                texture,
                replace=True,
            )
        register_studio_door(
            plan.ensemble,
            plan.pattern,
            plan.door,
            meter=plan.meter,
            replace=True,
        )
    except Exception:
        # Restore exactly the state before this apply.
        unapply_promotion(plan)
        raise
    return plan.body


def unapply_promotion(plan: PromotionPlan, *, force: bool = False) -> None:
    """Undo :func:`apply_promotion`; safe to call more than once.

    Restores the snapshot captured by the matching apply. A cell or door that
    was replaced after apply is left in place: unapply only restores values
    that this promotion actually changed. ``force`` is for an explicit
    unpromote route that rebuilds an equivalent plan; it restores the latest
    snapshot for the pattern even when the plan object differs.
    """
    if not isinstance(plan, PromotionPlan):
        raise TypeError("plan must be a PromotionPlan")
    key = _promotion_key(plan)
    stack = _APPLIED.get(key)
    if stack and (force or stack[-1].plan is plan):
        snapshot = stack.pop()
        if not stack:
            _APPLIED.pop(key, None)
        current_table = TEXTURE_CELLS.get((plan.pattern, plan.meter))
        if current_table is not None:
            for cell_id in list(current_table):
                if cell_id not in snapshot.cells:
                    unregister_texture_cell(
                        plan.pattern, plan.meter, cell_id
                    )
        for cell_id, previous in snapshot.cells.items():
            if previous is None:
                unregister_texture_cell(plan.pattern, plan.meter, cell_id)
            else:
                register_texture_cell(
                    plan.pattern,
                    plan.meter,
                    cell_id,
                    previous,
                    replace=True,
                )
        door_key = (plan.ensemble, plan.pattern)
        current_door = STUDIO_DOORS.get(door_key)
        if not force and current_door is not None and current_door is not plan.door:
            if snapshot.body_added:
                if snapshot.sentences is None:
                    SENTENCE_SPECS.pop((plan.pattern, plan.meter), None)
                else:
                    SENTENCE_SPECS[(plan.pattern, plan.meter)] = snapshot.sentences
            return
        if snapshot.door is None:
            unregister_studio_door(plan.ensemble, plan.pattern)
        else:
            register_studio_door(
                plan.ensemble,
                plan.pattern,
                snapshot.door,
                meter=snapshot.door_meter,
                replace=True,
            )
        if snapshot.body_added:
            if snapshot.sentences is None:
                SENTENCE_SPECS.pop((plan.pattern, plan.meter), None)
            else:
                SENTENCE_SPECS[(plan.pattern, plan.meter)] = snapshot.sentences
        return

    # Compatibility/no-snapshot path: remove only values this plan still owns.
    table = TEXTURE_CELLS.get((plan.pattern, plan.meter))
    for cell_id, texture in plan.cells.items():
        current = table.get(cell_id) if table else None
        if current is not None and (current is texture or current == texture):
            unregister_texture_cell(plan.pattern, plan.meter, cell_id)
    key_door = (plan.ensemble, plan.pattern)
    if STUDIO_DOORS.get(key_door) is plan.door:
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
    key = (body.pattern, body.meter)
    existing = SENTENCE_SPECS.get(key)
    stack = _APPLIED.get(
        (
            plan_or_spec.ensemble
            if isinstance(plan_or_spec, PromotionPlan)
            else "villa",
            body.pattern,
            body.meter,
        )
    )
    snapshot = stack[-1] if stack else None
    if existing is None:
        register_sentence_specs(body.pattern, body.meter, body, replace=replace)
        if snapshot is not None:
            snapshot.body_added = True
        return body
    register_sentence_specs(body.pattern, body.meter, body, replace=replace)
    if snapshot is not None and replace:
        snapshot.body_added = True
    return body
