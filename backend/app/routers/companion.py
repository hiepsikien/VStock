from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import companion as companion_service
from app.services.gemini_companion import is_gemini_configured, scrub_advice

router = APIRouter(prefix="/v1/companion", tags=["companion"])


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class CompanionContext(BaseModel):
    screen: str | None = None
    symbol: str | None = None
    sessionLabel: str | None = None
    watchlistSymbols: list[str] = Field(default_factory=list)
    avgChange: float | None = None
    recentEvents: list[dict[str, Any]] = Field(default_factory=list)
    bond: dict[str, Any] | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    context: CompanionContext | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    message: str


class NudgeRequest(BaseModel):
    context: CompanionContext | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    cooldownUntil: float | None = None


class NudgeResponse(BaseModel):
    show: bool
    message: str | None = None


class CompanionHealth(BaseModel):
    configured: bool
    provider: str = "gemini"


@router.get("/health", response_model=CompanionHealth)
async def companion_health() -> CompanionHealth:
    return CompanionHealth(configured=is_gemini_configured())


@router.post("/chat")
async def companion_chat(body: ChatRequest, request: Request):
    client = request.client.host if request.client else "anon"
    if not companion_service.check_rate_limit(client):
        raise HTTPException(status_code=429, detail="Too many companion requests")

    messages = [m.model_dump() for m in body.messages]
    context = body.context.model_dump() if body.context else None

    if not body.stream:
        try:
            text = await companion_service.chat_once(messages, context)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Companion unavailable: {exc}") from exc
        return ChatResponse(message=text)

    async def event_gen():
        buffered = ""
        try:
            async for piece in companion_service.chat_stream(messages, context):
                buffered += piece
                yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
            final = scrub_advice(buffered) or buffered
            if final != buffered:
                # Replace stream with scrubbed refusal.
                yield f"data: {json.dumps({'replace': final}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except RuntimeError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'Companion unavailable: {exc}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/nudge", response_model=NudgeResponse)
async def companion_nudge(body: NudgeRequest, request: Request) -> NudgeResponse:
    client = request.client.host if request.client else "anon"
    if not companion_service.check_rate_limit(f"nudge:{client}"):
        raise HTTPException(status_code=429, detail="Too many companion requests")

    context = body.context.model_dump() if body.context else None
    try:
        result = await companion_service.build_nudge(
            context,
            body.events,
            cooldown_until=body.cooldownUntil,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Companion unavailable: {exc}") from exc
    return NudgeResponse(**result)
