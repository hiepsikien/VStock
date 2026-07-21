from __future__ import annotations

import time
from collections import defaultdict

from app.services import gemini_companion

# Simple in-memory rate limit: max N chat requests / window / IP key.
_RATE_WINDOW_S = 60
_RATE_MAX = 30
_hits: dict[str, list[float]] = defaultdict(list)

VIEW_DETAIL_WINDOW_MS = 15 * 60 * 1000
VIEW_DETAIL_THRESHOLD = 3


def _rate_ok(key: str) -> bool:
    now = time.time()
    bucket = [t for t in _hits[key] if now - t < _RATE_WINDOW_S]
    _hits[key] = bucket
    if len(bucket) >= _RATE_MAX:
        return False
    bucket.append(now)
    return True


def check_rate_limit(client_key: str) -> bool:
    return _rate_ok(client_key or "anon")


def should_offer_nudge(events: list[dict], *, cooldown_until: float | None = None) -> bool:
    """Deterministic eligibility before calling Gemini for phrasing."""
    if cooldown_until and time.time() < cooldown_until:
        return False
    if not events:
        return False

    now_ms = int(time.time() * 1000)
    counts: dict[str, int] = defaultdict(int)
    for ev in events:
        if (ev.get("type") or ev.get("event")) != "view_detail":
            continue
        ts = int(ev.get("ts") or ev.get("at") or 0)
        if ts and now_ms - ts > VIEW_DETAIL_WINDOW_MS:
            continue
        sym = (ev.get("symbol") or "").upper()
        if not sym:
            continue
        counts[sym] += 1
        if counts[sym] >= VIEW_DETAIL_THRESHOLD:
            return True
    return False


async def chat_once(messages: list[dict], context: dict | None) -> str:
    if not gemini_companion.is_gemini_configured():
        raise RuntimeError("Gemini API not configured")
    return await gemini_companion.generate_reply(messages, context)


async def chat_stream(messages: list[dict], context: dict | None):
    if not gemini_companion.is_gemini_configured():
        raise RuntimeError("Gemini API not configured")
    async for piece in gemini_companion.stream_reply(messages, context):
        yield piece


async def build_nudge(
    context: dict | None,
    events: list[dict],
    *,
    cooldown_until: float | None = None,
) -> dict:
    if not should_offer_nudge(events, cooldown_until=cooldown_until):
        return {"show": False, "message": None}

    if not gemini_companion.is_gemini_configured():
        # Local fallback without API key — still useful for UI wiring.
        sym = _hot_symbol(events)
        msg = (
            f"Bạn vừa xem {sym} khá nhiều lần. Muốn nói vài phút không?"
            if sym
            else "Có vẻ bạn đang theo dõi thị trường khá sát. Muốn trò chuyện không?"
        )
        return {"show": True, "message": msg}

    try:
        text = await gemini_companion.generate_nudge(context, events)
    except Exception:
        text = None

    if not text:
        return {"show": False, "message": None}
    return {"show": True, "message": text}


def _hot_symbol(events: list[dict]) -> str | None:
    now_ms = int(time.time() * 1000)
    counts: dict[str, int] = defaultdict(int)
    for ev in events:
        if (ev.get("type") or ev.get("event")) != "view_detail":
            continue
        ts = int(ev.get("ts") or ev.get("at") or 0)
        if ts and now_ms - ts > VIEW_DETAIL_WINDOW_MS:
            continue
        sym = (ev.get("symbol") or "").upper()
        if sym:
            counts[sym] += 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]
