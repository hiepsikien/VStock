"""Studio validate/preview for an authored sentence spec.

No auth, database, queue, or publish here: this is the Phase 0/1 authoring
loop against the real renderers. The JSON parser is workstream A's
`app.studio.sentence_spec.parse_spec` directly.

Preview and validate both dispatch by the spec's pattern through
`app.studio.dispatch`: Torroba/Sor specs keep using `preview`, while the Villa
and Barrios candidate pilots use their own preview modules. Every family
answers with the same `PreviewResponse` shape, so the UI keeps posting to the
same URL. `GET /sentence/examples` serves the committed JSON so the UI does not
hand-copy it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_serializer

from app.studio import dispatch, examples
from app.studio.sentence_spec import parse_payload, parse_spec

router = APIRouter(prefix="/v1/studio", tags=["studio"])

_PARSE_ERRORS = (ValueError, KeyError, TypeError)


class SpecErrorOut(BaseModel):
    path: str
    message: str


def _parse_error(exc: Exception) -> SpecErrorOut:
    """Keep the authored path when the parser/model already carries one."""
    path = getattr(exc, "path", None)
    message = getattr(exc, "message", None)
    if isinstance(path, str) and path:
        return SpecErrorOut(path=path, message=str(message or exc))
    text = str(exc)
    # `parse_spec`/`_validate` may prefix the spec id before the authored path
    # (e.g. "castillo: slots[0].microVelocity.notes[0].bar: ..."). Find the
    # first path-shaped segment instead of splitting only at the first colon.
    for marker in ("spec.", "specs[", "slots[", "microVelocity."):
        index = text.find(marker)
        if index >= 0:
            path, separator, message = text[index:].partition(": ")
            if separator and path:
                return SpecErrorOut(path=path, message=message)
    head, separator, tail = text.partition(": ")
    if separator and (head == "spec" or head.startswith("spec.") or head.startswith("specs[")):
        return SpecErrorOut(path=head, message=tail)
    return SpecErrorOut(path="spec", message=text)


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
    # Authored slot contours keyed by slot index. Omitted from the JSON when
    # the spec has none, so existing response bodies are unchanged.
    microVelocity: list[dict[str, Any]] | None = None

    @model_serializer(mode="wrap")
    def _omit_empty_micro_velocity(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if isinstance(data, dict) and data.get("microVelocity") is None:
            data.pop("microVelocity", None)
        return data


class ExampleOut(BaseModel):
    pattern: str
    meter: str
    id: str
    payload: dict[str, Any]


class ExamplesResponse(BaseModel):
    ok: bool
    examples: list[ExampleOut] = Field(default_factory=list)
    errors: list[SpecErrorOut] = Field(default_factory=list)


@router.post("/sentence/validate", response_model=ValidateResponse)
def validate_sentence(body: dict[str, Any]) -> ValidateResponse:
    """Validate one spec mapping, or a v1 wrapper with several specs."""
    if "specs" in body:
        try:
            specs = parse_payload(body)
        except _PARSE_ERRORS as exc:
            return ValidateResponse(ok=False, errors=[_parse_error(exc)])
        errors: list[SpecErrorOut] = []
        for index, spec in enumerate(specs):
            for error in dispatch.validate(spec):
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
        return ValidateResponse(ok=False, errors=[_parse_error(exc)])
    errors = [
        SpecErrorOut(path=error.path, message=error.message)
        for error in dispatch.validate(spec)
    ]
    return ValidateResponse(ok=not errors, errors=errors)


@router.post("/sentence/preview", response_model=PreviewResponse)
def preview_sentence(body: PreviewRequest) -> PreviewResponse:
    """Validate and render one bounded fixture for an authored spec."""
    try:
        spec = parse_spec(body.spec)
    except _PARSE_ERRORS as exc:
        return PreviewResponse(ok=False, errors=[_parse_error(exc)])
    result = dispatch.preview_sentence(spec, body.fixture)
    return PreviewResponse(**result.as_response())


@router.get(
    "/sentence/examples",
    response_model=ExamplesResponse,
    response_model_exclude_defaults=True,
)
def list_sentence_examples() -> ExamplesResponse:
    """The committed Torroba/Sor, Villa, and Barrios example specs."""
    return ExamplesResponse(
        ok=True, examples=[item.as_response() for item in examples.examples()]
    )


@router.get(
    "/sentence/examples/{pattern}",
    response_model=ExamplesResponse,
    response_model_exclude_defaults=True,
)
def list_sentence_examples_for_pattern(pattern: str) -> ExamplesResponse:
    """The committed example specs for one pattern."""
    found = examples.examples_for(pattern)
    if not found:
        return ExamplesResponse(
            ok=False,
            errors=[
                SpecErrorOut(
                    path="pattern",
                    message=f"no committed example spec for pattern {pattern!r}",
                )
            ],
        )
    return ExamplesResponse(
        ok=True, examples=[item.as_response() for item in found]
    )
