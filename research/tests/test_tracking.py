from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime

from app import db
from app.breadth_filter import Counts
from app.jobs import Job, status_line
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


def _with_store(body):
    """Run `body` against a fresh research store and give back what it returns."""
    previous = os.environ.get("RESEARCH_DB_PATH")

    async def _run():
        os.environ["RESEARCH_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "research.db")
        await db.close_db()
        await db.init_db()
        try:
            return await body()
        finally:
            await db.close_db()

    try:
        return asyncio.run(_run())
    finally:
        if previous is None:
            os.environ.pop("RESEARCH_DB_PATH", None)
        else:
            os.environ["RESEARCH_DB_PATH"] = previous


class JobTest(unittest.TestCase):
    def test_a_double_click_runs_once_and_the_result_outlives_the_process(self) -> None:
        calls: list[int] = []

        async def slow():
            calls.append(1)
            await asyncio.sleep(0.2)
            return {"trade_count": 3}

        async def body():
            job = Job("walk")
            self.assertTrue(job.start(["run", 1], slow))
            self.assertFalse(job.start(["run", 1], slow))
            running = await job.state(["run", 1])
            await job.task
            # A new Job stands in for the web process after a restart.
            current = await Job("walk").state(["run", 1])
            moved = await Job("walk").state(["run", 2])
            return running, current, moved

        running, current, moved = _with_store(body)
        self.assertEqual(len(calls), 1)
        self.assertTrue(running["running"])
        self.assertIsNone(running["result"])
        self.assertEqual((current["result"], current["stale"], current["running"]), ({"trade_count": 3}, False, False))
        self.assertTrue(moved["stale"])

    def test_a_failure_is_stored_as_the_error(self) -> None:
        async def broken():
            raise SystemExit("Kho chưa có nến")

        async def body():
            job = Job("count")
            job.start(None, broken)
            await job.task
            return await job.state(None)

        state = _with_store(body)
        self.assertEqual(state["error"], "Kho chưa có nến")


class StatusLineTest(unittest.TestCase):
    def _line(self, **state) -> dict:
        base = {"running": False, "started": "", "at": "", "result": None, "error": "", "stale": False}
        return status_line(
            {**base, **state},
            what="phép đo trên 106 mã",
            button="Chạy phép đo",
            takes="Thường mất vài phút",
            refresh=20,
            session_busy=False,
        )

    def test_each_state_says_what_to_do(self) -> None:
        self.assertIn("Chưa tính phép đo trên 106 mã. Bấm “Chạy phép đo”", self._line()["text"])
        running = self._line(running=True, started="15:40:00 12/10", result={"n": 1}, at="09:00:00 12/10")
        self.assertIn("bắt đầu lúc 15:40:00 12/10", running["text"])
        self.assertIn("lần tính lúc 09:00:00 12/10", running["text"])
        stale = self._line(result={"n": 1}, at="09:00:00 12/10", stale=True)
        self.assertEqual(stale["kind"], "bad")
        self.assertIn("có thể đã cũ", stale["text"])
        self.assertIn("khớp", self._line(result={"n": 1}, at="09:00:00 12/10")["text"])
        failed = self._line(result={"error": "hỏng"}, error="hỏng", at="09:00:00 12/10")
        self.assertEqual((failed["kind"], failed["text"]), ("bad", "Lần tính lúc 09:00:00 12/10 lỗi: hỏng"))


class BacktestWalkTest(unittest.TestCase):
    def test_opening_pages_never_starts_work_and_the_buttons_do(self) -> None:
        from unittest import mock

        import httpx

        from app import web

        walks: list[int] = []
        counts: list[int] = []

        async def fake_walk(_inputs):
            walks.append(1)
            return {
                "error": None,
                "strategy_return": 0.1,
                "index_return": 0.05,
                "trade_count": 0,
                "slots": 5,
                "sessions": 1,
                "start": "2026-01-02",
                "end": "2026-10-12",
                "win_rate": None,
                "average_sessions": None,
                "max_drawdown": 0.0,
                "passed": True,
                "assumptions": "",
                "exit_counts": [],
                "trades": [],
            }

        async def fake_count():
            counts.append(1)
            return Counts("2026-10-13", "2026-10-12", 0, 0, 0, 0, 0, 0, 0, 0)

        async def body():
            web.backtest_job, web.filter_job = Job("backtest_walk"), Job("breadth_filter_counts")
            transport = httpx.ASGITransport(app=web.app)
            with (
                mock.patch.object(web, "run_walk", fake_walk),
                mock.patch.object(web, "count_filter_sample", fake_count),
                mock.patch.object(web, "load_exchanges", dict),
            ):
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    pages = [await client.get(path) for path in ("/", "/backtest", "/market", "/backtest")]
                    opened = (len(walks), len(counts))
                    await client.post("/backtest/run")
                    await client.post("/market/filter-count")
                    await web.backtest_job.task
                    await web.filter_job.task
                    after = (await client.get("/backtest")).text, (await client.get("/market")).text
            return pages, opened, after

        pages, opened, (backtest, market) = _with_store(body)
        self.assertEqual([page.status_code for page in pages], [200] * 4)
        self.assertEqual(opened, (0, 0))
        self.assertIn("Chưa tính phép đo", pages[1].text)
        self.assertIn("Chưa tính mẫu bộ lọc độ rộng", pages[2].text)
        self.assertEqual((len(walks), len(counts)), (1, 1))
        self.assertIn("khớp với lần chạy phiên", backtest)
        self.assertIn("khớp với lần chạy phiên", market)

    def test_the_worker_process_gets_the_industry_table_of_the_web_process(self) -> None:
        from app import industries, web

        saved = industries.industry_labels()

        async def _run():
            industries.set_industry_map({"ZZZ": "bank"})
            try:
                # Một lần đo trên kho rỗng: chỉ cần đi hết đường gửi sang worker và nhận về.
                return await web.run_walk(([], {}, {}, {}, {}, {}, {}))
            finally:
                if web._pool is not None:
                    web._pool.shutdown(wait=True)
                    web._pool = None

        try:
            result = asyncio.run(_run())
        finally:
            industries.set_industry_map(saved)
        self.assertIsInstance(result, dict)

    def test_the_wrapper_attaches_the_table_before_walking(self) -> None:
        from app import industries
        from app.backtest import run_backtest_with_industries

        saved = industries.industry_labels()
        try:
            run_backtest_with_industries({"ZZZ": "bank"}, [], {}, {}, {})
            self.assertEqual(industries.industry_labels(), {"ZZZ": "bank"})
        finally:
            industries.set_industry_map(saved)


if __name__ == "__main__":
    unittest.main()
