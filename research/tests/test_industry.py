"""Industry return, valuation, rank, one-session lag, and the hold doors."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import date
from unittest import mock

from app import db, exits
from app.config import DEFAULT_UNIVERSE
from app.evaluate import compose
from app.exits import OpenPosition, fell_under_base, manage_position
from app.industries import industry_of, members, yearly_universe
from app.industry_note import (
    contain_rate,
    month_note_days,
    monthly_prompt,
    note_beats_gate,
    parse_picks,
    shift_months,
)
from app.industry_screen import (
    average_by_day,
    build_open_map,
    compound,
    dated_returns,
    find_runs,
    is_open,
    layer_counts,
    passes_layer,
    passes_stock,
    previous_session,
    rolling_compound,
)
from app.ingest import fetch_foreign_flow
from app.pattern import Pattern, Regime
from app.stock_select import balance_sheet_block, position_rank, shortlist
from app.valuation import cheap_versus, market_cap, trailing_pe, trailing_profit


def _bars(start: str, closes: list[float]) -> list[dict]:
    day = date.fromisoformat(start)
    rows = []
    for close in closes:
        rows.append(
            {
                "trade_date": day.isoformat(),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 1,
            }
        )
        day = date.fromordinal(day.toordinal() + 1)
    return rows


class IndustryMathTest(unittest.TestCase):
    def test_equal_weight_skips_a_missing_name(self) -> None:
        averaged = average_by_day(
            [
                [("2024-01-02", 0.10), ("2024-01-03", 0.00)],
                [("2024-01-02", -0.10)],
            ]
        )
        self.assertEqual(averaged[0], ("2024-01-02", 0.0))
        self.assertEqual(averaged[1][0], "2024-01-03")

    def test_compound_needs_a_full_window(self) -> None:
        self.assertIsNone(compound([0.01] * 59))
        self.assertAlmostEqual(compound([0.0] * 60), 0.0)

    def test_open_reads_excess_credit_and_lead(self) -> None:
        banks = members("bank", DEFAULT_UNIVERSE)
        self.assertGreaterEqual(len(banks), 3)
        self.assertTrue(
            is_open("bank", list(DEFAULT_UNIVERSE), excess=0.02, lead_return=None, credit_growth=0.05, regime_open=True)
        )
        self.assertFalse(
            is_open("bank", list(DEFAULT_UNIVERSE), excess=0.02, lead_return=None, credit_growth=-0.01, regime_open=True)
        )
        self.assertFalse(
            is_open("energy", list(DEFAULT_UNIVERSE), excess=0.02, lead_return=-0.01, credit_growth=None, regime_open=True)
        )
        self.assertIsNone(
            is_open("tech", ["FPT"], excess=0.02, lead_return=None, credit_growth=None, regime_open=True)
        )

    def test_gate_uses_the_previous_session(self) -> None:
        closes = [100.0] * 80 + [130.0]
        bars = _bars("2024-01-01", closes)
        universe = ["VCB", "CTG", "BID"]
        book = {symbol: bars for symbol in universe}
        # Credit stays positive so the only thing that can close the banks is the price window.
        credit = {bar["trade_date"]: 0.05 for bar in bars}
        opened = build_open_map(bars, book, universe, credit_by_day=credit)
        jump = bars[-1]["trade_date"]
        self.assertFalse(opened[("VCB", jump)])
        self.assertEqual(previous_session([bar["trade_date"] for bar in bars], jump), bars[-2]["trade_date"])

    def test_year_list_is_the_largest_hundred(self) -> None:
        caps = {f"S{index:03d}": float(index) for index in range(1, 121)}
        chosen = yearly_universe(caps)
        self.assertEqual(len(chosen), 100)
        self.assertEqual(chosen[0], "S120")
        self.assertNotIn("S001", chosen)

    def test_trailing_pe_waits_for_the_statement_lag(self) -> None:
        shares = [("2024-12-31", 10.0)]
        profits = [
            ("2024-03-31", 1.0),
            ("2024-06-30", 1.0),
            ("2024-09-30", 1.0),
            ("2024-12-31", 1.0),
        ]
        self.assertIsNone(market_cap(20.0, shares, date(2025, 1, 10)))
        cap = market_cap(20.0, shares, date(2025, 2, 14))
        self.assertEqual(cap, 200.0)
        self.assertEqual(trailing_pe(cap, trailing_profit(profits, date(2025, 2, 14))), 50.0)
        self.assertIsNone(trailing_profit([("2024-12-31", -1.0)] * 4, date(2025, 2, 14)))

    def test_cheapness_is_a_ratio(self) -> None:
        self.assertAlmostEqual(cheap_versus(10.0, 20.0), 0.5)
        self.assertIsNone(cheap_versus(None, 20.0))

    def test_shortlist_keeps_the_stronger_half_then_the_cheaper_names(self) -> None:
        rows = [
            {"symbol": "AAA", "block": None, "position": 1, "cheap_industry": 0.9, "cheap_self": 1.0},
            {"symbol": "BBB", "block": None, "position": 2, "cheap_industry": 0.4, "cheap_self": 1.2},
            {"symbol": "CCC", "block": None, "position": 3, "cheap_industry": 0.2, "cheap_self": 0.5},
            {"symbol": "DDD", "block": "nợ vay vượt trần", "position": 1, "cheap_industry": 0.1, "cheap_self": 0.1},
        ]
        self.assertEqual(shortlist(rows), ["BBB", "AAA"])
        self.assertEqual(position_rank("BBB", {"AAA": 10, "BBB": 8, "CCC": 1}, {"AAA": 1, "BBB": 9, "CCC": 3}), 1)

    def test_debt_blocks_and_a_weak_profit_year_does_not(self) -> None:
        points = {
            "NET_PROFIT_QR": [("2026-06-30", 10.0)],
            "NET_PROFIT_QR_GRYOY": [("2026-06-30", -0.2)],
            "DEBT_TO_EQUITY_AQ": [("2026-06-30", 2.5)],
            "OUTSTANDING_SHARES": [("2026-06-30", 100.0), ("2025-06-30", 100.0)],
        }
        self.assertEqual(balance_sheet_block("FPT", points), "nợ vay vượt trần")
        points["DEBT_TO_EQUITY_AQ"] = [("2026-06-30", 0.4)]
        self.assertIsNone(balance_sheet_block("FPT", points))

    def test_thresholds_are_fixed_before_the_confirm_window(self) -> None:
        self.assertFalse(passes_layer(0.68, 0.16, 0.10, 0.70, 0.16, 0.10))
        self.assertTrue(passes_layer(0.60, 0.20, 0.10, 0.60, 0.20, 0.10))
        self.assertFalse(passes_stock(0.49, 0.80, 0.01, 0.01))
        self.assertTrue(passes_stock(0.50, 0.50, 0.01, 0.01))

    def test_a_flat_climb_is_one_run_and_the_always_open_baseline_sees_it(self) -> None:
        closes = [100.0 * (1.004 ** index) for index in range(80)]
        bars = _bars("2024-01-01", closes)
        runs = find_runs(bars, "2024-01-01", "2024-03-01")
        self.assertEqual(len(runs), 1)
        counts = layer_counts({"AAA": bars}, lambda _symbol, _day: True, "2024-01-01", "2024-12-31")
        self.assertGreater(counts["recall"], 0)
        self.assertAlmostEqual(counts["precision"], counts["baseline"])

    def test_prompt_has_no_future_and_the_note_must_beat_the_gate(self) -> None:
        text = monthly_prompt("2025-06-02", {"Ngân hàng 60 phiên": "+8%"})
        self.assertIn("2025-06-02", text)
        self.assertNotIn("SHS", text)
        self.assertTrue(note_beats_gate(0.4, 0.3))
        self.assertFalse(note_beats_gate(0.3, 0.3))
        days = month_note_days(
            ["2023-02-01", "2023-02-14", "2023-02-15", "2023-03-01", "2023-04-03"],
            "2023-02-14",
            "2023-03-01",
        )
        self.assertEqual(days, ["2023-02-14", "2023-03-01"])
        self.assertEqual(shift_months("2023-02-14", 3), "2023-05-14")
        self.assertEqual(parse_picks("Danh sách: Ngân hàng\nLý do: dư nợ tăng, Điện chưa mở"), ["bank"])
        self.assertAlmostEqual(contain_rate(["bank", "energy", "bank"], {"bank"}), 2 / 3)

    def test_every_mapped_name_is_in_the_universe(self) -> None:
        for symbol in DEFAULT_UNIVERSE:
            self.assertIsNotNone(industry_of(symbol), symbol)


class FlowHistoryTest(unittest.TestCase):
    def test_pages_are_walked_and_a_repeated_page_stops(self) -> None:
        class Response:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class Client:
            def __init__(self):
                self.pages = []

            async def get(self, _url, params=None, headers=None):
                page = params["page"]
                self.pages.append(page)
                days = {1: "2021-01-04", 2: "2022-01-04", 3: "2023-01-04"}
                row = {
                    "tradingDate": days[page],
                    "netVol": page,
                    "netVal": page,
                    "totalRoom": 10,
                    "currentRoom": 4,
                }
                payload = {"data": [row]}
                if page == 1:
                    payload["totalPages"] = 3
                return Response(payload)

        client = Client()
        points = asyncio.run(fetch_foreign_flow(client, "VCB"))
        self.assertEqual(
            [day for day, _value in points["FOREIGN_NET_VOL"]],
            ["2021-01-04", "2022-01-04", "2023-01-04"],
        )
        self.assertEqual(client.pages, [1, 2, 3])

    def test_upsert_keeps_an_older_session(self) -> None:
        previous = os.environ.get("RESEARCH_DB_PATH")

        async def _run():
            folder = tempfile.mkdtemp()
            os.environ["RESEARCH_DB_PATH"] = os.path.join(folder, "research.db")
            await db.close_db()
            await db.init_db()
            await db.upsert_flow("VCB", {"FOREIGN_NET_VAL": [("2021-01-04", 10.0)]})
            await db.upsert_flow("VCB", {"FOREIGN_NET_VAL": [("2026-10-09", 20.0)]})
            stored = await db.flow("VCB")
            await db.close_db()
            return stored

        try:
            stored = asyncio.run(_run())
        finally:
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
        days = [day for day, _value in stored["FOREIGN_NET_VAL"]]
        self.assertEqual(days, ["2021-01-04", "2026-10-09"])


class HoldDoorTest(unittest.TestCase):
    def _position(self, sessions: int) -> OpenPosition:
        return OpenPosition(
            symbol="FPT",
            entry_date="2024-01-02",
            entry_price=100.0,
            stop=90.0,
            initial_stop=90.0,
            target1=120.0,
            sessions=sessions,
            base_ceiling=101.0,
        )

    def _bar(self) -> dict:
        return {"trade_date": "2024-06-01", "open": 100, "high": 101, "low": 95, "close": 100}

    def test_ceiling_exit_lasts_three_sessions_only_when_the_long_hold_is_on(self) -> None:
        early = self._position(2)
        self.assertTrue(fell_under_base(early, self._bar()))
        later = self._position(4)
        with mock.patch.object(exits, "INDUSTRY_HOLD_ENABLED", True):
            self.assertFalse(fell_under_base(later, self._bar()))
            self.assertTrue(later.open)

    def test_time_stop_stays_until_the_industry_exit_is_on(self) -> None:
        parked = self._position(30)
        reason = manage_position(parked, self._bar())
        self.assertIn("Tiền chết", reason or "")
        long_hold = self._position(30)
        with mock.patch.object(exits, "INDUSTRY_HOLD_ENABLED", True):
            self.assertIsNone(manage_position(long_hold, self._bar()))
            capped = self._position(132)
            self.assertIn("132", manage_position(capped, self._bar()) or "")

    def test_industry_field_does_not_change_entry_until_the_gate_is_enforced(self) -> None:
        from app import evaluate

        points = {
            "NET_SALES_QR": [("2026-06-30", 100.0)],
            "NET_SALES_QR_GRYOY": [("2026-06-30", 0.10)],
            "NET_PROFIT_QR": [("2026-06-30", 10.0)],
            "NET_PROFIT_QR_GRYOY": [("2026-06-30", 0.12)],
            "OPERATING_PROFIT_QR_GRYOY": [("2026-06-30", 0.08)],
            "CFO_TO_SALES_QR": [("2026-06-30", 0.15)],
            "DEBT_TO_EQUITY_AQ": [("2026-06-30", 0.40)],
            "OUTSTANDING_SHARES": [
                (day, 100.0)
                for day in ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"]
            ],
        }
        articles = [
            {
                "published_at": "2026-07-20",
                "symbols": ["FPT"],
                "kind": "earnings_release",
                "title": "FPT công bố báo cáo tài chính quý 2",
            }
        ]
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            points,
            articles,
            Regime(True, "mở"),
            Pattern(True, "Phá nền", 0.08, 90.0),
            require_clock=True,
            industry_name="tech",
            industry_open=False,
        )
        self.assertEqual(verdict.status, "Được vào")
        self.assertEqual(verdict.industry_name, "tech")
        with mock.patch.object(evaluate, "INDUSTRY_GATE_ENFORCED", True):
            blocked = compose(
                "FPT",
                date(2026, 10, 10),
                points,
                articles,
                Regime(True, "mở"),
                Pattern(True, "Phá nền", 0.08, 90.0),
                require_clock=True,
                industry_name="tech",
                industry_open=False,
            )
        self.assertEqual(blocked.status, "Theo dõi")
        self.assertIn("Ngành", blocked.summary)

    def test_supplement_historical_shares_merges_older_quarters(self) -> None:
        from app.ingest import _supplement_historical_shares

        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "data": [
                        {"fiscalDate": "2020-09-30", "numericValue": 20899554450000.0},
                        {"fiscalDate": "2020-12-31", "numericValue": 20899554450000.0},
                        {"fiscalDate": "2021-03-31", "numericValue": 20899554450000.0},
                    ]
                }

        class FakeClient:
            async def get(self, *args, **kwargs):
                return FakeResponse()

        points = {"OUTSTANDING_SHARES": [("2022-12-31", 2089955445.0)]}
        asyncio.run(_supplement_historical_shares(FakeClient(), "VNM", points))
        self.assertEqual(len(points["OUTSTANDING_SHARES"]), 4)
        self.assertEqual(points["OUTSTANDING_SHARES"][0], ("2020-09-30", 2089955445.0))
        self.assertEqual(points["OUTSTANDING_SHARES"][-1], ("2022-12-31", 2089955445.0))
