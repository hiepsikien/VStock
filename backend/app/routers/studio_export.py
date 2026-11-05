"""Studio export: compile an authored spec into a publish bundle.

This is the "publish creates an artifact" seam, without writing into the repo.
The server answers with the bundle JSON; the UI or an agent decides where to
save `spec.json`, `fixture.json`, `rendered.json`, and `registration.md`.

Two routes:

* `POST /v1/studio/sentence/export` compiles the posted `{spec, fixture?}`.
* `POST /v1/studio/sentence/specs/{id}/export` reads a published row through
  `publish.get_spec`, re-validates it, and compiles the default fixture.

Both return `{ok, bundle}` or `{ok: false, errors}`. Neither touches
`SENTENCE_SPECS` and neither writes a file or calls MuseScore.
"""

from __future__ import annotations

from typing import Any, Mapping

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.sonify.sentence_specs import SentenceSpec
from app.store.db import get_db
from app.studio import compiler, publish
from app.studio import session as studio_session
from app.studio.sentence_spec import parse_spec

router = APIRouter(prefix="/v1/studio", tags=["studio-export"])

_PARSE_ERRORS = (ValueError, KeyError, TypeError)


class SpecErrorOut(BaseModel):
    path: str
    message: str


class ExportRequest(BaseModel):
    spec: dict[str, Any]
    fixture: dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    ok: bool
    bundle: dict[str, Any] | None = None
    errors: list[SpecErrorOut] = Field(default_factory=list)


def _parse_error(exc: Exception) -> SpecErrorOut:
    """Split a parser message such as ``spec.slots[0].figure: ...``."""
    text = str(exc) or exc.__class__.__name__
    path, separator, message = text.partition(": ")
    if separator and (path == "spec" or path.startswith("spec.")):
        return SpecErrorOut(path=path, message=message)
    return SpecErrorOut(path="spec", message=text)


def _compile(
    spec: SentenceSpec, fixture: Mapping[str, Any] | None = None
) -> ExportResponse:
    try:
        bundle = compiler.compile_bundle(spec, fixture)
    except compiler.CompileError as exc:
        return ExportResponse(
            ok=False,
            errors=[
                SpecErrorOut(path=error.path, message=error.message)
                for error in exc.errors
            ],
        )
    return ExportResponse(ok=True, bundle=bundle)


@router.post(
    "/sentence/export",
    response_model=ExportResponse,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
)
def export_sentence(body: ExportRequest) -> ExportResponse:
    """Compile one posted spec, returning the bundle and writing nothing."""
    try:
        spec = parse_spec(body.spec)
    except _PARSE_ERRORS as exc:
        return ExportResponse(ok=False, errors=[_parse_error(exc)])
    return _compile(spec, body.fixture)


@router.post(
    "/sentence/specs/{spec_id}/export",
    response_model=ExportResponse,
    response_model_exclude_none=True,
    response_model_exclude_defaults=True,
)
async def export_published_sentence(
    spec_id: str,
    owner_id: str = Depends(studio_session.owner_or_anonymous),
    db: aiosqlite.Connection = Depends(get_db),
) -> ExportResponse:
    """Compile a published spec by id; 404 when the row is not visible."""
    record = await publish.get_spec(db, spec_id, owner_id=owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="published spec not found")

    try:
        spec = parse_spec(record["payload"])
    except _PARSE_ERRORS as exc:
        return ExportResponse(ok=False, errors=[_parse_error(exc)])
    return _compile(spec)
