from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app import db, ingest
from app.config import MARKET_MIN_SESSIONS
from app.evaluate import compose
from app.money import LABELS, Money, money_state, thresholds
from app.pattern import Pattern, Regime

# Mọi chuỗi giá trong test đứng trong tháng 9 để as_of nằm gần số mới nhất.
START = date(2026, 9, 1)
AS_OF = "2026-09-06"
# Trang /market dựng bằng chính template của app để câu chữ trên đó cũng có test.
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _series(values: list[float]) -> list[tuple[str, float]]:
    return [
        ((START + timedelta(days=index)).isoformat(), float(value))
        for index, value in enumerate(values)
    ]


def _market(**overrides: list[float]) -> dict[str, list[tuple[str, float]]]:
    """Sáu phiên cho mỗi chuỗi giá, cộng bảng lãi điều hành: vừa đủ để cổng chấm."""
    points: dict[str, list[tuple[str, float]]] = {
        "INTERBANK_ON": _series([5.0, 5.0, 5.0, 5.0, 5.0, 5.0]),
        "GOV10Y": _series([4.0, 4.0, 4.0, 4.0, 4.0, 4.0]),
        "USDVND": _series([25_000.0, 25_000.0, 25_000.0, 25_000.0, 25_000.0, 25_000.0]),
    }
    points.update(overrides)
    return points


class MoneyGateTest(unittest.TestCase):
    def test_missing_series_sends_the_gate_to_chua_cham(self) -> None:
        gate = money_state({}, as_of=AS_OF, required=("INTERBANK_ON", "GOV10Y", "USDVND", "POLICY_RATE"))
        self.assertIsNone(gate.open)
        self.assertIn("Cổng tiền tệ chưa chấm", gate.reason)
        # Chuỗi bậc thang của lãi điều hành đứng sẵn, ba chuỗi còn lại chưa có số nào.
        self.assertEqual(gate.ready, ("POLICY_RATE",))
        self.assertIn("INTERBANK_ON", gate.missing)
        self.assertIn("USDVND", gate.missing)
        self.assertIn(LABELS["GOV10Y"], gate.reason)
        # Chưa có số nào là nhóm "absent"; nhóm "short" dành cho chuỗi có số mà chưa đủ phiên.
        self.assertEqual(set(gate.absent), {"INTERBANK_ON", "GOV10Y", "USDVND"})
        self.assertEqual(gate.short, ())

    def test_gate_ignores_missing_overnight_and_bond_yield_by_default(self) -> None:
        """Lãi qua đêm và TPCP 10Y chưa có lịch sử nên không bắt buộc trong cổng mặc định."""
        points = {"USDVND": _series([25_000.0] * 6)}
        gate = money_state(points, as_of=AS_OF)
        self.assertTrue(gate.open)
        self.assertNotIn("INTERBANK_ON", gate.missing)
        self.assertNotIn("GOV10Y", gate.missing)

    def test_quiet_market_opens_the_gate(self) -> None:
        gate = money_state(_market(), as_of=AS_OF)
        self.assertTrue(gate.open)
        self.assertEqual(gate.flags, ())
        self.assertEqual(gate.ready, ("INTERBANK_ON", "GOV10Y", "USDVND", "POLICY_RATE"))
        self.assertIn("Tiền chưa thắt", gate.reason)

    def test_overnight_rate_above_its_average_is_tight(self) -> None:
        gate = money_state(_market(INTERBANK_ON=_series([5.0] * 5 + [6.3])), as_of=AS_OF)
        self.assertFalse(gate.open)
        self.assertIn("lãi qua đêm", gate.reason)
        # Một nhịp nhỏ hơn ngưỡng đã khai báo thì chưa gọi là thắt.
        small = money_state(_market(INTERBANK_ON=_series([5.0] * 5 + [5.6])), as_of=AS_OF)
        self.assertTrue(small.open)

    def test_government_yield_above_its_average_is_tight(self) -> None:
        gate = money_state(_market(GOV10Y=_series([4.0] * 5 + [4.7])), as_of=AS_OF)
        self.assertFalse(gate.open)
        self.assertIn("lợi suất 10 năm", gate.reason)

    def test_fx_pressure_needs_the_declared_streak(self) -> None:
        one_day = money_state(_market(USDVND=_series([25_000.0] * 5 + [25_500.0])), as_of=AS_OF)
        self.assertTrue(one_day.open)
        # Các chuỗi giá đều phải có điểm của phiên 2026-09-15, nên chuỗi dài đi kèm chuỗi dài.
        held = money_state(
            _market(
                INTERBANK_ON=_series([5.0] * 15),
                GOV10Y=_series([4.0] * 15),
                USDVND=_series([25_000.0] * 10 + [25_750.0] * 5),
            ),
            as_of="2026-09-15",
        )
        self.assertFalse(held.open)
        self.assertIn("tỷ giá trên trung bình", held.reason)

    def test_a_later_point_never_reaches_an_earlier_session(self) -> None:
        """Số của hôm nay không được lấy để chấm lại phiên đã qua."""
        points = _market(INTERBANK_ON=_series([5.0] * 6 + [6.5]))
        self.assertTrue(money_state(points, as_of=AS_OF).open)
        self.assertFalse(money_state(points, as_of="2026-09-07").open)

    def test_a_series_without_a_point_for_the_session_counts_as_missing(self) -> None:
        """Chuỗi giá phải có điểm đúng phiên đang chấm, không mượn số của phiên trước."""
        # Số mới nhất là 2026-09-06, nên phiên 09-08 chỉ cách hai ngày vẫn không có số của mình:
        # nguồn chết trong phiên thì cổng đứng Chưa chấm, chứ không mở bằng số hôm qua.
        near = money_state(_market(), as_of="2026-09-08", required=("INTERBANK_ON", "GOV10Y", "USDVND", "POLICY_RATE"))
        self.assertIsNone(near.open)
        self.assertEqual(set(near.missing), {"INTERBANK_ON", "GOV10Y", "USDVND"})
        self.assertTrue(
            any("chưa có số của phiên 2026-09-08" in value for _label, value in near.metrics)
        )
        # Số cũ không dùng được cho phiên này, nên chuỗi thuộc nhóm chưa có số, không phải nhóm
        # có số mà thiếu phiên.
        self.assertEqual(set(near.absent), {"INTERBANK_ON", "GOV10Y", "USDVND"})
        self.assertEqual(near.short, ())
        # Và phiên cách cả tháng cũng vậy: không có chuyện số cũ dùng được trong bao nhiêu ngày.
        far = money_state(_market(), as_of="2026-10-10", required=("INTERBANK_ON", "GOV10Y", "USDVND", "POLICY_RATE"))
        self.assertIsNone(far.open)
        self.assertEqual(set(far.missing), {"INTERBANK_ON", "GOV10Y", "USDVND"})

    def test_a_series_with_too_few_sessions_is_not_counted_as_no_number(self) -> None:
        """Chuỗi mới có một phiên thì có số, chỉ chưa đủ: cổng Chưa chấm, và nói đúng vì sao."""
        thin = money_state(
            {"INTERBANK_ON": _series([5.0]), "GOV10Y": _series([4.0])},
            as_of=START.isoformat(),
            required=("INTERBANK_ON", "GOV10Y", "USDVND", "POLICY_RATE"),
        )
        self.assertIsNone(thin.open)
        self.assertEqual(
            thin.short,
            (
                ("INTERBANK_ON", 1, MARKET_MIN_SESSIONS),
                ("GOV10Y", 1, MARKET_MIN_SESSIONS),
            ),
        )
        self.assertEqual(thin.absent, ("USDVND",))
        self.assertIn("chưa đủ số phiên", thin.reason)
        self.assertIn(f"{LABELS['INTERBANK_ON']} (1/{MARKET_MIN_SESSIONS} phiên)", thin.reason)
        self.assertIn(f"chưa có số của phiên {START.isoformat()}", thin.reason)
        self.assertTrue(
            any(f"— 1/{MARKET_MIN_SESSIONS} phiên đã lưu" in value for _label, value in thin.metrics)
        )

    def test_a_policy_step_inside_the_lookback_is_tight(self) -> None:
        """Mốc cũ đứng ngoài 90 ngày, mốc mới đứng trong: nâng lãi vẫn là chuyện mới."""
        rising = money_state(
            _market(POLICY_RATE=[("2026-05-01", 4.5), ("2026-08-01", 5.0)]), as_of=AS_OF
        )
        self.assertFalse(rising.open)
        self.assertIn("lãi điều hành", rising.reason)
        # Nâng lãi đã cũ hơn 90 ngày: mức đang hiệu lực không còn là chuyện mới.
        older = money_state(
            _market(POLICY_RATE=[("2025-01-01", 4.0), ("2025-06-01", 4.5)]), as_of=AS_OF
        )
        self.assertTrue(older.open)

    def test_omo_drain_locks_the_gate_without_a_source(self) -> None:
        """Chuỗi chưa có nguồn công khai vẫn khai báo ngưỡng, nên nó khóa được khi có số."""
        gate = money_state(_market(NHNN_NET=_series([-2000.0] * 5)), as_of=AS_OF)
        self.assertFalse(gate.open)
        self.assertIn("hút ròng", gate.reason)
        self.assertEqual(gate.missing, ())

    def test_thresholds_are_written_down(self) -> None:
        written = dict(thresholds())
        self.assertIn("20 phiên", written[LABELS["INTERBANK_ON"]])
        self.assertIn("90 ngày", written[LABELS["POLICY_RATE"]])
        self.assertIn("phiên đang chấm", written["Điểm của phiên đang chấm"])
        self.assertEqual(len(written), len(LABELS) + 2)


class MarketPageCopyTest(unittest.TestCase):
    """Trang /market nói đúng số phiên từng chuỗi cần, không dùng một số phiên chung cho mọi chuỗi."""

    def _page(self, gate: Money) -> str:
        return TEMPLATES.get_template("market.html").render(
            money=gate,
            rows=[],
            thresholds=[],
            missing=[LABELS.get(code, code) for code in gate.absent],
            short=[(LABELS.get(code, code), have, need) for code, have, need in gate.short],
            policy=[],
            latest_day="",
        )

    def test_the_banner_carries_each_series_own_floor(self) -> None:
        """Bảng lãi điều hành cần 2 mốc, không phải 5: một con số chung ở banner là nói sai."""
        gate = money_state({"POLICY_RATE": [("2026-09-01", 4.5)]}, as_of="2026-09-01")
        self.assertEqual(gate.short, (("POLICY_RATE", 1, 2),))
        page = self._page(gate)
        self.assertIn(f"{LABELS['POLICY_RATE']} (1/2)", page)
        self.assertIn("chưa đủ số phiên", page)
        self.assertNotIn("chưa đủ 5 phiên", page)

    def test_the_banner_names_the_series_with_no_number_apart(self) -> None:
        """Chuỗi chưa có số nào không được lẫn với chuỗi có số mà chưa đủ phiên."""
        page = self._page(money_state({}, as_of=AS_OF, required=("INTERBANK_ON", "GOV10Y", "USDVND", "POLICY_RATE")))
        self.assertIn(f"Chưa có số: {LABELS['INTERBANK_ON']}", page)
        self.assertNotIn("Có số nhưng chưa đủ", page)


class ComposeGateTest(unittest.TestCase):
    def _compose(self, **kwargs):
        return compose(
            "FPT",
            date(2026, 10, 10),
            {},
            [],
            Regime(True, "VN-Index trên MA200", 1200, 1100),
            Pattern(True, "Phá nền", 0.08, 90),
            require_clock=True,
            **kwargs,
        )

    def test_a_missing_series_marks_the_row_chua_cham(self) -> None:
        verdict = self._compose(market=money_state({}))
        self.assertEqual(verdict.status, "Chưa chấm")
        self.assertIn("Cổng tiền tệ chưa chấm", verdict.summary)
        self.assertIsNone(verdict.market_open)

    def test_tight_money_locks_the_row(self) -> None:
        tight = money_state(_market(INTERBANK_ON=_series([5.0] * 5 + [6.4])), as_of=AS_OF)
        verdict = self._compose(market=tight)
        self.assertEqual(verdict.status, "Khóa")
        self.assertTrue(verdict.summary.startswith("Tiền thắt"))
        self.assertFalse(verdict.market_open)
        self.assertEqual(verdict.market_reason, verdict.summary)

    def test_open_money_leaves_the_name_alone(self) -> None:
        verdict = self._compose(market=money_state(_market(), as_of=AS_OF))
        self.assertTrue(verdict.market_open)
        self.assertNotIn("Cổng tiền tệ", verdict.summary)
        self.assertNotEqual(verdict.status, "Khóa")

    def test_the_numbers_land_in_the_market_section(self) -> None:
        verdict = self._compose(market=money_state(_market(), as_of=AS_OF))
        groups = dict(verdict.metric_groups)
        labels = [label for label, _value in groups["Thị trường"]]
        self.assertIn(LABELS["INTERBANK_ON"], labels)
        self.assertIn(LABELS["GOV10Y"], labels)


class MarketStoreTest(unittest.TestCase):
    def test_a_session_rewrites_its_own_point_only(self) -> None:
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
            await db.upsert_market_points(
                "INTERBANK_ON", [("2026-09-01", 5.0), ("2026-09-02", 5.1)]
            )
            await db.upsert_market_points(
                "INTERBANK_ON", [("2026-09-02", 5.4), ("2026-09-03", 5.2)]
            )
            points = await db.market_points()
            self.assertEqual(
                points["INTERBANK_ON"],
                [("2026-09-01", 5.0), ("2026-09-02", 5.4), ("2026-09-03", 5.2)],
            )
            # A feed that is down stores nothing, so it cannot overwrite a good session.
            await db.upsert_market_points("GOV10Y", [])
            self.assertIsNone((await db.market_points()).get("GOV10Y"))
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            for suffix in ("", "-wal", "-shm"):
                Path(path + suffix).unlink(missing_ok=True)


class MarketFeedTest(unittest.TestCase):
    def test_one_point_per_series_and_a_policy_step(self) -> None:
        asyncio.run(self._feed())

    async def _feed(self) -> None:
        client = _FakeClient({"ECONOMICS:VNINBR": (200, {"close": 6.47})})
        points = await ingest.fetch_market(client, "2026-09-06")
        self.assertEqual(points["INTERBANK_ON"], [("2026-09-06", 6.47)])
        self.assertIn("POLICY_RATE", points)
        self.assertGreater(len(points["POLICY_RATE"]), 1)

    def test_a_failed_series_is_left_out(self) -> None:
        asyncio.run(self._failed())

    async def _failed(self) -> None:
        client = _FakeClient(
            {
                "ECONOMICS:VNINBR": (200, {"code": "symbol_not_exists"}),
                "TVC:VN10Y": (200, {"close": 4.58}),
            }
        )
        points = await ingest.fetch_market(client, "2026-09-06")
        self.assertNotIn("INTERBANK_ON", points)
        self.assertEqual(points["GOV10Y"], [("2026-09-06", 4.58)])

    def test_fx_falls_back_to_the_second_quote(self) -> None:
        asyncio.run(self._fallback())

    async def _fallback(self) -> None:
        yahoo = ingest.YAHOO_CHART.format(symbol="USDVND%3DX")
        client = _FakeClient(
            {
                "FX_IDC:USDVND": (200, {"code": "symbol_not_exists"}),
                yahoo: (
                    200,
                    {"chart": {"result": [{"indicators": {"quote": [{"close": [25_800.0]}]}}]}},
                ),
            }
        )
        points = await ingest.fetch_market(client, "2026-09-06")
        self.assertEqual(points["USDVND"], [("2026-09-06", 25_800.0)])
        self.assertIn(yahoo, client.calls)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    """Canned payloads per symbol, so the feeds are exercised without the network."""

    def __init__(self, answers: dict):
        self.answers = answers
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs) -> _FakeResponse:
        symbol = (kwargs.get("params") or {}).get("symbol") or url
        self.calls.append(symbol)
        status, payload = self.answers.get(symbol, (200, {}))
        return _FakeResponse(status, payload)
