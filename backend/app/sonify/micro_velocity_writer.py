"""Feature-gated production writer path for the extracted micro-velocity contours.

This module joins the data half (``app.sonify.micro_velocity_contours``) to the
figure writers it was extracted from. It is off unless
``VSTOCK_MICRO_VELOCITY_WRITERS`` is truthy, read at render time so a caller can
switch it without reloading modules. Off is the historical path: no event is
touched and every writer keeps its hardcoded levels.

On, each extracted family is written at its neutral level and the contour in
``micro_velocity_contours`` supplies the deltas before ``apply_guitar_wave``:

* Tremolo: neutral ``58`` plus ``TREMOLO_CONTOURS[meter]`` per bar.
* Étude No. 1: neutral ``52`` plus ``ETUDE1`` per bar.
* Étude No. 11: neutral ``44`` plus the ``etude11_middle`` rule, flattened from
  the bar's written lead hairpin and band.
* Galop 1/2: the bar's written peak plus the ``galop1``/``galop2`` rule,
  flattened from the same peak the hardcoded step table reads.

The rule flattener and every offset table stay in ``micro_velocity_contours``;
this module only chooses the neutral level, flattens, and applies. No offset
table is duplicated here.

Pinned entries are never applied by the relative path. The writer records each
contour occurrence while it renders, then :func:`check_occurrences` verifies the
absolute writers' result after ``apply_guitar_wave`` and ``_apply_fans``.

Import is inert: no figure registration or module-level render change.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Collection, Sequence
from contextvars import ContextVar
from dataclasses import replace

from app.sonify.model import NoteEvent
from app.studio.micro_velocity import (
    MicroVelocity,
    apply_relative_offsets,
    check_pinned_attacks,
)

__all__ = [
    "WRITERS_FLAG",
    "WriterContourError",
    "apply_etude1",
    "apply_etude11",
    "apply_galop",
    "apply_tremolo",
    "begin_occurrences",
    "check_occurrences",
    "record_occurrence",
    "reset_occurrences",
    "writers_enabled",
]

WRITERS_FLAG = "VSTOCK_MICRO_VELOCITY_WRITERS"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


class WriterContourError(ValueError):
    """A pinned contour entry does not match the post-wave writer output."""


def writers_enabled() -> bool:
    """True when the contour writer path is selected for this render.

    Read on every call. Unset, empty, ``0``, and any value outside
    ``1/true/yes/on`` mean off, which is the byte-identical historical path.
    """
    value = os.environ.get(WRITERS_FLAG)
    return value is not None and value.strip().lower() in _TRUTHY


# ---------------------------------------------------------------------------
# Occurrence tracking (pinned checks)
# ---------------------------------------------------------------------------

# Contours are written before the wave, but pinned entries describe velocities
# the absolute writers (snap/stab/fan/tremolo trim) produce afterwards. The
# contour occurrence is recorded here while the figure is written; the render
# then checks every pinned entry once the absolute writers have run.
_OCCURRENCES: ContextVar[list[tuple[MicroVelocity, int]] | None] = ContextVar(
    "micro_velocity_occurrences", default=None
)


def begin_occurrences() -> object:
    """Start collecting contour occurrences for the render in this context."""
    return _OCCURRENCES.set([])


def reset_occurrences(token: object) -> None:
    """Restore the previous occurrence collector (the matching begin token)."""
    _OCCURRENCES.reset(token)


def record_occurrence(contour: MicroVelocity, origin_bar: int) -> None:
    """Register one contour occurrence for the post-wave pinned check."""
    _record(contour, origin_bar)


def check_occurrences(events: Sequence[NoteEvent]) -> None:
    """Verify every recorded pinned entry against the final event list.

    Call after ``apply_guitar_wave`` and ``_apply_fans``. A default contour has
    no pinned entries, so this is a no-op for the extracted data; an authored
    contour that pins an absolute writer's attack is checked here instead of
    being silently applied as a relative offset.
    """
    occurrences = _OCCURRENCES.get()
    if not occurrences:
        return
    errors = []
    for contour, origin_bar in occurrences:
        errors.extend(
            check_pinned_attacks(events, contour, origin_bar=origin_bar)
        )
    if errors:
        raise WriterContourError("; ".join(str(error) for error in errors))


def _record(contour: MicroVelocity, origin_bar: int) -> None:
    occurrences = _OCCURRENCES.get()
    if occurrences is not None:
        occurrences.append((contour, origin_bar))


# ---------------------------------------------------------------------------
# Application helpers
# ---------------------------------------------------------------------------


def _neutralized(events: Sequence[NoteEvent], base: int) -> list[NoteEvent]:
    """Sound every attack at one written level; rests and flags are kept."""
    return [
        replace(event, velocity=base)
        if event.midi is not None and event.velocity is not None
        else event
        for event in events
    ]


def _apply_offsets(
    events: Sequence[NoteEvent],
    contour: MicroVelocity,
    *,
    origin_bar: int,
    base: int,
) -> list[NoteEvent]:
    return apply_relative_offsets(
        _neutralized(events, base), contour, origin_bar=origin_bar
    )


def _apply_offsets_per_bar(
    events: Sequence[NoteEvent],
    contour: MicroVelocity,
    *,
    base: int,
) -> list[NoteEvent]:
    """Apply a one-bar contour to every bar in the list, preserving order."""
    result = list(events)
    for bar in sorted({event.bar for event in result}):
        indexes = [
            index for index, event in enumerate(result) if event.bar == bar
        ]
        group = [result[index] for index in indexes]
        updated = _apply_offsets(group, contour, origin_bar=bar, base=base)
        for index, event in zip(indexes, updated):
            result[index] = event
    return result


def apply_tremolo(
    lead: Sequence[NoteEvent],
    support: Sequence[NoteEvent],
    low: Sequence[NoteEvent],
    *,
    meter_kind: str,
    bars: Collection[int] | None = None,
) -> tuple[list[NoteEvent], list[NoteEvent], list[NoteEvent]] | None:
    """Rewrite one tremolo render through its meter contour.

    ``None`` means the meter has no extracted contour (for example 6/8, whose
    cluster grid the one-bar 4/4/3/4 data does not address); the caller keeps
    the writer's own output for that meter. ``bars`` limits the recorded
    occurrences to the bars the render actually keeps.
    """
    from app.sonify.micro_velocity_contours import (
        NEUTRAL_LEVELS,
        TREMOLO_CONTOURS,
    )

    contour = TREMOLO_CONTOURS.get(meter_kind)
    if contour is None:
        return None
    base = NEUTRAL_LEVELS["tremolo"]
    rebuilt = tuple(
        _apply_offsets_per_bar(events, contour, base=base)
        for events in (lead, support, low)
    )
    played = set(bars) if bars is not None else {event.bar for event in rebuilt[0]}
    for bar in sorted(played):
        _record(contour, bar)
    return rebuilt


def apply_etude1(
    support: Sequence[NoteEvent], *, origin_bar: int
) -> list[NoteEvent]:
    """Rewrite one Étude No. 1 middle-voice bar through the fixed arch."""
    from app.sonify.micro_velocity_contours import ETUDE1, NEUTRAL_LEVELS

    rebuilt = _apply_offsets(
        support, ETUDE1, origin_bar=origin_bar, base=NEUTRAL_LEVELS["etude1"]
    )
    _record(ETUDE1, origin_bar)
    return rebuilt


def apply_etude11(
    support: Sequence[NoteEvent],
    *,
    origin_bar: int,
    hairpin_at: Callable[[NoteEvent], int | None],
    band_at: Callable[[NoteEvent], str | None],
) -> list[NoteEvent]:
    """Rewrite one Étude No. 11 middle-voice bar through the sextuplet rule."""
    from app.sonify.micro_velocity_contours import (
        ETUDE11,
        NEUTRAL_LEVELS,
        apply_flattened_rule,
    )

    base = NEUTRAL_LEVELS["etude11"]
    rebuilt = apply_flattened_rule(
        _neutralized(support, base),
        ETUDE11,
        origin_bar=origin_bar,
        base_at=lambda _event: base,
        hairpin_at=hairpin_at,
        band_at=band_at,
    )
    _record(ETUDE11, origin_bar)
    return rebuilt


def _galop_peak(events: Sequence[NoteEvent]) -> int | None:
    written = [
        event.velocity
        for event in events
        if event.midi is not None and event.velocity is not None
    ]
    return max(written) if written else None


def apply_galop(
    lead: Sequence[NoteEvent], low: Sequence[NoteEvent], *, rule_id: str
) -> tuple[list[NoteEvent], list[NoteEvent]]:
    """Rewrite one galop cell bar through its rule and the bar's written peak.

    This mirrors the historical contour functions: the peak is the loudest
    written lead attack, and each note is a number of two-step units under it,
    floored at ``_GALOP_FLOOR``. The step table lives in the flattened rule.
    """
    from app.sonify.micro_velocity_contours import (
        GALOP1,
        GALOP2,
        apply_flattened_rule,
    )

    contour = GALOP1 if rule_id == "galop1" else GALOP2
    peak = _galop_peak(lead)
    if peak is None:
        return list(lead), list(low)
    origin = lead[0].bar

    def flatten(events: Sequence[NoteEvent]) -> list[NoteEvent]:
        return apply_flattened_rule(
            events,
            contour,
            origin_bar=origin,
            peak=peak,
            base_at=lambda event: event.velocity,
        )

    _record(contour, origin)
    return flatten(lead), flatten(low)
