from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import httpx
import yaml

from app import backtest, db, notify, pipeline
from app.config import BANKS, DEFAULT_UNIVERSE, INSURERS, SECURITIES
from app.evaluate import (
    METRIC_SECTIONS,
    SCORE_CEILINGS,
    UNPLACED_SECTION,
    compose,
    group_metrics,
    score_checklist,
    score_fundamentals,
    score_valuation,
)
from app.exits import blocking_filing, close_at, plan_exit, position_size, step_position
from app.flow import (
    ACCUMULATION,
    BLOCK,
    NEUTRAL,
    SUPPORT,
    WEAK,
    WAIT,
    FlowState,
    flow_flipped,
    flow_gate,
    flow_score,
    missing_flow,
)
from app.macro import macro_state
from app.notify import session_message, transition_lines
from app.paper import mark_positions, report as paper_report
from app.paper import row_return
from app.pattern import Pattern, Regime


def _bars(closes: list[float], volumes: list[float] | None = None) -> list[dict]:
    start = date(2026, 6, 1)
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "trade_date": (start + timedelta(days=index)).isoformat(),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": volumes[index] if volumes is not None else 1_000_000.0,
            }
        )
    return rows


async def _no_backfill(_client, _symbol, _points) -> bool:
    """Pipeline tests stay off the network: the statements source answers with nothing."""
    return True


def _flow_map(net_volumes: list[float], closes: list[float] | None = None) -> dict:
    closes = closes or [100.0] * len(net_volumes)
    dates = [bar["trade_date"] for bar in _bars(closes)]
    return {
        "FOREIGN_NET_VOL": list(zip(dates, net_volumes)),
        "FOREIGN_NET_VAL": list(zip(dates, [value * 1000 for value in net_volumes])),
    }


def _series(closes: list[float]) -> list[dict]:
    return [
        {"trade_date": bar["trade_date"], "close": value}
        for bar, value in zip(_bars(closes), closes)
    ]


class FlowGateTest(unittest.TestCase):
    def test_quiet_price_with_foreign_buying_is_accumulation(self) -> None:
        state = flow_gate(_flow_map([200_000.0] * 10), _bars([100.0] * 10))
        self.assertEqual(state.level, ACCUMULATION)
        self.assertEqual(state.state, "Mở")
        self.assertEqual(state.priority, 2)
        self.assertIn("Gom hàng", state.reason)

    def test_rising_price_sold_by_foreigners_is_a_trap(self) -> None:
        closes = [100.0 + index for index in range(10)]
        points = _flow_map([-200_000.0] * 10, closes)
        state = flow_gate(points, _bars(closes))
        self.assertEqual(state.level, BLOCK)
        self.assertEqual(state.state, WAIT)
        self.assertIn("Nghi bán vào đà tăng", state.reason)
        self.assertTrue(flow_flipped(points, _bars(closes)))

    def test_falling_price_sold_by_foreigners_is_weak(self) -> None:
        closes = [110.0 - index for index in range(10)]
        state = flow_gate(_flow_map([-200_000.0] * 10, closes), _bars(closes))
        self.assertEqual(state.level, WEAK)
        self.assertEqual(state.state, WAIT)

    def test_buying_into_a_rally_supports_the_trade(self) -> None:
        closes = [100.0 + index for index in range(10)]
        state = flow_gate(_flow_map([200_000.0] * 10, closes), _bars(closes))
        self.assertEqual(state.level, SUPPORT)
        self.assertEqual(state.priority, 1)

    def test_small_net_flow_stays_neutral(self) -> None:
        state = flow_gate(_flow_map([10_000.0] * 10), _bars([100.0] * 10))
        self.assertEqual(state.level, NEUTRAL)
        self.assertEqual(state.priority, 0)

    def test_thin_coverage_returns_missing(self) -> None:
        bars = _bars([100.0] * 10)
        thin = {"FOREIGN_NET_VOL": [("2026-06-01", 1.0)]}
        self.assertEqual(flow_gate(thin, bars).level, "missing")
        self.assertEqual(flow_gate({}, bars).state, missing_flow().state)

    def test_room_note_is_attached(self) -> None:
        bars = _bars([100.0] * 10)
        points = _flow_map([200_000.0] * 10)
        points["FOREIGN_ROOM_RATIO"] = [(bar["trade_date"], 0.02) for bar in bars]
        state = flow_gate(points, bars)
        self.assertIn("Room ngoại gần cạn", state.reason)
        self.assertAlmostEqual(state.room_ratio or 0, 0.02)

    def test_scores_follow_the_levels(self) -> None:
        self.assertEqual(flow_score(ACCUMULATION), 25)
        self.assertEqual(flow_score(BLOCK), 0)
        self.assertEqual(flow_score("unknown"), 12)


class MacroTest(unittest.TestCase):
    def test_dollar_and_fx_above_the_average_blocks(self) -> None:
        rising = [100.0 + index * 0.5 for index in range(25)]
        macro = macro_state(
            {"DXY": _series(rising), "USDVND": _series(rising), "SP500": _series(rising)}
        )
        self.assertTrue(macro.block)
        self.assertIs(macro.risk, True)
        self.assertIn("Chưa mở vị thế mới", macro.reason)

    def test_flat_cross_market_is_neutral(self) -> None:
        flat = _series([100.0] * 25)
        macro = macro_state({"DXY": flat, "USDVND": flat, "SP500": flat})
        self.assertFalse(macro.block)
        self.assertIs(macro.risk, False)
        self.assertIn("trung tính", macro.reason)

    def test_missing_data_does_not_block(self) -> None:
        macro = macro_state({})
        self.assertIsNone(macro.risk)
        self.assertFalse(macro.block)

    def test_a_blocking_leg_that_did_not_load_leaves_the_gate_unscored(self) -> None:
        """Cặp chặn là đô la và tỷ giá: thiếu tỷ giá thì cổng chưa chấm, không phải trung tính."""
        rising = [100.0 + index * 0.5 for index in range(25)]
        macro = macro_state({"DXY": _series(rising), "SP500": _series(rising)})
        self.assertIsNone(macro.risk)
        self.assertFalse(macro.block)
        self.assertIn("Tỷ giá USD/VND", macro.reason)
        self.assertIn("đô la tăng", macro.reason)
        self.assertIn(("Tỷ giá USD/VND", "chưa tải được"), macro.metrics)

    def test_a_warning_leg_that_did_not_load_still_scores(self) -> None:
        """Đủ hai chân chặn thì cổng chấm được; thiếu S&P 500 hay dầu chỉ là thiếu cảnh báo."""
        flat = _series([100.0] * 25)
        macro = macro_state({"DXY": flat, "USDVND": flat})
        self.assertIs(macro.risk, False)
        self.assertFalse(macro.block)

    def test_weak_index_alone_warns_without_blocking(self) -> None:
        falling = [120.0 - index * 0.4 for index in range(25)]
        flat = _series([100.0] * 25)
        macro = macro_state({"DXY": flat, "USDVND": flat, "SP500": _series(falling)})
        self.assertFalse(macro.block)
        self.assertIs(macro.risk, True)
        self.assertIn("S&P 500", macro.reason)



_REPORT = "2026-06-30"
_QUARTERS = ("2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30")


def _flat(code: str, late: float, early: float) -> list[tuple[str, float]]:
    return [(day, early if day != _REPORT else late) for day in _QUARTERS]


def _checklist_points(**overrides) -> dict:
    points: dict = {
        "NET_SALES_QR": [(_REPORT, 100.0)],
        "NET_SALES_QR_GRYOY": [(_REPORT, 0.10)],
        "NET_PROFIT_QR": [(_REPORT, 10.0)],
        "NET_PROFIT_QR_GRYOY": [(_REPORT, 0.12)],
        "OPERATING_PROFIT_QR_GRYOY": [(_REPORT, 0.08)],
        "CFO_TO_SALES_QR": _flat("cfo", 0.15, 0.20),
        "DEBT_TO_EQUITY_AQ": _flat("debt", 0.40, 0.50),
        "TOTAL_ASSETS_AQ": _flat("assets", 1000.0, 800.0),
        "CURRENT_RATIO_AQ": _flat("current", 1.50, 1.40),
        "INVENTORY_AQ": _flat("inventory", 1000.0, 500.0),
        "OUTSTANDING_SHARES": [(day, 100.0) for day in _QUARTERS],
    }
    points.update(overrides)
    return points


class ChecklistTest(unittest.TestCase):
    def test_full_checklist_scores_eight_items(self) -> None:
        scored = score_fundamentals("FPT", _checklist_points())
        self.assertEqual(scored.label, "Đạt")
        self.assertEqual(scored.f_score, 6)
        self.assertEqual(scored.f_score_max, 8)
        self.assertIn("Lợi nhuận tăng nhưng biên dòng tiền thu hẹp", scored.warnings)
        self.assertIn("Tồn kho phình nhanh hơn doanh thu", scored.warnings)

    def test_too_few_items_means_no_score(self) -> None:
        score, available, _failures, _warnings = score_checklist(
            {"NET_SALES_QR": [(_REPORT, 100.0)]},
            _REPORT,
            profit=10.0,
            profit_yoy=0.1,
            sales=100.0,
            sales_yoy=0.1,
            cfo_margin=0.15,
            debt_ratio=0.4,
            share_growth=0.0,
        )
        self.assertIsNone(score)
        self.assertEqual(available, 4)

    def test_weak_checklist_rejects_the_name(self) -> None:
        points = _checklist_points(
            NET_PROFIT_QR_GRYOY=[(_REPORT, 0.02)],
            NET_SALES_QR_GRYOY=[(_REPORT, 0.05)],
            CFO_TO_SALES_QR=_flat("cfo", 0.05, 0.20),
            CURRENT_RATIO_AQ=_flat("current", 1.30, 1.40),
            DEBT_TO_EQUITY_AQ=_flat("debt", 0.60, 0.50),
        )
        scored = score_fundamentals("FPT", points)
        self.assertEqual(scored.label, "Không đạt")
        self.assertEqual(scored.f_score, 3)
        self.assertIn("điểm cơ bản yếu 3/8", scored.reason)


def _services_points(debt: float) -> dict:
    return {
        "NET_SALES_QR": [(_REPORT, 100.0)],
        "NET_SALES_QR_GRYOY": [(_REPORT, 0.10)],
        "NET_PROFIT_QR": [(_REPORT, 10.0)],
        "NET_PROFIT_QR_GRYOY": [(_REPORT, 0.12)],
        "OWNERS_EQUITY_AQ": [(day, 100.0) for day in _QUARTERS],
        "DEBT_TO_EQUITY_AQ": [(day, debt) for day in _QUARTERS],
        "OUTSTANDING_SHARES": [(day, 100.0) for day in _QUARTERS],
    }


class ServicesTemplateTest(unittest.TestCase):
    def test_broker_leverage_is_not_blocked(self) -> None:
        scored = score_fundamentals("SSI", _services_points(3.5))
        self.assertEqual(scored.label, "Đạt")
        self.assertEqual(scored.template, "securities")

    def test_insurer_has_its_own_debt_ceiling(self) -> None:
        over = score_fundamentals("BVH", _services_points(3.5))
        self.assertEqual(over.label, "Không đạt")
        self.assertIn("vượt 3.0", over.reason)
        under = score_fundamentals("BVH", _services_points(2.0))
        self.assertEqual(under.label, "Đạt")
        self.assertEqual(under.template, "insurer")

    def test_services_template_still_needs_its_own_numbers(self) -> None:
        scored = score_fundamentals("SSI", {"NET_PROFIT_QR": [(_REPORT, 10.0)]})
        self.assertEqual(scored.label, "Chưa đủ số")
        self.assertEqual(scored.template, "securities")

    def test_valuation_ceiling(self) -> None:
        self.assertEqual(score_valuation({"pe": 35.0}).label, "Không đạt")
        self.assertEqual(score_valuation({"pe": 12.0}).label, "Đạt")
        self.assertEqual(score_valuation({"pe": None}).label, "Chưa có số")
        self.assertEqual(score_valuation(None).label, "Chưa có số")


class ExitPlanTest(unittest.TestCase):
    def test_stop_uses_the_base_low(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90), 2.0)
        self.assertAlmostEqual(pos.stop, 90.0)
        self.assertAlmostEqual(pos.target1, 110.0)

    def test_stop_falls_back_to_atr_then_to_a_fraction(self) -> None:
        self.assertAlmostEqual(plan_exit("FPT", "2026-06-01", 100.0, None, 2.5).stop, 95.0)
        self.assertAlmostEqual(plan_exit("FPT", "2026-06-01", 100.0, None, None).stop, 93.0)

    def test_stop_is_checked_before_the_target(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        bar = {"trade_date": "2026-06-02", "open": 101.0, "high": 115.0, "low": 88.0, "close": 95.0}
        self.assertEqual(step_position(pos, bar), "Chạm dừng lỗ")
        self.assertAlmostEqual(pos.exit_price or 0, 90.0)
        self.assertFalse(pos.tp1_done)

    def test_gap_through_the_stop_fills_at_the_open(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        bar = {"trade_date": "2026-06-02", "open": 85.0, "high": 86.0, "low": 84.0, "close": 85.0}
        step_position(pos, bar)
        self.assertAlmostEqual(pos.exit_price or 0, 85.0)

    def test_first_target_books_a_third_and_moves_the_stop_to_breakeven(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        bar = {"trade_date": "2026-06-02", "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0}
        self.assertIsNone(step_position(pos, bar))
        self.assertTrue(pos.tp1_done)
        self.assertAlmostEqual(pos.booked_fraction, 1 / 3)
        self.assertGreater(pos.stop, 100.0)
        mark = {"trade_date": "2026-06-03", "open": 110.0, "high": 116.0, "low": 109.0, "close": 115.0}
        step_position(pos, mark)
        expected = (110 / 100 - 1) / 3 + (115 / 100 - 1) * 2 / 3
        self.assertAlmostEqual(pos.unrealised(), expected, places=6)

    def test_trailing_stop_follows_the_average_after_the_first_target(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        pos.tp1_done = True
        pos.booked_fraction = 1 / 3
        bar = {"trade_date": "2026-06-02", "open": 108.0, "high": 109.0, "low": 107.0, "close": 108.0}
        step_position(pos, bar, ma20=106.0, atr14=2.0)
        self.assertAlmostEqual(pos.stop, 105.0)

    def test_a_trailing_level_cannot_fill_on_the_bar_it_was_read_from(self) -> None:
        """MA20 và ATR chỉ biết sau giờ đóng cửa, nên mức kéo chỉ canh được từ phiên sau."""
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        pos.tp1_done = True
        pos.booked_fraction = 1 / 3
        # The low of 101 never reached the 90 that rested in the book, even though this bar's own
        # MA20 draws a stop at 113: the level is only known once the session has closed.
        bar = {"trade_date": "2026-06-02", "open": 103.0, "high": 110.0, "low": 101.0, "close": 109.0}
        self.assertIsNone(step_position(pos, bar, ma20=114.0, atr14=2.0))
        self.assertTrue(pos.open)
        self.assertAlmostEqual(pos.stop, 113.0)
        # The next session opens with 113 in the book, so a low of 105 reaches it and fills at the open.
        after = {"trade_date": "2026-06-03", "open": 108.0, "high": 109.0, "low": 105.0, "close": 107.0}
        self.assertEqual(step_position(pos, after, ma20=114.0, atr14=2.0), "Chạm dừng lỗ")
        self.assertAlmostEqual(pos.exit_price or 0, 108.0)

    def test_time_stop_closes_dead_money(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        bar = {"trade_date": "2026-07-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}
        reason = None
        for _session in range(30):
            reason = step_position(pos, bar)
        self.assertEqual(reason, "Tiền chết 30 phiên")

    def test_hard_cap_closes_the_slot(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        pos.tp1_done = True
        bar = {"trade_date": "2026-08-01", "open": 120.0, "high": 121.0, "low": 119.0, "close": 120.0}
        reason = None
        for _session in range(60):
            reason = step_position(pos, bar)
        self.assertEqual(reason, "Đủ 60 phiên")

    def test_forced_close_uses_the_close(self) -> None:
        pos = plan_exit("FPT", "2026-06-01", 100.0, Pattern(True, "Nền", 0.05, 90))
        bar = {"trade_date": "2026-06-02", "open": 100.0, "high": 101.0, "low": 99.0, "close": 102.0}
        close_at(pos, bar, "Dòng tiền ngoại đảo chiều")
        self.assertEqual(pos.exit_reason, "Dòng tiền ngoại đảo chiều")
        self.assertAlmostEqual(pos.exit_price or 0, 102.0)

    def test_size_risks_one_percent_and_caps_at_thirty_five(self) -> None:
        self.assertAlmostEqual(position_size(1.0, 100.0, 90.0), 0.1)
        self.assertAlmostEqual(position_size(1.0, 100.0, 60.0), 0.025)
        self.assertAlmostEqual(position_size(1.0, 100.0, 99.0), 0.35)
        self.assertEqual(position_size(1.0, 100.0, 100.0), 0.0)

    def test_blocking_filing_only_counts_after_entry(self) -> None:
        articles = [
            {"published_at": "2026-05-30", "kind": "suspension", "title": "Cũ"},
            {"published_at": "2026-06-05", "kind": "audit_exception", "title": "Ngoại trừ"},
        ]
        self.assertEqual(blocking_filing(articles, "2026-06-01"), "Ngoại trừ")
        self.assertIsNone(blocking_filing(articles, "2026-06-06"))

    def test_blocking_filing_stops_at_the_session_being_walked(self) -> None:
        articles = [
            {"published_at": "2026-06-05", "kind": "audit_exception", "title": "Ngoại trừ"},
        ]
        # A walk through history must not read a filing published after its session.
        self.assertIsNone(blocking_filing(articles, "2026-06-01", "2026-06-04"))
        self.assertEqual(blocking_filing(articles, "2026-06-01", "2026-06-05"), "Ngoại trừ")
        self.assertEqual(blocking_filing(articles, "2026-06-01", "2026-06-30"), "Ngoại trừ")



def _corporate_points() -> dict:
    values = {
        "NET_SALES_QR": 100.0,
        "NET_SALES_QR_GRYOY": 0.10,
        "NET_PROFIT_QR": 10.0,
        "NET_PROFIT_QR_GRYOY": 0.12,
        "OPERATING_PROFIT_QR_GRYOY": 0.08,
        "CFO_TO_SALES_QR": 0.15,
        "DEBT_TO_EQUITY_AQ": 0.40,
    }
    points = {code: [(_REPORT, value)] for code, value in values.items()}
    points["OUTSTANDING_SHARES"] = [(day, 100.0) for day in _QUARTERS]
    return points


def _earnings() -> dict:
    return {
        "published_at": "2026-07-20",
        "symbols": ["FPT"],
        "kind": "earnings_release",
        "title": "FPT công bố báo cáo tài chính quý 2",
    }


def _diluted_corporate_points() -> dict:
    """Shares and equity up together over the year, so the quarter counts as dilution."""
    points = _corporate_points()
    points["OUTSTANDING_SHARES"] = [(day, 100.0 if day == _QUARTERS[0] else 110.0) for day in _QUARTERS]
    points["OWNERS_EQUITY_AQ"] = [(day, 100.0 if day == _QUARTERS[0] else 110.0) for day in _QUARTERS]
    return points


def _bank_points() -> dict:
    return {
        "NET_PROFIT_QR": [(_REPORT, 10.0)],
        "NET_PROFIT_QR_GRYOY": [(_REPORT, 0.12)],
        "BAD_LOANS_RATIO_AQ": [(day, 0.02) for day in _QUARTERS],
        "PROVISION_BAD_LOANS_AQ": [(day, 1.40) for day in _QUARTERS],
        "OWNERS_EQUITY_AQ": [(day, 100.0) for day in _QUARTERS],
        "CUSTOMER_LOANS_AQ_GRYOY": [(day, 0.15) for day in _QUARTERS],
    }


def _ready_pattern() -> Pattern:
    return Pattern(True, "Phá nền", 0.08, 90)


class ComposeTest(unittest.TestCase):
    def _compose(self, **kwargs):
        return compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [_earnings()],
            Regime(True, "VN-Index trên MA200", 1200, 1100),
            kwargs.pop("pattern", _ready_pattern()),
            require_clock=True,
            **kwargs,
        )

    def test_entry_survives_missing_flow_and_valuation(self) -> None:
        verdict = self._compose()
        self.assertEqual(verdict.status, "Được vào")
        self.assertEqual(verdict.flow_state, "Chưa có")
        self.assertEqual(verdict.valuation_label, "Chưa có số")

    def test_flow_block_downgrades_an_entry(self) -> None:
        flow = FlowState(WAIT, BLOCK, "Nghi bán vào đà tăng", net_volume=-1.0)
        verdict = self._compose(flow=flow)
        self.assertEqual(verdict.status, "Chờ")
        self.assertEqual(verdict.summary, "Nghi bán vào đà tăng")
        self.assertEqual(verdict.priority, 0)

    def test_accumulation_flow_raises_the_priority(self) -> None:
        flow = FlowState("Mở", ACCUMULATION, "Gom hàng", priority=2)
        verdict = self._compose(flow=flow)
        self.assertEqual(verdict.status, "Được vào")
        self.assertEqual(verdict.priority, 2)

    def test_macro_that_did_not_load_does_not_open_an_entry(self) -> None:
        """A feed that is down is not a green light: the layer has no numbers, so no entry."""
        verdict = self._compose(macro=macro_state({}))
        self.assertEqual(verdict.status, "Theo dõi")
        self.assertIn("Vĩ mô chưa có số", verdict.summary)
        self.assertFalse(verdict.macro_block)

    def test_a_blocking_leg_that_did_not_load_downgrades_an_entry(self) -> None:
        """Chặn bằng cả cặp đô la và tỷ giá, nên thiếu một chân cũng là chưa có số."""
        rising = [100.0 + index * 0.5 for index in range(25)]
        verdict = self._compose(macro=macro_state({"DXY": _series(rising)}))
        self.assertEqual(verdict.status, "Theo dõi")
        self.assertIn("Vĩ mô chưa có số", verdict.summary)
        self.assertFalse(verdict.macro_block)

    def test_macro_block_downgrades_an_entry(self) -> None:
        macro = macro_state({})
        blocked = macro.__class__(True, True, "Vĩ mô căng: tỷ giá trên MA20", [])
        verdict = self._compose(macro=blocked)
        self.assertEqual(verdict.status, "Theo dõi")
        self.assertTrue(verdict.macro_block)
        self.assertIn("Vĩ mô chặn vào", verdict.summary)
        self.assertIsNone(macro.risk)

    def test_valuation_over_the_ceiling_is_rejected(self) -> None:
        verdict = self._compose(valuation={"pe": 40.0})
        self.assertEqual(verdict.status, "Loại")
        self.assertIn("Định giá", verdict.summary)

    def test_score_parts_add_up_to_the_total(self) -> None:
        verdict = self._compose()
        self.assertEqual(sum(value for _label, value in verdict.score_parts), verdict.score)
        self.assertEqual(verdict.score, 55)
        self.assertFalse(verdict.score_ok)

    def test_every_score_bar_has_a_ceiling_of_its_own(self) -> None:
        """The page draws each bar against SCORE_CEILINGS, so every part must appear there."""
        verdict = self._compose()
        labels = [label for label, _value in verdict.score_parts]
        self.assertEqual(labels, list(SCORE_CEILINGS))
        for label, value in verdict.score_parts:
            self.assertLessEqual(value, SCORE_CEILINGS[label], label)

    def test_metrics_carry_every_layer(self) -> None:
        flow = FlowState("Mở", SUPPORT, "Ủng hộ", metrics=[("Dòng tiền ngoại", "mua ròng")])
        verdict = self._compose(
            valuation={"pe": 12.0, "pb": 1.5, "roe": 0.18, "updated_at": "2026-10-09T00:00:00"},
            flow=flow,
        )
        labels = [label for label, _value in verdict.metrics]
        self.assertIn("Dòng tiền ngoại", labels)
        self.assertIn("P/E", labels)
        self.assertIn("Điểm cơ bản (F-Score)", labels)

    def test_sections_rebuild_the_flat_numbers_of_a_verdict(self) -> None:
        """The store files a row written without groups back into sections by label."""
        rising = [100.0 + index * 0.5 for index in range(25)]
        macro = macro_state({"DXY": _series(rising), "USDVND": _series(rising), "SP500": _series(rising)})
        verdict = self._compose(
            valuation={"pe": 12.0, "pb": 1.5, "roe": 0.18, "updated_at": "2026-10-09T00:00:00"},
            flow=flow_gate(_flow_map([200_000.0] * 10), _bars([100.0] * 10)),
            macro=macro,
        )
        rebuilt = [(title, [tuple(metric) for metric in rows]) for title, rows in group_metrics(verdict.metrics)]
        composed = [(title, [tuple(metric) for metric in rows]) for title, rows in verdict.metric_groups]
        self.assertEqual(rebuilt, composed)
        self.assertEqual([title for title, _rows in rebuilt], [title for title, _labels in METRIC_SECTIONS])

    def test_every_number_a_producer_emits_has_a_section(self) -> None:
        """A label no section claims would be filed under the leftover bucket instead of its layer."""
        corporate = score_fundamentals("FPT", _corporate_points())
        diluted = score_fundamentals("FPT", _diluted_corporate_points())
        bank = score_fundamentals("VCB", _bank_points())
        broker = score_fundamentals("SSI", _services_points(3.5))
        insurer = score_fundamentals("BVH", _services_points(2.0))
        valuation = score_valuation({"pe": 12.0, "pb": 1.5, "roe": 0.18, "updated_at": "2026-10-09"})
        flow = FlowState("Mở", SUPPORT, "Ủng hộ", metrics=[("Dòng tiền ngoại", "mua ròng")])
        macro = macro_state({"DXY": _series([100.0] * 25), "USDVND": _series([100.0] * 25)})
        verdict = self._compose(flow=flow, macro=macro)

        labels = {
            label
            for source in (corporate, diluted, bank, broker, insurer, valuation, flow, macro)
            for label, _value in source.metrics
        }
        labels |= {label for label, _value in verdict.metrics}
        # A conditional number, so pin that the fixture still reaches the branch that emits it.
        self.assertIn("Tăng LNST trên mỗi cổ phiếu", {label for label, _value in diluted.metrics})
        # A claim of a section is all this checks, so the value is a placeholder.
        grouped = group_metrics([(label, "") for label in sorted(labels)])
        titles = [title for title, _rows in grouped]
        self.assertNotIn(UNPLACED_SECTION, titles)
        self.assertEqual(titles, [title for title, _labels in METRIC_SECTIONS])


class NotifyTest(unittest.TestCase):
    def _item(self, status: str, score: int = 80) -> dict:
        return {
            "symbol": "FPT",
            "status": status,
            "score": score,
            "stop_price": 90.0,
            "summary": "Nền đã siết",
        }

    def test_new_entry_is_announced(self) -> None:
        lines = transition_lines([self._item("Theo dõi")], [self._item("Được vào")])
        self.assertEqual(len(lines), 1)
        self.assertIn("Được vào", lines[0])
        self.assertIn("90.00", lines[0])

    def test_rejection_is_announced(self) -> None:
        lines = transition_lines([self._item("Chờ")], [self._item("Loại")])
        self.assertIn("Loại", lines[0])

    def test_unchanged_session_sends_nothing(self) -> None:
        current = [self._item("Theo dõi")]
        self.assertEqual(transition_lines(current.copy(), current), [])
        self.assertIsNone(session_message(current, current.copy(), "2026-10-10"))

    def test_message_has_a_header(self) -> None:
        message = session_message(
            [self._item("Được vào")], [self._item("Theo dõi")], "2026-10-10"
        )
        self.assertIsNotNone(message)
        self.assertTrue((message or "").startswith("VStock research 2026-10-10"))

    def test_a_stray_bracket_in_a_filing_title_is_escaped(self) -> None:
        """parse_mode is HTML, so a `<` in a title would make the whole session 400 away."""
        item = self._item("Loại")
        item["summary"] = "Đình chỉ <b>niêm yết</b> & xét lại"
        lines = transition_lines([self._item("Chờ")], [item])
        self.assertTrue(lines[0].startswith("<b>FPT</b>"))
        self.assertIn("&lt;b&gt;", lines[0])
        self.assertNotIn("<b>niêm yết", lines[0])

    def test_a_failed_send_does_not_log_the_bot_token(self) -> None:
        """The httpx message carries the request URL, and the URL carries the token."""
        request = httpx.Request("POST", "https://api.telegram.org/botSECRET/sendMessage")
        response = httpx.Response(400, request=request)
        error = httpx.HTTPStatusError(
            "Client error '400 Bad Request' for url 'https://api.telegram.org/botSECRET/sendMessage'",
            request=request,
            response=response,
        )

        class _Client:
            async def __aenter__(self) -> "_Client":
                return self

            async def __aexit__(self, *_args) -> bool:
                return False

            async def post(self, *_args, **_kwargs) -> httpx.Response:
                raise error

        with mock.patch.dict(
            os.environ, {"TELEGRAM_BOT_TOKEN": "SECRET", "TELEGRAM_CHAT_ID": "1"}
        ), mock.patch.object(notify.httpx, "AsyncClient", lambda **_kwargs: _Client()), self.assertLogs(
            "app.notify", level="WARNING"
        ) as logs:
            sent = asyncio.run(notify.send("xin chào"))
        self.assertFalse(sent)
        self.assertIn("400", "\n".join(logs.output))
        self.assertNotIn("SECRET", "\n".join(logs.output))

    def test_row_return_mixes_booked_and_open_parts(self) -> None:
        row = {
            "entry_price": 100.0,
            "booked_fraction": 1 / 3,
            "realised": (111 / 100 - 1) / 3,
            "last_price": 115.0,
            "exit_price": None,
        }
        self.assertAlmostEqual(row_return(row), (111 / 100 - 1) / 3 + (115 / 100 - 1) * 2 / 3)
        row["exit_price"] = 90.0
        self.assertAlmostEqual(row_return(row), (111 / 100 - 1) / 3 + (90 / 100 - 1) * 2 / 3)



class StoreTest(unittest.TestCase):
    """The store has to keep every new field, or the dashboard shows blanks."""

    def test_round_trip_of_verdicts_flow_and_paper(self) -> None:
        asyncio.run(self._run())

    def test_older_database_gets_the_new_verdict_columns(self) -> None:
        asyncio.run(self._migrate())

    def test_a_row_stored_without_groups_is_filed_by_its_labels(self) -> None:
        asyncio.run(self._legacy())

    async def _legacy(self) -> None:
        """The page reads sections, so a row written before they existed must still reach them."""
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            stored = await db.get_db()
            await stored.execute(
                """
                INSERT INTO verdicts (as_of, symbol, status, metrics_json, extra_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "2026-10-09",
                    "ACB",
                    "Theo dõi",
                    json.dumps(
                        [
                            ["Kỳ số liệu", "2026-06-30"],
                            ["Doanh thu thuần quý", "2374 tỷ"],
                            ["P/E", "7.3"],
                            ["Dòng tiền ngoại", "khối ngoại bán ròng 464,025 cp"],
                            ["S&P 500", "7,811.54 — +2.5% 20 phiên, trên MA20"],
                        ]
                    ),
                    "{}",
                ),
            )
            await stored.commit()

            item = await db.verdict("ACB")
            groups = dict(item["metric_groups"])
            self.assertEqual(
                list(groups), ["Cơ bản", "Định giá", "Dòng tiền ngoại", "Thị trường"]
            )
            self.assertEqual(groups["Cơ bản"][0], ("Kỳ số liệu", "2026-06-30"))
            self.assertEqual(groups["Thị trường"][0][0], "S&P 500")
            self.assertNotIn(UNPLACED_SECTION, groups)
            self.assertEqual(item["metrics"][0], ["Kỳ số liệu", "2026-06-30"])
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)

    async def _migrate(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE verdicts (
                    as_of TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    status TEXT NOT NULL,
                    regime_open INTEGER,
                    regime_reason TEXT NOT NULL DEFAULT '',
                    fa_label TEXT NOT NULL DEFAULT '',
                    fa_reason TEXT NOT NULL DEFAULT '',
                    news_state TEXT NOT NULL DEFAULT '',
                    news_reason TEXT NOT NULL DEFAULT '',
                    pattern_ready INTEGER NOT NULL DEFAULT 0,
                    pattern_reason TEXT NOT NULL DEFAULT '',
                    rs REAL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    stop_price REAL,
                    summary TEXT NOT NULL DEFAULT '',
                    metrics_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (as_of, symbol)
                );
                """
            )
            connection.commit()
            connection.close()
            await db.init_db()
            stored = await db.get_db()
            cursor = await stored.execute("PRAGMA table_info(verdicts)")
            columns = {row[1] for row in await cursor.fetchall()}
            self.assertLessEqual({"score", "flow_state", "extra_json"}, columns)
            self.assertEqual(await db.latest_verdicts(), [])
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            watching = compose(
                "FPT",
                date(2026, 10, 9),
                _corporate_points(),
                [_earnings()],
                Regime(True, "VN-Index trên MA200", 1200, 1100),
                Pattern(False, "Nền giá: chưa phá đỉnh nền", 0.02, 90),
                require_clock=True,
            )
            entering = compose(
                "FPT",
                date(2026, 10, 10),
                _corporate_points(),
                [_earnings()],
                Regime(True, "VN-Index trên MA200", 1200, 1100),
                _ready_pattern(),
                require_clock=True,
                flow=FlowState("Mở", ACCUMULATION, "Gom hàng", priority=2),
            )
            await db.save_verdicts([watching.row()])

            # The pipeline reads the session sitting in the store before it overwrites it,
            # so the older row is still the latest session at this point.
            before = await db.latest_verdicts()
            self.assertEqual([row["as_of"] for row in before], ["2026-10-09"])
            self.assertEqual(before[0]["status"], "Theo dõi")

            await db.save_verdicts([entering.row()])

            latest = await db.latest_verdicts()
            self.assertEqual(len(latest), 1)
            item = latest[0]
            self.assertEqual(item["as_of"], "2026-10-10")
            self.assertEqual(item["status"], "Được vào")
            self.assertEqual(item["score"], entering.score)
            self.assertEqual(item["flow_state"], "Mở")
            self.assertEqual(item["flow_level"], ACCUMULATION)
            self.assertEqual(item["patterns"], ())
            self.assertIsNone(item["f_score"])
            self.assertEqual(len(item["score_parts"]), 5)

            await db.replace_flow("FPT", {"FOREIGN_NET_VOL": [("2026-10-09", 1000.0)]})
            stored_flow = await db.flow("FPT")
            self.assertEqual(stored_flow["FOREIGN_NET_VOL"], [("2026-10-09", 1000.0)])

            position_id = await db.open_paper_position(
                {
                    "symbol": "FPT",
                    "entry_date": "2026-10-09",
                    "entry_price": 100.0,
                    "initial_stop": 90.0,
                    "stop_price": 90.0,
                    "target1": 110.0,
                    "atr14": 2.0,
                    "score": 80,
                    "note": "xác nhận",
                }
            )
            self.assertEqual((await db.open_paper_positions())[0]["score"], 80)
            await db.save_paper_position(
                {
                    "id": position_id,
                    "stop_price": 100.3,
                    "sessions": 3,
                    "tp1_done": True,
                    "booked_fraction": 1 / 3,
                    "realised": 0.1 / 3,
                    "last_price": 108.0,
                    "last_date": "2026-10-12",
                    "closed_at": None,
                    "exit_date": None,
                    "exit_price": None,
                    "exit_reason": None,
                }
            )
            await db.mark_paper(position_id, "2026-10-12", 108.0, 0.0833)
            rows = await db.paper_for("FPT")
            self.assertTrue(rows[0]["tp1_done"])
            self.assertAlmostEqual(rows[0]["last_price"] or 0, 108.0)

            report = await paper_report()
            self.assertEqual(report["count"], 1)
            self.assertEqual(report["open_count"], 1)
            self.assertEqual(report["closed_count"], 0)
            self.assertAlmostEqual(
                report["rows"][0]["return_pct"], 0.1 / 3 + (108 / 100 - 1) * 2 / 3, places=6
            )
            self.assertIsNone(report["alpha"])
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


class BacktestCacheTest(unittest.TestCase):
    """The walk takes seconds, so the page must not redo it on every glance."""

    def test_walk_is_reused_until_data_moves(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        from app import web

        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        calls: list[tuple] = []
        original = web.run_walk

        async def fake_walk(inputs):
            calls.append(inputs)
            return {"n": len(calls)}

        web.run_walk = fake_walk
        web._backtest_cache.update({"key": None, "result": None, "at": "", "task": None})
        try:
            await db.init_db()
            run_id = await db.start_run()
            first, first_pending = await web.backtest_result()
            second, second_pending = await web.backtest_result()
            self.assertEqual(len(calls), 1)
            self.assertEqual(first, second)
            self.assertFalse(first_pending or second_pending)
            self.assertTrue(web.backtest_computed_at())

            self.assertEqual((await web.backtest_result(fresh=True))[0]["n"], 2)
            self.assertEqual(len(calls), 2)

            await db.finish_run(run_id, "ok", "xong")
            self.assertEqual((await web.backtest_result())[0]["n"], 3)
            self.assertEqual(len(calls), 3)

            await db.add_symbol("ZZZ")
            self.assertEqual((await web.backtest_result())[0]["n"], 4)
            self.assertEqual(len(calls), 4)
        finally:
            web.run_walk = original
            web._backtest_cache.update({"key": None, "result": None, "at": "", "task": None})
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


def _walk_bars() -> tuple[list[dict], list[dict]]:
    """A 215-session index plus one name that breaks out, then dips through its stop.

    Sessions 140 to 179 slide 12.6% to 88 and climb 15% back to 100.88, so the fixed
    20-session base that ends at session 199 (the flat-base gate) sits on top of a real
    advance. The stop bar dips to 98 and closes back at 101.50, above the 99.70 stop, so an
    exit booked at the close would look better than the fill the plan really got. The name
    keeps sliding after the dip, so it can never be a candidate again.
    """
    start = date(2026, 2, 1)
    index_bars: list[dict] = []
    stock_bars: list[dict] = []
    for i in range(215):
        day = (start + timedelta(days=i)).isoformat()
        level = 1000.0 + i * 0.5
        index_bars.append(
            {
                "trade_date": day,
                "open": level,
                "high": level,
                "low": level,
                "close": level,
                "volume": 1.0,
            }
        )
        if i < 200:
            if i < 140:
                close = 100.0 + i * 0.005
            elif i < 160:
                close = 100.7 - (i - 140) * (100.7 - 88.0) / 19
            elif i < 180:
                close = 88.0 + (i - 159) * (100.88 - 88.0) / 20
            else:
                close = 100.0 + i * 0.005
            spread = 0.4 if i >= 190 else 1.2
            bar = {
                "trade_date": day,
                "open": close,
                "high": close + spread,
                "low": close - spread,
                "close": close,
                "volume": 800.0 if i >= 190 else 2000.0,
            }
        elif i == 200:
            bar = {
                "trade_date": day,
                "open": 101.0,
                "high": 105.5,
                "low": 100.8,
                "close": 105.0,
                "volume": 3000.0,
            }
        elif i == 201:
            bar = {
                "trade_date": day,
                "open": 104.0,
                "high": 104.5,
                "low": 98.0,
                "close": 101.5,
                "volume": 4000.0,
            }
        else:
            close = 101.5 - (i - 201) * 1.5
            bar = {
                "trade_date": day,
                "open": close + 0.5,
                "high": close + 2.5,
                "low": close - 2.5,
                "close": close,
                "volume": 5000.0,
            }
        stock_bars.append(bar)
    return index_bars, stock_bars

def _walk_bars_without(index: int) -> tuple[list[dict], list[dict]]:
    """The same walk with one session missing from the name's own bars."""
    index_bars, stock_bars = _walk_bars()
    return index_bars, stock_bars[:index] + stock_bars[index + 1 :]


def _walk_bars_halted_after_the_breakout() -> tuple[list[dict], list[dict]]:
    """Bar 199 is a ready breakout and the name then stops trading at all.

    The walk window opens on the session after that bar, so a walk that scores the last bar of
    the slice instead of the bar of the session would buy this name on 2026-08-20 at 199's close
    of 104.50 — a price the name had not traded at for a session — and date the entry to a session
    the name was nowhere near.
    """
    index_bars, stock_bars = _walk_bars()
    rows = list(stock_bars)
    rows[199] = {
        "trade_date": stock_bars[199]["trade_date"],
        "open": 103.0,
        "high": 105.0,
        "low": 102.5,
        "close": 104.5,
        "volume": 3000.0,
    }
    return index_bars, rows[:200]


def _walk_bars_with_a_hole() -> tuple[list[dict], list[dict]]:
    """The walk with a trim booked and the session right after it missing for the name.

    Bar 201 jumps to 111, which books 1/3 at TP1 and pulls the stop up to 105.32, while bar
    201's own low of 101 stays well behind it. The session after that never traded for the name,
    and the sessions after that fall away. So the question this fixture puts to the walk is
    whether it reads bar 201 again on the missing session — filling the raised stop with a low
    that happened before the stop was raised — or waits for a bar of its own.
    """
    index_bars, stock_bars = _walk_bars()
    replayed = list(stock_bars)
    replayed[201] = {
        "trade_date": stock_bars[201]["trade_date"],
        "open": 106.0,
        "high": 111.0,
        "low": 101.0,
        "close": 110.0,
        "volume": 4000.0,
    }
    return index_bars, replayed[:202] + replayed[203:]




class BacktestWalkTest(unittest.TestCase):
    """The walk moves the money, so it has to book exits the way the live ledger does."""

    def test_stop_fill_future_filing_and_the_interest_order(self) -> None:
        index_bars, stock_bars = _walk_bars()
        filings = {
            "FPT": [
                {
                    "published_at": "2027-01-01",
                    "kind": "suspension",
                    "title": "Đình chỉ niêm yết",
                }
            ]
        }
        # One percent a day, so interest landing on cash still in the stock overnight shows
        # up well clear of the noise instead of hiding in the last decimal.
        with mock.patch.object(backtest, "CASH_YIELD", 3.65):
            result = backtest.run_backtest(
                index_bars,
                {"FPT": stock_bars},
                {"FPT": _corporate_points()},
                filings,
            )

        self.assertEqual(result["start"], "2026-08-20")
        self.assertEqual(result["end"], "2026-09-03")
        self.assertEqual(result["trade_count"], 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry"], "2026-08-20")

        # 1. The stop fills at min(open, stop) — 99.70 — and settling the slot must not
        #    overwrite that with the 101.50 close.
        self.assertEqual(trade["reason"], "Chạm dừng lỗ")
        self.assertAlmostEqual(trade["exit_price"], 99.7)
        self.assertAlmostEqual(trade["return_pct"], 99.7 / 105.0 - 1)
        self.assertNotAlmostEqual(trade["return_pct"], 101.5 / 105.0 - 1)

        # 2. The suspension is published long after the walk ends, so only the stop may
        #    close the slot; the exit gate needs its own date ceiling.
        self.assertNotIn("Công bố chặn", trade["reason"] or "")

        # 3. Cash earns the deposit rate over the nights it is out of the market: the idle
        #    balance takes all 14 nights after entry (sessions 2..15), while the proceeds of
        #    the stop — still inside the stock on that night — take 13.
        side_cost = 0.003 / 2
        daily = (1 + 3.65) ** (1 / 365)
        spend = 0.01 / (105.0 - 99.7) * 105.0
        proceeds = spend * (1 - side_cost) * (99.7 / 105.0) * (1 - side_cost)
        expected = (1 - spend) * daily**14 + proceeds * daily**13
        self.assertAlmostEqual(result["strategy_return"] + 1, expected, places=9)
        self.assertNotAlmostEqual(
            result["strategy_return"] + 1, (1 - spend + proceeds) * daily**14, places=6
        )

    def test_a_session_the_name_did_not_trade_is_not_stepped(self) -> None:
        """The name is halted on 2026-08-21, so that session may not count for the slot."""
        index_bars, stock_bars = _walk_bars_without(201)
        result = backtest.run_backtest(
            index_bars, {"FPT": stock_bars}, {"FPT": _corporate_points()}, {}
        )
        self.assertEqual(result["trade_count"], 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry"], "2026-08-20")
        # The stop lands on the bar that really traded, and the halted session leaves no mark
        # behind it. Re-reading the entry bar on that session would hand the slot a session it
        # was never exposed to and bring the 30-session shelf closer.
        self.assertEqual(trade["exit"], "2026-08-22")
        self.assertEqual(trade["sessions"], 1)
        self.assertEqual(trade["reason"], "Chạm dừng lỗ")

    def test_a_session_without_a_bar_is_not_an_entry(self) -> None:
        """The name stopped trading, so the walk may not buy it at its last traded close."""
        index_bars, stock_bars = _walk_bars_halted_after_the_breakout()
        result = backtest.run_backtest(
            index_bars, {"FPT": stock_bars}, {"FPT": _corporate_points()}, {}
        )
        entries = [trade["entry"] for trade in result["trades"]]
        self.assertNotIn("2026-08-20", entries)
        # An entry dated after its own exit is the shape of the same mistake.
        for trade in result["trades"]:
            self.assertLessEqual(trade["entry"], trade["exit"])

    def test_a_missing_session_cannot_refill_a_raised_stop(self) -> None:
        """The session after the trim is missing; bar 201's low already happened behind it."""
        index_bars, stock_bars = _walk_bars_with_a_hole()
        result = backtest.run_backtest(
            index_bars, {"FPT": stock_bars}, {"FPT": _corporate_points()}, {}
        )
        self.assertEqual(result["trade_count"], 1)
        trade = result["trades"][0]
        self.assertEqual(trade["entry"], "2026-08-20")
        # 1/3 was booked at TP1 on 2026-08-21 and the stop moved up to 105.32, behind the low
        # of 101 that session had already printed. The next session did not trade for the name,
        # so the raised stop may not be filled there: the slot lives on to 2026-08-23 and gets
        # the fill that bar really offered.
        self.assertEqual(trade["exit"], "2026-08-23")
        self.assertEqual(trade["sessions"], 2)
        self.assertAlmostEqual(trade["exit_price"], 99.0)
        self.assertEqual(trade["reason"], "Chạm dừng lỗ")


def _paper_bars() -> list[dict]:
    """Five flat sessions; the fourth dips through the 90 stop and closes back at 95."""
    start = date(2026, 10, 8)
    bars: list[dict] = []
    for i in range(5):
        if i == 3:
            bar = {
                "trade_date": (start + timedelta(days=i)).isoformat(),
                "open": 95.5,
                "high": 95.5,
                "low": 85.0,
                "close": 95.0,
                "volume": 1_000_000.0,
            }
        else:
            close = 100.0 if i < 3 else 95.0
            bar = {
                "trade_date": (start + timedelta(days=i)).isoformat(),
                "open": close,
                "high": close + 0.5,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000.0,
            }
        bars.append(bar)
    return bars


class PaperLedgerTest(unittest.TestCase):
    """The paper book has to step each session once, even after a re-run or a missed day."""

    def test_missed_and_repeated_sessions(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            await db.replace_bars("FPT", _paper_bars())
            position_id = await db.open_paper_position(
                {
                    "symbol": "FPT",
                    "entry_date": "2026-10-08",
                    "entry_price": 100.0,
                    "initial_stop": 90.0,
                    "stop_price": 90.0,
                    "target1": 110.0,
                    "atr14": 2.0,
                    "score": 80,
                    "note": "xác nhận",
                }
            )

            # The entry session itself is not a step.
            self.assertEqual(await mark_positions("2026-10-08"), [])
            self.assertEqual((await db.open_paper_positions())[0]["sessions"], 0)

            await mark_positions("2026-10-09")
            row = (await db.open_paper_positions())[0]
            self.assertEqual(row["sessions"], 1)
            self.assertEqual(row["last_date"], "2026-10-09")

            # Opening the page twice on the same day must not buy two sessions.
            await mark_positions("2026-10-09")
            self.assertEqual((await db.open_paper_positions())[0]["sessions"], 1)

            # Two sessions skipped at once: both count, and the bar that was missed — the
            # only one to touch the stop — is the bar that closes the slot.
            messages = await mark_positions("2026-10-12")
            self.assertEqual(len(messages), 1)
            self.assertIn("Chạm dừng lỗ", messages[0])
            self.assertEqual(await db.open_paper_positions(), [])

            connection = await db.get_db()
            cursor = await connection.execute(
                "SELECT mark_date FROM paper_marks WHERE position_id = ? ORDER BY mark_date",
                (position_id,),
            )
            marks = [item["mark_date"] for item in await cursor.fetchall()]
            self.assertEqual(marks, ["2026-10-09", "2026-10-10", "2026-10-11"])

            closed = (await db.paper_for("FPT"))[0]
            self.assertEqual(closed["sessions"], 3)
            self.assertEqual(closed["exit_date"], "2026-10-11")
            self.assertAlmostEqual(closed["exit_price"] or 0, 90.0)
            self.assertEqual(closed["exit_reason"], "Chạm dừng lỗ")
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)

class PaperAlphaTest(unittest.TestCase):
    """Alpha compares a slot only with the index window that slot has actually lived through."""

    def test_a_slot_without_a_marked_session_is_left_out_of_both_averages(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            index_bars = _alpha_index_bars()
            await db.replace_bars("VNINDEX", index_bars)

            # A slot held for ten sessions, 10% up while the index is up less.
            seasoned = await db.open_paper_position(
                {
                    "symbol": "FPT",
                    "entry_date": "2026-10-01",
                    "entry_price": 100.0,
                    "initial_stop": 90.0,
                    "stop_price": 90.0,
                    "target1": 110.0,
                    "atr14": 2.0,
                    "score": 80,
                    "note": "xác nhận",
                }
            )
            await db.save_paper_position(
                {
                    "id": seasoned,
                    "stop_price": 90.0,
                    "sessions": 7,
                    "tp1_done": False,
                    "booked_fraction": 0.0,
                    "realised": 0.0,
                    "last_price": 110.0,
                    "last_date": "2026-10-10",
                    "closed_at": None,
                    "exit_date": None,
                    "exit_price": None,
                    "exit_reason": None,
                }
            )
            # A slot confirmed on the last session: no mark yet, so its 0% has no index window.
            await db.open_paper_position(
                {
                    "symbol": "VNM",
                    "entry_date": "2026-10-11",
                    "entry_price": 50.0,
                    "initial_stop": 45.0,
                    "stop_price": 45.0,
                    "target1": 55.0,
                    "atr14": 1.0,
                    "score": 80,
                    "note": "xác nhận",
                }
            )

            report = await paper_report()
            window = [
                bar for bar in index_bars if "2026-10-01" <= bar["trade_date"] <= "2026-10-10"
            ]
            index_pct = window[-1]["close"] / window[0]["close"] - 1
            self.assertEqual(report["count"], 2)
            # One slot has a marked session and an index window of its own; the fresh one has
            # neither, so it must be missing from both sides of the subtraction.
            self.assertEqual(sum(1 for row in report["rows"] if row["index_pct"] is None), 1)
            self.assertAlmostEqual(report["average_return"] or 0, 0.10, places=9)
            self.assertAlmostEqual(report["average_index"] or 0, index_pct, places=9)
            self.assertAlmostEqual(report["alpha"] or 0, 0.10 - index_pct, places=9)
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


def _alpha_index_bars() -> list[dict]:
    """Eleven index sessions from 2026-10-01, one point a session on 1200."""
    start = date(2026, 10, 1)
    bars: list[dict] = []
    for i in range(11):
        close = 1200.0 + i
        bars.append(
            {
                "trade_date": (start + timedelta(days=i)).isoformat(),
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000_000.0,
            }
        )
    return bars




class UniverseTest(unittest.TestCase):
    """An older store has to pick up the default list growing, without losing its edits."""

    def test_a_curated_store_without_a_bookmark_keeps_its_list(self) -> None:
        asyncio.run(self._run(("AAA",)))

    def test_a_fresh_store_gets_the_default_list(self) -> None:
        asyncio.run(self._run(()))

    async def _run(self, seeded: tuple[str, ...]) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        path = _store_with(seeded)
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            symbols = await db.universe()
            if seeded:
                # The list predates the bookmark, so it is the operator's: the defaults are not
                # poured back in and a name dropped by hand before the upgrade stays dropped.
                self.assertEqual(symbols, list(seeded))
            else:
                self.assertTrue(set(DEFAULT_UNIVERSE) <= set(symbols))

            # The bookmark is recorded on this very boot, so a default added later still lands.
            with mock.patch.object(db, "DEFAULT_UNIVERSE", list(DEFAULT_UNIVERSE) + ["ZZZ"]):
                await db.close_db()
                await db.init_db()
            self.assertIn("ZZZ", await db.universe())

            # A symbol the operator removed by hand must stay removed across restarts.
            await db.remove_symbol("PLX")
            await db.close_db()
            await db.init_db()
            self.assertNotIn("PLX", await db.universe())
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


def _store_with(symbols: tuple[str, ...]) -> str:
    """A sqlite file holding just a universe table, the way a store from before looks."""
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    connection = sqlite3.connect(handle.name)
    rows = "".join(
        f"INSERT INTO universe (symbol, added_at) VALUES ('{symbol}', 'cũ');" for symbol in symbols
    )
    connection.executescript(
        "CREATE TABLE universe (symbol TEXT PRIMARY KEY, added_at TEXT NOT NULL);" + rows
    )
    connection.commit()
    connection.close()
    return handle.name


PROVIDERS = Path(__file__).resolve().parents[2] / "backend" / "config" / "providers.yaml"


class UniverseWatchlistTest(unittest.TestCase):
    """The two hand-kept lists feed each other, so a test has to hold them together."""

    @unittest.skipUnless(PROVIDERS.exists(), "backend config is not in this checkout")
    def test_research_universe_matches_the_ingestion_watchlist(self) -> None:
        ingestion = yaml.safe_load(PROVIDERS.read_text(encoding="utf-8"))["ingestion"]
        watchlist = list(ingestion["quote_symbols"])
        self.assertEqual(
            set(DEFAULT_UNIVERSE),
            set(watchlist),
            "DEFAULT_UNIVERSE và ingestion.quote_symbols đã lệch nhau",
        )
        self.assertEqual(len(DEFAULT_UNIVERSE), len(set(DEFAULT_UNIVERSE)))
        self.assertEqual(len(watchlist), len(set(watchlist)))


class FinancialTemplateCoverageTest(unittest.TestCase):
    """The basket grew with financials, so each declared code has to land in its own template."""

    def test_every_declared_financial_code_is_watched(self) -> None:
        declared = BANKS | SECURITIES | INSURERS
        self.assertEqual(
            declared - set(DEFAULT_UNIVERSE),
            set(),
            "mã tài chính có bộ cổng riêng nhưng chưa nằm trong rổ đang chấm",
        )

    def test_the_three_financial_templates_do_not_overlap(self) -> None:
        # A symbol in two sets would silently take whichever branch is checked first.
        self.assertEqual(BANKS & SECURITIES, set())
        self.assertEqual(BANKS & INSURERS, set())
        self.assertEqual(SECURITIES & INSURERS, set())

    def test_no_financial_code_falls_through_to_the_corporate_template(self) -> None:
        for symbol in sorted(BANKS | SECURITIES | INSURERS):
            with self.subTest(symbol=symbol):
                if symbol in BANKS:
                    expected = "bank"
                elif symbol in SECURITIES:
                    expected = "securities"
                else:
                    expected = "insurer"
                scored = score_fundamentals(symbol, _corporate_points())
                self.assertEqual(scored.template, expected)


class VerdictOrderTest(unittest.TestCase):
    """The table note says the composite score ranks, so the table has to rank by it."""

    def test_the_score_leads_inside_a_state(self) -> None:
        from app import web

        rows = [
            {"symbol": "AAA", "status": "Theo dõi", "score": 40, "priority": 0},
            {"symbol": "BBB", "status": "Theo dõi", "score": 70, "priority": 0},
            {"symbol": "CCC", "status": "Được vào", "score": 55, "priority": 0},
            {"symbol": "DDD", "status": "Được vào", "score": 55, "priority": 1},
        ]
        self.assertEqual(
            [item["symbol"] for item in web._ordered(rows)], ["DDD", "CCC", "BBB", "AAA"]
        )

    def test_a_state_with_no_priority_still_orders_by_score(self) -> None:
        """Every name is Khóa under a closed market gate, and the score still has to rank."""
        from app import web

        rows = [
            {"symbol": "AAA", "status": "Khóa", "score": 30, "priority": 0},
            {"symbol": "BBB", "status": "Khóa", "score": 62, "priority": 0},
            {"symbol": "CCC", "status": "Khóa", "score": 51, "priority": 0},
        ]
        self.assertEqual(
            [item["symbol"] for item in web._ordered(rows)], ["BBB", "CCC", "AAA"]
        )


class PipelineAlertTest(unittest.TestCase):
    """A session has to be diffed against the session in the store, not an older one."""

    def test_transition_comes_from_the_stored_session(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        index_bars, stock_bars = _walk_bars()
        points = _corporate_points()
        sent: list[str] = []

        async def fake_bars(_client, symbol, *, index=False):
            return index_bars if symbol == "VNINDEX" else stock_bars

        async def fake_ratios(_client, symbol):
            return points

        async def fake_news(_client, symbol):
            return [
                {
                    "id": "fpt-q2",
                    "title": "FPT công bố báo cáo tài chính quý 2",
                    "published_at": "2026-08-01",
                    "symbols": ["FPT"],
                    "kind": "earnings_release",
                }
            ]

        async def fake_flow(_client, symbol):
            return {}

        async def fake_macro(_client):
            return {}

        async def fake_market(_client, day):
            """Năm phiên đã lưu tính tới hôm nay, để cổng tiền tệ có số mà chấm."""
            end = date.fromisoformat(day)
            days = [(end - timedelta(days=step)).isoformat() for step in reversed(range(5))]
            return {
                "INTERBANK_ON": [(when, 5.0) for when in days],
                "GOV10Y": [(when, 4.0) for when in days],
                "USDVND": [(when, 25_000.0) for when in days],
            }

        async def fake_send(text):
            sent.append(text)
            return True

        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            connection = await db.get_db()
            await connection.execute("DELETE FROM universe WHERE symbol <> 'FPT'")
            await connection.commit()

            with mock.patch.multiple(
                pipeline,
                fetch_bars=fake_bars,
                fetch_ratios=fake_ratios,
                supplement_historical_shares=_no_backfill,
                fetch_symbol_news=fake_news,
                fetch_foreign_flow=fake_flow,
                fetch_macro=fake_macro,
                fetch_market=fake_market,
                load_market_articles=lambda: [],
                load_exchanges=lambda: {},
                load_valuation=lambda: {},
            ), mock.patch.object(notify, "send", fake_send):
                first = await pipeline._run()
                self.assertTrue(first.startswith("Phiên 2026-09-03"))
                self.assertIn("Theo dõi", first)
                self.assertEqual(sent, [])  # nothing stored yet, so nothing to compare

                # The same session re-run with the debt gate failing must be announced
                # against the session just stored, not against an older one or nothing.
                points["DEBT_TO_EQUITY_AQ"] = [(_REPORT, 3.0)]
                await pipeline._run()

            self.assertEqual(len(sent), 1)
            self.assertIn("<b>FPT</b> Loại", sent[0])
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


class PipelineSessionBarTest(unittest.TestCase):
    """A session may only score a name that has a bar of the session being read.

    The backtest has always dropped those names, and the paper ledger only ever steps a real
    bar, but the live run composed every name in the list from whatever bars and flow the store
    still held, under the VN-Index session date. A feed that failed, or a name that simply did
    not trade, then carried an older bar as if it were this session's.

    A failed fetch only costs the name its session when the store has no bar for that session: a
    bar stored by an earlier run the same day keeps the name scored, so "Không tải được" is not
    the same list as the names that left the table.
    """

    def test_failed_fetch_is_not_scored_on_the_bar_left_in_the_store(self) -> None:
        asyncio.run(self._run(fail=True))

    def test_loaded_name_with_no_bar_of_the_session_is_named_apart(self) -> None:
        asyncio.run(self._run(fail=False))

    async def _run(self, *, fail: bool) -> None:
        index_bars, stock_bars = _walk_bars()
        points = _corporate_points()
        session = index_bars[-1]["trade_date"]
        # TPB's bars stop on the session before, the way a feed that dies leaves them.
        stale = stock_bars[:-1]
        self.assertEqual(stale[-1]["trade_date"], index_bars[-2]["trade_date"])
        sent: list[str] = []

        async def fake_bars(_client, symbol, *, index=False):
            if symbol == "VNINDEX":
                return index_bars
            if symbol == "TPB":
                if fail:
                    raise httpx.ConnectError("feed down")
                return stale
            return stock_bars

        async def fake_ratios(_client, symbol):
            return points

        async def fake_news(_client, symbol):
            return [_earnings()]

        async def fake_flow(_client, symbol):
            return {}

        async def fake_macro(_client):
            return {}

        async def fake_market(_client, day):
            return {}

        async def fake_send(text):
            sent.append(text)
            return True

        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        path = handle.name
        os.environ["RESEARCH_DB_PATH"] = path
        try:
            await db.init_db()
            connection = await db.get_db()
            await connection.execute("DELETE FROM universe WHERE symbol NOT IN ('FPT', 'TPB')")
            await connection.commit()
            # An earlier session loaded TPB, so the store holds a close there to compose on.
            await db.replace_bars("TPB", stale)

            with mock.patch.multiple(
                pipeline,
                fetch_bars=fake_bars,
                fetch_ratios=fake_ratios,
                supplement_historical_shares=_no_backfill,
                fetch_symbol_news=fake_news,
                fetch_foreign_flow=fake_flow,
                fetch_macro=fake_macro,
                fetch_market=fake_market,
                load_market_articles=lambda: [],
                load_exchanges=lambda: {},
                load_valuation=lambda: {},
            ), mock.patch.object(notify, "send", fake_send):
                message = await pipeline._run()

            self.assertTrue(message.startswith(f"Phiên {session}: "), message)
            rows = await db.latest_verdicts()
            self.assertEqual([row["symbol"] for row in rows], ["FPT"])
            self.assertIsNone(await db.verdict("TPB"))
            cursor = await connection.execute("SELECT COUNT(*) FROM verdicts WHERE symbol = 'TPB'")
            self.assertEqual((await cursor.fetchone())[0], 0)
            self.assertEqual([text for text in sent if "TPB" in text], [])
            if fail:
                self.assertIn("Không tải được: TPB", message)
            else:
                self.assertIn("Chưa có nến phiên này: TPB", message)
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

