"""Unit tests for Vy five-core-question helpers (no live Gemini/network)."""

from __future__ import annotations

from app.services.companion import (
    _NEWS_GENERIC_RE,
    _fundamentals_focus_symbols,
    _news_item_payload,
    _slim_income_period,
    _watchlist_movers_for_chat,
)
from app.services.companion_intent import (
    WatchlistIntent,
    guard_intent_performance_as_chat,
)
from app.services.companion_packs import get_knowledge_pack
from app.services.gemini_companion import _format_context, build_quick_suggestions


def test_vy_pack_includes_fundamentals():
    pack = get_knowledge_pack("vy")
    assert "fundamentals" in pack.data_sources
    assert "quotes" in pack.data_sources


def test_guard_performance_forces_chat():
    intent = WatchlistIntent(kind="status_watchlist", confidence=0.9, source="llm")
    out = guard_intent_performance_as_chat(intent, "Watchlist hôm nay thế nào?")
    assert out.kind == "chat"


def test_guard_membership_stays_status():
    intent = WatchlistIntent(kind="status_watchlist", confidence=0.95, source="llm")
    out = guard_intent_performance_as_chat(intent, "Xóa xong chưa?")
    assert out.kind == "status_watchlist"


def test_guard_list_con_gi_stays_status():
    intent = WatchlistIntent(kind="status_watchlist", confidence=0.9)
    out = guard_intent_performance_as_chat(intent, "List còn gì?")
    assert out.kind == "status_watchlist"


def test_news_generic_re():
    assert _NEWS_GENERIC_RE.search("Có tin gì đáng chú ý không?")
    assert _NEWS_GENERIC_RE.search("Tin mới hôm nay")
    assert not _NEWS_GENERIC_RE.search("FPT định giá thế nào?")


def test_news_item_payload_keeps_summary():
    row = _news_item_payload(
        {
            "title": "FPT tăng mạnh",
            "summary": "Công ty công bố hợp đồng lớn " + ("x" * 250),
            "publishedAt": "2026-07-21T10:00:00Z",
            "id": "n1",
        },
        "FPT",
    )
    assert row is not None
    assert row["symbol"] == "FPT"
    assert len(row["summary"]) <= 200
    assert row["publishedAt"] == "2026-07-21T10:00:00Z"


def test_slim_income_period():
    slim = _slim_income_period(
        {
            "fiscalDate": "2025-12-31",
            "year": 2025,
            "quarter": None,
            "netRevenue": 1.2e12,
            "netIncome": 3.4e11,
            "extra": "drop",
        }
    )
    assert slim == {
        "fiscalDate": "2025-12-31",
        "year": 2025,
        "quarter": None,
        "netRevenue": 1.2e12,
        "netIncome": 3.4e11,
    }


def test_fundamentals_focus_prefers_msg_then_movers():
    focus = _fundamentals_focus_symbols(
        {"VCB"},
        {"symbol": "FPT", "watchlistSymbols": ["HAG", "VIC"]},
        [{"symbol": "HAG", "changePercent": -3}],
    )
    assert focus[0] == "VCB"
    assert "FPT" in focus
    assert "HAG" in focus
    assert len(focus) <= 3


def test_watchlist_movers_fallback_ranks_by_abs():
    ctx = {"watchlistSymbols": ["AAA", "BBB", "CCC"]}
    quote_map = {
        "AAA": {"price": 10, "changePercent": 0.5, "change": 0.05},
        "BBB": {"price": 20, "changePercent": -1.2, "change": -0.2},
        "CCC": {"price": 30, "changePercent": 0.1, "change": 0.03},
    }
    movers = _watchlist_movers_for_chat(ctx, quote_map)
    assert movers[0]["symbol"] == "BBB"
    assert len(movers) == 3


def test_format_context_includes_fundamentals_and_income():
    text = _format_context(
        {
            "liveFundamentals": [
                {
                    "symbol": "FPT",
                    "pe": 18.5,
                    "eps": 5.2,
                    "pb": 3.1,
                    "roe": 22.0,
                    "roa": 10.0,
                    "marketCap": "120T",
                }
            ],
            "liveIncome": [
                {
                    "symbol": "FPT",
                    "revenueLabel": "Doanh thu thuần",
                    "latestAnnual": {
                        "year": 2025,
                        "netRevenue": 6e13,
                        "netIncome": 8e12,
                    },
                    "lastQuarters": [
                        {
                            "year": 2026,
                            "quarter": 1,
                            "netRevenue": 1.5e13,
                            "netIncome": 2e12,
                        }
                    ],
                }
            ],
            "watchlistMovers": [
                {"symbol": "FPT", "price": 95.2, "changePercent": 2.4}
            ],
            "liveNews": [
                {
                    "symbol": "FPT",
                    "title": "FPT ký hợp đồng lớn",
                    "summary": "Giá trị hàng trăm triệu USD",
                    "publishedAt": "2026-07-21",
                }
            ],
        }
    )
    assert "[Định giá VStock" in text
    assert "PE 18.5" in text
    assert "[KQKD VStock" in text
    assert "LNST" in text
    assert "[Watchlist movers" in text
    assert "Giá trị hàng trăm triệu USD" in text


def test_quick_suggestions_cover_core_questions():
    chips = build_quick_suggestions(
        {
            "symbol": "FPT",
            "watchlistSymbols": ["FPT", "VCB"],
        },
        [],
    )
    assert len(chips) <= 4
    joined = " | ".join(chips)
    assert "Watchlist hôm nay thế nào?" in joined
    assert "FPT" in joined
    assert "Tin đáng chú ý?" in joined or "định giá" in joined.lower()
