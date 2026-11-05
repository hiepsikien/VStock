"""A procedure is a third slot realizer, alongside figures and cells.

The schema change is groundwork: a procedure slot names a spec in
`procedure_specs.PROCEDURES`, but neither planner emits a span for it and the
Studio preview refuses to invent notes. No committed sentence uses one yet, so
the existing Torroba/Sor registry must stay byte-for-byte unchanged.
"""

from __future__ import annotations

import copy

import pytest

import app.sonify.guitar_sor  # noqa: F401  (registers the galop cycle)
import app.sonify.guitar_torroba  # noqa: F401  (registers the Torroba rows)
from app.sonify.procedure_specs import (
    BACH_IMITATION,
    PROCEDURES,
    validate_procedure,
)
from app.sonify.sentence_specs import (
    SENTENCE_SPECS,
    Select,
    SentenceSpec,
    Slot,
    Span,
    plan_run,
    plan_sentence,
    register,
)
from app.sonify.guitar_sor import GALOP_CYCLE
from app.sonify.guitar_torroba import CASTILLO_34_WALK, CASTILLO_44_TYPE7_L5
from app.studio.preview import preview_spec, validate_spec
from app.studio.sentence_spec import (
    parse_payload,
    parse_spec,
    spec_to_mapping,
    specs_to_payload,
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


def _spec(name: str, *, span: Span, slots: tuple[Slot, ...]) -> SentenceSpec:
    return SentenceSpec(
        id=name,
        pattern=name,
        meter="3/4",
        select=Select(),
        span=span,
        slots=slots,
    )


def _register(*specs: SentenceSpec, **kwargs) -> None:
    register(specs[0].pattern, "3/4", *specs, replace=True, **kwargs)


# A real spec with its figure swapped for the Bach procedure. It lives on the
# castillo 4/4 key so `validate_spec` can resolve the pattern and meter.
PROCEDURE_SPEC = SentenceSpec(
    id="castillo_44_type7_procedure",
    pattern="castillo",
    meter="4/4",
    select=Select(length_min=5, length_max=5, n_parity="even"),
    span=Span(exact=True, remainder="exact"),
    slots=(Slot(start=0, bars=5, procedure="bach_imitation"),),
)


def test_the_procedure_registry_names_the_bach_imitation() -> None:
    assert PROCEDURES == {"bach_imitation": BACH_IMITATION}
    assert validate_procedure("bach_imitation") == "bach_imitation"
    with pytest.raises(ValueError, match="unknown procedure 'episode'"):
        validate_procedure("episode")
    with pytest.raises(ValueError, match="non-empty string"):
        validate_procedure("")


def test_register_accepts_figure_cell_and_procedure_realizers() -> None:
    figure = _spec(
        "unit_realizer_figure",
        span=Span(tile=1),
        slots=(Slot(0, 1, figure=1),),
    )
    cell = _spec(
        "unit_realizer_cell",
        span=Span(tile=1, cycle=True, remainder="truncate_cycle"),
        slots=(Slot(0, 1, cell="a"),),
    )
    procedure = _spec(
        "unit_realizer_procedure",
        span=Span(tile=1),
        slots=(Slot(0, 1, procedure="bach_imitation"),),
    )

    _register(figure, valid_figures={1})
    _register(cell, valid_cells={"a"})
    _register(procedure, valid_procedures={"bach_imitation"})

    assert SENTENCE_SPECS[("unit_realizer_figure", "3/4")] == (figure,)
    assert SENTENCE_SPECS[("unit_realizer_cell", "3/4")] == (cell,)
    assert SENTENCE_SPECS[("unit_realizer_procedure", "3/4")] == (procedure,)


def test_a_slot_needs_exactly_one_realizer() -> None:
    empty = _spec(
        "unit_realizer_empty",
        span=Span(tile=1),
        slots=(Slot(0, 1),),
    )
    with pytest.raises(ValueError, match="exactly one of figure, cell, or procedure"):
        _register(empty)

    figure_and_procedure = _spec(
        "unit_realizer_pair",
        span=Span(tile=1),
        slots=(Slot(0, 1, figure=1, procedure="bach_imitation"),),
    )
    with pytest.raises(ValueError, match="exactly one of figure, cell, or procedure"):
        _register(figure_and_procedure)

    cell_and_procedure = _spec(
        "unit_realizer_cell_pair",
        span=Span(tile=1),
        slots=(Slot(0, 1, cell="a", procedure="bach_imitation"),),
    )
    with pytest.raises(ValueError, match="exactly one of figure, cell, or procedure"):
        _register(cell_and_procedure)


def test_register_rejects_an_unknown_procedure() -> None:
    spec = _spec(
        "unit_procedure_typo",
        span=Span(tile=1),
        slots=(Slot(0, 1, procedure="episode"),),
    )
    with pytest.raises(
        ValueError, match=r"procedures \['episode'\] are not registered"
    ):
        _register(spec, valid_procedures=set(PROCEDURES))


def test_validate_rejects_an_unknown_procedure_with_a_path() -> None:
    typo = SentenceSpec(
        id="castillo_44_type7_typo",
        pattern="castillo",
        meter="4/4",
        select=Select(length_min=5, length_max=5, n_parity="even"),
        span=Span(exact=True, remainder="exact"),
        slots=(Slot(start=0, bars=5, procedure="episode"),),
    )
    errors = validate_spec(typo)
    assert [(error.path, "not registered" in error.message) for error in errors] == [
        ("slots[0].procedure", True)
    ]


def test_validate_accepts_a_known_procedure() -> None:
    assert validate_spec(PROCEDURE_SPEC) == []


def test_json_round_trip_includes_the_procedure() -> None:
    mapping = spec_to_mapping(PROCEDURE_SPEC)
    slot = mapping["slots"][0]
    assert slot["procedure"] == "bach_imitation"
    assert "figure" not in slot and "cell" not in slot

    assert parse_spec(mapping) == PROCEDURE_SPEC
    assert parse_payload(specs_to_payload([PROCEDURE_SPEC])) == (PROCEDURE_SPEC,)


def test_json_rejects_zero_or_two_realizers() -> None:
    payload = specs_to_payload([PROCEDURE_SPEC])

    empty = copy.deepcopy(payload)
    del empty["specs"][0]["slots"][0]["procedure"]
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\].*exactly one"):
        parse_payload(empty)
    with pytest.raises(ValueError, match=r"^spec\.slots\[0\].*exactly one"):
        parse_spec(empty["specs"][0])

    both = copy.deepcopy(payload)
    both["specs"][0]["slots"][0]["figure"] = 7
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\].*exactly one"):
        parse_payload(both)


def test_json_rejects_a_bad_procedure_value() -> None:
    for value in ("", 1):
        mapping = spec_to_mapping(PROCEDURE_SPEC)
        mapping["slots"][0]["procedure"] = value
        with pytest.raises(ValueError, match=r"^spec\.slots\[0\]\.procedure:"):
            parse_spec(mapping)


def test_a_procedure_slot_produces_no_plan() -> None:
    spec = _spec(
        "unit_procedure_plan",
        span=Span(tile=5, exact=True),
        slots=(Slot(0, 5, procedure="bach_imitation"),),
    )
    _register(spec, valid_procedures=set(PROCEDURES))

    assert plan_sentence("unit_procedure_plan", "3/4", 5, 0) == []
    assert plan_run("unit_procedure_plan", "3/4", 5) == []


def test_preview_reports_a_procedure_as_not_implemented() -> None:
    result = preview_spec(PROCEDURE_SPEC)
    assert not result.ok
    assert [
        (error.path, "preview not implemented" in error.message)
        for error in result.errors
    ] == [("slots[0].procedure", True)]
    assert result.plan is None
    assert result.notes == ()
    assert result.render_hash is None


def test_existing_torroba_and_sor_specs_are_unchanged() -> None:
    assert validate_spec(CASTILLO_34_WALK) == []
    assert validate_spec(GALOP_CYCLE) == []

    for specs in SENTENCE_SPECS.values():
        for spec in specs:
            mapping = spec_to_mapping(spec)
            assert all("procedure" not in slot for slot in mapping["slots"]), spec.id
            assert parse_spec(mapping) == spec
