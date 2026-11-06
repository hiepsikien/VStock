"""Pure helpers for the Studio pattern figure pool (Phase 4).

A Studio pattern draft has a **figure pool**. Each figure is a ``TextureSpec``
plus a local ``cellId``, a bar count, and zero or more role tags. The tags are
metadata: the production body is still a ``SentenceSpec`` that tiles the
figure's cell.

Five tags are required for promotion (``key`` and the four door frames). Two
more are optional body material (``contrast`` for the B phrase and ``close``
for the final phrase); a pool without them is still complete and later phases
fall back to ``key`` with a warning.

This module owns the tag vocabulary and the one-way derivation from the
``key`` tag to a body sentence. It imports no renderer and mutates nothing:
every helper is pure, so Studio preview/export can use the same rules the
backend will apply at promote time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

__all__ = [
    "FIGURE_TAGS",
    "KEY_BODY_MISSING",
    "OPTIONAL_FIGURE_TAGS",
    "REQUIRED_FIGURE_TAGS",
    "PatternFigure",
    "body_sentence_errors",
    "derive_body_sentence",
    "figure_tag_errors",
    "missing_figure_tags",
    "validate_figure_tags",
    "validate_figures",
]

REQUIRED_FIGURE_TAGS = (
    "key",
    "intro.short",
    "intro.long",
    "outro.short",
    "outro.long",
)
#: Body material a plan may use but a complete five-tag pool need not have.
OPTIONAL_FIGURE_TAGS = frozenset({"contrast", "close"})
FIGURE_TAGS = frozenset(REQUIRED_FIGURE_TAGS) | OPTIONAL_FIGURE_TAGS
#: `missing[]` uses this when the key figure is absent or unusable, per §3.5.
KEY_BODY_MISSING = "key.body"

#: Short scripts are 2 bars, long scripts are 4. `key` may be any length >= 1.
#: A tuple is an inclusive ``(min, max)`` range: `contrast`/`close` are body
#: phrases, so any 1-4 bar figure is legal.
_TAG_BARS: dict[str, int | tuple[int, int]] = {
    "intro.short": 2,
    "intro.long": 4,
    "outro.short": 2,
    "outro.long": 4,
    "contrast": (1, 4),
    "close": (1, 4),
}


@dataclass(frozen=True)
class PatternFigure:
    """One figure-pool entry.

    ``id`` is the local stable id; ``cell_id`` maps 1:1 to
    ``TEXTURE_CELLS[(pattern, meter)]``. They may differ only with an explicit
    mapping at promote time.
    """

    id: str
    cell_id: str
    bars: int
    tags: tuple[str, ...] = ()


def figure_tag_errors(tags: Sequence[str], bars: int) -> tuple[str, ...]:
    """Every reason a tag set is invalid for ``bars`` (empty means valid).

    The rules are deliberately the same for one figure:
    * ``key`` needs at least one bar;
    * ``intro/outro.short`` needs exactly 2 bars;
    * ``intro/outro.long`` needs exactly 4 bars;
    * ``contrast``/``close`` need 1-4 bars;
    * a multi-tag figure must satisfy every tag it carries;
    * a tag may appear only once on one figure.
    """
    errors: list[str] = []
    if not isinstance(bars, int) or isinstance(bars, bool) or bars < 1:
        errors.append("bars must be an integer >= 1")
    seen: set[str] = set()
    for tag in tags:
        if tag not in FIGURE_TAGS:
            errors.append(f"unknown figure tag {tag!r}")
            continue
        if tag in seen:
            errors.append(f"duplicate figure tag {tag!r}")
            continue
        seen.add(tag)
        expected = _TAG_BARS.get(tag)
        if isinstance(expected, tuple):
            low, high = expected
            if (
                isinstance(bars, int)
                and not isinstance(bars, bool)
                and not low <= bars <= high
            ):
                errors.append(
                    f"tag {tag!r} needs {low}-{high} bars, got {bars}"
                )
        elif expected is not None and bars != expected:
            errors.append(
                f"tag {tag!r} needs {expected} bars, got {bars}"
            )
    return tuple(errors)


def validate_figure_tags(tags: Sequence[str], bars: int) -> None:
    """Raise ``ValueError`` for the first invalid tag/bar combination."""
    errors = figure_tag_errors(tags, bars)
    if errors:
        raise ValueError("; ".join(errors))


def validate_figures(figures: Sequence[PatternFigure]) -> tuple[str, ...]:
    """Cross-figure rules: per-figure tags plus one owner per tag (MVP).

    The one-owner rule covers **every** known tag, required or optional: two
    figures claiming ``contrast`` are as ambiguous as two claiming ``key``.
    """
    errors: list[str] = []
    owners: dict[str, list[str]] = {}
    for figure in figures:
        if not isinstance(figure, PatternFigure):
            errors.append("figure must be a PatternFigure")
            continue
        for error in figure_tag_errors(figure.tags, figure.bars):
            errors.append(f"{figure.id}: {error}")
        for tag in figure.tags:
            if tag in FIGURE_TAGS:
                owners.setdefault(tag, []).append(figure.id)
    for tag in sorted(owners):
        if len(owners[tag]) > 1:
            errors.append(
                f"tag {tag!r} is claimed by more than one figure: "
                f"{sorted(owners[tag])}"
            )
    return tuple(errors)


def _valid_owners(
    figures: Sequence[PatternFigure],
) -> dict[str, list[PatternFigure]]:
    """Figures whose own tag/bar rules pass, grouped by tag."""
    owners: dict[str, list[PatternFigure]] = {}
    for figure in figures:
        if not isinstance(figure, PatternFigure):
            continue
        if figure_tag_errors(figure.tags, figure.bars):
            continue
        for tag in figure.tags:
            if tag in FIGURE_TAGS:
                owners.setdefault(tag, []).append(figure)
    return owners


def missing_figure_tags(
    figures: Sequence[PatternFigure],
) -> tuple[str, ...]:
    """The required tags no valid figure owns, in display order.

    A tag with more than one owner is incomplete (MVP: one figure per tag), so
    it is reported as missing. A missing or unusable key report is
    ``"key.body"`` rather than ``"key"``, because the completeness question is
    whether the body sentence is derivable, not whether a label exists.

    Optional tags (``contrast``/``close``) are deliberately not reported: a
    five-tag pool is complete, and the arrangement builder warns and falls back
    to ``key`` when they are absent.
    """
    owners = _valid_owners(figures)
    missing: list[str] = []
    for tag in REQUIRED_FIGURE_TAGS:
        unique = len(owners.get(tag, ())) == 1
        if tag == "key":
            if not unique:
                missing.append(KEY_BODY_MISSING)
        elif not unique:
            missing.append(tag)
    return tuple(missing)


def _key_figure(key_figure: PatternFigure) -> PatternFigure:
    if not isinstance(key_figure, PatternFigure):
        raise ValueError("key figure must be a PatternFigure")
    if "key" not in key_figure.tags:
        raise ValueError(f"{key_figure.id}: figure does not carry the 'key' tag")
    errors = figure_tag_errors(key_figure.tags, key_figure.bars)
    if errors:
        raise ValueError(f"{key_figure.id}: {errors[0]}")
    if not key_figure.cell_id:
        raise ValueError(f"{key_figure.id}: cell_id must be non-empty")
    return key_figure


def derive_body_sentence(
    pattern: str,
    meter: str,
    key_figure: PatternFigure,
    *,
    existing: Sequence[SentenceSpec] = (),
) -> SentenceSpec:
    """The body sentence for a key figure.

    If ``existing`` already holds a sentence whose slot uses the key's
    ``cellId`` with matching bars and a tile that can carry it, that sentence
    is returned unchanged. A sentence that uses the cell with the wrong slot
    length or too short a tile is rejected: silently deriving a second body
    would hide the authoring error.
    """
    key = _key_figure(key_figure)
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern must be a non-empty string")
    if not isinstance(meter, str) or not meter:
        raise ValueError("meter must be a non-empty string")

    matches = [
        spec
        for spec in existing
        if any(slot.cell == key.cell_id for slot in spec.slots)
    ]
    for spec in matches:
        cell_slots = [slot for slot in spec.slots if slot.cell == key.cell_id]
        tile = spec.span.tile
        for slot in cell_slots:
            if slot.bars != key.bars:
                raise ValueError(
                    f"{spec.id}: key cell slot has {slot.bars} bars, "
                    f"figure has {key.bars}"
                )
            if tile is not None and tile < key.bars:
                raise ValueError(
                    f"{spec.id}: tile {tile} is shorter than the key figure "
                    f"({key.bars} bars)"
                )
        return spec

    return SentenceSpec(
        id=f"{pattern}_{key.cell_id}_body",
        pattern=pattern,
        meter=meter,
        select=Select(length_min=key.bars),
        span=Span(
            tile=key.bars,
            remainder="same_figure",
            truncate_to_length=True,
        ),
        slots=(Slot(start=0, bars=key.bars, cell=key.cell_id),),
    )


def body_sentence_errors(
    pattern: str,
    meter: str,
    key_figure: PatternFigure,
    existing: Sequence[SentenceSpec] = (),
) -> tuple[str, ...]:
    """Non-raising wrapper around :func:`derive_body_sentence`."""
    try:
        derive_body_sentence(
            pattern, meter, key_figure, existing=existing
        )
    except ValueError as exc:
        return (str(exc),)
    return ()
