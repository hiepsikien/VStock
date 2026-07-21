"""LLM intent classifier for Companion watchlist mutations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.services import gemini_companion

logger = logging.getLogger(__name__)

IntentKind = Literal[
    "chat",
    "status_watchlist",
    "propose_change",
    "execute_add",
    "execute_remove",
    "execute_create",
]

EXECUTE_KINDS = frozenset({"execute_add", "execute_remove", "execute_create"})
NO_MUTATE_KINDS = frozenset({"chat", "status_watchlist", "propose_change"})

_INTENT_SYSTEM = """Bạn là bộ phân loại ý định watchlist cho app chứng khoán VStock.
Chỉ trả về JSON đúng schema. Không trả lời chat.

kind:
- chat: hỏi chuyện / giá / tin / tư vấn chung — KHÔNG thêm/xóa/tạo list.
- status_watchlist: hỏi trạng thái list ("xóa xong chưa?", "còn bao nhiêu mã?", "list còn gì?").
- propose_change: muốn cắt/gọn/thêm theo tiêu chí chung ("mã kém", "thêm vài mã ngân hàng", "tái cấu trúc") mà CHƯA chỉ rõ mã hoặc CHƯA xác nhận gợi ý trước — cần gợi ý trước, chưa mutate.
- execute_add: đã rõ muốn thêm mã cụ thể (hoặc đồng ý thêm mã vừa bàn).
- execute_remove: đã rõ muốn xóa mã cụ thể, hoặc xác nhận xóa gợi ý trước đó ("ok", "đồng ý", "xóa mấy mã đó").
- execute_create: muốn tạo danh sách/list mới.

symbols: mã 3 chữ cái user đã nêu hoặc đang xác nhận (viết HOA). Có thể [].
watchlist_hint: tên list nếu user nhắc.
notes: 1 câu ngắn gợi ý cho assistant (tiếng Việt).
confidence: 0..1.
"""


class WatchlistIntent(BaseModel):
    kind: IntentKind = "chat"
    symbols: list[str] = Field(default_factory=list)
    watchlist_hint: str | None = None
    notes: str | None = None
    confidence: float = 0.0
    source: str = "llm"  # llm | fallback


def _latest_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        role = (msg.get("role") or "user").lower()
        if role == "assistant":
            continue
        text = (msg.get("content") or msg.get("text") or "").strip()
        if text:
            return text
    return ""


def _recent_transcript(messages: list[dict], *, max_turns: int = 6) -> str:
    rows: list[str] = []
    for msg in messages[-max_turns:]:
        role = (msg.get("role") or "user").lower()
        if role in ("assistant", "model"):
            label = "assistant"
        else:
            label = "user"
        text = (msg.get("content") or msg.get("text") or "").strip()
        if text:
            rows.append(f"{label}: {text}")
    return "\n".join(rows)


def _watchlists_blurb(context: dict | None) -> str:
    if not isinstance(context, dict):
        return "(không có watchlist)"
    wl = context.get("watchlists")
    if not isinstance(wl, dict):
        return "(không có watchlist)"
    lists = wl.get("lists") or []
    active = wl.get("activeId")
    if not lists:
        return "(không có watchlist)"
    lines: list[str] = []
    for item in lists[:12]:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "Danh sách"
        wid = item.get("id")
        mark = " (đang mở)" if wid == active else ""
        syms = ", ".join(str(s).upper() for s in (item.get("symbols") or [])[:24])
        lines.append(f"- {name}{mark}: {syms or '(trống)'}")
    return "\n".join(lines) if lines else "(không có watchlist)"


def _normalize_symbols(raw: Any) -> list[str]:
    out: list[str] = []
    if isinstance(raw, str):
        parts = re.split(r"[,/\s|;]+", raw)
    elif isinstance(raw, list):
        parts = [str(x) for x in raw]
    else:
        parts = []
    for part in parts:
        sym = part.upper().strip()
        if len(sym) == 3 and sym.isalpha() and sym not in out:
            out.append(sym)
    return out[:12]


def _parse_intent_payload(data: dict[str, Any]) -> WatchlistIntent:
    kind_raw = str(data.get("kind") or "chat").strip().lower()
    allowed: set[str] = {
        "chat",
        "status_watchlist",
        "propose_change",
        "execute_add",
        "execute_remove",
        "execute_create",
    }
    kind: IntentKind = kind_raw if kind_raw in allowed else "chat"  # type: ignore[assignment]
    try:
        conf = float(data.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))
    hint = data.get("watchlist_hint")
    notes = data.get("notes")
    return WatchlistIntent(
        kind=kind,
        symbols=_normalize_symbols(data.get("symbols")),
        watchlist_hint=str(hint).strip() if hint else None,
        notes=str(notes).strip() if notes else None,
        confidence=conf,
        source="llm",
    )


def intent_allows_tools(intent: WatchlistIntent) -> bool:
    return intent.kind in EXECUTE_KINDS and intent.confidence >= 0.45


def intent_allows_actions(intent: WatchlistIntent) -> bool:
    return intent_allows_tools(intent)


def gate_actions_by_intent(
    actions: list[dict[str, Any]],
    intent: WatchlistIntent,
) -> list[dict[str, Any]]:
    """Keep only actions that match classified intent."""
    if not intent_allows_actions(intent):
        return []

    kind = intent.kind
    wanted_types: set[str]
    if kind == "execute_add":
        wanted_types = {"add_symbol", "suggest_add_symbol"}
    elif kind == "execute_remove":
        wanted_types = {"remove_symbol"}
    elif kind == "execute_create":
        wanted_types = {"create_watchlist"}
    else:
        return []

    filtered = [a for a in actions if a.get("type") in wanted_types]
    if intent.symbols and kind in ("execute_add", "execute_remove"):
        allow = {s.upper() for s in intent.symbols}
        filtered = [
            a
            for a in filtered
            if str(a.get("symbol") or "").upper() in allow
            or a.get("type") == "create_watchlist"
        ]
    return filtered


def inject_intent_into_context(
    context: dict | None,
    intent: WatchlistIntent,
) -> dict:
    ctx = dict(context or {})
    ctx["watchlistIntent"] = {
        "kind": intent.kind,
        "symbols": intent.symbols,
        "watchlistHint": intent.watchlist_hint,
        "notes": intent.notes,
        "confidence": intent.confidence,
        "source": intent.source,
    }
    return ctx


async def classify_watchlist_intent(
    messages: list[dict],
    context: dict | None = None,
) -> WatchlistIntent:
    """Classify latest user turn for watchlist mutation intent."""
    user = _latest_user_text(messages)
    if not user:
        return WatchlistIntent(kind="chat", confidence=1.0, source="fallback")

    prompt = (
        f"Watchlists hiện tại:\n{_watchlists_blurb(context)}\n\n"
        f"Hội thoại gần đây:\n{_recent_transcript(messages)}\n\n"
        f"Tin nhắn user mới nhất:\n{user}\n"
    )

    try:
        client = gemini_companion._client()
        config = types.GenerateContentConfig(
            system_instruction=_INTENT_SYSTEM,
            temperature=0.2,
            max_output_tokens=256,
            response_mime_type="application/json",
        )
        response = await client.aio.models.generate_content(
            model=gemini_companion._model_name(),
            contents=prompt,
            config=config,
        )
        raw = gemini_companion._text_from_response(response)
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            raise ValueError("intent payload is not an object")
        intent = _parse_intent_payload(data)
        if intent.confidence < 0.35:
            # Low confidence → safe chat (no mutate).
            return WatchlistIntent(
                kind="chat",
                symbols=intent.symbols,
                watchlist_hint=intent.watchlist_hint,
                notes=intent.notes,
                confidence=intent.confidence,
                source="llm",
            )
        return intent
    except Exception as exc:
        logger.warning("watchlist intent classify failed: %s", exc)
        return WatchlistIntent(
            kind="chat",
            confidence=0.0,
            source="fallback",
            notes="intent_classify_failed",
        )
