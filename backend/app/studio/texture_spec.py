"""Bounded Phase 0 schema for Texture Studio specs.

This module owns the *data* half of Phase 0 from
``docs/sonify-texture-studio.md``: a meter spec that stores all six
``form.Meter`` fields, declarative pitch references, authored events, and a
bounded ``TextureSpec`` with offline validation and a JSON round-trip.

It is deliberately not a compiler, an interpreter, a registry, or a renderer:

* ``parse_*`` functions only turn mappings into frozen values. Cross-field
  rules live in the ``validate_*`` functions, which return ``TextureError``
  records so one call can report every problem.
* Importing this module imports ``app.sonify.form`` only. It never imports
  ``guitar_patterns``, registers a pattern/sentence, or changes runtime code.
* Fields that need a render context (resolved MIDI, register, hand span,
  string/fret playability, velocity) stay declarative. They are checked only
  where an offline rule exists.

Errors raised by parsing are ``TextureSpecError`` (a ``ValueError``) carrying
the authored JSON path, for example ``meter_variants[0].meter``.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.sonify.form import Meter

__all__ = [
    "KINDS",
    "LEVELS",
    "MIN_PUBLISH_CONFIDENCE",
    "PITCH_KINDS",
    "REVIEW_VALUES",
    "RUNTIMES",
    "STATUSES",
    "TIE_VALUES",
    "SLUR_VALUES",
    "TRANSFORMS",
    "AuthoredEvent",
    "MeterSpec",
    "MeterVariant",
    "PitchRef",
    "TextureError",
    "TextureSpec",
    "TextureSpecError",
    "check_texture_spec",
    "meter_key",
    "meter_spec_to_mapping",
    "parse_meter_spec",
    "parse_texture_spec",
    "publishable",
    "texture_spec_to_mapping",
    "validate_authored",
    "validate_pitch_ref",
    "validate_texture_spec",
]

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

PITCH_KINDS = (
    "melody_eighth",
    "chord_degree",
    "chord_root",
    "scale_step",
    "literal_midi",
)

# Fields that are meaningful for each pitch kind. Everything else is rejected
# rather than silently carried along.
PITCH_FIELDS: dict[str, tuple[str, ...]] = {
    "melody_eighth": ("eighth", "offset"),
    "chord_degree": ("degree",),
    "chord_root": (),
    "scale_step": ("steps",),
    "literal_midi": ("value",),
}

PITCH_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "melody_eighth": ("eighth",),
    "chord_degree": ("degree",),
    "chord_root": (),
    "scale_step": ("steps",),
    "literal_midi": ("value",),
}

KINDS = ("pattern", "sentence")
LEVELS = ("topic", "texture")
RUNTIMES = ("code", "interpreter")
STATUSES = ("draft", "reviewed", "published")
REVIEW_VALUES = ("pending", "accepted", "edited")
TRANSFORMS = ("none", "triplet_subdivision")

TIE_VALUES = ("none", "start", "stop", "continue", "next_bar")
SLUR_VALUES = ("none", "start", "stop", "continue")

MIN_PUBLISH_CONFIDENCE = 0.6

# String/fret playability by string needs the runtime fret table and render
# context, so only the string range and fret lower bound are checked offline.

_TOP_KEYS = frozenset(
    {
        "id",
        "composer",
        "kind",
        "level",
        "parent",
        "runtime",
        "status",
        "source",
        "meter_variants",
        "authored",
        "derived",
        "routing",
        "traits",
        "selection",
        "provenance",
    }
)
_REQUIRED_TOP_KEYS = frozenset(
    {"id", "composer", "kind", "level", "runtime", "status", "meter_variants"}
)
_METER_KEYS = frozenset(
    {
        "id",
        "beats",
        "beat_type",
        "eighths_per_bar",
        "strong_eighths",
        "subbar_breaks",
        "extra_weights",
    }
)
_METER_REQUIRED = frozenset(
    {
        "id",
        "beats",
        "beat_type",
        "eighths_per_bar",
        "strong_eighths",
        "subbar_breaks",
    }
)
_VARIANT_KEYS = frozenset(
    {"meter", "materializer", "transform", "unsupported", "reason", "sentences"}
)
_AUTHORED_KEYS = frozenset({"events"})
_EVENT_REQUIRED = frozenset({"bar", "beat", "duration_beats", "voice", "pitch"})
_EVENT_KEYS = _EVENT_REQUIRED | frozenset(
    {
        "staff",
        "tie",
        "slur",
        "accent",
        "tenuto",
        "staccato",
        "string",
        "fret",
        "written_pitch",
        "sounding_pitch",
        "confidence",
        "conflict",
        "review",
    }
)
_EPSILON = 1e-9


# ---------------------------------------------------------------------------
# Error records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TextureError:
    """One validation failure, addressed at an authored JSON path."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


class TextureSpecError(ValueError):
    """A texture mapping could not be parsed into typed values."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}" if path else message)


# ---------------------------------------------------------------------------
# MeterSpec
# ---------------------------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


@dataclass(frozen=True)
class MeterSpec:
    """The six ``form.Meter`` fields plus a display-only ``id``.

    ``id`` is never identity. Use :meth:`key` (the canonical tuple) for every
    comparison and for registry/variant uniqueness.
    """

    id: str
    beats: int
    beat_type: int
    eighths_per_bar: int
    strong_eighths: tuple[int, ...]
    subbar_breaks: tuple[int, ...]
    extra_weights: tuple[tuple[int, float], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise ValueError("id must be a string")
        for name in ("beats", "beat_type", "eighths_per_bar"):
            value = getattr(self, name)
            if not _is_int(value) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.beats * 8 != self.eighths_per_bar * self.beat_type:
            raise ValueError(
                "eighths_per_bar must equal beats * 8 / beat_type "
                f"({self.beats} * 8 != {self.eighths_per_bar} * {self.beat_type})"
            )
        strong = _int_tuple(self.strong_eighths, "strong_eighths")
        breaks = _int_tuple(self.subbar_breaks, "subbar_breaks")
        for value in strong:
            if not 0 <= value < self.eighths_per_bar:
                raise ValueError("strong_eighths values must be inside the bar")
        for value in breaks:
            if not 0 <= value < self.eighths_per_bar:
                raise ValueError("subbar_breaks values must be inside the bar")
        weights: list[tuple[int, float]] = []
        raw_weights = self.extra_weights
        if not isinstance(raw_weights, (tuple, list)):
            raise ValueError("extra_weights must be a sequence")
        for pair in raw_weights:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError("extra_weights entries must be [eighth, weight]")
            eighth, weight = pair
            if not _is_int(eighth):
                raise ValueError("extra_weights eighth must be an integer")
            if not 0 <= eighth < self.eighths_per_bar:
                raise ValueError("extra_weights eighth must be inside the bar")
            if not _is_number(weight):
                raise ValueError("extra_weights weight must be a finite number")
            weights.append((eighth, float(weight)))
        object.__setattr__(self, "strong_eighths", strong)
        object.__setattr__(self, "subbar_breaks", breaks)
        object.__setattr__(self, "extra_weights", tuple(weights))

    @property
    def quarter_beats(self) -> float:
        """Bar length in quarter notes: ``eighths_per_bar / 2``."""
        return self.eighths_per_bar / 2

    def key(self) -> tuple[int, int, int, tuple[int, ...], tuple[int, ...], tuple[tuple[int, float], ...]]:
        """Canonical identity. ``id`` is deliberately not part of it."""
        return (
            self.beats,
            self.beat_type,
            self.eighths_per_bar,
            self.strong_eighths,
            self.subbar_breaks,
            self.extra_weights,
        )

    @classmethod
    def from_form_meter(cls, meter: Meter, id: str | None = None) -> "MeterSpec":
        """Build a spec from ``app.sonify.form.Meter``, keeping every field."""
        if not isinstance(meter, Meter):
            raise TypeError("meter must be an app.sonify.form.Meter")
        return cls(
            id=f"{meter.beats}/{meter.beat_type}" if id is None else id,
            beats=meter.beats,
            beat_type=meter.beat_type,
            eighths_per_bar=meter.eighths_per_bar,
            strong_eighths=meter.strong_eighths,
            subbar_breaks=meter.subbar_breaks,
            extra_weights=meter.extra_weights,
        )

    def to_form_meter(self) -> Meter:
        return Meter(
            self.beats,
            self.beat_type,
            self.eighths_per_bar,
            self.strong_eighths,
            self.subbar_breaks,
            self.extra_weights,
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "beats": self.beats,
            "beat_type": self.beat_type,
            "eighths_per_bar": self.eighths_per_bar,
            "strong_eighths": list(self.strong_eighths),
            "subbar_breaks": list(self.subbar_breaks),
            "extra_weights": [[eighth, weight] for eighth, weight in self.extra_weights],
        }

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, path: str = "meter"
    ) -> "MeterSpec":
        return parse_meter_spec(mapping, path=path)


def _int_tuple(value: Any, name: str) -> tuple[int, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be a sequence")
    items: list[int] = []
    for item in value:
        if not _is_int(item):
            raise ValueError(f"{name} values must be integers")
        items.append(item)
    return tuple(items)


def meter_key(meter: Meter | MeterSpec) -> tuple[Any, ...]:
    """Canonical key for either a runtime ``Meter`` or a ``MeterSpec``."""
    if isinstance(meter, MeterSpec):
        return meter.key()
    if isinstance(meter, Meter):
        return (
            meter.beats,
            meter.beat_type,
            meter.eighths_per_bar,
            meter.strong_eighths,
            meter.subbar_breaks,
            meter.extra_weights,
        )
    raise TypeError("meter must be a Meter or MeterSpec")


# ---------------------------------------------------------------------------
# PitchRef
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PitchRef:
    """A declarative pitch reference.

    Only ``literal_midi`` is absolute. Every other kind resolves from the
    render context and therefore cannot be checked against a MIDI value
    offline. A field that is not valid for the chosen kind is rejected.
    """

    kind: str
    eighth: int | None = None
    offset: int | None = None
    degree: int | None = None
    steps: int | None = None
    value: int | None = None

    @classmethod
    def melody_eighth(cls, eighth: int, offset: int | None = None) -> "PitchRef":
        return cls(kind="melody_eighth", eighth=eighth, offset=offset)

    @classmethod
    def chord_degree(cls, degree: int) -> "PitchRef":
        return cls(kind="chord_degree", degree=degree)

    @classmethod
    def chord_root(cls) -> "PitchRef":
        return cls(kind="chord_root")

    @classmethod
    def scale_step(cls, steps: int) -> "PitchRef":
        return cls(kind="scale_step", steps=steps)

    @classmethod
    def literal_midi(cls, value: int) -> "PitchRef":
        return cls(kind="literal_midi", value=value)

    def to_mapping(self) -> dict[str, Any]:
        mapping: dict[str, Any] = {"kind": self.kind}
        for name in PITCH_FIELDS.get(self.kind, ()):
            value = getattr(self, name)
            if value is not None:
                mapping[name] = value
        return mapping

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, path: str = "pitch"
    ) -> "PitchRef":
        return _parse_pitch_ref(mapping, path)


def validate_pitch_ref(
    ref: PitchRef,
    *,
    melody_length: int | None = None,
    path: str = "pitch",
) -> tuple[TextureError, ...]:
    """Return every offline violation of a pitch reference.

    ``melody_length`` switches on the ``melody_eighth`` bounds check. The
    runtime ``_melody_at`` clamps; this validator deliberately errors instead.
    """
    errors: list[TextureError] = []
    if not isinstance(ref, PitchRef):
        return (TextureError(path, "expected a PitchRef"),)
    if ref.kind not in PITCH_KINDS:
        return (TextureError(f"{path}.kind", f"unknown pitch kind {ref.kind!r}"),)

    allowed = set(PITCH_FIELDS[ref.kind])
    for name in ("eighth", "offset", "degree", "steps", "value"):
        if getattr(ref, name) is not None and name not in allowed:
            errors.append(
                TextureError(
                    f"{path}.{name}",
                    f"field {name!r} is not valid for kind {ref.kind!r}",
                )
            )

    for name in PITCH_REQUIRED_FIELDS[ref.kind]:
        if getattr(ref, name) is None:
            errors.append(TextureError(f"{path}.{name}", f"missing required field {name!r}"))

    if ref.kind == "melody_eighth":
        eighth_ok = False
        if ref.eighth is not None:
            if not _is_int(ref.eighth):
                errors.append(TextureError(f"{path}.eighth", "must be an integer"))
            elif ref.eighth < 0:
                errors.append(TextureError(f"{path}.eighth", "must be >= 0"))
            else:
                eighth_ok = True
        offset = 0 if ref.offset is None else ref.offset
        offset_ok = False
        if ref.offset is not None:
            if not _is_int(ref.offset):
                errors.append(TextureError(f"{path}.offset", "must be an integer"))
            elif ref.offset < 0:
                errors.append(TextureError(f"{path}.offset", "must be >= 0"))
            else:
                offset_ok = True
        else:
            offset_ok = True
        if melody_length is not None and eighth_ok and offset_ok:
            if not _is_int(melody_length) or melody_length < 0:
                errors.append(TextureError(path, "melody_length must be a non-negative integer"))
            else:
                if ref.eighth >= melody_length:
                    errors.append(
                        TextureError(
                            f"{path}.eighth",
                            f"eighth {ref.eighth} is outside melody length {melody_length}",
                        )
                    )
                elif ref.eighth + offset >= melody_length:
                    errors.append(
                        TextureError(
                            f"{path}.offset",
                            f"eighth + offset {ref.eighth + offset} is outside "
                            f"melody length {melody_length}",
                        )
                    )
    elif ref.kind == "chord_degree":
        if ref.degree is not None:
            if not _is_int(ref.degree):
                errors.append(TextureError(f"{path}.degree", "must be an integer"))
            elif ref.degree < 1:
                errors.append(TextureError(f"{path}.degree", "must be >= 1"))
    elif ref.kind == "scale_step":
        if ref.steps is not None and not _is_int(ref.steps):
            errors.append(TextureError(f"{path}.steps", "must be an integer"))
    elif ref.kind == "literal_midi":
        if ref.value is not None:
            if not _is_int(ref.value):
                errors.append(TextureError(f"{path}.value", "must be an integer"))
            elif not 0 <= ref.value <= 127:
                errors.append(TextureError(f"{path}.value", "must be in 0..127"))
    return tuple(errors)


def _parse_pitch_ref(mapping: Mapping[str, Any], path: str) -> PitchRef:
    data = _mapping(mapping, path)
    if "kind" not in data:
        raise TextureSpecError(f"{path}.kind", "missing field")
    kind = _string(data["kind"], f"{path}.kind")
    if kind not in PITCH_KINDS:
        raise TextureSpecError(f"{path}.kind", f"unknown pitch kind {kind!r}")
    allowed = {"kind", *PITCH_FIELDS[kind]}
    unknown = set(data) - allowed
    if unknown:
        raise TextureSpecError(path, f"unknown field(s) {sorted(unknown)}")
    kwargs: dict[str, Any] = {}
    for name in PITCH_FIELDS[kind]:
        if name not in data:
            continue
        kwargs[name] = _integer(data[name], f"{path}.{name}")
    missing = [name for name in PITCH_REQUIRED_FIELDS[kind] if name not in kwargs]
    if missing:
        raise TextureSpecError(path, f"missing field(s) {sorted(missing)}")
    return PitchRef(kind=kind, **kwargs)


# ---------------------------------------------------------------------------
# AuthoredEvent
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthoredEvent:
    """One authored note: placement plus a declarative pitch reference.

    ``resolved_midi``, velocity, hairpin, and pinned are derived at render
    time; they are not fields here. ``string``/``fret``/``written_pitch``/
    ``sounding_pitch`` are optional tab metadata, not ``NoteEvent`` fields.
    """

    bar: int
    beat: float
    duration_beats: float
    voice: int
    pitch: PitchRef
    staff: int = 1
    tie: str = "none"
    slur: str = "none"
    accent: bool = False
    tenuto: bool = False
    staccato: bool = False
    string: int | None = None
    fret: int | None = None
    written_pitch: str | None = None
    sounding_pitch: str | None = None
    confidence: float | None = None
    conflict: bool = False
    # Fail closed: a missing review must not import as already approved.
    review: str = "pending"

    def to_mapping(self) -> dict[str, Any]:
        mapping: dict[str, Any] = {
            "bar": self.bar,
            "beat": self.beat,
            "duration_beats": self.duration_beats,
            "voice": self.voice,
            "pitch": self.pitch.to_mapping(),
            "staff": self.staff,
            "tie": self.tie,
            "slur": self.slur,
            "accent": self.accent,
            "tenuto": self.tenuto,
            "staccato": self.staccato,
            "conflict": self.conflict,
            "review": self.review,
        }
        for name in (
            "string",
            "fret",
            "written_pitch",
            "sounding_pitch",
            "confidence",
        ):
            value = getattr(self, name)
            if value is not None:
                mapping[name] = value
        return mapping

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, path: str = "event"
    ) -> "AuthoredEvent":
        return _parse_authored_event(mapping, path)


def _parse_authored_event(mapping: Mapping[str, Any], path: str) -> AuthoredEvent:
    data = _mapping(mapping, path)
    unknown = set(data) - _EVENT_KEYS
    if unknown:
        raise TextureSpecError(path, f"unknown field(s) {sorted(unknown)}")
    missing = _EVENT_REQUIRED - set(data)
    if missing:
        raise TextureSpecError(path, f"missing field(s) {sorted(missing)}")

    return AuthoredEvent(
        bar=_integer(data["bar"], f"{path}.bar"),
        beat=_number(data["beat"], f"{path}.beat"),
        duration_beats=_number(data["duration_beats"], f"{path}.duration_beats"),
        voice=_integer(data["voice"], f"{path}.voice"),
        pitch=_parse_pitch_ref(_mapping(data["pitch"], f"{path}.pitch"), f"{path}.pitch"),
        staff=_integer(data.get("staff", 1), f"{path}.staff"),
        tie=_string(data.get("tie", "none"), f"{path}.tie"),
        slur=_string(data.get("slur", "none"), f"{path}.slur"),
        accent=_boolean(data.get("accent", False), f"{path}.accent"),
        tenuto=_boolean(data.get("tenuto", False), f"{path}.tenuto"),
        staccato=_boolean(data.get("staccato", False), f"{path}.staccato"),
        string=_optional_integer(data.get("string"), f"{path}.string"),
        fret=_optional_integer(data.get("fret"), f"{path}.fret"),
        written_pitch=_optional_string(data.get("written_pitch"), f"{path}.written_pitch"),
        sounding_pitch=_optional_string(data.get("sounding_pitch"), f"{path}.sounding_pitch"),
        confidence=_optional_number(data.get("confidence"), f"{path}.confidence"),
        conflict=_boolean(data.get("conflict", False), f"{path}.conflict"),
        review=_string(data.get("review", "pending"), f"{path}.review"),
    )


def validate_authored(
    events: Sequence[AuthoredEvent],
    meter: Meter | MeterSpec,
    *,
    require_full_bars: bool = False,
    path: str = "authored.events",
) -> tuple[TextureError, ...]:
    """Check placement and notation metadata offline.

    Per-voice rules, not a global sum: guitar voices sound simultaneously, so
    three full-bar voices are valid. ``require_full_bars`` compares each
    voice's duration sum in each bar to ``meter.quarter_beats``.

    Ties and slurs are paired per voice. ``tie="next_bar"`` is a start whose
    stop must be the next event in the same voice, in the next bar at beat 0.
    """
    errors = list(_authored_metadata_errors(events, path))
    if not isinstance(events, (list, tuple)):
        return tuple(errors)

    try:
        meter_spec = meter if isinstance(meter, MeterSpec) else MeterSpec.from_form_meter(meter)
    except (TypeError, ValueError) as exc:
        errors.append(TextureError("meter", str(exc)))
        return tuple(errors)

    quarter = meter_spec.quarter_beats
    by_voice: dict[int, list[tuple[int, AuthoredEvent]]] = {}
    for index, event in enumerate(events):
        if not isinstance(event, AuthoredEvent):
            continue
        if not (
            _is_int(event.bar)
            and event.bar >= 0
            and _is_number(event.beat)
            and _is_number(event.duration_beats)
            and _is_int(event.voice)
            and 1 <= event.voice <= 4
        ):
            continue
        beat = float(event.beat)
        duration = float(event.duration_beats)
        if beat < 0:
            errors.append(TextureError(f"{path}[{index}].beat", "must be >= 0"))
            continue
        if beat >= quarter:
            errors.append(
                TextureError(
                    f"{path}[{index}].beat",
                    f"beat {beat} is outside bar length {quarter}",
                )
            )
            continue
        if duration <= 0:
            # Reported by the metadata pass already; keep geometry quiet.
            continue
        if beat + duration > quarter + _EPSILON:
            errors.append(
                TextureError(
                    f"{path}[{index}].duration_beats",
                    f"note overflows the bar: {beat} + {duration} > {quarter}",
                )
            )
        by_voice.setdefault(event.voice, []).append((index, event))

    for voice, items in sorted(by_voice.items()):
        items.sort(key=lambda item: (float(item[1].beat), item[0]))
        previous_end = -1.0
        for index, event in items:
            start = float(event.beat)
            if start + _EPSILON < previous_end:
                errors.append(
                    TextureError(
                        f"{path}[{index}].beat",
                        f"voice {voice} note overlaps the previous note "
                        f"({start} < {previous_end})",
                    )
                )
            previous_end = max(previous_end, start + float(event.duration_beats))

    if require_full_bars:
        totals: dict[tuple[int, int], float] = {}
        for event in events:
            if not isinstance(event, AuthoredEvent):
                continue
            if not (
                _is_int(event.bar)
                and event.bar >= 0
                and _is_int(event.voice)
                and 1 <= event.voice <= 4
                and _is_number(event.duration_beats)
                and float(event.duration_beats) > 0
            ):
                continue
            key = (event.voice, event.bar)
            totals[key] = totals.get(key, 0.0) + float(event.duration_beats)
        for (voice, bar), total in sorted(totals.items()):
            if abs(total - quarter) > _EPSILON:
                errors.append(
                    TextureError(
                        f"{path}.voice[{voice}].bar[{bar}]",
                        f"voice {voice} duration sum {total} != {quarter} beats",
                    )
                )
    return tuple(errors)


def _authored_metadata_errors(
    events: Sequence[AuthoredEvent], path: str
) -> tuple[TextureError, ...]:
    errors: list[TextureError] = []
    if not isinstance(events, (list, tuple)):
        return (TextureError(path, "expected a list of events"),)

    for index, event in enumerate(events):
        item = f"{path}[{index}]"
        if not isinstance(event, AuthoredEvent):
            errors.append(TextureError(item, "expected an AuthoredEvent"))
            continue
        if not _is_int(event.bar) or event.bar < 0:
            errors.append(TextureError(f"{item}.bar", "must be an integer >= 0"))
        if not _is_number(event.beat) or float(event.beat) < 0:
            errors.append(TextureError(f"{item}.beat", "must be a finite number >= 0"))
        if not _is_number(event.duration_beats) or float(event.duration_beats) <= 0:
            errors.append(TextureError(f"{item}.duration_beats", "must be a finite number > 0"))
        if not _is_int(event.voice) or not 1 <= event.voice <= 4:
            errors.append(TextureError(f"{item}.voice", "must be 1..4"))
        if not isinstance(event.pitch, PitchRef):
            errors.append(TextureError(f"{item}.pitch", "expected a PitchRef"))
        else:
            errors.extend(validate_pitch_ref(event.pitch, path=f"{item}.pitch"))
        if not _is_int(event.staff) or not 1 <= event.staff <= 2:
            errors.append(TextureError(f"{item}.staff", "must be 1 or 2"))
        if event.tie not in TIE_VALUES:
            errors.append(TextureError(f"{item}.tie", f"unknown value {event.tie!r}"))
        if event.slur not in SLUR_VALUES:
            errors.append(TextureError(f"{item}.slur", f"unknown value {event.slur!r}"))
        for name in ("accent", "tenuto", "staccato", "conflict"):
            if not isinstance(getattr(event, name), bool):
                errors.append(TextureError(f"{item}.{name}", "must be a boolean"))
        if event.string is not None:
            if not _is_int(event.string) or not 1 <= event.string <= 6:
                errors.append(TextureError(f"{item}.string", "must be 1..6"))
        if event.fret is not None:
            if not _is_int(event.fret) or event.fret < 0:
                errors.append(TextureError(f"{item}.fret", "must be an integer >= 0"))
            if event.string is None:
                errors.append(TextureError(f"{item}.fret", "fret requires string"))
        for name in ("written_pitch", "sounding_pitch"):
            value = getattr(event, name)
            if value is not None and not isinstance(value, str):
                errors.append(TextureError(f"{item}.{name}", "must be a string"))
        if event.confidence is not None:
            if not _is_number(event.confidence) or not 0 <= float(event.confidence) <= 1:
                errors.append(TextureError(f"{item}.confidence", "must be in 0..1"))
        if event.review not in REVIEW_VALUES:
            errors.append(TextureError(f"{item}.review", f"unknown value {event.review!r}"))

    errors.extend(_endpoint_errors(events, path, "tie", TIE_VALUES))
    errors.extend(_endpoint_errors(events, path, "slur", SLUR_VALUES))
    return tuple(errors)


def _endpoint_errors(
    events: Sequence[AuthoredEvent],
    path: str,
    field_name: str,
    values: tuple[str, ...],
) -> tuple[TextureError, ...]:
    errors: list[TextureError] = []
    by_voice: dict[int, list[tuple[int, AuthoredEvent]]] = {}
    for index, event in enumerate(events):
        if not isinstance(event, AuthoredEvent):
            continue
        value = getattr(event, field_name)
        if value == "none" or value not in values:
            continue
        if not (
            _is_int(event.bar)
            and event.bar >= 0
            and _is_number(event.beat)
            and _is_int(event.voice)
            and 1 <= event.voice <= 4
        ):
            continue
        by_voice.setdefault(event.voice, []).append((index, event))

    for voice, items in sorted(by_voice.items()):
        items.sort(key=lambda item: (item[1].bar, float(item[1].beat), item[0]))
        stack: list[int] = []
        for position, (index, event) in enumerate(items):
            value = getattr(event, field_name)
            if value in ("start", "next_bar"):
                if value == "next_bar":
                    if field_name != "tie":
                        continue
                    target = items[position + 1] if position + 1 < len(items) else None
                    if (
                        target is None
                        or target[1].bar != event.bar + 1
                        or abs(float(target[1].beat)) > _EPSILON
                        or getattr(target[1], field_name) not in ("stop", "continue")
                    ):
                        errors.append(
                            TextureError(
                                f"{path}[{index}].{field_name}",
                                "next_bar start needs a stop/continue in the next "
                                "bar at beat 0 in the same voice",
                            )
                        )
                        # Do not also report "start without a stop": the
                        # missing target is the actionable failure.
                        continue
                stack.append(index)
            elif value == "continue":
                if not stack:
                    errors.append(
                        TextureError(
                            f"{path}[{index}].{field_name}",
                            f"{field_name} continue without a start",
                        )
                    )
            elif value == "stop":
                if not stack:
                    errors.append(
                        TextureError(
                            f"{path}[{index}].{field_name}",
                            f"{field_name} stop without a start",
                        )
                    )
                else:
                    stack.pop()
        for index in stack:
            errors.append(
                TextureError(
                    f"{path}[{index}].{field_name}",
                    f"{field_name} start without a stop",
                )
            )
    return tuple(errors)


# ---------------------------------------------------------------------------
# MeterVariant + TextureSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MeterVariant:
    """One declared meter of a pattern, with declarative support metadata."""

    meter: MeterSpec
    materializer: str | None = None
    transform: str = "none"
    unsupported: bool = False
    reason: str | None = None
    sentences: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "meter": self.meter.to_mapping(),
            "materializer": self.materializer,
            "transform": self.transform,
            "unsupported": self.unsupported,
            "reason": self.reason,
            "sentences": list(self.sentences),
        }

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, path: str = "variant"
    ) -> "MeterVariant":
        return _parse_meter_variant(mapping, path)


@dataclass(frozen=True)
class TextureSpec:
    """Bounded authored texture spec.

    ``source``, ``derived``, ``routing``, ``traits``, ``selection``, and
    ``provenance`` are declarative mappings. This module type-checks them but
    does not interpret them; that is compiler/runtime work.

    Unknown top-level keys are rejected unless they were parsed with
    ``allow_extra=True``; those keys are preserved in ``extra`` and emitted
    again by :func:`texture_spec_to_mapping`.
    """

    id: str
    composer: str
    kind: str
    level: str
    runtime: str
    status: str
    parent: str | None = None
    source: Mapping[str, Any] | None = None
    meter_variants: tuple[MeterVariant, ...] = ()
    authored: tuple[AuthoredEvent, ...] = ()
    derived: Mapping[str, Any] | None = None
    routing: Mapping[str, Any] | None = None
    traits: Mapping[str, Any] | None = None
    selection: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any], *, allow_extra: bool = False
    ) -> "TextureSpec":
        return parse_texture_spec(mapping, allow_extra=allow_extra)


def _parse_meter_variant(mapping: Mapping[str, Any], path: str) -> MeterVariant:
    data = _mapping(mapping, path)
    unknown = set(data) - _VARIANT_KEYS
    if unknown:
        raise TextureSpecError(path, f"unknown field(s) {sorted(unknown)}")
    if "meter" not in data:
        raise TextureSpecError(path, "missing field(s) ['meter']")
    meter = parse_meter_spec(_mapping(data["meter"], f"{path}.meter"), path=f"{path}.meter")
    materializer = _optional_string(data.get("materializer"), f"{path}.materializer")
    transform = _string(data.get("transform", "none"), f"{path}.transform")
    unsupported = _boolean(data.get("unsupported", False), f"{path}.unsupported")
    reason = _optional_string(data.get("reason"), f"{path}.reason")
    raw_sentences = data.get("sentences", [])
    if not isinstance(raw_sentences, (list, tuple)):
        raise TextureSpecError(f"{path}.sentences", "expected a list")
    sentences = tuple(
        _non_empty_string(item, f"{path}.sentences[{index}]")
        for index, item in enumerate(raw_sentences)
    )
    return MeterVariant(
        meter=meter,
        materializer=materializer,
        transform=transform,
        unsupported=unsupported,
        reason=reason,
        sentences=sentences,
    )


def parse_texture_spec(
    mapping: Mapping[str, Any], *, allow_extra: bool = False
) -> TextureSpec:
    """Parse a mapping into a ``TextureSpec`` without cross-field validation.

    Structural errors (missing/unknown keys, wrong JSON types, malformed meter)
    raise :class:`TextureSpecError` naming the path. Call
    :func:`validate_texture_spec` (or :func:`check_texture_spec`) for rules such
    as duplicate meter keys, sentence parents, and the publish gate.
    """
    data = _mapping(mapping, "spec")
    unknown = set(data) - _TOP_KEYS
    if unknown and not allow_extra:
        raise TextureSpecError("spec", f"unknown top-level field(s) {sorted(unknown)}")
    missing = _REQUIRED_TOP_KEYS - set(data)
    if missing:
        raise TextureSpecError("spec", f"missing field(s) {sorted(missing)}")

    parent = data.get("parent")
    if parent is not None:
        parent = _string(parent, "spec.parent")

    raw_variants = data["meter_variants"]
    if not isinstance(raw_variants, (list, tuple)):
        raise TextureSpecError("spec.meter_variants", "expected a list")
    meter_variants = tuple(
        _parse_meter_variant(
            _mapping(raw, f"spec.meter_variants[{index}]"),
            f"spec.meter_variants[{index}]",
        )
        for index, raw in enumerate(raw_variants)
    )

    authored: tuple[AuthoredEvent, ...] = ()
    raw_authored = data.get("authored")
    if raw_authored is not None:
        authored_data = _mapping(raw_authored, "spec.authored")
        unknown_authored = set(authored_data) - _AUTHORED_KEYS
        if unknown_authored:
            raise TextureSpecError(
                "spec.authored", f"unknown field(s) {sorted(unknown_authored)}"
            )
        if "events" not in authored_data:
            raise TextureSpecError("spec.authored", "missing field(s) ['events']")
        raw_events = authored_data["events"]
        if not isinstance(raw_events, (list, tuple)):
            raise TextureSpecError("spec.authored.events", "expected a list")
        authored = tuple(
            _parse_authored_event(
                _mapping(raw, f"spec.authored.events[{index}]"),
                f"spec.authored.events[{index}]",
            )
            for index, raw in enumerate(raw_events)
        )

    declarative: dict[str, Mapping[str, Any] | None] = {}
    for name in ("source", "derived", "routing", "traits", "selection", "provenance"):
        value = data.get(name)
        if value is None:
            declarative[name] = None
        else:
            declarative[name] = dict(_mapping(value, f"spec.{name}"))

    extra = (
        {key: dict(value) if isinstance(value, Mapping) else value
         for key, value in data.items() if key not in _TOP_KEYS}
        if allow_extra
        else {}
    )

    return TextureSpec(
        id=_string(data["id"], "spec.id"),
        composer=_string(data["composer"], "spec.composer"),
        kind=_string(data["kind"], "spec.kind"),
        level=_string(data["level"], "spec.level"),
        runtime=_string(data["runtime"], "spec.runtime"),
        status=_string(data["status"], "spec.status"),
        parent=parent,
        source=declarative["source"],
        meter_variants=meter_variants,
        authored=authored,
        derived=declarative["derived"],
        routing=declarative["routing"],
        traits=declarative["traits"],
        selection=declarative["selection"],
        provenance=declarative["provenance"],
        extra=extra,
    )


def texture_spec_to_mapping(spec: TextureSpec) -> dict[str, Any]:
    """Return the JSON mapping for a spec, preserving extra keys verbatim."""
    if not isinstance(spec, TextureSpec):
        raise TypeError("spec must be a TextureSpec")
    mapping: dict[str, Any] = dict(spec.extra)
    mapping.update(
        {
            "id": spec.id,
            "composer": spec.composer,
            "kind": spec.kind,
            "level": spec.level,
            "parent": spec.parent,
            "runtime": spec.runtime,
            "status": spec.status,
        }
    )
    for name in ("source", "derived", "routing", "traits", "selection", "provenance"):
        value = getattr(spec, name)
        if value is not None:
            mapping[name] = copy.deepcopy(dict(value))
    mapping["meter_variants"] = [
        variant.to_mapping()
        if isinstance(variant, MeterVariant)
        else copy.deepcopy(variant)
        for variant in spec.meter_variants
    ]
    mapping["authored"] = {
        "events": [
            event.to_mapping()
            if isinstance(event, AuthoredEvent)
            else copy.deepcopy(event)
            for event in spec.authored
        ]
    }
    return mapping


def validate_texture_spec(
    spec: TextureSpec,
    *,
    meter: Meter | MeterSpec | None = None,
    require_full_bars: bool = False,
    allow_extra: bool = False,
) -> tuple[TextureError, ...]:
    """Return every offline rule violation of a ``TextureSpec``.

    Without ``meter`` only context-free authored checks run (voice, review,
    confidence, string/fret, tie/slur pairing). Pass the authored meter to
    also check per-voice overlap, bar overflow, and optional full bars. A spec
    with several meter variants must choose one; validating authored geometry
    against every variant would report false failures.
    """
    errors: list[TextureError] = []
    if not isinstance(spec, TextureSpec):
        return (TextureError("spec", "expected a TextureSpec"),)

    if not isinstance(spec.id, str) or not spec.id:
        errors.append(TextureError("id", "must be a non-empty string"))
    if not isinstance(spec.composer, str) or not spec.composer:
        errors.append(TextureError("composer", "must be a non-empty string"))
    if spec.kind not in KINDS:
        errors.append(TextureError("kind", f"unknown value {spec.kind!r}"))
    if spec.level not in LEVELS:
        errors.append(TextureError("level", f"unknown value {spec.level!r}"))
    if spec.runtime not in RUNTIMES:
        errors.append(TextureError("runtime", f"unknown value {spec.runtime!r}"))
    if spec.status not in STATUSES:
        errors.append(TextureError("status", f"unknown value {spec.status!r}"))

    if spec.parent is not None and (not isinstance(spec.parent, str) or not spec.parent):
        errors.append(TextureError("parent", "must be a non-empty string or null"))
    if spec.kind == "sentence" and not spec.parent:
        errors.append(TextureError("parent", "kind 'sentence' requires a parent pattern"))

    for name in ("source", "derived", "routing", "traits", "selection", "provenance"):
        value = getattr(spec, name)
        if value is not None and not isinstance(value, Mapping):
            errors.append(TextureError(name, "must be a mapping or null"))

    variants = spec.meter_variants
    if not isinstance(variants, (tuple, list)):
        errors.append(TextureError("meter_variants", "expected a list"))
        variants = ()
    if not variants:
        errors.append(TextureError("meter_variants", "must not be empty"))
    seen: dict[tuple[Any, ...], int] = {}
    for index, variant in enumerate(variants):
        path = f"meter_variants[{index}]"
        if not isinstance(variant, MeterVariant):
            errors.append(TextureError(path, "expected a MeterVariant"))
            continue
        meter_spec = variant.meter
        if not isinstance(meter_spec, MeterSpec):
            errors.append(TextureError(f"{path}.meter", "expected a MeterSpec"))
        else:
            if not isinstance(meter_spec.id, str) or not meter_spec.id:
                errors.append(TextureError(f"{path}.meter.id", "must be a non-empty string"))
            key = meter_spec.key()
            if key in seen:
                errors.append(
                    TextureError(
                        f"{path}.meter",
                        f"duplicate meter variant key {key} "
                        f"(also at meter_variants[{seen[key]}])",
                    )
                )
            else:
                seen[key] = index
        if variant.materializer is not None and not isinstance(variant.materializer, str):
            errors.append(TextureError(f"{path}.materializer", "must be a string or null"))
        elif not variant.unsupported and not variant.materializer:
            errors.append(
                TextureError(
                    f"{path}.materializer",
                    "supported variants need a non-empty materializer",
                )
            )
        if variant.transform not in TRANSFORMS:
            errors.append(
                TextureError(f"{path}.transform", f"unknown value {variant.transform!r}")
            )
        if not isinstance(variant.unsupported, bool):
            errors.append(TextureError(f"{path}.unsupported", "must be a boolean"))
        elif variant.unsupported and (
            not isinstance(variant.reason, str) or not variant.reason.strip()
        ):
            errors.append(
                TextureError(f"{path}.reason", "unsupported variant requires a reason")
            )
        sentences = variant.sentences
        if not isinstance(sentences, (tuple, list)):
            errors.append(TextureError(f"{path}.sentences", "expected a list"))
        else:
            for position, sentence in enumerate(sentences):
                if not isinstance(sentence, str) or not sentence:
                    errors.append(
                        TextureError(
                            f"{path}.sentences[{position}]",
                            "must be a non-empty string",
                        )
                    )

    if meter is not None:
        errors.extend(
            validate_authored(
                spec.authored,
                meter,
                require_full_bars=require_full_bars,
                path="authored.events",
            )
        )
    else:
        errors.extend(_authored_metadata_errors(spec.authored, "authored.events"))
        if require_full_bars:
            errors.append(
                TextureError(
                    "meter",
                    "require_full_bars needs an explicit meter (multiple variants "
                    "are not guessed for authored geometry)",
                )
            )

    if not isinstance(spec.extra, Mapping):
        errors.append(TextureError("extra", "must be a mapping"))
    elif spec.extra and not allow_extra:
        for key in sorted(spec.extra):
            errors.append(TextureError(key, "unknown top-level field"))
    elif allow_extra:
        for key in spec.extra:
            if not isinstance(key, str) or not key:
                errors.append(TextureError("extra", "extra keys must be non-empty strings"))
    return tuple(errors)


def check_texture_spec(
    mapping: Mapping[str, Any],
    *,
    allow_extra: bool = False,
    meter: Meter | MeterSpec | None = None,
    require_full_bars: bool = False,
) -> tuple[TextureError, ...]:
    """Parse and validate one mapping, returning records instead of raising."""
    try:
        spec = parse_texture_spec(mapping, allow_extra=allow_extra)
    except TextureSpecError as exc:
        return (TextureError(exc.path, exc.message),)
    return validate_texture_spec(
        spec,
        meter=meter,
        require_full_bars=require_full_bars,
        allow_extra=allow_extra,
    )


def publishable(spec: TextureSpec) -> bool:
    """Publish gate: no pending review and no confidence below 0.6."""
    if not isinstance(spec, TextureSpec):
        return False
    for event in spec.authored:
        if not isinstance(event, AuthoredEvent):
            return False
        if event.review not in ("accepted", "edited"):
            return False
        if event.confidence is not None:
            if not _is_number(event.confidence):
                return False
            if float(event.confidence) < MIN_PUBLISH_CONFIDENCE:
                return False
    return True


# ---------------------------------------------------------------------------
# Small JSON helpers
# ---------------------------------------------------------------------------


def parse_meter_spec(mapping: Mapping[str, Any], *, path: str = "meter") -> MeterSpec:
    data = _mapping(mapping, path)
    unknown = set(data) - _METER_KEYS
    if unknown:
        raise TextureSpecError(path, f"unknown field(s) {sorted(unknown)}")
    missing = _METER_REQUIRED - set(data)
    if missing:
        raise TextureSpecError(path, f"missing field(s) {sorted(missing)}")
    try:
        return MeterSpec(
            id=_string(data["id"], f"{path}.id"),
            beats=_integer(data["beats"], f"{path}.beats"),
            beat_type=_integer(data["beat_type"], f"{path}.beat_type"),
            eighths_per_bar=_integer(data["eighths_per_bar"], f"{path}.eighths_per_bar"),
            strong_eighths=_integer_list(data["strong_eighths"], f"{path}.strong_eighths"),
            subbar_breaks=_integer_list(data["subbar_breaks"], f"{path}.subbar_breaks"),
            extra_weights=_weight_list(
                data.get("extra_weights", []), f"{path}.extra_weights"
            ),
        )
    except TextureSpecError:
        raise
    except ValueError as exc:
        # MeterSpec.__post_init__ reports field rules without a JSON path.
        raise TextureSpecError(path, str(exc)) from None


def meter_spec_to_mapping(spec: MeterSpec) -> dict[str, Any]:
    if not isinstance(spec, MeterSpec):
        raise TypeError("spec must be a MeterSpec")
    return spec.to_mapping()


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TextureSpecError(path, "expected an object")
    return dict(value)


def _integer(value: Any, path: str) -> int:
    if not _is_int(value):
        raise TextureSpecError(path, "expected an integer")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _integer(value, path)


def _number(value: Any, path: str) -> float:
    if not _is_number(value):
        raise TextureSpecError(path, "expected a finite number")
    return float(value)


def _optional_number(value: Any, path: str) -> float | None:
    if value is None:
        return None
    return _number(value, path)


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise TextureSpecError(path, "expected a string")
    return value


def _optional_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _non_empty_string(value: Any, path: str) -> str:
    text = _string(value, path)
    if not text:
        raise TextureSpecError(path, "expected a non-empty string")
    return text


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise TextureSpecError(path, "expected a boolean")
    return value


def _integer_list(value: Any, path: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)):
        raise TextureSpecError(path, "expected a list")
    return tuple(_integer(item, f"{path}[{index}]") for index, item in enumerate(value))


def _weight_list(value: Any, path: str) -> tuple[tuple[int, float], ...]:
    if not isinstance(value, (list, tuple)):
        raise TextureSpecError(path, "expected a list")
    weights: list[tuple[int, float]] = []
    for index, pair in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise TextureSpecError(item_path, "expected [eighth, weight]")
        weights.append(
            (
                _integer(pair[0], f"{item_path}[0]"),
                _number(pair[1], f"{item_path}[1]"),
            )
        )
    return tuple(weights)
