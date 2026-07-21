from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from app.services.companion_packs import get_knowledge_pack
from app.services.companion_tools import (
    WATCHLIST_TOOL_INSTRUCTION,
    extract_function_calls,
    watchlist_tool_config,
    watchlist_tool_declarations,
)

# Backward-compatible default (Vy pack). Prefer system_instruction_for().
SYSTEM_INSTRUCTION = get_knowledge_pack("vy").system_instruction

ADVICE_PATTERNS = (
    re.compile(r"\bkhuyến\s*nghị\s*(mua|bán|nắm giữ)?\b", re.I),
    re.compile(r"\btarget\s*price\b", re.I),
    re.compile(r"\bmua\s+ngay\b", re.I),
    re.compile(r"\bbán\s+ngay\b", re.I),
    re.compile(r"\ball[\s-]*in\b", re.I),
    re.compile(r"\bcắt\s*lỗ\s*ngay\b", re.I),
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
    pack = context.get("knowledgePack")
    if isinstance(pack, dict) and pack.get("id"):
        parts.append(f"- Knowledge pack: {pack.get('id')} ({pack.get('name') or ''})")
        expertise = pack.get("expertise") or []
        if expertise:
            parts.append(
                "- Chuyên môn: " + "; ".join(str(x) for x in expertise[:6])
            )
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
        parts.append(f"- Watchlist đang xem: {', '.join(str(s) for s in watchlist[:20])}")

    watchlists = context.get("watchlists")
    if isinstance(watchlists, dict):
        lists = watchlists.get("lists") or []
        active_id = watchlists.get("activeId")
        if lists:
            parts.append("[Danh sách theo dõi của user]")
            for item in lists[:12]:
                if not isinstance(item, dict):
                    continue
                wid = item.get("id")
                name = item.get("name") or "Danh sách"
                syms = item.get("symbols") or []
                active = " (đang mở)" if wid == active_id else ""
                sym_text = ", ".join(str(s) for s in syms[:24]) if syms else "(trống)"
                parts.append(f"  · {name}{active}: {sym_text}")
            parts.append(
                "- User có thể nhờ thêm mã / tạo danh sách mới — "
                "khi đồng ý, gọi function add_symbol_to_watchlist hoặc create_watchlist.\n"
                "- Muốn cắt mã kém / gọn list: gợi ý mã + lý do trước; chỉ gọi "
                "remove_symbol_from_watchlist sau khi user nêu mã hoặc đồng ý.\n"
                "- Hỏi 'xóa xong chưa': trả lời theo list hiện tại, không gọi function."
            )

    intent = context.get("watchlistIntent")
    if isinstance(intent, dict) and intent.get("kind"):
        parts.append("[Intent]")
        parts.append(f"- kind: {intent.get('kind')}")
        syms = intent.get("symbols") or []
        if syms:
            parts.append(f"- symbols: {', '.join(str(s) for s in syms)}")
        hint = intent.get("watchlistHint") or intent.get("watchlist_hint")
        if hint:
            parts.append(f"- watchlist_hint: {hint}")
        notes = intent.get("notes")
        if notes:
            parts.append(f"- notes: {notes}")
        parts.append(
            "- Chỉ gọi mutate function khi kind là execute_add / execute_remove / execute_create. "
            "propose_change: gợi ý + hỏi, không gọi function. "
            "status_watchlist / chat: không gọi function."
        )
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
        nickname = str(bond.get("userNickname") or "").strip()
        if nickname:
            parts.append(f"- Biệt danh user muốn được gọi: {nickname}")
        parts.append(
            "- Hãy nói như người đã quen: gọi lại ký ức nhẹ nhàng khi hợp, "
            "không chào kiểu lần đầu, không tụng danh sách."
        )

    today_mood = context.get("todayMood")
    if today_mood:
        parts.append(f"- Mood hôm nay (user vừa chia sẻ): {today_mood}")

    nudge_kind = context.get("nudgeKind")
    if nudge_kind == "recall":
        parts.append("[Nhắc lại chủ đề cũ]")
        topic = context.get("recallTopic")
        days = context.get("daysSinceLastChat")
        if topic:
            parts.append(f"- Mã/topic hay quan tâm trước đây: {topic}")
        if days is not None:
            parts.append(f"- Đã {days} ngày không trò chuyện")
        parts.append(
            "- Viết một câu nhắc nhẹ kiểu 'Hôm trước hay ngó X…' — không salesy."
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
    sector_candidates = context.get("sectorCandidates") or []
    if sector_candidates:
        parts.append(
            "- User đang hỏi theo nhóm ngành; ưu tiên chọn trong danh sách này khi gợi ý tham khảo: "
            + ", ".join(str(s) for s in sector_candidates[:12])
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

    live_news = context.get("liveNews") or []
    if live_news:
        parts.append("[Tin mới VStock — tiêu đề thật, không bịa thêm]")
        for item in live_news[:8]:
            if not isinstance(item, dict):
                continue
            sym = item.get("symbol") or "TT"
            title = (item.get("title") or "").strip()
            if not title:
                continue
            line = f"  · [{sym}] {title}"
            summary = (item.get("summary") or "").strip()
            if summary:
                line += f" — {summary[:160]}"
            published = item.get("publishedAt")
            if published:
                line += f" ({published})"
            parts.append(line)
        parts.append(
            "- Khi user hỏi vì sao mã động / có tin gì: bám headline/summary trên nếu hợp."
        )

    movers = context.get("watchlistMovers") or context.get("nudgeMovers") or []
    if movers:
        parts.append("[Watchlist movers — xếp theo |%| phiên]")
        for m in movers[:5]:
            if not isinstance(m, dict):
                continue
            sym = m.get("symbol") or "?"
            pct = m.get("changePercent")
            price = m.get("price")
            parts.append(f"  · {sym}: {price} ({pct}%)")
        parts.append(
            "- Khi hỏi watchlist hôm nay / giữ-gỡ mã: ưu tiên các mã trong block này."
        )

    live_fundamentals = context.get("liveFundamentals") or []
    if live_fundamentals:
        parts.append("[Định giá VStock — nguồn app, không bịa]")
        for f in live_fundamentals[:5]:
            if not isinstance(f, dict):
                continue
            sym = f.get("symbol") or "?"
            parts.append(
                f"  · {sym}: PE {f.get('pe')}, EPS {f.get('eps')}, "
                f"P/B {f.get('pb')}, ROE {f.get('roe')}, ROA {f.get('roa')}, "
                f"vốn hóa {f.get('marketCap')}"
            )
        parts.append(
            "- Khi hỏi định giá: nêu đúng số trên; thiếu field thì nói chưa có."
        )

    live_income = context.get("liveIncome") or []
    if live_income:
        parts.append("[KQKD VStock — doanh thu / LNST, không bịa]")
        for inc in live_income[:5]:
            if not isinstance(inc, dict):
                continue
            sym = inc.get("symbol") or "?"
            label = inc.get("revenueLabel") or "Doanh thu"
            annual = inc.get("latestAnnual") if isinstance(inc.get("latestAnnual"), dict) else None
            if annual:
                parts.append(
                    f"  · {sym} năm {annual.get('year')}: "
                    f"{label} {annual.get('netRevenue')}, LNST {annual.get('netIncome')}"
                )
            for q in (inc.get("lastQuarters") or [])[:2]:
                if not isinstance(q, dict):
                    continue
                qlabel = f"Q{q.get('quarter')}/{q.get('year')}" if q.get("quarter") else q.get("fiscalDate")
                parts.append(
                    f"  · {sym} {qlabel}: {label} {q.get('netRevenue')}, LNST {q.get('netIncome')}"
                )
        parts.append(
            "- Khi hỏi KQKD / doanh thu / LNST: dùng đúng số trên."
        )

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


def system_instruction_for(context: dict | None = None) -> str:
    character_id = None
    if isinstance(context, dict):
        character_id = context.get("characterId") or context.get("character_id")
    return get_knowledge_pack(
        str(character_id) if character_id else None
    ).system_instruction


async def generate_reply(messages: list[dict], context: dict | None = None) -> str:
    text, _calls = await generate_agent_reply(messages, context)
    return text


def _text_from_response(response) -> str:
    chunks: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        for part in getattr(content, "parts", None) or []:
            t = getattr(part, "text", None)
            if t:
                chunks.append(t)
    text = "".join(chunks).strip()
    if not text:
        text = (getattr(response, "text", None) or "").strip()
    return text


async def generate_agent_reply(
    messages: list[dict],
    context: dict | None = None,
    *,
    allow_tools: bool = True,
) -> tuple[str, list[dict]]:
    """Gemini reply; optionally with watchlist function calling."""
    client = _client()
    contents = build_contents(messages, context)
    system = system_instruction_for(context)
    if allow_tools:
        system = system + WATCHLIST_TOOL_INSTRUCTION
    intent = (context or {}).get("watchlistIntent") if isinstance(context, dict) else None
    if isinstance(intent, dict) and intent.get("kind") == "propose_change":
        system += (
            "\n\n[Chế độ đề xuất] User muốn thay đổi list nhưng chưa xác nhận mã. "
            "Gợi ý cụ thể vài mã + lý do ngắn từ list/context, hỏi đồng ý. "
            "KHÔNG gọi function mutate trong lượt này."
        )
    config_kwargs: dict = {
        "system_instruction": system,
        "temperature": 0.85,
        "max_output_tokens": 2048,
    }
    if allow_tools:
        config_kwargs["tools"] = watchlist_tool_declarations()
        config_kwargs["tool_config"] = watchlist_tool_config()
    config = types.GenerateContentConfig(**config_kwargs)
    response = await client.aio.models.generate_content(
        model=_model_name(),
        contents=contents,
        config=config,
    )
    text = _text_from_response(response)
    calls = extract_function_calls(response) if allow_tools else []
    text = _repair_truncated_reply(text)
    if text:
        text = scrub_advice(text) or REFUSAL
    elif calls:
        from app.services.companion_watchlist import POPUP_READY_TEXT

        text = POPUP_READY_TEXT
    else:
        text = scrub_advice(text) or REFUSAL
    return text, calls


async def stream_reply(
    messages: list[dict],
    context: dict | None = None,
) -> AsyncIterator[str]:
    client = _client()
    contents = build_contents(messages, context)
    config = types.GenerateContentConfig(
        system_instruction=system_instruction_for(context),
        temperature=0.85,
        max_output_tokens=2048,
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


NUDGE_TAIL = (
    "\n\nNhiệm vụ đặc biệt: viết ĐÚNG MỘT câu ngắn (≤160 ký tự) theo giọng nhân vật "
    "để mở lời — như bạn thân ghé ngang, không salesy. "
    "Ưu tiên nhắc mã đang biến động mạnh trong [Mã biến động mạnh] nếu có "
    "(vd. FPT +2.4%), rồi mời nói chuyện. "
    "Nếu có [Nhắc lại chủ đề cũ]: nhắc nhẹ mã/topic trước đây, kiểu 'Hôm trước hay ngó X…'. "
    "Dùng biệt danh nếu có thay cho 'bạn'. "
    "Không hỏi nhiều câu. Không tư vấn mua/bán. "
    "Nếu không có lý do rõ để mở lời, trả về đúng chữ: SKIP"
)

NUDGE_SYSTEM = SYSTEM_INSTRUCTION + NUDGE_TAIL


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
        system_instruction=system_instruction_for(payload) + NUDGE_TAIL,
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


BOND_SUMMARY_SYSTEM = """Bạn là trợ lý nội bộ của Companion Vy trên VStock.
Nhiệm vụ: đọc hội thoại gần đây và viết 3–5 ghi chú ngắn (tiếng Việt) về người dùng
để Vy nhớ và gắn kết dần. Mỗi dòng một ghi chú, không đánh số, không markdown.
Tập trung: mã quan tâm, thói quen xem bảng, cảm xúc/phong cách (lo, FOMO, kỷ luật…).
Không tư vấn mua/bán. Không bịa điều không có trong chat.
"""


def _is_complete_utterance(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if re.search(r'[.!?…]\s*$', s):
        return True
    # Soft Vietnamese chat endings
    return bool(re.search(r"(nhỉ|nhé|nhá|à|ạ|không|chứ)\s*$", s, re.I))


def _safe_focus_symbols(context: dict | None) -> list[str]:
    """Only real tickers from app context — never Vietnamese words like NAY/SAO."""
    ctx = context or {}
    ordered: list[str] = []

    def add(sym: object | None) -> None:
        if not sym:
            return
        s = str(sym).strip().upper()
        if len(s) != 3 or not s.isalpha():
            return
        if s in _VI_FALSE_TICKERS:
            return
        if s not in ordered:
            ordered.append(s)

    add(ctx.get("symbol"))
    for q in ctx.get("liveQuotes") or []:
        if isinstance(q, dict):
            add(q.get("symbol"))
    for s in ctx.get("watchlistSymbols") or ctx.get("watchlist") or []:
        add(s)
    bond = ctx.get("bond") if isinstance(ctx.get("bond"), dict) else {}
    for s in (bond or {}).get("symbolsOfInterest") or []:
        add(s)
    return ordered


# Vietnamese / chat words that look like 3-letter tickers when uppercased.
_VI_FALSE_TICKERS = {
    "NAY",
    "TIN",
    "SAO",
    "THE",
    "ROI",
    "ROI",
    "CUA",
    "CHO",
    "VAO",
    "VOI",
    "MOT",
    "HAI",
    "BA",
    "BON",
    "NAM",
    "SAU",
    "BAY",
    "TAM",
    "HON",
    "RAT",
    "LAI",
    "VAN",
    "DEN",
    "NUA",
    "THI",
    "NEU",
    "KHI",
    "SE",
    "DA",
    "DUOC",
    "KHONG",
    "PHAI",
    "NUA",
    "LAM",
    "CAI",
    "NAY",
    "DAY",
    "NOI",
    "XEM",
    "HOI",
    "GIA",
    "MUC",
    "LOI",
    "LO",
    "VANG",
    "DAU",
    "NEN",
    "BAN",
    "MUA",
    "NHA",
    "ONG",
    "CHI",
    "EM",
    "ANH",
    "TOI",
    "MINH",
    "BAN",
    "APP",
    "API",
    "CEO",
    "CFO",
    "IPO",
    "ATC",
    "ATO",
    "FOMO",
    "ETF",
    "USD",
    "VND",
    "AND",
    "FOR",
    "THE",
    "YOU",
    "ALL",
    "CAN",
    "HOW",
    "NEW",
    "NOW",
    "OLD",
    "SEE",
    "TWO",
    "WAY",
    "WHO",
    "DID",
    "ITS",
    "LET",
    "PUT",
    "SAY",
    "SHE",
    "TOO",
    "USE",
    "BUT",
    "NOT",
    "ARE",
    "WAS",
    "ONE",
    "OUR",
    "OUT",
    "DAY",
    "GET",
    "HAS",
    "HIM",
    "HIS",
    "HER",
}


def build_quick_suggestions(
    context: dict | None,
    messages: list[dict],
) -> list[str]:
    """Contextual quick-reply chips aligned to the five core question types."""
    ctx = context or {}
    chips: list[str] = []

    def add(label: str) -> None:
        label = label.strip()
        if label and label not in chips:
            chips.append(label)

    focus_list = _safe_focus_symbols(ctx)
    focus = focus_list[0] if focus_list else None
    has_watchlist = bool(
        ctx.get("watchlistSymbols")
        or ctx.get("watchlist")
        or (
            isinstance(ctx.get("watchlists"), dict)
            and (ctx.get("watchlists") or {}).get("lists")
        )
    )

    # Q1 — watchlist / market pulse
    if has_watchlist:
        add("Watchlist hôm nay thế nào?")
    else:
        add("Thị trường hôm nay thế nào?")

    # Q2 / Q4 — symbol-specific
    if focus:
        add(f"Tại sao {focus} biến động?")
        add(f"{focus} định giá / KQKD?")
    else:
        add("Tin đáng chú ý?")

    # Q3 — news (if not already added)
    add("Tin đáng chú ý?")

    # Q5 — keep / trim
    if has_watchlist:
        add("Nên giữ hay gỡ mã nào?")

    return chips[:4]


def _repair_truncated_reply(text: str) -> str:
    """Drop mid-sentence tails / leftover --- fragments from truncated generations."""
    raw = (text or "").strip()
    if not raw:
        return raw
    raw = re.sub(r"\n\s*---\s*\n[\s\S]*$", "", raw).strip()
    raw = re.sub(r"\n\s*---\s*$", "", raw).strip()
    if _is_complete_utterance(raw):
        return raw
    ends = list(re.finditer(r"[.!?…]", raw))
    if ends:
        trimmed = raw[: ends[-1].end()].strip()
        if len(trimmed) >= 24:
            return trimmed
    return raw


def split_reply_bubbles(text: str) -> list[str]:
    """Split Vy reply into natural chat bubbles (complete utterances only)."""
    raw = _repair_truncated_reply(text)
    if not raw:
        return []

    raw = re.sub(r"\n\s*---\s*\n", "\n\n", raw).strip()

    paras = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if 2 <= len(paras) <= 3 and all(_is_complete_utterance(p) for p in paras):
        return paras

    if len(raw) > 220 and _is_complete_utterance(raw):
        sentences = re.findall(r"[^.!?…]+[.!?…]+(?:\s+|$)", raw)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) >= 2:
            mid = max(1, (len(sentences) + 1) // 2)
            first = " ".join(sentences[:mid]).strip()
            second = " ".join(sentences[mid:]).strip()
            out = [p for p in (first, second) if p]
            if len(out) >= 2 and all(_is_complete_utterance(p) for p in out):
                return out

    return [raw]


async def refresh_bond_notes(
    messages: list[dict],
    bond: dict | None,
) -> list[str] | None:
    """Occasional LLM pass to deepen bonding memory."""
    if not is_gemini_configured():
        return None
    recent = []
    for msg in messages[-16:]:
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        who = "Vy" if role == "assistant" else "User"
        recent.append(f"{who}: {text[:400]}")
    if len(recent) < 4:
        return None

    existing = []
    if isinstance(bond, dict):
        existing = [str(n) for n in (bond.get("notes") or [])[:8]]

    prompt = (
        "Hội thoại gần đây:\n"
        + "\n".join(recent)
        + "\n\nGhi chú cũ (có thể giữ/viết lại):\n"
        + ("\n".join(f"- {n}" for n in existing) if existing else "(chưa có)")
        + "\n\nViết 3–5 ghi chú mới, mỗi dòng một ghi chú."
    )
    try:
        client = _client()
        response = await client.aio.models.generate_content(
            model=_model_name(),
            contents=[
                types.Content(role="user", parts=[types.Part(text=prompt)])
            ],
            config=types.GenerateContentConfig(
                system_instruction=BOND_SUMMARY_SYSTEM,
                temperature=0.4,
                max_output_tokens=280,
            ),
        )
        text = (response.text or "").strip()
    except Exception:
        return None

    notes: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"^[\s\-•*\d.]+", "", line).strip()
        if 6 <= len(cleaned) <= 120:
            notes.append(cleaned)
        if len(notes) >= 5:
            break
    return notes or None
