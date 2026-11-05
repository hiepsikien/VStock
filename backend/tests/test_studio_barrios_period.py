"""Preview-only Barrios period pilot (*La Catedral*).

The candidate must round-trip from JSON, render through the real Barrios per-bar
renderers, and never enter the production sentence registry.
"""

from __future__ import annotations

import json
from dataclasses import replace

from app.sonify import sentence_specs as specs

# Import both production owners so the registry snapshot is complete before a
# candidate preview checks that it did not change.
import app.sonify.guitar_sor  # noqa: F401
import app.sonify.guitar_torroba  # noqa: F401
from app.sonify.guitar_barrios_figures import (
    BARRIOS_FIGURES,
    BARRIOS_PRELUDIO,
    BARRIOS_TREMOLO,
    figure_pattern,
)
from app.sonify.sentence_specs import plan_sentence
from app.studio.barrios_preview import (
    preview_barrios_period,
    validate_barrios_period,
)
from app.studio.candidates import (
    BARRIOS_CATHEDRAL_PERIOD,
    BARRIOS_CATHEDRAL_PATH,
    barrios_cathedral_spec,
    load_barrios_cathedral,
)


def _snapshot() -> dict:
    return dict(specs.SENTENCE_SPECS)


def test_the_candidate_json_round_trips_to_the_builder() -> None:
    payload = json.loads(BARRIOS_CATHEDRAL_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["runtime"] == "code"
    loaded = load_barrios_cathedral()
    assert loaded == (BARRIOS_CATHEDRAL_PERIOD,)
    assert barrios_cathedral_spec() == BARRIOS_CATHEDRAL_PERIOD


def test_the_period_is_preludio_tremolo_preludio() -> None:
    spec = barrios_cathedral_spec()
    assert spec.id == "barrios_cathedral_period"
    assert spec.pattern == "preludio"
    assert spec.meter == "4/4"
    assert spec.span.tile == 12 and spec.span.exact
    assert [(slot.start, slot.bars) for slot in spec.slots] == [
        (0, 4),
        (4, 4),
        (8, 4),
    ]
    assert [slot.figure for slot in spec.slots] == [
        BARRIOS_PRELUDIO,
        BARRIOS_TREMOLO,
        BARRIOS_PRELUDIO,
    ]
    # Every authored figure is a live realizer, not a second production table.
    assert all(slot.figure in BARRIOS_FIGURES for slot in spec.slots)
    assert figure_pattern(BARRIOS_PRELUDIO) == "preludio"
    assert figure_pattern(BARRIOS_TREMOLO) == "tremolo"


def test_the_candidate_is_not_registered_and_preview_does_not_leak() -> None:
    before = _snapshot()
    assert ("preludio", "4/4") not in before
    assert plan_sentence("preludio", "4/4", 12, 0) is None

    result = preview_barrios_period(barrios_cathedral_spec(), {"bars": 4})
    assert result.ok

    after = _snapshot()
    assert after == before
    assert specs.SENTENCE_SPECS is not before
    assert ("preludio", "4/4") not in specs.SENTENCE_SPECS
    assert plan_sentence("preludio", "4/4", 12, 0) is None


def test_preview_returns_a_plan_notes_and_a_hash() -> None:
    result = preview_barrios_period(barrios_cathedral_spec())

    assert result.ok and not result.errors
    assert result.plan == {
        "kind": "barrios_period",
        "pattern": "preludio",
        "meter": "4/4",
        "length": 12,
        "selected": True,
        "spans": [
            {"figure": BARRIOS_PRELUDIO, "pattern": "preludio", "bars": [0, 1, 2, 3]},
            {"figure": BARRIOS_TREMOLO, "pattern": "tremolo", "bars": [4, 5, 6, 7]},
            {"figure": BARRIOS_PRELUDIO, "pattern": "preludio", "bars": [8, 9, 10, 11]},
        ],
    }
    assert result.row == (
        ["preludio"] * 4 + ["tremolo"] * 4 + ["preludio"] * 4
    )
    assert result.notes
    assert all(note["voice"] in {1, 2, 3} for note in result.notes)
    assert {note["bar"] for note in result.notes} == set(range(12))
    assert result.render_hash and result.render_hash.startswith("sha256:")


def test_preview_is_deterministic() -> None:
    first = preview_barrios_period(barrios_cathedral_spec())
    second = preview_barrios_period(barrios_cathedral_spec())
    assert first.render_hash == second.render_hash
    assert first.notes == second.notes
    assert first.row == second.row
    assert first.matrix == second.matrix


def test_the_middle_slot_sings_the_sixteenth_tremolo() -> None:
    result = preview_barrios_period(barrios_cathedral_spec())
    tremolo = [
        note for note in result.notes if note["bar"] == 4 and note["voice"] == 1
    ]
    assert len(tremolo) == 16  # four quarter clusters of four sixteenths
    assert all(abs(note["duration"] - 0.25) < 1e-9 for note in tremolo)
    preludio = [
        note for note in result.notes if note["bar"] == 0 and note["voice"] == 1
    ]
    # Each 2-beat cell sings count 1 for six sixteenths and count 7 for two.
    assert [note["duration"] for note in preludio] == [1.5, 0.5, 1.5, 0.5]


def test_preview_respects_the_bounded_bars_fixture() -> None:
    full = preview_barrios_period(barrios_cathedral_spec(), {"bars": 12})
    short = preview_barrios_period(barrios_cathedral_spec(), {"bars": 4})
    assert {note["bar"] for note in full.notes} == set(range(12))
    assert {note["bar"] for note in short.notes} == set(range(4))
    assert len(short.notes) < len(full.notes)
    assert short.render_hash != full.render_hash
    assert short.row == full.row


def test_unknown_figure_is_rejected() -> None:
    spec = replace(
        barrios_cathedral_spec(),
        slots=(
            replace(barrios_cathedral_spec().slots[0], figure=999),
            *barrios_cathedral_spec().slots[1:],
        ),
    )
    errors = validate_barrios_period(spec)
    assert [(error.path, "BARRIOS_FIGURES" in error.message) for error in errors] == [
        ("slots[0].figure", True)
    ]
    result = preview_barrios_period(spec)
    assert not result.ok
    assert result.as_response()["plan"] is None


def test_a_period_with_a_gap_is_rejected() -> None:
    spec = replace(
        barrios_cathedral_spec(),
        slots=(replace(barrios_cathedral_spec().slots[0], bars=3),),
    )
    errors = validate_barrios_period(spec)
    assert any(error.path == "slots" and "tile" in error.message for error in errors)


def test_a_non_exact_length_is_rejected_by_the_fixture() -> None:
    result = preview_barrios_period(barrios_cathedral_spec(), {"length": 8})
    assert not result.ok
    assert result.errors[0].path == "fixture"


def test_the_matrix_is_minimal_and_marks_the_render_row() -> None:
    result = preview_barrios_period(barrios_cathedral_spec())
    assert len(result.matrix) == 1
    row = result.matrix[0]
    assert row["selected"] is True
    assert row["render"] is True
    assert row["renderHash"] == result.render_hash
    assert row["spans"] == result.plan["spans"]

    narrowed = preview_barrios_period(
        barrios_cathedral_spec(),
        {"matrix": {"lengths": [8, 12], "n": [0], "closes": [False], "rise": [0]}},
    )
    assert [row["selected"] for row in narrowed.matrix] == [False, True]
    assert [row["render"] for row in narrowed.matrix] == [False, True]
