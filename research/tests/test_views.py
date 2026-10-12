from __future__ import annotations

import unittest

from app.industry_screen import IndustryDay
from app.money import Money
from app.pattern import Regime
from app.views import (
    funnel,
    gate_chain,
    group_changes,
    held_by_market,
    hold_reason,
    industry_panel,
    lane_counts,
    market_headline,
    market_lights,
    paper_alerts,
    render_markdown,
    stamp_lights,
    status_changes,
)


def _item(symbol: str = "FPT", **fields) -> dict:
    item = {
        "symbol": symbol,
        "status": "Khóa",
        "open_status": "Được vào",
        "summary": "VN-Index dưới MA200",
        "open_summary": "Phá nền",
        "regime_open": False,
        "regime_reason": "VN-Index dưới MA200",
        "market_open": True,
        "macro_block": False,
        "macro_reason": "Vĩ mô trung tính: không có cảnh báo liên thị trường",
        "fa_label": "Đạt",
        "fa_reason": "Đạt cổng cơ bản",
        "valuation_label": "Đạt",
        "valuation_reason": "P/E 12",
        "news_state": "Mở",
        "news_reason": "",
        "pattern_ready": True,
        "pattern_reason": "Phá nền",
        "flow_state": "Mở",
        "flow_level": "neutral",
        "flow_reason": "",
        "industry_name": "tech",
        "industry_open": True,
    }
    item.update(fields)
    return item


class MarketLightsTest(unittest.TestCase):
    def _lights(self, regime: Regime, money: Money, verdicts=None):
        return market_lights(regime, money, verdicts or [_item()], 0.31, False)

    def test_the_index_under_its_average_locks_the_list_and_says_by_how_much(self) -> None:
        lights = self._lights(Regime(False, "dưới", 1700.0, 1800.0), Money(True, "Tiền chưa thắt"))
        headline = market_headline(lights)
        self.assertEqual(headline["state"], "closed")
        self.assertIn("VN-Index / MA200", headline["text"])
        self.assertIn("-5.6%", headline["text"])

    def test_gates_that_only_watch_never_lock_the_headline(self) -> None:
        """Độ rộng đóng nhưng chưa được phép khóa, nên câu đầu vẫn nói thị trường mở."""
        lights = self._lights(Regime(True, "trên", 1900.0, 1800.0), Money(True, "Tiền chưa thắt"))
        breadth = next(light for light in lights if light["key"] == "breadth")
        self.assertEqual((breadth["state"], breadth["enforced"]), ("closed", False))
        self.assertEqual(market_headline(lights)["state"], "open")

    def test_a_money_gate_without_numbers_reads_as_not_scored(self) -> None:
        lights = self._lights(Regime(True, "trên", 1900.0, 1800.0), Money(None, "Cổng tiền tệ chưa chấm: thiếu"))
        self.assertEqual(market_headline(lights)["state"], "unknown")

    def test_the_industry_light_counts_open_groups(self) -> None:
        verdicts = [_item("A", industry_name="tech", industry_open=True), _item("B", industry_name="bank", industry_open=False)]
        lights = self._lights(Regime(True, "trên", 1900.0, 1800.0), Money(True, ""), verdicts)
        industry = next(light for light in lights if light["key"] == "industry")
        self.assertEqual((industry["state"], industry["word"]), ("watch", "1/2 nhóm mở"))


class ListTest(unittest.TestCase):
    def test_a_locked_name_is_grouped_by_what_it_would_be_if_the_market_opened(self) -> None:
        rows = [_item("A"), _item("B", open_status="Loại"), _item("C", status="Theo dõi", open_status="")]
        self.assertTrue(held_by_market(rows[0]))
        self.assertFalse(held_by_market(rows[2]))
        self.assertEqual(lane_counts(rows), [("Được vào", 1), ("Theo dõi", 1), ("Loại", 1)])

    def test_the_funnel_narrows_layer_by_layer(self) -> None:
        rows = [
            _item("A"),
            _item("B", pattern_ready=False),
            _item("C", news_state="Chờ"),
            _item("D", fa_label="Không đạt"),
        ]
        counts = [step["count"] for step in funnel(rows)]
        self.assertEqual(counts, [4, 3, 2, 1, 1, 0])

    def test_changes_name_the_status_or_the_status_if_the_market_opened(self) -> None:
        rows = [_item("A"), _item("B", open_status="Theo dõi"), _item("C"), _item("D")]
        previous = {
            "A": ("Chưa chấm", ""),
            "B": ("Khóa", "Được vào"),
            "C": ("Khóa", "Được vào"),
            "E": ("Khóa", "Loại"),
        }
        changes = status_changes(rows, previous)
        self.assertEqual(
            [(change["symbol"], change["kind"]) for change in changes],
            [("B", "open"), ("A", "status"), ("D", "new")],
        )
        grouped = group_changes(status_changes([_item("A"), _item("B")], {"A": ("Chưa chấm", ""), "B": ("Chưa chấm", "")}))
        self.assertEqual(grouped, [{"kind": "status", "before": "Chưa chấm", "after": "Khóa", "symbols": ["A", "B"]}])


class PaperAlertTest(unittest.TestCase):
    def test_a_slot_near_its_stop_or_its_clock_is_flagged(self) -> None:
        base = {"entry_price": 100.0, "stop_price": 95.0, "exit_date": None, "tp1_done": 0}
        rows = [
            {**base, "symbol": "NEAR", "last_price": 97.0, "sessions": 3},
            {**base, "symbol": "SAFE", "last_price": 110.0, "sessions": 3},
            {**base, "symbol": "OLD", "last_price": 110.0, "sessions": 27},
            {**base, "symbol": "SHUT", "last_price": 96.0, "sessions": 29, "exit_date": "2026-10-01"},
        ]
        alerts = paper_alerts(rows)
        self.assertEqual([(alert["symbol"], alert["level"]) for alert in alerts], [("NEAR", "bad"), ("OLD", "wait")])


class GateChainTest(unittest.TestCase):
    def test_the_first_closed_gate_is_the_one_that_decides(self) -> None:
        chain = gate_chain(_item())
        decides = [step["name"] for step in chain if step.get("decides")]
        self.assertEqual(decides, ["Thị trường"])

    def test_a_row_stored_before_open_status_still_reads_the_market_flags(self) -> None:
        chain = gate_chain(_item(open_status="", open_summary=""))
        self.assertEqual(chain[0]["state"], "closed")

    def test_a_missing_pe_does_not_decide(self) -> None:
        item = _item(
            status="Theo dõi", open_status="Theo dõi", regime_open=True, pattern_ready=False,
            valuation_label="Chưa có số",
        )
        chain = gate_chain(item)
        self.assertEqual([step["name"] for step in chain if step.get("decides")], ["Nền giá"])
        self.assertEqual(chain[2]["word"], "Chưa có số")

    def test_an_entry_has_no_deciding_gate(self) -> None:
        item = _item(status="Được vào", open_status="Được vào", regime_open=True)
        self.assertFalse(any(step.get("decides") for step in gate_chain(item)))

    def _decides(self, chain: list[dict]) -> list[str]:
        return [step["name"] for step in chain if step.get("decides")]

    def test_macro_blocking_an_entry_names_macro_not_the_index(self) -> None:
        item = _item(
            status="Theo dõi", summary="Vĩ mô chặn vào: Vĩ mô căng: USD tăng nhanh",
            regime_open=True, regime_reason="VN-Index trên MA200", macro_block=True,
            macro_reason="Vĩ mô căng: USD tăng nhanh",
        )
        chain = gate_chain(item)
        self.assertEqual(self._decides(chain), ["Thị trường"])
        self.assertEqual(chain[0]["state"], "closed")
        self.assertTrue(chain[0]["detail"].startswith("Vĩ mô chặn vào"))

    def test_macro_numbers_that_failed_to_load_read_as_not_scored(self) -> None:
        item = _item(
            status="Theo dõi", summary="Vĩ mô chưa có số: không tải được chuỗi vĩ mô",
            regime_open=True, macro_block=False, macro_reason="",
        )
        chain = gate_chain(item)
        self.assertEqual(self._decides(chain), ["Thị trường"])
        self.assertEqual((chain[0]["state"], chain[0]["word"]), ("unknown", "Chưa chấm"))

    def test_macro_does_not_decide_a_name_its_own_layers_already_stopped(self) -> None:
        item = _item(
            status="Loại", open_status="Loại", summary="Có tin chặn", open_summary="Có tin chặn",
            regime_open=True, macro_block=True, news_state="Loại",
            macro_reason="Vĩ mô căng: USD tăng nhanh",
        )
        chain = gate_chain(item)
        self.assertEqual(self._decides(chain), ["Tin"])
        self.assertEqual((chain[0]["state"], chain[0]["word"]), ("watch", "Vĩ mô chặn lệnh mới"))

    def test_missing_market_numbers_read_as_not_scored(self) -> None:
        item = _item(
            status="Chưa chấm", open_status="Theo dõi", summary="Cổng tiền tệ chưa chấm: thiếu lãi suất liên ngân hàng",
            open_summary="Chưa phá nền", regime_open=True, market_open=None, pattern_ready=False,
        )
        chain = gate_chain(item)
        self.assertEqual(self._decides(chain), ["Thị trường"])
        self.assertEqual((chain[0]["state"], chain[0]["word"]), ("unknown", "Chưa chấm"))
        self.assertEqual(chain[0]["detail"], item["summary"])

    def test_missing_numbers_on_both_sides_still_name_the_market_first(self) -> None:
        item = _item(
            status="Chưa chấm", open_status="Chưa chấm", summary="VN-Index chưa đủ 200 phiên",
            open_summary="Thiếu báo cáo quý", regime_open=None, fa_label="Chưa đủ số",
        )
        self.assertEqual(self._decides(gate_chain(item)), ["Thị trường"])

    def test_a_blocking_news_item_decides_before_missing_fundamentals(self) -> None:
        item = _item(
            status="Loại", open_status="Loại", summary="Có tin chặn", open_summary="Có tin chặn",
            regime_open=True, fa_label="Chưa đủ số", news_state="Loại",
        )
        self.assertEqual(self._decides(gate_chain(item)), ["Tin"])

    def test_an_unadjusted_price_decides_on_the_price_base(self) -> None:
        item = _item(
            status="Chưa chấm", open_status="Chưa chấm", summary="Giá chưa chỉnh chia tách",
            open_summary="Giá chưa chỉnh chia tách", pattern_reason="Giá chưa chỉnh chia tách",
            regime_open=True, pattern_ready=False, news_state="Loại",
        )
        self.assertEqual(self._decides(gate_chain(item)), ["Nền giá"])

    def test_a_row_stored_before_open_status_reads_macro_from_its_summary(self) -> None:
        item = _item(
            status="Theo dõi", open_status="", open_summary="", summary="Vĩ mô chặn vào: Vĩ mô căng",
            regime_open=True, macro_block=True,
        )
        self.assertEqual(self._decides(gate_chain(item)), ["Thị trường"])
        legacy_loai = _item(
            status="Loại", open_status="", open_summary="", summary="Không đạt cổng cơ bản",
            regime_open=True, macro_block=True, fa_label="Không đạt",
        )
        self.assertEqual(self._decides(gate_chain(legacy_loai)), ["Cơ bản"])


class HoldTest(unittest.TestCase):
    def test_the_reason_the_list_is_held_names_lock_missing_numbers_or_macro(self) -> None:
        macro = _item(status="Theo dõi", summary="Vĩ mô chặn vào: căng")
        self.assertEqual(hold_reason([macro, _item("B", status="Loại", open_status="Loại")]), "macro")
        self.assertEqual(hold_reason([macro, _item("C")]), "locked")
        self.assertEqual(hold_reason([_item(status="Chưa chấm")]), "unknown")
        self.assertEqual(hold_reason([_item(status="Loại", open_status="Loại")]), "")

    def test_lights_that_read_a_later_day_than_the_table_are_flagged(self) -> None:
        lights = [{"key": "index"}, {"key": "macro"}, {"key": "breadth"}]
        stale = stamp_lights(lights, {"index": "2026-10-13", "macro": "2026-10-12"}, "2026-10-12")
        self.assertTrue(stale)
        self.assertEqual([light["stale"] for light in lights], [True, False, False])
        self.assertFalse(stamp_lights(lights, {"index": "2026-10-12"}, "2026-10-12"))


class IndustryPanelTest(unittest.TestCase):
    DAYS = ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12"]

    def test_an_open_group_says_since_when_and_which_conditions_hold(self) -> None:
        closed = IndustryDay(own=0.01, index=0.02, lead=0.05, credit=None, regime=False, open=False)
        opened = IndustryDay(own=0.08, index=0.02, lead=0.05, credit=None, regime=False, open=True)
        tech = IndustryDay(own=0.05, index=0.02, lead=None, credit=None, regime=False, open=False)
        rows = industry_panel(
            self.DAYS,
            {"tech": [tech] * 5, "energy": [closed, closed, opened, opened, opened]},
            {"energy": ["GAS", "PLX", "PVS"], "tech": ["FPT", "CMG", "ELC"]},
            60,
        )
        energy, tech_row = rows
        self.assertEqual(energy["code"], "energy")
        self.assertEqual((energy["open"], energy["since"], energy["since_known"], energy["sessions"]), (True, "2026-10-08", True, 3))
        self.assertEqual([(c["ok"], c["name"]) for c in energy["conditions"]], [(True, "Nhóm mạnh hơn VN-Index 60 phiên"), (True, "Giá dầu tăng 60 phiên")])
        self.assertIn("chênh +6.0%", energy["conditions"][0]["value"])
        self.assertEqual(energy["changes"], [{"day": "2026-10-08", "open": True}])
        self.assertEqual([(s["open"], s["width"]) for s in energy["strip"]], [(False, 40.0), (True, 60.0)])
        self.assertAlmostEqual(energy["open_share"], 0.6)

    def test_a_group_closed_all_along_names_the_failing_condition(self) -> None:
        tech = IndustryDay(own=0.05, index=0.02, lead=None, credit=None, regime=False, open=False)
        (row,) = industry_panel(self.DAYS, {"tech": [tech] * 5}, {"tech": ["FPT"]}, 60)
        self.assertFalse(row["since_known"])
        self.assertEqual(
            [(c["name"], c["ok"], c["value"]) for c in row["conditions"]][-1], ("VN-Index trên MA200", False, "dưới")
        )


class MarkdownTest(unittest.TestCase):
    def test_reports_render_headings_tables_lists_and_escape_html(self) -> None:
        text = "# Cổng\n\nĐoạn **đậm** và `mã` <b>.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n- một\n- hai\n"
        out = render_markdown(text)
        self.assertIn("<h2>Cổng</h2>", out)
        self.assertIn("<strong>đậm</strong>", out)
        self.assertIn("<code>mã</code>", out)
        self.assertIn("&lt;b&gt;", out)
        self.assertIn("<th>A</th>", out)
        self.assertIn("<td>2</td>", out)
        self.assertIn("<ul><li>một</li><li>hai</li></ul>", out)

    def test_a_quote_in_a_link_stays_inside_the_href(self) -> None:
        out = render_markdown('[x](https://a.b/"onmouseover="alert(1))')
        self.assertNotIn('"onmouseover', out)
        self.assertIn("&quot;onmouseover=&quot;", out)

    def test_a_product_is_not_italic_and_code_is_left_alone(self) -> None:
        self.assertNotIn("<em>", render_markdown("Lãi = a * b * c"))
        self.assertIn("<em>nghiêng</em>", render_markdown("chữ *nghiêng* ở đây"))
        out = render_markdown("Viết `**x**` và **đậm**")
        self.assertIn("<code>**x**</code>", out)
        self.assertIn("<strong>đậm</strong>", out)


if __name__ == "__main__":
    unittest.main()
