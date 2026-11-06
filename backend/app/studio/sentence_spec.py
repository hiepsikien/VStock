"""JSON schema v1 for sentence specs.

The wrapper is::

    {"schema_version": 1, "runtime": "code", "specs": [spec, ...]}

A spec carries the fields of :class:`app.sonify.sentence_specs.SentenceSpec`.
The JSON is an authoring source and a test fixture only; the runtime stays on
the code specs in `guitar_torroba.py` and `guitar_sor.py`, so `runtime` must be
``"code"``. There is deliberately no interpreter here.

Parsing validates every field and its cross-field rules. Errors are
``ValueError`` and name the failing location, for example
``specs[0].slots[1].figure``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.sonify.sentence_specs import (
    _ANCHORS,
    _CLOSES,
    _N_PARITY,
    _REMAINDER,
    Select,
    SentenceSpec,
    Slot,
    Span,
    _validate,
)
from app.studio.micro_velocity import (
    MicroVelocity,
    micro_velocity_to_mapping,
    parse_micro_velocity,
)

SCHEMA_VERSION = 1
RUNTIME = "code"

_WRAPPER_KEYS = frozenset({"schema_version", "runtime", "specs"})
_SPEC_KEYS = frozenset(
    {"id", "pattern", "meter", "select", "span", "slots", "role"}
)
_SELECT_KEYS = frozenset(
    {"length_min", "length_max", "n_parity", "n_mod", "closes", "rise_min"}
)
_SPAN_KEYS = frozenset({"tile", "remainder", "truncate_to_length", "cycle", "exact"})
_SLOT_KEYS = frozenset(
    {"start", "bars", "figure", "cell", "procedure", "anchor", "microVelocity"}
)
_SLOT_REQUIRED = frozenset({"start", "bars", "anchor"})
_N_MOD_KEYS = frozenset({"mod", "value"})


def spec_to_mapping(spec: SentenceSpec) -> dict[str, Any]:
    """Return the JSON mapping for one spec.

    Keys are written in schema order; exporters still sort keys so the file
    bytes stay stable.
    """
    select = spec.select
    span = spec.span
    mapping: dict[str, Any] = {
        "id": spec.id,
        "pattern": spec.pattern,
        "meter": spec.meter,
    }
    if spec.role is not None:
        mapping["role"] = spec.role
    mapping.update(
        {
            "select": {
                "length_min": select.length_min,
                "length_max": select.length_max,
                "n_parity": select.n_parity,
                "n_mod": (
                    None
                    if select.n_mod is None
                    else {"mod": select.n_mod[0], "value": select.n_mod[1]}
                ),
                "closes": select.closes,
                "rise_min": select.rise_min,
            },
            "span": {
                "tile": span.tile,
                "remainder": span.remainder,
                "truncate_to_length": span.truncate_to_length,
                "cycle": span.cycle,
                "exact": span.exact,
            },
            "slots": [_slot_to_mapping(slot) for slot in spec.slots],
        }
    )
    return mapping


def _slot_to_mapping(slot: Slot) -> dict[str, Any]:
    mapping: dict[str, Any] = {"start": slot.start, "bars": slot.bars}
    if slot.figure is not None:
        mapping["figure"] = slot.figure
    if slot.cell is not None:
        mapping["cell"] = slot.cell
    if slot.procedure is not None:
        mapping["procedure"] = slot.procedure
    if slot.micro_velocity is not None:
        mapping["microVelocity"] = micro_velocity_to_mapping(slot.micro_velocity)
    mapping["anchor"] = slot.anchor
    return mapping


def specs_to_payload(specs: tuple[SentenceSpec, ...] | list[SentenceSpec]) -> dict[str, Any]:
    """Wrap specs in the v1 envelope."""
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime": RUNTIME,
        "specs": [spec_to_mapping(spec) for spec in specs],
    }


def parse_spec(mapping: Mapping[str, Any], *, path: str = "spec") -> SentenceSpec:
    """Build one :class:`SentenceSpec` from its JSON mapping.

    Raises ``ValueError`` with the offending path. This does not touch the
    global registry.
    """
    data = _mapping(mapping, path)
    _check_keys(
        data,
        _SPEC_KEYS,
        path,
        optional=frozenset({"role"}),
    )

    sid = _non_empty_str(data["id"], f"{path}.id")
    pattern = _non_empty_str(data["pattern"], f"{path}.pattern")
    meter = _non_empty_str(data["meter"], f"{path}.meter")
    role = data.get("role")
    if role is not None and role not in ("A", "B", "close"):
        raise ValueError(f"{path}.role: must be 'A', 'B' or 'close'")
    select = _parse_select(_mapping(data["select"], f"{path}.select"), f"{path}.select")
    span = _parse_span(_mapping(data["span"], f"{path}.span"), f"{path}.span")
    slots = _parse_slots(data["slots"], f"{path}.slots")

    spec = SentenceSpec(
        id=sid,
        pattern=pattern,
        meter=meter,
        select=select,
        span=span,
        slots=slots,
        role=role,
    )
    try:
        _validate(spec, pattern, meter)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from None
    return spec


def parse_payload(payload: Mapping[str, Any]) -> tuple[SentenceSpec, ...]:
    """Parse a wrapper without touching the global registry.

    The returned specs keep file order, so a preview can plan from a sandbox
    copy. Duplicate ids within one `(pattern, meter)` pair are rejected.
    """
    data = _mapping(payload, "root")
    _check_keys(data, _WRAPPER_KEYS, "root")

    version = _integer(data["schema_version"], "schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"schema_version: expected {SCHEMA_VERSION}, got {version}"
        )
    runtime = _string(data["runtime"], "runtime")
    if runtime != RUNTIME:
        raise ValueError(f"runtime: expected {RUNTIME!r}, got {runtime!r}")

    raw_specs = data["specs"]
    if not isinstance(raw_specs, list):
        raise ValueError("specs: expected a list")
    specs: list[SentenceSpec] = []
    seen: dict[tuple[str, str], set[str]] = {}
    for index, raw in enumerate(raw_specs):
        path = f"specs[{index}]"
        spec = parse_spec(_mapping(raw, path), path=path)
        key = (spec.pattern, spec.meter)
        ids = seen.setdefault(key, set())
        if spec.id in ids:
            raise ValueError(f"{path}.id: duplicate id {spec.id!r} for {key}")
        ids.add(spec.id)
        specs.append(spec)
    return tuple(specs)


def _parse_select(data: dict[str, Any], path: str) -> Select:
    _check_keys(data, _SELECT_KEYS, path)
    length_min = _integer(data["length_min"], f"{path}.length_min")
    length_max = _optional_integer(data["length_max"], f"{path}.length_max")
    n_parity = _string(data["n_parity"], f"{path}.n_parity")
    if n_parity not in _N_PARITY:
        raise ValueError(f"{path}.n_parity: unknown value {n_parity!r}")
    n_mod = _parse_n_mod(data["n_mod"], f"{path}.n_mod")
    closes = data["closes"]
    if closes is not None:
        closes = _string(closes, f"{path}.closes")
        if closes not in _CLOSES:
            raise ValueError(f"{path}.closes: unknown value {closes!r}")
    rise_min = _integer(data["rise_min"], f"{path}.rise_min")
    return Select(
        length_min=length_min,
        length_max=length_max,
        n_parity=n_parity,
        n_mod=n_mod,
        closes=closes,
        rise_min=rise_min,
    )


def _parse_n_mod(value: Any, path: str) -> tuple[int, int] | None:
    if value is None:
        return None
    data = _mapping(value, path)
    _check_keys(data, _N_MOD_KEYS, path)
    return (
        _integer(data["mod"], f"{path}.mod"),
        _integer(data["value"], f"{path}.value"),
    )


def _parse_span(data: dict[str, Any], path: str) -> Span:
    _check_keys(data, _SPAN_KEYS, path)
    tile = _optional_integer(data["tile"], f"{path}.tile")
    remainder = _string(data["remainder"], f"{path}.remainder")
    if remainder not in _REMAINDER:
        raise ValueError(f"{path}.remainder: unknown value {remainder!r}")
    return Span(
        tile=tile,
        remainder=remainder,
        truncate_to_length=_boolean(
            data["truncate_to_length"], f"{path}.truncate_to_length"
        ),
        cycle=_boolean(data["cycle"], f"{path}.cycle"),
        exact=_boolean(data["exact"], f"{path}.exact"),
    )


def _parse_slots(value: Any, path: str) -> tuple[Slot, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{path}: expected a list")
    return tuple(_parse_slot(_mapping(raw, f"{path}[{index}]"), f"{path}[{index}]")
                 for index, raw in enumerate(value))


def _parse_slot(data: dict[str, Any], path: str) -> Slot:
    unknown = set(data) - _SLOT_KEYS
    if unknown:
        raise ValueError(f"{path}: unknown field(s) {sorted(unknown)}")
    missing = _SLOT_REQUIRED - set(data)
    if missing:
        raise ValueError(f"{path}: missing field(s) {sorted(missing)}")
    start = _integer(data["start"], f"{path}.start")
    bars = _integer(data["bars"], f"{path}.bars")
    anchor = _string(data["anchor"], f"{path}.anchor")
    if anchor not in _ANCHORS:
        raise ValueError(f"{path}.anchor: unknown value {anchor!r}")

    figure = data.get("figure")
    cell = data.get("cell")
    procedure = data.get("procedure")
    if figure is not None:
        figure = _integer(figure, f"{path}.figure")
    if cell is not None:
        cell = _non_empty_str(cell, f"{path}.cell")
    if procedure is not None:
        procedure = _non_empty_str(procedure, f"{path}.procedure")
    if sum(
        realizer is not None for realizer in (figure, cell, procedure)
    ) != 1:
        raise ValueError(
            f"{path}: a slot needs exactly one of figure, cell, or procedure"
        )
    micro_velocity: MicroVelocity | None = None
    if data.get("microVelocity") is not None:
        micro_velocity = parse_micro_velocity(
            data["microVelocity"], path=f"{path}.microVelocity"
        )
    return Slot(
        start=start,
        bars=bars,
        figure=figure,
        cell=cell,
        procedure=procedure,
        anchor=anchor,
        micro_velocity=micro_velocity,
    )


def _check_keys(
    data: Mapping[str, Any],
    allowed: frozenset[str],
    path: str,
    *,
    optional: frozenset[str] = frozenset(),
) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"{path}: unknown field(s) {sorted(unknown)}")
    missing = (allowed - optional) - set(data)
    if missing:
        raise ValueError(f"{path}: missing field(s) {sorted(missing)}")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path}: expected an object")
    return dict(value)


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}: expected an integer")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    if value is None:
        return None
    return _integer(value, path)


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{path}: expected a string")
    return value


def _non_empty_str(value: Any, path: str) -> str:
    text = _string(value, path)
    if not text:
        raise ValueError(f"{path}: expected a non-empty string")
    return text


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{path}: expected a boolean")
    return value
