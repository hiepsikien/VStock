"""Registry behaviour for fields the next migrations depend on."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.sonify.sentence_specs import (
    METER_ANY,
    SENTENCE_SPECS,
    Select,
    SentenceSpec,
    Slot,
    Span,
    plan_sentence,
    register,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Unit registrations must not leak into other tests."""
    saved = dict(SENTENCE_SPECS)
    try:
        yield
    finally:
        SENTENCE_SPECS.clear()
        SENTENCE_SPECS.update(saved)


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


def test_truncate_cycle_requires_cycle() -> None:
    spec = _spec(
        "unit_cycle_flag",
        select=Select(),
        span=Span(tile=8, remainder="truncate_cycle", cycle=False),
    )
    with pytest.raises(ValueError, match="cycle=True"):
        register("unit_cycle_flag", "3/4", spec, replace=True)


def test_cycle_requires_truncate_cycle_remainder() -> None:
    spec = _spec(
        "unit_cycle_rem",
        select=Select(),
        span=Span(tile=8, cycle=True, remainder="same_figure"),
    )
    with pytest.raises(ValueError, match="truncate_cycle"):
        register("unit_cycle_rem", "3/4", spec, replace=True)


def test_registered_figures_exist() -> None:
    """Every slot figure in the global registry must exist in _FIGURES."""
    from app.sonify.guitar_torroba import _FIGURES

    for specs in SENTENCE_SPECS.values():
        for spec in specs:
            for slot in spec.slots:
                assert slot.figure in _FIGURES, (spec.id, slot.figure)


def test_register_rejects_unknown_anchor() -> None:
    spec = _spec(
        "unit_anchor_bad",
        select=Select(),
        span=Span(tile=9),
        slots=(Slot(0, 1, 1, anchor="center"),),
    )
    with pytest.raises(ValueError, match="unknown slot anchor"):
        register("unit_anchor_bad", "3/4", spec, replace=True)


def test_middle_anchor_is_relative_to_the_phrase_middle() -> None:
    spec = _spec(
        "unit_anchor_middle",
        select=Select(length_min=2),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(-1, 2, 1, anchor="middle"),),
    )
    pattern = _register(spec)
    # base = length // 2 - 1: 0 at L2/L3, 1 at L4/L5, 2 at L6/L7.
    assert plan_sentence(pattern, "3/4", 2, 0) == [(1, (0, 1))]
    assert plan_sentence(pattern, "3/4", 3, 0) == [(1, (0, 1))]
    assert plan_sentence(pattern, "3/4", 4, 0) == [(1, (1, 2))]
    assert plan_sentence(pattern, "3/4", 6, 0) == [(1, (2, 3))]
    assert plan_sentence(pattern, "3/4", 7, 0) == [(1, (2, 3))]


def test_middle_anchor_needs_an_exact_span() -> None:
    spec = _spec(
        "unit_anchor_middle_tile",
        select=Select(),
        span=Span(tile=8),
        slots=(Slot(-1, 2, 1, anchor="middle"),),
    )
    with pytest.raises(ValueError, match="needs an exact span"):
        register("unit_anchor_middle_tile", "3/4", spec, replace=True)


def test_middle_anchor_must_stay_inside_the_shortest_sentence() -> None:
    left = _spec(
        "unit_anchor_middle_left",
        select=Select(length_min=2),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(-2, 2, 1, anchor="middle"),),
    )
    with pytest.raises(ValueError, match="outside the phrase"):
        register("unit_anchor_middle_left", "3/4", left, replace=True)

    right = _spec(
        "unit_anchor_middle_right",
        select=Select(length_min=4),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(2, 2, 1, anchor="middle"),),
    )
    with pytest.raises(ValueError, match="outside the phrase"):
        register("unit_anchor_middle_right", "3/4", right, replace=True)


def test_middle_anchor_cannot_overlap_start_slots() -> None:
    spec = _spec(
        "unit_anchor_middle_overlap",
        select=Select(length_min=4),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(0, 2, 1), Slot(-1, 2, 2, anchor="middle")),
    )
    with pytest.raises(ValueError, match="middle slot overlaps an earlier slot"):
        register("unit_anchor_middle_overlap", "3/4", spec, replace=True)


def test_end_anchor_needs_an_exact_span() -> None:
    spec = _spec(
        "unit_anchor_tile",
        select=Select(),
        span=Span(tile=9),
        slots=(Slot(0, 3, 1, anchor="end"),),
    )
    with pytest.raises(ValueError, match="needs an exact span"):
        register("unit_anchor_tile", "3/4", spec, replace=True)


def test_end_anchor_must_start_at_zero() -> None:
    spec = _spec(
        "unit_anchor_start",
        select=Select(length_min=4),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(1, 3, 1, anchor="end"),),
    )
    with pytest.raises(ValueError, match="start=0"):
        register("unit_anchor_start", "3/4", spec, replace=True)


def test_end_anchor_cannot_overlap_start_slots() -> None:
    spec = _spec(
        "unit_anchor_overlap",
        select=Select(length_min=4),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(0, 2, 1), Slot(0, 3, 2, anchor="end")),
    )
    with pytest.raises(ValueError, match="overlaps an earlier slot"):
        register("unit_anchor_overlap", "3/4", spec, replace=True)


def test_end_slot_must_fit_the_shortest_sentence() -> None:
    spec = _spec(
        "unit_anchor_short",
        select=Select(length_min=2),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(0, 3, 1, anchor="end"),),
    )
    with pytest.raises(ValueError, match="below the end slot size"):
        register("unit_anchor_short", "3/4", spec, replace=True)


def test_exact_meter_wins_over_wildcard() -> None:
    wild = _spec(
        "unit_prec_wild",
        pattern="unit_prec",
        select=Select(),
        span=Span(tile=1),
        slots=(Slot(0, 1, 1),),
    )
    register("unit_prec", METER_ANY, replace(wild, meter=METER_ANY), replace=True)
    exact = replace(
        wild,
        id="unit_prec_exact",
        meter="4/4",
        slots=(Slot(0, 1, 2),),
    )
    register("unit_prec", "4/4", exact, replace=True)
    assert plan_sentence("unit_prec", "4/4", 1, 0) == [(2, (0,))]
    assert plan_sentence("unit_prec", "3/4", 1, 0) == [(1, (0,))]


def test_exact_meter_wins_after_owner_import(monkeypatch) -> None:
    """The exact key must win even when it only appears after the owner imports."""
    import app.sonify.sentence_specs as specs

    wild = _spec(
        "unit_prec2_wild",
        pattern="unit_prec2",
        select=Select(),
        span=Span(tile=1),
        slots=(Slot(0, 1, 1),),
    )
    specs.register("unit_prec2", METER_ANY, replace(wild, meter=METER_ANY), replace=True)
    exact = replace(
        wild, id="unit_prec2_exact", meter="4/4", slots=(Slot(0, 1, 2),)
    )

    def fake_import(name: str):
        if (name == "unit_owner"):
            specs.register("unit_prec2", "4/4", exact, replace=True)
        return object()

    monkeypatch.setattr(specs, "_OWNER_MODULES", ("unit_owner",))
    monkeypatch.setattr(specs.importlib, "import_module", fake_import)
    # Start with the exact key absent so _lookup has to import the owner.
    specs.SENTENCE_SPECS.pop(("unit_prec2", "4/4"), None)

    assert plan_sentence("unit_prec2", "4/4", 1, 0) == [(2, (0,))]
    assert plan_sentence("unit_prec2", "3/4", 1, 0) == [(1, (0,))]
