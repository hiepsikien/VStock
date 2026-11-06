"""Studio compiler/export seam: one deterministic bundle per sentence spec.

Phase 0/1 has no runtime interpreter and no repo writes from the server. The
artifact is a bundle: the authored JSON, the resolved preview fixture, the
rendered golden, and a registration checklist. These tests pin:

* every committed example compiles, and its `renderHash` is the preview's;
* invalid specs and fixtures are rejected with errors and no bundle;
* publishing a candidate and exporting it by id is the same bundle;
* `alreadyRegistered` only reports real registry membership, and compiling
  never changes `SENTENCE_SPECS`;
* `export_bundle` writes exactly the four documented files, deterministically.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.sonify.guitar_sor  # noqa: F401  (registers the galop cycle)
import app.sonify.guitar_torroba  # noqa: F401  (registers the Torroba rows)
from app.routers import studio_export as studio_export_router
from app.routers import studio_publish as studio_publish_router
from app.sonify import sentence_specs as specs
from app.sonify.guitar_barrios_period import (
    BARRIOS_CATHEDRAL_PERIOD_ID,
    barrios_period_enabled,
)
from app.sonify.guitar_sor import GALOP_CELL_1, GALOP_CELL_2
from app.sonify.guitar_torroba import CASTILLO_34_WALK, _FIGURES
from app.sonify.sentence_specs import SentenceSpec
from app.studio import compiler, dispatch, examples
from app.studio.candidates import CANDIDATES_DIR, load_candidate, villa_candidate_spec
from app.studio.export import PILOT_PATTERNS
from app.studio.preview import Error
from app.studio.sentence_spec import parse_spec, spec_to_mapping

BUNDLE_KEYS = {"schemaVersion", "spec", "fixture", "rendered", "registration"}
RENDERED_KEYS = {"plan", "row", "notes", "renderHash", "matrix"}
REGISTRATION_KEYS = {
    "pattern",
    "meter",
    "id",
    "family",
    "ownerModule",
    "alreadyRegistered",
    "validFigures",
    "checklist",
}

EXPORT = "/v1/studio/sentence/export"
SPECS = "/v1/studio/sentence/specs"

EXAMPLES = examples.examples()
EXAMPLE_IDS = [f"{item.pattern}-{item.id}" for item in EXAMPLES]


def _spec(item: examples.Example) -> SentenceSpec:
    return parse_spec(item.payload)


# ---------------------------------------------------------------------------
# every committed example


@pytest.mark.parametrize("item", EXAMPLES, ids=EXAMPLE_IDS)
def test_every_committed_example_compiles(item: examples.Example) -> None:
    spec = _spec(item)
    bundle = compiler.compile_sentence(spec)

    assert set(bundle) == BUNDLE_KEYS
    assert bundle["schemaVersion"] == compiler.SCHEMA_VERSION
    assert bundle["spec"] == item.payload
    assert set(bundle["rendered"]) == RENDERED_KEYS
    assert set(bundle["registration"]) == REGISTRATION_KEYS

    # The bundle is a golden, not a second renderer: it must equal the preview.
    direct = dispatch.preview_sentence(spec)
    assert direct.ok is True
    assert bundle["rendered"]["renderHash"] == direct.render_hash
    assert bundle["rendered"]["plan"] == direct.plan
    assert bundle["rendered"]["row"] == direct.row
    assert bundle["rendered"]["notes"] == list(direct.notes)
    assert bundle["rendered"]["matrix"] == list(direct.matrix)

    # The fixture is resolved and self-contained: feeding it back reproduces
    # the same render hash.
    fixture = bundle["fixture"]
    assert fixture["pattern"] == spec.pattern
    assert fixture["meter"] in {"3/4", "4/4", "6/8"}
    assert set(fixture["matrix"]) == {"lengths", "n", "closes", "rise"}
    assert compiler.compile_sentence(spec, fixture) == bundle

    registration = bundle["registration"]
    assert registration["pattern"] == spec.pattern
    assert registration["meter"] == spec.meter
    assert registration["id"] == spec.id
    assert registration["family"] == dispatch.family_for(spec.pattern)
    assert registration["checklist"]
    assert any(line.startswith("renderer: ") for line in registration["checklist"])
    assert any(line.startswith("registry: ") for line in registration["checklist"])
    assert any(line.startswith("figures: ") for line in registration["checklist"])
    assert any(line.startswith("sentence JSON: ") for line in registration["checklist"])
    assert any(line.startswith("tests: ") for line in registration["checklist"])


def test_galop_cycle_is_owned_by_sor_and_lists_cells() -> None:
    item = next(item for item in EXAMPLES if item.pattern == "galop")
    registration = compiler.compile_sentence(_spec(item))["registration"]

    assert registration["family"] == dispatch.TORROBA_SOR
    assert registration["ownerModule"] == "backend/app/sonify/guitar_sor.py"
    assert registration["validFigures"] == sorted((GALOP_CELL_1, GALOP_CELL_2))
    assert any("cell realizers" in line for line in registration["checklist"])


def test_torroba_registration_lists_the_figure_registry() -> None:
    item = next(item for item in EXAMPLES if item.pattern == "castillo")
    registration = compiler.compile_sentence(_spec(item))["registration"]
    assert registration["ownerModule"] == "backend/app/sonify/guitar_torroba.py"
    assert registration["validFigures"] == sorted(_FIGURES)


# ---------------------------------------------------------------------------
# alreadyRegistered / registry immutability


def test_already_registered_tracks_registry_membership_only() -> None:
    for item in EXAMPLES:
        registration = compiler.compile_sentence(_spec(item))["registration"]
        expected = item.pattern in PILOT_PATTERNS
        if item.id == BARRIOS_CATHEDRAL_PERIOD_ID and barrios_period_enabled():
            # The Barrios period is registered only when its flag is on.
            expected = True
        assert registration["alreadyRegistered"] is expected, item.id


def test_candidates_are_not_registered_and_say_so() -> None:
    candidate_specs = [
        villa_candidate_spec(),
        load_candidate(CANDIDATES_DIR / "brouwer_aba.json")[0],
        load_candidate(CANDIDATES_DIR / "barrios_cathedral.json")[0],
    ]
    for spec in candidate_specs:
        if spec.id == BARRIOS_CATHEDRAL_PERIOD_ID and barrios_period_enabled():
            continue  # the flag registers this exact period in production
        bundle = compiler.compile_sentence(spec)
        registration = bundle["registration"]
        assert registration["alreadyRegistered"] is False
        assert any(
            line.startswith("still preview-only: ")
            for line in registration["checklist"]
        )


def test_compile_and_export_leave_the_registry_untouched(tmp_path: Path) -> None:
    before = dict(specs.SENTENCE_SPECS)

    for item in EXAMPLES:
        compiler.compile_sentence(_spec(item))
    compiler.export_bundle(CASTILLO_34_WALK, None, tmp_path / "bundle")

    assert specs.SENTENCE_SPECS == before
    assert specs.SENTENCE_SPECS[("castillo", "3/4")] == before[("castillo", "3/4")]


# ---------------------------------------------------------------------------
# errors


def _errors(
    spec: SentenceSpec, fixture: dict | None = None
) -> tuple[Error, ...]:
    with pytest.raises(compiler.CompileError) as caught:
        compiler.compile_bundle(spec, fixture)
    return caught.value.errors


def test_invalid_spec_has_errors_and_no_bundle() -> None:
    from dataclasses import replace

    spec = replace(CASTILLO_34_WALK, slots=(replace(CASTILLO_34_WALK.slots[0], figure=999),))
    errors = _errors(spec)

    assert errors[0].path == "slots[0].figure"


@pytest.mark.parametrize(
    "fixture",
    [
        {"length": 0},
        {"length": 3, "bpm": 0},
        {"pattern": "sonatina"},
        {"unknown": 1},
    ],
)
def test_invalid_fixture_has_errors_and_no_bundle(fixture: dict) -> None:
    errors = _errors(CASTILLO_34_WALK, fixture)
    assert errors[0].path == "fixture"


def test_unknown_pattern_is_rejected() -> None:
    from dataclasses import replace

    errors = _errors(replace(CASTILLO_34_WALK, pattern="not_a_family"))
    assert errors[0].path == "pattern"


def test_procedure_candidate_has_no_compiler_path_yet() -> None:
    """Bach's exposition is a procedure slot; the generic compiler cannot render it."""
    bach = load_candidate(CANDIDATES_DIR / "bach_exposition.json")[0]
    errors = _errors(bach)
    assert errors[0].path == "pattern"


def test_compile_bundle_matches_compile_sentence() -> None:
    assert compiler.compile_bundle(CASTILLO_34_WALK) == compiler.compile_sentence(
        CASTILLO_34_WALK
    )


def test_export_bundle_refuses_an_invalid_spec(tmp_path: Path) -> None:
    from dataclasses import replace

    target = tmp_path / "never"
    with pytest.raises(compiler.CompileError):
        compiler.export_bundle(
            replace(CASTILLO_34_WALK, meter="12/8"), None, target
        )
    assert not target.exists()


# ---------------------------------------------------------------------------
# export_bundle files


def test_export_bundle_writes_the_four_files_deterministically(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    written = compiler.export_bundle(CASTILLO_34_WALK, None, first)
    assert [path.name for path in written] == list(compiler.BUNDLE_FILES)
    assert sorted(path.name for path in first.iterdir()) == sorted(compiler.BUNDLE_FILES)

    compiler.export_bundle(CASTILLO_34_WALK, None, second)
    for name in compiler.BUNDLE_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    # A third write overwrites the same bytes and touches nothing else.
    sentinel = first / "keep.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")
    compiler.export_bundle(CASTILLO_34_WALK, None, first)
    assert sentinel.read_text(encoding="utf-8") == "untouched\n"
    assert sorted(path.name for path in first.iterdir()) == sorted(
        (*compiler.BUNDLE_FILES, "keep.txt")
    )
    for name in compiler.BUNDLE_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_bundle_files_carry_no_paths_or_timestamps(tmp_path: Path) -> None:
    target = tmp_path / "bundle"
    compiler.export_bundle(CASTILLO_34_WALK, None, target)

    texts = {
        name: (target / name).read_text(encoding="utf-8")
        for name in compiler.BUNDLE_FILES
    }
    for name, text in texts.items():
        assert str(tmp_path) not in text, name
        assert "/Users/" not in text, name
        assert str(Path.cwd()) not in text, name
        assert re.search(r"\b\d{4}-\d{2}-\d{2}[T ]", text) is None, name

    rendered = json.loads(texts["rendered.json"])
    assert set(rendered) == RENDERED_KEYS
    assert rendered["renderHash"].startswith("sha256:")

    registration = texts["registration.md"]
    assert registration.startswith("# Registration: castillo_34_walk\n")
    assert "- registered: yes" in registration
    assert "- [ ] renderer: backend/app/sonify/guitar_torroba.py" in registration
    assert "- [ ] sentence JSON: backend/app/studio/specs/castillo-3-4.json" in registration
    assert "backend/tests/test_studio_export.py" in registration


def test_candidate_registration_md_says_preview_only(tmp_path: Path) -> None:
    target = tmp_path / "candidate"
    compiler.export_bundle(villa_candidate_spec(), None, target)

    registration = (target / "registration.md").read_text(encoding="utf-8")
    assert "- registered: no" in registration
    assert "- [ ] still preview-only: " in registration
    assert (
        "- [ ] sentence JSON: backend/app/studio/candidates/villa_arpeggio.json"
        in registration
    )


# ---------------------------------------------------------------------------
# endpoints


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    from app.store import db as store

    if store._db is not None:  # pragma: no cover - defensive cleanup
        asyncio.run(store.close_db())

    monkeypatch.setenv("VSTOCK_DB_PATH", str(tmp_path / "studio.db"))
    app = FastAPI()
    app.include_router(studio_publish_router.router)
    app.include_router(studio_export_router.router)
    with TestClient(app) as test_client:
        try:
            yield test_client
        finally:
            test_client.portal.call(store.close_db)


def _post_export(client: TestClient, body: dict) -> dict:
    response = client.post(EXPORT, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_export_endpoint_returns_ok_and_bundle(client: TestClient) -> None:
    payload = spec_to_mapping(CASTILLO_34_WALK)
    body = _post_export(client, {"spec": payload})

    assert set(body) == {"ok", "bundle"}
    assert body["ok"] is True
    bundle = body["bundle"]
    assert set(bundle) == BUNDLE_KEYS
    assert bundle["rendered"]["renderHash"] == compiler.compile_sentence(
        CASTILLO_34_WALK
    )["rendered"]["renderHash"]


def test_export_endpoint_accepts_a_fixture(client: TestClient) -> None:
    body = _post_export(
        client,
        {"spec": spec_to_mapping(CASTILLO_34_WALK), "fixture": {"bars": 2}},
    )
    assert body["ok"] is True
    assert body["bundle"]["fixture"]["bars"] == 2


def test_export_endpoint_rejects_parse_and_family_errors(client: TestClient) -> None:
    broken = spec_to_mapping(CASTILLO_34_WALK)
    del broken["pattern"]
    body = _post_export(client, {"spec": broken})
    assert set(body) == {"ok", "errors"}
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "spec"

    from dataclasses import replace

    bad_figure = spec_to_mapping(
        replace(CASTILLO_34_WALK, slots=(replace(CASTILLO_34_WALK.slots[0], figure=999),))
    )
    body = _post_export(client, {"spec": bad_figure})
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "slots[0].figure"

    body = _post_export(
        client, {"spec": spec_to_mapping(CASTILLO_34_WALK), "fixture": {"length": 0}}
    )
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "fixture"


def _publish(client: TestClient, mapping: dict) -> dict:
    response = client.post("/v1/studio/sentence/publish", json=mapping)
    assert response.status_code == 200, response.text
    return response.json()


def test_export_published_candidate_by_id(client: TestClient) -> None:
    spec = villa_candidate_spec()
    published = _publish(client, spec_to_mapping(spec))
    assert published["ok"] is True

    response = client.post(f"{SPECS}/{published['id']}/export")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"ok", "bundle"}
    assert body["ok"] is True

    bundle = body["bundle"]
    assert bundle["spec"] == spec_to_mapping(spec)
    assert bundle["rendered"]["renderHash"] == dispatch.preview_sentence(spec).render_hash
    assert bundle["registration"]["alreadyRegistered"] is False


def test_export_unknown_published_spec_returns_404(client: TestClient) -> None:
    assert client.post(f"{SPECS}/missing/export").status_code == 404


def test_export_published_spec_is_scoped_to_the_session(client: TestClient) -> None:
    publish_url = "/v1/studio/sentence/publish"
    body = spec_to_mapping(CASTILLO_34_WALK)
    owner = {"X-Studio-Session": "session-a"}
    stranger = {"X-Studio-Session": "session-b"}

    private = client.post(publish_url, json=body, headers=owner).json()
    assert private["ok"] is True
    assert (
        client.post(f"{SPECS}/{private['id']}/export", headers=owner).status_code
        == 200
    )
    assert (
        client.post(f"{SPECS}/{private['id']}/export", headers=stranger).status_code
        == 404
    )

    public = client.post(
        publish_url, json=body, headers=owner, params={"visibility": "public"}
    ).json()
    assert public["visibility"] == "public"
    assert (
        client.post(f"{SPECS}/{public['id']}/export", headers=stranger).status_code
        == 200
    )


def test_export_published_row_that_fails_family_validation(client: TestClient) -> None:
    bad = spec_to_mapping(CASTILLO_34_WALK)
    bad["pattern"] = "not_a_family"
    _insert_raw_spec(
        client,
        spec_id="legacy-unknown-family",
        pattern="not_a_family",
        meter="3/4",
        payload=json.dumps(bad, sort_keys=True),
    )

    response = client.post(f"{SPECS}/legacy-unknown-family/export")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"ok", "errors"}
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "pattern"


def _insert_raw_spec(
    client: TestClient,
    *,
    spec_id: str,
    pattern: str,
    meter: str,
    payload: str,
) -> None:
    from app.store import db as store

    async def insert() -> None:
        db = await store.get_db()
        await db.execute(
            """
            INSERT INTO studio_sentence_specs
                (id, pattern, meter, version, payload, status, created_at)
            VALUES (?, ?, ?, 1, ?, 'published', '2026-01-01T00:00:00+00:00')
            """,
            (spec_id, pattern, meter, payload),
        )
        await db.commit()

    client.portal.call(insert)
