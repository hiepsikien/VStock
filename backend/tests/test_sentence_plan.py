"""Phrase plan policies, offsets, and explicit-plan validation."""

from __future__ import annotations

import pytest

from app.sonify.sentence_plan import (
    AutoAABA,
    Explicit,
    PhraseView,
    Trio,
    build_plan,
)
from app.sonify.sentence_specs import (
    Select,
    SentenceSpec,
    Slot,
    Span,
    plan_sentence,
    plan_slots,
)

PATTERN = "unit_plan"
METER = "4/4"


def _spec(spec_id: str, length_min: int = 1) -> SentenceSpec:
    return SentenceSpec(
        id=spec_id,
        pattern=PATTERN,
        meter=METER,
        select=Select(length_min=length_min),
        span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
        slots=(
            Slot(0, 1, 1),
            Slot(1, 1, 2),
            Slot(2, 1, 1),
            Slot(3, 1, 2),
        ),
    )


SPEC = _spec("unit_plan_a")
REGISTRY = {(PATTERN, METER): (SPEC,)}


def _views(
    starts: list[int], *, rises: list[int] | None = None
) -> tuple[PhraseView, ...]:
    rises = rises or [0] * len(starts)
    count = len(starts)
    return tuple(
        PhraseView(
            index=index,
            count=count,
            start_bar=start,
            bars=4,
            closes=index == count - 1,
            rise=rises[index],
            kind="phrase",
        )
        for index, start in enumerate(starts)
    )


def test_auto_aaba_three_phrases_put_b_at_n1() -> None:
    roles = AutoAABA().roles(_views([0, 4, 8]))
    assert [role.role for role in roles] == ["A", "B", "close"]


def test_auto_aaba_four_and_five_phrases_put_b_at_n2() -> None:
    four = AutoAABA().roles(_views([0, 4, 8, 12]))
    five = AutoAABA().roles(_views([0, 4, 8, 12, 16]))
    assert [role.role for role in four] == ["A", "A", "B", "close"]
    assert [role.role for role in five] == ["A", "A", "B", "A", "close"]


def test_rise_never_adds_a_second_b() -> None:
    roles = AutoAABA().roles(_views([0, 4, 8, 12], rises=[0, 0, 5, 0]))
    assert [role.role for role in roles] == ["A", "A", "B", "close"]
    assert roles[2].reason == "aaba_rise"


def test_trio_puts_b_on_the_middle_or_trio_phrase() -> None:
    roles = Trio().roles(_views([0, 4, 8]))
    assert [role.role for role in roles] == ["A", "B", "A"]


def test_rise_selects_the_stronger_b_spec_without_adding_b() -> None:
    normal = SentenceSpec(
        id="unit_b_normal",
        pattern=PATTERN,
        meter=METER,
        select=Select(length_min=1),
        span=Span(tile=4),
        slots=(Slot(0, 1, 1), Slot(1, 1, 2), Slot(2, 1, 1), Slot(3, 1, 2)),
    )
    strong = SentenceSpec(
        id="unit_b_strong",
        pattern=PATTERN,
        meter=METER,
        select=Select(length_min=1, rise_min=3),
        span=Span(tile=4),
        slots=(Slot(0, 1, 3), Slot(1, 1, 4), Slot(2, 1, 3), Slot(3, 1, 4)),
    )
    registry = {(PATTERN, METER): (normal, strong)}
    plan = build_plan(
        PATTERN,
        METER,
        _views([0, 4, 8], rises=[0, 5, 0]),
        policy=AutoAABA(),
        registry=registry,
    )
    roles = [phrase.role.role for phrase in plan.phrases]
    assert roles == ["A", "B", "close"]
    assert [slot.figure for slot in plan.phrases[1].slots] == [3, 4, 3, 4]


def test_plan_sentence_and_slots_shift_by_offset() -> None:
    assert plan_sentence(
        PATTERN, METER, 4, 0, offset=5, registry=REGISTRY
    ) == [
        (1, (5,)),
        (2, (6,)),
        (1, (7,)),
        (2, (8,)),
    ]
    slots = plan_slots(PATTERN, METER, 4, 0, offset=5, registry=REGISTRY)
    assert slots is not None
    assert [slot.slot_start for slot in slots] == [5, 6, 7, 8]
    assert [slot.bars for slot in slots] == [(5,), (6,), (7,), (8,)]


def test_build_plan_uses_each_phrase_offset() -> None:
    plan = build_plan(
        PATTERN,
        METER,
        _views([4, 8, 12]),
        policy=AutoAABA(),
        registry=REGISTRY,
    )
    assert [phrase.phrase.start_bar for phrase in plan.phrases] == [4, 8, 12]
    assert [slot.slot_start for slot in plan.slots] == list(range(4, 16))
    assert [slot.bars for slot in plan.slots] == [
        (bar,) for bar in range(4, 16)
    ]


def _explicit(starts: list[int], roles: list[str]) -> Explicit:
    return Explicit(
        {
            "version": 1,
            "id": "unit_explicit",
            "pattern": PATTERN,
            "meter": METER,
            "phrases": [
                {"startBar": start + 1, "bars": 4, "role": role}
                for start, role in zip(starts, roles, strict=True)
            ],
            "sentenceByRole": {
                "A": "unit_plan_a",
                "B": "unit_plan_a",
                "close": "unit_plan_a",
            },
        }
    )


def test_explicit_plan_round_trips_and_uses_zero_based_bars() -> None:
    policy = _explicit([0, 4, 8], ["A", "B", "close"])
    plan = build_plan(
        PATTERN, METER, _views([0, 4, 8]), policy=policy, registry=REGISTRY
    )
    assert plan.policy_id == "explicit"
    assert [phrase.role.role for phrase in plan.phrases] == ["A", "B", "close"]
    assert [slot.slot_start for slot in plan.slots] == list(range(12))


def test_explicit_rejects_a_plan_that_does_not_end_close() -> None:
    with pytest.raises(ValueError, match="end with role 'close'"):
        _explicit([0, 4, 8], ["A", "close", "B"])


def test_explicit_rejects_a_b_on_the_last_phrase() -> None:
    with pytest.raises(ValueError, match="end with role 'close'"):
        _explicit([0, 4, 8], ["A", "A", "B"])


def test_explicit_rejects_a_wrong_meter() -> None:
    policy = _explicit([0, 4, 8], ["A", "B", "close"])
    with pytest.raises(ValueError, match="pattern/meter"):
        build_plan(
            PATTERN,
            "3/4",
            _views([0, 4, 8]),
            policy=policy,
            registry=REGISTRY,
        )


def test_explicit_rejects_an_unknown_sentence_id() -> None:
    policy = Explicit(
        {
            "pattern": PATTERN,
            "meter": METER,
            "phrases": [
                {"startBar": 1, "bars": 4, "role": "A"},
                {"startBar": 5, "bars": 4, "role": "B"},
                {"startBar": 9, "bars": 4, "role": "close"},
            ],
            "sentenceByRole": {
                "A": "unit_plan_a",
                "B": "missing_b",
                "close": "unit_plan_a",
            },
        }
    )
    with pytest.raises(ValueError, match="unknown sentence id"):
        build_plan(
            PATTERN, METER, _views([0, 4, 8]), policy=policy, registry=REGISTRY
        )


def test_role_tagged_specs_choose_the_matching_phrase_role() -> None:
    def tagged(role: str, figure: int) -> SentenceSpec:
        return SentenceSpec(
            id=f"unit_role_{role}",
            pattern=PATTERN,
            meter=METER,
            select=Select(
                length_min=4,
                closes="close" if role == "close" else None,
            ),
            span=Span(tile=4),
            slots=tuple(Slot(bar, 1, figure) for bar in range(4)),
            role=role,
        )

    registry = {
        (PATTERN, METER): (
            tagged("A", 1),
            tagged("B", 2),
            tagged("close", 3),
        )
    }
    plan = build_plan(
        PATTERN,
        METER,
        _views([0, 4, 8]),
        policy=AutoAABA(),
        registry=registry,
    )
    assert [phrase.role.role for phrase in plan.phrases] == ["A", "B", "close"]
    assert {slot.figure for slot in plan.phrases[0].slots} == {1}
    assert {slot.figure for slot in plan.phrases[1].slots} == {2}
    assert {slot.figure for slot in plan.phrases[2].slots} == {3}


def test_role_tagged_a_survives_a_rise_without_adding_a_second_b() -> None:
    def tagged(role: str, figure: int) -> SentenceSpec:
        return SentenceSpec(
            id=f"unit_rise_{role}",
            pattern=PATTERN,
            meter=METER,
            select=Select(
                length_min=4,
                closes="close" if role == "close" else None,
                rise_min=3 if role == "B" else 0,
            ),
            span=Span(tile=4),
            slots=tuple(Slot(bar, 1, figure) for bar in range(4)),
            role=role,
        )

    registry = {
        (PATTERN, METER): (
            tagged("A", 1),
            tagged("B", 2),
            tagged("close", 3),
        )
    }
    plan = build_plan(
        PATTERN,
        METER,
        _views([0, 4, 8, 12], rises=[5, 0, 5, 0]),
        policy=AutoAABA(),
        registry=registry,
    )
    assert [phrase.role.role for phrase in plan.phrases] == [
        "A",
        "A",
        "B",
        "close",
    ]
    assert [slot.figure for slot in plan.phrases[0].slots] == [1, 1, 1, 1]
    assert [slot.figure for slot in plan.phrases[1].slots] == [1, 1, 1, 1]
    assert [slot.figure for slot in plan.phrases[2].slots] == [2, 2, 2, 2]
    assert [slot.figure for slot in plan.phrases[3].slots] == [3, 3, 3, 3]
