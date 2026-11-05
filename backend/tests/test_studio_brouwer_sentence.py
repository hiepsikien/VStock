"""Preview-only Brouwer sentence pilot.

The candidate JSON must round-trip through the v1 schema, the preview must go
through the real Brouwer bar writers, and the candidate must stay invisible to
the production registry.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

# Import both production owners so the registry snapshot is complete before a
# candidate preview checks that it did not change.
import app.sonify.guitar_sor  # noqa: F401
import app.sonify.guitar_torroba  # noqa: F401
from app.sonify import sentence_specs as specs
from app.sonify.guitar_brouwer_figures import (
    BROUWER_ELOGIO,
    BROUWER_ETUDE,
    BROUWER_FIGURES,
    BROUWER_FIGURE_NAMES,
    BROUWER_NOVIEMBRE,
    BROUWER_SARABANDE,
    figure_pattern,
)
from app.sonify.sentence_specs import plan_sentence
from app.studio.brouwer_preview import (
    BROUWER_PATTERNS,
    MAX_PLAN_BARS,
    preview_brouwer_sentence,
    validate_brouwer_spec,
)
from app.studio.candidates.brouwer import (
    BROUWER_ABA,
    BROUWER_ABA_PATH,
    brouwer_aba_spec,
    load_brouwer_aba,
)
from app.studio.sentence_spec import parse_payload, specs_to_payload


def _snapshot() -> dict:
    return dict(specs.SENTENCE_SPECS)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """A preview must never leave a candidate in the global registry."""
    saved = dict(specs.SENTENCE_SPECS)
    try:
        yield
    finally:
        specs.SENTENCE_SPECS.clear()
        specs.SENTENCE_SPECS.update(saved)


def test_candidate_round_trips_through_the_v1_schema() -> None:
    specs_in = load_brouwer_aba()
    payload = specs_to_payload(specs_in)
    assert parse_payload(payload) == specs_in
    assert payload["schema_version"] == 1
    assert payload["runtime"] == "code"

    # The file on disk is already the canonical wrapper.
    on_disk = json.loads(BROUWER_ABA_PATH.read_text(encoding="utf-8"))
    assert on_disk == payload
    assert specs_in == (BROUWER_ABA,)


def test_candidate_is_an_aba_sentence_of_brouwer_figures() -> None:
    spec = brouwer_aba_spec()
    assert spec.id == "brouwer_etude_noviembre_aba"
    assert spec.pattern == "brouwer_etude"
    assert spec.meter == "4/4"
    assert spec.span.tile == 3
    assert (spec.select.length_min, spec.select.length_max) == (3, None)
    assert [slot.figure for slot in spec.slots] == [
        BROUWER_ETUDE,
        BROUWER_NOVIEMBRE,
        BROUWER_ETUDE,
    ]
    assert [slot.start for slot in spec.slots] == [0, 1, 2]
    assert validate_brouwer_spec(spec) == []


def test_figure_registry_covers_the_brouwer_bar_writers() -> None:
    assert set(BROUWER_FIGURES) == {
        BROUWER_ETUDE,
        BROUWER_NOVIEMBRE,
        BROUWER_ELOGIO,
        BROUWER_SARABANDE,
    }
    assert set(BROUWER_FIGURE_NAMES) == set(BROUWER_FIGURES)
    assert len(set(BROUWER_FIGURE_NAMES.values())) == len(BROUWER_FIGURES)
    assert BROUWER_PATTERNS == frozenset(BROUWER_FIGURE_NAMES.values())
    assert figure_pattern(BROUWER_ETUDE) == "brouwer_etude"
    assert figure_pattern(BROUWER_NOVIEMBRE) == "noviembre"


def test_preview_returns_an_aba_plan_notes_and_a_hash() -> None:
    before = _snapshot()
    result = preview_brouwer_sentence(brouwer_aba_spec())

    assert result.ok and not result.errors
    assert result.plan == {
        "kind": "figure",
        "length": 3,
        "selected": True,
        "spans": [
            {"figure": BROUWER_ETUDE, "bars": [0]},
            {"figure": BROUWER_NOVIEMBRE, "bars": [1]},
            {"figure": BROUWER_ETUDE, "bars": [2]},
        ],
    }
    assert result.row == ["brouwer_etude", "noviembre", "brouwer_etude"]
    assert result.notes
    assert {note["bar"] for note in result.notes} == {0, 1, 2}
    assert all(note["voice"] in {1, 2, 3} for note in result.notes)
    assert result.render_hash and result.render_hash.startswith("sha256:")
    assert result.matrix
    assert sum(1 for row in result.matrix if row["render"]) == 1
    assert specs.SENTENCE_SPECS == before


def test_every_registered_figure_renders_through_its_bar_writer() -> None:
    spec = brouwer_aba_spec()
    for figure in BROUWER_FIGURES:
        bars = tuple(replace(slot, figure=figure) for slot in spec.slots)
        result = preview_brouwer_sentence(replace(spec, slots=bars))
        assert result.ok, (figure, result.errors)
        assert result.notes
        assert set(result.row) == {figure_pattern(figure)}


def test_preview_is_deterministic() -> None:
    first = preview_brouwer_sentence(brouwer_aba_spec())
    second = preview_brouwer_sentence(brouwer_aba_spec())
    assert first.render_hash == second.render_hash
    assert first.notes == second.notes
    assert first.plan == second.plan
    assert first.row == second.row
    assert first.matrix == second.matrix


def test_preview_notes_and_hash_change_when_a_figure_changes() -> None:
    spec = brouwer_aba_spec()
    first = preview_brouwer_sentence(spec)
    swapped = replace(
        spec,
        slots=(spec.slots[0], replace(spec.slots[1], figure=BROUWER_ELOGIO), spec.slots[2]),
    )
    second = preview_brouwer_sentence(swapped)
    assert first.ok and second.ok
    assert first.render_hash != second.render_hash
    assert first.notes != second.notes
    assert first.row == ["brouwer_etude", "noviembre", "brouwer_etude"]
    assert second.row == ["brouwer_etude", "elogio_pizz", "brouwer_etude"]


def test_unknown_figure_is_rejected_before_rendering() -> None:
    spec = brouwer_aba_spec()
    bad = replace(
        spec,
        slots=(replace(spec.slots[0], figure=999), *spec.slots[1:]),
    )
    errors = validate_brouwer_spec(bad)
    assert [(error.path, "BROUWER_FIGURES" in error.message) for error in errors] == [
        ("slots[0].figure", True)
    ]
    result = preview_brouwer_sentence(bad)
    assert not result.ok
    assert result.notes == ()
    assert result.render_hash is None


def test_non_brouwer_pattern_and_cell_slots_are_rejected() -> None:
    spec = brouwer_aba_spec()
    wrong_pattern = replace(spec, pattern="castillo")
    assert [error.path for error in validate_brouwer_spec(wrong_pattern)] == ["pattern"]

    cell_slot = replace(spec.slots[0], figure=None, cell="galop1")
    wrong_slot = replace(spec, slots=(cell_slot, *spec.slots[1:]))
    assert any(error.path == "slots[0].cell" for error in validate_brouwer_spec(wrong_slot))


def test_fixture_is_bounded_and_rejects_unknown_keys() -> None:
    spec = brouwer_aba_spec()
    huge = preview_brouwer_sentence(spec, {"length": MAX_PLAN_BARS + 1})
    assert not huge.ok
    assert huge.errors[0].path == "fixture"
    assert "fixture.length" in huge.errors[0].message

    unknown = preview_brouwer_sentence(spec, {"nope": 1})
    assert not unknown.ok
    assert unknown.errors[0].path == "fixture"
    assert "unknown field" in unknown.errors[0].message


def test_a_longer_fixture_repeats_the_three_bar_tile() -> None:
    result = preview_brouwer_sentence(brouwer_aba_spec(), {"length": 6})
    assert result.ok
    assert result.plan["length"] == 6
    assert result.row == [
        "brouwer_etude",
        "noviembre",
        "brouwer_etude",
        "brouwer_etude",
        "noviembre",
        "brouwer_etude",
    ]
    assert {note["bar"] for note in result.notes} == set(range(6))


def test_candidate_never_reaches_the_production_registry() -> None:
    # Brouwer has no registered sentence, so the production planner still falls
    # back to the code path.
    before = _snapshot()
    assert ("brouwer_etude", "4/4") not in before
    assert plan_sentence("brouwer_etude", "4/4", 3, 0) is None

    preview_brouwer_sentence(brouwer_aba_spec(), {"length": 6})

    after = _snapshot()
    assert after == before
    assert ("brouwer_etude", "4/4") not in specs.SENTENCE_SPECS
    assert plan_sentence("brouwer_etude", "4/4", 3, 0) is None
    assert "brouwer_etude" in BROUWER_PATTERNS
