"""Unit tests for watchlist intent gating (no live Gemini)."""

from __future__ import annotations

from app.services.companion_intent import (
    WatchlistIntent,
    gate_actions_by_intent,
    intent_allows_tools,
    _parse_intent_payload,
)


def test_parse_execute_remove():
    intent = _parse_intent_payload(
        {
            "kind": "execute_remove",
            "symbols": ["fpt", "HAG", "vic"],
            "confidence": 0.9,
            "notes": "xóa 3 mã",
        }
    )
    assert intent.kind == "execute_remove"
    assert intent.symbols == ["FPT", "HAG", "VIC"]
    assert intent_allows_tools(intent)


def test_parse_propose_blocks_tools():
    intent = _parse_intent_payload(
        {"kind": "propose_change", "symbols": [], "confidence": 0.85}
    )
    assert intent.kind == "propose_change"
    assert not intent_allows_tools(intent)
    assert gate_actions_by_intent(
        [{"type": "remove_symbol", "symbol": "FPT"}],
        intent,
    ) == []


def test_parse_status_blocks_tools():
    intent = _parse_intent_payload(
        {"kind": "status_watchlist", "confidence": 0.95}
    )
    assert not intent_allows_tools(intent)


def test_gate_intersect_symbols():
    intent = WatchlistIntent(
        kind="execute_remove",
        symbols=["FPT", "HAG"],
        confidence=0.9,
    )
    actions = [
        {"type": "remove_symbol", "symbol": "FPT"},
        {"type": "remove_symbol", "symbol": "VIC"},
        {"type": "add_symbol", "symbol": "FPT"},
    ]
    gated = gate_actions_by_intent(actions, intent)
    assert [a["symbol"] for a in gated] == ["FPT"]


def test_gate_execute_add():
    intent = WatchlistIntent(
        kind="execute_add",
        symbols=["VCB"],
        confidence=0.8,
    )
    actions = [
        {"type": "add_symbol", "symbol": "VCB"},
        {"type": "remove_symbol", "symbol": "VCB"},
    ]
    gated = gate_actions_by_intent(actions, intent)
    assert len(gated) == 1
    assert gated[0]["type"] == "add_symbol"


def test_low_confidence_forced_chat():
    intent = _parse_intent_payload(
        {"kind": "execute_remove", "symbols": ["FPT"], "confidence": 0.2}
    )
    # _parse keeps kind; classify_watchlist_intent forces chat — simulate that rule:
    if intent.confidence < 0.35:
        intent = WatchlistIntent(kind="chat", confidence=intent.confidence, source="llm")
    assert intent.kind == "chat"
    assert not intent_allows_tools(intent)


def test_enrich_confirm_after_remove_suggestion():
    from app.services.companion_intent import (
        WatchlistIntent,
        enrich_intent_from_thread,
    )

    ctx = {
        "watchlists": {
            "activeId": "l1",
            "lists": [
                {
                    "id": "l1",
                    "name": "Demo",
                    "symbols": ["VCB", "FPT", "HAG", "VIC", "TCB"],
                }
            ],
        }
    }
    messages = [
        {"role": "user", "content": "List cồng kềnh, bỏ 3 mã kém"},
        {
            "role": "assistant",
            "content": "Mình gợi ý cắt FPT, HAG, VIC vì biến động kém. Bạn ok không?",
        },
        {"role": "user", "content": "đồng ý"},
    ]
    intent = WatchlistIntent(kind="chat", confidence=0.7, source="llm")
    enriched = enrich_intent_from_thread(intent, messages, ctx)
    assert enriched.kind == "execute_remove"
    assert set(enriched.symbols) == {"FPT", "HAG", "VIC"}


def test_actions_from_intent_symbols_remove():
    from app.services.companion_watchlist import actions_from_intent_symbols

    ctx = {
        "watchlists": {
            "activeId": "l1",
            "lists": [
                {
                    "id": "l1",
                    "name": "Demo",
                    "symbols": ["FPT", "HAG", "VIC", "VCB"],
                }
            ],
        }
    }
    actions = actions_from_intent_symbols(
        "execute_remove",
        ["FPT", "HAG", "VIC"],
        ctx,
        user_text="đồng ý",
    )
    assert len(actions) == 3
    assert all(a["type"] == "remove_symbol" for a in actions)
    assert {a["symbol"] for a in actions} == {"FPT", "HAG", "VIC"}


def test_kqkd_question_not_upgraded_to_remove():
    """Asking about fundamentals after watchlist talk must stay chat."""
    from app.services.companion_intent import (
        WatchlistIntent,
        enrich_intent_from_thread,
        guard_intent_info_as_chat,
    )

    ctx = {
        "watchlists": {
            "activeId": "l1",
            "lists": [
                {
                    "id": "l1",
                    "name": "Demo",
                    "symbols": ["VNM", "FPT", "VCB"],
                }
            ],
        }
    }
    messages = [
        {"role": "user", "content": "Watchlist hôm nay thế nào?"},
        {
            "role": "assistant",
            "content": "List khá ổn, VNM hơi giảm nhé, FPT vẫn xanh.",
        },
        {"role": "user", "content": "KQKD của VNM như thế nào?"},
    ]
    # Even if LLM wrongly said execute_remove:
    intent = WatchlistIntent(
        kind="execute_remove",
        symbols=["VNM"],
        confidence=0.8,
        source="llm",
    )
    enriched = enrich_intent_from_thread(intent, messages, ctx)
    assert enriched.kind == "chat"
    guarded = guard_intent_info_as_chat(enriched, "KQKD của VNM như thế nào?")
    assert guarded.kind == "chat"


def test_info_guard_blocks_execute_remove():
    from app.services.companion_intent import (
        WatchlistIntent,
        guard_intent_info_as_chat,
    )

    intent = WatchlistIntent(kind="execute_remove", symbols=["VNM"], confidence=0.9)
    out = guard_intent_info_as_chat(intent, "VNM định giá / KQKD?")
    assert out.kind == "chat"
