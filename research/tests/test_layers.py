from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import db
from app.evaluate import (
    compose,
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
from app.paper import report as paper_report
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

            before = await db.previous_verdicts()
            self.assertEqual([row["as_of"] for row in before], ["2026-10-09"])
            self.assertEqual(before[0]["status"], "Theo dõi")

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
        original = web.run_backtest
        web.run_backtest = lambda *args, **kwargs: calls.append(args) or {"n": len(calls)}
        web._backtest_cache.update({"key": None, "result": None, "at": ""})
        try:
            await db.init_db()
            run_id = await db.start_run()
            first = await web.backtest_result()
            second = await web.backtest_result()
            self.assertEqual(len(calls), 1)
            self.assertEqual(first, second)
            self.assertTrue(web.backtest_computed_at())

            self.assertEqual((await web.backtest_result(fresh=True))["n"], 2)
            self.assertEqual(len(calls), 2)

            await db.finish_run(run_id, "ok", "xong")
            self.assertEqual((await web.backtest_result())["n"], 3)
            self.assertEqual(len(calls), 3)

            await db.add_symbol("ZZZ")
            self.assertEqual((await web.backtest_result())["n"], 4)
            self.assertEqual(len(calls), 4)
        finally:
            web.run_backtest = original
            web._backtest_cache.update({"key": None, "result": None, "at": ""})
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

