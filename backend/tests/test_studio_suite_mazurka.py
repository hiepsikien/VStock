"""Preview-only Suite Popular Brasileira candidate: Mazurka-Choro in 3/4.

The candidate JSON must round-trip through the v1 schema, the preview must
render a real 3/4 bar through the existing Villa writers, dispatch must reach it
through the shared Villa family, and the candidate must stay invisible to the
production registry.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.sonify import sentence_specs as specs
from app.sonify.form import METER_34
from app.sonify.guitar_villa_figures import (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_FIGURES,
)
from app.sonify.sentence_specs import plan_sentence
from app.studio import dispatch
from app.studio.candidates.suite_mazurka import (
    SUITE_MAZURKA_AABA,
    SUITE_MAZURKA_AABA_ID,
    SUITE_MAZURKA_PATH,
    load_suite_mazurka,
    suite_mazurka_spec,
)
from app.studio.sentence_spec import parse_payload, specs_to_payload
from app.studio.villa_preview import (
    MAX_PLAN_BARS,
    VILLA_METERS,
    preview_villa_sentence,
    validate_villa_spec,
)

BARS_PER_TILE = 4
QUARTER_BEATS_34 = METER_34.quarter_beats


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
    specs_in = load_suite_mazurka()
    payload = specs_to_payload(specs_in)
    assert parse_payload(payload) == specs_in
    assert payload["schema_version"] == 1
    assert payload["runtime"] == "code"

    # The file on disk is already the canonical wrapper.
    on_disk = json.loads(SUITE_MAZURKA_PATH.read_text(encoding="utf-8"))
    assert on_disk == payload
    assert specs_in == (SUITE_MAZURKA_AABA,)


def test_candidate_is_a_four_bar_3_4_aaba_of_existing_figures() -> None:
    spec = suite_mazurka_spec()
    assert spec.id == SUITE_MAZURKA_AABA_ID
    assert spec.pattern == "villa_pattern"
    assert spec.meter == "3/4"
    assert spec.meter in VILLA_METERS
    assert VILLA_METERS[spec.meter] is METER_34
    assert spec.span.tile == BARS_PER_TILE
    assert (spec.select.length_min, spec.select.length_max) == (4, None)
    assert [slot.figure for slot in spec.slots] == [
        VILLA_ARPEGGIO,
        VILLA_ARPEGGIO,
        VILLA_CHORD_MELODY,
        VILLA_ARPEGGIO,
    ]
    assert [slot.start for slot in spec.slots] == [0, 1, 2, 3]
    assert all(slot.bars == 1 for slot in spec.slots)
    assert set(slot.figure for slot in spec.slots) <= set(VILLA_FIGURES)
    assert validate_villa_spec(spec) == []


def test_preview_renders_one_real_3_4_phrase() -> None:
    before = _snapshot()
    result = preview_villa_sentence(suite_mazurka_spec())

    assert result.ok and not result.errors
    assert result.plan == {
        "kind": "figure",
        "length": BARS_PER_TILE,
        "selected": True,
        "spans": [
            {"figure": VILLA_ARPEGGIO, "bars": [0]},
            {"figure": VILLA_ARPEGGIO, "bars": [1]},
            {"figure": VILLA_CHORD_MELODY, "bars": [2]},
            {"figure": VILLA_ARPEGGIO, "bars": [3]},
        ],
    }
    assert result.row == [
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
    ]
    assert {note["bar"] for note in result.notes} == set(range(BARS_PER_TILE))
    assert all(note["voice"] in {1, 2, 3} for note in result.notes)
    # A 3/4 bar is three quarter beats. Nothing may spill into a fourth beat:
    # that would mean the 4/4 branch rendered while the spec said 3/4.
    assert all(
        note["beat"] + note["duration"] <= QUARTER_BEATS_34
        for note in result.notes
    )
    assert any(
        note["beat"] + note["duration"] == QUARTER_BEATS_34 for note in result.notes
    )
    assert result.render_hash and result.render_hash.startswith("sha256:")
    assert result.matrix
    assert sum(1 for row in result.matrix if row["render"]) == 1
    assert specs.SENTENCE_SPECS == before
    assert specs.SENTENCE_SPECS is not before


def test_preview_is_deterministic() -> None:
    first = preview_villa_sentence(suite_mazurka_spec())
    second = preview_villa_sentence(suite_mazurka_spec())
    assert first.render_hash == second.render_hash
    assert first.notes == second.notes
    assert first.plan == second.plan
    assert first.row == second.row
    assert first.matrix == second.matrix


def test_preview_hash_and_notes_change_when_a_figure_changes() -> None:
    spec = suite_mazurka_spec()
    first = preview_villa_sentence(spec)
    swapped = replace(
        spec,
        slots=(
            spec.slots[0],
            replace(spec.slots[1], figure=VILLA_CHORD_MELODY),
            *spec.slots[2:],
        ),
    )
    second = preview_villa_sentence(swapped)
    assert first.ok and second.ok
    assert first.render_hash != second.render_hash
    assert first.notes != second.notes
    assert second.row[1] == "villa_chord_melody"


def test_fixture_cannot_flip_the_candidate_to_4_4() -> None:
    result = preview_villa_sentence(suite_mazurka_spec(), {"meter": "4/4"})
    assert not result.ok
    assert result.errors[0].path == "fixture"
    assert "does not match spec.meter" in result.errors[0].message


def test_a_longer_fixture_repeats_the_four_bar_tile() -> None:
    result = preview_villa_sentence(suite_mazurka_spec(), {"length": 8})
    assert result.ok
    assert result.plan["length"] == 8
    assert result.row == [
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
    ]
    assert {note["bar"] for note in result.notes} == set(range(8))
    assert all(
        note["beat"] + note["duration"] <= QUARTER_BEATS_34
        for note in result.notes
    )


def test_preview_reaches_the_candidate_through_dispatch() -> None:
    spec = suite_mazurka_spec()
    assert dispatch.family_for(spec.pattern) == dispatch.VILLA

    direct = preview_villa_sentence(spec)
    dispatched = dispatch.preview_sentence(spec)
    assert dispatched.ok
    assert dispatched.render_hash == direct.render_hash
    assert dispatched.notes == direct.notes
    assert dispatched.plan == direct.plan
    assert dispatched.row == direct.row

    resolved = dispatch.resolve_fixture(spec)
    assert resolved["pattern"] == "villa_pattern"
    assert resolved["meter"] == "3/4"
    assert resolved["length"] == BARS_PER_TILE


def test_fixture_is_bounded_and_rejects_unknown_keys() -> None:
    spec = suite_mazurka_spec()
    huge = preview_villa_sentence(spec, {"length": MAX_PLAN_BARS + 1})
    assert not huge.ok
    assert huge.errors[0].path == "fixture"
    assert "fixture.length" in huge.errors[0].message

    unknown = preview_villa_sentence(spec, {"nope": 1})
    assert not unknown.ok
    assert unknown.errors[0].path == "fixture"
    assert "unknown field" in unknown.errors[0].message


def test_candidate_never_reaches_the_production_registry() -> None:
    # Villa has no registered 3/4 sentence; the production planner must keep
    # falling back to the code path for this key.
    before = _snapshot()
    assert ("villa_pattern", "3/4") not in before
    assert plan_sentence("villa_pattern", "3/4", BARS_PER_TILE, 0) is None

    preview_villa_sentence(suite_mazurka_spec(), {"length": 8})

    after = _snapshot()
    assert after == before
    assert ("villa_pattern", "3/4") not in specs.SENTENCE_SPECS
    assert plan_sentence("villa_pattern", "3/4", BARS_PER_TILE, 0) is None
    assert not [key for key in specs.SENTENCE_SPECS if key[0].startswith("suite_")]
