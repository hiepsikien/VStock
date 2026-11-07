"""Studio Render Piece API: MusicXML plus production audio jobs.

Prefix: ``/v1/studio/figure``. ``POST /render`` validates a tagged figure pool,
resolves a form from a 1D bar series, renders through the ``studio_piece``
seam, stores the MusicXML, and enqueues a production WAV export.

``GET /render/{renderHash}.musicxml`` serves the score and
``GET /render/{audioHash}.wav`` serves the finished WAV. ``POST .../audio`` is
the explicit retry/export endpoint and ``GET .../audio/{jobId}`` is the poll.
These routes never call the 45-second sentence preview. No request mutates
``TEXTURE_CELLS``, ``SENTENCE_SPECS`` or ``STUDIO_DOORS``.
"""

from __future__ import annotations

import math
from typing import Annotated, Any

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.sonify.model import Bar
from app.sonify.pattern_figures import PatternFigure
from app.studio import (
    render_audio,
    render_jobs,
    render_store,
    session as studio_session,
)
from app.studio.render_piece import (
    RenderPieceError,
    RenderPieceRequest,
    RenderPieceResult,
    render_piece,
)
from app.studio.texture_spec import (
    TextureSpecError,
    parse_texture_spec,
)

router = APIRouter(prefix="/v1/studio/figure", tags=["studio-figure-render"])

studio_owner = studio_session.owner_or_anonymous

_RENDER_AUDIO_ENV = "VSTOCK_STUDIO_RENDER_AUDIO"
_RENDER_AUDIO_TOKEN_ENV = "VSTOCK_STUDIO_RENDER_AUDIO_TOKEN"
_TRUE = frozenset({"1", "true", "yes", "on"})


def _audio_gate(token: str | None) -> bool:
    """Production audio is gated; MusicXML always remains available."""
    if os.environ.get(_RENDER_AUDIO_ENV, "on").strip().lower() not in _TRUE:
        return False
    expected = os.environ.get(_RENDER_AUDIO_TOKEN_ENV, "").strip()
    return not expected or token == expected

_MAX_FIGURES = 64
_MAX_BARS = 2048
_MAX_ID = 128
_MAX_TAG = 64
_MAX_WARNINGS = 32
_MAX_ERRORS = 32


class RenderErrorOut(BaseModel):
    path: str
    message: str


class RenderFigureIn(BaseModel):
    id: str = Field(min_length=1, max_length=_MAX_ID)
    cellId: str | None = Field(default=None, min_length=1, max_length=_MAX_ID)
    bars: int = Field(ge=1, le=256)
    tags: list[Annotated[str, Field(min_length=1, max_length=_MAX_TAG)]] = Field(
        default_factory=list, max_length=16
    )
    spec: Any = None


class RenderPlanIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    sentenceByRole: dict[str, str] | None = None


class RenderBarIn(BaseModel):
    close: float
    volume: float = 0.0


class RenderSeriesIn(BaseModel):
    kind: str | None = Field(default="bars", max_length=32)
    bars: list[RenderBarIn] = Field(
        default_factory=list, max_length=_MAX_BARS
    )


class RenderFormIn(BaseModel):
    span: str = Field(default="1W", min_length=1, max_length=8)
    movementIndex: int | None = Field(default=None, ge=0, le=3)


class RenderOptionsIn(BaseModel):
    includeDoors: bool = True
    audio: bool = True


class RenderRequestIn(BaseModel):
    pattern: str = Field(min_length=1, max_length=_MAX_ID)
    meter: str = Field(min_length=1, max_length=32)
    figures: list[RenderFigureIn] = Field(
        default_factory=list, max_length=_MAX_FIGURES
    )
    plan: str | RenderPlanIn = "auto_aaba"
    series: RenderSeriesIn = Field(default_factory=RenderSeriesIn)
    form: RenderFormIn = Field(default_factory=RenderFormIn)
    title: str | None = Field(default=None, max_length=200)
    options: RenderOptionsIn = Field(default_factory=RenderOptionsIn)


class RenderAudioErrorOut(BaseModel):
    path: str = "audio"
    code: str
    message: str


class RenderAudioOut(BaseModel):
    status: str = "unavailable"
    jobId: str | None = None
    audioUrl: str | None = None
    audioHash: str | None = None
    errors: list[RenderAudioErrorOut] = Field(default_factory=list)
    retryAfter: int | None = None


class RenderResponse(BaseModel):
    ok: bool
    renderHash: str | None = None
    musicxmlUrl: str | None = None
    meter: str | None = None
    bars: int = 0
    notes: int = 0
    plan: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[RenderErrorOut] = Field(default_factory=list)
    audio: RenderAudioOut = Field(default_factory=RenderAudioOut)


class RenderAudioSubmitResponse(BaseModel):
    ok: bool = True
    renderHash: str
    jobId: str
    status: str


class RenderAudioJobResponse(BaseModel):
    ok: bool = True
    renderHash: str
    jobId: str
    status: str
    audioUrl: str | None = None
    audioHash: str | None = None
    durationSec: float = 0.0
    errors: list[RenderAudioErrorOut] = Field(default_factory=list)
    retryAfter: int | None = None


def _error(path: str, message: str) -> RenderErrorOut:
    return RenderErrorOut(path=path, message=message)


def _prefixed(prefix: str, path: str) -> str:
    if not path or path == "spec":
        return prefix
    if path.startswith("spec."):
        return f"{prefix}{path[4:]}"
    return f"{prefix}.{path}"


def _parse_error(exc: Exception, default_path: str) -> RenderErrorOut:
    path = getattr(exc, "path", None)
    message = getattr(exc, "message", None)
    if isinstance(path, str) and path:
        return _error(path, str(message or exc))
    text = str(exc)
    head, separator, tail = text.partition(": ")
    if separator and head and not head.startswith(" "):
        return _error(head, tail)
    return _error(default_path, text)


def _plan_id(plan: str | RenderPlanIn) -> str:
    return plan if isinstance(plan, str) else plan.id


def _parse_figures(
    figures: list[RenderFigureIn],
) -> tuple[list[tuple[PatternFigure, Any]], list[RenderErrorOut]]:
    pairs: list[tuple[PatternFigure, Any]] = []
    errors: list[RenderErrorOut] = []
    for index, raw in enumerate(figures):
        path = f"figures[{index}]"
        figure = PatternFigure(
            id=raw.id,
            cell_id=raw.cellId or raw.id,
            bars=raw.bars,
            tags=tuple(raw.tags),
        )
        if raw.spec is None:
            errors.append(_error(f"{path}.spec", "expected a TextureSpec object"))
            continue
        try:
            texture = parse_texture_spec(raw.spec)
        except TextureSpecError as exc:
            errors.append(
                _error(_prefixed(f"{path}.spec", exc.path), exc.message)
            )
            continue
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(_parse_error(exc, f"{path}.spec"))
            continue
        pairs.append((figure, texture))
    return pairs, errors


def _bars(series: RenderSeriesIn) -> tuple[list[Bar], list[RenderErrorOut]]:
    errors: list[RenderErrorOut] = []
    bars: list[Bar] = []
    for index, raw in enumerate(series.bars):
        if not math.isfinite(float(raw.close)):
            errors.append(
                _error(f"series.bars[{index}].close", "close must be finite")
            )
            continue
        if not math.isfinite(float(raw.volume)) or float(raw.volume) < 0:
            errors.append(
                _error(
                    f"series.bars[{index}].volume",
                    "volume must be a finite number >= 0",
                )
            )
            continue
        bars.append(Bar(close=float(raw.close), volume=float(raw.volume)))
    return bars, errors


def _audio_out(
    result: RenderPieceResult,
    owner_id: str,
) -> RenderAudioOut:
    """Report cached audio or enqueue one job; never block on MuseScore."""
    if result.audio_status == "ready" and result.audio_url:
        return RenderAudioOut(
            status="ready",
            audioUrl=result.audio_url,
            audioHash=result.audio_hash,
        )
    try:
        job = render_jobs.get_registry().submit(
            result.render_hash, owner_id=owner_id
        )
    except render_jobs.AudioJobQueueFull as exc:
        return RenderAudioOut(
            status="unavailable",
            errors=[
                RenderAudioErrorOut(
                    path="audio",
                    code="audio_rate_limited",
                    message=str(exc),
                )
            ],
            retryAfter=exc.retry_after,
        )
    except ValueError as exc:
        return RenderAudioOut(
            status="unavailable",
            errors=[
                RenderAudioErrorOut(
                    path="audio",
                    code="audio_failed",
                    message=str(exc),
                )
            ],
        )

    if job.status == render_jobs.READY:
        return RenderAudioOut(
            status="ready",
            jobId=job.id,
            audioUrl=job.audio_url,
            audioHash=job.audio_hash,
        )
    if job.status == render_jobs.FAILED:
        return RenderAudioOut(
            status="unavailable",
            jobId=job.id,
            errors=[
                RenderAudioErrorOut(
                    path=item.get("path", "audio"),
                    code=item.get("code", "audio_failed"),
                    message=item.get("message", "audio export failed"),
                )
                for item in job.errors[:_MAX_ERRORS]
            ],
        )
    return RenderAudioOut(status="queued", jobId=job.id)


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": code, "message": message}
    )


@router.post("/render", response_model=RenderResponse)
def render_piece_route(
    body: RenderRequestIn,
    owner_id: str = Depends(studio_owner),
    render_token: str | None = Header(
        default=None, alias="X-Studio-Render-Token"
    ),
) -> RenderResponse:
    """Render one Studio Piece to MusicXML; never publishes or mutates registries."""
    pairs, errors = _parse_figures(body.figures)
    bars, bar_errors = _bars(body.series)
    errors.extend(bar_errors)
    if errors:
        return RenderResponse(ok=False, errors=errors)

    plan_id = _plan_id(body.plan)
    if isinstance(body.plan, RenderPlanIn) and body.plan.sentenceByRole:
        return RenderResponse(
            ok=False,
            errors=[
                _error(
                    "plan.sentenceByRole",
                    "sentenceByRole is not implemented for Render Piece; "
                    "tag contrast/close instead",
                )
            ],
        )
    if body.series.kind not in (None, "bars"):
        return RenderResponse(
            ok=False,
            errors=[
                _error(
                    "series.kind",
                    "only series.kind='bars' is implemented; send resolved bars",
                )
            ],
        )
    request = RenderPieceRequest(
        pattern=body.pattern,
        meter=body.meter,
        figures=tuple(pairs),
        plan=plan_id,
        bars=tuple(bars),
        span=body.form.span,
        movement_index=body.form.movementIndex,
        title=body.title,
        include_doors=body.options.includeDoors,
        session=owner_id,
    )
    try:
        result = render_piece(request)
    except RenderPieceError as exc:
        return RenderResponse(
            ok=False,
            errors=[
                RenderErrorOut(path=item.path, message=item.message)
                for item in exc.errors
            ],
        )
    except (ValueError, TypeError, OSError) as exc:
        return RenderResponse(
            ok=False,
            errors=[_error("render", str(exc))],
        )

    audio_enabled = body.options.audio and _audio_gate(render_token)
    audio_out = (
        _audio_out(result, owner_id)
        if audio_enabled
        else RenderAudioOut(status="unavailable")
    )
    warnings = list(result.warnings[:_MAX_WARNINGS])
    if not body.options.audio:
        warnings.append("audio disabled by request")
    elif not audio_enabled:
        warnings.append("production audio is disabled by server gate")
    return RenderResponse(
        ok=True,
        renderHash=result.render_hash,
        musicxmlUrl=result.musicxml_url,
        meter=result.meter,
        bars=result.bars,
        notes=result.notes,
        plan=result.plan,
        warnings=warnings,
        audio=audio_out,
    )


@router.get("/render/{hash_value}.musicxml")
def get_render_musicxml(hash_value: str) -> FileResponse:
    """Serve one cached score. Only a 64-hex render hash can become a path."""
    path = render_store.musicxml_path(hash_value)
    if path is None or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "render_not_found",
                "message": "no cached MusicXML for that renderHash",
            },
        )
    return FileResponse(
        path,
        media_type="application/vnd.recordare.musicxml+xml",
        filename=f"{render_store.normalize_hash(hash_value)}.musicxml",
    )


def _normalized_or_404(value: str, code: str) -> str:
    digest = render_store.normalize_hash(value)
    if digest is None:
        raise _not_found(code, "hash must be 64 lowercase hex characters")
    return digest


@router.post(
    "/render/{hash_value}/audio",
    response_model=RenderAudioSubmitResponse,
    status_code=202,
)
def post_render_audio(
    hash_value: str,
    owner_id: str = Depends(studio_owner),
    render_token: str | None = Header(
        default=None, alias="X-Studio-Render-Token"
    ),
) -> RenderAudioSubmitResponse:
    """Queue one production WAV export; a cached/queued hash is deduplicated."""
    if not _audio_gate(render_token):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "figure_audio_disabled",
                "message": "production audio is disabled by server gate",
            },
        )
    digest = _normalized_or_404(hash_value, "render_not_found")
    render = render_store.load_render(digest)
    if render is None:
        raise _not_found(
            "render_not_found", "no cached MusicXML for that renderHash"
        )
    try:
        job = render_jobs.get_registry().submit(
            render.render_hash, owner_id=owner_id
        )
    except render_jobs.AudioJobQueueFull as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "audio_rate_limited",
                "message": str(exc),
                "retryAfter": exc.retry_after,
            },
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    return RenderAudioSubmitResponse(
        renderHash=render.render_hash,
        jobId=job.id,
        status=job.status,
    )


@router.get(
    "/render/{hash_value}/audio/{job_id}",
    response_model=RenderAudioJobResponse,
)
def get_render_audio_job(
    hash_value: str,
    job_id: str,
    owner_id: str = Depends(studio_owner),
) -> RenderAudioJobResponse:
    """Poll one audio job. A missing/foreign job id is a 404."""
    digest = _normalized_or_404(hash_value, "render_not_found")
    status = render_jobs.get_registry().get(job_id, owner_id=owner_id)
    if status is None:
        raise _not_found("audio_job_not_found", "no Studio audio job with that id")
    if render_store.normalize_hash(status.render_hash) != digest:
        raise _not_found(
            "audio_job_not_found", "job does not belong to that renderHash"
        )
    return RenderAudioJobResponse(
        renderHash=status.render_hash,
        jobId=status.id,
        status=status.status,
        audioUrl=status.audio_url,
        audioHash=status.audio_hash,
        durationSec=status.duration_sec,
        errors=[
            RenderAudioErrorOut(
                path=item.get("path", "audio"),
                code=item.get("code", "audio_failed"),
                message=item.get("message", "audio export failed"),
            )
            for item in status.errors[:_MAX_ERRORS]
        ],
    )


@router.get("/render/{hash_value}.wav")
def get_render_audio(hash_value: str) -> FileResponse:
    """Serve one production WAV. Only an ``audioHash`` can become a path."""
    path = render_audio.audio_path(hash_value)
    if path is None or not path.is_file():
        raise _not_found(
            "audio_not_found", "no cached WAV for that audioHash"
        )
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"{render_store.normalize_hash(hash_value)}.wav",
    )
