from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.classify import classify_article
from app.evaluate import compose, latest_due_quarter_end, score_fundamentals
from app.ingest import parse_vietstock_filings
from app.pattern import Pattern, Regime, assess_pattern, market_regime


def _regime_open() -> Regime:
    return Regime(True, "VN-Index trên MA200", 1200, 1100)


def _pattern(ready: bool = False) -> Pattern:
    if ready:
        return Pattern(True, "Phá nền", 0.08, 90)
    return Pattern(False, "Nền giá: chưa phá đỉnh nền", 0.02, 90)


def _corporate_points(**overrides: float) -> dict:
    report = "2026-06-30"
    dates = ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", report]
    values = {
        "NET_SALES_QR": 100.0,
        "NET_SALES_QR_GRYOY": 0.10,
        "NET_PROFIT_QR": 10.0,
        "NET_PROFIT_QR_GRYOY": 0.12,
        "OPERATING_PROFIT_QR_GRYOY": 0.08,
        "CFO_TO_SALES_QR": 0.15,
        "DEBT_TO_EQUITY_AQ": 0.40,
    }
    values.update(overrides)
    points = {code: [(report, value)] for code, value in values.items()}
    points["OUTSTANDING_SHARES"] = [(day, 100.0) for day in dates]
    return points


def _earnings(day: str = "2026-07-20") -> dict:
    return {
        "published_at": day,
        "symbols": ["FPT"],
        "kind": "earnings_release",
        "title": "FPT công bố báo cáo tài chính quý 2",
    }


class RulesTest(unittest.TestCase):
    def test_due_quarter_before_deadline(self) -> None:
        self.assertEqual(latest_due_quarter_end(date(2026, 10, 10)), date(2026, 6, 30))

    def test_commentary_is_ignored(self) -> None:
        label = classify_article("Cổ phiếu tâm điểm hôm nay", "", "stock_news")
        self.assertEqual(label.kind, "ignore")

    def test_vietstock_filing_is_the_earnings_clock(self) -> None:
        html = """
        _NewsData=[
          {"ArticleID":1481060,"Title":"VCB: BCTC Hợp nhất 6 tháng đầu năm 2026 ",
           "PublishTime":"/Date(1786640400000)/","ChannelID":737,
           "URL":"/2026/08/vcb-bctc-hop-nhat-6-thang-dau-nam-2026-737-1481060.htm","Head":""},
          {"ArticleID":9,"Title":"Cổ phiếu ngân hàng tháng 8/2026",
           "PublishTime":"/Date(1786640400000)/","ChannelID":757,
           "URL":"/2026/08/ngan-hang.htm","Head":"BCTC hợp nhất quý 2 vừa công bố"}
        ]
        """
        articles = parse_vietstock_filings(html, "VCB")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["kind"], "earnings_release")
        self.assertEqual(articles[0]["published_at"], "2026-08-14")
        self.assertEqual(articles[0]["symbols"], ["VCB"])
        self.assertIn("1481060", articles[0]["url"])

    def test_disclosure_kinds(self) -> None:
        self.assertEqual(
            classify_article("Đăng ký giao dịch bán cổ phiếu", "", "disclosure").kind,
            "insider_sell",
        )
        self.assertEqual(
            classify_article("Công bố báo cáo tài chính hợp nhất", "", "disclosure").effect,
            "clock",
        )
        self.assertEqual(
            classify_article(
                "Thông báo về việc hủy niêm yết trái phiếu quốc tế",
                "",
                "disclosure",
            ).kind,
            "other",
        )
        self.assertEqual(
            classify_article("Chia cổ tức bằng cổ phiếu tỷ lệ 100:100", "", "disclosure").kind,
            "bonus_shares",
        )
        self.assertEqual(
            classify_article("Chào bán riêng lẻ cho nhà đầu tư", "", "disclosure").kind,
            "dilution",
        )
        self.assertEqual(
            classify_article("Ý kiến kiểm toán ngoại trừ", "", "company_news").effect,
            "block",
        )

    def test_pass_then_wait_for_breakout(self) -> None:
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [_earnings()],
            _regime_open(),
            _pattern(False),
            require_clock=True,
        )
        self.assertEqual(verdict.fa_label, "Đạt")
        self.assertEqual(verdict.status, "Theo dõi")

    def test_ready_when_pattern_breaks(self) -> None:
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [_earnings(), {**_earnings("2026-09-01"), "kind": "insider_buy", "title": "Đăng ký mua"}],
            _regime_open(),
            _pattern(True),
            require_clock=True,
        )
        self.assertEqual(verdict.status, "Được vào")
        self.assertEqual(verdict.priority, 1)

    def test_missing_filing_blocks_entry(self) -> None:
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [],
            _regime_open(),
            _pattern(True),
            require_clock=True,
        )
        self.assertEqual(verdict.status, "Chưa chấm")

    def test_insider_sell_waits(self) -> None:
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [_earnings(), {"published_at": "2026-09-20", "symbols": ["FPT"], "kind": "insider_sell", "title": "Đăng ký bán"}],
            _regime_open(),
            _pattern(True),
            require_clock=True,
        )
        self.assertEqual(verdict.status, "Chờ")

    def test_regime_lock_overrides_a_ready_name(self) -> None:
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [_earnings()],
            Regime(False, "VN-Index dưới MA200"),
            _pattern(True),
            require_clock=True,
        )
        self.assertEqual(verdict.status, "Khóa")

    def test_operating_profit_decline_fails(self) -> None:
        scored = score_fundamentals("FPT", _corporate_points(OPERATING_PROFIT_QR_GRYOY=-0.05, NET_PROFIT_QR_GRYOY=0.2))
        self.assertEqual(scored.label, "Không đạt")

    def test_dilution_reduces_per_share_profit(self) -> None:
        points = _corporate_points(NET_PROFIT_QR_GRYOY=0.05)
        points["OUTSTANDING_SHARES"] = [
            ("2025-06-30", 100),
            ("2025-09-30", 100),
            ("2025-12-31", 100),
            ("2026-03-31", 100),
            ("2026-06-30", 120),
        ]
        scored = score_fundamentals(
            "FPT",
            points
            | {
                "OWNERS_EQUITY_AQ": [("2025-06-30", 100.0), ("2026-06-30", 118.0)],
            },
        )
        self.assertEqual(scored.label, "Không đạt")

    def test_bonus_share_issue_is_not_dilution(self) -> None:
        points = _corporate_points(NET_PROFIT_QR_GRYOY=0.05)
        points["OUTSTANDING_SHARES"] = [
            ("2025-06-30", 100),
            ("2025-09-30", 100),
            ("2025-12-31", 100),
            ("2026-03-31", 100),
            ("2026-06-30", 200),
        ]
        points["OWNERS_EQUITY_AQ"] = [("2025-06-30", 500.0), ("2026-06-30", 520.0)]
        scored = score_fundamentals("FPT", points)
        self.assertEqual(scored.label, "Đạt")

    def test_unclassified_share_jump_stays_unstamped(self) -> None:
        points = _corporate_points()
        points["OUTSTANDING_SHARES"] = [
            ("2025-06-30", 100),
            ("2025-09-30", 100),
            ("2025-12-31", 100),
            ("2026-03-31", 100),
            ("2026-06-30", 150),
        ]
        scored = score_fundamentals("FPT", points)
        self.assertEqual(scored.label, "Chưa đủ số")
        self.assertIn("chưa rõ", scored.reason)

    def test_raw_split_gap_stops_scoring(self) -> None:
        bars = [
            {"trade_date": "2026-01-01", "close": 100.0},
            {"trade_date": "2026-01-02", "close": 50.0},
        ]
        pattern = assess_pattern(bars, bars)
        self.assertTrue(pattern.unadjusted)
        verdict = compose(
            "FPT",
            date(2026, 10, 10),
            _corporate_points(),
            [_earnings()],
            _regime_open(),
            pattern,
            require_clock=True,
        )
        self.assertEqual(verdict.status, "Chưa chấm")
        self.assertIn("chia tách", verdict.summary)

    def test_hnx_limit_move_is_not_a_split(self) -> None:
        bars = [
            {"trade_date": "2026-01-01", "close": 100.0},
            {"trade_date": "2026-01-02", "close": 110.0},
        ]
        hose = assess_pattern(bars, bars, "HOSE")
        hnx = assess_pattern(bars, bars, "HNX")
        self.assertTrue(hose.unadjusted)
        self.assertFalse(hnx.unadjusted)

    def test_bank_npl_fails(self) -> None:
        report = "2026-06-30"
        points = {
            "NET_PROFIT_QR": [(report, 10.0)],
            "NET_PROFIT_QR_GRYOY": [(report, 0.05)],
            "BAD_LOANS_RATIO_AQ": [(report, 0.05)],
            "PROVISION_BAD_LOANS_AQ": [(report, 1.2)],
            "OWNERS_EQUITY_AQ": [(report, 100.0)],
        }
        scored = score_fundamentals("VCB", points)
        self.assertEqual(scored.label, "Không đạt")

    def test_securities_house_has_no_corporate_gate(self) -> None:
        scored = score_fundamentals("SSI", _corporate_points())
        self.assertEqual(scored.label, "Chưa đủ số")

    def test_base_breakout(self) -> None:
        start = date(2026, 1, 1)
        stock = []
        index = []
        for i in range(80):
            day = (start + timedelta(days=i)).isoformat()
            close = 100 + i * 0.4
            spread = 4 if 59 <= i <= 68 else 0.2
            volume = 1000 if 59 <= i <= 68 else 100
            if i == 79:
                close = 140
                spread = 1
                volume = 2000
            stock.append(
                {
                    "trade_date": day,
                    "open": close,
                    "high": close + spread,
                    "low": close - spread,
                    "close": close,
                    "volume": volume,
                }
            )
            index.append(
                {
                    "trade_date": day,
                    "open": 100 + i * 0.05,
                    "high": 101 + i * 0.05,
                    "low": 99 + i * 0.05,
                    "close": 100 + i * 0.05,
                    "volume": 1,
                }
            )
        pattern = assess_pattern(stock, index)
        self.assertTrue(pattern.ready)
        self.assertGreater(pattern.rs or 0, 0)

    def test_relative_strength_reads_the_index_on_the_stock_dates(self) -> None:
        # A name that halted for ten sessions carries fewer bars than the index, so
        # counting back 61 positions lands on different dates for the two windows.
        start = date(2026, 1, 1)
        index = []
        stock = []
        for i in range(80):
            day = (start + timedelta(days=i)).isoformat()
            index.append(
                {
                    "trade_date": day,
                    "open": 1000.0 + i,
                    "high": 1000.0 + i,
                    "low": 1000.0 + i,
                    "close": 1000.0 + i,
                    "volume": 1,
                }
            )
            if 30 <= i <= 39:
                continue
            close = 102.0 if i == 79 else 100.0
            stock.append(
                {
                    "trade_date": day,
                    "open": close,
                    "high": close + 0.5,
                    "low": close - 0.5,
                    "close": close,
                    "volume": 1000,
                }
            )
        pattern = assess_pattern(stock, index)
        # The stock window starts at its 61st bar (d9), so the index leg is read there —
        # not at the index's own 61st bar, which sits ten sessions later at d19.
        self.assertEqual(stock[-61]["trade_date"], index[9]["trade_date"])
        self.assertAlmostEqual(
            pattern.rs or 0, (102.0 / 100.0 - 1) - (1079.0 / 1009.0 - 1), places=9
        )
        self.assertNotAlmostEqual(
            pattern.rs or 0, (102.0 / 100.0 - 1) - (1079.0 / 1019.0 - 1), places=9
        )

    def test_regime_needs_two_hundred_sessions(self) -> None:
        bars = [
            {"trade_date": f"2020-01-{(i % 28) + 1:02d}", "close": 100 + i}
            for i in range(199)
        ]
        self.assertIsNone(market_regime(bars).open)
        bars.append({"trade_date": "2024-01-01", "close": 400})
        self.assertTrue(market_regime(bars).open)


if __name__ == "__main__":
    unittest.main()
