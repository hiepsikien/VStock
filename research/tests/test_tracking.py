from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime

from app import db
from app.breadth_filter import Counts
from app.scheduled import VN
from app.tracking import breadth_rows, filter_view, run_rows, schedule_view


class RunRowsTest(unittest.TestCase):
    def test_times_are_shown_in_vietnam_time_with_the_duration_and_source(self) -> None:
        rows = run_rows(
            [
                {
                    "started_at": "2026-10-13T08:30:00+00:00",
                    "finished_at": "2026-10-13T08:32:30+00:00",
                    "status": "ok",
                    "message": "Phiên 2026-10-13: Khóa 106",
                    "source": "lịch",
                },
                {"started_at": "2026-10-12T07:08:40+00:00", "finished_at": None, "status": "running", "message": "", "source": ""},
            ]
        )
        self.assertEqual((rows[0]["started"], rows[0]["seconds"], rows[0]["source"]), ("13/10 15:30", 150, "Lịch chạy"))
        self.assertEqual((rows[1]["seconds"], rows[1]["source"]), (None, "—"))


class ScheduleViewTest(unittest.TestCase):
    def test_a_closed_session_with_a_state_raises_no_warning(self) -> None:
        view = schedule_view(["2026-10-12", "2026-10-13"], [("2026-10-13", 1.0)], datetime(2026, 10, 13, 16, 0, tzinfo=VN))
        self.assertEqual(view["warning"], "")
        self.assertEqual((view["measured"], view["missing"]), (1, []))

    def test_a_closed_session_without_its_bar_or_its_state_is_flagged(self) -> None:
        now = datetime(2026, 10, 14, 16, 0, tzinfo=VN)
        no_bar = schedule_view(["2026-10-13"], [("2026-10-13", 1.0)], now)
        self.assertIn("chưa có nến VN-Index phiên 2026-10-14", no_bar["warning"])
        no_state = schedule_view(["2026-10-13", "2026-10-14"], [("2026-10-13", 1.0)], now)
        self.assertEqual(no_state["warning"], "Phiên 2026-10-14 chưa có trạng thái độ rộng.")
        self.assertEqual(no_state["missing"], ["2026-10-14"])

    def test_sessions_before_the_measurement_never_count_as_missing(self) -> None:
        view = schedule_view(["2026-10-09", "2026-10-12"], [], datetime(2026, 10, 12, 14, 0, tzinfo=VN))
        self.assertEqual((view["measured"], view["missing"]), (0, []))


class BreadthRowsTest(unittest.TestCase):
    def test_every_index_session_is_listed_newest_first_including_missed_ones(self) -> None:
        rows = breadth_rows(
            ["2026-10-09", "2026-10-13", "2026-10-14"],
            [("2026-10-09", 0.4), ("2026-10-14", 0.6)],
            [("2026-10-09", 0.0), ("2026-10-14", 1.0)],
        )
        self.assertEqual(
            [(row["day"], row["share"], row["open"], row["measured"]) for row in rows],
            [
                ("2026-10-14", 0.6, True, True),
                ("2026-10-13", None, None, True),
                ("2026-10-09", 0.4, False, False),
            ],
        )


class FilterViewTest(unittest.TestCase):
    def test_the_view_carries_counts_and_the_deadline_only(self) -> None:
        counts = Counts("2026-10-13", "2027-01-13", 3, 5, 1, 2, 0, 1, 63, 2)
        view = filter_view(counts)
        self.assertEqual(view["deadline"], "2031-10-13")
        self.assertTrue(view["started"])
        self.assertEqual(view["status"], "Chưa đủ điều kiện đo.")
        self.assertNotIn("%", view["status"])

    def test_before_the_first_session(self) -> None:
        view = filter_view(Counts("2026-10-13", "2026-10-09", 0, 0, 0, 0, 0, 0, 0, 0))
        self.assertFalse(view["started"])


class RunSourceTest(unittest.TestCase):
    def test_runs_record_their_source_and_old_stores_gain_the_column(self) -> None:
        previous = os.environ.get("RESEARCH_DB_PATH")
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "research.db")
        legacy = sqlite3.connect(path)
        legacy.execute(
            "CREATE TABLE runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, "
            "finished_at TEXT, status TEXT NOT NULL, message TEXT NOT NULL DEFAULT '')"
        )
        legacy.execute("INSERT INTO runs (started_at, status, message) VALUES ('2026-10-10T15:00:00+00:00', 'ok', 'cũ')")
        legacy.commit()
        legacy.close()

        async def _run():
            os.environ["RESEARCH_DB_PATH"] = path
            await db.close_db()
            await db.init_db()
            run_id = await db.start_run("lịch")
            await db.finish_run(run_id, "ok", "Phiên 2026-10-13")
            runs = await db.recent_runs(5)
            latest = await db.latest_run()
            await db.close_db()
            return runs, latest

        try:
            runs, latest = asyncio.run(_run())
        finally:
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
        self.assertEqual([(run["source"], run["message"]) for run in runs], [("lịch", "Phiên 2026-10-13"), ("", "cũ")])
        self.assertEqual(latest["source"], "lịch")


if __name__ == "__main__":
    unittest.main()
