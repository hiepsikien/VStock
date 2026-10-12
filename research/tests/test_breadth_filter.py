"""Bộ lọc độ rộng: mẫu đo, giá vào phiên sau, điều kiện đo và kết luận theo luật đã chốt."""

from __future__ import annotations

import asyncio
import unittest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from app.breadth_filter import (
    DROP,
    KEEP,
    Counts,
    FilterSignal,
    classify,
    count,
    counts_text,
    judge,
    months_between,
    next_session_return,
    refresh_bars,
    report_text,
    settle_unconfirmed,
    stored_states,
    unconfirmed,
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


class ConfirmTest(unittest.TestCase):
    """Tín hiệu nào chặn lệnh đo vì không xác nhận được nến. Tín hiệu ở phiên 0, bán ở phiên 1 + 3."""

    def setUp(self) -> None:
        self.days = _days(10)
        self.signal = FilterSignal("AAA", self.days[0], KEEP, True, 0.05)

    def _unsure(self, last: int, refreshed: set[str], listings: dict | None = None) -> list[FilterSignal]:
        bars = {"AAA": _bars(self.days[: last + 1], [100.0] * (last + 1))}
        return unconfirmed([self.signal], bars, self.days, listings or {}, refreshed, horizon=3)

    def test_a_refreshed_name_is_confirmed_even_when_its_bars_stop_early(self) -> None:
        # Mã tạm ngừng giao dịch: nguồn vừa trả đủ, chỉ là không có phiên sau.
        self.assertEqual(self._unsure(1, {"AAA"}), [])

    def test_stored_bars_up_to_the_exit_are_enough_without_a_refresh(self) -> None:
        self.assertEqual(self._unsure(4, set()), [])

    def test_a_delisted_name_with_bars_up_to_its_delisting_is_confirmed(self) -> None:
        listings = {"AAA": {"delisted_date": self.days[3]}}
        self.assertEqual(self._unsure(2, set(), listings), [])

    def test_stale_bars_without_a_refresh_block_the_measure(self) -> None:
        # Không nạp lại được, hoặc không nằm trong danh sách nạp lại: hai trường hợp như nhau.
        self.assertEqual(self._unsure(2, set()), [self.signal])
        listings = {"AAA": {"delisted_date": self.days[9]}}
        self.assertEqual(self._unsure(2, set(), listings), [self.signal])

    def test_signals_outside_the_measure_never_block(self) -> None:
        bars = {"AAA": _bars(self.days[:1], [100.0])}
        signals = [
            FilterSignal("AAA", self.days[0], DROP, False, None),
            FilterSignal("AAA", self.days[0], None, True, 0.01),
        ]
        self.assertEqual(unconfirmed(signals, bars, self.days, {}, set(), horizon=3), [])

    def test_unconfirmed_signals_block_until_the_deadline_then_count_as_missing_price(self) -> None:
        n = BREADTH_FILTER_MIN_SIGNALS
        unsure = [FilterSignal("STALE", "2027-01-05", DROP, True, -0.01)]
        signals = _signals([0.05] * n, [-0.01] * (n - 1)) + unsure
        with self.assertRaises(SystemExit):
            settle_unconfirmed(signals, unsure, _counts(BREADTH_FILTER_MAX_MONTHS - 1, n, n))
        settled = settle_unconfirmed(signals, unsure, _counts(BREADTH_FILTER_MAX_MONTHS, n, n))
        verdict = judge(settled, _counts(BREADTH_FILTER_MAX_MONTHS, n, n))
        self.assertEqual((verdict.outcome, verdict.missing_price), ("không đủ mẫu", 1))
        self.assertIs(settle_unconfirmed(signals, [], _counts(1, n, n)), signals)

    def test_the_report_names_the_amendments_the_code_and_the_unpriced_signals(self) -> None:
        n = BREADTH_FILTER_MIN_SIGNALS
        signals = _signals([0.05] * n, [-0.01] * n)
        counts = _counts(BREADTH_FILTER_MIN_MONTHS, n, n)
        text = report_text(signals, counts, judge(signals, counts), code="abc123", unpriced=[signals[0]])
        self.assertIn("`prereg/breadth-filter-amend2`", text)
        self.assertIn("`abc123`", text)
        self.assertIn("K 2027-01-04", text)


class RefreshTest(unittest.TestCase):
    def _run(self, entrade, vndirect) -> tuple[list[str], list[str]]:
        written: list[str] = []

        async def _replace(symbol, _bars):
            written.append(symbol)

        async def _entrade(_client, symbol, **_kwargs):
            return entrade(symbol)

        async def _vndirect(_client, symbol, _start):
            return vndirect(symbol)

        with (
            patch("app.ingest.fetch_bars", _entrade),
            patch("app.ingest.fetch_market_bars", _vndirect),
            patch("app.db.init_db", AsyncMock()),
            patch("app.db.close_db", AsyncMock()),
            patch("app.db.replace_bars", _replace),
        ):
            failed = asyncio.run(refresh_bars(["AAA", "OLD", "BAD"]))
        return failed, written

    def test_falls_back_to_vndirect_and_reports_names_neither_source_has(self) -> None:
        bar = [{"trade_date": "2027-01-04", "close": 1.0}]

        def entrade(symbol):
            if symbol == "VNINDEX" or symbol == "AAA":
                return bar
            if symbol == "OLD":
                raise RuntimeError("400")
            return []

        def vndirect(symbol):
            if symbol == "OLD":
                return bar
            raise RuntimeError("down")

        failed, written = self._run(entrade, vndirect)
        self.assertEqual(failed, ["BAD"])
        self.assertEqual(sorted(written), ["AAA", "OLD", "VNINDEX"])


if __name__ == "__main__":
    unittest.main()
