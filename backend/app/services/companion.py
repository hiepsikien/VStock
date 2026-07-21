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
# Watchlist mover nudge thresholds (|changePercent|).
PRICE_MOVE_PCT = 2.0
WATCHLIST_AVG_MOVE_PCT = 1.5

_TICKER_RE = re.compile(r"\b([A-Za-z]{3})\b")
_TICKER_STOP = set(gemini_companion._VI_FALSE_TICKERS) | {
    "APP",
    "AI",
}

_SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bank": ("ngân hàng", "ngan hang", "bank"),
    "securities": ("chứng khoán", "chung khoan", "broker", "securities"),
    "real_estate": ("bất động sản", "bat dong san", "real estate", "property"),
    "energy": ("năng lượng", "nang luong", "energy", "dầu khí", "dau khi", "điện", "dien", "power", "oil & gas"),
}

_SECTOR_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "bank": ("ngân hàng", "bank"),
    "securities": ("chứng khoán", "securities"),
    "real_estate": ("bất động sản", "real estate", "property"),
    "energy": ("năng lượng", "dầu khí", "điện", "power", "oil", "gas", "petrol", "nhiên liệu"),
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


def should_offer_nudge(
    events: list[dict],
    *,
    cooldown_until: float | None = None,
    context: dict | None = None,
    movers: list[dict] | None = None,
) -> bool:
    """Eligible if repeated detail views OR meaningful price moves OR topic recall."""
    if cooldown_until and time.time() < cooldown_until:
        return False

    ctx = context or {}
    if ctx.get("nudgeKind") == "recall":
        return True

    if movers:
        return True

    ctx = context or {}
    avg = ctx.get("avgChange")
    try:
        if avg is not None and abs(float(avg)) >= WATCHLIST_AVG_MOVE_PCT:
            return True
    except (TypeError, ValueError):
        pass

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


def _watchlist_movers(context: dict | None, quote_map: dict[str, dict]) -> list[dict]:
    """Symbols on the user's list that moved sharply today."""
    ctx = context or {}
    watch = [
        str(s).strip().upper()
        for s in (ctx.get("watchlistSymbols") or ctx.get("watchlist") or [])
        if str(s).strip()
    ]
    if not watch:
        watch = [str(ctx.get("symbol")).upper()] if ctx.get("symbol") else []

    movers: list[dict] = []
    for sym in watch:
        q = quote_map.get(sym)
        if not q:
            continue
        try:
            pct = float(q.get("changePercent") or 0)
        except (TypeError, ValueError):
            continue
        if abs(pct) < PRICE_MOVE_PCT:
            continue
        movers.append(
            {
                "symbol": sym,
                "price": q.get("price"),
                "changePercent": pct,
                "change": q.get("change"),
            }
        )
    movers.sort(key=lambda m: abs(float(m["changePercent"])), reverse=True)
    return movers[:5]


async def build_nudge(
    context: dict | None,
    events: list[dict],
    *,
    cooldown_until: float | None = None,
) -> dict:
    # Enrich first so we can gate on live movers.
    enriched = await enrich_context_with_market([], context)
    quote_map = {
        str(q.get("symbol")).upper(): q
        for q in (enriched.get("liveQuotes") or [])
        if isinstance(q, dict) and q.get("symbol")
    }
    movers = _watchlist_movers(enriched, quote_map)
    enriched["nudgeMovers"] = movers

    if not should_offer_nudge(
        events,
        cooldown_until=cooldown_until,
        context=enriched,
        movers=movers,
    ):
        return {"show": False, "message": None}

    if not gemini_companion.is_gemini_configured():
        if enriched.get("nudgeKind") == "recall":
            msg = _recall_fallback(enriched)
            return {"show": True, "message": msg}
        if movers:
            top = movers[0]
            direction = "tăng" if float(top["changePercent"]) > 0 else "giảm"
            msg = (
                f"{top['symbol']} đang {direction} {abs(float(top['changePercent'])):.1f}% "
                f"trên watchlist. Muốn mình cùng nhìn qua không?"
            )
        else:
            sym = _hot_symbol(events)
            msg = (
                f"Bạn vừa xem {sym} khá nhiều lần. Muốn nói vài phút không?"
                if sym
                else "Watchlist hôm nay biến động khá. Muốn trò chuyện không?"
            )
        return {"show": True, "message": msg}

    try:
        text = await gemini_companion.generate_nudge(enriched, events)
    except Exception:
        text = None

    if not text and enriched.get("nudgeKind") == "recall":
        text = _recall_fallback(enriched)

    if not text:
        return {"show": False, "message": None}
    return {"show": True, "message": text}


def _recall_fallback(context: dict | None) -> str:
    ctx = context or {}
    bond = ctx.get("bond") if isinstance(ctx.get("bond"), dict) else {}
    sym = (ctx.get("recallTopic") or "").strip().upper()
    if not sym:
        syms = bond.get("symbolsOfInterest") or []
        sym = str(syms[0]).upper() if syms else ""
    nickname = str(bond.get("userNickname") or "").strip()
    who = nickname or "bạn"
    if sym:
        return f"Hôm trước {who} hay ngó {sym}… dạo này còn theo không?"
    notes = bond.get("notes") or []
    if notes:
        return f"Lâu rồi không trò chuyện, {who}. Dạo này thế nào?"
    return f"Chào lại {who}. Watchlist dạo này ra sao?"


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


def _detect_sector_key(text: str) -> str | None:
    lowered = (text or "").strip().lower()
    if not lowered:
        return None
    for key, terms in _SECTOR_KEYWORDS.items():
        if any(t in lowered for t in terms):
            return key
    return None


async def _sector_symbols_from_text(text: str, limit: int = 12) -> list[str]:
    key = _detect_sector_key(text)
    if not key:
        return []
    try:
        from app.services.symbols import fetch_all_symbols

        rows = await fetch_all_symbols()
    except Exception:
        return []
    hints = _SECTOR_NAME_HINTS.get(key, ())
    out: list[str] = []
    for row in rows:
        name = str(row.get("name") or "").lower()
        sym = str(row.get("symbol") or "").upper().strip()
        if len(sym) != 3 or not sym.isalpha():
            continue
        if sym in _TICKER_STOP:
            continue
        if any(h in name for h in hints):
            out.append(sym)
        if len(out) >= limit:
            break
    return out


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


async def _fetch_news_safe(symbols: list[str], timeout_s: float = 3.0) -> list[dict]:
    from app.services import news as news_service

    headlines: list[dict] = []
    focus = symbols[:3]

    async def one_symbol(sym: str) -> list[dict]:
        try:
            items = await asyncio.wait_for(
                news_service.fetch_symbol_news(sym, limit=2),
                timeout=timeout_s,
            )
            out = []
            for it in items or []:
                title = (it.get("title") or "").strip()
                if title:
                    out.append(
                        {
                            "symbol": sym,
                            "title": title[:180],
                            "id": it.get("id"),
                        }
                    )
            return out
        except Exception:
            return []

    if focus:
        results = await asyncio.gather(*(one_symbol(s) for s in focus))
        for batch in results:
            headlines.extend(batch)

    if len(headlines) < 2:
        try:
            market = await asyncio.wait_for(
                news_service.fetch_market_news(limit=4),
                timeout=timeout_s,
            )
            for it in market or []:
                title = (it.get("title") or "").strip()
                if not title:
                    continue
                headlines.append(
                    {
                        "symbol": "TT",
                        "title": title[:180],
                        "id": it.get("id"),
                    }
                )
                if len(headlines) >= 6:
                    break
        except Exception:
            pass

    # Dedupe by title
    seen: set[str] = set()
    unique: list[dict] = []
    for h in headlines:
        key = str(h.get("title") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique[:8]


async def enrich_context_with_market(
    messages: list[dict],
    context: dict | None,
) -> dict:
    """Attach live VStock data according to the active character knowledge pack."""
    from app.services.companion_packs import get_knowledge_pack

    ctx = dict(context or {})
    pack = get_knowledge_pack(
        str(ctx.get("characterId") or ctx.get("character_id") or "vy")
    )
    sources = set(pack.data_sources)
    ctx["characterId"] = pack.id
    ctx["knowledgePack"] = {
        "id": pack.id,
        "name": pack.name,
        "expertise": list(pack.expertise),
        "dataSources": list(pack.data_sources),
    }

    candidates = _collect_candidate_symbols(messages, ctx)
    latest_user_text = _latest_user_text(messages)
    msg_tickers = set(_symbols_from_text(latest_user_text))
    sector_symbols = (
        await _sector_symbols_from_text(latest_user_text, limit=12)
        if not msg_tickers
        else []
    )
    for sym in sector_symbols:
        if sym not in candidates:
            candidates.append(sym)
    known = await _known_symbol_set()

    filtered: list[str] = []
    for sym in candidates:
        if sym in msg_tickers and known is not None and sym not in known:
            continue
        filtered.append(sym)

    to_fetch = filtered[:18]
    live_quotes: list[dict] = []
    if "quotes" in sources and to_fetch:
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
    if sector_symbols:
        ctx["sectorCandidates"] = sector_symbols[:12]

    if "indices" in sources:
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
    else:
        ctx["liveIndices"] = []

    if "news" in sources:
        news_focus = list(msg_tickers)[:3] or (
            [str(ctx.get("symbol")).upper()] if ctx.get("symbol") else to_fetch[:2]
        )
        ctx["liveNews"] = await _fetch_news_safe([s for s in news_focus if s])
    else:
        ctx["liveNews"] = []

    return ctx


BOND_REFRESH_EVERY = 6


async def chat_once(messages: list[dict], context: dict | None) -> dict:
    if not gemini_companion.is_gemini_configured():
        raise RuntimeError("Gemini API not configured")
    enriched = await enrich_context_with_market(messages, context)
    text, tool_calls = await gemini_companion.generate_agent_reply(messages, enriched)
    bubbles = gemini_companion.split_reply_bubbles(text)
    suggestions = gemini_companion.build_quick_suggestions(enriched, messages)

    from app.services.companion_watchlist import infer_watchlist_actions, resolve_tool_calls

    known = await _known_symbol_set()
    actions = await resolve_tool_calls(
        tool_calls,
        enriched,
        known_symbols=known,
        messages=messages,
    )
    if not actions:
        actions = await infer_watchlist_actions(
            messages,
            enriched,
            known_symbols=known,
        )

    bond_notes = None
    bond = enriched.get("bond") if isinstance(enriched.get("bond"), dict) else None
    msg_count = int((bond or {}).get("messageCount") or 0)
    if msg_count > 0 and msg_count % BOND_REFRESH_EVERY == 0:
        bond_notes = await gemini_companion.refresh_bond_notes(messages, bond)

    return {
        "message": text,
        "bubbles": bubbles or [text],
        "suggestions": suggestions,
        "bondNotes": bond_notes,
        "actions": actions,
    }


async def chat_stream(messages: list[dict], context: dict | None):
    if not gemini_companion.is_gemini_configured():
        raise RuntimeError("Gemini API not configured")
    enriched = await enrich_context_with_market(messages, context)
    async for piece in gemini_companion.stream_reply(messages, enriched):
        yield piece
