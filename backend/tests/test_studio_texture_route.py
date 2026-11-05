"""Focused tests for ``POST /v1/studio/texture/validate``.

The route is the seam between the Gemini draft panel and
``app.studio.texture_spec``. It must return path-shaped contract errors and must
never render, register, resolve pitch, or publish.
"""

from __future__ import annotations

import copy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_texture


def _spec() -> dict:
    return {
        "id": "gemini_draft",
        "composer": "unknown",
        "kind": "pattern",
        "level": "texture",
        "runtime": "code",
        "status": "draft",
        "meter_variants": [
            {
                "meter": {
                    "id": "3/4",
                    "beats": 3,
                    "beat_type": 4,
                    "eighths_per_bar": 6,
                    "strong_eighths": [0],
                    "subbar_breaks": [4],
                    "extra_weights": [[4, 0.8]],
                },
                "materializer": "grid",
                "transform": "none",
                "unsupported": False,
                "reason": None,
                "sentences": [],
            }
        ],
        "authored": {
            "events": [
                {
                    "bar": 0,
                    "beat": 0.0,
                    "duration_beats": 1.5,
                    "voice": 1,
                    "pitch": {"kind": "literal_midi", "value": 64},
                    "confidence": 0.91,
                    "review": "pending",
                }
            ]
        },
    }


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_texture.router)
    return TestClient(app)


def test_valid_texture_spec_is_ok(client: TestClient) -> None:
    response = client.post("/v1/studio/texture/validate", json={"spec": _spec()})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "errors": []}


def test_validation_errors_carry_authored_paths(client: TestClient) -> None:
    spec = _spec()
    spec["status"] = "shipped"
    response = client.post("/v1/studio/texture/validate", json={"spec": spec})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["errors"] == [{"path": "status", "message": "unknown value 'shipped'"}]


def test_event_metadata_errors_keep_the_event_index(client: TestClient) -> None:
    spec = copy.deepcopy(_spec())
    spec["authored"]["events"][0]["review"] = "maybe"
    response = client.post("/v1/studio/texture/validate", json={"spec": spec})
    body = response.json()
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "authored.events[0].review"
    assert "unknown value 'maybe'" in body["errors"][0]["message"]


def test_structural_errors_name_the_meter_path(client: TestClient) -> None:
    spec = _spec()
    del spec["meter_variants"][0]["meter"]["beats"]
    response = client.post("/v1/studio/texture/validate", json={"spec": spec})
    body = response.json()
    assert body["ok"] is False
    assert body["errors"] == [
        {
            "path": "spec.meter_variants[0].meter",
            "message": "missing field(s) ['beats']",
        }
    ]


def test_unknown_top_level_field_is_rejected(client: TestClient) -> None:
    spec = _spec()
    spec["rhythm"] = {"swing": True}
    response = client.post("/v1/studio/texture/validate", json={"spec": spec})
    body = response.json()
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "spec"
    assert "rhythm" in body["errors"][0]["message"]


def test_request_needs_a_spec_object(client: TestClient) -> None:
    response = client.post("/v1/studio/texture/validate", json={"spec": []})
    assert response.status_code == 422
