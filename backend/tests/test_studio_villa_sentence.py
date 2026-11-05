"""Preview-only Villa sentence pilot.

The candidate JSON must round-trip through the v1 schema, the preview must go
through the real Villa bar writers, and the candidate must stay invisible to
the production registry.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.sonify import sentence_specs as specs
from app.sonify.guitar_villa_figures import (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_ETUDE1,
    VILLA_ETUDE11,
    VILLA_FIGURES,
    VILLA_FIGURE_NAMES,
)
from app.sonify.sentence_specs import plan_sentence
from app.studio.candidates import (
    VILLA_ARPEGGIO_PATH,
    load_villa_candidate,
    villa_candidate_spec,
)
from app.studio.sentence_spec import parse_payload, specs_to_payload
from app.studio.villa_preview import (
    MAX_PLAN_BARS,
    VILLA_PATTERNS,
    preview_villa_sentence,
    validate_villa_spec,
)


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
    specs_in = load_villa_candidate()
    payload = specs_to_payload(specs_in)
    assert parse_payload(payload) == specs_in
    assert payload["schema_version"] == 1
    assert payload["runtime"] == "code"

    # The file on disk is already the canonical wrapper.
    on_disk = json.loads(VILLA_ARPEGGIO_PATH.read_text(encoding="utf-8"))
    assert on_disk == payload


def test_candidate_is_an_aba_sentence_of_villa_figures() -> None:
    spec = villa_candidate_spec()
    assert spec.pattern == "villa_pattern"
    assert spec.meter == "4/4"
    assert spec.span.tile == 3
    assert (spec.select.length_min, spec.select.length_max) == (3, None)
    assert [slot.figure for slot in spec.slots] == [
        VILLA_ARPEGGIO,
        VILLA_CHORD_MELODY,
        VILLA_ARPEGGIO,
    ]
    assert [slot.start for slot in spec.slots] == [0, 1, 2]
    assert validate_villa_spec(spec) == []


def test_figure_registry_covers_the_villa_bar_writers() -> None:
    assert set(VILLA_FIGURES) == {
        VILLA_ARPEGGIO,
        VILLA_CHORD_MELODY,
        VILLA_ETUDE1,
        VILLA_ETUDE11,
    }
    assert set(VILLA_FIGURE_NAMES) == set(VILLA_FIGURES)
    assert len(set(VILLA_FIGURE_NAMES.values())) == len(VILLA_FIGURES)


def test_preview_returns_a_plan_notes_and_a_hash() -> None:
    before = _snapshot()
    result = preview_villa_sentence(villa_candidate_spec())

    assert result.ok and not result.errors
    assert result.plan == {
        "kind": "figure",
        "length": 3,
        "selected": True,
        "spans": [
            {"figure": VILLA_ARPEGGIO, "bars": [0]},
            {"figure": VILLA_CHORD_MELODY, "bars": [1]},
            {"figure": VILLA_ARPEGGIO, "bars": [2]},
        ],
    }
    assert result.row == [
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
    ]
    assert result.notes
    assert {note["bar"] for note in result.notes} == {0, 1, 2}
    assert all(note["voice"] in {1, 2, 3} for note in result.notes)
    assert result.render_hash and result.render_hash.startswith("sha256:")
    assert result.matrix
    assert sum(1 for row in result.matrix if row["render"]) == 1
    assert specs.SENTENCE_SPECS == before
    assert specs.SENTENCE_SPECS is not before


def test_preview_is_deterministic() -> None:
    first = preview_villa_sentence(villa_candidate_spec())
    second = preview_villa_sentence(villa_candidate_spec())
    assert first.render_hash == second.render_hash
    assert first.notes == second.notes
    assert first.plan == second.plan
    assert first.row == second.row
    assert first.matrix == second.matrix


def test_preview_hash_changes_when_a_figure_changes() -> None:
    spec = villa_candidate_spec()
    first = preview_villa_sentence(spec)
    swapped = replace(
        spec,
        slots=(replace(spec.slots[1], figure=VILLA_ETUDE1), *spec.slots[2:]),
    )
    second = preview_villa_sentence(swapped)
    assert first.ok and second.ok
    assert first.render_hash != second.render_hash
    assert second.row[1] == "villa_etude1"


def test_unknown_figure_is_rejected_before_rendering() -> None:
    spec = villa_candidate_spec()
    bad = replace(
        spec,
        slots=(replace(spec.slots[0], figure=999), *spec.slots[1:]),
    )
    errors = validate_villa_spec(bad)
    assert [(error.path, "VILLA_FIGURES" in error.message) for error in errors] == [
        ("slots[0].figure", True)
    ]
    result = preview_villa_sentence(bad)
    assert not result.ok
    assert result.notes == ()
    assert result.render_hash is None


def test_non_villa_pattern_and_cell_slots_are_rejected() -> None:
    spec = villa_candidate_spec()
    wrong_pattern = replace(spec, pattern="castillo")
    assert [error.path for error in validate_villa_spec(wrong_pattern)] == ["pattern"]

    cell_slot = replace(spec.slots[0], figure=None, cell="galop1")
    wrong_slot = replace(spec, slots=(cell_slot, *spec.slots[1:]))
    assert any(error.path == "slots[0].cell" for error in validate_villa_spec(wrong_slot))


def test_fixture_must_be_selected_by_the_spec() -> None:
    result = preview_villa_sentence(villa_candidate_spec(), {"length": 2})
    assert not result.ok
    assert result.errors[0].path == "fixture"


def test_villa_fixture_is_bounded_and_rejects_unknown_keys() -> None:
    spec = villa_candidate_spec()
    huge = preview_villa_sentence(spec, {"length": MAX_PLAN_BARS + 1})
    assert not huge.ok
    assert huge.errors[0].path == "fixture"
    assert "fixture.length" in huge.errors[0].message

    unknown = preview_villa_sentence(spec, {"nope": 1})
    assert not unknown.ok
    assert unknown.errors[0].path == "fixture"
    assert "unknown field" in unknown.errors[0].message


def test_a_longer_fixture_repeats_the_three_bar_tile() -> None:
    result = preview_villa_sentence(villa_candidate_spec(), {"length": 6})
    assert result.ok
    assert result.plan["length"] == 6
    assert result.row == [
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
    ]
    assert {note["bar"] for note in result.notes} == set(range(6))


def test_candidate_never_reaches_the_production_registry() -> None:
    # Villa has no registered sentence, so the production planner still falls
    # back to the code path.
    assert ("villa_pattern", "4/4") not in specs.SENTENCE_SPECS
    assert plan_sentence("villa_pattern", "4/4", 3, 0) is None

    before = _snapshot()
    preview_villa_sentence(villa_candidate_spec(), {"length": 6})
    assert specs.SENTENCE_SPECS == before
    assert specs.SENTENCE_SPECS is not before
    assert ("villa_pattern", "4/4") not in specs.SENTENCE_SPECS
    assert "villa_pattern" in VILLA_PATTERNS
