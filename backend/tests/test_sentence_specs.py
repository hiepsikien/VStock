"""Registry behaviour for fields the next migrations depend on."""

from __future__ import annotations

import pytest

from app.sonify.sentence_specs import (
    Select,
    SentenceSpec,
    Slot,
    Span,
    plan_sentence,
    register,
)


def _spec(
    name: str,
    *,
    select: Select,
    span: Span,
    slots: tuple[Slot, ...] = (Slot(0, 1, 1),),
    pattern: str | None = None,
) -> SentenceSpec:
    return SentenceSpec(
        id=name,
        pattern=name if pattern is None else pattern,
        meter="3/4",
        select=select,
        span=span,
        slots=slots,
    )


def _register(*specs: SentenceSpec, **kwargs) -> str:
    pattern = specs[0].pattern
    register(pattern, "3/4", *specs, replace=True, **kwargs)
    return pattern


def test_n_mod_selects_the_turn() -> None:
    spec = _spec(
        "unit_nmod",
        select=Select(n_mod=(3, 0)),
        span=Span(tile=9),
        slots=(Slot(0, 9, 1),),
    )
    pattern = _register(spec)
    assert plan_sentence(pattern, "3/4", 9, 0) == [(1, tuple(range(9)))]
    assert plan_sentence(pattern, "3/4", 9, 1) == []


def test_closes_picks_open_or_close() -> None:
    open_spec = _spec(
        "unit_closes_open",
        pattern="unit_closes",
        select=Select(closes="open"),
        span=Span(tile=9),
        slots=(Slot(0, 9, 1),),
    )
    close_spec = _spec(
        "unit_closes_close",
        pattern="unit_closes",
        select=Select(closes="close"),
        span=Span(tile=9),
        slots=(Slot(0, 9, 2),),
    )
    pattern = _register(open_spec, close_spec)
    assert plan_sentence(pattern, "3/4", 9, 0, closes=False) == [(1, tuple(range(9)))]
    assert plan_sentence(pattern, "3/4", 9, 0, closes=True) == [(2, tuple(range(9)))]


def test_rise_min_gates_the_archetype() -> None:
    spec = _spec(
        "unit_rise",
        select=Select(rise_min=2),
        span=Span(tile=9),
        slots=(Slot(0, 9, 1),),
    )
    pattern = _register(spec)
    assert plan_sentence(pattern, "3/4", 9, 0, rise=1) == []
    assert plan_sentence(pattern, "3/4", 9, 0, rise=2) == [(1, tuple(range(9)))]


def test_exact_mismatch_does_not_stop_the_next_spec() -> None:
    short = _spec(
        "unit_exact",
        select=Select(length_min=5, length_max=6),
        span=Span(tile=5, exact=True),
        slots=(Slot(0, 5, 1),),
    )
    exact_six = SentenceSpec(
        id="unit_exact_six",
        pattern="unit_exact",
        meter="3/4",
        select=Select(length_min=6, length_max=6),
        span=Span(tile=6, exact=True),
        slots=(Slot(0, 6, 2),),
    )
    pattern = _register(short, exact_six)
    assert plan_sentence(pattern, "3/4", 6, 0) == [(2, tuple(range(6)))]
    assert plan_sentence(pattern, "3/4", 5, 0) == [(1, tuple(range(5)))]
    assert plan_sentence(pattern, "3/4", 7, 0) == []


def test_cycle_repeats_and_truncates() -> None:
    spec = _spec(
        "unit_cycle",
        select=Select(length_min=1),
        span=Span(tile=8, cycle=True, remainder="truncate_cycle"),
        slots=(Slot(0, 4, 1), Slot(4, 4, 2)),
    )
    pattern = _register(spec)
    assert plan_sentence(pattern, "3/4", 10, 0) == [
        (1, (0, 1, 2, 3)),
        (2, (4, 5, 6, 7)),
        (1, (8, 9)),
    ]


def test_register_rejects_unknown_figure() -> None:
    spec = _spec(
        "unit_badfigure",
        select=Select(),
        span=Span(tile=9),
        slots=(Slot(0, 9, 999),),
    )
    with pytest.raises(ValueError, match="not registered"):
        register("unit_badfigure", "3/4", spec, replace=True, valid_figures={1})


def test_register_is_idempotent() -> None:
    spec = _spec("unit_idem", select=Select(), span=Span(tile=9))
    _register(spec)
    _register(spec)  # must not raise on reload/re-register


def test_register_rejects_duplicate_ids() -> None:
    first = _spec("unit_dup", select=Select(), span=Span(tile=9))
    second = _spec("unit_dup", select=Select(), span=Span(tile=9), slots=(Slot(0, 9, 2),))
    with pytest.raises(ValueError, match="duplicate ids"):
        register("unit_dup", "3/4", first, second, replace=True)


def test_truncate_cycle_requires_truncation() -> None:
    spec = _spec(
        "unit_cycle_bad",
        select=Select(),
        span=Span(tile=8, cycle=True, remainder="truncate_cycle", truncate_to_length=False),
    )
    with pytest.raises(ValueError, match="truncate_to_length"):
        register("unit_cycle_bad", "3/4", spec, replace=True)


def test_partial_tile_is_rejected_when_truncation_is_off() -> None:
    spec = _spec(
        "unit_notrunc",
        select=Select(),
        span=Span(tile=9, truncate_to_length=False),
        slots=(Slot(0, 9, 1),),
    )
    pattern = _register(spec)
    assert plan_sentence(pattern, "3/4", 10, 0) == []
    assert plan_sentence(pattern, "3/4", 9, 0) == [(1, tuple(range(9)))]
