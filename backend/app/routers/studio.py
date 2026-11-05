"""Studio validate/preview for an authored sentence spec.

No auth, database, queue, or publish here: this is the Phase 0/1 authoring
loop against the real renderers. The JSON parser is workstream A's
`app.studio.sentence_spec.parse_spec`, reached through the adapter in
`app.studio.preview`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.studio import preview
from app.studio.sentence_spec import parse_payload, parse_spec

router = APIRouter(prefix="/v1/studio", tags=["studio"])

_PARSE_ERRORS = (ValueError, KeyError, TypeError)


class SpecErrorOut(BaseModel):
    path: str
    message: str


class ValidateResponse(BaseModel):
    ok: bool
    errors: list[SpecErrorOut] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    spec: dict[str, Any]
    fixture: dict[str, Any] = Field(default_factory=dict)


class PreviewResponse(BaseModel):
    ok: bool
    errors: list[SpecErrorOut] = Field(default_factory=list)
    plan: dict[str, Any] | None = None
    row: list[str] | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)
    renderHash: str | None = None
    matrix: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/sentence/validate", response_model=ValidateResponse)
def validate_sentence(body: dict[str, Any]) -> ValidateResponse:
    """Validate one spec mapping, or a v1 wrapper with several specs."""
    if "specs" in body:
        try:
            specs = parse_payload(body)
        except _PARSE_ERRORS as exc:
            return ValidateResponse(
                ok=False, errors=[SpecErrorOut(path="spec", message=str(exc))]
            )
        errors: list[SpecErrorOut] = []
        for index, spec in enumerate(specs):
            for error in preview.validate_spec(spec):
                path = (
                    f"specs[{index}]"
                    if error.path == "spec"
                    else f"specs[{index}].{error.path}"
                )
                errors.append(SpecErrorOut(path=path, message=error.message))
        return ValidateResponse(ok=not errors, errors=errors)

    try:
        spec = parse_spec(body)
    except _PARSE_ERRORS as exc:
        return ValidateResponse(
            ok=False, errors=[SpecErrorOut(path="spec", message=str(exc))]
        )
    errors = [
        SpecErrorOut(path=error.path, message=error.message)
        for error in preview.validate_spec(spec)
    ]
    return ValidateResponse(ok=not errors, errors=errors)


@router.post("/sentence/preview", response_model=PreviewResponse)
def preview_sentence(body: PreviewRequest) -> PreviewResponse:
    """Validate and render one bounded fixture for an authored spec."""
    try:
        spec = parse_spec(body.spec)
    except _PARSE_ERRORS as exc:
        return PreviewResponse(
            ok=False, errors=[SpecErrorOut(path="spec", message=str(exc))]
        )
    result = preview.preview_spec(spec, body.fixture)
    return PreviewResponse(**result.as_response())
