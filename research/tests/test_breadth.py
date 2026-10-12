"""Độ rộng: mã nào được đếm, tỷ lệ trên MA50, và trạng thái có độ trễ hai ngưỡng."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.breadth import adjustment_breaks, breadth_by_day, breadth_reason, breadth_states, gate_on
from app.pit_universe import Basket


def _days(count: int, start: str = "2024-01-02") -> list[str]:
    day = date.fromisoformat(start)
    return [(day + timedelta(days=step)).isoformat() for step in range(count)]


def _bars(days: list[str], closes: list[float]) -> list[dict]:
    return [
        {"trade_date": day, "open": close, "high": close, "low": close, "close": close, "volume": 1.0}
        for day, close in zip(days, closes)
    ]


def _rising(days: list[str]) -> list[dict]:
    return _bars(days, [10 + step * 0.01 for step in range(len(days))])


def _falling(days: list[str]) -> list[dict]:
    return _bars(days, [20 - step * 0.01 for step in range(len(days))])


def _basket(names: list[str], day: str = "2024-01-02") -> dict[int, Basket]:
    return {2024: Basket(day, names, names[:2])}


class BreadthShareTest(unittest.TestCase):
    def test_share_counts_names_above_their_own_average(self) -> None:
        days = _days(80)
        bars = {f"U{n}": _rising(days) for n in range(3)} | {"D0": _falling(days)}
        points = breadth_by_day(days, bars, _basket(list(bars)), min_names=1, window=50)
        last = points[days[-1]]
        self.assertEqual((last.above, last.names), (3, 4))
        self.assertAlmostEqual(last.share, 0.75)

    def test_short_history_is_not_counted(self) -> None:
        days = _days(60)
        bars = {"OLD": _rising(days), "NEW": _rising(days[-20:])}
        point = breadth_by_day(days, bars, _basket(list(bars)), min_names=1, window=50)[days[-1]]
        self.assertEqual((point.names, point.short), (1, 1))

    def test_too_few_names_is_unscored(self) -> None:
        days = _days(60)
        bars = {"A": _rising(days)}
        point = breadth_by_day(days, bars, _basket(["A"]), min_names=2, window=50)[days[-1]]
        self.assertIsNone(point.share)
        self.assertEqual(point.names, 1)

    def test_suspended_name_drops_out_after_stale_limit(self) -> None:
        """Mã ngừng giao dịch kiểu HPX không được giữ giá cũ trong độ rộng."""
        days = _days(70)
        bars = {"LIVE": _rising(days), "HALT": _rising(days[:62])}
        points = breadth_by_day(days, bars, _basket(list(bars)), min_names=1, window=50, max_stale=5)
        self.assertEqual(points[days[66]].names, 2)  # nến cuối cách 5 phiên: vẫn đếm
        self.assertEqual((points[days[67]].names, points[days[67]].stale), (1, 1))

    def test_adjustment_break_excludes_name_while_inside_window(self) -> None:
        """Bước +26% của TV2 2021-07-15 là hệ số chia tách lệch, không phải giá thật."""
        days = _days(130)
        closes = [10 + step * 0.01 for step in range(130)]
        closes[60:] = [close * 1.26 for close in closes[60:]]
        bars = {"TV2": _bars(days, closes), "OK": _rising(days)}
        points = breadth_by_day(days, bars, _basket(list(bars)), {"TV2": "HOSE"}, min_names=1, window=50)
        self.assertEqual(adjustment_breaks(bars["TV2"], "HOSE"), [days[60]])
        self.assertEqual(points[days[59]].names, 2)
        self.assertEqual((points[days[60]].names, points[days[60]].broken), (1, 1))
        # Từ nến 109 cửa sổ 50 nến bắt đầu ở chính nến 60, nên cả cửa sổ cùng một mặt bằng giá.
        self.assertEqual(points[days[108]].broken, 1)
        self.assertEqual(points[days[109]].names, 2)

    def test_hnx_band_is_wider_than_hose(self) -> None:
        days = _days(3)
        bars = _bars(days, [10.0, 11.0, 11.0])  # +10%
        self.assertEqual(adjustment_breaks(bars, "HOSE"), [days[1]])
        self.assertEqual(adjustment_breaks(bars, "HNX"), [])

    def test_basket_switches_on_the_new_year(self) -> None:
        days = _days(400, "2023-11-01")
        bars = {"A": _rising(days), "B": _falling(days)}
        baskets = {2023: Basket("2023-01-03", ["A"], ["A"]), 2024: Basket("2024-01-02", ["B"], ["B"])}
        points = breadth_by_day(days, bars, baskets, min_names=1, window=50)
        self.assertEqual(points["2023-12-31"].share, 1.0)
        self.assertEqual(points["2024-01-01"].share, 1.0)  # trước phiên chốt rổ 2024
        self.assertEqual(points["2024-01-02"].share, 0.0)


class BreadthStateTest(unittest.TestCase):
    def test_first_state_uses_the_start_mark(self) -> None:
        self.assertEqual(breadth_states([("d1", 0.50)]), {"d1": True})
        self.assertEqual(breadth_states([("d1", 0.49)]), {"d1": False})

    def test_band_holds_the_previous_state(self) -> None:
        series = [("d1", 0.40), ("d2", 0.54), ("d3", 0.55), ("d4", 0.46), ("d5", 0.45), ("d6", 0.50)]
        states = breadth_states(series)
        self.assertEqual(
            [states[day] for day, _ in series], [False, False, True, True, False, False]
        )

    def test_unscored_session_keeps_the_state_for_later(self) -> None:
        states = breadth_states([("d1", 0.60), ("d2", None), ("d3", 0.50)])
        self.assertEqual(states, {"d1": True, "d2": None, "d3": True})

    def test_gate_on_reads_point_and_state_of_the_day(self) -> None:
        days = _days(60)
        bars = {"A": _rising(days), "B": _rising(days)}
        points = breadth_by_day(days, bars, _basket(list(bars)), min_names=1, window=50)
        states = breadth_states([(day, points[day].share) for day in days])
        gate = gate_on(days[-1], points, states)
        self.assertTrue(gate.open)
        self.assertEqual(gate.share, 1.0)
        self.assertIsNone(gate_on(days[0], points, states).open)

    def test_reason_names_the_other_threshold(self) -> None:
        self.assertIn("đóng khi xuống 45%", breadth_reason(0.6, True, 180))
        self.assertIn("mở khi lên 55%", breadth_reason(0.4, False))
        self.assertIn("chưa chấm", breadth_reason(None, None))


class BreadthLiveTest(unittest.TestCase):
    def test_market_page_shows_the_stored_breadth(self) -> None:
        from app.config import BREADTH_SERIES, BREADTH_STATE_SERIES
        from app.money import money_state
        from app.web import _breadth_view, templates

        view = _breadth_view(
            {
                BREADTH_SERIES: [("2026-10-08", 0.58), ("2026-10-09", 0.51)],
                BREADTH_STATE_SERIES: [("2026-10-08", 1.0), ("2026-10-09", 1.0)],
            },
            ["2026-10-08", "2026-10-09", "2026-10-13"],
        )
        self.assertEqual((view["last_day"], view["sessions"]), ("2026-10-09", 2))
        self.assertIn("Độ rộng mở: 51%", view["reason"])
        self.assertEqual(
            [(row["day"], row["share"], row["open"]) for row in view["recent"]],
            [("2026-10-13", "—", None), ("2026-10-09", "51.0%", True), ("2026-10-08", "58.0%", True)],
        )
        page = templates.get_template("market.html").render(
            money=money_state({}), rows=[], thresholds=[], missing=[], short=[], policy=[],
            latest_day="", breadth=view,
        )
        self.assertIn("Độ rộng mở: 51%", page)
        self.assertIn("Chỉ để quan sát", page)
        # Phiên 2026-10-13 thuộc phép đo bộ lọc mà không có trạng thái.
        self.assertIn("chưa ghi", page)

    def test_enforced_gate_locks_a_ready_name(self) -> None:
        from datetime import date as day_type
        from unittest import mock

        from app import evaluate
        from app.breadth import BreadthGate
        from app.pattern import Pattern, Regime

        def _status(enforced: bool, gate: BreadthGate) -> tuple[str, str]:
            with mock.patch.object(evaluate, "BREADTH_GATE_ENFORCED", enforced):
                verdict = evaluate.compose(
                    "FPT",
                    day_type(2026, 10, 9),
                    {},
                    [],
                    Regime(True, "VN-Index trên MA200", 1200, 1100),
                    Pattern(True, "phá nền", 0.1, 90.0),
                    require_clock=False,
                    breadth=gate,
                )
            return verdict.status, verdict.summary

        closed = BreadthGate(False, "Độ rộng đóng: 40% mã của rổ trên MA50", 0.40)
        self.assertEqual(_status(True, closed), ("Khóa", closed.reason))
        self.assertNotEqual(_status(False, closed)[0], "Khóa")
        self.assertEqual(_status(True, BreadthGate(None, "Độ rộng chưa chấm"))[0], "Chưa chấm")


if __name__ == "__main__":
    unittest.main()
