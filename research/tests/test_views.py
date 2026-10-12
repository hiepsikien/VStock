from __future__ import annotations

import unittest

from app.money import Money
from app.pattern import Regime
from app.views import (
    funnel,
    gate_chain,
    group_changes,
    held_by_market,
    lane_counts,
    market_headline,
    market_lights,
    paper_alerts,
    render_markdown,
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


if __name__ == "__main__":
    unittest.main()
