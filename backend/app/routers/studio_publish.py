"""Studio publish/versioning for sentence specs (Phase 0/1 MVP).

Publishing validates one authored mapping with
`app.studio.sentence_spec.parse_spec` and stores it in SQLite. It deliberately
does not register the spec into `SENTENCE_SPECS`: the runtime keeps reading the
code specs until the Phase 2 `texture_registry.py` loader exists.

The router lives separately from `app.routers.studio` (validate/preview) so the
two workstreams do not collide.

Every route reads the optional `X-Studio-Session` header and resolves it to an
opaque `owner_id` (docs §10.2). A missing or blank header resolves to the
`anonymous` namespace, so older clients and tests keep working; new rows stay
`private` by default. This is a namespace, not auth.
"""

from __future__ import annotations

from typing import Any, Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.store.db import get_db
from app.studio import dispatch, publish, quota as studio_quota, session as studio_session
from app.studio.sentence_spec import parse_spec

router = APIRouter(prefix="/v1/studio", tags=["studio-publish"])

_PARSE_ERRORS = (ValueError, KeyError, TypeError)

# Missing/blank `X-Studio-Session` resolves to `anonymous`, so pre-scoping
# clients and tests keep working. This is a namespace, not auth.
studio_owner = studio_session.owner_or_anonymous


class SpecErrorOut(BaseModel):
    path: str
    message: str


class PublishResponse(BaseModel):
    ok: bool
    id: str | None = None
    pattern: str | None = None
    meter: str | None = None
    version: int | None = None
    rollbackOf: str | None = None
    # Default-private responses omit the field (exclude_defaults), so the
    # pre-visibility response shape is unchanged for existing clients.
    visibility: str = publish.VISIBILITY_PRIVATE
    errors: list[SpecErrorOut] = Field(default_factory=list)


class RollbackResponse(PublishResponse):
    """`rollbackOf` names the source version the new version copies."""


class PublishedSpecSummary(BaseModel):
    id: str
    pattern: str
    meter: str
    version: int
    status: str
    createdAt: str
    rollbackOf: str | None = None
    visibility: str = publish.VISIBILITY_PRIVATE


class SpecsResponse(BaseModel):
    ok: bool = True
    specs: list[PublishedSpecSummary]


class PublishedSpecResponse(PublishedSpecSummary):
    ok: bool = True
    payload: dict[str, Any]


def _spec_error(exc: Exception) -> SpecErrorOut:
    """Split a parser message such as ``spec.slots[0].figure: ...``."""
    text = str(exc) or exc.__class__.__name__
    path, separator, message = text.partition(": ")
    if separator and (path == "spec" or path.startswith("spec.")):
        return SpecErrorOut(path=path, message=message)
    return SpecErrorOut(path="spec", message=text)


@router.post(
    "/sentence/publish",
    response_model=PublishResponse,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
)
async def publish_sentence(
    body: dict[str, Any],
    visibility: Literal["private", "public"] = Query(default="private"),
    owner_id: str = Depends(studio_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> PublishResponse:
    """Validate and persist one sentence spec, assigning the next version.

    `visibility` is an optional query flag (`private` default, `public` makes
    the row readable from every namespace).
    """
    try:
        spec = parse_spec(body)
    except _PARSE_ERRORS as exc:
        return PublishResponse(ok=False, errors=[_spec_error(exc)])

    errors = [
        SpecErrorOut(path=error.path, message=error.message)
        for error in dispatch.validate(spec)
    ]
    if errors:
        return PublishResponse(ok=False, errors=errors)

    limits = studio_session.quota_limits()
    global_limits = studio_session.global_quota_limits()
    decision = await studio_quota.consume_with_global(
        db,
        owner_id,
        studio_quota.KIND_SPEC,
        limits.specs_per_day,
        global_limits.specs_per_day,
    )
    if not decision.allowed:
        scope = (
            "Server-wide" if getattr(decision, "scope", "owner") == "global" else "Daily"
        )
        raise HTTPException(
            status_code=429,
            detail={
                "code": "quota_exceeded",
                "message": f"{scope} {decision.kind} quota ({decision.limit}) is exhausted",
                "kind": decision.kind,
                "day": decision.day,
                "limit": decision.limit,
                "retryAfter": decision.retry_after_seconds,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    record = await publish.publish_spec(
        db, spec, owner_id=owner_id, visibility=visibility
    )
    return PublishResponse(
        ok=True,
        id=record["id"],
        pattern=record["pattern"],
        meter=record["meter"],
        version=record["version"],
        visibility=record["visibility"],
    )


@router.get("/sentence/specs", response_model=SpecsResponse)
async def list_sentence_specs(
    pattern: str | None = Query(default=None),
    meter: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    owner_id: str = Depends(studio_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> SpecsResponse:
    """List the caller's specs plus every public spec, newest version first."""
    rows = await publish.list_specs(
        db, pattern=pattern, meter=meter, limit=limit, owner_id=owner_id
    )
    return SpecsResponse(specs=[PublishedSpecSummary(**row) for row in rows])


@router.get("/sentence/specs/{spec_id}", response_model=PublishedSpecResponse)
async def get_sentence_spec(
    spec_id: str,
    owner_id: str = Depends(studio_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> PublishedSpecResponse:
    """Return one published spec including its payload.

    A private row owned by another namespace reads as 404, not 403, so its
    existence is not leaked.
    """
    record = await publish.get_spec(db, spec_id, owner_id=owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="published spec not found")
    return PublishedSpecResponse(**record)


@router.post(
    "/sentence/specs/{spec_id}/rollback",
    response_model=RollbackResponse,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
)
async def rollback_sentence_spec(
    spec_id: str,
    owner_id: str = Depends(studio_owner),
    db: aiosqlite.Connection = Depends(get_db),
) -> RollbackResponse:
    """Republish an old version as the next version; never mutate the old row.

    Only the owner can roll a version back, including a public one.
    """
    record = await publish.get_spec(db, spec_id, owner_id=owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="published spec not found")

    # The stored payload passed validation when it was published, but family
    # rules can tighten later, so re-parse and re-validate before copying it.
    try:
        spec = parse_spec(record["payload"])
    except _PARSE_ERRORS as exc:
        return RollbackResponse(ok=False, errors=[_spec_error(exc)])

    errors = [
        SpecErrorOut(path=error.path, message=error.message)
        for error in dispatch.validate(spec)
    ]
    if errors:
        return RollbackResponse(ok=False, errors=errors)

    new_record = await publish.rollback_spec(db, spec, spec_id, owner_id=owner_id)
    if new_record is None:
        # A public row owned by someone else passes the read above but is not
        # rollback-able here; answer the same 404 as a missing row.
        raise HTTPException(status_code=404, detail="published spec not found")
    return RollbackResponse(
        ok=True,
        id=new_record["id"],
        pattern=new_record["pattern"],
        meter=new_record["meter"],
        version=new_record["version"],
        rollbackOf=new_record["rollbackOf"],
        visibility=new_record["visibility"],
    )
