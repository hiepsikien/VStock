"""Infer watchlist actions from companion chat (add symbol, create list, suggest)."""

from __future__ import annotations

import re
from typing import Any

from app.services.companion import _detect_sector_key, _sector_symbols_from_text
from app.services.gemini_companion import _VI_FALSE_TICKERS

_TICKER_RE = re.compile(r"\b([A-Za-z]{3})\b")

# Vietnamese words that look like 3-letter tickers in "thêm mã XXX"
_ADD_STOPWORDS = frozenset(
    {"MÃ", "MA", "VÀO", "VOA", "LIST", "THE", "CHO", "MỘT", "MOT", "VÀ", "VA"},
)

_ADD_PATTERNS = (
    re.compile(r"\bth[eê]m\s+(?:mã\s+)?([A-Za-z]{3})\b", re.I),
    re.compile(r"\badd\s+([A-Za-z]{3})\b", re.I),
    re.compile(r"\bcho\s+([A-Za-z]{3})\s+vào\b", re.I),
    re.compile(r"\bđưa\s+([A-Za-z]{3})\s+vào\b", re.I),
)

_REMOVE_PATTERNS = (
    re.compile(r"\bx[oó]a\s+(?:mã\s+)?([A-Za-z]{3})\b", re.I),
    re.compile(r"\bgỡ\s+(?:mã\s+)?([A-Za-z]{3})\b", re.I),
    re.compile(r"\bbỏ\s+(?:mã\s+)?([A-Za-z]{3})\b", re.I),
    re.compile(r"\bremove\s+([A-Za-z]{3})\b", re.I),
)

# Soft intent — does not require "khỏi/from" (covers "xóa giúp mình VCB, FPT").
_WANTS_REMOVE = re.compile(
    r"\b(x[oó]a|gỡ|remove|loại\s*bỏ)\b|\bbỏ\s+(?:mã\s+)?[A-Za-z]{3}\b",
    re.I,
)

_WANTS_CREATE = re.compile(
    r"\b(tạo|làm)\b.*\b(list|danh\s*sách|mảng)\b",
    re.I,
)

_WANTS_ADD = re.compile(
    r"\b(th[eê]m|add|cho|đưa)\b.*\b(vào|to)\b",
    re.I,
)

_TARGET_LIST_PATTERNS = (
    re.compile(r"\bvào\s+(?:danh\s*sách|list)\s+(.+?)(?:\s*$|[,.])", re.I),
    re.compile(r"\bkhỏi\s+(?:danh\s*sách|list)\s+(.+?)(?:\s*$|[,.])", re.I),
    re.compile(r"\b(?:danh\s*sách|list)\s+(.+?)(?:\s*$|[,.])", re.I),
)

_SECTOR_LIST_NAMES: dict[str, str] = {
    "bank": "Ngân hàng",
    "securities": "Chứng khoán",
    "real_estate": "Bất động sản",
    "energy": "Năng lượng",
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
    if s in _VI_FALSE_TICKERS or s in _ADD_STOPWORDS:
        return False
    if known is not None and s not in known:
        return False
    return True


def _extract_tickers(text: str) -> list[str]:
    found: list[str] = []
    for m in _TICKER_RE.finditer(text):
        sym = m.group(1).upper()
        if sym in found or sym in _VI_FALSE_TICKERS or sym in _ADD_STOPWORDS:
            continue
        found.append(sym)
    return found


def user_wants_remove(messages: list[dict] | str) -> bool:
    """True when latest user message is asking to delete/remove symbols."""
    text = messages if isinstance(messages, str) else _latest_user_text(messages)
    if not text:
        return False
    return bool(_WANTS_REMOVE.search(text))


def _ticker_candidates_from_arg(value: Any) -> list[str]:
    """Normalize symbol / symbols / 'VCB, FPT' into uppercase 3-letter codes."""
    out: list[str] = []

    def push(raw: str) -> None:
        for part in re.split(r"[,/\s|;]+", raw):
            sym = part.upper().strip()
            if len(sym) == 3 and sym.isalpha() and sym not in out:
                if sym in _VI_FALSE_TICKERS or sym in _ADD_STOPWORDS:
                    continue
                out.append(sym)

    if isinstance(value, str):
        push(value)
    elif isinstance(value, list):
        for item in value:
            push(str(item or ""))
    return out


def _extract_remove_symbols(
    user: str,
    lists: list[dict],
    known: set[str] | None,
) -> list[str]:
    """Tickers the user asked to remove that actually exist in some watchlist."""
    in_lists = _all_watchlist_symbols(lists)
    found: list[str] = []

    for pat in _REMOVE_PATTERNS:
        for m in pat.finditer(user):
            candidate = m.group(1).upper()
            if candidate in in_lists and candidate not in found:
                if known is None or candidate in known or candidate in in_lists:
                    found.append(candidate)

    # Also pick every valid ticker mentioned that is currently on a list.
    for sym in _extract_tickers(user):
        if sym in in_lists and sym not in found:
            found.append(sym)

    return found[:8]


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
        if n == q or q in n or n in q:
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


def _extract_create_list_name(text: str, sector: str | None) -> str:
    patterns = (
        re.compile(
            r"\b(?:list|danh\s*sách|mảng)\s+(?:mới\s+)?(.+?)(?:\s+với|\s*$)",
            re.I,
        ),
        re.compile(
            r"\b(?:tạo|làm)\b.*?\b(?:list|danh\s*sách|mảng)\s+(?:mới\s+)?(.+?)(?:\s+với|\s*$)",
            re.I,
        ),
    )
    for pat in patterns:
        m = pat.search(text)
        if not m:
            continue
        name = m.group(1).strip()
        name = re.sub(r"\s+\d+\s*mã.*$", "", name, flags=re.I).strip()
        name = re.sub(
            r"\s+(giúp|cho)\s+(mình|tôi|em).*$",
            "",
            name,
            flags=re.I,
        ).strip()
        if name and name.lower() not in ("mới", "new"):
            return name[:48]
    if sector:
        return _SECTOR_LIST_NAMES.get(sector, "Danh sách mới")
    return "Danh sách mới"


def _sector_symbols_from_context(
    context: dict | None,
    known: set[str] | None,
    limit: int,
) -> list[str]:
    ctx = context or {}
    ordered: list[str] = []
    seen: set[str] = set()
    candidates = [str(s).upper() for s in (ctx.get("sectorCandidates") or [])]
    candidate_set = set(candidates)

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
        sym = str(q.get("symbol") or "")
        if candidate_set and sym.upper() not in candidate_set:
            continue
        add(sym)
        if len(ordered) >= limit:
            return ordered[:limit]

    for sym in candidates:
        add(sym)
        if len(ordered) >= limit:
            return ordered[:limit]

    return ordered[:limit]


def _symbol_from_thread(
    messages: list[dict],
    known: set[str] | None,
) -> str | None:
    """When user omits ticker, borrow from recent assistant/user messages."""
    user = _latest_user_text(messages)
    for sym in reversed(_extract_tickers(user)):
        if _valid_ticker(sym, known):
            return sym

    for msg in reversed(messages):
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or msg.get("text") or "").strip()
        if not text:
            continue
        if role == "user" and text == user:
            continue
        for sym in reversed(_extract_tickers(text)):
            if _valid_ticker(sym, known):
                return sym
        if role == "assistant":
            break
    return None


async def _build_create_action_async(
    user: str,
    context: dict | None,
    sector: str | None,
    known: set[str] | None,
) -> dict[str, Any]:
    name = _extract_create_list_name(user, sector)
    if sector:
        name = _SECTOR_LIST_NAMES.get(sector, name)
    limit = _symbol_limit_from_text(user, default=4)
    syms: list[str] = []

    if sector:
        syms = _sector_symbols_from_context(context, known, limit)
        if not syms:
            syms = [
                s
                for s in (await _sector_symbols_from_text(user, limit=limit))[:limit]
                if _valid_ticker(s, known)
            ]

    syms_from_text = [
        t for t in _extract_tickers(user) if _valid_ticker(t, known)
    ]
    if syms_from_text:
        syms = syms_from_text[:limit]

    payload: dict[str, Any] = {
        "type": "create_watchlist",
        "name": name,
    }
    if syms:
        payload["symbols"] = syms
        payload["label"] = f"Tạo “{name}” ({', '.join(syms)})"
    else:
        payload["label"] = f"Tạo danh sách “{name}”"
    return payload


def _build_add_action(
    sym: str,
    lists: list[dict],
    user: str,
) -> dict[str, Any] | None:
    sym = sym.upper()
    target = _parse_target_list(user, lists)
    already_everywhere = all(
        sym in {str(s).upper() for s in (item.get("symbols") or [])}
        for item in lists
    )
    if already_everywhere:
        return None

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
    return payload


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

    # --- Create watchlist (sector or generic phrasing) ---
    if wants_create:
        action = await _build_create_action_async(user, context, sector, known_symbols)
        return [action]

    # --- Remove symbol(s) from list (before add / suggest) ---
    wants_remove = user_wants_remove(user)
    if wants_remove:
        remove_syms = _extract_remove_symbols(user, lists, known_symbols)
        if not remove_syms:
            # Intent clear but no ticker in text — try thread focus.
            focus = _symbol_from_thread(messages, known_symbols)
            if focus and focus in _all_watchlist_symbols(lists):
                remove_syms = [focus]
        remove_actions: list[dict[str, Any]] = []
        for sym in remove_syms:
            action = _build_remove_action(sym, lists, user)
            if action:
                remove_actions.append(action)
        # Never fall through to suggest_add when user asked to delete.
        return remove_actions[:8]

    # --- Add symbol to list ---
    sym: str | None = None
    for pat in _ADD_PATTERNS:
        m = pat.search(user)
        if not m:
            continue
        candidate = m.group(1).upper()
        if _valid_ticker(candidate, known_symbols):
            sym = candidate
            break

    if not sym and _WANTS_ADD.search(user):
        sym = _symbol_from_thread(messages, known_symbols)

    if sym:
        add_action = _build_add_action(sym, lists, user)
        if add_action:
            return [add_action]

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


async def resolve_tool_calls(
    calls: list[dict],
    context: dict | None,
    *,
    known_symbols: set[str] | None = None,
    messages: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Turn Gemini function calls into validated client actions."""
    lists = _watchlist_lists(context)
    if not lists or not calls:
        return []

    actions: list[dict[str, Any]] = []
    for call in calls[:8]:
        name = str(call.get("name") or "")
        args = call.get("args") if isinstance(call.get("args"), dict) else {}

        if name == "create_watchlist":
            action = await _resolve_create_tool(args, context, known_symbols)
            if action:
                actions.append(action)
        elif name == "add_symbol_to_watchlist":
            action = _resolve_add_tool(args, lists, known_symbols)
            if action:
                actions.append(action)
        elif name == "remove_symbol_from_watchlist":
            actions.extend(_resolve_remove_tool(args, lists))
        elif name == "suggest_add_symbol":
            action = _resolve_suggest_tool(args, lists, known_symbols)
            if action:
                actions.append(action)

    # Drop suggest/add when this turn is a remove request or already has removes.
    if any(a.get("type") == "remove_symbol" for a in actions) or (
        messages is not None and user_wants_remove(messages)
    ):
        actions = [
            a
            for a in actions
            if a.get("type") not in ("suggest_add_symbol", "add_symbol")
        ]

    # Dedupe remove/add by type+symbol+list
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for action in actions:
        key = (
            f"{action.get('type')}|{action.get('symbol')}|{action.get('watchlistId')}"
            f"|{action.get('name')}"
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped[:8]


async def _resolve_create_tool(
    args: dict,
    context: dict | None,
    known: set[str] | None,
) -> dict[str, Any] | None:
    raw_name = str(args.get("name") or "").strip()
    sector_key = str(args.get("sector") or "").strip().lower() or None
    if sector_key and sector_key not in _SECTOR_LIST_NAMES:
        sector_key = _detect_sector_key(sector_key) or sector_key
    if sector_key not in _SECTOR_LIST_NAMES:
        sector_key = _detect_sector_key(raw_name)

    name = raw_name or _SECTOR_LIST_NAMES.get(sector_key or "", "Danh sách mới")
    if sector_key:
        name = _SECTOR_LIST_NAMES.get(sector_key, name)

    syms: list[str] = []
    raw_syms = args.get("symbols")
    if isinstance(raw_syms, list):
        for s in raw_syms:
            sym = str(s).upper().strip()
            if _valid_ticker(sym, known) and sym not in syms:
                syms.append(sym)

    limit = 4
    if not syms and sector_key:
        syms = _sector_symbols_from_context(context, known, limit)
        if not syms:
            fetched = await _sector_symbols_from_text(raw_name or sector_key, limit=limit)
            syms = [s for s in fetched if _valid_ticker(s, known)][:limit]

    syms = syms[:12]
    payload: dict[str, Any] = {"type": "create_watchlist", "name": name[:48]}
    if syms:
        payload["symbols"] = syms
        payload["label"] = f"Tạo “{name}” ({', '.join(syms)})"
    else:
        payload["label"] = f"Tạo danh sách “{name}”"
    return payload


def _resolve_list_target(
    args: dict,
    lists: list[dict],
) -> dict | None:
    wid = str(args.get("watchlist_id") or "").strip()
    if wid:
        for item in lists:
            if str(item.get("id") or "") == wid:
                return item
    wname = str(args.get("watchlist_name") or "").strip()
    if wname:
        return _find_list_by_name(lists, wname)
    return None


def _resolve_add_tool(
    args: dict,
    lists: list[dict],
    known: set[str] | None,
) -> dict[str, Any] | None:
    sym = str(args.get("symbol") or "").upper().strip()
    if not _valid_ticker(sym, known):
        return None

    already_everywhere = all(
        sym in {str(s).upper() for s in (item.get("symbols") or [])}
        for item in lists
    )
    if already_everywhere:
        return None

    target = _resolve_list_target(args, lists)
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
    return payload


def _symbol_in_list(sym: str, item: dict) -> bool:
    return sym in {str(s).upper() for s in (item.get("symbols") or [])}


def _build_remove_action(
    sym: str,
    lists: list[dict],
    user: str,
) -> dict[str, Any] | None:
    sym = sym.upper()
    target = _parse_target_list(user, lists)
    in_any = any(_symbol_in_list(sym, item) for item in lists)
    if not in_any:
        return None

    payload: dict[str, Any] = {"type": "remove_symbol", "symbol": sym}
    if target and _symbol_in_list(sym, target):
        payload["watchlistId"] = str(target.get("id") or "")
        payload["watchlistName"] = str(target.get("name") or "")
        payload["label"] = f"Xóa {sym} khỏi “{payload['watchlistName']}”"
    elif len(lists) == 1 and _symbol_in_list(sym, lists[0]):
        payload["watchlistId"] = str(lists[0].get("id") or "")
        payload["watchlistName"] = str(lists[0].get("name") or "")
        payload["label"] = f"Xóa {sym} khỏi “{payload['watchlistName']}”"
    else:
        holders = [item for item in lists if _symbol_in_list(sym, item)]
        if len(holders) == 1:
            payload["watchlistId"] = str(holders[0].get("id") or "")
            payload["watchlistName"] = str(holders[0].get("name") or "")
            payload["label"] = f"Xóa {sym} khỏi “{payload['watchlistName']}”"
        else:
            payload["label"] = f"Xóa {sym} khỏi danh sách…"
    return payload


def _resolve_remove_tool(
    args: dict,
    lists: list[dict],
) -> list[dict[str, Any]]:
    symbols = _ticker_candidates_from_arg(args.get("symbols"))
    symbols.extend(
        s for s in _ticker_candidates_from_arg(args.get("symbol")) if s not in symbols
    )
    if not symbols:
        return []

    target = _resolve_list_target(args, lists)
    out: list[dict[str, Any]] = []
    for sym in symbols[:8]:
        if target and not _symbol_in_list(sym, target):
            continue
        if not target and not any(_symbol_in_list(sym, item) for item in lists):
            continue

        payload: dict[str, Any] = {"type": "remove_symbol", "symbol": sym}
        if target:
            payload["watchlistId"] = str(target.get("id") or "")
            payload["watchlistName"] = str(target.get("name") or "")
            payload["label"] = f"Xóa {sym} khỏi “{payload['watchlistName']}”"
        elif len(lists) == 1:
            payload["watchlistId"] = str(lists[0].get("id") or "")
            payload["watchlistName"] = str(lists[0].get("name") or "")
            payload["label"] = f"Xóa {sym} khỏi “{payload['watchlistName']}”"
        else:
            # Prefer the list that actually holds the symbol when ambiguous.
            holders = [item for item in lists if _symbol_in_list(sym, item)]
            if len(holders) == 1:
                payload["watchlistId"] = str(holders[0].get("id") or "")
                payload["watchlistName"] = str(holders[0].get("name") or "")
                payload["label"] = f"Xóa {sym} khỏi “{payload['watchlistName']}”"
            else:
                payload["label"] = f"Xóa {sym} khỏi danh sách…"
        out.append(payload)
    return out


def _resolve_suggest_tool(
    args: dict,
    lists: list[dict],
    known: set[str] | None,
) -> dict[str, Any] | None:
    sym = str(args.get("symbol") or "").upper().strip()
    if not _valid_ticker(sym, known):
        return None
    in_lists = _all_watchlist_symbols(lists)
    if sym in in_lists:
        return None
    return {
        "type": "suggest_add_symbol",
        "symbol": sym,
        "reason": str(args.get("reason") or "interest"),
        "label": f"Thêm {sym} vào danh sách",
    }
