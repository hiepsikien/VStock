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
- chat: hỏi chuyện / giá / tin / định giá / KQKD / tư vấn chung / diễn biến phiên — KHÔNG thêm/xóa/tạo list.
- status_watchlist: CHỈ hỏi membership/completion của list ("xóa xong chưa?", "còn bao nhiêu mã?", "list còn gì?", "đã gỡ chưa?"). KHÔNG dùng cho câu hỏi hiệu suất phiên.
- propose_change: muốn cắt/gọn/thêm theo tiêu chí chung ("mã kém", "thêm vài mã ngân hàng", "tái cấu trúc") mà CHƯA chỉ rõ mã hoặc CHƯA xác nhận gợi ý trước — cần gợi ý trước, chưa mutate.
- execute_add: đã rõ muốn thêm mã cụ thể (hoặc đồng ý thêm mã vừa bàn).
- execute_remove: đã rõ muốn xóa mã cụ thể, hoặc xác nhận xóa/gỡ/cắt gợi ý trước đó.
- execute_create: muốn tạo danh sách/list mới.

QUAN TRỌNG — hiệu suất ≠ status:
- "watchlist hôm nay thế nào?", "list biến động ra sao?", "mã nào mạnh/yếu?", "list của mình thế nào hôm nay?" → kind=chat (cần đọc giá/%), KHÔNG phải status_watchlist.
- status_watchlist chỉ khi user hỏi còn mã gì / đã xóa chưa / đếm số mã.

QUAN TRỌNG — xác nhận sau gợi ý:
- Nếu assistant vừa gợi ý vài mã để XÓA/CẮT/GỠ, và user trả lời ngắn kiểu "đồng ý", "ok", "oke", "được", "ừ", "xóa đi", "làm đi", "xóa mấy mã đó" → kind=execute_remove.
- Điền symbols = các mã 3 chữ cái mà assistant vừa nêu (có trong watchlist). Không để symbols rỗng trong trường hợp này.
- Tương tự với gợi ý THÊM → execute_add + symbols.

symbols: mã 3 chữ cái user đã nêu hoặc đang xác nhận từ gợi ý trước (viết HOA).
watchlist_hint: tên list nếu user nhắc.
notes: 1 câu ngắn gợi ý cho assistant (tiếng Việt).
confidence: 0..1.
"""

_CONFIRM_RE = re.compile(
    r"\b(đồng\s*ý|ok|oke|okay|ừ+|được|xác\s*nhận|làm\s*đi|xóa\s*đi|gỡ\s*đi|"
    r"bỏ\s*đi|cứ\s*xóa|xóa\s*hết|agree|yes)\b",
    re.I,
)

_STATUS_RE = re.compile(
    r"(x[oó]a\s*xong|đã\s*x[oó]a|x[oó]a\s*chưa|hoàn\s*thành.{0,24}x[oó]a|"
    r"xong\s*chưa|còn\s*(bao\s*nhiêu|bn|mấy)\s*mã|"
    r"list\s*còn\s*gì|còn\s*mã\s*gì|đã\s*gỡ\s*chưa)",
    re.I,
)

# Performance / mood of list → must stay chat (not status membership dump).
_PERFORMANCE_RE = re.compile(
    r"(hôm\s*nay\s*thế\s*nào|thế\s*nào\s*hôm\s*nay|biến\s*động|"
    r"mạnh\s*/?\s*yếu|mã\s*nào\s*(mạnh|yếu|tăng|giảm)|"
    r"ra\s*sao|diễn\s*biến|hiệu\s*suất|watchlist.{0,20}thế\s*nào|"
    r"list.{0,20}thế\s*nào|%[^\n]{0,12}watchlist|watchlist.{0,12}%)",
    re.I,
)

_REMOVE_HINT_RE = re.compile(
    r"(x[oó]a|gỡ|cắt|bỏ|loại|kém|yếu|gọn|trim|remove)",
    re.I,
)

_ADD_HINT_RE = re.compile(
    r"(th[eê]m|add|cho\s+vào|đưa\s+vào)",
    re.I,
)

_TICKER_RE = re.compile(r"\b([A-Za-z]{3})\b")


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


def _watchlist_symbol_set(context: dict | None) -> set[str]:
    out: set[str] = set()
    if not isinstance(context, dict):
        return out
    wl = context.get("watchlists")
    if not isinstance(wl, dict):
        return out
    for item in wl.get("lists") or []:
        if not isinstance(item, dict):
            continue
        for s in item.get("symbols") or []:
            sym = str(s).upper().strip()
            if len(sym) == 3:
                out.add(sym)
    return out


def _last_assistant_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        role = (msg.get("role") or "").lower()
        if role not in ("assistant", "model"):
            continue
        text = (msg.get("content") or msg.get("text") or "").strip()
        if text:
            return text
    return ""


def _tickers_in_text(text: str, allowed: set[str] | None = None) -> list[str]:
    found: list[str] = []
    for m in _TICKER_RE.finditer(text or ""):
        sym = m.group(1).upper()
        if sym in found:
            continue
        if allowed is not None and sym not in allowed:
            continue
        found.append(sym)
    return found[:8]


def guard_intent_performance_as_chat(intent: WatchlistIntent, user_text: str) -> WatchlistIntent:
    """Force chat when user asks about session performance, not list membership."""
    text = (user_text or "").strip()
    if not text:
        return intent
    if intent.kind != "status_watchlist":
        return intent
    # Real membership questions stay status.
    if _STATUS_RE.search(text) and not _PERFORMANCE_RE.search(text):
        return intent
    if _PERFORMANCE_RE.search(text) or not _STATUS_RE.search(text):
        # Ambiguous "list thế nào" without membership keywords → chat.
        if _PERFORMANCE_RE.search(text) or re.search(
            r"(watchlist|list|danh\s*sách).{0,24}(thế\s*nào|ra\s*sao)",
            text,
            re.I,
        ):
            return intent.model_copy(
                update={
                    "kind": "chat",
                    "notes": (intent.notes or "") + " | forced_chat_performance",
                    "confidence": max(intent.confidence, 0.85),
                }
            )
    return intent


def enrich_intent_from_thread(
    intent: WatchlistIntent,
    messages: list[dict],
    context: dict | None,
) -> WatchlistIntent:
    """
    Upgrade short confirmations ("đồng ý", "ok") after an assistant suggestion
    into execute_remove / execute_add with symbols filled from that suggestion.
    """
    user = _latest_user_text(messages)
    if not user or _STATUS_RE.search(user):
        return intent

    in_lists = _watchlist_symbol_set(context)
    assistant = _last_assistant_text(messages)
    suggested = _tickers_in_text(assistant, in_lists if in_lists else None)
    if not suggested:
        return intent

    is_confirm = bool(_CONFIRM_RE.search(user))
    # Also treat bare confirm-ish replies that mention those codes.
    user_syms = _tickers_in_text(user, set(suggested))
    if not is_confirm and not user_syms:
        # Still fill empty symbols on execute_* if assistant just named them.
        if intent.kind in EXECUTE_KINDS and not intent.symbols:
            return intent.model_copy(update={"symbols": suggested, "confidence": max(intent.confidence, 0.8)})
        return intent

    assistant_wants_remove = bool(_REMOVE_HINT_RE.search(assistant))
    assistant_wants_add = bool(_ADD_HINT_RE.search(assistant)) and not assistant_wants_remove

    if is_confirm or user_syms:
        if assistant_wants_remove or intent.kind == "execute_remove" or (
            intent.kind in ("chat", "propose_change") and assistant_wants_remove
        ):
            return WatchlistIntent(
                kind="execute_remove",
                symbols=user_syms or intent.symbols or suggested,
                watchlist_hint=intent.watchlist_hint,
                notes=intent.notes or "User xác nhận xóa các mã đã gợi ý",
                confidence=max(intent.confidence, 0.9),
                source=intent.source,
            )
        if assistant_wants_add or intent.kind == "execute_add":
            return WatchlistIntent(
                kind="execute_add",
                symbols=user_syms or intent.symbols or suggested,
                watchlist_hint=intent.watchlist_hint,
                notes=intent.notes or "User xác nhận thêm các mã đã gợi ý",
                confidence=max(intent.confidence, 0.9),
                source=intent.source,
            )
        # Confirm after a suggestion that listed tickers but wording was soft —
        # default to remove when prior user turn was about trimming (in transcript).
        transcript = _recent_transcript(messages, max_turns=4)
        if _REMOVE_HINT_RE.search(transcript):
            return WatchlistIntent(
                kind="execute_remove",
                symbols=user_syms or intent.symbols or suggested,
                watchlist_hint=intent.watchlist_hint,
                notes=intent.notes or "User xác nhận thao tác trên mã đã gợi ý",
                confidence=max(intent.confidence, 0.85),
                source=intent.source,
            )

    if intent.kind in EXECUTE_KINDS and not intent.symbols and suggested:
        return intent.model_copy(update={"symbols": suggested})

    return intent


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
            intent = WatchlistIntent(
                kind="chat",
                symbols=intent.symbols,
                watchlist_hint=intent.watchlist_hint,
                notes=intent.notes,
                confidence=intent.confidence,
                source="llm",
            )
        intent = enrich_intent_from_thread(intent, messages, context)
        return guard_intent_performance_as_chat(intent, user)
    except Exception as exc:
        logger.warning("watchlist intent classify failed: %s", exc)
        fallback = WatchlistIntent(
            kind="chat",
            confidence=0.0,
            source="fallback",
            notes="intent_classify_failed",
        )
        intent = enrich_intent_from_thread(fallback, messages, context)
        return guard_intent_performance_as_chat(intent, user)
