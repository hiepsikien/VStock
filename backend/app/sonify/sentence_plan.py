"""Phrase-level plan policy, independent of the renderer.

The renderer only needs `PlannedSlot[]`. Choosing A/B/close is data: a policy
turns body phrases into roles, then `build_plan` selects a registered
`SentenceSpec` for each role and calls `plan_slots` with the phrase offset. No
policy code knows about `_Ctx`, guitar figures, or the wave/dynamics tail.

The historical `SuiteGate` single-spec path stays in `guitar_suite_gate`; this
module is the seam a multi-spec movement (or an external JSON plan) uses. The
built-in `AutoAABA` encodes the MVP rules:

* B always exists when the body has at least three phrases;
* `b_index = min(2, len(body) - 2)` (3 phrases -> n1, 4+ -> n2);
* a bridge/trio phrase wins its own B slot;
* the last phrase is always `close`;
* `rise` only asks the registry for a stronger B spec; it never adds a B.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from app.sonify import sentence_specs
from app.sonify.sentence_specs import (
    PlannedSlot,
    SentenceSpec,
    _matches,
    _slot_entries,
    _tile,
    plan_slots,
)

# Same threshold as `phrasing.MIN_RISE`: three semitones is the smallest
# change a listener hears as a rise rather than an ornament.
MIN_RISE = 3
_ROLES = frozenset({"A", "B", "close"})
_BRIDGE_KINDS = frozenset({"bridge", "trio"})


@dataclass(frozen=True)
class PhraseView:
    """One body phrase, in bar units, as the planner sees it."""

    index: int
    count: int
    start_bar: int
    bars: int
    closes: bool
    rise: int
    kind: str = "phrase"


@dataclass(frozen=True)
class PhraseRole:
    """The role chosen for one phrase, plus the spec id when explicit."""

    role: str
    sentence_id: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class PhrasePlan:
    """One phrase paired with its role and realized slots."""

    phrase: PhraseView
    role: PhraseRole
    slots: tuple[PlannedSlot, ...]


@dataclass(frozen=True)
class Plan:
    """A whole movement plan.

    Slots are absolute and flattened in phrase order.
    """

    policy_id: str
    phrases: tuple[PhrasePlan, ...]
    slots: tuple[PlannedSlot, ...]


@runtime_checkable
class PlanPolicy(Protocol):
    """Turns body phrases into roles.

    Pure: no renderer and no registry mutation.
    """

    id: str

    def roles(self, phrases: Sequence[PhraseView]) -> tuple[PhraseRole, ...]:
        ...


def _role(
    role: str,
    *,
    reason: str,
    sentence_id: str | None = None,
) -> PhraseRole:
    return PhraseRole(role, sentence_id=sentence_id, reason=reason)


@dataclass(frozen=True)
class AutoAABA:
    """The MVP policy: A/A/B/close with B always present for 3+ phrases."""

    id: str = "auto_aaba"

    def roles(self, phrases: Sequence[PhraseView]) -> tuple[PhraseRole, ...]:
        body = tuple(phrases)
        count = len(body)
        if count == 0:
            return ()
        b_index = min(2, count - 2) if count >= 3 else None
        found: list[PhraseRole] = []
        for index, phrase in enumerate(body):
            if index == count - 1:
                found.append(_role("close", reason="last_phrase"))
            elif phrase.kind in _BRIDGE_KINDS:
                found.append(_role("B", reason=phrase.kind))
            elif b_index is not None and index == b_index:
                reason = "bridge_trio_absent"
                if phrase.rise >= MIN_RISE:
                    reason = "aaba_rise"
                found.append(_role("B", reason=reason))
            else:
                found.append(_role("A", reason="aaba_default"))
        return tuple(found)


@dataclass(frozen=True)
class Trio:
    """A B A: place B on the trio/bridge phrase, else the middle phrase."""

    id: str = "trio"

    def roles(self, phrases: Sequence[PhraseView]) -> tuple[PhraseRole, ...]:
        body = tuple(phrases)
        count = len(body)
        if count == 0:
            return ()
        if count == 1:
            return (_role("A", reason="single_phrase"),)
        if count == 2:
            return (
                _role("A", reason="trio_default"),
                _role("A", reason="trio_default"),
            )
        bridge = next(
            (
                index
                for index, phrase in enumerate(body[:-1])
                if phrase.kind in _BRIDGE_KINDS
            ),
            None,
        )
        b_index = bridge if bridge is not None else max(1, count // 2)
        if b_index >= count - 1:
            b_index = max(0, count - 2)
        found: list[PhraseRole] = []
        for index, _phrase in enumerate(body):
            if index == b_index:
                reason = "trio" if bridge is not None else "middle"
                found.append(_role("B", reason=reason))
            else:
                found.append(_role("A", reason="trio_default"))
        return tuple(found)


@dataclass(frozen=True)
class Explicit:
    """Roles and sentence ids from an external JSON-ish mapping.

    ``startBar`` is 1-based in the payload; the plan uses 0-based bars. The
    payload is validated against the concrete `PhraseView` tuple and the
    registry when `build_plan` runs, so an invalid plan is a clear error, never
    a silent fallback.
    """

    payload: Mapping[str, Any]
    id: str = "explicit"

    def __post_init__(self) -> None:
        # Fail at construction: a malformed external plan never reaches the
        # renderer and never silently falls back.
        if not isinstance(self.payload, Mapping):
            raise ValueError("explicit plan must be a mapping")
        self._entries()

    def _entries(self) -> tuple[Mapping[str, Any], ...]:
        entries = self.payload.get("phrases")
        if not isinstance(entries, (list, tuple)) or not entries:
            raise ValueError("explicit plan needs a non-empty phrases list")
        found: list[Mapping[str, Any]] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                raise ValueError(f"explicit phrase {index} must be a mapping")
            role = entry.get("role")
            if role not in _ROLES:
                raise ValueError(
                    f"explicit phrase {index} role must be one of "
                    f"{sorted(_ROLES)}"
                )
            start = entry.get("startBar")
            bars = entry.get("bars")
            if not isinstance(start, int) or isinstance(start, bool):
                raise ValueError(
                    f"explicit phrase {index} startBar must be an integer"
                )
            if start < 1:
                raise ValueError(
                    f"explicit phrase {index} startBar must be >= 1"
                )
            if not isinstance(bars, int) or isinstance(bars, bool):
                raise ValueError(
                    f"explicit phrase {index} bars must be an integer"
                )
            if bars < 1:
                raise ValueError(f"explicit phrase {index} bars must be >= 1")
            found.append(entry)
        if found[-1]["role"] != "close":
            raise ValueError("explicit plan must end with role 'close'")
        if any(entry["role"] == "B" for entry in found[-1:]):
            raise ValueError("explicit plan cannot put B on the last phrase")
        return tuple(found)

    def roles(self, phrases: Sequence[PhraseView]) -> tuple[PhraseRole, ...]:
        body = tuple(phrases)
        entries = self._entries()
        if len(entries) != len(body):
            raise ValueError(
                f"explicit plan has {len(entries)} phrases, "
                f"movement has {len(body)}"
            )
        by_role = self.payload.get("sentenceByRole") or {}
        if not isinstance(by_role, Mapping):
            raise ValueError("explicit plan sentenceByRole must be a mapping")
        found: list[PhraseRole] = []
        rows = zip(entries, body, strict=True)
        for index, (entry, phrase) in enumerate(rows):
            start_bar = entry["startBar"] - 1
            if start_bar != phrase.start_bar:
                raise ValueError(
                    f"explicit phrase {index} startBar {entry['startBar']} "
                    f"does not match body bar {phrase.start_bar + 1}"
                )
            if entry["bars"] != phrase.bars:
                raise ValueError(
                    f"explicit phrase {index} bars {entry['bars']} "
                    f"does not match body phrase length {phrase.bars}"
                )
            role = entry["role"]
            sentence_id = by_role.get(role)
            if role in {"B", "close"} and not sentence_id:
                raise ValueError(
                    f"explicit plan has no sentenceByRole for {role}"
                )
            found.append(
                _role(
                    role,
                    sentence_id=sentence_id,
                    reason=f"explicit:{index}",
                )
            )
        return tuple(found)


@dataclass(frozen=True)
class CompositePolicy:
    """First child policy that produces roles wins. Kept deliberately small."""

    policies: tuple[PlanPolicy, ...]
    id: str = "composite"

    def roles(self, phrases: Sequence[PhraseView]) -> tuple[PhraseRole, ...]:
        for policy in self.policies:
            roles = policy.roles(phrases)
            if roles:
                return roles
        return ()


def _registry_specs(
    pattern: str,
    meter: str,
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None,
) -> tuple[SentenceSpec, ...]:
    specs = sentence_specs._lookup(pattern, meter, registry)
    if specs is None:
        raise ValueError(
            f"no sentence specs registered for {(pattern, meter)}"
        )
    return specs


def _spec_by_id(
    specs: Sequence[SentenceSpec],
    sentence_id: str,
) -> SentenceSpec:
    for spec in specs:
        if spec.id == sentence_id:
            return spec
    raise ValueError(
        f"unknown sentence id {sentence_id!r} for this pattern/meter"
    )


def _plan_named_spec(
    spec: SentenceSpec,
    phrase: PhraseView,
) -> tuple[PlannedSlot, ...]:
    if phrase.bars < 1:
        raise ValueError(f"phrase {phrase.index} has no bars")
    # An explicit plan owns the sentence choice; the span still has to fill the
    # phrase. A too-short sentence truncates through the usual tile contract.
    slots = _tile(spec, phrase.bars, _slot_entries, offset=phrase.start_bar)
    return tuple(slots)


def _plan_phrase(
    pattern: str,
    meter: str,
    phrase: PhraseView,
    role: PhraseRole,
    specs: Sequence[SentenceSpec],
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None,
) -> tuple[PlannedSlot, ...]:
    if role.sentence_id is not None:
        spec = _spec_by_id(specs, role.sentence_id)
        planned = _plan_named_spec(spec, phrase)
    elif role.role == "B":
        # A rise may only change which B spec we choose. Prefer the matching
        # spec with the highest `rise_min`; it never creates a second B role.
        candidates = [
            spec
            for spec in specs
            if _matches(
                spec,
                phrase.bars,
                phrase.index,
                False,
                phrase.rise,
            )
        ]
        if candidates:
            stronger = max(candidates, key=lambda spec: spec.select.rise_min)
            planned = _plan_named_spec(stronger, phrase)
        else:
            planned = tuple(
                plan_slots(
                    pattern,
                    meter,
                    phrase.bars,
                    phrase.index,
                    closes=False,
                    rise=phrase.rise,
                    offset=phrase.start_bar,
                    registry=registry,
                )
                or ()
            )
    else:
        # `rise` is a B-only selector. Passing it on A/close could select a
        # stronger spec and silently add a second contrast phrase.
        rise = 0
        slots = plan_slots(
            pattern,
            meter,
            phrase.bars,
            phrase.index,
            closes=role.role == "close",
            rise=rise,
            offset=phrase.start_bar,
            registry=registry,
        )
        if slots is None:
            raise ValueError(
                f"no sentence specs registered for {(pattern, meter)}"
            )
        planned = tuple(slots)
        if not planned and role.role != "A":
            # Fallback A of the same phrase rather than dropping the phrase.
            fallback = plan_slots(
                pattern,
                meter,
                phrase.bars,
                phrase.index,
                closes=False,
                rise=0,
                offset=phrase.start_bar,
                registry=registry,
            )
            planned = tuple(fallback or ())
        if not planned:
            # Last resort: the first registered spec. This keeps an unusual
            # phrase length audible instead of silently erasing the phrase.
            planned = _plan_named_spec(specs[0], phrase)
    if not planned:
        raise ValueError(f"phrase {phrase.index} planned no slots")
    return planned


def build_plan(
    pattern: str,
    meter: str,
    phrases: Sequence[PhraseView],
    *,
    policy: PlanPolicy,
    registry: Mapping[tuple[str, str], tuple[SentenceSpec, ...]] | None = None,
) -> Plan:
    """Pure phrase plan: roles -> specs -> absolute `PlannedSlot[]`.

    The explicit policy validates its pattern/meter and every referenced
    sentence id before planning. Other policies use the registry selection with
    the phrase's own index, close flag, rise, and absolute bar offset.
    """
    if isinstance(policy, Explicit):
        payload_pattern = policy.payload.get("pattern")
        payload_meter = policy.payload.get("meter")
        if payload_pattern != pattern or payload_meter != meter:
            raise ValueError(
                "explicit plan pattern/meter do not match the movement "
                f"({payload_pattern!r}/{payload_meter!r} != "
                f"{pattern!r}/{meter!r})"
            )
    specs = _registry_specs(pattern, meter, registry)
    roles = policy.roles(tuple(phrases))
    if len(roles) != len(phrases):
        raise ValueError("policy returned a role per phrase mismatch")
    if isinstance(policy, Explicit):
        by_role = policy.payload.get("sentenceByRole") or {}
        for role in roles:
            if role.sentence_id is not None:
                _spec_by_id(specs, role.sentence_id)
        if not isinstance(by_role, Mapping):
            raise ValueError("explicit plan sentenceByRole must be a mapping")

    planned_phrases: list[PhrasePlan] = []
    all_slots: list[PlannedSlot] = []
    for phrase, role in zip(phrases, roles, strict=True):
        slots = _plan_phrase(pattern, meter, phrase, role, specs, registry)
        planned_phrases.append(PhrasePlan(phrase, role, slots))
        all_slots.extend(slots)
    return Plan(policy.id, tuple(planned_phrases), tuple(all_slots))


__all__ = [
    "AutoAABA",
    "CompositePolicy",
    "Explicit",
    "MIN_RISE",
    "PhrasePlan",
    "PhraseRole",
    "PhraseView",
    "Plan",
    "PlanPolicy",
    "Trio",
    "build_plan",
]
