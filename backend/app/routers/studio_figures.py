"""Explicit Studio figure promote seam (Phase 4).

Prefix: ``/v1/studio/figure``. A Studio pattern draft owns a pool of tagged
figures (``TextureSpec`` plus a local ``cellId``, bar count, and role tags).
This router validates that pool against the pure Phase 4 helpers and offers an
**explicit**, opt-in promote step.

``POST /validate`` is pure: it parses every texture, runs the five-tag gate,
and returns the derived body sentence and the ``tag -> cellId`` projection. It
never mutates ``TEXTURE_CELLS``, ``SENTENCE_SPECS``, or ``STUDIO_DOORS``.

``POST /promote`` defaults to ``apply: false`` and therefore behaves exactly
like validate. Only an explicit ``apply: true`` registers cells, the body
sentence, and the compiled door. It never writes SQLite, publishes a version,
or renders audio.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.sonify.pattern_figures import (
    FIGURE_TAGS,
    REQUIRED_FIGURE_TAGS,
    PatternFigure,
    _TAG_BARS,
    derive_body_sentence,
    figure_tag_errors,
    missing_figure_tags,
    validate_figures,
)
from app.sonify.pattern_promote import (
    PromotionPlan,
    apply_promotion,
    promote_figures,
    register_body_sentence,
    unapply_promotion,
    unapply_promotion_by_key,
)
from app.sonify.pattern_registry import PATTERN_META
from app.sonify.sentence_specs import SENTENCE_SPECS
from app.studio import session as studio_session
from app.studio.sentence_spec import parse_spec, spec_to_mapping
from app.studio.texture_spec import (
    TextureSpec,
    TextureSpecError,
    parse_texture_spec,
    validate_texture_spec,
)

router = APIRouter(prefix="/v1/studio/figure", tags=["studio-figure"])

studio_owner = studio_session.owner_or_anonymous

_PROMOTE_ENV = "VSTOCK_STUDIO_FIGURE_PROMOTE"
_PROMOTE_TOKEN_ENV = "VSTOCK_STUDIO_FIGURE_PROMOTE_TOKEN"
_TRUE = frozenset({"1", "true", "yes", "on"})


def _promote_gate(
    owner_id: str,
    token: str | None,
) -> None:
    """Gate explicit registry mutation behind an off-by-default flag."""
    enabled = os.environ.get(_PROMOTE_ENV, "").strip().lower() in _TRUE
    if not enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "figure_promote_disabled",
                "message": f"set {_PROMOTE_ENV}=on to enable figure promotion",
            },
        )
    if owner_id == "anonymous":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "studio_session_required",
                "message": "X-Studio-Session is required for figure promotion",
            },
        )
    expected = os.environ.get(_PROMOTE_TOKEN_ENV, "").strip()
    if expected and token != expected:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "figure_promote_forbidden",
                "message": "invalid X-Studio-Promote-Token",
            },
        )

_MAX_FIGURES = 64
_MAX_SENTENCES = 64
_MAX_ID = 128
_MAX_TAG = 64


class FigureErrorOut(BaseModel):
    path: str
    message: str


class FigureRequest(BaseModel):
    """One draft figure from the Studio panel.

    ``cellId`` is optional for older drafts: a missing value falls back to the
    figure ``id``, matching the draft schema. The promote plan still treats the
    cell id as the registry key, never the figure id.
    """

    id: str = Field(min_length=1, max_length=_MAX_ID)
    cellId: str | None = Field(default=None, min_length=1, max_length=_MAX_ID)
    bars: int = Field(ge=1, le=256)
    tags: list[Annotated[str, Field(min_length=1, max_length=_MAX_TAG)]] = Field(
        default_factory=list, max_length=16
    )
    spec: Any = None


class FigureValidateRequest(BaseModel):
    pattern: str = Field(min_length=1, max_length=_MAX_ID)
    meter: str = Field(min_length=1, max_length=32)
    figures: list[FigureRequest] = Field(
        default_factory=list, max_length=_MAX_FIGURES
    )
    # Kept as ``Any`` so a non-object sentence is a path-shaped contract error
    # instead of a transport 422. The list itself stays bounded.
    sentences: list[Any] = Field(
        default_factory=list, max_length=_MAX_SENTENCES
    )


class FigurePromoteRequest(FigureValidateRequest):
    # Promotion is never implicit. A missing flag is a validate-only request.
    apply: bool = False


class FigureValidateResponse(BaseModel):
    ok: bool
    errors: list[FigureErrorOut] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    bodySentence: dict[str, Any] | None = None
    cellIds: dict[str, str] = Field(default_factory=dict)
    complete: bool = False


class FigurePromoteResponse(FigureValidateResponse):
    applied: bool = False
    removed: bool = False


class FigureUnpromoteRequest(BaseModel):
    pattern: str = Field(min_length=1, max_length=_MAX_ID)
    meter: str = Field(min_length=1, max_length=32)
    ensemble: str = Field(default="villa", min_length=1, max_length=32)


class FigureTagOut(BaseModel):
    name: str
    bars: int | None


class FigureTagsResponse(BaseModel):
    ok: bool = True
    tags: list[FigureTagOut] = Field(default_factory=list)


@dataclass
class _Evaluation:
    errors: list[FigureErrorOut]
    missing: list[str]
    body_sentence: dict[str, Any] | None
    cell_ids: dict[str, str]
    plan: PromotionPlan | None = None

    @property
    def complete(self) -> bool:
        return not self.errors and not self.missing and self.plan is not None

    def response(self) -> FigureValidateResponse:
        return FigureValidateResponse(
            ok=self.complete,
            errors=self.errors,
            missing=self.missing,
            bodySentence=self.body_sentence,
            cellIds=self.cell_ids,
            complete=self.complete,
        )


def _error(path: str, message: str) -> FigureErrorOut:
    return FigureErrorOut(path=path, message=message)


def _prefixed(prefix: str, path: str) -> str:
    """Turn ``spec.a`` into ``figures[0].spec.a`` without doubling ``spec``."""
    if not path or path == "spec":
        return prefix
    if path.startswith("spec."):
        return f"{prefix}{path[4:]}"
    return f"{prefix}.{path}"


def _texture_error(prefix: str, exc: TextureSpecError) -> FigureErrorOut:
    return _error(_prefixed(prefix, exc.path), exc.message)


def _parse_error(exc: Exception, default_path: str) -> FigureErrorOut:
    """Keep a parser's authored path; never expose the traceback."""
    path = getattr(exc, "path", None)
    message = getattr(exc, "message", None)
    if isinstance(path, str) and path:
        return _error(path, str(message or exc))
    text = str(exc)
    head, separator, tail = text.partition(": ")
    if separator and head and not head.startswith(" "):
        return _error(head, tail)
    return _error(default_path, text)


def _safe_promotion_error(exc: BaseException) -> str:
    """Only authored ``ValueError``/``TypeError`` text is safe to return."""
    if isinstance(exc, (ValueError, TypeError)) and str(exc):
        return str(exc)
    return "promotion could not be applied"


def _parse_sentences(
    raw_sentences: list[Any],
) -> tuple[list[Any], list[FigureErrorOut]]:
    """Parse SentenceSpec mappings, keeping errors path-shaped."""
    parsed: list[Any] = []
    errors: list[FigureErrorOut] = []
    for index, raw in enumerate(raw_sentences):
        path = f"sentences[{index}]"
        if not isinstance(raw, Mapping):
            errors.append(_error(path, "expected an object"))
            continue
        try:
            parsed.append(parse_spec(dict(raw), path=path))
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(_parse_error(exc, path))
    return parsed, errors


def _project_cell_ids(figures: list[PatternFigure]) -> dict[str, str]:
    """``tag -> cellId`` for every known tag in the pool."""
    cells: dict[str, str] = {}
    for figure in figures:
        for tag in figure.tags:
            if tag in FIGURE_TAGS:
                cells[tag] = figure.cell_id
    return cells


def _derive_body_mapping(
    pattern: str,
    meter: str,
    figures: list[PatternFigure],
    sentences: list[Any],
    errors: list[FigureErrorOut],
) -> dict[str, Any] | None:
    """Best-effort body projection even when later tags are still missing."""
    keys = [figure for figure in figures if "key" in figure.tags]
    if len(keys) != 1:
        return None
    try:
        body = derive_body_sentence(
            pattern, meter, keys[0], existing=sentences
        )
    except ValueError as exc:
        errors.append(_error("key", str(exc)))
        return None
    return spec_to_mapping(body)


def _evaluate(body: FigureValidateRequest) -> _Evaluation:
    errors: list[FigureErrorOut] = []
    sentences, sentence_errors = _parse_sentences(body.sentences)
    errors.extend(sentence_errors)
    if body.pattern in PATTERN_META:
        errors.append(
            _error(
                "pattern",
                f"{body.pattern!r} is a production pattern; Studio promotion "
                "cannot shadow it",
            )
        )
    existing_sentences = tuple(sentences) + tuple(
        SENTENCE_SPECS.get((body.pattern, body.meter), ())
    )

    figures: list[PatternFigure] = []
    pairs: list[tuple[PatternFigure, TextureSpec]] = []
    for index, raw in enumerate(body.figures):
        path = f"figures[{index}]"
        figure = PatternFigure(
            id=raw.id,
            cell_id=raw.cellId or raw.id,
            bars=raw.bars,
            tags=tuple(raw.tags),
        )
        figures.append(figure)

        try:
            texture = parse_texture_spec(raw.spec)
        except TextureSpecError as exc:
            errors.append(_texture_error(f"{path}.spec", exc))
            continue
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(_parse_error(exc, f"{path}.spec"))
            continue

        for texture_error in validate_texture_spec(texture):
            errors.append(
                _error(
                    _prefixed(f"{path}.spec", texture_error.path),
                    texture_error.message,
                )
            )
        pairs.append((figure, texture))

    for index, figure in enumerate(figures):
        for message in figure_tag_errors(figure.tags, figure.bars):
            tag_path = (
                f"figures[{index}].bars"
                if message.startswith("bars ")
                else f"figures[{index}].tags"
            )
            errors.append(_error(tag_path, message))

    # ``validate_figures`` repeats the per-figure checks above; only its
    # cross-figure ownership errors add information here.
    for message in validate_figures(figures):
        if "claimed by more than one figure" in message:
            errors.append(_error("figures", message))

    missing = list(missing_figure_tags(figures))
    cell_ids = _project_cell_ids(figures)
    body_sentence = _derive_body_mapping(
        body.pattern, body.meter, figures, existing_sentences, errors
    )

    if errors or missing:
        return _Evaluation(
            errors=errors,
            missing=missing,
            body_sentence=body_sentence,
            cell_ids=cell_ids,
        )

    try:
        plan = promote_figures(
            body.pattern,
            body.meter,
            pairs,
            existing_sentences=existing_sentences,
        )
    except ValueError as exc:
        message = str(exc)
        path = (
            "sentences"
            if "is a figure id" in message or "slot cell" in message
            else "figures"
        )
        errors.append(_error(path, message))
        return _Evaluation(
            errors=errors,
            missing=[],
            body_sentence=body_sentence,
            cell_ids=cell_ids,
        )

    return _Evaluation(
        errors=[],
        missing=[],
        body_sentence=spec_to_mapping(plan.body),
        cell_ids=dict(plan.cell_ids),
        plan=plan,
    )


@router.post("/validate", response_model=FigureValidateResponse)
def validate_figures_route(body: FigureValidateRequest) -> FigureValidateResponse:
    """Validate a tagged figure pool without touching any registry."""
    return _evaluate(body).response()


@router.post("/promote", response_model=FigurePromoteResponse)
def promote_figures_route(
    body: FigurePromoteRequest,
    owner_id: str = Depends(studio_owner),
    promote_token: str | None = Header(
        default=None, alias="X-Studio-Promote-Token"
    ),
) -> FigurePromoteResponse:
    """Validate first; register only when the caller explicitly sets ``apply``."""
    if body.apply:
        _promote_gate(owner_id, promote_token)
    evaluation = _evaluate(body)
    if not evaluation.complete or evaluation.plan is None:
        response = evaluation.response()
        return FigurePromoteResponse(
            **response.model_dump(), applied=False
        )

    if not body.apply:
        response = evaluation.response()
        return FigurePromoteResponse(
            **response.model_dump(), applied=False
        )

    plan = evaluation.plan
    applied = False
    try:
        apply_promotion(plan)
        applied = True
        register_body_sentence(plan)
    except Exception as exc:  # noqa: BLE001 - transport boundary
        # `apply_promotion` is atomic; only roll back when it completed and
        # the separate body registration failed.
        if applied:
            try:
                unapply_promotion(plan)
            except Exception:  # noqa: BLE001 - best-effort rollback
                pass
        response = evaluation.response()
        return FigurePromoteResponse(
            ok=False,
            applied=False,
            errors=[_error("apply", _safe_promotion_error(exc))],
            missing=response.missing,
            bodySentence=response.bodySentence,
            cellIds=response.cellIds,
            complete=response.complete,
        )

    return FigurePromoteResponse(
        ok=True,
        applied=True,
        errors=[],
        missing=[],
        bodySentence=evaluation.body_sentence,
        cellIds=dict(plan.cell_ids),
        complete=True,
    )


@router.post("/unpromote", response_model=FigurePromoteResponse)
def unpromote_figures_route(
    body: FigureUnpromoteRequest,
    owner_id: str = Depends(studio_owner),
    promote_token: str | None = Header(
        default=None, alias="X-Studio-Promote-Token"
    ),
) -> FigurePromoteResponse:
    """Revert the latest promotion by key, without the draft pool.

    Unpromote must work even when the Studio draft is incomplete or edited, so
    it only takes ``pattern``/``meter``/``ensemble``.
    """
    _promote_gate(owner_id, promote_token)
    try:
        removed = unapply_promotion_by_key(
            body.ensemble, body.pattern, body.meter
        )
    except Exception as exc:  # noqa: BLE001 - transport boundary
        return FigurePromoteResponse(
            ok=False,
            applied=False,
            removed=False,
            errors=[_error("unapply", _safe_promotion_error(exc))],
            complete=True,
        )
    return FigurePromoteResponse(
        ok=True,
        applied=False,
        removed=removed,
        errors=[],
        missing=[],
        bodySentence=None,
        cellIds={},
        complete=True,
    )


@router.get("/tags", response_model=FigureTagsResponse)
def figure_tags() -> FigureTagsResponse:
    """The five role tags and their required bar counts (``None`` = any)."""
    return FigureTagsResponse(
        tags=[
            FigureTagOut(
                name=tag,
                bars=_TAG_BARS.get(tag),
            )
            for tag in REQUIRED_FIGURE_TAGS
        ]
    )
