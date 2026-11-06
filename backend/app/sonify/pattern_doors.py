"""Compile tagged Studio figures into frame doors (Phase 4).

A Studio pattern draft tags four figures for the entrance and cadence frames:
``intro.short``/``outro.short`` (two bars) and ``intro.long``/``outro.long``
(four bars). :func:`compile_figure_doors` turns those four figures into the
callable shape :func:`app.sonify.guitar_frame._dispatch` already expects::

    door(ctx, bar, role, *, steps, closing, index) -> list[tuple]

The callable renders one authored bar of the selected cell with
:func:`app.sonify.texture_figure.render_texture_bar` and converts each
``NoteEvent`` back into the ``(offset, length, midi, voice, velocity, flags)``
tuple the frame realizer uses.

This module is a pure compiler plus a small runtime registry:

* importing it creates empty tables and reads nothing;
* :func:`register_studio_door` adds one ``(ensemble, pattern)`` door for
  :func:`app.sonify.guitar_frame._extra_doors` to merge;
* :func:`unregister_studio_door` removes it again.

It never writes ``_RETAINED_DOORS``, ``DOORS``, or ``SENTENCE_SPECS`` and
never mutates authored data.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.sonify.model import NoteEvent
from app.sonify.pattern_figures import (
    PatternFigure,
    figure_tag_errors,
    validate_figure_tags,
)
from app.sonify.texture_figure import TEXTURE_CELLS, render_texture_bar
from app.studio.texture_spec import TextureSpec

__all__ = [
    "DEFAULT_DOOR_VELOCITY",
    "STUDIO_DOORS",
    "compile_figure_doors",
    "frame_role_bar",
    "register_studio_door",
    "studio_doors",
    "unregister_studio_door",
]

#: The authored layer carries no velocity; the frame realizer needs an int.
#: The humanize pass can still move it afterwards.
DEFAULT_DOOR_VELOCITY = 56

#: ``(ensemble, pattern)`` -> door callable. Empty at import.
STUDIO_DOORS: dict[tuple[str, str], Callable[..., list[tuple]]] = {}

_FLAG_NAMES = (
    "tie_start",
    "tie_stop",
    "slur_start",
    "slur_stop",
    "accent",
    "tenuto",
    "staccato",
)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _non_empty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def frame_role_bar(role: int, *, steps: int) -> int:
    """The cell-local authored bar for one frame screenplay step.

    The short screenplay has two steps (``steps=2``) and the long one has four
    (``steps=4``); :func:`app.sonify.guitar_frame.frame_roles` chooses which
    step each frame bar plays. This helper only validates and maps that step to
    the 0-based cell bar, so a three-bar frame plays role ``0, 2, 3`` and a
    one-bar frame compresses roles ``0, 1``.
    """
    if not _is_int(steps) or steps not in (2, 4):
        raise ValueError("steps must be 2 or 4")
    if not _is_int(role) or not 0 <= role < steps:
        raise ValueError(f"role must be an integer in 0..{steps - 1}")
    return role


def _door_figure(
    figure: PatternFigure,
    tag: str,
    bars: int,
) -> PatternFigure:
    """Validate one tagged door figure and its required bar count."""
    if not isinstance(figure, PatternFigure):
        raise ValueError(f"{tag} figure must be a PatternFigure")
    errors = figure_tag_errors(figure.tags, figure.bars)
    if errors:
        raise ValueError(f"{figure.id}: {errors[0]}")
    if tag not in figure.tags:
        raise ValueError(f"{figure.id}: figure does not carry the {tag!r} tag")
    if figure.bars != bars:
        raise ValueError(f"{figure.id}: {tag!r} needs {bars} bars, got {figure.bars}")
    if not figure.cell_id:
        raise ValueError(f"{figure.id}: cell_id must be non-empty")
    validate_figure_tags(figure.tags, figure.bars)
    return figure


def _flags(event: NoteEvent) -> dict[str, bool]:
    return {
        name: True
        for name in _FLAG_NAMES
        if bool(getattr(event, name, False))
    }


def _event_spec(
    event: NoteEvent,
    *,
    epb: int,
    velocity: int,
) -> tuple[int, int, int, int, int, dict[str, bool]] | None:
    """One ``NoteEvent`` as a frame realizer spec, or ``None`` to skip it."""
    if event.midi is None:
        return None
    offset = int(round(event.beat * 2))
    if offset < 0 or offset >= epb:
        return None
    length = max(1, int(round(event.duration_beats * 2)))
    # A frame door owns exactly one bar. Never let a rendered note leak into
    # the next bar even if a caller authored a long duration.
    length = min(length, epb - offset)
    if length <= 0:
        return None
    if event.voice not in (1, 2, 3, 4):
        return None
    # Voice 4 is the authored upper middle; the frame realizer only knows 1-3.
    voice = event.voice if event.voice in (1, 2, 3) else 2
    return (
        offset,
        length,
        int(event.midi),
        voice,
        int(velocity),
        _flags(event),
    )


def _resolve_texture(
    pattern: str,
    meter: str,
    figure: PatternFigure,
) -> TextureSpec | None:
    table = TEXTURE_CELLS.get((pattern, meter))
    if not table:
        return None
    return table.get(figure.cell_id)


def compile_figure_doors(
    pattern: str,
    meter: str,
    intro_short: PatternFigure,
    intro_long: PatternFigure,
    outro_short: PatternFigure,
    outro_long: PatternFigure,
    *,
    velocity: int = DEFAULT_DOOR_VELOCITY,
) -> Callable[..., list[tuple]]:
    """Compile the four tagged figures into a frame door callable.

    The returned callable resolves the selected figure's ``cell_id`` in
    :data:`app.sonify.texture_figure.TEXTURE_CELLS` on every call, so a cell
    registered after compilation is still seen. A missing cell or authored bar
    returns ``[]`` and lets the frame silence stand instead of crashing.

    ``velocity`` is the fallback for authored notes, which carry no velocity.
    """
    pattern = _non_empty_string(pattern, "pattern")
    meter = _non_empty_string(meter, "meter")
    if not _is_int(velocity) or not 0 <= velocity <= 127:
        raise ValueError("velocity must be an integer in 0..127")

    doors = {
        (False, 2): _door_figure(intro_short, "intro.short", 2),
        (False, 4): _door_figure(intro_long, "intro.long", 4),
        (True, 2): _door_figure(outro_short, "outro.short", 2),
        (True, 4): _door_figure(outro_long, "outro.long", 4),
    }

    def door(
        ctx: Any,
        bar: int,
        role: int,
        *,
        steps: int,
        closing: bool,
        index: int,
    ) -> list[tuple]:
        del index
        cell_bar = frame_role_bar(role, steps=steps)
        figure = doors[(bool(closing), steps)]
        texture = _resolve_texture(pattern, meter, figure)
        if texture is None:
            return []
        lead, support, low = render_texture_bar(
            texture, ctx, bar, cell_bar=cell_bar
        )
        epb = int(getattr(ctx, "epb"))
        specs: list[tuple] = []
        for event in (*lead, *support, *low):
            spec = _event_spec(event, epb=epb, velocity=velocity)
            if spec is not None:
                specs.append(spec)
        return specs

    door.__name__ = f"studio_door_{pattern}"
    door.__doc__ = (
        f"Compiled Studio door for {pattern!r} in {meter!r}; "
        "reads TEXTURE_CELLS at call time."
    )
    return door


def _door_key(ensemble: str, pattern: str) -> tuple[str, str]:
    return (
        _non_empty_string(ensemble, "ensemble"),
        _non_empty_string(pattern, "pattern"),
    )


def register_studio_door(
    ensemble: str,
    pattern: str,
    door: Callable[..., list[tuple]],
    *,
    replace: bool = False,
) -> bool:
    """Add one door for ``_extra_doors`` to merge; return whether it changed.

    Re-registering the identical callable is a no-op. A different callable for
    the same key raises unless ``replace=True``.
    """
    key = _door_key(ensemble, pattern)
    if not callable(door):
        raise TypeError("door must be callable")
    if key not in STUDIO_DOORS:
        # A Studio promotion must never shadow a shipped pattern door. The
        # production door table is process-global; a request-local registration
        # would otherwise change playback for every user on this worker.
        from app.sonify import guitar_frame

        protected = key in guitar_frame._RETAINED_DOORS or key in guitar_frame._extra_doors()
        if protected:
            raise ValueError(
                f"{key} is a production door; Studio promotion cannot shadow it"
            )
    existing = STUDIO_DOORS.get(key)
    if existing is not None:
        if existing is door:
            return False
        if not replace:
            raise ValueError(f"a studio door is already registered for {key}")
    STUDIO_DOORS[key] = door
    return True


def unregister_studio_door(ensemble: str, pattern: str) -> bool:
    """Remove one registered door; return whether it was present."""
    key = _door_key(ensemble, pattern)
    return STUDIO_DOORS.pop(key, None) is not None


def studio_doors() -> Mapping[tuple[str, str], Callable[..., list[tuple]]]:
    """A shallow copy of the registered doors for the frame dispatcher."""
    return dict(STUDIO_DOORS)
