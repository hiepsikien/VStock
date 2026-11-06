"""Contract tests for the explicit Studio figure promote API.

``POST /v1/studio/figure/validate`` must stay pure. ``POST .../promote`` may
only mutate the three in-memory registries when the caller explicitly sends
``apply: true``; it never renders, publishes, or writes SQLite.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_figures
from app.sonify.pattern_doors import STUDIO_DOORS
from app.sonify.pattern_figures import PatternFigure
from app.sonify.pattern_promote import promote_figures, unapply_promotion
from app.sonify.sentence_specs import (
    SENTENCE_SPECS,
    Select,
    SentenceSpec,
    Slot,
    Span,
    register as register_sentence_specs,
)
from app.sonify.texture_figure import TEXTURE_CELLS
from app.studio.texture_spec import parse_texture_spec

PATTERN = "suite_figures_api"
METER = "3/4"


@pytest.fixture(autouse=True)
def _isolate_registries():
    saved_cells = {key: dict(value) for key, value in TEXTURE_CELLS.items()}
    saved_doors = dict(STUDIO_DOORS)
    saved_specs = dict(SENTENCE_SPECS)
    TEXTURE_CELLS.clear()
    STUDIO_DOORS.clear()
    SENTENCE_SPECS.clear()
    try:
        yield
    finally:
        TEXTURE_CELLS.clear()
        TEXTURE_CELLS.update(saved_cells)
        STUDIO_DOORS.clear()
        STUDIO_DOORS.update(saved_doors)
        SENTENCE_SPECS.clear()
        SENTENCE_SPECS.update(saved_specs)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_figures.router)
    return TestClient(app)


def _texture(spec_id: str, bars: int) -> dict[str, Any]:
    return {
        "id": spec_id,
        "composer": "villa",
        "kind": "pattern",
        "level": "topic",
        "runtime": "code",
        "status": "draft",
        "meter_variants": [
            {
                "meter": {
                    "id": METER,
                    "beats": 3,
                    "beat_type": 4,
                    "eighths_per_bar": 6,
                    "strong_eighths": [0],
                    "subbar_breaks": [4],
                    "extra_weights": [[4, 0.8]],
                },
                "materializer": "grid_3_4",
                "transform": "none",
                "unsupported": False,
                "reason": None,
                "sentences": [],
            }
        ],
        "authored": {
            "events": [
                {
                    "bar": bar,
                    "beat": 0.0,
                    "duration_beats": 1.0,
                    "voice": 1,
                    "pitch": {"kind": "chord_root"},
                    "confidence": 0.9,
                    "review": "pending",
                }
                for bar in range(bars)
            ]
        },
    }


def _figure(
    figure_id: str,
    cell_id: str,
    bars: int,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "id": figure_id,
        "cellId": cell_id,
        "bars": bars,
        "tags": tags,
        "spec": _texture(cell_id, bars),
    }


def _pool() -> list[dict[str, Any]]:
    return [
        _figure("fig_key", "cell_key", 4, ["key"]),
        _figure("fig_in2", "cell_in2", 2, ["intro.short"]),
        _figure("fig_in4", "cell_in4", 4, ["intro.long"]),
        _figure("fig_out2", "cell_out2", 2, ["outro.short"]),
        _figure("fig_out4", "cell_out4", 4, ["outro.long"]),
    ]


def _body() -> dict[str, Any]:
    return {"pattern": PATTERN, "meter": METER, "figures": _pool(), "sentences": []}


def _sentence(cell: str) -> dict[str, Any]:
    return {
        "id": "draft_sentence",
        "pattern": PATTERN,
        "meter": METER,
        "select": {
            "length_min": 4,
            "length_max": None,
            "n_parity": "any",
            "n_mod": None,
            "closes": None,
            "rise_min": 0,
        },
        "span": {
            "tile": 4,
            "remainder": "same_figure",
            "truncate_to_length": True,
            "cycle": False,
            "exact": False,
        },
        "slots": [{"start": 0, "bars": 4, "cell": cell, "anchor": "start"}],
    }


def _assert_no_registry_mutation() -> None:
    assert TEXTURE_CELLS == {}
    assert STUDIO_DOORS == {}
    assert SENTENCE_SPECS == {}


def test_validate_complete_pool_returns_body_and_five_cell_ids(
    client: TestClient,
) -> None:
    response = client.post("/v1/studio/figure/validate", json=_body())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["complete"] is True
    assert body["errors"] == []
    assert body["missing"] == []
    assert body["cellIds"] == {
        "key": "cell_key",
        "intro.short": "cell_in2",
        "intro.long": "cell_in4",
        "outro.short": "cell_out2",
        "outro.long": "cell_out4",
    }
    assert body["bodySentence"]["id"] == f"{PATTERN}_cell_key_body"
    assert body["bodySentence"]["slots"][0]["cell"] == "cell_key"
    _assert_no_registry_mutation()


def test_missing_tag_is_reported_without_a_write(client: TestClient) -> None:
    payload = _body()
    payload["figures"] = [
        figure for figure in payload["figures"] if figure["id"] != "fig_out4"
    ]

    response = client.post("/v1/studio/figure/validate", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["complete"] is False
    assert body["missing"] == ["outro.long"]
    # The key figure still exists, so the body projection is derivable.
    assert body["bodySentence"]["id"] == f"{PATTERN}_cell_key_body"
    _assert_no_registry_mutation()


def test_bad_texture_spec_returns_a_path_shaped_error(
    client: TestClient,
) -> None:
    payload = _body()
    payload["figures"][0]["spec"]["status"] = "shipped"

    response = client.post("/v1/studio/figure/validate", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["errors"] == [
        {
            "path": "figures[0].spec.status",
            "message": "unknown value 'shipped'",
        }
    ]
    _assert_no_registry_mutation()


def test_non_dict_spec_and_sentence_are_contract_errors(
    client: TestClient,
) -> None:
    payload = _body()
    payload["figures"][0]["spec"] = [1, 2]
    payload["sentences"] = [1]

    response = client.post("/v1/studio/figure/validate", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    paths = {error["path"] for error in body["errors"]}
    assert "figures[0].spec" in paths
    assert "sentences[0]" in paths
    assert all("expected an object" in error["message"] for error in body["errors"])


def test_duplicate_and_unknown_tags_are_errors(client: TestClient) -> None:
    duplicate = _body()
    duplicate["figures"].append(_figure("fig_key_2", "cell_key_2", 4, ["key"]))
    duplicate_response = client.post(
        "/v1/studio/figure/validate", json=duplicate
    )
    duplicate_body = duplicate_response.json()
    assert duplicate_body["ok"] is False
    assert any(
        "'key' is claimed by more than one figure" in error["message"]
        for error in duplicate_body["errors"]
    )

    unknown = _body()
    unknown["figures"][1]["tags"] = ["mystery"]
    unknown_response = client.post("/v1/studio/figure/validate", json=unknown)
    unknown_body = unknown_response.json()
    assert unknown_body["ok"] is False
    assert any(
        "unknown figure tag 'mystery'" in error["message"]
        for error in unknown_body["errors"]
    )
    assert any(error["path"] == "figures[1].tags" for error in unknown_body["errors"])
    _assert_no_registry_mutation()


def test_a_sentence_slot_using_the_figure_id_is_rejected(
    client: TestClient,
) -> None:
    payload = _body()
    payload["sentences"] = [_sentence("fig_key")]

    response = client.post("/v1/studio/figure/validate", json=payload)

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert any(
        "is a figure id" in error["message"] for error in body["errors"]
    )
    _assert_no_registry_mutation()


def test_promote_defaults_to_validate_only(client: TestClient) -> None:
    response = client.post("/v1/studio/figure/promote", json=_body())

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["complete"] is True
    assert body["applied"] is False
    _assert_no_registry_mutation()


def test_promote_with_apply_registers_cells_body_and_door(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/studio/figure/promote",
        json={**_body(), "apply": True},
        headers={"X-Studio-Session": "test-owner"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is True
    assert body["applied"] is True
    assert body["complete"] is True
    assert set(body["cellIds"].values()) == {
        "cell_key",
        "cell_in2",
        "cell_in4",
        "cell_out2",
        "cell_out4",
    }

    assert set(TEXTURE_CELLS[(PATTERN, METER)]) == set(body["cellIds"].values())
    assert (PATTERN, METER) in SENTENCE_SPECS
    assert len(SENTENCE_SPECS[(PATTERN, METER)]) == 1
    assert ("villa", PATTERN) in STUDIO_DOORS


def test_apply_is_reversible_through_the_promote_helpers(
    client: TestClient,
) -> None:
    client.post(
        "/v1/studio/figure/promote",
        json={**_body(), "apply": True},
        headers={"X-Studio-Session": "test-owner"},
    )

    assert (PATTERN, METER) in TEXTURE_CELLS
    assert ("villa", PATTERN) in STUDIO_DOORS

    # Rebuild the same pure plan, then point it at the door the API installed
    # so ``unapply_promotion`` can remove it by identity.
    pairs = [
        (
            PatternFigure(
                id=figure["id"],
                cell_id=figure["cellId"],
                bars=figure["bars"],
                tags=tuple(figure["tags"]),
            ),
            parse_texture_spec(figure["spec"]),
        )
        for figure in _pool()
    ]
    plan = promote_figures(PATTERN, METER, pairs)
    installed = replace(plan, door=STUDIO_DOORS[("villa", PATTERN)])

    unapply_promotion(installed)

    assert (PATTERN, METER) not in TEXTURE_CELLS
    assert ("villa", PATTERN) not in STUDIO_DOORS
    # ``unapply_promotion`` deliberately does not own SENTENCE_SPECS.
    SENTENCE_SPECS.pop((PATTERN, METER), None)


def test_registration_failure_rolls_back_and_hides_the_trace(
    client: TestClient,
) -> None:
    wrong = SentenceSpec(
        id="already_registered",
        pattern=PATTERN,
        meter=METER,
        select=Select(length_min=2),
        span=Span(tile=2, remainder="same_figure", truncate_to_length=True),
        slots=(Slot(0, 2, cell="someone_else"),),
    )
    register_sentence_specs(PATTERN, METER, wrong)

    response = client.post(
        "/v1/studio/figure/promote",
        json={**_body(), "apply": True},
        headers={"X-Studio-Session": "test-owner"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["ok"] is False
    assert body["applied"] is False
    assert body["errors"]
    assert body["errors"][0]["path"] == "apply"
    assert "Traceback" not in body["errors"][0]["message"]
    # A failed registration must not leave cells or a door behind.
    assert (PATTERN, METER) not in TEXTURE_CELLS
    assert ("villa", PATTERN) not in STUDIO_DOORS


def test_tags_endpoint_lists_the_five_roles(client: TestClient) -> None:
    response = client.get("/v1/studio/figure/tags")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["tags"] == [
        {"name": "key", "bars": None},
        {"name": "intro.short", "bars": 2},
        {"name": "intro.long", "bars": 4},
        {"name": "outro.short", "bars": 2},
        {"name": "outro.long", "bars": 4},
    ]


def test_figure_apply_requires_a_studio_session(client: TestClient) -> None:
    response = client.post(
        "/v1/studio/figure/promote", json={**_body(), "apply": True}
    )
    assert response.status_code == 403


def test_validate_rejects_literal_midi(client: TestClient) -> None:
    payload = _body()
    payload["figures"][0]["spec"]["authored"]["events"][0]["pitch"] = {
        "kind": "literal_midi",
        "value": 60,
    }
    response = client.post("/v1/studio/figure/validate", json=payload)
    body = response.json()
    assert body["ok"] is False
    assert any("literal_midi is preview-only" in error["message"] for error in body["errors"])


def test_apply_twice_is_an_upsert_not_a_door_collision(client: TestClient) -> None:
    headers = {"X-Studio-Session": "test-owner"}
    first = client.post(
        "/v1/studio/figure/promote",
        json={**_body(), "apply": True},
        headers=headers,
    )
    second = client.post(
        "/v1/studio/figure/promote",
        json={**_body(), "apply": True},
        headers=headers,
    )
    assert first.json()["ok"] is True
    assert second.json()["ok"] is True
    assert (PATTERN, METER) in TEXTURE_CELLS


def test_unpromote_removes_the_latest_explicit_promotion(client: TestClient) -> None:
    headers = {"X-Studio-Session": "test-owner"}
    promoted = client.post(
        "/v1/studio/figure/promote",
        json={**_body(), "apply": True},
        headers=headers,
    )
    assert promoted.json()["ok"] is True

    removed = client.post(
        "/v1/studio/figure/unpromote",
        json=_body(),
        headers=headers,
    )
    body = removed.json()
    assert body["ok"] is True
    assert body["removed"] is True
    assert (PATTERN, METER) not in TEXTURE_CELLS
    assert ("villa", PATTERN) not in STUDIO_DOORS
