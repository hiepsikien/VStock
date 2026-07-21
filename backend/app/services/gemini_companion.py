from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

SYSTEM_INSTRUCTION = """Bạn là Vy — nhân vật đồng hành trong app VStock.

Tính cách (bám sát, đừng phá):
- Bạn thân ngồi cạnh nhìn bảng: gần gũi, tinh tế, hơi dí dỏm nhẹ, không “corporate”.
- Xưng “mình”, gọi người dùng “bạn”.
- Empathy trước: nhận cảm xúc (lo, FOMO, hưng phấn) rồi mới nói số liệu / ngữ cảnh.
- Không emoji trừ khi user dùng trước; tối đa 1 nếu thật sự hợp.
- Không giả lập môi giới, không khoe “chắc chắn”, không nói như chatbot CSKH.

Giọng nói — Hà Nội / miền Bắc (bắt buộc):
- Dùng từ Bắc: “thế”, “nhỉ”, “đấy”, “cơ”, “ý là”, “nhá”, “à”, “thế à”.
- Tránh từ/miền Nam: “thiệt”, “rứa”, “hen”, “nha”, “một phát”, “rồi đó”, “đâu á”.
- Nói như người Hà Nội trẻ nói chuyện tự nhiên, không viết văn mẫu.

Bonding & trí nhớ:
- Nếu có lịch sử chat hoặc mục [Ký ức gắn kết]: nhớ và gọi lại nhẹ (mã hay quan tâm, cảm xúc thường gặp) — như người quen, không tụng checklist.
- Đừng chào như lần đầu nếu đã từng nói chuyện.
- Xây dần sự tin cậy: lắng nghe, nhất quán, không phán xét.

Vai trò:
- Giải thích thị trường VN, chỉ số, mã, tin, ngữ cảnh phiên — rõ, ngắn, dễ nuốt trên mobile.
- Bám context app gửi (watchlist, hành vi gần đây, màn đang mở, ký ức).

Dữ liệu giá VStock (bắt buộc khi có):
- Nếu context có mục [Giá live VStock] hoặc [Chỉ số live]: PHẢI dùng đúng số đó khi trả lời về giá / biến động / khối lượng.
- Đơn vị giá cổ phiếu trong app là nghìn đồng (vd. 95.2 = 95.200đ). Nói tự nhiên: “FPT đang 95.2, +1.2%”.
- Không bịa giá. Không có mã trong liveQuotes thì nói thật là mình chưa kéo được giá mã đó lúc này.
- Trả lời cụ thể, không chung chung kiểu “thị trường biến động” khi đã có số.

Cấm tuyệt đối:
- Không tư vấn đầu tư: không bảo nên mua / bán / nắm giữ / cắt lỗ / bắt đáy.
- Không target price, tỷ lệ chắc chắn, “đảm bảo lợi nhuận”.
- Không đóng vai bác sĩ / trị liệu lâm sàng.

Khi bị hỏi “có nên mua/bán không?”:
- Từ chối nhẹ, đúng giọng Vy (không formal), nhắc mình không đưa khuyến nghị.
- Vẫn giúp làm rõ thông tin / rủi ro khái niệm / khung tự quyết định.

Độ dài:
- Ưu tiên 2–4 câu ngắn; hỏi sâu mới dài hơn.
- Tránh liệt kê bullet dày; viết như nói chuyện.
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
    "Khoan đã nhá — mình không đưa lời khuyên mua hay bán đâu. "
    "Bạn kể mục tiêu với mức rủi ro đang đặt, "
    "mình cùng làm rõ thông tin; quyết định vẫn là của bạn."
)

DEFAULT_MODEL = "gemini-3.5-flash"


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

    bond = context.get("bond")
    if isinstance(bond, dict) and bond:
        parts.append("[Ký ức gắn kết với người dùng]")
        mc = bond.get("messageCount")
        if mc is not None:
            parts.append(f"- Số tin đã trò chuyện: {mc}")
        first = bond.get("firstMetAt")
        if first:
            parts.append(f"- quen từ (epoch ms): {first}")
        syms = bond.get("symbolsOfInterest") or []
        if syms:
            parts.append(f"- Mã hay nhắc/quan tâm: {', '.join(str(s) for s in syms[:12])}")
        notes = bond.get("notes") or []
        if notes:
            parts.append("- Ghi chú gắn kết:\n" + "\n".join(f"  · {n}" for n in notes[:12]))
        parts.append(
            "- Hãy nói như người đã quen: gọi lại ký ức nhẹ nhàng khi hợp, "
            "không chào kiểu lần đầu, không tụng danh sách."
        )

    live_quotes = context.get("liveQuotes") or []
    if live_quotes:
        parts.append("[Giá live VStock — nguồn app, đơn vị nghìn đồng]")
        for q in live_quotes[:15]:
            if not isinstance(q, dict):
                continue
            sym = q.get("symbol") or "?"
            price = q.get("price")
            ch = q.get("change")
            pct = q.get("changePercent")
            vol = q.get("volume")
            hi = q.get("high")
            lo = q.get("low")
            stale = " (stale)" if q.get("stale") else ""
            line = f"  · {sym}: giá {price}, đổi {ch} ({pct}%)"
            if hi is not None and lo is not None:
                line += f", cao {hi} / thấp {lo}"
            if vol is not None:
                line += f", KL {vol}"
            line += stale
            parts.append(line)
        parts.append(
            "- Khi user hỏi giá/biến động: nêu đúng số trên, nói tự nhiên, không bịa."
        )

    live_indices = context.get("liveIndices") or []
    if live_indices:
        parts.append("[Chỉ số / hàng hóa live VStock]")
        for ix in live_indices[:10]:
            if not isinstance(ix, dict):
                continue
            sym = ix.get("symbol") or ix.get("name") or "?"
            price = ix.get("price")
            pct = ix.get("changePercent")
            parts.append(f"  · {sym}: {price} ({pct}%)")

    return "\n".join(parts)


def build_contents(messages: list[dict], context: dict | None) -> list[types.Content]:
    contents: list[types.Content] = []
    ctx_block = _format_context(context)

    # Attach live market context to the latest user turn (not the oldest).
    last_user_idx = -1
    prepared: list[tuple[str, str]] = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or msg.get("text") or "").strip()
        if not text:
            continue
        if role == "assistant":
            prepared.append(("model", text))
        else:
            prepared.append(("user", text))
            last_user_idx = len(prepared) - 1

    if not prepared and ctx_block:
        contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            f"{ctx_block}\n\n"
                            "Chào ngắn đúng giọng Vy và hỏi bạn đang quan tâm gì."
                        )
                    )
                ],
            )
        )
        return contents

    for i, (role, text) in enumerate(prepared):
        if role == "user" and i == last_user_idx and ctx_block:
            text = f"{ctx_block}\n\n[Tin nhắn người dùng]\n{text}"
        contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
    return contents


async def generate_reply(messages: list[dict], context: dict | None = None) -> str:
    client = _client()
    contents = build_contents(messages, context)
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.9,
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
        temperature=0.9,
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
    + "\n\nNhiệm vụ đặc biệt: viết ĐÚNG MỘT câu ngắn (≤160 ký tự) theo giọng Vy "
    "để mở lời dựa trên hành vi gần đây — như bạn thân ghé ngang, không salesy. "
    "Không hỏi nhiều câu. Không tư vấn mua/bán. "
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
