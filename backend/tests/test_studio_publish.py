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


def test_publish_accepts_a_candidate_spec(client: TestClient) -> None:
    from app.studio.candidates import villa_candidate_spec

    data = _publish(client, spec_to_mapping(villa_candidate_spec()))
    assert data["ok"] is True
    assert data["pattern"] == "villa_pattern"


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


# --- rollback = republish an old payload as a new version -------------------


def _rollback(client: TestClient, spec_id: str) -> dict:
    response = client.post(f"{SPECS}/{spec_id}/rollback")
    assert response.status_code == 200, response.text
    return response.json()


def _insert_raw_spec(
    client: TestClient,
    *,
    spec_id: str,
    pattern: str,
    meter: str,
    version: int,
    payload: str,
) -> None:
    """Write a legacy row directly, bypassing publish validation."""
    from app.store import db as store

    async def insert() -> None:
        db = await store.get_db()
        await db.execute(
            """
            INSERT INTO studio_sentence_specs
                (id, pattern, meter, version, payload, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'published', '2026-01-01T00:00:00+00:00')
            """,
            (spec_id, pattern, meter, version, payload),
        )
        await db.commit()

    client.portal.call(insert)


def test_rollback_republishes_the_old_payload_as_a_new_version(
    client: TestClient,
) -> None:
    v1 = _publish(client, spec_to_mapping(CASTILLO_34_WALK))
    v2_body = spec_to_mapping(replace(CASTILLO_34_WALK, id="castillo_34_walk_v2"))
    v2 = _publish(client, v2_body)
    assert (v1["version"], v2["version"]) == (1, 2)

    before_v1 = client.get(f"{SPECS}/{v1['id']}").json()
    before_v2 = client.get(f"{SPECS}/{v2['id']}").json()

    rolled = _rollback(client, v1["id"])
    assert set(rolled) == {"ok", "id", "pattern", "meter", "version", "rollbackOf"}
    assert rolled["ok"] is True
    assert (rolled["pattern"], rolled["meter"]) == ("castillo", "3/4")
    assert rolled["version"] == 3
    assert rolled["rollbackOf"] == v1["id"]
    assert rolled["id"] not in {v1["id"], v2["id"]}

    # The new row carries v1's payload; the old rows are byte-for-byte intact.
    new_detail = client.get(f"{SPECS}/{rolled['id']}").json()
    assert new_detail["payload"] == spec_to_mapping(CASTILLO_34_WALK)
    assert client.get(f"{SPECS}/{v1['id']}").json() == before_v1
    assert client.get(f"{SPECS}/{v2['id']}").json() == before_v2

    # Lineage shows up in list (newest first) and in the detail summary.
    listed = client.get(SPECS, params={"pattern": "castillo"}).json()["specs"]
    assert [item["version"] for item in listed] == [3, 2, 1]
    assert listed[0]["rollbackOf"] == v1["id"]
    assert listed[1]["rollbackOf"] is None
    assert listed[2]["rollbackOf"] is None
    assert new_detail["rollbackOf"] == v1["id"]


def test_rollback_advances_the_sequence_for_its_own_key(client: TestClient) -> None:
    v1 = _publish(client, spec_to_mapping(CASTILLO_34_WALK))
    v2 = _publish(client, spec_to_mapping(CASTILLO_34_WALK))

    first = _rollback(client, v1["id"])
    second = _rollback(client, v2["id"])
    assert (first["version"], first["rollbackOf"]) == (3, v1["id"])
    assert (second["version"], second["rollbackOf"]) == (4, v2["id"])

    listed = client.get(SPECS).json()["specs"]
    assert [item["version"] for item in listed] == [4, 3, 2, 1]


def test_rollback_works_for_a_candidate_spec(client: TestClient) -> None:
    from app.studio.candidates import villa_candidate_spec

    body = spec_to_mapping(villa_candidate_spec())
    v1 = _publish(client, body)

    rolled = _rollback(client, v1["id"])
    assert rolled["ok"] is True
    assert rolled["pattern"] == "villa_pattern"
    assert rolled["version"] == 2
    assert rolled["rollbackOf"] == v1["id"]
    assert client.get(f"{SPECS}/{rolled['id']}").json()["payload"] == body


def test_rollback_of_unknown_spec_returns_404(client: TestClient) -> None:
    assert client.post(f"{SPECS}/missing/rollback").status_code == 404
    assert client.get(SPECS).json()["specs"] == []


def test_rollback_rejects_a_stored_payload_that_fails_family_validation(
    client: TestClient,
) -> None:
    import json

    bad_body = spec_to_mapping(CASTILLO_34_WALK)
    bad_body["pattern"] = "not_a_family"
    _insert_raw_spec(
        client,
        spec_id="legacy-unknown-family",
        pattern="not_a_family",
        meter="3/4",
        version=1,
        payload=json.dumps(bad_body, sort_keys=True),
    )

    data = _rollback(client, "legacy-unknown-family")
    assert data["ok"] is False
    assert data["errors"][0]["path"] == "pattern"
    assert "unknown pattern" in data["errors"][0]["message"]

    # Nothing was appended; the rejected source remains the only row.
    assert [item["id"] for item in client.get(SPECS).json()["specs"]] == [
        "legacy-unknown-family"
    ]


def test_rollback_rejects_an_unparseable_stored_payload(client: TestClient) -> None:
    _insert_raw_spec(
        client,
        spec_id="legacy-broken",
        pattern="castillo",
        meter="3/4",
        version=1,
        payload='{"pattern": "castillo"}',
    )

    data = _rollback(client, "legacy-broken")
    assert data["ok"] is False
    assert data["errors"][0]["path"] == "spec"
    assert [item["id"] for item in client.get(SPECS).json()["specs"]] == [
        "legacy-broken"
    ]


def test_init_db_adds_rollback_of_to_an_existing_table(tmp_path, monkeypatch) -> None:
    """The nullable lineage column migrates in place; old rows read as NULL."""
    import sqlite3

    from app.store import db as store

    if store._db is not None:  # pragma: no cover - defensive cleanup
        asyncio.run(store.close_db())

    legacy_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(legacy_path)
    connection.executescript(
        """
        CREATE TABLE studio_sentence_specs (
            id TEXT PRIMARY KEY,
            pattern TEXT NOT NULL,
            meter TEXT NOT NULL,
            version INTEGER NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'published',
            created_at TEXT NOT NULL,
            UNIQUE(pattern, meter, version)
        );
        INSERT INTO studio_sentence_specs
            (id, pattern, meter, version, payload, status, created_at)
        VALUES ('old-row', 'castillo', '3/4', 1, '{}', 'published', '2025-01-01');
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setenv("VSTOCK_DB_PATH", str(legacy_path))

    async def migrate():
        await store.init_db()
        db = await store.get_db()
        cursor = await db.execute("PRAGMA table_info(studio_sentence_specs)")
        columns = {row[1] for row in await cursor.fetchall()}
        cursor = await db.execute(
            "SELECT rollback_of FROM studio_sentence_specs WHERE id = 'old-row'"
        )
        row = await cursor.fetchone()
        await store.close_db()
        return columns, row

    columns, row = asyncio.run(migrate())
    assert "rollback_of" in columns
    assert row["rollback_of"] is None
