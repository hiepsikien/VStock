"""Studio MVP: sentence spec validation and bounded preview.

The preview must go through the real renderers and leave the global
`SENTENCE_SPECS` exactly as it found it.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio as studio_router
from app.sonify import sentence_specs as specs
from app.sonify.guitar_sor import GALOP_CELL_1, GALOP_CELL_2, GALOP_CYCLE
from app.sonify.guitar_torroba import (
    CASTILLO_34_WALK,
    CASTILLO_44_TYPE7_L5,
    DANZA_34_SPECS,
    FANDANGUILLO_SPECS,
    SONATINA_SPECS,
    _FIGURES,
)
from app.sonify.sentence_specs import plan_sentence
from app.studio import preview
from app.studio.export import SPECS_DIR
from app.studio.preview import preview_spec, validate_spec


def _snapshot() -> dict:
    return dict(specs.SENTENCE_SPECS)


def _assert_restored(snapshot: dict) -> None:
    assert specs.SENTENCE_SPECS == snapshot
    # The object identity must survive too: other modules hold the same dict.
    assert specs.SENTENCE_SPECS is not snapshot


def test_validate_accepts_real_torroba_specs() -> None:
    before = _snapshot()
    for spec in (
        CASTILLO_34_WALK,
        CASTILLO_44_TYPE7_L5,
        SONATINA_SPECS[0],
        FANDANGUILLO_SPECS[0],
        DANZA_34_SPECS[0],
    ):
        assert validate_spec(spec) == [], spec.id
    _assert_restored(before)


def test_validate_accepts_the_galop_cycle() -> None:
    assert validate_spec(GALOP_CYCLE) == []


def test_validate_rejects_a_typo_figure() -> None:
    spec = replace(
        CASTILLO_34_WALK,
        slots=(replace(CASTILLO_34_WALK.slots[0], figure=999),),
    )
    errors = validate_spec(spec)
    assert [(error.path, "figure 999" in error.message) for error in errors] == [
        ("slots[0].figure", True)
    ]


def test_validate_rejects_a_typo_cell() -> None:
    spec = replace(
        GALOP_CYCLE,
        slots=(replace(GALOP_CYCLE.slots[0], cell="galop9"), GALOP_CYCLE.slots[1]),
    )
    errors = validate_spec(spec)
    assert any(error.path == "slots[0].cell" for error in errors)


def test_validate_rejects_a_bad_meter() -> None:
    unknown = replace(CASTILLO_34_WALK, meter="3/5")
    assert [error.path for error in validate_spec(unknown)] == ["meter"]

    # 6/8 is a real meter, but castillo has no 6/8 registration on purpose.
    unregistered = replace(CASTILLO_34_WALK, meter="6/8")
    errors = validate_spec(unregistered)
    assert [error.path for error in errors] == ["meter"]
    assert "not registered" in errors[0].message


def test_validate_rejects_a_bad_slot() -> None:
    spec = replace(
        CASTILLO_34_WALK,
        slots=(replace(CASTILLO_34_WALK.slots[0], bars=20),),
    )
    errors = validate_spec(spec)
    assert any(error.path.startswith("slots[0]") for error in errors)


def test_validate_rejects_a_missing_realizer() -> None:
    spec = replace(
        CASTILLO_34_WALK,
        slots=(replace(CASTILLO_34_WALK.slots[0], figure=None),),
    )
    errors = validate_spec(spec)
    assert any(
        "exactly one of figure, cell, or procedure" in error.message
        for error in errors
    )


def test_preview_returns_a_plan_notes_and_a_hash() -> None:
    before = _snapshot()
    result = preview_spec(CASTILLO_34_WALK)

    assert result.ok and not result.errors
    assert result.plan == {
        "kind": "figure",
        "length": 9,
        "selected": True,
        "spans": [{"figure": CASTILLO_34_WALK.slots[0].figure, "bars": list(range(9))}],
    }
    assert result.row == ["castillo"] * 9
    assert result.notes
    assert all(note["voice"] in {1, 2, 3} for note in result.notes)
    assert {note["bar"] for note in result.notes} == set(range(9))
    assert result.render_hash and result.render_hash.startswith("sha256:")
    _assert_restored(before)


def test_preview_is_deterministic() -> None:
    first = preview_spec(CASTILLO_34_WALK)
    second = preview_spec(CASTILLO_34_WALK)
    assert first.render_hash == second.render_hash
    assert first.notes == second.notes
    assert first.matrix == second.matrix


def test_preview_does_not_leak_the_authoring_spec() -> None:
    before = _snapshot()
    real_spans = plan_sentence("castillo", "3/4", 9, 0)

    authored = replace(
        CASTILLO_34_WALK,
        id="studio_probe",
        slots=(replace(CASTILLO_34_WALK.slots[0], start=1, bars=8),),
    )
    result = preview_spec(authored)
    assert result.ok
    assert result.plan["spans"][0]["bars"] == [1, 2, 3, 4, 5, 6, 7, 8]

    _assert_restored(before)
    assert plan_sentence("castillo", "3/4", 9, 0) == real_spans


def test_preview_of_galop_returns_the_cycle_plan() -> None:
    before = _snapshot()
    result = preview_spec(GALOP_CYCLE)

    assert result.ok
    assert result.plan == {
        "kind": "cell",
        "length": 8,
        "selected": True,
        "spans": [
            {"cell": GALOP_CELL_1, "bars": [0, 1, 2, 3]},
            {"cell": GALOP_CELL_2, "bars": [4, 5, 6, 7]},
        ],
    }
    assert result.row == ["galop"] * 8
    assert result.notes
    _assert_restored(before)


def test_a_cycle_fixture_accepts_run_length() -> None:
    result = preview_spec(GALOP_CYCLE, {"run_length": 10})
    assert result.ok
    assert result.plan["length"] == 10
    assert len(result.row or []) == 10


def test_preview_respects_the_bounded_bars_fixture() -> None:
    full = preview_spec(CASTILLO_34_WALK, {"bars": 9})
    short = preview_spec(CASTILLO_34_WALK, {"bars": 2})
    assert {note["bar"] for note in full.notes} == set(range(9))
    assert {note["bar"] for note in short.notes} == {0, 1}
    assert len(short.notes) < len(full.notes)
    assert short.render_hash != full.render_hash


def test_preview_fixture_rejects_a_meter_that_does_not_match() -> None:
    result = preview_spec(CASTILLO_34_WALK, {"meter": "4/4"})
    assert not result.ok
    assert result.errors[0].path == "fixture"


def test_preview_matrix_marks_the_fixture_render_row() -> None:
    result = preview_spec(CASTILLO_34_WALK)
    assert len(result.matrix) == 12 * 4 * 2 * 3
    rendered = [row for row in result.matrix if row["render"]]
    assert len(rendered) == 1
    row = rendered[0]
    assert (row["length"], row["n"], row["closes"], row["rise"]) == (9, 0, False, 0)
    assert row["spans"] == result.plan["spans"]
    assert row["renderHash"] == result.render_hash
    assert all(row["renderHash"] is None for row in result.matrix if not row["render"])
    # Even n only for the walk archetype.
    assert all(row["n"] % 2 == 0 for row in result.matrix if row["selected"])


def test_preview_matrix_can_be_narrowed_and_is_bounded() -> None:
    result = preview_spec(
        CASTILLO_34_WALK,
        {"matrix": {"lengths": [9], "n": [0], "closes": [False], "rise": [0]}},
    )
    assert len(result.matrix) == 1
    assert result.matrix[0]["render"] is True

    invalid = preview_spec(CASTILLO_34_WALK, {"matrix": {"lengths": [0]}})
    assert not invalid.ok
    assert invalid.errors[0].path == "fixture"


def test_validate_errors_are_json_shaped() -> None:
    spec = replace(
        CASTILLO_34_WALK,
        slots=(replace(CASTILLO_34_WALK.slots[0], figure=999),),
    )
    result = preview_spec(spec)
    payload = result.as_response()
    assert payload["ok"] is False
    assert payload["errors"] == [
        {"path": "slots[0].figure", "message": "figure 999 is not in _FIGURES"}
    ]
    assert payload["plan"] is None


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(preview, "parse_spec", lambda _mapping: CASTILLO_34_WALK)
    app = FastAPI()
    app.include_router(studio_router.router)
    return TestClient(app)


def test_a_committed_json_spec_round_trips_through_the_api() -> None:
    payload = json.loads(
        (SPECS_DIR / "castillo-3-4.json").read_text(encoding="utf-8")
    )["specs"][0]
    app = FastAPI()
    app.include_router(studio_router.router)
    client = TestClient(app)

    validated = client.post("/v1/studio/sentence/validate", json=payload)
    assert validated.status_code == 200
    assert validated.json() == {"ok": True, "errors": []}

    result = client.post(
        "/v1/studio/sentence/preview",
        json={"spec": payload, "fixture": {"length": 9, "bars": 9}},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is True
    assert body["plan"]["kind"] == "figure"
    assert body["renderHash"].startswith("sha256:")
    assert body["notes"]


def test_api_validate_shape(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post("/v1/studio/sentence/validate", json={"id": "anything"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "errors": []}


def test_api_preview_shape(monkeypatch) -> None:
    client = _client(monkeypatch)
    response = client.post(
        "/v1/studio/sentence/preview",
        json={"spec": {"id": "anything"}, "fixture": {"bars": 2}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["row"] == ["castillo"] * 9
    assert body["plan"]["kind"] == "figure"
    assert body["notes"]
    assert {note["bar"] for note in body["notes"]} == {0, 1}
    assert body["renderHash"].startswith("sha256:")
    assert len(body["matrix"]) == 12 * 4 * 2 * 3


def test_api_reports_the_missing_parser(monkeypatch) -> None:
    if importlib.util.find_spec("app.studio.sentence_spec") is not None:
        pytest.skip("workstream A's parser is present")
    client = _client(monkeypatch)
    monkeypatch.undo()
    response = client.post("/v1/studio/sentence/validate", json={"id": "anything"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "spec"
    assert "app.studio.sentence_spec.parse_spec" in body["errors"][0]["message"]


def test_figure_ids_are_real_torroba_figures() -> None:
    """The fixture specs used above must point at live renderers."""
    for spec in (CASTILLO_34_WALK, CASTILLO_44_TYPE7_L5, *SONATINA_SPECS[:1]):
        for slot in spec.slots:
            assert slot.figure in _FIGURES
    assert {GALOP_CELL_1, GALOP_CELL_2} == {"galop1", "galop2"}


def test_preview_matches_the_galop_code_render_except_boundary_ties() -> None:
    """The preview runs the same per-bar realizer as the full score.

    The full render adds its global slur/bass post-passes after the bars are
    written; for this fixture that only touches the closing barline. Melody,
    rhythm, pitches, and the cycle are identical.
    """
    from collections import Counter

    from test_sentence_galop_migration import FRAME, _galop_score

    body = 8
    score = _galop_score(body)
    key = lambda event: (
        event.bar - FRAME,
        round(event.beat, 6),
        round(event.duration_beats, 6),
        event.midi,
        event.voice,
    )
    full = Counter(
        key(event)
        for event in (*score.lead, *score.support, *score.low)
        if event.midi is not None and FRAME <= event.bar < FRAME + body
    )

    result = preview_spec(
        GALOP_CYCLE,
        {
            "length": body,
            "bars": body,
            "bpm": 88,
            "character": "rally",
            "mode": "major",
            "meter": "4/4",
        },
    )
    preview_notes = Counter(
        (
            note["bar"],
            note["beat"],
            note["duration"],
            note["midi"],
            note["voice"],
        )
        for note in result.notes
    )

    assert not preview_notes - full
    missing = full - preview_notes
    assert all(note[0] == body - 1 for note in missing)
    assert sum(missing.values()) <= 2


def test_fixture_path_is_documented() -> None:
    doc = pathlib.Path(preview.__file__).read_text()
    keys = (
        "pattern",
        "meter",
        "length",
        "n",
        "closes",
        "rise",
        "bars",
        "character",
        "profile",
    )
    for key in keys:
        assert f"`{key}`" in doc, key
