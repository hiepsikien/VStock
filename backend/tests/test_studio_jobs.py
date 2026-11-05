"""Studio job queue: 202 after submit, 409 while busy, 200 when done.

The queue is process-local by design. Every test gets its own registry and
single-worker executor so a blocked job in one test cannot delay another, and
the router is exercised through the same FastAPI wiring production uses.
"""

from __future__ import annotations

import inspect
import json
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_jobs as studio_jobs_router
from app.studio import dispatch, jobs
from app.studio.export import SPECS_DIR


def _castillo_payload() -> dict:
    data = json.loads((SPECS_DIR / "castillo-3-4.json").read_text(encoding="utf-8"))
    return data["specs"][0]


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_jobs_router.router)
    return TestClient(app)


@pytest.fixture
def registry(monkeypatch):
    reg = jobs.JobRegistry()
    monkeypatch.setattr(jobs, "get_registry", lambda: reg)
    yield reg
    reg.shutdown(wait=True)


def _wait(client: TestClient, job_id: str, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/v1/studio/jobs/{job_id}")
        if response.status_code != 409:
            return response
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


class _Clock:
    """Deterministic monotonic clock for TTL tests."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _wait_registry(registry: jobs.JobRegistry, job_id: str) -> jobs.JobStatus:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        status = registry.get(job_id)
        assert status is not None
        if status.done:
            return status
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish")


def test_validate_job_returns_202_then_200(registry) -> None:
    client = _client()
    response = client.post(
        "/v1/studio/jobs",
        json={"kind": "validate", "spec": _castillo_payload()},
    )
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["ok"] is True
    assert accepted["status"] == "queued"
    assert accepted["jobId"].startswith("job_")

    done = _wait(client, accepted["jobId"])
    assert done.status_code == 200
    body = done.json()
    assert body["ok"] is True
    assert body["jobId"] == accepted["jobId"]
    assert body["status"] == "ok"
    assert body["result"]["ok"] is True
    assert body["result"]["errors"] == []
    assert "errors" not in body


def test_preview_job_returns_the_same_preview_result(registry) -> None:
    client = _client()
    spec = _castillo_payload()
    fixture = {"length": 9, "bars": 2}
    response = client.post(
        "/v1/studio/jobs",
        json={"kind": "preview", "spec": spec, "fixture": fixture},
    )
    assert response.status_code == 202

    done = _wait(client, response.json()["jobId"])
    assert done.status_code == 200
    body = done.json()
    assert body["ok"] is True
    result = body["result"]
    assert result["ok"] is True
    assert result["renderHash"].startswith("sha256:")
    assert result["notes"]
    assert result["plan"] is not None
    assert result["matrix"]


def test_invalid_spec_is_a_finished_job_with_errors(registry) -> None:
    client = _client()
    spec = {**_castillo_payload(), "meter": "3/5"}
    response = client.post(
        "/v1/studio/jobs", json={"kind": "validate", "spec": spec}
    )
    assert response.status_code == 202

    body = _wait(client, response.json()["jobId"]).json()
    assert body["status"] == "ok"
    assert body["ok"] is True
    assert body["result"]["ok"] is False
    assert [error["path"] for error in body["result"]["errors"]] == ["meter"]


def test_unparseable_spec_is_recorded_not_raised(registry) -> None:
    client = _client()
    response = client.post(
        "/v1/studio/jobs",
        json={"kind": "preview", "spec": {"id": "broken"}},
    )
    assert response.status_code == 202

    body = _wait(client, response.json()["jobId"]).json()
    assert body["status"] == "ok"
    result = body["result"]
    assert result["ok"] is False
    assert result["errors"][0]["path"] == "spec"
    assert result["plan"] is None
    assert result["matrix"] == []


def test_409_while_running_then_200(registry, monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    original = dispatch.preview_sentence

    def blocking_preview(spec, fixture=None):
        started.set()
        assert release.wait(5.0)
        return original(spec, fixture)

    monkeypatch.setattr(dispatch, "preview_sentence", blocking_preview)

    client = _client()
    response = client.post(
        "/v1/studio/jobs",
        json={
            "kind": "preview",
            "spec": _castillo_payload(),
            "fixture": {"length": 9, "bars": 2},
        },
    )
    assert response.status_code == 202
    job_id = response.json()["jobId"]
    assert started.wait(5.0)

    busy = client.get(f"/v1/studio/jobs/{job_id}")
    assert busy.status_code == 409
    assert busy.headers["Retry-After"] == "1"
    assert busy.json() == {"ok": False, "jobId": job_id, "status": "running"}

    release.set()
    done = _wait(client, job_id)
    assert done.status_code == 200
    assert done.json()["result"]["renderHash"].startswith("sha256:")


def test_renderer_error_is_stored_as_a_job_error(registry, monkeypatch) -> None:
    def exploding_preview(spec, fixture=None):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(dispatch, "preview_sentence", exploding_preview)

    client = _client()
    response = client.post(
        "/v1/studio/jobs",
        json={
            "kind": "preview",
            "spec": _castillo_payload(),
            "fixture": {"length": 9, "bars": 2},
        },
    )
    assert response.status_code == 202

    done = _wait(client, response.json()["jobId"])
    assert done.status_code == 200
    body = done.json()
    assert body["ok"] is False
    assert body["status"] == "error"
    assert "result" not in body
    assert body["errors"] == [
        {"path": "preview", "message": "RuntimeError: renderer exploded"}
    ]


def test_unknown_job_is_404(registry) -> None:
    response = _client().get("/v1/studio/jobs/job_missing")
    assert response.status_code == 404
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "missing"
    assert body["errors"][0]["path"] == "job"


def test_expired_finished_job_is_404(registry, monkeypatch) -> None:
    clock = _Clock()
    reg = jobs.JobRegistry(ttl_seconds=10, clock=clock)
    monkeypatch.setattr(jobs, "get_registry", lambda: reg)
    client = _client()

    accepted = client.post(
        "/v1/studio/jobs",
        json={"kind": "validate", "spec": _castillo_payload()},
    ).json()
    assert _wait(client, accepted["jobId"]).status_code == 200

    clock.advance(10)
    response = client.get(f"/v1/studio/jobs/{accepted['jobId']}")
    assert response.status_code == 404
    assert response.json()["status"] == "missing"
    reg.shutdown(wait=True)


def test_queue_bound_evicts_the_oldest_finished_job(registry) -> None:
    clock = _Clock()
    reg = jobs.JobRegistry(max_jobs=2, clock=clock)
    spec = _castillo_payload()

    first = reg.submit("validate", spec)
    assert _wait_registry(reg, first.id).status == "ok"
    second = reg.submit("validate", spec)
    assert _wait_registry(reg, second.id).status == "ok"

    third = reg.submit("validate", spec)
    assert _wait_registry(reg, third.id).status == "ok"

    assert reg.get(first.id) is None
    assert reg.get(second.id) is not None
    assert reg.get(third.id) is not None
    assert reg.size == 2
    reg.shutdown(wait=True)


def test_full_queue_rejects_when_every_job_is_active(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    original = dispatch.preview_sentence

    def blocking_preview(spec, fixture=None):
        started.set()
        assert release.wait(5.0)
        return original(spec, fixture)

    monkeypatch.setattr(dispatch, "preview_sentence", blocking_preview)
    reg = jobs.JobRegistry(max_jobs=1)

    first = reg.submit(
        "preview", _castillo_payload(), {"length": 9, "bars": 2}
    )
    assert started.wait(5.0)
    with pytest.raises(jobs.JobQueueFull):
        reg.submit("validate", _castillo_payload())

    release.set()
    assert _wait_registry(reg, first.id).status == "ok"
    reg.shutdown(wait=True)


def test_owner_cap_limits_active_jobs(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()
    original = dispatch.preview_sentence

    def blocking_preview(spec, fixture=None):
        started.set()
        assert release.wait(5.0)
        return original(spec, fixture)

    monkeypatch.setattr(dispatch, "preview_sentence", blocking_preview)
    reg = jobs.JobRegistry(max_per_owner=1)

    first = reg.submit(
        "preview",
        _castillo_payload(),
        {"length": 9, "bars": 2},
        owner_id="owner-a",
    )
    assert started.wait(5.0)
    with pytest.raises(jobs.JobOwnerFull):
        reg.submit(
            "validate", _castillo_payload(), owner_id="owner-a"
        )
    second = reg.submit(
        "validate", _castillo_payload(), owner_id="owner-b"
    )

    release.set()
    assert _wait_registry(reg, first.id).status == "ok"
    assert _wait_registry(reg, second.id).status == "ok"
    reg.shutdown(wait=True)


def test_finished_job_releases_the_submitted_spec_and_fixture() -> None:
    reg = jobs.JobRegistry()
    accepted = reg.submit(
        "preview",
        _castillo_payload(),
        {"length": 9, "bars": 2},
    )
    assert _wait_registry(reg, accepted.id).status == "ok"
    job = reg._jobs[accepted.id]
    assert job.spec == {}
    assert job.fixture == {}
    reg.shutdown(wait=True)


def test_ttl_prunes_only_finished_jobs(monkeypatch) -> None:
    clock = _Clock()
    reg = jobs.JobRegistry(ttl_seconds=30, clock=clock)

    done = reg.submit("validate", _castillo_payload())
    assert _wait_registry(reg, done.id).status == "ok"
    clock.advance(31)
    assert reg.get(done.id) is None

    started = threading.Event()
    release = threading.Event()
    original = dispatch.preview_sentence

    def blocking_preview(spec, fixture=None):
        started.set()
        assert release.wait(5.0)
        return original(spec, fixture)

    monkeypatch.setattr(dispatch, "preview_sentence", blocking_preview)
    running = reg.submit(
        "preview", _castillo_payload(), {"length": 9, "bars": 2}
    )
    assert started.wait(5.0)
    clock.advance(3600)
    status = reg.get(running.id)
    assert status is not None
    assert status.status == "running"
    release.set()
    assert _wait_registry(reg, running.id).status == "ok"
    reg.shutdown(wait=True)


def test_handlers_are_sync_so_fastapi_keeps_them_off_the_event_loop() -> None:
    assert not inspect.iscoroutinefunction(studio_jobs_router.submit_job)
    assert not inspect.iscoroutinefunction(studio_jobs_router.get_job)


def test_queue_routes_are_registered(main_app) -> None:
    served = {
        (method, route.path)
        for route in main_app.routes
        for method in getattr(route, "methods", ()) or ()
    }
    assert ("POST", "/v1/studio/jobs") in served
    assert ("GET", "/v1/studio/jobs/{job_id}") in served


@pytest.fixture
def main_app():
    from app.main import app

    return app
