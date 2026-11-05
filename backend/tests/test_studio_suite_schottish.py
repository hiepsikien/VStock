"""Preview-only Suite candidate: Schottish-Choro, a folded 4/4 probe.

The source is 2/4 but `form.Meter` has no 2/4, so the candidate renders through
the existing 4/4 engine and records the fold caveat. The JSON must round-trip,
the preview must render a real 4/4 phrase through the existing Villa writers,
dispatch must reach it through the shared Villa family, and the candidate must
stay invisible to the production registry.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.sonify import sentence_specs as specs
from app.sonify.form import METER_44
from app.sonify.guitar_villa_figures import (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_FIGURES,
)
from app.sonify.sentence_specs import plan_sentence
from app.studio import dispatch
from app.studio.candidates.suite_schottish import (
    ENGINE_METER,
    FORM_FOLD,
    METER_CAVEAT,
    SOURCE_METER,
    SUITE_SCHOTTISH_ABAB,
    SUITE_SCHOTTISH_ABAB_ID,
    SUITE_SCHOTTISH_PATH,
    load_suite_schottish,
    suite_schottish_spec,
)
from app.studio.sentence_spec import parse_payload, specs_to_payload
from app.studio.villa_preview import (
    MAX_PLAN_BARS,
    VILLA_METERS,
    preview_villa_sentence,
    validate_villa_spec,
)

BARS_PER_TILE = 4
QUARTER_BEATS_44 = METER_44.quarter_beats
ABAB_FIGURES = [
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
]


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
    specs_in = load_suite_schottish()
    payload = specs_to_payload(specs_in)
    assert parse_payload(payload) == specs_in
    assert payload["schema_version"] == 1
    assert payload["runtime"] == "code"

    # The file on disk is already the canonical wrapper.
    on_disk = json.loads(SUITE_SCHOTTISH_PATH.read_text(encoding="utf-8"))
    assert on_disk == payload
    assert specs_in == (SUITE_SCHOTTISH_ABAB,)


def test_candidate_records_the_2_4_to_4_4_fold_caveat() -> None:
    # The engine cannot see a 2/4 source; the candidate says so in data, not
    # only in prose.
    assert SOURCE_METER == "2/4"
    assert ENGINE_METER == "4/4"
    assert FORM_FOLD == 2
    assert METER_CAVEAT.strip()
    assert "fold" in METER_CAVEAT.lower()
    assert suite_schottish_spec().meter == ENGINE_METER


def test_candidate_is_a_four_bar_folded_4_4_abab_of_existing_figures() -> None:
    spec = suite_schottish_spec()
    assert spec.id == SUITE_SCHOTTISH_ABAB_ID
    # The movement id stays free for a future registered pattern.
    assert spec.id != "suite_schottish"
    assert spec.pattern == "villa_pattern"
    assert spec.meter == "4/4"
    assert spec.meter in VILLA_METERS
    assert VILLA_METERS[spec.meter] is METER_44
    assert spec.span.tile == BARS_PER_TILE
    assert (spec.select.length_min, spec.select.length_max) == (4, None)
    assert [slot.figure for slot in spec.slots] == ABAB_FIGURES
    assert [slot.start for slot in spec.slots] == [0, 1, 2, 3]
    assert all(slot.bars == 1 for slot in spec.slots)
    assert set(slot.figure for slot in spec.slots) <= set(VILLA_FIGURES)
    # ABAB is a repeated source bar-pair, not one 4/4 melody.
    assert ABAB_FIGURES[:2] == ABAB_FIGURES[2:]
    assert validate_villa_spec(spec) == []


def test_preview_renders_one_real_4_4_folded_phrase() -> None:
    before = _snapshot()
    result = preview_villa_sentence(suite_schottish_spec())

    assert result.ok and not result.errors
    assert result.plan == {
        "kind": "figure",
        "length": BARS_PER_TILE,
        "selected": True,
        "spans": [
            {"figure": figure, "bars": [bar]}
            for bar, figure in enumerate(ABAB_FIGURES)
        ],
    }
    assert result.row == [
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
        "villa_chord_melody",
    ]
    assert {note["bar"] for note in result.notes} == set(range(BARS_PER_TILE))
    assert all(note["voice"] in {1, 2, 3} for note in result.notes)
    # A 4/4 bar is four quarter beats; nothing may spill past it.
    assert all(
        note["beat"] + note["duration"] <= QUARTER_BEATS_44
        for note in result.notes
    )
    assert any(
        note["beat"] + note["duration"] == QUARTER_BEATS_44 for note in result.notes
    )
    assert result.render_hash and result.render_hash.startswith("sha256:")
    assert result.matrix
    assert sum(1 for row in result.matrix if row["render"]) == 1
    assert specs.SENTENCE_SPECS == before
    assert specs.SENTENCE_SPECS is not before


def test_preview_is_deterministic() -> None:
    first = preview_villa_sentence(suite_schottish_spec())
    second = preview_villa_sentence(suite_schottish_spec())
    assert first.render_hash == second.render_hash
    assert first.notes == second.notes
    assert first.plan == second.plan
    assert first.row == second.row
    assert first.matrix == second.matrix


def test_preview_hash_and_notes_change_when_a_figure_changes() -> None:
    spec = suite_schottish_spec()
    first = preview_villa_sentence(spec)
    swapped = replace(
        spec,
        slots=(
            spec.slots[0],
            replace(spec.slots[1], figure=VILLA_ARPEGGIO),
            *spec.slots[2:],
        ),
    )
    second = preview_villa_sentence(swapped)
    assert first.ok and second.ok
    assert first.render_hash != second.render_hash
    assert first.notes != second.notes
    assert second.row[1] == "villa_arpeggio"


def test_fixture_cannot_flip_the_candidate_to_3_4() -> None:
    result = preview_villa_sentence(suite_schottish_spec(), {"meter": "3/4"})
    assert not result.ok
    assert result.errors[0].path == "fixture"
    assert "does not match spec.meter" in result.errors[0].message


def test_a_longer_fixture_repeats_the_four_bar_tile() -> None:
    result = preview_villa_sentence(suite_schottish_spec(), {"length": 8})
    assert result.ok
    assert result.plan["length"] == 8
    assert result.row == [
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
        "villa_chord_melody",
    ] * 2
    assert {note["bar"] for note in result.notes} == set(range(8))
    assert all(
        note["beat"] + note["duration"] <= QUARTER_BEATS_44
        for note in result.notes
    )


def test_preview_reaches_the_candidate_through_dispatch() -> None:
    spec = suite_schottish_spec()
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
    assert resolved["meter"] == "4/4"
    assert resolved["length"] == BARS_PER_TILE


def test_fixture_is_bounded_and_rejects_unknown_keys() -> None:
    spec = suite_schottish_spec()
    huge = preview_villa_sentence(spec, {"length": MAX_PLAN_BARS + 1})
    assert not huge.ok
    assert huge.errors[0].path == "fixture"
    assert "fixture.length" in huge.errors[0].message

    unknown = preview_villa_sentence(spec, {"nope": 1})
    assert not unknown.ok
    assert unknown.errors[0].path == "fixture"
    assert "unknown field" in unknown.errors[0].message


def test_candidate_never_reaches_the_production_registry() -> None:
    # Villa has no registered 4/4 sentence; the production planner must keep
    # falling back to the code path for this key.
    before = _snapshot()
    assert ("villa_pattern", "4/4") not in before
    assert plan_sentence("villa_pattern", "4/4", BARS_PER_TILE, 0) is None

    preview_villa_sentence(suite_schottish_spec(), {"length": 8})

    after = _snapshot()
    assert after == before
    assert ("villa_pattern", "4/4") not in specs.SENTENCE_SPECS
    assert plan_sentence("villa_pattern", "4/4", BARS_PER_TILE, 0) is None
    assert not [key for key in specs.SENTENCE_SPECS if key[0].startswith("suite_")]
