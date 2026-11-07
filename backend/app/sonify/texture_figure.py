"""Phase 4 runtime for authored texture cells.

A tagged Studio figure is a ``TextureSpec`` (see
``app.studio.texture_spec``). This module turns one of its bars into the
``(lead, support, low)`` shape the Suite gate already expects, so a
``SentenceSpec`` can use ``Slot(cell=...)`` outside a run cycle.

The module is deliberately small:

* :data:`TEXTURE_CELLS` maps ``(pattern, meter)`` to ``cell id -> TextureSpec``.
  Importing this module creates the empty table and reads nothing.
* :func:`bind_texture` rebinds only ``melody_eighth`` indexes. It does **not**
  move an authored event's ``bar``: ``authored_to_events(bar_offset=...)``
  owns that, and doing both would shift the figure twice.
* :func:`render_texture_bar` selects one authored bar, resolves pitch through
  :mod:`app.studio.texture_resolve`, clips any note at the target bar line,
  and clears tie/slur endpoints that would hang across the cell boundary.

It never imports ``guitar_patterns``, never registers a sentence, and never
mutates global render state. A missing cell returns ``None`` so the caller can
fall back to the historical path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any

from app.sonify.model import NoteEvent
from app.studio.texture_resolve import authored_to_events
from app.studio.texture_spec import AuthoredEvent, TextureSpec

__all__ = [
    "TEXTURE_CELLS",
    "bind_texture",
    "register_texture_cell",
    "render_texture_bar",
    "render_texture_cell",
    "unregister_texture_cell",
]

#: ``(pattern, meter)`` -> ``cell id -> TextureSpec``. Empty at import.
TEXTURE_CELLS: dict[tuple[str, str], dict[str, TextureSpec]] = {}

_EPSILON = 1e-9


@dataclass(frozen=True)
class _MeterView:
    """The only meter field ``authored_to_events`` needs."""

    quarter_beats: float


def register_texture_cell(
    pattern: str,
    meter: str,
    cell_id: str,
    texture: TextureSpec,
    *,
    replace: bool = False,
) -> bool:
    """Add one cell to the runtime table; return whether it was added.

    Re-registering the identical spec is a no-op, so ``importlib.reload`` keeps
    working. A different spec under the same id raises unless ``replace=True``.
    """
    if not isinstance(pattern, str) or not pattern:
        raise ValueError("pattern must be a non-empty string")
    if not isinstance(meter, str) or not meter:
        raise ValueError("meter must be a non-empty string")
    if not isinstance(cell_id, str) or not cell_id:
        raise ValueError("cell id must be a non-empty string")
    if not isinstance(texture, TextureSpec):
        raise TypeError("texture must be an app.studio.texture_spec.TextureSpec")

    table = TEXTURE_CELLS.setdefault((pattern, meter), {})
    existing = table.get(cell_id)
    if existing is not None:
        if existing == texture:
            return False
        if not replace:
            raise ValueError(
                f"texture cell {cell_id!r} is already registered for "
                f"{(pattern, meter)}"
            )
    table[cell_id] = texture
    return True


def unregister_texture_cell(pattern: str, meter: str, cell_id: str) -> bool:
    """Remove one cell, leaving the rest of the pattern table alone."""
    table = TEXTURE_CELLS.get((pattern, meter))
    if table is None or cell_id not in table:
        return False
    del table[cell_id]
    if not table:
        TEXTURE_CELLS.pop((pattern, meter), None)
    return True


def bind_texture(
    texture: TextureSpec,
    *,
    bar_offset: int,
    epb: int,
    pitch_eighth_offset: int = 0,
) -> TextureSpec:
    """Rebind ``melody_eighth`` indexes for a figure tiled at ``bar_offset``.

    ``melody_eighth`` is absolute inside ``ctx.melody``. Moving the figure to a
    later bar means its earlier eighth indexes must move with it. Authored
    ``bar`` is deliberately left alone: ``authored_to_events`` shifts that.

    ``pitch_eighth_offset`` moves only the pitch lookup, not the authored
    placement. The compressed one-bar frame uses it for its second half: that
    half is placed at beat ``cut`` but must read the melody after ``cut``, not
    the opening melody again.
    """
    if not isinstance(texture, TextureSpec):
        raise TypeError("texture must be a TextureSpec")
    if not isinstance(bar_offset, int) or isinstance(bar_offset, bool) or bar_offset < 0:
        raise ValueError("bar_offset must be an integer >= 0")
    if not isinstance(epb, int) or isinstance(epb, bool) or epb < 1:
        raise ValueError("epb must be an integer >= 1")
    if (
        not isinstance(pitch_eighth_offset, int)
        or isinstance(pitch_eighth_offset, bool)
        or pitch_eighth_offset < 0
    ):
        raise ValueError("pitch_eighth_offset must be an integer >= 0")

    shift = bar_offset * epb + pitch_eighth_offset
    if shift == 0:
        return texture
    events: list[AuthoredEvent] = []
    for event in texture.authored:
        if event.pitch.kind == "melody_eighth":
            eighth = (event.pitch.eighth or 0) + shift
            event = replace(event, pitch=replace(event.pitch, eighth=eighth))
        events.append(event)
    return replace(texture, authored=tuple(events))


def _meter_view(ctx: Any) -> _MeterView:
    quarter = getattr(ctx, "bar_beats", None)
    if not isinstance(quarter, (int, float)) or isinstance(quarter, bool) or quarter <= 0:
        kind = getattr(ctx, "kind", "")
        numerator, _, denominator = str(kind).partition("/")
        try:
            beats = int(numerator)
            beat_type = int(denominator)
        except ValueError:
            beats, beat_type = 4, 4
        quarter = beats * 4 / max(1, beat_type)
    return _MeterView(float(quarter))


def _clip_and_close(
    events: list[NoteEvent],
    quarter: float,
    *,
    starts_cell: bool,
    ends_cell: bool,
) -> list[NoteEvent]:
    """Clip to the target bar and clear endpoints at the cell edges.

    Nothing outside this bar is rendered by the call, so a note that would
    cross the bar line is shortened here. A tie/slur that leaves the cell at
    its first or last bar has no partner in this cell; keeping it would export
    as a dangling endpoint.
    """
    result: list[NoteEvent] = []
    for event in events:
        end = event.beat + event.duration_beats
        tie_start = event.tie_start
        tie_stop = event.tie_stop
        slur_start = event.slur_start
        slur_stop = event.slur_stop
        duration = event.duration_beats
        if end > quarter + _EPSILON:
            duration = max(quarter - event.beat, _EPSILON)
            end = event.beat + duration
            tie_start = False
            slur_start = False
        if starts_cell and event.beat <= _EPSILON:
            tie_stop = False
            slur_stop = False
        if ends_cell and end >= quarter - _EPSILON:
            tie_start = False
            slur_start = False
        if (
            duration != event.duration_beats
            or tie_start != event.tie_start
            or tie_stop != event.tie_stop
            or slur_start != event.slur_start
            or slur_stop != event.slur_stop
        ):
            event = replace(
                event,
                duration_beats=duration,
                tie_start=tie_start,
                tie_stop=tie_stop,
                slur_start=slur_start,
                slur_stop=slur_stop,
            )
        result.append(event)
    return result


def render_texture_bar(
    texture: TextureSpec,
    ctx: Any,
    target_bar: int,
    *,
    cell_bar: int = 0,
    pitch_eighth_offset: int = 0,
    max_beat: float | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]]:
    """One authored bar of ``texture`` as (lead, support, low).

    ``cell_bar`` selects the authored bar inside the cell (0-based). The
    selected events are reindexed to bar 0, rebound with ``bar_offset`` so
    ``melody_eighth`` follows the target bar, then placed at ``target_bar`` by
    ``authored_to_events``.

    ``pitch_eighth_offset`` shifts only the melody lookup. A compressed frame
    moves its second half by ``cut`` beats but still reads the melody from the
    second half of the target bar. ``max_beat`` drops source events the caller
    will discard before resolving them, so a shifted lookup cannot run past the
    melody just because the unused tail of the cell bar is still authored.
    """
    if not isinstance(texture, TextureSpec):
        raise TypeError("texture must be a TextureSpec")
    if not isinstance(target_bar, int) or isinstance(target_bar, bool) or target_bar < 0:
        raise ValueError("target_bar must be an integer >= 0")
    if not isinstance(cell_bar, int) or isinstance(cell_bar, bool) or cell_bar < 0:
        raise ValueError("cell_bar must be an integer >= 0")
    if (
        not isinstance(pitch_eighth_offset, int)
        or isinstance(pitch_eighth_offset, bool)
        or pitch_eighth_offset < 0
    ):
        raise ValueError("pitch_eighth_offset must be an integer >= 0")
    if max_beat is not None and (
        isinstance(max_beat, bool)
        or not isinstance(max_beat, (int, float))
        or not math.isfinite(float(max_beat))
        or float(max_beat) <= 0
    ):
        raise ValueError("max_beat must be a positive finite number or None")

    authored_bars = [event.bar for event in texture.authored]
    if cell_bar not in authored_bars:
        return [], [], []
    last_bar = max(authored_bars)

    selected = [
        replace(event, bar=0)
        for event in texture.authored
        if event.bar == cell_bar
        and (max_beat is None or event.beat < float(max_beat))
    ]
    cropped = replace(texture, authored=tuple(selected))
    bound = bind_texture(
        cropped,
        bar_offset=target_bar,
        epb=int(ctx.epb),
        pitch_eighth_offset=pitch_eighth_offset,
    )
    meter = _meter_view(ctx)
    events = _clip_and_close(
        authored_to_events(bound, ctx, meter, bar_offset=target_bar),
        meter.quarter_beats,
        starts_cell=cell_bar == 0,
        ends_cell=cell_bar == last_bar,
    )

    lead: list[NoteEvent] = []
    support: list[NoteEvent] = []
    low: list[NoteEvent] = []
    for event in events:
        if event.voice == 1:
            lead.append(event)
        elif event.voice in (2, 4):
            support.append(event)
        elif event.voice == 3:
            low.append(event)
    return lead, support, low


def render_texture_cell(
    ctx: Any,
    bar: int,
    phrase: Any,
    cell_id: str,
    cell_bar: int,
    pattern: str,
    meter: str,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]] | None:
    """Resolve ``cell_id`` in :data:`TEXTURE_CELLS` and render one bar.

    ``phrase`` is accepted for the Suite gate's call shape and is unused: a
    cell is bar-written data, not a phrase-selected figure. A missing table
    entry returns ``None`` so the caller falls back instead of crashing.
    """
    del phrase
    table = TEXTURE_CELLS.get((pattern, meter))
    if not table:
        return None
    texture = table.get(cell_id)
    if texture is None:
        return None
    return render_texture_bar(texture, ctx, bar, cell_bar=cell_bar)
