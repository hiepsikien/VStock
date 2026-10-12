"""Bộ lọc độ rộng: mẫu đo, giá vào phiên sau, điều kiện đo và kết luận theo luật đã chốt."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.breadth_filter import (
    DROP,
    KEEP,
    Counts,
    FilterSignal,
    blocking_failures,
    classify,
    count,
    counts_text,
    judge,
    months_between,
    next_session_return,
    stored_states,
)
from app.config import BREADTH_FILTER_MAX_MONTHS, BREADTH_FILTER_MIN_MONTHS, BREADTH_FILTER_MIN_SIGNALS


def _days(count: int, start: str = "2026-10-13") -> list[str]:
    day = date.fromisoformat(start)
    return [(day + timedelta(days=step)).isoformat() for step in range(count)]


def _bars(days: list[str], closes: list[float]) -> list[dict]:
    return [{"trade_date": day, "close": close} for day, close in zip(days, closes)]


def _counts(months: int, keep: int, drop: int) -> Counts:
    return Counts("2026-10-13", "2027-10-13", months, keep, keep, drop, drop, 0, 250, 0)


def _signals(keep: list[float], drop: list[float]) -> list[FilterSignal]:
    return [FilterSignal("K", "2027-01-04", KEEP, True, value) for value in keep] + [
        FilterSignal("D", "2027-01-04", DROP, True, value) for value in drop
    ]


class ReturnTest(unittest.TestCase):
    def test_return_starts_at_the_next_session_close(self) -> None:
        days = _days(10)
        series = _bars(days, [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0, 190.0])
        # Tín hiệu ở phiên 0: mua ở giá đóng cửa phiên 1 (110), bán ở phiên 1 + 3 (140).
        self.assertAlmostEqual(next_session_return(series, days, 0, 3), 140.0 / 110.0 - 1)

    def test_a_halted_name_keeps_its_last_close(self) -> None:
        days = _days(10)
        series = _bars(days[:3], [100.0, 110.0, 99.0])
        self.assertAlmostEqual(next_session_return(series, days, 0, 5), 99.0 / 110.0 - 1)

    def test_no_return_before_the_horizon_is_complete(self) -> None:
        days = _days(5)
        series = _bars(days, [100.0] * 5)
        self.assertIsNone(next_session_return(series, days, 0, 4))
        self.assertIsNotNone(next_session_return(series, days, 0, 3))


class SampleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.days = _days(12, "2026-10-10")
        self.bars = {"AAA": _bars(self.days, [100.0 + step for step in range(12)])}
        self.ma200 = {day: True for day in self.days}

    def test_groups_follow_the_stored_state_and_skip_closed_ma200(self) -> None:
        states = stored_states([(self.days[3], 1.0), (self.days[4], 0.0)])
        ma200 = dict(self.ma200)
        ma200[self.days[5]] = False
        raw = [
            {"symbol": "AAA", "day": self.days[1]},  # trước ngày bắt đầu
            {"symbol": "AAA", "day": self.days[3]},  # độ rộng mở
            {"symbol": "AAA", "day": self.days[4]},  # độ rộng đóng
            {"symbol": "AAA", "day": self.days[5]},  # MA200 đóng
            {"symbol": "AAA", "day": self.days[6]},  # không có trạng thái đã lưu
        ]
        signals = classify(raw, self.days, self.bars, ma200, states, start="2026-10-13", horizon=3)
        self.assertEqual([(s.day, s.group) for s in signals], [
            (self.days[3], KEEP),
            (self.days[4], DROP),
            (self.days[6], None),
        ])
        counts = count(signals, self.days, states, start="2026-10-13")
        self.assertEqual((counts.keep_total, counts.drop_total, counts.missing_state), (1, 1, 1))
        self.assertEqual(counts.sessions, 9)
        self.assertEqual(counts.sessions_without_state, 7)

    def test_only_signals_past_the_horizon_are_matured(self) -> None:
        states = {day: True for day in self.days}
        raw = [{"symbol": "AAA", "day": self.days[7]}, {"symbol": "AAA", "day": self.days[8]}]
        signals = classify(raw, self.days, self.bars, self.ma200, states, start="2026-10-13", horizon=3)
        self.assertEqual([s.matured for s in signals], [True, False])
        self.assertIsNone(signals[1].forward)

    def test_the_last_stored_value_wins(self) -> None:
        states = stored_states([("2026-10-13", 1.0), ("2026-10-13", 0.0)])
        self.assertFalse(states["2026-10-13"])


class GateTest(unittest.TestCase):
    def test_months_are_whole_months(self) -> None:
        self.assertEqual(months_between("2026-10-13", "2027-10-12"), 11)
        self.assertEqual(months_between("2026-10-13", "2027-10-13"), 12)

    def test_measuring_early_is_refused(self) -> None:
        enough = BREADTH_FILTER_MIN_SIGNALS
        with self.assertRaises(ValueError):
            judge([], _counts(BREADTH_FILTER_MIN_MONTHS - 1, enough, enough))
        with self.assertRaises(ValueError):
            judge([], _counts(BREADTH_FILTER_MIN_MONTHS, enough, enough - 1))

    def test_past_the_deadline_without_enough_signals_is_not_enough_sample(self) -> None:
        verdict = judge([], _counts(BREADTH_FILTER_MAX_MONTHS, 80, BREADTH_FILTER_MIN_SIGNALS - 1))
        self.assertEqual(verdict.outcome, "không đủ mẫu")

    def test_edge_of_two_points_passes_even_when_the_dropped_group_is_profitable(self) -> None:
        n = BREADTH_FILTER_MIN_SIGNALS
        counts = _counts(BREADTH_FILTER_MIN_MONTHS, n, n)
        # Nhóm bỏ lãi +1%, cao hơn phí cả vòng: chỉ là số báo cáo, không chặn kết luận.
        self.assertEqual(judge(_signals([0.031] * n, [0.01] * n), counts).outcome, "qua")
        self.assertEqual(judge(_signals([0.029] * n, [0.01] * n), counts).outcome, "không qua")

    def test_missing_prices_can_push_a_group_below_the_minimum(self) -> None:
        n = BREADTH_FILTER_MIN_SIGNALS
        signals = _signals([0.05] * n, [-0.01] * (n - 1)) + [FilterSignal("D", "2027-01-04", DROP, True, None)]
        verdict = judge(signals, _counts(BREADTH_FILTER_MIN_MONTHS, n, n))
        self.assertEqual(verdict.outcome, "không đủ mẫu")
        self.assertEqual(verdict.missing_price, 1)

    def test_counts_text_has_no_returns(self) -> None:
        text = counts_text(_counts(3, 10, 4))
        self.assertNotIn("%", text)
        self.assertIn("chưa đủ điều kiện đo", text)

    def test_counts_text_before_the_first_session(self) -> None:
        counts = Counts("2026-10-13", "2026-10-09", 0, 0, 0, 0, 0, 0, 0, 0)
        self.assertIn("Từ 2026-10-13: chưa có phiên nào, phiên mới nhất trong kho là 2026-10-09.", counts_text(counts))

    def test_a_failed_refresh_blocks_only_names_used_in_the_sample(self) -> None:
        signals = [
            FilterSignal("AAA", "2027-01-04", KEEP, True, 0.05),
            FilterSignal("BBB", "2027-01-04", DROP, False, None),
            FilterSignal("CCC", "2027-01-04", None, True, 0.01),
        ]
        # BBB chưa đủ phiên và CCC không có trạng thái, nên nến cũ của chúng không vào phép đo.
        self.assertEqual(blocking_failures(signals, ["BBB", "CCC", "DDD"]), [])
        self.assertEqual(blocking_failures(signals, ["AAA", "DDD"]), ["AAA"])


if __name__ == "__main__":
    unittest.main()
