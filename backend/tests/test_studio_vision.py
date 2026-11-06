"""Phase 1 Studio vision backend seam.

Covers the session namespace, `/access` shape, upload dedupe/owner isolation,
MIME/size rejection, signed media tokens, daily quota, Gemini analysis with a
monkeypatched client (never the network), the unconfigured-key error, DELETE
refcounting, and the additive DB migration.

No image bytes live in the repo: ``_png`` builds a tiny valid PNG in memory.
"""

from __future__ import annotations

import asyncio
import hashlib
import sqlite3
import struct
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.routers import studio_vision as studio_vision_router
from app.services import gemini_companion
from app.store import db as store
from app.studio import quota as studio_quota
from app.studio import session as studio_session
from app.studio import store as studio_store
from app.studio import vision

BASE = "/v1/musicalize/studio"
SESSION_A = {"X-Studio-Session": "alpha-session-0001"}
SESSION_B = {"X-Studio-Session": "beta-session-0002"}


def _png(width: int = 4, height: int = 3, *, seed: int = 0) -> bytes:
    """A minimal valid RGB PNG; only the header matters for our parser."""
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


@contextmanager
def _studio_client(tmp_path, monkeypatch, *, vision_flag):
    """Build the same app; ``vision_flag=None`` leaves the flag unset (off)."""
    if store._db is not None:  # pragma: no cover - defensive cleanup
        asyncio.run(store.close_db())

    monkeypatch.setenv("VSTOCK_DB_PATH", str(tmp_path / "studio.db"))
    monkeypatch.setenv("VSTOCK_STUDIO_DIR", str(tmp_path / "studio"))
    monkeypatch.setenv("VSTOCK_STUDIO_SECRET", "test-secret")
    if vision_flag is None:
        monkeypatch.delenv(studio_vision_router.VISION_FLAG, raising=False)
    else:
        monkeypatch.setenv(studio_vision_router.VISION_FLAG, vision_flag)
    for name in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_GENAI_API_KEY",
        "GCP_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "GEMINI_MODEL",
        "VSTOCK_STUDIO_UPLOADS_PER_DAY",
        "VSTOCK_STUDIO_ANALYSES_PER_DAY",
        "VSTOCK_STUDIO_MAX_IMAGE_MB",
        "VSTOCK_STUDIO_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)

    app = FastAPI()
    app.include_router(studio_vision_router.router)
    with TestClient(app) as test_client:
        try:
            yield test_client
        finally:
            test_client.portal.call(store.close_db)


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    with _studio_client(tmp_path, monkeypatch, vision_flag="1") as test_client:
        yield test_client


@pytest.fixture()
def vision_disabled_client(tmp_path, monkeypatch) -> TestClient:
    with _studio_client(tmp_path, monkeypatch, vision_flag=None) as test_client:
        yield test_client


def _upload(
    client: TestClient,
    data: bytes,
    *,
    session: dict | None = SESSION_A,
    name: str = "page.png",
    mime: str = "image/png",
):
    return client.post(
        f"{BASE}/uploads",
        files={"file": (name, data, mime)},
        headers=session or {},
    )


def _refcount(client: TestClient, sha256: str) -> int:
    async def read() -> int:
        db = await store.get_db()
        return await studio_store.blob_refcount(db, sha256)

    return client.portal.call(read)


def _quota_used(client: TestClient, owner_id: str, kind: str) -> int:
    async def read() -> int:
        db = await store.get_db()
        return await studio_quota.used(db, owner_id, kind)

    return client.portal.call(read)


# ---------------------------------------------------------------------------
# session namespace


def test_session_hash_is_stable_and_isolated() -> None:
    owner = studio_session.owner_id_for("alpha-session-0001")
    assert owner == studio_session.owner_id_for("alpha-session-0001")
    assert owner == studio_session.owner_id_for("  alpha-session-0001  ")
    assert owner != studio_session.owner_id_for("beta-session-0002")
    assert len(owner or "") == 64
    assert studio_session.owner_id_for(None) is None
    assert studio_session.owner_id_for("") is None
    assert studio_session.owner_id_for("   ") is None


def test_access_shape_needs_no_session(client: TestClient) -> None:
    response = client.get(f"{BASE}/access")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["reason"] == "open_beta"
    assert body["quota"] == {
        "uploadsPerDay": 20,
        "analysesPerDay": 100,
        "specsPerDay": 50,
        "maxImageMb": 20,
        "previewsConcurrent": 1,
    }


def test_access_reflects_env_and_disabled_mode(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_ENABLED", "0")
    monkeypatch.setenv("VSTOCK_STUDIO_UPLOADS_PER_DAY", "3")
    body = client.get(f"{BASE}/access").json()
    assert body["enabled"] is False
    assert body["reason"] == "disabled"
    assert body["quota"]["uploadsPerDay"] == 3

    blocked = _upload(client, _png())
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "studio_disabled"


def test_missing_session_is_400_for_upload_and_analyze(client: TestClient) -> None:
    upload = _upload(client, _png(), session=None)
    assert upload.status_code == 400
    assert upload.json()["detail"]["code"] == "studio_session_required"

    analyze = client.post(
        f"{BASE}/analyze", json={"uploadId": "anything"}, headers={}
    )
    assert analyze.status_code == 400


DISABLED_DETAIL = {
    "ok": False,
    "errors": [{"path": "vision", "message": "Studio vision is disabled"}],
}


def _forbid_gemini(monkeypatch) -> list[int]:
    """A Gemini seam that fails loudly if the disabled routes reach it."""
    calls: list[int] = []

    async def sentinel(*args, **kwargs):
        calls.append(1)
        raise AssertionError("Gemini must not be called while vision is disabled")

    monkeypatch.setattr(vision, "analyze_image", sentinel)
    monkeypatch.setattr(vision, "_call_gemini", sentinel)
    return calls


def test_vision_flag_off_hides_every_route_without_calling_gemini(
    vision_disabled_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    calls = _forbid_gemini(monkeypatch)

    access = vision_disabled_client.get(f"{BASE}/access")
    assert access.status_code == 404
    assert access.json()["detail"] == DISABLED_DETAIL

    analyze = vision_disabled_client.post(
        f"{BASE}/analyze", json={"uploadId": "anything"}, headers=SESSION_A
    )
    assert analyze.status_code == 404
    assert analyze.json()["detail"] == DISABLED_DETAIL

    upload = _upload(vision_disabled_client, _png())
    assert upload.status_code == 404
    assert upload.json()["detail"] == DISABLED_DETAIL

    media = vision_disabled_client.get(f"{BASE}/uploads/any?t=token")
    assert media.status_code == 404

    deleted = vision_disabled_client.delete(
        f"{BASE}/uploads/any", headers=SESSION_A
    )
    assert deleted.status_code == 404

    assert calls == []


def test_vision_enabled_reads_the_env_on_every_call(monkeypatch) -> None:
    monkeypatch.delenv(studio_vision_router.VISION_FLAG, raising=False)
    assert studio_vision_router.VISION_FLAG == "VSTOCK_STUDIO_VISION"
    assert studio_vision_router.vision_enabled() is False

    with pytest.raises(HTTPException) as disabled:
        studio_vision_router.require_vision_enabled()
    assert disabled.value.status_code == 404
    assert disabled.value.detail == DISABLED_DETAIL

    monkeypatch.setenv(studio_vision_router.VISION_FLAG, "1")
    assert studio_vision_router.vision_enabled() is True
    assert studio_vision_router.require_vision_enabled() is None

    monkeypatch.setenv(studio_vision_router.VISION_FLAG, "0")
    assert studio_vision_router.vision_enabled() is False

    for truthy in ("true", "YES", " on "):
        monkeypatch.setenv(studio_vision_router.VISION_FLAG, truthy)
        assert studio_vision_router.vision_enabled() is True

    for falsy in ("", "false", "off", "no"):
        monkeypatch.setenv(studio_vision_router.VISION_FLAG, falsy)
        assert studio_vision_router.vision_enabled() is False

    monkeypatch.delenv(studio_vision_router.VISION_FLAG, raising=False)
    assert studio_vision_router.vision_enabled() is False


# ---------------------------------------------------------------------------
# uploads


def test_upload_returns_metadata_and_signed_url(client: TestClient) -> None:
    data = _png(7, 5)
    response = _upload(client, data)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["width"] == 7 and body["height"] == 5
    assert body["mime"] == "image/png"
    assert body["sizeBytes"] == len(data)
    assert body["sha256"] == hashlib.sha256(data).hexdigest()
    assert body["url"].startswith(f"{BASE}/uploads/{body['id']}?t=")
    assert body["token"] in body["url"]
    assert 300 <= body["tokenTtlSeconds"] <= 900

    media = client.get(body["url"])
    assert media.status_code == 200
    assert media.content == data
    assert media.headers["content-type"] == "image/png"


def test_upload_dedupes_by_sha256_but_keeps_ids(client: TestClient) -> None:
    data = _png(seed=9)
    first = _upload(client, data, name="one.png").json()
    second = _upload(client, data, name="two.png").json()
    assert first["id"] != second["id"]
    assert first["sha256"] == second["sha256"]
    assert _refcount(client, first["sha256"]) == 2

    files = list((studio_store.studio_root() / "uploads").iterdir())
    assert len(files) == 1


def test_upload_owner_isolation(client: TestClient) -> None:
    upload = _upload(client, _png(), session=SESSION_A).json()
    owner_a = studio_session.owner_id_for("alpha-session-0001")
    owner_b = studio_session.owner_id_for("beta-session-0002")

    ok = client.get(upload["url"])
    assert ok.status_code == 200

    wrong_owner_token, _ = studio_session.sign_media_token(owner_b, upload["id"])
    wrong = client.get(f"{BASE}/uploads/{upload['id']}?t={wrong_owner_token}")
    assert wrong.status_code == 403

    deleted = client.delete(f"{BASE}/uploads/{upload['id']}", headers=SESSION_B)
    assert deleted.status_code == 404
    assert client.get(upload["url"]).status_code == 200
    assert owner_a != owner_b


def test_upload_rejects_unknown_mime_and_mismatched_bytes(client: TestClient) -> None:
    text = _upload(client, b"not an image", mime="text/plain")
    assert text.status_code == 415
    assert text.json()["detail"]["code"] == "unsupported_mime"

    jpeg_bytes = b"\xff\xd8\xff\xe0" + b"0" * 32
    mismatch = _upload(client, jpeg_bytes, mime="image/png")
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "mime_mismatch"

    generic = _upload(
        client, _png(seed=5), mime="application/octet-stream", name="camera"
    )
    assert generic.status_code == 201
    assert generic.json()["mime"] == "image/png"


def test_upload_rejects_too_many_bytes(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_MAX_IMAGE_MB", "1")
    oversized = _png() + b"0" * (1024 * 1024)
    response = _upload(client, oversized)
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "image_too_large"


def test_upload_rejects_too_many_pixels(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_MAX_PIXELS", "2")
    response = _upload(client, _png(4, 3))
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "image_too_large"


def test_media_token_valid_expired_and_wrong_resource() -> None:
    owner = studio_session.owner_id_for("alpha")
    token, expires_at = studio_session.sign_media_token(owner, "upload-1", now=1000)
    assert expires_at == 1000 + studio_session.token_ttl_seconds()
    assert studio_session.verify_media_token(token, "upload-1", now=1001) == owner

    with pytest.raises(studio_session.TokenError) as expired:
        studio_session.verify_media_token(token, "upload-1", now=expires_at + 1)
    assert expired.value.code == "expired"

    # Mutate the first signature character, not the last: base64 ignores the
    # low padding bits of the final character, so a last-character change can
    # decode to the same bytes and make this assertion flaky.
    signature_start = token.index(".") + 1
    signature_tail = signature_start + 1
    replacement = "A" if token[signature_start] != "A" else "B"
    tampered_token = (
        token[:signature_start] + replacement + token[signature_tail:]
    )
    with pytest.raises(studio_session.TokenError) as tampered:
        studio_session.verify_media_token(tampered_token, "upload-1", now=1001)
    assert tampered.value.code == "bad_signature"

    with pytest.raises(studio_session.TokenError) as other:
        studio_session.verify_media_token(token, "upload-2", now=1001)
    assert other.value.code == "bad_signature"


def test_expired_http_token_is_403(client: TestClient) -> None:
    upload = _upload(client, _png()).json()
    owner = studio_session.owner_id_for("alpha-session-0001")
    token, _ = studio_session.sign_media_token(owner, upload["id"], ttl_seconds=-5)
    response = client.get(f"{BASE}/uploads/{upload['id']}?t={token}")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "invalid_token"

    assert client.get(f"{BASE}/uploads/{upload['id']}").status_code == 403


# ---------------------------------------------------------------------------
# quota


def test_upload_quota_returns_429_with_retry_after(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_UPLOADS_PER_DAY", "1")
    first = _upload(client, _png(seed=1))
    assert first.status_code == 201

    second = _upload(client, _png(seed=2))
    assert second.status_code == 429
    detail = second.json()["detail"]
    assert detail["code"] == "quota_exceeded"
    assert detail["kind"] == "upload"
    assert detail["limit"] == 1
    assert int(second.headers["Retry-After"]) > 0

    owner = studio_session.owner_id_for("alpha-session-0001")
    assert _quota_used(client, owner, studio_quota.KIND_UPLOAD) == 1


def test_content_length_guard_rejects_oversized_multipart() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/uploads",
            "headers": [(b"content-length", b"999999999")],
        }
    )
    with pytest.raises(HTTPException) as exc:
        studio_vision_router._content_length_guard(request)
    assert exc.value.status_code == 413


def test_chunked_upload_is_rejected_before_spooling() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/uploads",
            "headers": [(b"transfer-encoding", b"chunked")],
        }
    )
    with pytest.raises(HTTPException) as exc:
        studio_vision_router._content_length_guard(request)
    assert exc.value.status_code == 411


def test_global_quota_stops_session_rotation(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_GLOBAL_UPLOADS_PER_DAY", "1")
    first = client.post(
        f"{BASE}/uploads",
        headers=SESSION_A,
        files={"file": ("a.png", _png(seed=1), "image/png")},
    )
    assert first.status_code == 201
    second = client.post(
        f"{BASE}/uploads",
        headers=SESSION_B,
        files={"file": ("b.png", _png(seed=2), "image/png")},
    )
    assert second.status_code == 429
    assert second.json()["detail"]["kind"] == "upload"
    assert "Server-wide" in second.json()["detail"]["message"]


def test_vision_cache_prunes_old_drafts(tmp_path, monkeypatch) -> None:
    import os
    import time

    monkeypatch.setenv("VSTOCK_STUDIO_DIR", str(tmp_path))
    path = tmp_path / "vision-cache"
    path.mkdir()
    old = path / "old.json"
    old.write_text("{}", encoding="utf-8")
    stale = time.time() - 40 * 86400
    os.utime(old, (stale, stale))
    fresh = path / "fresh.json"
    fresh.write_text("{}", encoding="utf-8")
    assert vision.cache_dir() == path
    assert not old.exists()
    assert fresh.exists()


def test_vision_cache_prunes_to_max_files(tmp_path, monkeypatch) -> None:
    import os
    import time

    monkeypatch.setenv("VSTOCK_STUDIO_DIR", str(tmp_path))
    monkeypatch.setenv("VSTOCK_STUDIO_VISION_CACHE_MAX_FILES", "1")
    path = tmp_path / "vision-cache"
    path.mkdir()
    older = path / "older.json"
    newer = path / "newer.json"
    older.write_text("{}", encoding="utf-8")
    newer.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(older, (now - 60, now - 60))
    os.utime(newer, (now, now))
    vision.cache_dir()
    assert not older.exists()
    assert newer.exists()


def test_missing_secret_is_random_not_a_known_constant(monkeypatch) -> None:
    monkeypatch.delenv("VSTOCK_STUDIO_SECRET", raising=False)
    secret = studio_session._secret()
    assert secret != b"vstock-studio-dev-secret"
    token, _ = studio_session.sign_media_token("owner", "resource", now=1000)
    assert studio_session.verify_media_token(token, "resource", now=1000) == "owner"


def test_upload_quota_is_per_owner(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_UPLOADS_PER_DAY", "1")
    assert _upload(client, _png(seed=1), session=SESSION_A).status_code == 201
    assert _upload(client, _png(seed=2), session=SESSION_A).status_code == 429
    assert _upload(client, _png(seed=3), session=SESSION_B).status_code == 201


def test_quota_uses_injected_clock_and_resets_next_day(client: TestClient) -> None:
    owner = studio_session.owner_id_for("alpha-session-0001")
    late = datetime(2026, 1, 1, 23, 59, tzinfo=timezone.utc)
    tomorrow = datetime(2026, 1, 2, 0, 1, tzinfo=timezone.utc)

    async def run() -> tuple[bool, bool, int]:
        db = await store.get_db()
        first = await studio_quota.consume(
            db, owner, studio_quota.KIND_ANALYZE, 1, now=late
        )
        blocked = await studio_quota.consume(
            db, owner, studio_quota.KIND_ANALYZE, 1, now=late
        )
        next_day = await studio_quota.consume(
            db, owner, studio_quota.KIND_ANALYZE, 1, now=tomorrow
        )
        return first.allowed, blocked.allowed, next_day.used

    assert client.portal.call(run) == (True, False, 1)


def test_analyze_quota_returns_429(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_ANALYSES_PER_DAY", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    upload = _upload(client, _png()).json()

    async def fake(*args, **kwargs):
        return _FakeResponse()

    monkeypatch.setattr(vision, "_call_gemini", fake)
    first = client.post(
        f"{BASE}/analyze", json={"uploadId": upload["id"]}, headers=SESSION_A
    )
    assert first.status_code == 200
    second = client.post(
        f"{BASE}/analyze",
        json={"uploadId": upload["id"], "useCache": False},
        headers=SESSION_A,
    )
    assert second.status_code == 429
    assert second.json()["detail"]["kind"] == "analyze"


# ---------------------------------------------------------------------------
# Gemini analysis


class _FakeFinish:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeCandidate:
    def __init__(self, name: str = "STOP") -> None:
        self.finish_reason = _FakeFinish(name)


class _FakeResponse:
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


def test_analyze_caches_draft_and_skips_second_gemini_call(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    upload = _upload(client, _png(seed=4)).json()
    calls: list[str] = []

    async def fake(data, mime, crop, metadata, *, model, client=None):
        calls.append(model)
        return _FakeResponse()

    monkeypatch.setattr(vision, "_call_gemini", fake)

    first = client.post(
        f"{BASE}/analyze",
        json={"uploadId": upload["id"], "crop": {"x": 10, "y": 20}},
        headers=SESSION_A,
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["ok"] is True
    assert body["cacheHit"] is False
    assert body["draft"]["review"] == "pending"
    assert body["draft"]["source"] == "gemini"
    assert body["draft"]["notes"][0]["sounding_pitch"] == "E3"
    assert body["draft"]["measures"][0]["meter"] == "3/4"
    assert body["promptVersion"] == vision.PROMPT_VERSION == "studio-v1"
    assert body["schemaVersion"] == vision.SCHEMA_VERSION == "studio-v1"
    assert body["quota"]["used"] == 1

    second = client.post(
        f"{BASE}/analyze",
        json={"uploadId": upload["id"], "crop": {"x": 10, "y": 20}},
        headers=SESSION_A,
    )
    assert second.status_code == 200
    assert second.json()["cacheHit"] is True
    assert len(calls) == 1

    # A different model must not reuse the draft.
    monkeypatch.setenv("GEMINI_MODEL", "different-model")
    third = client.post(
        f"{BASE}/analyze",
        json={"uploadId": upload["id"], "crop": {"x": 10, "y": 20}},
        headers=SESSION_A,
    )
    assert third.json()["cacheHit"] is False
    assert calls == [gemini_companion.DEFAULT_MODEL, "different-model"]


def test_analyze_without_gemini_is_an_error_not_a_fake_draft(
    client: TestClient,
) -> None:
    upload = _upload(client, _png()).json()
    response = client.post(
        f"{BASE}/analyze", json={"uploadId": upload["id"]}, headers=SESSION_A
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["draft"] is None
    assert body["error"]["code"] == "gemini_unconfigured"
    assert body["quota"] is None
    assert "GEMINI_API_KEY" in body["error"]["message"]


def test_analyze_blocked_response_is_an_error_without_retry(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    upload = _upload(client, _png()).json()
    calls: list[int] = []

    async def blocked(*args, **kwargs):
        calls.append(1)
        return _FakeResponse("SAFETY")

    monkeypatch.setattr(vision, "_call_gemini", blocked)
    response = client.post(
        f"{BASE}/analyze", json={"uploadId": upload["id"]}, headers=SESSION_A
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "gemini_blocked"
    assert body["draft"] is None
    assert calls == [1]


def test_analyze_unknown_or_foreign_upload_is_404(client: TestClient) -> None:
    unknown = client.post(
        f"{BASE}/analyze", json={"uploadId": "missing"}, headers=SESSION_A
    )
    assert unknown.status_code == 404

    upload = _upload(client, _png(), session=SESSION_A).json()
    foreign = client.post(
        f"{BASE}/analyze", json={"uploadId": upload["id"]}, headers=SESSION_B
    )
    assert foreign.status_code == 404


def test_analyze_ignores_cached_draft_of_another_model() -> None:
    """Cache key includes model/prompt/schema: keys differ, no cross-reads."""
    base = vision.cache_key("a" * 64, None, "model-a")
    assert base != vision.cache_key("a" * 64, None, "model-b")
    assert base != vision.cache_key("a" * 64, {"x": 1}, "model-a")
    assert base != vision.cache_key("a" * 64, None, "model-a", "studio-v2")
    assert base != vision.cache_key(
        "a" * 64, None, "model-a", schema_version="studio-v2"
    )


# ---------------------------------------------------------------------------
# delete and refcount


def test_delete_decrements_refcount_and_removes_file_at_zero(
    client: TestClient,
) -> None:
    data = _png(seed=12)
    first = _upload(client, data).json()
    second = _upload(client, data).json()
    path = studio_store.blob_path(f"uploads/{first['sha256']}.png")
    assert path.is_file()

    one = client.delete(f"{BASE}/uploads/{first['id']}", headers=SESSION_A)
    assert one.status_code == 200
    assert _refcount(client, first["sha256"]) == 1
    assert path.is_file()

    two = client.delete(f"{BASE}/uploads/{second['id']}", headers=SESSION_A)
    assert two.status_code == 200
    assert _refcount(client, first["sha256"]) == 0
    assert not path.is_file()


def test_delete_is_409_while_a_spec_references_the_upload(
    client: TestClient, monkeypatch
) -> None:
    upload = _upload(client, _png()).json()

    async def referenced(db, upload_id, owner_id):
        return True

    monkeypatch.setattr(studio_store, "has_spec_reference", referenced)
    response = client.delete(f"{BASE}/uploads/{upload['id']}", headers=SESSION_A)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "upload_in_use"
    assert client.get(upload["url"]).status_code == 200


# ---------------------------------------------------------------------------
# migration


def test_init_db_adds_studio_tables_and_backfills_upload_columns(
    tmp_path, monkeypatch
) -> None:
    if store._db is not None:  # pragma: no cover - defensive cleanup
        asyncio.run(store.close_db())

    legacy_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(legacy_path)
    connection.executescript(
        """
        CREATE TABLE studio_uploads (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            blob_sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO studio_uploads (id, owner_id, blob_sha256, created_at)
        VALUES ('old-upload', 'old-owner', 'aabb', '2025-01-01');
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setenv("VSTOCK_DB_PATH", str(legacy_path))

    async def migrate():
        await store.init_db()
        db = await store.get_db()
        cursor = await db.execute("PRAGMA table_info(studio_uploads)")
        columns = {row[1] for row in await cursor.fetchall()}
        cursor = await db.execute(
            "SELECT filename, mime, width, height FROM studio_uploads "
            "WHERE id = 'old-upload'"
        )
        row = await cursor.fetchone()
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('studio_blobs', 'studio_quota')"
        )
        tables = {item[0] for item in await cursor.fetchall()}
        await store.close_db()
        return columns, row, tables

    columns, row, tables = asyncio.run(migrate())
    assert {"filename", "mime", "width", "height"} <= columns
    assert row["filename"] == "" and row["mime"] == ""
    assert row["width"] is None and row["height"] is None
    assert tables == {"studio_blobs", "studio_quota"}
