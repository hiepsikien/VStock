"""End-to-end Studio stabilization suite (no production behaviour changes).

This module wires every Studio router into one ``TestClient`` with a temporary
SQLite database and temporary Studio/audio roots. It is deliberately *not* the
full ``app.main`` app: that lifespan warms the market-data caches and would
touch the network. A module-level socket guard makes the "no network" promise
explicit; Gemini is exercised through the existing ``vision._call_gemini``
seam with a fake response.

Covered journeys
----------------
1. Committed example spec -> ``/sentence/validate`` -> ``/sentence/preview``.
   One case per owning family: Torroba (``castillo``), Villa
   (``villa_pattern``), Barrios (``preludio``), Brouwer (``brouwer_etude``).
2. ``/sentence/audio`` synthesizes a real WAV from the preview (no MuseScore),
   plus the cached ``renderHash`` lookup and the signed/WAV download.
3. ``/sentence/publish`` -> versions -> ``/rollback`` -> list/get, including
   that a rollback appends a new row instead of mutating the old one.
4. Upload a tiny PNG -> mocked Gemini ``/analyze`` -> pending draft; signed
   media URL works without a session header; another session cannot read the
   blob or analyze the upload.
5. ``/v1/studio/jobs`` submit/poll for a preview; job ids are owner-scoped.
6. Private/public owner visibility: session A cannot read session B's private
   spec; a public row is readable but still not rollback-able by B.

Local-run checklist (reported in the hand-off, kept here so it travels with
the suite)
--------------------------------------------------------------------------
Prerequisites
  [ ] ``cd backend``
  [ ] ``python -m pytest --version`` works and backend requirements are installed
  [ ] No ``GEMINI_API_KEY`` needed: this suite fakes the one Gemini seam
  [ ] No MuseScore, no ffmpeg, no Docker, no network needed
  [ ] ``git status`` is clean except the files under review
  [ ] Never merge ``main``; this branch is local integration only (docs §13.11)

Focused run
  [ ] ``python -m pytest tests/test_studio_e2e.py -q``
  [ ] Re-run with ``-x`` and read the first failure instead of rerunning blindly
  [ ] Confirm the temporary DB/studio/audio dirs disappear after the run

Studio-adjacent regression run
  [ ] ``python -m pytest tests/test_studio_*.py -q``
  [ ] ``python -m pytest tests/test_studio_candidate_api.py tests/test_studio_publish.py tests/test_studio_jobs.py tests/test_studio_audio.py tests/test_studio_vision.py -q``

Full backend gate
  [ ] ``python -m pytest -q`` from ``backend``
  [ ] Keep the full log; do not summarise a failure as "flaky" without a rerun

Frontend gate (only if Node deps are installed)
  [ ] ``npm run test:studio`` from the repository root
  [ ] ``npm run test:unit`` when the suite is meant to be the full gate
  [ ] ``npm run web`` boots and the Studio pill/room opens (manual smoke)

Expected invariants
  [ ] No external network requests; the socket guard fails a test immediately
  [ ] No writes outside pytest's temporary directory
  [ ] No change to ``SENTENCE_SPECS`` or other production registries
  [ ] Published specs stay in SQLite; the runtime still reads code specs
  [ ] Job queue remains process-local and owner-scoped

Hand-off report
  [ ] Record exact pytest counts (passed/failed/skipped)
  [ ] Quote any real bug plus the smallest production fix, if one was required
  [ ] Propose doc updates separately; do not edit ``docs/`` in this branch
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
import socket
import struct
import time
import wave
import zlib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Register the production Torroba/Sor rows before previewing a castillo example.
import app.sonify.guitar_sor  # noqa: F401
import app.sonify.guitar_torroba  # noqa: F401
from app.sonify import sentence_specs as runtime_specs
from app.routers import (
    studio,
    studio_audio,
    studio_jobs,
    studio_publish,
    studio_vision,
)
from app.services import gemini_companion
from app.store import db as store
from app.studio import audio as studio_audio_module
from app.studio import jobs as studio_jobs_module
from app.studio import session as studio_session
from app.studio import vision

VALIDATE = "/v1/studio/sentence/validate"
PREVIEW = "/v1/studio/sentence/preview"
AUDIO = "/v1/studio/sentence/audio"
EXAMPLES = "/v1/studio/sentence/examples"
PUBLISH = "/v1/studio/sentence/publish"
SPECS = "/v1/studio/sentence/specs"
JOBS = "/v1/studio/jobs"
VISION = "/v1/musicalize/studio"

SESSION_A = {"X-Studio-Session": "e2e-alpha-session"}
SESSION_B = {"X-Studio-Session": "e2e-beta-session"}

EXAMPLE_IDS = {
    "torroba": "castillo_34_walk",
    "villa": "villa_arpeggio_aba",
    "barrios": "barrios_cathedral_period",
    "brouwer": "brouwer_etude_noviembre_aba",
}
PREVIEW_SHAPE = {"ok", "errors", "plan", "row", "notes", "renderHash", "matrix"}


# ---------------------------------------------------------------------------
# fixtures


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any code path tries to open an external connection."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("Studio E2E must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    root = tmp_path_factory.mktemp("studio-e2e")

    if store._db is not None:  # pragma: no cover - defensive cleanup
        asyncio.run(store.close_db())

    registry = studio_jobs_module.JobRegistry()

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("VSTOCK_DB_PATH", str(root / "studio.db"))
        patch.setenv("VSTOCK_STUDIO_DIR", str(root / "studio"))
        patch.setenv("VSTOCK_STUDIO_AUDIO_DIR", str(root / "audio"))
        patch.setenv("VSTOCK_STUDIO_SECRET", "studio-e2e-secret")
        # Configured path, but every actual call goes through the fake seam.
        patch.setenv("GEMINI_API_KEY", "studio-e2e-dummy-key")
        for name in (
            "GOOGLE_API_KEY",
            "GOOGLE_GENAI_API_KEY",
            "GCP_PROJECT",
            "GOOGLE_CLOUD_PROJECT",
            "GEMINI_MODEL",
            "VSTOCK_STUDIO_ENABLED",
            "VSTOCK_STUDIO_UPLOADS_PER_DAY",
            "VSTOCK_STUDIO_ANALYSES_PER_DAY",
            "VSTOCK_STUDIO_SPECS_PER_DAY",
            "VSTOCK_STUDIO_MAX_IMAGE_MB",
        ):
            patch.delenv(name, raising=False)

        # Process-local queue: use a dedicated registry so this module cannot
        # delay or be delayed by another test module's jobs.
        patch.setattr(studio_jobs_module, "get_registry", lambda: registry)

        app = FastAPI()
        for router in (
            studio,
            studio_audio,
            studio_jobs,
            studio_publish,
            studio_vision,
        ):
            app.include_router(router.router)

        with TestClient(app) as test_client:
            try:
                yield test_client
            finally:
                # Close inside the TestClient loop: aiosqlite is loop-bound.
                test_client.portal.call(store.close_db)

    registry.shutdown(wait=True)
    shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# helpers


def _png(width: int = 4, height: int = 3, *, seed: int = 0) -> bytes:
    """A minimal valid RGB PNG; the Studio parser only needs the header."""
    rows = b"".join(
        b"\x00" + bytes([seed, 0, 0]) * width for _ in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", crc)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class _FakeFinish:
    def __init__(self, name: str = "STOP") -> None:
        self.name = name


class _FakeCandidate:
    def __init__(self, name: str = "STOP") -> None:
        self.finish_reason = _FakeFinish(name)


class _FakeGeminiResponse:
    """The smallest object ``vision._parse_response`` accepts."""

    def __init__(self, name: str = "STOP") -> None:
        self.parsed = {
            "measures": [{"index": 1, "meter": "3/4", "key": "A minor"}],
            "notes": [
                {
                    "measure": 1,
                    "beat": 0.0,
                    "duration_beats": 1.0,
                    "written_pitch": "E4",
                    "sounding_pitch": "E3",
                    "confidence": 0.91,
                }
            ],
            "warnings": [],
        }
        self.candidates = [_FakeCandidate(name)]
        self.prompt_feedback = None
        self.text = None


def _examples(client: TestClient) -> list[dict]:
    response = client.get(EXAMPLES)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True and not body.get("errors")
    return body["examples"]


def _example(client: TestClient, spec_id: str) -> dict:
    for example in _examples(client):
        if example["id"] == spec_id:
            return example
    raise AssertionError(f"committed example {spec_id!r} is missing")


def _validate(client: TestClient, payload: dict) -> dict:
    response = client.post(VALIDATE, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _preview(client: TestClient, payload: dict, fixture: dict | None = None) -> dict:
    response = client.post(PREVIEW, json={"spec": payload, "fixture": fixture or {}})
    assert response.status_code == 200, response.text
    return response.json()


def _publish(
    client: TestClient,
    payload: dict,
    *,
    session: dict,
    visibility: str | None = None,
) -> dict:
    params = {"visibility": visibility} if visibility is not None else None
    response = client.post(PUBLISH, json=payload, headers=session, params=params)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True, body
    return body


def _list(client: TestClient, *, session: dict, **params) -> list[dict]:
    response = client.get(SPECS, headers=session, params=params)
    assert response.status_code == 200, response.text
    return response.json()["specs"]


def _get(client: TestClient, spec_id: str, *, session: dict):
    return client.get(f"{SPECS}/{spec_id}", headers=session)


def _upload(client: TestClient, data: bytes, *, session: dict, name: str = "page.png"):
    return client.post(
        f"{VISION}/uploads",
        files={"file": (name, data, "image/png")},
        headers=session,
    )


def _wait_for_job(client: TestClient, job_id: str, *, session: dict, timeout: float = 10.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        response = client.get(f"{JOBS}/{job_id}", headers=session)
        last = response
        if response.status_code == 200:
            return response
        assert response.status_code == 409, response.text
        assert int(response.headers["Retry-After"]) >= 1
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish: {last and last.text}")


# ---------------------------------------------------------------------------
# journey 1: committed example -> validate -> preview, one case per family


@pytest.mark.parametrize(
    ("family", "expected_plan_kind"),
    [
        ("torroba", "figure"),
        ("villa", "figure"),
        ("barrios", "barrios_period"),
        ("brouwer", "figure"),
    ],
)
def test_example_validate_preview_per_family(
    client: TestClient, family: str, expected_plan_kind: str
) -> None:
    example = _example(client, EXAMPLE_IDS[family])
    payload = example["payload"]
    assert example["pattern"] == payload["pattern"]

    validated = _validate(client, payload)
    assert validated == {"ok": True, "errors": []}

    preview = _preview(client, payload)
    assert set(preview) == PREVIEW_SHAPE
    assert preview["ok"] is True, preview["errors"]
    assert preview["errors"] == []
    assert preview["plan"] is not None
    assert preview["plan"]["kind"] == expected_plan_kind
    assert preview["row"]
    assert preview["notes"], "a successful preview must render note events"
    assert preview["renderHash"].startswith("sha256:")
    assert len(preview["renderHash"]) == 71  # "sha256:" + 64 hex chars
    assert isinstance(preview["matrix"], list)

    if family == "torroba":
        # The preview is a bounded slice of the real castillo render.
        assert set(preview["row"]) == {"castillo"}
    if family == "villa":
        assert "villa_arpeggio" in preview["row"]
        assert "villa_chord_melody" in preview["row"]
    if family == "barrios":
        assert [span["pattern"] for span in preview["plan"]["spans"]] == [
            "preludio",
            "tremolo",
            "preludio",
        ]


def test_meter_gate_rejects_a_spec_the_runtime_does_not_support(
    client: TestClient,
) -> None:
    """12/8 stays a known Phase 3 gap; Studio must reject it, not guess 4/4."""
    payload = dict(_example(client, EXAMPLE_IDS["torroba"])["payload"])
    payload["meter"] = "12/8"
    body = _validate(client, payload)
    assert body["ok"] is False
    assert body["errors"]
    assert all(error["path"] for error in body["errors"])


# ---------------------------------------------------------------------------
# journey 2: synthesized preview audio (WAV, no MuseScore)


def test_sentence_audio_synthesizes_and_serves_a_wav(client: TestClient) -> None:
    payload = _example(client, EXAMPLE_IDS["torroba"])["payload"]
    preview = _preview(client, payload, {"length": 9, "bars": 2})
    render_hash = preview["renderHash"]

    synthesized = client.post(AUDIO, json={"spec": payload, "fixture": {"length": 9, "bars": 2}})
    assert synthesized.status_code == 200, synthesized.text
    body = synthesized.json()
    assert body["ok"] is True, body["errors"]
    assert body["renderHash"] == render_hash
    assert body["durationSec"] > 0
    assert body["audioUrl"].startswith(f"{AUDIO}/")
    assert body["audioUrl"].endswith(".wav")

    download = client.get(body["audioUrl"])
    assert download.status_code == 200
    assert download.headers["content-type"] == "audio/wav"
    data = download.content
    assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"

    # The file really is a bounded mono PCM WAV, not a placeholder.
    path = studio_audio_module.audio_root() / Path(body["audioUrl"]).name
    assert path.is_file()
    with wave.open(str(path)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == studio_audio_module.SAMPLE_RATE
        measured = wav.getnframes() / wav.getframerate()
    assert measured == pytest.approx(body["durationSec"], abs=1e-6)
    assert 0.0 < body["durationSec"] <= studio_audio_module.MAX_AUDIO_SEC

    # A request that only knows the render hash reuses the cached WAV.
    cached = client.post(AUDIO, json={"renderHash": render_hash})
    assert cached.status_code == 200, cached.text
    assert cached.json()["ok"] is True
    assert cached.json()["audioUrl"] == body["audioUrl"]

    # The route only serves cache-shaped names.
    assert client.get(f"{AUDIO}/not-a-cache-key.wav").status_code == 404


# ---------------------------------------------------------------------------
# journey 3: publish -> version -> rollback -> list/get


def test_publish_rollback_list_and_get(client: TestClient) -> None:
    payload = _example(client, EXAMPLE_IDS["torroba"])["payload"]

    first = _publish(client, payload, session=SESSION_A)
    assert first["pattern"] == "castillo"
    assert first["meter"] == "3/4"
    assert first.get("visibility", "private") == "private"
    assert first["version"] >= 1

    second = _publish(client, payload, session=SESSION_A)
    assert second["version"] == first["version"] + 1
    assert second["id"] != first["id"]

    detail = _get(client, first["id"], session=SESSION_A)
    assert detail.status_code == 200
    assert detail.json()["payload"] == payload
    assert detail.json()["version"] == first["version"]

    listed = _list(client, session=SESSION_A, pattern="castillo", meter="3/4")
    ids = {item["id"] for item in listed}
    assert {first["id"], second["id"]} <= ids
    assert all("payload" not in item for item in listed)

    rolled = client.post(
        f"{SPECS}/{first['id']}/rollback", headers=SESSION_A
    )
    assert rolled.status_code == 200, rolled.text
    body = rolled.json()
    assert body["ok"] is True
    assert body["id"] not in {first["id"], second["id"]}
    assert body["version"] == second["version"] + 1
    assert body["rollbackOf"] == first["id"]
    assert body.get("visibility", "private") == "private"

    # Rollback is append-only: the source row is untouched.
    source = _get(client, first["id"], session=SESSION_A).json()
    assert source["payload"] == payload
    assert source["version"] == first["version"]
    copied = _get(client, body["id"], session=SESSION_A).json()
    assert copied["payload"] == payload

    after = _list(client, session=SESSION_A, pattern="castillo", meter="3/4")
    assert len(after) >= 3
    assert all(item["pattern"] == "castillo" for item in after)


# ---------------------------------------------------------------------------
# journey 4: upload -> mocked Gemini analyze -> draft -> signed media


def test_authoring_flows_leave_the_runtime_registry_untouched(
    client: TestClient,
) -> None:
    """Storage/preview stay Phase 0/1 seams: the runtime keeps reading code specs."""
    before = {
        key: tuple(items) for key, items in runtime_specs.SENTENCE_SPECS.items()
    }

    payload = _example(client, EXAMPLE_IDS["torroba"])["payload"]
    assert _validate(client, payload)["ok"] is True
    assert _preview(client, payload)["ok"] is True
    assert client.post(
        AUDIO, json={"spec": payload, "fixture": {}}
    ).json()["ok"] is True
    published = _publish(client, payload, session=SESSION_A)
    assert _get(client, published["id"], session=SESSION_A).status_code == 200

    after = {
        key: tuple(items) for key, items in runtime_specs.SENTENCE_SPECS.items()
    }
    assert after == before


def test_upload_analyze_draft_and_signed_media(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _png(width=7, height=5, seed=3)

    uploaded = _upload(client, data, session=SESSION_A)
    assert uploaded.status_code == 201, uploaded.text
    upload = uploaded.json()
    assert upload["ok"] is True
    assert upload["mime"] == "image/png"
    assert (upload["width"], upload["height"]) == (7, 5)
    assert upload["sha256"] == hashlib.sha256(data).hexdigest()
    assert upload["sizeBytes"] == len(data)
    assert upload["url"].startswith(f"{VISION}/uploads/{upload['id']}?t=")
    assert upload["token"] in upload["url"]
    assert 300 <= upload["tokenTtlSeconds"] <= 900

    # Signed media is readable without the session header (an <img> cannot send it).
    media = client.get(upload["url"])
    assert media.status_code == 200
    assert media.content == data
    assert media.headers["content-type"] == "image/png"

    # Another namespace cannot mint a valid token for this blob.
    owner_b = studio_session.owner_id_for("e2e-beta-session")
    foreign_token, _ = studio_session.sign_media_token(owner_b, upload["id"])
    foreign = client.get(f"{VISION}/uploads/{upload['id']}?t={foreign_token}")
    assert foreign.status_code == 403
    assert foreign.json()["detail"]["code"] == "invalid_token"

    # Uploads are owner-scoped too.
    assert client.delete(f"{VISION}/uploads/{upload['id']}", headers=SESSION_B).status_code == 404
    assert client.post(
        f"{VISION}/analyze", json={"uploadId": upload["id"]}, headers=SESSION_B
    ).status_code == 404

    calls: list[str] = []

    async def fake_gemini(data, mime, crop, metadata, *, model, client=None):
        calls.append(model)
        return _FakeGeminiResponse()

    monkeypatch.setattr(vision, "_call_gemini", fake_gemini)

    crop = {"x": 1, "y": 2, "w": 3, "h": 4}
    first = client.post(
        f"{VISION}/analyze",
        json={"uploadId": upload["id"], "crop": crop},
        headers=SESSION_A,
    )
    assert first.status_code == 200, first.text
    draft = first.json()
    assert draft["ok"] is True, draft.get("error")
    assert draft["cacheHit"] is False
    assert draft["uploadId"] == upload["id"]
    assert draft["draft"]["source"] == "gemini"
    assert draft["draft"]["review"] == "pending"
    assert draft["draft"]["notes"][0]["sounding_pitch"] == "E3"
    assert draft["quota"]["kind"] == "analyze"
    assert draft["quota"]["used"] == 1
    assert calls == [gemini_companion.DEFAULT_MODEL]

    # A cached draft is served without a second Gemini call or quota spend.
    second = client.post(
        f"{VISION}/analyze",
        json={"uploadId": upload["id"], "crop": crop},
        headers=SESSION_A,
    )
    assert second.status_code == 200, second.text
    assert second.json()["cacheHit"] is True
    # The router still spends one analyze quota unit on a configured call; the
    # cache only saves the Gemini request itself.
    assert second.json()["quota"]["used"] == 2
    assert len(calls) == 1

    # Deleting the upload removes the row and, at refcount zero, the blob.
    deleted = client.delete(f"{VISION}/uploads/{upload['id']}", headers=SESSION_A)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(upload["url"]).status_code == 404


# ---------------------------------------------------------------------------
# journey 5: job queue submit/poll for a preview, owner-scoped ids


def test_preview_job_submit_poll_and_owner_scope(client: TestClient) -> None:
    payload = _example(client, EXAMPLE_IDS["villa"])["payload"]

    submitted = client.post(
        JOBS,
        json={"kind": "preview", "spec": payload, "fixture": {}},
        headers=SESSION_A,
    )
    assert submitted.status_code == 202, submitted.text
    accepted = submitted.json()
    assert accepted["ok"] is True
    assert accepted["status"] == "queued"
    assert accepted["jobId"].startswith("job_")

    # The id is bound to the submitting namespace, even before it finishes.
    foreign = client.get(f"{JOBS}/{accepted['jobId']}", headers=SESSION_B)
    assert foreign.status_code == 404

    done = _wait_for_job(client, accepted["jobId"], session=SESSION_A)
    body = done.json()
    assert body["ok"] is True
    assert body["status"] == "ok"
    assert body["result"]["ok"] is True, body["result"]["errors"]
    assert body["result"]["renderHash"].startswith("sha256:")
    assert body["result"]["notes"]
    assert "errors" not in body

    # The same owner can still read it after completion; the other cannot.
    assert client.get(f"{JOBS}/{accepted['jobId']}", headers=SESSION_A).status_code == 200
    assert client.get(f"{JOBS}/{accepted['jobId']}", headers=SESSION_B).status_code == 404
    assert client.get(f"{JOBS}/job_does_not_exist", headers=SESSION_A).status_code == 404

    # A rejected spec is a successful job with a failed result, not a 500.
    invalid = dict(payload)
    invalid["meter"] = "5/4"
    submitted = client.post(
        JOBS,
        json={"kind": "validate", "spec": invalid},
        headers=SESSION_A,
    )
    assert submitted.status_code == 202
    done = _wait_for_job(client, submitted.json()["jobId"], session=SESSION_A)
    body = done.json()
    assert body["ok"] is True
    assert body["result"]["ok"] is False
    assert body["result"]["errors"]


# ---------------------------------------------------------------------------
# journey 6: owner/visibility isolation


def test_private_spec_is_invisible_to_another_session(client: TestClient) -> None:
    payload = _example(client, EXAMPLE_IDS["villa"])["payload"]

    private = _publish(client, payload, session=SESSION_A)
    assert private.get("visibility", "private") == "private"

    # A cannot be tricked into reading B's spec, and B cannot read A's.
    assert _get(client, private["id"], session=SESSION_A).status_code == 200
    assert _get(client, private["id"], session=SESSION_B).status_code == 404
    assert private["id"] not in {
        item["id"] for item in _list(client, session=SESSION_B)
    }

    # Rollback is owner-only, and a foreign private row reads as 404.
    denied = client.post(f"{SPECS}/{private['id']}/rollback", headers=SESSION_B)
    assert denied.status_code == 404

    # Public rows are readable by every namespace but still owner-only to roll back.
    public = _publish(
        client, payload, session=SESSION_A, visibility="public"
    )
    assert public["visibility"] == "public"
    assert _get(client, public["id"], session=SESSION_B).status_code == 200
    assert public["id"] in {
        item["id"] for item in _list(client, session=SESSION_B)
    }
    assert client.post(
        f"{SPECS}/{public['id']}/rollback", headers=SESSION_B
    ).status_code == 404

    # B's own publish remains invisible to A.
    b_private = _publish(client, payload, session=SESSION_B)
    assert _get(client, b_private["id"], session=SESSION_A).status_code == 404
    assert _get(client, b_private["id"], session=SESSION_B).status_code == 200
