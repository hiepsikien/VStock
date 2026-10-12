from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone

from app.config import BREADTH_STATE_SERIES
from app.pipeline import BUSY_MESSAGE
from app.scheduled import VN, breadth_line, expected_session, in_session, lost_sessions, should_alert


class SessionHoursTest(unittest.TestCase):
    def test_weekday_trading_hours_are_in_session(self) -> None:
        self.assertTrue(in_session(datetime(2026, 10, 13, 9, 0, tzinfo=VN)))
        self.assertTrue(in_session(datetime(2026, 10, 13, 14, 59, tzinfo=VN)))

    def test_after_close_before_open_and_weekends_are_not(self) -> None:
        self.assertFalse(in_session(datetime(2026, 10, 13, 15, 0, tzinfo=VN)))
        self.assertFalse(in_session(datetime(2026, 10, 13, 8, 59, tzinfo=VN)))
        self.assertFalse(in_session(datetime(2026, 10, 17, 10, 0, tzinfo=VN)))

    def test_the_clock_is_read_in_vietnam_time(self) -> None:
        # 03:00 UTC là 10:00 giờ Việt Nam.
        self.assertTrue(in_session(datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)))


class ExpectedSessionTest(unittest.TestCase):
    def test_after_the_close_today_is_expected(self) -> None:
        self.assertEqual(expected_session(datetime(2026, 10, 13, 15, 30, tzinfo=VN)), "2026-10-13")

    def test_before_the_close_the_previous_weekday_is_expected(self) -> None:
        self.assertEqual(expected_session(datetime(2026, 10, 13, 14, 0, tzinfo=VN)), "2026-10-12")
        self.assertEqual(expected_session(datetime(2026, 10, 14, 8, 0, tzinfo=VN)), "2026-10-13")
        # Sáng thứ Hai và cả cuối tuần chờ phiên thứ Sáu.
        self.assertEqual(expected_session(datetime(2026, 10, 19, 8, 0, tzinfo=VN)), "2026-10-16")
        self.assertEqual(expected_session(datetime(2026, 10, 17, 8, 0, tzinfo=VN)), "2026-10-16")


class BreadthLineTest(unittest.TestCase):
    def test_the_last_stored_value_of_the_session_is_reported(self) -> None:
        states = [("2026-10-12", 1.0), ("2026-10-13", 1.0), ("2026-10-13", 0.0)]
        self.assertEqual(
            breadth_line("2026-10-13", states, "2026-10-13"), ("Độ rộng phiên 2026-10-13: đóng.", "ok")
        )

    def test_a_session_without_a_state_is_flagged(self) -> None:
        line, found = breadth_line("2026-10-13", [("2026-10-12", 1.0)], "2026-10-13")
        self.assertEqual(found, "no_state")
        self.assertIn("chưa ghi", line)
        self.assertEqual(breadth_line(None, [], "2026-10-13")[1], "no_index")

    def test_an_index_that_has_not_reached_the_closed_session_is_flagged(self) -> None:
        line, found = breadth_line("2026-10-09", [("2026-10-09", 0.0)], "2026-10-12")
        self.assertEqual(found, "no_bar")
        self.assertIn("Chưa có nến phiên 2026-10-12", line)


class AlertTest(unittest.TestCase):
    def test_a_late_bar_alerts_only_on_the_next_morning(self) -> None:
        for hour in (15, 20):
            same_day = datetime(2026, 10, 13, hour, 30, tzinfo=VN)
            self.assertFalse(should_alert("Phiên 2026-10-13: Khóa 106", "no_bar", "2026-10-12", "2026-10-13", same_day))
        morning = datetime(2026, 10, 14, 8, 0, tzinfo=VN)
        self.assertTrue(should_alert("Phiên 2026-10-14: Khóa 106", "no_bar", "2026-10-12", "2026-10-13", morning))

    def test_a_holiday_run_alerts_once(self) -> None:
        # Nghỉ từ thứ Hai 2027-02-08: sáng thứ Ba báo, sáng thứ Tư và các ngày sau thì im.
        tuesday = datetime(2027, 2, 9, 8, 0, tzinfo=VN)
        wednesday = datetime(2027, 2, 10, 8, 0, tzinfo=VN)
        self.assertTrue(should_alert("", "no_bar", "2027-02-05", "2027-02-08", tuesday))
        self.assertFalse(should_alert("", "no_bar", "2027-02-05", "2027-02-09", wednesday))

    def test_failures_and_missing_states_always_alert(self) -> None:
        now = datetime(2026, 10, 13, 15, 30, tzinfo=VN)
        self.assertTrue(should_alert("Phiên lỗi: timeout", "ok", "2026-10-13", "2026-10-13", now))
        self.assertTrue(should_alert(BUSY_MESSAGE, "ok", "2026-10-13", "2026-10-13", now))
        self.assertTrue(should_alert("Phiên 2026-10-13", "no_state", "2026-10-13", "2026-10-13", now))
        self.assertFalse(should_alert("Phiên 2026-10-13", "ok", "2026-10-13", "2026-10-13", now))


class LostSessionTest(unittest.TestCase):
    def test_only_measured_sessions_behind_the_latest_bar_count(self) -> None:
        days = ["2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"]
        states = [("2026-10-14", 1.0)]
        # 2026-10-12 trước phép đo, 2026-10-15 là nến mới nhất còn ghi được.
        self.assertEqual(lost_sessions(days, states, set()), ["2026-10-13"])
        self.assertEqual(lost_sessions(days, states, {"2026-10-13"}), [])

    def _runs(self, outcomes: list[bool], configured: bool) -> tuple[list[tuple[str, bool]], int]:
        """Ngủ qua 15:30, 20:00 và 08:00, thức trong giờ giao dịch: lần 15:30 hôm sau mới thấy.

        `outcomes` là kết quả của từng lần gửi Telegram, theo thứ tự.
        """
        from unittest import mock

        from app import db, scheduled

        previous = os.environ.get("RESEARCH_DB_PATH")
        sends = iter(outcomes)
        attempts: list[str] = []

        async def fake_send(text: str) -> bool:
            attempts.append(text)
            return next(sends)

        async def fake_session(*_args, **_kwargs) -> str:
            return "Phiên 2026-10-14: Khóa 106"

        async def _run():
            os.environ["RESEARCH_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "research.db")
            await db.init_db()
            bar = {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}
            await db.replace_bars(
                "VNINDEX", [{"trade_date": day, **bar} for day in ("2026-10-12", "2026-10-13", "2026-10-14")]
            )
            await db.upsert_market_points(BREADTH_STATE_SERIES, [("2026-10-12", 1.0), ("2026-10-14", 1.0)])
            await db.close_db()
            now = datetime(2026, 10, 14, 15, 30, tzinfo=VN)
            with (
                mock.patch.object(scheduled, "run_session", fake_session),
                mock.patch.object(scheduled.notify, "send", fake_send),
                mock.patch.object(scheduled.notify, "configured", lambda: configured),
            ):
                return [await scheduled._once(now) for _ in range(len(outcomes) + 1)]

        try:
            results = asyncio.run(_run())
        finally:
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
        return results, len(attempts)

    def test_a_mac_asleep_through_every_run_is_reported_once(self) -> None:
        results, attempts = self._runs([True], configured=True)
        self.assertFalse(results[0][1])
        self.assertIn("Mất trạng thái độ rộng ở phiên 2026-10-13", results[0][0])
        self.assertTrue(results[1][1])
        self.assertEqual(attempts, 1)

    def test_a_failed_send_is_retried_on_the_next_run(self) -> None:
        results, attempts = self._runs([False, True], configured=True)
        self.assertEqual([ok for _text, ok in results], [False, False, True])
        self.assertEqual(attempts, 2)

    def test_without_telegram_the_loss_is_logged_once(self) -> None:
        results, attempts = self._runs([False], configured=False)
        self.assertEqual([ok for _text, ok in results], [False, True])
        self.assertEqual(attempts, 1)


if __name__ == "__main__":
    unittest.main()
