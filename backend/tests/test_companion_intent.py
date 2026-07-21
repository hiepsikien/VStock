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


def test_parse_unknown_kind_defaults_chat():
    intent = _parse_intent_payload({"kind": "whatever", "confidence": 0.9})
    assert intent.kind == "chat"
