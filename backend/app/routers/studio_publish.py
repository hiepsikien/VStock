"""Studio publish/versioning for sentence specs (Phase 0/1 MVP).

Publishing validates one authored mapping with
`app.studio.sentence_spec.parse_spec` and stores it in SQLite. It deliberately
does not register the spec into `SENTENCE_SPECS`: the runtime keeps reading the
code specs until the Phase 2 `texture_registry.py` loader exists.

The router lives separately from `app.routers.studio` (validate/preview) so the
two workstreams do not collide.
"""

from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.store.db import get_db
from app.studio import dispatch, publish
from app.studio.sentence_spec import parse_spec

router = APIRouter(prefix="/v1/studio", tags=["studio-publish"])

_PARSE_ERRORS = (ValueError, KeyError, TypeError)


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
    db: aiosqlite.Connection = Depends(get_db),
) -> PublishResponse:
    """Validate and persist one sentence spec, assigning the next version."""
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

    record = await publish.publish_spec(db, spec)
    return PublishResponse(
        ok=True,
        id=record["id"],
        pattern=record["pattern"],
        meter=record["meter"],
        version=record["version"],
    )


@router.get("/sentence/specs", response_model=SpecsResponse)
async def list_sentence_specs(
    pattern: str | None = Query(default=None),
    meter: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: aiosqlite.Connection = Depends(get_db),
) -> SpecsResponse:
    """List published spec summaries, optionally filtered by pattern or meter."""
    rows = await publish.list_specs(db, pattern=pattern, meter=meter, limit=limit)
    return SpecsResponse(specs=[PublishedSpecSummary(**row) for row in rows])


@router.get("/sentence/specs/{spec_id}", response_model=PublishedSpecResponse)
async def get_sentence_spec(
    spec_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> PublishedSpecResponse:
    """Return one published spec including its payload."""
    record = await publish.get_spec(db, spec_id)
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
    db: aiosqlite.Connection = Depends(get_db),
) -> RollbackResponse:
    """Republish an old version as the next version; never mutate the old row."""
    record = await publish.get_spec(db, spec_id)
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

    new_record = await publish.rollback_spec(db, spec, spec_id)
    if new_record is None:  # pragma: no cover - the row was just read
        raise HTTPException(status_code=404, detail="published spec not found")
    return RollbackResponse(
        ok=True,
        id=new_record["id"],
        pattern=new_record["pattern"],
        meter=new_record["meter"],
        version=new_record["version"],
        rollbackOf=new_record["rollbackOf"],
    )
