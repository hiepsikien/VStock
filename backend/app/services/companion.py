from __future__ import annotations

import asyncio
import re
import time
from collections import defaultdict

from app.services import gemini_companion
from app.services import indices as indices_service
from app.services import quotes as quotes_service

# Simple in-memory rate limit: max N chat requests / window / IP key.
_RATE_WINDOW_S = 60
_RATE_MAX = 30
_hits: dict[str, list[float]] = defaultdict(list)

VIEW_DETAIL_WINDOW_MS = 15 * 60 * 1000
VIEW_DETAIL_THRESHOLD = 3

_TICKER_RE = re.compile(r"\b([A-Za-z]{3})\b")
_TICKER_STOP = {
    "THE",
    "AND",
    "FOR",
    "ARE",
    "BUT",
    "NOT",
    "YOU",
    "ALL",
    "CAN",
    "HER",
    "WAS",
    "ONE",
    "OUR",
    "OUT",
    "DAY",
    "GET",
    "HAS",
    "HIM",
    "HIS",
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
    "VND",
    "USD",
    "CEO",
    "CFO",
    "IPO",
    "ETF",
    "API",
    "APP",
    "AI",
}


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


def _latest_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        role = (msg.get("role") or "user").lower()
        if role == "assistant":
            continue
        text = (msg.get("content") or msg.get("text") or "").strip()
        if text:
            return text
    return ""


def _symbols_from_text(text: str) -> list[str]:
    found: list[str] = []
    for m in _TICKER_RE.finditer(text):
        sym = m.group(1).upper()
        if sym in _TICKER_STOP:
            continue
        if sym not in found:
            found.append(sym)
    return found


async def _known_symbol_set() -> set[str] | None:
    """Read symbol universe from DB/cache only — never trigger a full ingest."""
    try:
        cached = __import__("app.services.cache", fromlist=["cache"]).cache.get("symbols:all")
        if cached:
            return {str(r.get("symbol") or "").upper() for r in cached if r.get("symbol")}
        from app.repositories.symbols_repo import SymbolsRepository

        rows = await SymbolsRepository().get_all()
        if not rows:
            return None
        return {str(r.get("symbol") or "").upper() for r in rows if r.get("symbol")}
    except Exception:
        return None


async def _fetch_quotes_safe(symbols: list[str], timeout_s: float = 4.0) -> dict[str, dict]:
    if not symbols:
        return {}
    try:
        return await asyncio.wait_for(quotes_service.fetch_quotes(symbols), timeout=timeout_s)
    except Exception:
        return {}


async def _fetch_indices_safe(timeout_s: float = 3.0) -> list[dict]:
    try:
        return await asyncio.wait_for(indices_service.fetch_market_indices(), timeout=timeout_s)
    except Exception:
        return []


def _collect_candidate_symbols(messages: list[dict], context: dict | None) -> list[str]:
    ctx = context or {}
    ordered: list[str] = []

    def add(sym: str | None) -> None:
        if not sym:
            return
        s = str(sym).strip().upper()
        if len(s) < 3 or s in ordered:
            return
        ordered.append(s)

    # Prefer what the user just asked about.
    for sym in _symbols_from_text(_latest_user_text(messages)):
        add(sym)

    add(ctx.get("symbol"))

    bond = ctx.get("bond") if isinstance(ctx.get("bond"), dict) else {}
    for sym in bond.get("symbolsOfInterest") or []:
        add(str(sym))

    for sym in ctx.get("watchlistSymbols") or ctx.get("watchlist") or []:
        add(str(sym))

    for ev in (ctx.get("recentEvents") or [])[-10:]:
        if isinstance(ev, dict):
            add(ev.get("symbol"))

    return ordered


async def enrich_context_with_market(
    messages: list[dict],
    context: dict | None,
) -> dict:
    """Attach live VStock quotes/indices so Vy can answer with real numbers."""
    ctx = dict(context or {})
    candidates = _collect_candidate_symbols(messages, ctx)
    msg_tickers = set(_symbols_from_text(_latest_user_text(messages)))
    known = await _known_symbol_set()

    filtered: list[str] = []
    for sym in candidates:
        # Tickers typed in the message must exist in the universe when available.
        if sym in msg_tickers and known is not None and sym not in known:
            continue
        filtered.append(sym)

    to_fetch = filtered[:12]
    live_quotes: list[dict] = []
    if to_fetch:
        quote_map = await _fetch_quotes_safe(to_fetch)
        for sym in to_fetch:
            q = quote_map.get(sym)
            if not q:
                continue
            live_quotes.append(
                {
                    "symbol": sym,
                    "price": q.get("price"),
                    "change": q.get("change"),
                    "changePercent": q.get("changePercent"),
                    "open": q.get("open"),
                    "high": q.get("high"),
                    "low": q.get("low"),
                    "volume": q.get("volume"),
                    "ref": q.get("ref"),
                    "stale": bool(q.get("stale")),
                }
            )

    ctx["liveQuotes"] = live_quotes

    indices = await _fetch_indices_safe()
    ctx["liveIndices"] = [
        {
            "symbol": ix.get("symbol"),
            "name": ix.get("name"),
            "price": ix.get("price"),
            "changePercent": ix.get("changePercent"),
        }
        for ix in (indices or [])[:8]
        if isinstance(ix, dict)
    ]

    return ctx


async def chat_once(messages: list[dict], context: dict | None) -> str:
    if not gemini_companion.is_gemini_configured():
        raise RuntimeError("Gemini API not configured")
    enriched = await enrich_context_with_market(messages, context)
    return await gemini_companion.generate_reply(messages, enriched)


async def chat_stream(messages: list[dict], context: dict | None):
    if not gemini_companion.is_gemini_configured():
        raise RuntimeError("Gemini API not configured")
    enriched = await enrich_context_with_market(messages, context)
    async for piece in gemini_companion.stream_reply(messages, enriched):
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
        enriched = await enrich_context_with_market([], context)
        text = await gemini_companion.generate_nudge(enriched, events)
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
