"""TextureSpec validation seam for the Studio draft panel.

Prefix: ``/v1/studio/texture``. This router is deliberately small: it parses
one ``TextureSpec`` mapping, runs the offline validator, and reports path-shaped
errors. It does not render, register, resolve pitch, or publish; runtime and
interpreter work stay out of Phase 0/1.

``POST /validate`` body is ``{ "spec": { ... } }`` and the response mirrors the
sentence validator: ``{ ok, errors: [{ path, message }] }``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.studio.texture_spec import (
    TextureSpecError,
    parse_texture_spec,
    validate_texture_spec,
)

router = APIRouter(prefix="/v1/studio/texture", tags=["studio-texture"])


class SpecErrorOut(BaseModel):
    path: str
    message: str


class TextureValidateRequest(BaseModel):
    spec: dict[str, Any]


class TextureValidateResponse(BaseModel):
    ok: bool
    errors: list[SpecErrorOut] = Field(default_factory=list)


@router.post("/validate", response_model=TextureValidateResponse)
def validate_texture(body: TextureValidateRequest) -> TextureValidateResponse:
    """Parse and validate one TextureSpec mapping without rendering it."""
    try:
        spec = parse_texture_spec(body.spec)
    except TextureSpecError as exc:
        return TextureValidateResponse(
            ok=False, errors=[SpecErrorOut(path=exc.path, message=exc.message)]
        )
    errors = [
        SpecErrorOut(path=error.path, message=error.message)
        for error in validate_texture_spec(spec)
    ]
    return TextureValidateResponse(ok=not errors, errors=errors)
