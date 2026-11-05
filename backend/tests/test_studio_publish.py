"""Studio publish MVP: versioned persistence of authored sentence specs.

Publishing stores the JSON in SQLite and assigns a monotonic version per
`(pattern, meter)`. It must never touch the global `SENTENCE_SPECS` registry:
the Phase 0/1 runtime still reads the code specs.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.sonify.guitar_sor  # noqa: F401  (registers the galop cycle)
import app.sonify.guitar_torroba  # noqa: F401  (registers the Torroba rows)
from app.routers import studio_publish as studio_publish_router
from app.sonify import sentence_specs as specs
from app.sonify.guitar_torroba import CASTILLO_34_WALK, SONATINA_SPECS
from app.studio.sentence_spec import spec_to_mapping

PUBLISH = "/v1/studio/sentence/publish"
SPECS = "/v1/studio/sentence/specs"


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    from app.store import db as store

    if store._db is not None:  # pragma: no cover - defensive cleanup
        asyncio.run(store.close_db())

    monkeypatch.setenv("VSTOCK_DB_PATH", str(tmp_path / "studio.db"))
    app = FastAPI()
    app.include_router(studio_publish_router.router)
    with TestClient(app) as test_client:
        try:
            yield test_client
        finally:
            # Close inside the TestClient loop: aiosqlite connections are bound
            # to the loop that opened them.
            test_client.portal.call(store.close_db)


def _publish(client: TestClient, mapping: dict) -> dict:
    response = client.post(PUBLISH, json=mapping)
    assert response.status_code == 200, response.text
    return response.json()


def test_publish_persists_and_round_trips(client: TestClient) -> None:
    before = dict(specs.SENTENCE_SPECS)
    body = spec_to_mapping(CASTILLO_34_WALK)

    data = _publish(client, body)
    assert data["ok"] is True
    assert data["pattern"] == "castillo"
    assert data["meter"] == "3/4"
    assert data["version"] == 1
    assert set(data) == {"ok", "id", "pattern", "meter", "version"}

    listed = client.get(SPECS).json()
    assert listed["ok"] is True
    assert [item["id"] for item in listed["specs"]] == [data["id"]]
    assert listed["specs"][0]["version"] == 1
    assert "payload" not in listed["specs"][0]

    detail = client.get(f"{SPECS}/{data['id']}")
    assert detail.status_code == 200
    assert detail.json()["payload"] == body

    # Publishing is storage-only: the runtime registry is untouched.
    assert specs.SENTENCE_SPECS == before
    assert CASTILLO_34_WALK in specs.SENTENCE_SPECS[("castillo", "3/4")]


def test_versions_increment_per_pattern_and_meter(client: TestClient) -> None:
    body = spec_to_mapping(CASTILLO_34_WALK)
    assert _publish(client, body)["version"] == 1
    assert _publish(client, body)["version"] == 2

    # A different key starts its own sequence.
    other = _publish(client, spec_to_mapping(SONATINA_SPECS[0]))
    assert (other["pattern"], other["meter"], other["version"]) == (
        SONATINA_SPECS[0].pattern,
        SONATINA_SPECS[0].meter,
        1,
    )


def test_list_filters_and_order(client: TestClient) -> None:
    _publish(client, spec_to_mapping(CASTILLO_34_WALK))
    _publish(client, spec_to_mapping(CASTILLO_34_WALK))
    _publish(client, spec_to_mapping(SONATINA_SPECS[0]))

    all_specs = client.get(SPECS).json()["specs"]
    assert len(all_specs) == 3

    castillo = client.get(SPECS, params={"pattern": "castillo"}).json()["specs"]
    assert [item["version"] for item in castillo] == [2, 1]

    sonatina = client.get(SPECS, params={"meter": SONATINA_SPECS[0].meter}).json()["specs"]
    assert [item["pattern"] for item in sonatina] == ["sonatina"]

    limited = client.get(SPECS, params={"limit": 1}).json()["specs"]
    assert len(limited) == 1


def test_publish_rejects_a_bad_realizer_without_storing(client: TestClient) -> None:
    body = spec_to_mapping(
        replace(
            CASTILLO_34_WALK,
            slots=(replace(CASTILLO_34_WALK.slots[0], figure=999),),
        )
    )
    response = client.post(PUBLISH, json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["errors"][0]["path"] == "slots[0].figure"
    assert client.get(SPECS).json()["specs"] == []


def test_invalid_payload_is_rejected(client: TestClient) -> None:
    body = spec_to_mapping(CASTILLO_34_WALK)
    del body["pattern"]

    response = client.post(PUBLISH, json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert set(data) == {"ok", "errors"}
    assert data["errors"][0]["path"] == "spec"
    assert "pattern" in data["errors"][0]["message"]

    bad_select = spec_to_mapping(CASTILLO_34_WALK)
    bad_select["select"]["n_parity"] = "maybe"
    errors = client.post(PUBLISH, json=bad_select).json()["errors"]
    assert errors[0]["path"] == "spec.select.n_parity"

    # Nothing was persisted.
    assert client.get(SPECS).json()["specs"] == []


def test_versions_persist_across_a_new_store_session(client: TestClient) -> None:
    from app.store import db as store

    first = _publish(client, spec_to_mapping(CASTILLO_34_WALK))
    assert first["version"] == 1

    # Simulate a new connection/session against the same SQLite file.
    client.portal.call(store.close_db)
    assert store._db is None

    second = _publish(client, spec_to_mapping(CASTILLO_34_WALK))
    assert second["version"] == 2

    listed = client.get(SPECS).json()["specs"]
    assert sorted(item["version"] for item in listed) == [1, 2]
    assert client.get(f"{SPECS}/{first['id']}").json()["payload"] == spec_to_mapping(
        CASTILLO_34_WALK
    )


def test_get_unknown_spec_returns_404(client: TestClient) -> None:
    assert client.get(f"{SPECS}/missing").status_code == 404
