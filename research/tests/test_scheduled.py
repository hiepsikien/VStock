from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.pipeline import BUSY_MESSAGE
from app.scheduled import VN, breadth_line, expected_session, in_session, should_alert


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


if __name__ == "__main__":
    unittest.main()
