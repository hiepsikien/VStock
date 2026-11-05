"""Gemini vision draft for a photographed score page.

This module owns the prompt, the JSON schema, response parsing, and the cache.
It reuses ``app.services.gemini_companion`` for the API key, client, and model
name — there is no second key path.

Hard rules:

* No fake draft. If Gemini is not configured, the result is ``ok=False`` with
  ``error.code == "gemini_unconfigured"``; the UI must fall back to manual entry.
* A ``SAFETY`` / ``RECITATION`` / ``PROHIBITED_CONTENT`` finish or a prompt block
  is an error with its own code. There is no blind retry: one call per request.
* Only successful drafts are cached, keyed by
  ``sha256(image) + crop + model + prompt_version + schema_version``.
* Gemini drafts are ``review="pending"``; a human must accept or edit them
  before publish (§9.5 / acceptance criterion 20).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.genai import types

from app.services import gemini_companion
from app.studio.store import detect_image_mime, studio_root

PROMPT_VERSION = "studio-v1"
SCHEMA_VERSION = "studio-v1"
MAX_OUTPUT_TOKENS = 8192
_BLOCKED_FINISHES = {
    "SAFETY",
    "RECITATION",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
}

SYSTEM_INSTRUCTION = """You transcribe classical guitar notation from a photograph.
Return only JSON that follows the requested schema. Do not invent notes that are
not visible; when unsure, lower `confidence` and add a `warnings` entry.

Rules:
- Guitar music is written one octave above sounding pitch. For every note report
  both `written_pitch` and `sounding_pitch` (scientific pitch notation, e.g. E4/E3).
- `beat` is 0-based within the measure; `duration_beats` is in quarter-note beats.
- `measure` is 1-based.
- Include `string`/`fret` only when the tablature or fingering is visible.
- Mark `conflict=true` when the staff and tab disagree.
- Never choose voices, routing, dynamics, micro-timing, or pattern structure on
  behalf of the app; only transcribe what is visible.
- Use `warnings` for unreadable systems, missing clef/key, cut-off measures, and
  any assumption you had to make.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "measures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "meter": {"type": "string"},
                    "key": {"type": "string"},
                },
                "required": ["index"],
            },
        },
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "measure": {"type": "integer"},
                    "beat": {"type": "number"},
                    "duration_beats": {"type": "number"},
                    "voice_hint": {"type": "string"},
                    "written_pitch": {"type": "string"},
                    "sounding_pitch": {"type": "string"},
                    "string": {"type": "integer"},
                    "fret": {"type": "integer"},
                    "tie": {"type": "string"},
                    "slur": {"type": "boolean"},
                    "articulation": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "confidence": {"type": "number"},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "number"},
                    },
                    "conflict": {"type": "boolean"},
                },
                "required": [
                    "measure",
                    "beat",
                    "duration_beats",
                    "written_pitch",
                    "sounding_pitch",
                    "confidence",
                ],
            },
        },
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["measures", "notes"],
}


@dataclass(frozen=True)
class AnalysisResult:
    ok: bool
    cache_key: str
    draft: dict[str, Any] | None = None
    cache_hit: bool = False
    model: str | None = None
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION
    error_code: str | None = None
    error_message: str | None = None

    @property
    def error(self) -> dict[str, str] | None:
        if self.error_code is None:
            return None
        return {"code": self.error_code, "message": self.error_message or ""}


class _VisionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# cache


DEFAULT_CACHE_MAX_AGE_DAYS = 30


def cache_max_age_days() -> int:
    raw = os.environ.get("VSTOCK_STUDIO_VISION_CACHE_DAYS", "").strip()
    try:
        return max(1, int(raw)) if raw else DEFAULT_CACHE_MAX_AGE_DAYS
    except ValueError:
        return DEFAULT_CACHE_MAX_AGE_DAYS


def _prune_cache(path: Path) -> None:
    """Drop old drafts/temp files; the cache is disposable and must stay bounded."""
    cutoff = time.time() - cache_max_age_days() * 86400
    try:
        children = list(path.iterdir())
    except OSError:
        return
    for child in children:
        try:
            if not child.is_file() or child.stat().st_mtime >= cutoff:
                continue
            child.unlink()
        except OSError:
            continue


def cache_dir() -> Path:
    path = studio_root() / "vision-cache"
    path.mkdir(parents=True, exist_ok=True)
    _prune_cache(path)
    return path


def canonical_crop(crop: Any) -> Any:
    """Normalize crop for hashing: dicts sort keys, numbers stay numbers."""
    if crop is None:
        return None
    return json.loads(json.dumps(crop, sort_keys=True, separators=(",", ":")))


def cache_key(
    sha256: str,
    crop: Any,
    model: str,
    prompt_version: str = PROMPT_VERSION,
    schema_version: str = SCHEMA_VERSION,
) -> str:
    payload = {
        "sha256": sha256,
        "crop": canonical_crop(crop),
        "model": model,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _read_cache(key: str) -> dict[str, Any] | None:
    path = cache_dir() / f"{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_cache(key: str, draft: dict[str, Any]) -> None:
    target = cache_dir() / f"{key}.json"
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)


# ---------------------------------------------------------------------------
# Gemini


def _build_contents(
    data: bytes,
    mime: str,
    crop: Any,
    metadata: dict[str, Any] | None,
) -> list[types.Content]:
    context = {
        "crop": canonical_crop(crop),
        "metadata": metadata or {},
    }
    prompt = (
        "Transcribe this guitar score image into the JSON schema.\n"
        "Request context (crop rectangle in source pixels, and known metadata):\n"
        f"{json.dumps(context, ensure_ascii=False, sort_keys=True)}\n"
        "If a crop is present, transcribe only inside that rectangle."
    )
    return [
        types.Content(
            role="user",
            parts=[
                types.Part.from_bytes(data=data, mime_type=mime),
                types.Part(text=prompt),
            ],
        )
    ]


async def _call_gemini(
    data: bytes,
    mime: str,
    crop: Any,
    metadata: dict[str, Any] | None,
    *,
    model: str,
    client: Any | None = None,
) -> Any:
    """One Gemini call. Kept as a seam so tests never touch the network."""
    active = client if client is not None else gemini_companion._client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=RESPONSE_SCHEMA,
        temperature=0.1,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    return await active.aio.models.generate_content(
        model=model,
        contents=_build_contents(data, mime, crop, metadata),
        config=config,
    )


def _enum_name(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    text = str(value)
    return text.rsplit(".", 1)[-1] if text else None


def _blocked_reason(response: Any) -> str | None:
    feedback = getattr(response, "prompt_feedback", None)
    blocked = _enum_name(getattr(feedback, "block_reason", None))
    if blocked and blocked not in {"BLOCK_REASON_UNSPECIFIED"}:
        return blocked
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    finish = _enum_name(getattr(candidates[0], "finish_reason", None))
    if finish in _BLOCKED_FINISHES:
        return finish
    return None


def _response_text(response: Any) -> str:
    chunks: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                chunks.append(text)
    text = "".join(chunks).strip()
    if not text:
        text = (getattr(response, "text", None) or "").strip()
    return text


def _strip_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_draft(payload: dict[str, Any]) -> dict[str, Any]:
    measures = payload.get("measures")
    notes = payload.get("notes")
    warnings = payload.get("warnings") or []
    if not isinstance(measures, list) or not isinstance(notes, list):
        raise _VisionError(
            "gemini_bad_json",
            "Gemini response is not the expected {measures, notes} shape",
        )
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    clean_measures = [item for item in measures if isinstance(item, dict)]
    clean_notes: list[dict[str, Any]] = []
    for item in notes:
        if not isinstance(item, dict):
            continue
        note = dict(item)
        confidence = max(0.0, min(1.0, _numeric(note.get("confidence"), 0.0)))
        note["confidence"] = confidence
        clean_notes.append(note)
    return {
        "measures": clean_measures,
        "notes": clean_notes,
        "warnings": [str(item) for item in warnings],
        # §9.5: Gemini drafts are pending until a human accepts or edits them.
        "review": "pending",
        "source": "gemini",
    }


def _parse_response(response: Any) -> dict[str, Any]:
    blocked = _blocked_reason(response)
    if blocked:
        raise _VisionError(
            "gemini_blocked", f"Gemini blocked the response ({blocked})"
        )
    candidates = getattr(response, "candidates", None) or []
    finish = (
        _enum_name(getattr(candidates[0], "finish_reason", None))
        if candidates
        else None
    )
    if finish == "MAX_TOKENS":
        raise _VisionError(
            "gemini_incomplete", "Gemini stopped at the token limit"
        )

    parsed = getattr(response, "parsed", None)
    payload: Any = parsed if isinstance(parsed, dict) else None
    if payload is None:
        text = _strip_fence(_response_text(response))
        if not text:
            raise _VisionError("gemini_empty", "Gemini returned no text")
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise _VisionError(
                "gemini_bad_json", "Gemini did not return valid JSON"
            ) from exc
    if not isinstance(payload, dict):
        raise _VisionError(
            "gemini_bad_json", "Gemini response is not a JSON object"
        )
    return _normalize_draft(payload)


async def analyze_image(
    path: str | Path,
    crop: Any = None,
    metadata: dict[str, Any] | None = None,
    *,
    client: Any | None = None,
    use_cache: bool = True,
) -> AnalysisResult:
    """Transcribe one stored image into a pending Studio draft."""
    model = gemini_companion._model_name()
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        return AnalysisResult(
            ok=False,
            cache_key="",
            model=model,
            error_code="image_unreadable",
            error_message=str(exc),
        )

    digest = hashlib.sha256(data).hexdigest()
    key = cache_key(digest, crop, model)
    if use_cache:
        cached = _read_cache(key)
        if cached is not None:
            return AnalysisResult(
                ok=True, cache_key=key, draft=cached, cache_hit=True, model=model
            )

    if client is None and not gemini_companion.is_gemini_configured():
        return AnalysisResult(
            ok=False,
            cache_key=key,
            model=model,
            error_code="gemini_unconfigured",
            error_message=(
                "Gemini is not configured on the backend; set GEMINI_API_KEY "
                "(or GCP_PROJECT for Vertex) and enter notes manually for now."
            ),
        )

    mime = detect_image_mime(data) or "image/jpeg"
    try:
        response = await _call_gemini(
            data,
            mime,
            crop,
            metadata,
            model=model,
            client=client,
        )
        draft = _parse_response(response)
    except _VisionError as exc:
        return AnalysisResult(
            ok=False,
            cache_key=key,
            model=model,
            error_code=exc.code,
            error_message=exc.message,
        )
    except Exception as exc:  # Gemini transport/API failures
        return AnalysisResult(
            ok=False,
            cache_key=key,
            model=model,
            error_code="gemini_unavailable",
            error_message=str(exc) or exc.__class__.__name__,
        )

    if use_cache:
        _write_cache(key, draft)
    return AnalysisResult(
        ok=True, cache_key=key, draft=draft, cache_hit=False, model=model
    )
