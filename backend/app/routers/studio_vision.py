"""Phase 1 Studio vision seam: session namespace, uploads, signed media, Gemini.

Prefix: ``/v1/musicalize/studio``. This router does not touch publish, list, get,
candidate, or runtime code; the existing ``/v1/studio/sentence`` endpoints keep
their semantics.

Endpoints:

* ``GET  /access``                — capability + quota shape (no session needed)
* ``POST /uploads``               — multipart image upload, deduped by sha256
* ``GET  /uploads/{id}?t=...``    — signed-token media (headers impossible here)
* ``DELETE /uploads/{id}``        — owner only; 409 if a spec references it
* ``POST /analyze``               — Gemini vision draft, cached by content key

Session is a namespace, not auth: ``X-Studio-Session`` hashes to ``owner_id``.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services import gemini_companion
from app.store.db import get_db
from app.studio import quota as studio_quota
from app.studio import store as studio_store
from app.studio import vision
from app.studio import session as studio_session

router = APIRouter(prefix="/v1/musicalize/studio", tags=["studio-vision"])

_UPLOAD_CHUNK = 1024 * 1024
# Multipart boundaries/headers are small; allow them before the byte cap so a
# normal max-size image is not rejected by the Content-Length guard.
_UPLOAD_OVERHEAD = 64 * 1024


def _content_length_guard(request: Request) -> None:
    """Reject an obviously oversized multipart body before Starlette spools it."""
    if "chunked" in request.headers.get("transfer-encoding", "").lower():
        # Without a declared length the multipart parser can spool an unbounded
        # body before this route runs. Browsers send Content-Length for FormData.
        raise HTTPException(
            status_code=411,
            detail=_detail(
                "length_required",
                "Uploads must declare Content-Length; chunked uploads are not accepted",
            ),
        )
    raw = request.headers.get("content-length", "").strip()
    if not raw:
        return
    try:
        length = int(raw)
    except ValueError:
        return
    cap = studio_session.quota_limits().max_image_bytes + _UPLOAD_OVERHEAD
    if length > cap:
        raise HTTPException(
            status_code=413,
            detail=_detail(
                "image_too_large",
                "Image exceeds the configured upload limit",
            ),
        )


class QuotaOut(BaseModel):
    uploadsPerDay: int
    analysesPerDay: int
    specsPerDay: int
    maxImageMb: int
    previewsConcurrent: int


class AccessResponse(BaseModel):
    enabled: bool
    reason: str
    quota: QuotaOut


class UploadResponse(BaseModel):
    ok: bool = True
    id: str
    sha256: str
    filename: str
    mime: str
    width: int | None = None
    height: int | None = None
    sizeBytes: int
    createdAt: str
    url: str
    token: str
    tokenExpiresAt: str
    tokenTtlSeconds: int


class DeleteUploadResponse(BaseModel):
    ok: bool = True
    id: str
    deleted: bool = True
    sha256: str


class ErrorOut(BaseModel):
    code: str
    message: str


class QuotaStateOut(BaseModel):
    kind: str
    day: str
    used: int
    limit: int
    remaining: int


class AnalyzeRequest(BaseModel):
    uploadId: str = Field(min_length=1)
    crop: Any | None = None
    metadata: dict[str, Any] | None = None
    useCache: bool = True


class AnalyzeResponse(BaseModel):
    ok: bool
    uploadId: str
    draft: dict[str, Any] | None = None
    cacheHit: bool = False
    model: str | None = None
    promptVersion: str = vision.PROMPT_VERSION
    schemaVersion: str = vision.SCHEMA_VERSION
    quota: QuotaStateOut | None = None
    error: ErrorOut | None = None


def _detail(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _upload_error(exc: studio_store.UploadError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail=_detail(exc.code, str(exc)),
    )


def _quota_error(decision: studio_quota.QuotaDecision) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            **_detail(
                "quota_exceeded",
                (
                    f"Server-wide daily {decision.kind} quota "
                    f"({decision.limit}) is exhausted"
                    if getattr(decision, "scope", "owner") == "global"
                    else f"Daily {decision.kind} quota ({decision.limit}) is exhausted"
                ),
            ),
            "kind": decision.kind,
            "day": decision.day,
            "limit": decision.limit,
            "retryAfter": decision.retry_after_seconds,
        },
        headers={"Retry-After": str(decision.retry_after_seconds)},
    )


def _quota_state(decision: studio_quota.QuotaDecision) -> QuotaStateOut:
    return QuotaStateOut(
        kind=decision.kind,
        day=decision.day,
        used=decision.used,
        limit=decision.limit,
        remaining=decision.remaining,
    )


def _expires_iso(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()


def _upload_payload(record: studio_store.UploadRecord) -> UploadResponse:
    token, expires_at = studio_session.sign_media_token(
        record.owner_id, record.id
    )
    ttl = studio_session.token_ttl_seconds()
    return UploadResponse(
        id=record.id,
        sha256=record.sha256,
        filename=record.filename,
        mime=record.mime,
        width=record.width,
        height=record.height,
        sizeBytes=record.size_bytes,
        createdAt=record.created_at,
        url=f"/v1/musicalize/studio/uploads/{record.id}?t={token}",
        token=token,
        tokenExpiresAt=_expires_iso(expires_at),
        tokenTtlSeconds=ttl,
    )


@router.get("/access", response_model=AccessResponse)
def get_access() -> AccessResponse:
    """Capability + limits; deliberately does not require a session."""
    return AccessResponse(**studio_session.access_payload())


@router.post(
    "/uploads",
    response_model=UploadResponse,
    status_code=201,
    dependencies=[
        Depends(studio_session.require_enabled),
        Depends(_content_length_guard),
    ],
)
async def create_upload(
    file: UploadFile = File(...),
    owner_id: str = Depends(studio_session.require_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> UploadResponse:
    """Store one image, deduped by sha256; each upload gets its own row."""
    limits = studio_session.quota_limits()
    if file.size is not None and file.size > limits.max_image_bytes:
        raise HTTPException(
            status_code=413,
            detail=_detail(
                "image_too_large",
                f"Image exceeds the {limits.max_image_mb} MB limit",
            ),
        )
    total = 0
    with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as spool:
        while True:
            chunk = await file.read(_UPLOAD_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > limits.max_image_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=_detail(
                        "image_too_large",
                        f"Image exceeds the {limits.max_image_mb} MB limit",
                    ),
                )
            spool.write(chunk)
        spool.seek(0)
        data = spool.read()

    try:
        studio_store.validate_image(
            data,
            file.content_type,
            max_bytes=limits.max_image_bytes,
        )
    except studio_store.UploadError as exc:
        raise _upload_error(exc) from exc

    global_limits = studio_session.global_quota_limits()
    decision = await studio_quota.consume_with_global(
        db,
        owner_id,
        studio_quota.KIND_UPLOAD,
        limits.uploads_per_day,
        global_limits.uploads_per_day,
    )
    if not decision.allowed:
        raise _quota_error(decision)

    try:
        record = await studio_store.save_upload(
            db,
            owner_id,
            data,
            filename=file.filename,
            declared_mime=file.content_type,
            max_bytes=limits.max_image_bytes,
        )
    except studio_store.UploadError as exc:
        raise _upload_error(exc) from exc
    return _upload_payload(record)


@router.get("/uploads/{upload_id}")
async def get_upload_media(
    upload_id: str,
    t: str = Query(default=""),
    db: aiosqlite.Connection = Depends(get_db),
) -> FileResponse:
    """Serve image bytes for a short-lived owner token (no session header)."""
    try:
        owner_claim = studio_session.verify_media_token(t, upload_id)
    except studio_session.TokenError as exc:
        raise HTTPException(
            status_code=403,
            detail=_detail("invalid_token", str(exc)),
        ) from exc

    record = await studio_store.get_upload(db, upload_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=_detail("upload_not_found", "No such upload")
        )
    if record.owner_id != owner_claim:
        raise HTTPException(
            status_code=403, detail=_detail("invalid_token", "Token owner mismatch")
        )
    if not record.path.is_file():
        raise HTTPException(
            status_code=404, detail=_detail("upload_blob_missing", "Blob is gone")
        )
    return FileResponse(
        record.path,
        media_type=record.mime,
        filename=record.filename or None,
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.delete(
    "/uploads/{upload_id}",
    response_model=DeleteUploadResponse,
    dependencies=[Depends(studio_session.require_enabled)],
)
async def delete_upload(
    upload_id: str,
    owner_id: str = Depends(studio_session.require_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> DeleteUploadResponse:
    """Delete this owner's upload; 409 while a spec still references it."""
    try:
        record = await studio_store.delete_upload(db, upload_id, owner_id)
    except studio_store.UploadInUse as exc:
        raise HTTPException(
            status_code=409,
            detail=_detail(exc.code, str(exc)),
        ) from exc
    if record is None:
        raise HTTPException(
            status_code=404, detail=_detail("upload_not_found", "No such upload")
        )
    return DeleteUploadResponse(id=record.id, sha256=record.sha256)


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    dependencies=[Depends(studio_session.require_enabled)],
)
async def analyze_upload(
    body: AnalyzeRequest,
    owner_id: str = Depends(studio_session.require_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> AnalyzeResponse:
    """Run one cached Gemini vision draft for an uploaded image."""
    record = await studio_store.get_upload(db, body.uploadId)
    if record is None or record.owner_id != owner_id:
        raise HTTPException(
            status_code=404, detail=_detail("upload_not_found", "No such upload")
        )

    # A cached draft is still valid without a key; only an uncached call needs
    # Gemini, and it must not burn quota when the backend is unconfigured.
    if not gemini_companion.is_gemini_configured():
        result = await vision.analyze_image(
            record.path,
            body.crop,
            body.metadata,
            use_cache=body.useCache,
        )
        return AnalyzeResponse(
            ok=result.ok,
            uploadId=record.id,
            draft=result.draft,
            cacheHit=result.cache_hit,
            model=result.model,
            promptVersion=result.prompt_version,
            schemaVersion=result.schema_version,
            quota=None,
            error=ErrorOut(**result.error) if result.error else None,
        )

    limits = studio_session.quota_limits()
    global_limits = studio_session.global_quota_limits()
    decision = await studio_quota.consume_with_global(
        db,
        owner_id,
        studio_quota.KIND_ANALYZE,
        limits.analyses_per_day,
        global_limits.analyses_per_day,
    )
    if not decision.allowed:
        raise _quota_error(decision)

    result = await vision.analyze_image(
        record.path,
        body.crop,
        body.metadata,
        use_cache=body.useCache,
    )
    return AnalyzeResponse(
        ok=result.ok,
        uploadId=record.id,
        draft=result.draft,
        cacheHit=result.cache_hit,
        model=result.model,
        promptVersion=result.prompt_version,
        schemaVersion=result.schema_version,
        quota=_quota_state(decision),
        error=ErrorOut(**result.error) if result.error else None,
    )
