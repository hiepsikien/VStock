"""Optional authored micro-velocity contours.

This module owns the data half of ``docs/sonify-texture-studio.md`` §6.9: the
per-note velocity contour that a figure, sentence slot, or texture may carry.
It is deliberately not a registry, a compiler, or a renderer:

* A contour is either ``kind: "offsets"`` with per-note deltas, or
  ``kind: "rule"`` with the rule id/version/params that the Studio flattens
  into per-note offsets for the selected fixture.
* Coordinates are relative to the figure/slot: ``bar`` (0-based) and
  ``beat`` (0-based quarter-note beat inside that bar). ``beat`` addresses
  every attack, including sixteenths (``0.25``) and triplets. Never absolute
  song positions; ``apply_relative_offsets`` shifts bars with
  ``origin_bar`` when the figure starts later.
* A contour is a delta, not a velocity. Only ``pinned`` entries store an
  absolute velocity, and those attacks belong to the absolute writers
  (snap/stab/fan/tremolo trim). ``apply_relative_offsets`` therefore skips
  pinned entries; ``check_pinned_attacks`` verifies them after the wave.
* No contour, and a canonical empty contour, are the zero-diff path: every
  ``NoteEvent`` stays byte-identical.

Parsing raises :class:`MicroVelocitySpecError` (a ``ValueError``) carrying the
JSON path. :func:`validate_micro_velocity` returns the same failures as
:class:`MicroVelocityError` records instead of raising.

Importing this module imports ``app.sonify.model`` only. It never imports
``guitar_patterns``, registers a figure/sentence, or changes runtime code.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from app.sonify.model import NoteEvent

__all__ = [
    "BEAT_EPSILON",
    "EMPTY_MICRO_VELOCITY",
    "FINGERS",
    "KINDS",
    "THUMB_VOICE",
    "MicroVelocity",
    "MicroVelocityError",
    "MicroVelocitySpecError",
    "VelocityOffset",
    "apply_relative_offsets",
    "check_pinned_attacks",
    "is_empty",
    "micro_velocity_to_mapping",
    "parse_micro_velocity",
    "validate_micro_velocity",
]

KINDS = ("offsets", "rule")
FINGERS = ("p", "a", "m", "i")
THUMB_VOICE = 3
VELOCITY_MIN = 1
VELOCITY_MAX = 127
# Matching tolerance between an entry beat and a NoteEvent beat. Authors and
# renderers both use binary floats, so exact equality would miss values such
# as 1/3 or 0.1 + 0.2.
BEAT_EPSILON = 1e-6

_TOP_KEYS = frozenset({"kind", "notes", "thumb", "ruleId", "ruleVersion", "params"})
_ENTRY_KEYS = frozenset({"bar", "beat", "voice", "finger", "offset", "pinned", "velocity"})
_ENTRY_REQUIRED = frozenset({"bar", "beat"})


# ---------------------------------------------------------------------------
# Error records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MicroVelocityError:
    """One validation failure, addressed at an authored JSON path."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


class MicroVelocitySpecError(ValueError):
    """A micro-velocity mapping could not be parsed into typed values."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VelocityOffset:
    """One contour entry.

    ``bar`` is 0-based relative to the figure or slot. ``beat`` is the 0-based
    quarter-note beat inside that bar, so sixteenths (``0.25``), eighths
    (``0.5``) and triplets are all addressable. ``voice`` is 1..4. An absent
    ``finger`` means the entry applies by ``(bar, beat, voice)`` regardless of
    finger.

    Exactly one of ``offset`` (a delta) or ``pinned=True`` + ``velocity`` (the
    absolute velocity an absolute writer will produce) is meaningful.
    """

    bar: int
    beat: float
    voice: int
    finger: str | None = None
    offset: int | None = None
    pinned: bool = False
    velocity: int | None = None

    def key(self) -> tuple[int, float, int, str | None]:
        """Coordinate identity used for duplicate detection.

        ``beat`` is rounded to the matching tolerance so ``0.5`` and
        ``0.5000001`` cannot both claim the same attack.
        """
        return (self.bar, round(float(self.beat), 6), self.voice, self.finger)

    def to_mapping(self) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            "bar": self.bar,
            "beat": self.beat,
            "voice": self.voice,
        }
        if self.finger is not None:
            mapping["finger"] = self.finger
        if self.pinned:
            mapping["pinned"] = True
            mapping["velocity"] = self.velocity
        else:
            mapping["offset"] = self.offset
        return mapping

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, path: str = "note", thumb: bool = False
    ) -> "VelocityOffset":
        return _parse_offset(mapping, path, thumb=thumb)


@dataclass(frozen=True)
class MicroVelocity:
    """An authored contour: per-note offsets or a named rule."""

    kind: str = "offsets"
    notes: tuple[VelocityOffset, ...] = ()
    thumb: tuple[VelocityOffset, ...] = ()
    rule_id: str | None = None
    rule_version: int | None = None
    params: Mapping[str, Any] | None = None

    def to_mapping(self) -> dict[str, Any]:
        return micro_velocity_to_mapping(self)

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, path: str = "micro_velocity"
    ) -> "MicroVelocity":
        return parse_micro_velocity(mapping, path=path)


# The canonical "no contour" value. It is accepted by ``is_empty`` and
# ``validate_micro_velocity`` but is not an authored mapping: parsing rejects
# an offsets contour with no notes, so authors either omit the field or list
# at least one entry.
EMPTY_MICRO_VELOCITY = MicroVelocity(kind="offsets")


def is_empty(value: MicroVelocity | None) -> bool:
    """True when a contour carries no authored data (the zero-diff path)."""
    if value is None:
        return True
    if not isinstance(value, MicroVelocity):
        return False
    return (
        value.kind == "offsets"
        and not value.notes
        and not value.thumb
        and value.rule_id is None
        and value.rule_version is None
        and value.params is None
    )


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse_micro_velocity(
    mapping: Mapping[str, Any], *, path: str = "micro_velocity"
) -> MicroVelocity:
    """Build a :class:`MicroVelocity` from its JSON mapping.

    Structural errors raise :class:`MicroVelocitySpecError` naming the path;
    cross-field rules then run through :func:`validate_micro_velocity` and the
    first failure is raised the same way. This never touches a registry.
    """
    data = _mapping(mapping, path)
    unknown = set(data) - _TOP_KEYS
    if unknown:
        raise MicroVelocitySpecError(path, f"unknown field(s) {sorted(unknown)}")

    kind = _string(data.get("kind"), f"{path}.kind")
    notes = _parse_offsets(data.get("notes", []), f"{path}.notes", thumb=False)
    thumb = _parse_offsets(data.get("thumb", []), f"{path}.thumb", thumb=True)

    rule_id = data.get("ruleId")
    if rule_id is not None:
        rule_id = _non_empty_string(rule_id, f"{path}.ruleId")
    rule_version = _optional_integer(data.get("ruleVersion"), f"{path}.ruleVersion")
    params = data.get("params")
    if params is not None:
        params = dict(_mapping(params, f"{path}.params"))

    value = MicroVelocity(
        kind=kind,
        notes=notes,
        thumb=thumb,
        rule_id=rule_id,
        rule_version=rule_version,
        params=params,
    )
    errors = validate_micro_velocity(value, path=path)
    if errors:
        raise MicroVelocitySpecError(errors[0].path, errors[0].message)
    return value


def _parse_offsets(value: Any, path: str, *, thumb: bool) -> tuple[VelocityOffset, ...]:
    if not isinstance(value, (list, tuple)):
        raise MicroVelocitySpecError(path, "expected a list")
    return tuple(
        _parse_offset(_mapping(raw, f"{path}[{index}]"), f"{path}[{index}]", thumb=thumb)
        for index, raw in enumerate(value)
    )


def _parse_offset(mapping: Mapping[str, Any], path: str, *, thumb: bool) -> VelocityOffset:
    data = _mapping(mapping, path)
    unknown = set(data) - _ENTRY_KEYS
    if unknown:
        raise MicroVelocitySpecError(path, f"unknown field(s) {sorted(unknown)}")
    missing = _ENTRY_REQUIRED - set(data)
    if missing:
        raise MicroVelocitySpecError(path, f"missing field(s) {sorted(missing)}")

    bar = _integer(data["bar"], f"{path}.bar")
    beat = _number(data["beat"], f"{path}.beat")
    if thumb:
        voice = _integer(data.get("voice", THUMB_VOICE), f"{path}.voice")
    else:
        if "voice" not in data:
            raise MicroVelocitySpecError(path, "missing field(s) ['voice']")
        voice = _integer(data["voice"], f"{path}.voice")
    finger = _optional_string(data.get("finger"), f"{path}.finger")
    offset = _optional_integer(data.get("offset"), f"{path}.offset")
    pinned = _boolean(data.get("pinned", False), f"{path}.pinned")
    velocity = _optional_integer(data.get("velocity"), f"{path}.velocity")

    return VelocityOffset(
        bar=bar,
        beat=beat,
        voice=voice,
        finger=finger,
        offset=offset,
        pinned=pinned,
        velocity=velocity,
    )


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def validate_micro_velocity(
    value: MicroVelocity,
    *,
    bars: int | None = None,
    beats_per_bar: float | None = None,
    path: str = "micro_velocity",
) -> tuple[MicroVelocityError, ...]:
    """Return every offline violation of a contour.

    ``bars`` and ``beats_per_bar`` are optional figure/slot bounds. Coordinate
    overflow is context-dependent, so it is only checked when the caller passes
    the span and meter it wants to bound. ``path`` prefixes every error so a
    caller can report ``slots[1].microVelocity.notes[0].bar``.
    """
    errors: list[MicroVelocityError] = []
    if not isinstance(value, MicroVelocity):
        return (MicroVelocityError(path, "expected a MicroVelocity"),)

    if value is EMPTY_MICRO_VELOCITY:
        # The canonical empty contour is the zero-diff sentinel, not authored
        # JSON: parsing still rejects ``{"kind": "offsets", "notes": []}``.
        return ()

    if value.kind not in KINDS:
        return (MicroVelocityError(f"{path}.kind", f"unknown value {value.kind!r}"),)

    if bars is not None and (not _is_int(bars) or bars < 0):
        errors.append(MicroVelocityError("bars", "must be an integer >= 0"))
    if beats_per_bar is not None and (
        not _is_number(beats_per_bar) or beats_per_bar <= 0
    ):
        errors.append(
            MicroVelocityError("beats_per_bar", "must be a finite number > 0")
        )

    if value.kind == "rule":
        if not isinstance(value.rule_id, str) or not value.rule_id:
            errors.append(
                MicroVelocityError(f"{path}.ruleId", "kind 'rule' requires a rule id")
            )
        if not _is_int(value.rule_version) or value.rule_version < 1:
            errors.append(
                MicroVelocityError(
                    f"{path}.ruleVersion",
                    "kind 'rule' requires a rule version >= 1",
                )
            )
        if not isinstance(value.params, Mapping):
            errors.append(
                MicroVelocityError(f"{path}.params", "kind 'rule' requires params")
            )
        elif not value.params:
            errors.append(
                MicroVelocityError(f"{path}.params", "kind 'rule' requires non-empty params")
            )
    else:
        if value.rule_id is not None:
            errors.append(
                MicroVelocityError(
                    f"{path}.ruleId", "field 'ruleId' is only valid for kind 'rule'"
                )
            )
        if value.rule_version is not None:
            errors.append(
                MicroVelocityError(
                    f"{path}.ruleVersion",
                    "field 'ruleVersion' is only valid for kind 'rule'",
                )
            )
        if value.params is not None:
            errors.append(
                MicroVelocityError(
                    f"{path}.params", "field 'params' is only valid for kind 'rule'"
                )
            )
        if not value.notes:
            errors.append(
                MicroVelocityError(
                    f"{path}.notes", "kind 'offsets' requires at least one note entry"
                )
            )

    notes = value.notes
    if not isinstance(notes, (tuple, list)):
        errors.append(MicroVelocityError(f"{path}.notes", "expected a list"))
        notes = ()
    thumb = value.thumb
    if not isinstance(thumb, (tuple, list)):
        errors.append(MicroVelocityError(f"{path}.thumb", "expected a list"))
        thumb = ()

    seen: dict[tuple[int, float, int, str | None], str] = {}
    for lane, entries in (("notes", notes), ("thumb", thumb)):
        for index, entry in enumerate(entries):
            item = f"{path}.{lane}[{index}]"
            entry_errors, key = _offset_errors(
                entry, item, bars=bars, beats_per_bar=beats_per_bar
            )
            errors.extend(entry_errors)
            if key is None:
                continue
            previous = seen.get(key)
            if previous is not None:
                errors.append(
                    MicroVelocityError(
                        item,
                        f"duplicate key {key} (also at {previous})",
                    )
                )
            else:
                seen[key] = item
    return tuple(errors)


def _offset_errors(
    entry: Any,
    path: str,
    *,
    bars: int | None,
    beats_per_bar: float | None,
) -> tuple[list[MicroVelocityError], tuple[int, float, int, str | None] | None]:
    errors: list[MicroVelocityError] = []
    if not isinstance(entry, VelocityOffset):
        return [MicroVelocityError(path, "expected a VelocityOffset")], None

    key_ok = True
    if not _is_int(entry.bar) or entry.bar < 0:
        errors.append(MicroVelocityError(f"{path}.bar", "must be an integer >= 0"))
        key_ok = False
    elif bars is not None and _is_int(bars) and bars >= 0 and entry.bar >= bars:
        errors.append(
            MicroVelocityError(
                f"{path}.bar", f"bar {entry.bar} is outside figure length {bars}"
            )
        )
    if not _is_number(entry.beat) or entry.beat < 0:
        errors.append(
            MicroVelocityError(
                f"{path}.beat", "must be a finite number >= 0"
            )
        )
        key_ok = False
    elif (
        beats_per_bar is not None
        and _is_number(beats_per_bar)
        and beats_per_bar > 0
        and entry.beat >= beats_per_bar
    ):
        errors.append(
            MicroVelocityError(
                f"{path}.beat",
                f"beat {entry.beat} is outside bar length {beats_per_bar}",
            )
        )
    if not _is_int(entry.voice) or not 1 <= entry.voice <= 4:
        errors.append(MicroVelocityError(f"{path}.voice", "must be 1..4"))
        key_ok = False
    if entry.finger is not None and entry.finger not in FINGERS:
        errors.append(
            MicroVelocityError(
                f"{path}.finger", f"unknown finger {entry.finger!r}; expected one of {FINGERS}"
            )
        )

    if not isinstance(entry.pinned, bool):
        errors.append(MicroVelocityError(f"{path}.pinned", "must be a boolean"))
    if entry.pinned:
        if entry.offset is not None:
            errors.append(
                MicroVelocityError(
                    f"{path}.offset", "offset is not allowed when pinned is true"
                )
            )
        if not _is_int(entry.velocity):
            errors.append(
                MicroVelocityError(
                    f"{path}.velocity", "pinned attack requires an integer velocity"
                )
            )
        elif not VELOCITY_MIN <= entry.velocity <= VELOCITY_MAX:
            errors.append(
                MicroVelocityError(
                    f"{path}.velocity",
                    f"velocity must be in {VELOCITY_MIN}..{VELOCITY_MAX}",
                )
            )
    else:
        if entry.offset is None:
            errors.append(
                MicroVelocityError(
                    f"{path}.offset",
                    "exactly one of offset or pinned+velocity is required",
                )
            )
        elif not _is_int(entry.offset):
            errors.append(MicroVelocityError(f"{path}.offset", "must be an integer"))
        if entry.velocity is not None:
            errors.append(
                MicroVelocityError(
                    f"{path}.velocity", "velocity is only valid when pinned is true"
                )
            )

    key = entry.key() if key_ok else None
    return errors, key


# ---------------------------------------------------------------------------
# Serialize
# ---------------------------------------------------------------------------


def micro_velocity_to_mapping(value: MicroVelocity) -> dict[str, Any]:
    """Return the canonical JSON mapping for a contour.

    ``notes`` and ``thumb`` are always emitted (empty lists included) so the
    round-trip is deterministic. Rule fields appear only for ``kind: "rule"``.
    """
    if not isinstance(value, MicroVelocity):
        raise TypeError("value must be a MicroVelocity")
    mapping: dict[str, Any] = {
        "kind": value.kind,
        "notes": [
            entry.to_mapping() if isinstance(entry, VelocityOffset) else copy.deepcopy(entry)
            for entry in value.notes
        ],
        "thumb": [
            entry.to_mapping() if isinstance(entry, VelocityOffset) else copy.deepcopy(entry)
            for entry in value.thumb
        ],
    }
    if value.kind == "rule":
        mapping["ruleId"] = value.rule_id
        mapping["ruleVersion"] = value.rule_version
        mapping["params"] = (
            copy.deepcopy(dict(value.params)) if isinstance(value.params, Mapping) else None
        )
    return mapping


# ---------------------------------------------------------------------------
# Apply (relative) and check (pinned absolute)
# ---------------------------------------------------------------------------


def apply_relative_offsets(
    events: Sequence[NoteEvent],
    contour: MicroVelocity | None,
    *,
    origin_bar: int = 0,
    finger_at: Callable[[NoteEvent], str | None] | None = None,
) -> list[NoteEvent]:
    """Return a new event list with authored relative offsets applied.

    A contour coordinate ``(bar, beat, voice)`` matches the event whose local
    start is that bar and whose beat is within :data:`BEAT_EPSILON` after
    subtracting ``origin_bar`` from ``event.bar``. ``beat`` is already relative
    within the bar, so an entry at ``0.25`` addresses a sixteenth exactly. An
    entry without ``finger`` matches every finger; an entry with ``finger``
    matches only when ``finger_at`` resolves that event to the same finger. A
    finger-specific entry wins over the finger-agnostic entry for the same
    coordinate.

    Only non-pinned entries add their delta, and the result is clamped to
    1..127. Pinned entries are ignored here; they are verified by
    :func:`check_pinned_attacks` after the absolute writers run. The input
    list and its events are never mutated. With no contour (or an empty one)
    the returned list is a shallow copy with identical events.
    """
    result = list(events)
    if is_empty(contour):
        return result
    if not _is_int(origin_bar):
        raise ValueError("origin_bar must be an integer")

    general: list[VelocityOffset] = []
    by_finger: dict[str, list[VelocityOffset]] = {}
    for entry in _entries(contour):
        if entry.pinned or entry.offset is None:
            continue
        if entry.finger is None:
            general.append(entry)
        else:
            by_finger.setdefault(entry.finger, []).append(entry)
    if not general and not by_finger:
        return result

    for index, event in enumerate(result):
        if not isinstance(event, NoteEvent):
            continue
        if event.midi is None or event.velocity is None:
            continue
        target_bar = event.bar - origin_bar
        delta = None
        if finger_at is not None:
            finger = finger_at(event)
            if finger is not None:
                delta = _offset_at(
                    by_finger.get(finger, ()), target_bar, event.beat, event.voice
                )
        if delta is None:
            delta = _offset_at(general, target_bar, event.beat, event.voice)
        if delta is None or delta == 0:
            continue
        velocity = max(VELOCITY_MIN, min(VELOCITY_MAX, int(event.velocity) + int(delta)))
        result[index] = replace(event, velocity=velocity)
    return result


def check_pinned_attacks(
    events: Sequence[NoteEvent],
    contour: MicroVelocity | None,
    *,
    origin_bar: int = 0,
    finger_at: Callable[[NoteEvent], str | None] | None = None,
    path: str = "micro_velocity",
) -> tuple[MicroVelocityError, ...]:
    """Verify that every pinned entry matches the final event velocity.

    Run this after ``apply_guitar_wave`` and the absolute writers. It never
    applies or rewrites an entry; a missing attack or a different velocity is
    reported as a path-shaped error. Matching uses the same bar subtraction
    and :data:`BEAT_EPSILON` beat tolerance as :func:`apply_relative_offsets`.
    """
    if is_empty(contour):
        return ()
    if not _is_int(origin_bar):
        raise ValueError("origin_bar must be an integer")

    errors: list[MicroVelocityError] = []
    lanes = []
    if isinstance(contour.notes, (tuple, list)):
        lanes.append((contour.notes, "notes"))
    if isinstance(contour.thumb, (tuple, list)):
        lanes.append((contour.thumb, "thumb"))
    for entries, lane in lanes:
        for index, entry in enumerate(entries):
            if not isinstance(entry, VelocityOffset) or not entry.pinned:
                continue
            item = f"{path}.{lane}[{index}]"
            matches = [
                event
                for event in events
                if isinstance(event, NoteEvent)
                and event.bar - origin_bar == entry.bar
                and event.voice == entry.voice
                and _beat_matches(entry.beat, event.beat)
                and _finger_matches(entry, event, finger_at)
            ]
            if not matches:
                errors.append(
                    MicroVelocityError(
                        f"{item}.velocity",
                        f"pinned attack (bar {entry.bar}, beat {entry.beat}, "
                        f"voice {entry.voice}) has no matching event",
                    )
                )
                continue
            for event in matches:
                if event.velocity != entry.velocity:
                    errors.append(
                        MicroVelocityError(
                            f"{item}.velocity",
                            f"pinned velocity {entry.velocity} != event velocity "
                            f"{event.velocity}",
                        )
                    )
    return tuple(errors)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _entries(value: MicroVelocity) -> tuple[VelocityOffset, ...]:
    notes = tuple(value.notes) if isinstance(value.notes, (tuple, list)) else ()
    thumb = tuple(value.thumb) if isinstance(value.thumb, (tuple, list)) else ()
    return tuple(
        entry for entry in notes + thumb if isinstance(entry, VelocityOffset)
    )


def _offset_at(
    entries: Sequence[VelocityOffset], bar: int, beat: float, voice: int
) -> int | None:
    for entry in entries:
        if (
            entry.bar == bar
            and entry.voice == voice
            and _beat_matches(entry.beat, beat)
        ):
            return entry.offset
    return None


def _beat_matches(entry_beat: float, event_beat: float) -> bool:
    try:
        return abs(float(entry_beat) - float(event_beat)) <= BEAT_EPSILON
    except (TypeError, ValueError):
        return False


def _finger_matches(
    entry: VelocityOffset,
    event: NoteEvent,
    finger_at: Callable[[NoteEvent], str | None] | None,
) -> bool:
    if entry.finger is None:
        return True
    if finger_at is None:
        return False
    return finger_at(event) == entry.finger


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MicroVelocitySpecError(path, "expected an object")
    return dict(value)


def _integer(value: Any, path: str) -> int:
    if not _is_int(value):
        raise MicroVelocitySpecError(path, "expected an integer")
    return value


def _number(value: Any, path: str) -> float:
    if not _is_number(value):
        raise MicroVelocitySpecError(path, "expected a finite number")
    return float(value)


def _optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _integer(value, path)


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise MicroVelocitySpecError(path, "expected a string")
    return value


def _non_empty_string(value: Any, path: str) -> str:
    text = _string(value, path)
    if not text:
        raise MicroVelocitySpecError(path, "expected a non-empty string")
    return text


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise MicroVelocitySpecError(path, "expected a boolean")
    return value
