from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

SYSTEM_INSTRUCTION = """Bạn là Companion của ứng dụng VStock — người đồng hành cho nhà đầu tư chứng khoán Việt Nam.

Vai trò:
- Giải thích thị trường, chỉ số, mã, tin tức và ngữ cảnh phiên một cách rõ ràng, ngắn gọn.
- Thể hiện empathy: lắng nghe cảm xúc (lo lắng, FOMO, hưng phấn), không phán xét.
- Bám context người dùng gửi (watchlist, hành vi gần đây, màn hình hiện tại).

Cấm tuyệt đối:
- Không tư vấn đầu tư: không bảo nên mua / bán / nắm giữ / cắt lỗ / bắt đáy bất kỳ mã nào.
- Không đưa target price, tỷ lệ chắc chắn, hay “đảm bảo lợi nhuận”.
- Không đóng vai bác sĩ / trị liệu lâm sàng.

Khi bị hỏi “có nên mua/bán không?” hoặc tương tự:
- Từ chối nhẹ nhàng, nhắc rằng bạn không đưa khuyến nghị.
- Có thể giúp làm rõ thông tin, rủi ro khái niệm, hoặc khung tự quyết định của họ.

Giọng: tiếng Việt, gần gũi như đồng nghiệp bình tĩnh trên sàn. Trả lời ngắn trên mobile (ưu tiên 2–5 câu trừ khi user hỏi sâu).
"""

ADVICE_PATTERNS = (
    re.compile(r"\bnên\s+mua\b", re.I),
    re.compile(r"\bnên\s+bán\b", re.I),
    re.compile(r"\bkhuyến\s*nghị\b", re.I),
    re.compile(r"\btarget\s*price\b", re.I),
    re.compile(r"\bmua\s+ngay\b", re.I),
    re.compile(r"\bbán\s+ngay\b", re.I),
    re.compile(r"\bđảm\s*bảo\s+lợi\s*nhuận\b", re.I),
)

REFUSAL = (
    "Mình không đưa khuyến nghị mua hay bán. "
    "Bạn có thể kể mục tiêu và mức rủi ro mình tự đặt — "
    "mình giúp làm rõ thông tin và giữ kỷ luật, còn quyết định là của bạn."
)

DEFAULT_MODEL = "gemini-2.5-flash"


def _api_key() -> str | None:
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("GOOGLE_GENAI_API_KEY")
    )


def is_gemini_configured() -> bool:
    if _api_key():
        return True
    return bool(os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT"))


def _client() -> genai.Client:
    key = _api_key()
    if key:
        return genai.Client(api_key=key)
    project = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = (
        os.getenv("GCP_LOCATION")
        or os.getenv("GOOGLE_CLOUD_LOCATION")
        or "asia-southeast1"
    )
    if not project:
        raise RuntimeError(
            "Gemini not configured. Set GEMINI_API_KEY for local, "
            "or GCP_PROJECT (+ ADC) for Vertex."
        )
    return genai.Client(vertexai=True, project=project, location=location)


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL") or DEFAULT_MODEL


def scrub_advice(text: str) -> str:
    if not text or not text.strip():
        return text
    if any(p.search(text) for p in ADVICE_PATTERNS):
        return REFUSAL
    return text


def _format_context(context: dict | None) -> str:
    if not context:
        return ""
    parts: list[str] = ["[Context phiên làm việc]"]
    screen = context.get("screen")
    if screen:
        parts.append(f"- Màn hình: {screen}")
    symbol = context.get("symbol")
    if symbol:
        parts.append(f"- Mã đang xem: {symbol}")
    session = context.get("sessionLabel") or context.get("session")
    if session:
        parts.append(f"- Phiên: {session}")
    watchlist = context.get("watchlistSymbols") or context.get("watchlist")
    if watchlist:
        parts.append(f"- Watchlist: {', '.join(str(s) for s in watchlist[:20])}")
    avg = context.get("avgChange")
    if avg is not None:
        parts.append(f"- TB thay đổi watchlist: {avg}%")
    events = context.get("recentEvents") or context.get("events") or []
    if events:
        lines = []
        for ev in events[-15:]:
            if isinstance(ev, dict):
                t = ev.get("type") or ev.get("event")
                sym = ev.get("symbol") or ""
                lines.append(f"  · {t} {sym}".strip())
            else:
                lines.append(f"  · {ev}")
        parts.append("- Hành vi gần đây:\n" + "\n".join(lines))
    return "\n".join(parts)


def build_contents(messages: list[dict], context: dict | None) -> list[types.Content]:
    contents: list[types.Content] = []
    ctx_block = _format_context(context)
    primed = False
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or msg.get("text") or "").strip()
        if not text:
            continue
        if role == "assistant":
            contents.append(types.Content(role="model", parts=[types.Part(text=text)]))
            continue
        if not primed and ctx_block:
            text = f"{ctx_block}\n\n[Tin nhắn người dùng]\n{text}"
            primed = True
        contents.append(types.Content(role="user", parts=[types.Part(text=text)]))
    if not contents and ctx_block:
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=f"{ctx_block}\n\nHãy chào ngắn và hỏi mình có thể giúp gì."
                    )
                ],
            )
        )
    return contents


async def generate_reply(messages: list[dict], context: dict | None = None) -> str:
    client = _client()
    contents = build_contents(messages, context)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
        max_output_tokens=1024,
    )
    response = await client.aio.models.generate_content(
        model=_model_name(),
        contents=contents,
        config=config,
    )
    text = (response.text or "").strip()
    return scrub_advice(text) or REFUSAL


async def stream_reply(
    messages: list[dict],
    context: dict | None = None,
) -> AsyncIterator[str]:
    client = _client()
    contents = build_contents(messages, context)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.7,
        max_output_tokens=1024,
    )
    stream = await client.aio.models.generate_content_stream(
        model=_model_name(),
        contents=contents,
        config=config,
    )
    async for chunk in stream:
        piece = getattr(chunk, "text", None) or ""
        if piece:
            yield piece


NUDGE_SYSTEM = (
    SYSTEM_INSTRUCTION
    + "\n\nNhiệm vụ đặc biệt: viết ĐÚNG MỘT câu ngắn (≤160 ký tự) để mở lời "
    "dựa trên hành vi gần đây. Không hỏi nhiều câu. Không tư vấn mua/bán. "
    "Nếu không có lý do rõ để mở lời, trả về đúng chữ: SKIP"
)


async def generate_nudge(context: dict | None, events: list[dict]) -> str | None:
    payload = {
        **(context or {}),
        "recentEvents": events[-15:],
    }
    client = _client()
    ctx_block = _format_context(payload)
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(
                    text=f"{ctx_block}\n\nViết một câu mở lời đồng hành (hoặc SKIP)."
                )
            ],
        )
    ]
    config = types.GenerateContentConfig(
        system_instruction=NUDGE_SYSTEM,
        temperature=0.6,
        max_output_tokens=120,
    )
    response = await client.aio.models.generate_content(
        model=_model_name(),
        contents=contents,
        config=config,
    )
    text = scrub_advice((response.text or "").strip())
    if not text or text.upper().startswith("SKIP"):
        return None
    if len(text) > 200:
        text = text[:197] + "…"
    return text
