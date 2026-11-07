"""Build a :class:`StudioPiece` arrangement from tagged figures and a form.

This is the Phase B plan layer from ``docs/studio-render-piece-plan.md`` §5/§6.3.
It is pure: figures and a :class:`~app.sonify.form.FormSpec` go in, a frozen
render plan comes out. No registry is read or written, so two builds with the
same inputs cannot collide.

The form is split into three spans:

* ``intro``/``warmup`` sections use the ``intro.short`` (2-bar) or
  ``intro.long`` (4-bar) figure;
* ``outro``/``cooldown`` sections use ``outro.short``/``outro.long``;
* every other section is body. Each body section is one phrase, and a role
  policy (``auto_aaba`` or ``trio``) assigns ``A``/``B``/``close`` once per
  phrase. The role expands to one entry per body bar.

Body material never invents notes. ``A`` uses ``key``, ``B`` prefers the
optional ``contrast`` figure, and ``close`` prefers the optional ``close``
figure. When an optional figure is absent the builder falls back to ``key`` and
records a warning instead of failing the render.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.sonify.form import FormSpec
from app.sonify.guitar_frame import frame_roles
from app.sonify.pattern_doors import frame_role_bar
from app.sonify.pattern_figures import (
    FIGURE_TAGS,
    PatternFigure,
    missing_figure_tags,
    validate_figures,
)
from app.sonify.studio_piece import StudioPiece, StudioProductionOptions
from app.studio.texture_spec import TextureSpec

__all__ = [
    "ARRANGEMENT_POLICIES",
    "ArrangementResult",
    "build_arrangement",
]

#: Plan ids Phase B implements. ``abab``/``through`` stay future work.
ARRANGEMENT_POLICIES = ("auto_aaba", "trio")

_INTRO_KINDS = frozenset({"intro", "warmup"})
_OUTRO_KINDS = frozenset({"outro", "cooldown"})

_WARN_B_FALLBACK = "B fallback: key"
_WARN_CLOSE_FALLBACK = "close fallback: VILLA_CADENCE"


@dataclass(frozen=True)
class ArrangementResult:
    """A renderable piece plus the plan decisions that produced it."""

    piece: StudioPiece
    roles: tuple[str, ...]
    warnings: tuple[str, ...]
    used_tags: tuple[str, ...]


def _non_empty_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _section_group(kind: str) -> str:
    if kind in _INTRO_KINDS:
        return "intro"
    if kind in _OUTRO_KINDS:
        return "outro"
    return "body"


def _tag_map(
    figures: Sequence[PatternFigure],
    *,
    require_doors: bool = True,
) -> dict[str, PatternFigure]:
    """Validate the pool and project ``tag -> figure``.

    ``validate_figures`` already rejects duplicate owners for every known tag,
    including ``contrast``/``close``. ``missing_figure_tags`` only checks the
    five required tags, so a pool without optional material is still valid.
    """
    for figure in figures:
        if not isinstance(figure, PatternFigure):
            raise ValueError("figures must contain PatternFigure values")
    errors = validate_figures(figures)
    if errors:
        raise ValueError("; ".join(errors))
    missing = missing_figure_tags(figures)
    if require_doors:
        if missing:
            raise ValueError("missing figure tags: " + ", ".join(missing))
    elif not any("key" in figure.tags for figure in figures):
        raise ValueError("missing figure tag: key")

    tags: dict[str, PatternFigure] = {}
    for figure in figures:
        for tag in figure.tags:
            if tag in FIGURE_TAGS:
                tags[tag] = figure
    return tags


def _auto_aaba_roles(count: int) -> tuple[str, ...]:
    """A/A/B/close; for fewer than three phrases, A + close (or close)."""
    if count == 0:
        return ()
    if count == 1:
        return ("close",)
    if count == 2:
        return ("A", "close")
    roles = ["A"] * count
    roles[min(2, count - 2)] = "B"
    roles[-1] = "close"
    return tuple(roles)


def _trio_roles(
    count: int,
    sections: Sequence[object],
) -> tuple[str, ...]:
    """A/B/A with B on the trio/bridge phrase or the middle phrase.

    The final A is the close; unlike ``auto_aaba`` this policy never adds a
    separate ``close`` role, matching `sentence_plan.Trio`.
    """
    if count == 0:
        return ()
    if count == 1:
        return ("A",)
    if count == 2:
        return ("A", "A")
    roles = ["A"] * count
    bridge = next(
        (
            index
            for index, section in enumerate(sections[:-1])
            if bool(getattr(section, "trio", False))
            or bool(getattr(section, "bridge", False))
        ),
        None,
    )
    b_index = bridge if bridge is not None else max(1, count // 2)
    if b_index >= count - 1:
        b_index = max(0, count - 2)
    roles[b_index] = "B"
    return tuple(roles)


def _body_roles(
    body_sections: Sequence[object],
    policy: str,
) -> tuple[str, ...]:
    count = len(body_sections)
    if policy == "auto_aaba":
        return _auto_aaba_roles(count)
    if policy == "trio":
        return _trio_roles(count, body_sections)
    raise ValueError(
        f"unknown arrangement policy {policy!r}; "
        f"expected one of {ARRANGEMENT_POLICIES}"
    )


def _warn(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _body_figure(
    role: str,
    tags: Mapping[str, PatternFigure],
    warnings: list[str],
) -> tuple[PatternFigure, str]:
    """Choose the figure for one body phrase and remember the tag used."""
    if role == "B":
        figure = tags.get("contrast")
        if figure is None:
            _warn(warnings, _WARN_B_FALLBACK)
            return tags["key"], "key"
        return figure, "contrast"
    if role == "close":
        figure = tags.get("close")
        if figure is None:
            _warn(warnings, _WARN_CLOSE_FALLBACK)
            return tags["key"], "key"
        return figure, "close"
    return tags["key"], "key"


def _texture_for(
    figure: PatternFigure,
    textures: Mapping[str, TextureSpec],
    used_cells: dict[str, TextureSpec],
) -> TextureSpec:
    texture = textures.get(figure.cell_id)
    if texture is None:
        raise ValueError(
            f"{figure.id}: no texture for cell {figure.cell_id!r}; "
            "pass textures[cell_id]"
        )
    previous = used_cells.get(figure.cell_id)
    if previous is not None and previous != texture:
        raise ValueError(
            f"cell {figure.cell_id!r} is mapped to two different textures"
        )
    used_cells[figure.cell_id] = texture
    return texture


def _door_entries(
    section: object,
    tag: str,
    figure: PatternFigure,
    *,
    used_tags: list[str],
) -> list[tuple[str, str, int]]:
    """One entry per frame bar, mapping the frame screenplay to a cell bar."""
    length = int(getattr(section, "end")) - int(getattr(section, "start"))
    if length <= 0:
        return []
    steps = 2 if length <= 2 else 4
    roles = frame_roles(length)
    if len(roles) != length:
        raise ValueError(
            f"frame_roles({length}) returned {len(roles)} roles"
        )
    entries: list[tuple[str, str, int]] = []
    if length == 1:
        if figure.bars < 2:
            raise ValueError(
                f"{figure.id}: a one-bar frame needs a 2-bar short cell"
            )
        entries.append(("compressed", figure.cell_id, 0))
        used_tags.append(tag)
        return entries
    for role in roles:
        cell_bar = frame_role_bar(role, steps=steps)
        if cell_bar >= figure.bars:
            raise ValueError(
                f"{figure.id}: frame role {role} maps to cell bar {cell_bar}, "
                f"but the figure has {figure.bars} bars"
            )
        entries.append(("cell", figure.cell_id, cell_bar))
        used_tags.append(tag)
    return entries


def build_arrangement(
    *,
    pattern: str,
    meter: str,
    figures: Sequence[PatternFigure],
    form: FormSpec,
    policy: str = "auto_aaba",
    textures: Mapping[str, TextureSpec] | None = None,
    require_doors: bool = True,
    production: StudioProductionOptions | None = None,
) -> ArrangementResult:
    """Build a :class:`StudioPiece` for ``form`` from a tagged figure pool.

    ``textures`` maps a figure's ``cell_id`` to its authored
    :class:`TextureSpec`; the builder never reads ``TEXTURE_CELLS``. A missing
    texture is a hard error because the arrangement would otherwise name a cell
    the renderer cannot resolve.

    Invalid figure tags, missing required tags, duplicate optional tags, and
    gaps/overlaps between form sections all raise ``ValueError``. Missing
    optional body material is a warning, not an error.
    """
    pattern = _non_empty_string(pattern, "pattern")
    meter = _non_empty_string(meter, "meter")
    if policy not in ARRANGEMENT_POLICIES:
        raise ValueError(
            f"unknown arrangement policy {policy!r}; "
            f"expected one of {ARRANGEMENT_POLICIES}"
        )
    if not isinstance(figures, Sequence) or isinstance(figures, (str, bytes)):
        raise ValueError("figures must be a sequence")
    sections = getattr(form, "sections", None)
    form_bars = getattr(form, "bars", None)
    if sections is None or not isinstance(form_bars, int):
        raise ValueError("form must expose bars and sections")

    tags = _tag_map(figures, require_doors=require_doors)
    textures = {} if textures is None else textures

    ordered = sorted(sections, key=lambda section: int(section.start))
    cursor = 0
    for section in ordered:
        start = int(section.start)
        end = int(section.end)
        if start != cursor:
            raise ValueError(
                f"form sections must be contiguous; expected start {cursor}, "
                f"got {start}"
            )
        if end < start:
            raise ValueError(f"form section {start}..{end} is inverted")
        cursor = end
    if cursor != form_bars:
        raise ValueError(
            f"form sections cover {cursor} bars, form.bars is {form_bars}"
        )

    body_sections = [
        section for section in ordered if _section_group(section.kind) == "body"
    ]
    roles_by_phrase = _body_roles(body_sections, policy)
    warnings: list[str] = []
    used_tags: list[str] = []
    used_cells: dict[str, TextureSpec] = {}
    arrangement: list[tuple[str, str, int]] = []
    roles: list[str] = []
    body_index = 0

    for section in ordered:
        length = int(section.end) - int(section.start)
        group = _section_group(section.kind)
        if group in {"intro", "outro"}:
            short = length <= 2
            tag = f"{group}.{'short' if short else 'long'}"
            figure = tags[tag]
            _texture_for(figure, textures, used_cells)
            arrangement.extend(
                _door_entries(section, tag, figure, used_tags=used_tags)
            )
            continue

        role = roles_by_phrase[body_index]
        body_index += 1
        if length <= 0:
            continue
        if role == "close" and "close" not in tags:
            _warn(warnings, _WARN_CLOSE_FALLBACK)
            key = tags["key"]
            _texture_for(key, textures, used_cells)
            used_tags.append("key")
            for local_bar in range(length):
                if local_bar == length - 1:
                    arrangement.append(("cadence", "villa_cadence", 0))
                else:
                    arrangement.append(
                        ("cell", key.cell_id, local_bar % key.bars)
                    )
                roles.append(role)
            continue
        figure, tag = _body_figure(role, tags, warnings)
        _texture_for(figure, textures, used_cells)
        used_tags.append(tag)
        for local_bar in range(length):
            arrangement.append(
                ("cell", figure.cell_id, local_bar % figure.bars)
            )
            roles.append(role)

    piece = StudioPiece(
        pattern=pattern,
        meter=meter,
        cells=used_cells,
        arrangement=tuple(arrangement),
        production=production or StudioProductionOptions(),
    )
    errors = piece.validate()
    if errors:
        raise ValueError("invalid StudioPiece: " + "; ".join(errors))
    if len(arrangement) != form_bars:
        # The section walk should make this impossible; keep it explicit so a
        # caller can never export a piece shorter or longer than its form.
        raise ValueError(
            f"arrangement has {len(arrangement)} bars, form has {form_bars}"
        )

    deduped_tags: list[str] = []
    for tag in used_tags:
        if tag not in deduped_tags:
            deduped_tags.append(tag)

    return ArrangementResult(
        piece=piece,
        roles=tuple(roles),
        warnings=tuple(warnings),
        used_tags=tuple(deduped_tags),
    )
