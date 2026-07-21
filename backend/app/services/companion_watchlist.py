"""Infer watchlist actions from companion chat (add symbol, create list, suggest)."""

from __future__ import annotations

import re
from typing import Any

from app.services.companion import _detect_sector_key, _sector_symbols_from_text
from app.services.gemini_companion import _VI_FALSE_TICKERS

_TICKER_RE = re.compile(r"\b([A-Za-z]{3})\b")

_ADD_PATTERNS = (
    re.compile(r"\bth[eê]m\s+([A-Za-z]{3})\b", re.I),
    re.compile(r"\badd\s+([A-Za-z]{3})\b", re.I),
    re.compile(r"\bcho\s+([A-Za-z]{3})\s+vào\b", re.I),
    re.compile(r"\bđưa\s+([A-Za-z]{3})\s+vào\b", re.I),
)

_CREATE_PATTERNS = (
    re.compile(
        r"\btạo\s+(?:một\s+)?(?:danh\s*sách|list)(?:\s+mới)?(?:\s+tên)?\s+(.+?)(?:\s+và|\s*$)",
        re.I,
    ),
    re.compile(r"\btạo\s+(?:một\s+)?(?:danh\s*sách|list)\s+mới\b", re.I),
    re.compile(r"\blàm\s+(?:một\s+)?(?:danh\s*sách|list)\b", re.I),
    re.compile(r"\bnew\s+watchlist(?:\s+(.+?))?(?:\s*$)", re.I),
)

_WANTS_CREATE = re.compile(
    r"\b(tạo|làm|tạo\s+một)\b.*\b(list|danh\s*sách)\b",
    re.I,
)

_TARGET_LIST_PATTERNS = (
    re.compile(r"\bvào\s+danh\s*sách\s+(.+?)(?:\s*$|[,.])", re.I),
    re.compile(r"\blist\s+(.+?)(?:\s*$|[,.])", re.I),
)

_SECTOR_LIST_NAMES: dict[str, str] = {
    "bank": "Ngân hàng",
    "securities": "Chứng khoán",
    "real_estate": "Bất động sản",
}


def _latest_user_text(messages: list[dict]) -> str:
    for msg in reversed(messages):
        role = (msg.get("role") or "user").lower()
        if role == "assistant":
            continue
        text = (msg.get("content") or msg.get("text") or "").strip()
        if text:
            return text
    return ""


def _valid_ticker(sym: str, known: set[str] | None) -> bool:
    s = sym.upper().strip()
    if len(s) != 3 or not s.isalpha():
        return False
    if s in _VI_FALSE_TICKERS:
        return False
    if known is not None and s not in known:
        return False
    return True


def _extract_tickers(text: str) -> list[str]:
    found: list[str] = []
    for m in _TICKER_RE.finditer(text):
        sym = m.group(1).upper()
        if sym not in found and sym not in _VI_FALSE_TICKERS:
            found.append(sym)
    return found


def _watchlist_lists(context: dict | None) -> list[dict[str, Any]]:
    wl = (context or {}).get("watchlists")
    if not isinstance(wl, dict):
        return []
    lists = wl.get("lists")
    return lists if isinstance(lists, list) else []


def _all_watchlist_symbols(lists: list[dict]) -> set[str]:
    out: set[str] = set()
    for item in lists:
        for sym in item.get("symbols") or []:
            out.add(str(sym).upper())
    return out


def _find_list_by_name(lists: list[dict], name: str) -> dict | None:
    q = name.strip().lower()
    if not q:
        return None
    for item in lists:
        n = str(item.get("name") or "").lower()
        if n == q or q in n:
            return item
    return None


def _parse_target_list(user_text: str, lists: list[dict]) -> dict | None:
    for pat in _TARGET_LIST_PATTERNS:
        m = pat.search(user_text)
        if not m:
            continue
        hit = _find_list_by_name(lists, m.group(1))
        if hit:
            return hit
    return None


def _count_symbol_mentions(messages: list[dict], symbol: str) -> int:
    sym = symbol.upper()
    count = 0
    for msg in messages:
        if (msg.get("role") or "user").lower() != "user":
            continue
        text = (msg.get("content") or "").upper()
        if re.search(rf"\b{re.escape(sym)}\b", text):
            count += 1
    return count


def _count_detail_views(events: list[dict], symbol: str) -> int:
    sym = symbol.upper()
    return sum(
        1
        for ev in events
        if (ev.get("type") or ev.get("event")) == "view_detail"
        and str(ev.get("symbol") or "").upper() == sym
    )


def _symbol_limit_from_text(text: str, default: int = 4) -> int:
    m = re.search(r"(\d+)\s*mã", text.lower())
    if m:
        try:
            return max(1, min(int(m.group(1)), 12))
        except ValueError:
            pass
    return default


def _sector_symbols_from_context(
    context: dict | None,
    known: set[str] | None,
    limit: int,
) -> list[str]:
    ctx = context or {}
    ordered: list[str] = []
    seen: set[str] = set()

    def add(sym: str) -> None:
        s = sym.upper()
        if s in seen or not _valid_ticker(s, known):
            return
        seen.add(s)
        ordered.append(s)

    live = ctx.get("liveQuotes") or []
    live_sorted = sorted(
        [q for q in live if isinstance(q, dict) and q.get("symbol")],
        key=lambda q: abs(float(q.get("changePercent") or 0)),
        reverse=True,
    )
    for q in live_sorted:
        add(str(q.get("symbol") or ""))
        if len(ordered) >= limit:
            return ordered[:limit]

    for sym in ctx.get("sectorCandidates") or []:
        add(str(sym))
        if len(ordered) >= limit:
            return ordered[:limit]

    return ordered[:limit]


async def infer_watchlist_actions(
    messages: list[dict],
    context: dict | None,
    *,
    known_symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Return client-executable watchlist actions — user confirms via in-chat buttons."""
    user = _latest_user_text(messages)
    if not user:
        return []

    lists = _watchlist_lists(context)
    if not lists:
        return []

    actions: list[dict[str, Any]] = []
    sector = _detect_sector_key(user)
    user_lower = user.lower()
    wants_create = bool(_WANTS_CREATE.search(user)) or (
        sector
        and re.search(r"\b(tạo|làm)\b", user_lower)
        and re.search(r"\b(list|danh\s*sách|mảng|\d+\s*mã)\b", user_lower)
    )

    # --- Create sector watchlist (e.g. banking list with 4 symbols) ---
    if wants_create and sector:
        limit = _symbol_limit_from_text(user, default=4)
        syms = _sector_symbols_from_context(context, known_symbols, limit)
        if not syms:
            syms = (
                await _sector_symbols_from_text(user, limit=limit)
            )[:limit]
            syms = [s for s in syms if _valid_ticker(s, known_symbols)]
        if syms:
            name = _SECTOR_LIST_NAMES.get(sector, "Danh sách mới")
            label = f"Tạo “{name}” ({', '.join(syms)})"
            return [
                {
                    "type": "create_watchlist",
                    "name": name,
                    "symbols": syms,
                    "label": label,
                }
            ]

    # --- Generic create watchlist ---
    for pat in _CREATE_PATTERNS:
        m = pat.search(user)
        if not m:
            continue
        name = (m.group(1) if m.lastindex else "Danh sách mới").strip()
        if not name or name.lower() in ("mới", "new"):
            name = "Danh sách mới"
        if sector and name.lower() in ("danh sách mới", "mới", "new"):
            name = _SECTOR_LIST_NAMES.get(sector, name)

        syms = [
            t
            for t in _extract_tickers(user)
            if _valid_ticker(t, known_symbols)
        ]
        limit = _symbol_limit_from_text(user, default=4)
        if not syms and sector:
            syms = _sector_symbols_from_context(context, known_symbols, limit)
        syms = syms[:limit]

        payload: dict[str, Any] = {
            "type": "create_watchlist",
            "name": name[:48],
        }
        if syms:
            payload["symbols"] = syms
            payload["label"] = f"Tạo “{name}” ({', '.join(syms)})"
        else:
            payload["label"] = f"Tạo danh sách “{name}”"
        return [payload]

    # --- Add symbol to list ---
    for pat in _ADD_PATTERNS:
        m = pat.search(user)
        if not m:
            continue
        sym = m.group(1).upper()
        if not _valid_ticker(sym, known_symbols):
            continue
        target = _parse_target_list(user, lists)
        already_everywhere = all(
            sym in {str(s).upper() for s in (item.get("symbols") or [])}
            for item in lists
        )
        if already_everywhere:
            return actions
        payload: dict[str, Any] = {"type": "add_symbol", "symbol": sym}
        if target:
            payload["watchlistId"] = str(target.get("id") or "")
            payload["watchlistName"] = str(target.get("name") or "")
            payload["label"] = f"Thêm {sym} vào “{payload['watchlistName']}”"
        elif len(lists) == 1:
            payload["watchlistId"] = str(lists[0].get("id") or "")
            payload["watchlistName"] = str(lists[0].get("name") or "")
            payload["label"] = f"Thêm {sym} vào “{payload['watchlistName']}”"
        else:
            payload["label"] = f"Thêm {sym} vào danh sách…"
        return [payload]

    # --- Proactive suggest ---
    ctx = context or {}
    bond = ctx.get("bond") if isinstance(ctx.get("bond"), dict) else {}
    candidates: list[str] = []
    screen_sym = str(ctx.get("symbol") or "").upper()
    if screen_sym and _valid_ticker(screen_sym, known_symbols):
        candidates.append(screen_sym)
    for s in bond.get("symbolsOfInterest") or []:
        sym = str(s).upper()
        if sym not in candidates and _valid_ticker(sym, known_symbols):
            candidates.append(sym)

    in_lists = _all_watchlist_symbols(lists)
    events = ctx.get("recentEvents") or []

    for sym in candidates[:5]:
        if sym in in_lists:
            continue
        mentions = _count_symbol_mentions(messages, sym)
        views = _count_detail_views(events, sym)
        if mentions >= 2 or views >= 2 or (mentions >= 1 and views >= 1):
            actions.append(
                {
                    "type": "suggest_add_symbol",
                    "symbol": sym,
                    "reason": "interest",
                    "label": f"Thêm {sym} vào danh sách",
                }
            )
            break

    return actions[:3]
