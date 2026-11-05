"""Studio sentence audio preview (synthesized, not MuseScore).

Separate from `app.routers.studio` so the authoring endpoints and the audio
cache stay independent. The POST validates and previews the spec through the
same module as `/v1/studio/sentence/preview`, then synthesizes or reuses one
short WAV. The GET only serves names that match the cache's key format, so no
request can address an arbitrary path.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.studio import audio as studio_audio
from app.studio.sentence_spec import parse_spec

router = APIRouter(prefix="/v1/studio", tags=["studio"])

_PARSE_ERRORS = (ValueError, KeyError, TypeError)


class SpecErrorOut(BaseModel):
    path: str
    message: str


class AudioRequest(BaseModel):
    spec: dict[str, Any] | None = None
    fixture: dict[str, Any] = Field(default_factory=dict)
    renderHash: str | None = None


class AudioResponse(BaseModel):
    ok: bool
    errors: list[SpecErrorOut] = Field(default_factory=list)
    audioUrl: str | None = None
    durationSec: float = 0.0
    renderHash: str | None = None


def _response(result: studio_audio.AudioResult) -> AudioResponse:
    asset = result.asset
    return AudioResponse(
        ok=result.ok,
        errors=[
            SpecErrorOut(path=path, message=message) for path, message in result.errors
        ],
        audioUrl=asset.audio_url if asset is not None else None,
        durationSec=asset.duration_sec if asset is not None else 0.0,
        renderHash=result.render_hash,
    )


@router.post("/sentence/audio", response_model=AudioResponse)
def sentence_audio(body: AudioRequest) -> AudioResponse:
    """Synthesize (or reuse) a short WAV for one preview fixture."""
    if body.spec is not None:
        try:
            spec = parse_spec(body.spec)
        except _PARSE_ERRORS as exc:
            return AudioResponse(
                ok=False,
                errors=[SpecErrorOut(path="spec", message=str(exc))],
            )
        return _response(studio_audio.preview_audio(spec, body.fixture))
    if body.renderHash is not None:
        return _response(studio_audio.audio_for_hash(body.renderHash))
    return AudioResponse(
        ok=False,
        errors=[
            SpecErrorOut(
                path="spec",
                message="send spec and fixture, or the renderHash of a cached preview",
            )
        ],
    )


@router.get("/sentence/audio/{filename}")
def get_sentence_audio(filename: str) -> FileResponse:
    """Serve one cached preview WAV by its key name."""
    path = studio_audio.audio_path(filename)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="No such preview audio")
    return FileResponse(path, media_type="audio/wav", filename=filename)
