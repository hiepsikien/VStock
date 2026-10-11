"""Rổ theo từng giai đoạn: cửa sổ niêm yết, sàng thanh khoản, nhãn ICB và nến đã lưu.

Ba nhóm dữ liệu của một rổ đúng điểm — bảng niêm yết, nến đã điều chỉnh của mã hủy niêm yết,
và bảng phân loại ICB — đều được kiểm ở đây, vì rổ sai thì mọi con số của báo cáo sai theo.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import date
from typing import Any

from app import db, ingest
from app.industries import (
    icb_industry,
    industry_labels,
    industry_of,
    industry_rows,
    load_industry_map,
    set_industry_map,
)
from app.pit_universe import (
    basket_members,
    baskets_from_bars,
    listed_from,
    member_of,
    ranked_on,
    tapes,
    trade_member_of,
    trade_members,
)

# Số cổ phiếu quý 2 công bố giữa tháng 8, nên biết được từ mọi phiên chốt rổ trong đề bài.
SHARES_DAY = "2024-06-30"


# Giá trong kho tính bằng nghìn đồng và khối lượng bằng cổ phiếu, nên `close` ở đây là 10.0
# cho một mã giá 10.000 đồng — đúng đơn vị mà `pit_universe` dùng để đo thanh khoản.
def _bars(start: str, count: int, close: float = 10.0, volume: float = 1_000_000.0) -> list[dict]:
    day = date.fromisoformat(start)
    rows = []
    for step in range(count):
        rows.append(
            {
                "trade_date": day.isoformat(),
                "open": close,
                "high": close,
                "low": close,
                "close": close * (1 + step / 10_000),
                "volume": volume,
            }
        )
        day = date.fromordinal(day.toordinal() + 1)
    return rows


def _shares(count: float) -> dict:
    return {"OUTSTANDING_SHARES": [(SHARES_DAY, count)]}


class ListingWindowTest(unittest.TestCase):
    def test_a_delisted_symbol_leaves_on_the_session_after_its_last_day(self) -> None:
        listed = listed_from(
            {
                "OLD": {"listed_date": "2015-01-05", "delisted_date": "2020-06-30"},
                "NEW": {"listed_date": "2023-03-15", "delisted_date": None},
            }
        )
        self.assertTrue(listed("OLD", "2019-12-31"))
        self.assertTrue(listed("OLD", "2020-06-30"))
        self.assertFalse(listed("OLD", "2020-07-01"))
        self.assertFalse(listed("NEW", "2023-03-14"))
        self.assertTrue(listed("NEW", "2023-03-15"))
        self.assertTrue(listed("NEW", "2026-01-05"))

    def test_a_symbol_the_source_never_confirmed_stays_out(self) -> None:
        listed = listed_from({"BARE": {"listed_date": None, "delisted_date": None}})
        self.assertFalse(listed("GONE", "2024-01-02"))
        # Dòng cũ của nguồn không có ngày niêm yết: coi như niêm yết từ trước, không loại.
        self.assertTrue(listed("BARE", "1999-01-04"))


class RankedOnTest(unittest.TestCase):
    def test_rank_drops_thin_names_shareless_names_and_short_history(self) -> None:
        day = "2025-01-04"
        bars = {
            "BIG": _bars("2024-12-16", 20, close=10.0, volume=2_000_000.0),
            "MID": _bars("2024-12-16", 20, close=5.0, volume=2_000_000.0),
            "THIN": _bars("2024-12-16", 20, close=10.0, volume=100_000.0),
            "NOCAP": _bars("2024-12-16", 20, close=10.0, volume=2_000_000.0),
            "SHORT": _bars("2025-01-01", 4, close=10.0, volume=2_000_000.0),
        }
        ratios = {
            "BIG": _shares(5_000_000.0),
            "MID": _shares(5_000_000.0),
            "THIN": _shares(5_000_000.0),
            "SHORT": _shares(5_000_000.0),
            # NOCAP cố tình thiếu số cổ phiếu, SHORT chưa đủ năm phiên giao dịch.
        }
        ranked = ranked_on(day, tapes(bars), ratios, list(bars))
        self.assertEqual(ranked, ["BIG", "MID"])
        # Vốn hóa của THIN lớn hơn MID, nên chỉ ngưỡng thanh khoản mới loại được nó.
        thin_only = ranked_on(
            day, tapes(bars), ratios, ["THIN"], min_turnover=1_000_000_000.0
        )
        self.assertEqual(thin_only, ["THIN"])

    def test_turnover_is_measured_in_dong_not_in_thousand_dong(self) -> None:
        day = "2025-01-04"
        bars = {"ONLY": _bars("2024-12-16", 20, close=10.0, volume=100_000.0)}
        ratios = {"ONLY": _shares(5_000_000.0)}
        # 10 nghìn đồng × 100.000 cổ phiếu = 1 tỷ đồng một phiên: vừa đủ khi ngưỡng là 1 tỷ,
        # còn ngưỡng mặc định 3 tỷ thì loại.
        self.assertEqual(
            ranked_on(day, tapes(bars), ratios, ["ONLY"], min_turnover=1_000_000_000.0), ["ONLY"]
        )
        self.assertEqual(ranked_on(day, tapes(bars), ratios, ["ONLY"]), [])


class RawTapeTest(unittest.TestCase):
    """Cạnh thật của nguồn: vốn hóa và thanh khoản của rổ không đo bằng giá đã điều chỉnh."""

    def test_capitalisation_is_measured_on_the_real_close(self) -> None:
        day = "2025-01-04"
        adjusted = _bars("2024-12-16", 20, close=10.0, volume=2_000_000.0)
        real = [dict(bar, raw_close=50.0) for bar in adjusted]
        ratios = {"REAL": _shares(5_000_000.0), "SAME": _shares(5_000_000.0)}
        # Hai mã cùng giá đã điều chỉnh và cùng số cổ phiếu, nhưng REAL có giá thật gấp năm lần,
        # nên vốn hóa của nó lớn hơn và đứng trước.
        self.assertEqual(
            ranked_on(day, tapes({"REAL": real, "SAME": adjusted}), ratios, ["REAL", "SAME"]),
            ["REAL", "SAME"],
        )
        # Thiếu giá thật thì hai mã bằng nhau, và thứ tự chỉ còn theo mã: đúng hành vi cũ.
        self.assertEqual(
            ranked_on(
                day,
                tapes({"REAL": adjusted, "SAME": adjusted}),
                ratios,
                ["REAL", "SAME"],
            ),
            ["SAME", "REAL"],
        )

    def test_the_traded_value_from_the_source_beats_the_adjusted_product(self) -> None:
        day = "2025-01-04"
        # Giá đã điều chỉnh 10 nghìn đồng × 2 triệu cổ phiếu = 20 tỷ một phiên, đủ qua ngưỡng;
        # nhưng giá trị khớp thật chỉ 0,1 tỷ, nên mã này không được vào rổ.
        bars = {
            "FAKE": [
                dict(bar, trade_value=100_000_000.0)
                for bar in _bars("2024-12-16", 20, close=10.0, volume=2_000_000.0)
            ]
        }
        ratios = {"FAKE": _shares(5_000_000.0)}
        self.assertEqual(ranked_on(day, tapes(bars), ratios, ["FAKE"], min_turnover=1_000_000_000.0), [])

    def test_a_session_without_trades_still_carries_its_real_close(self) -> None:
        day = "2025-01-04"
        bars = {
            "HALT": [
                dict(bar, raw_close=50.0, trade_value=0.0)
                for bar in _bars("2024-12-16", 20, close=10.0, volume=100_000.0)
            ]
        }
        ratios = {"HALT": _shares(5_000_000.0)}
        tape = tapes(bars)["HALT"]
        # Phiên không khớp lệnh vẫn có giá thật, nên vốn hóa không quay về giá đã điều chỉnh.
        self.assertEqual(tape.raw_close_on(day), 50.0)
        # Còn thanh khoản của phiên đó đo bằng công thức cũ: 10 nghìn × 100.000 cổ phiếu = 1 tỷ.
        self.assertAlmostEqual(tape.median_turnover(day, 20), 1_000_000_000.0, delta=1_000_000.0)
        self.assertEqual(
            ranked_on(day, tapes(bars), ratios, ["HALT"], min_turnover=1_000_000_000.0), ["HALT"]
        )

    def test_bars_without_the_real_side_fall_back_to_the_adjusted_price(self) -> None:
        day = "2025-01-04"
        # 0 là giá trị trống chứ không phải một mức giá hay một phiên không khớp lệnh, nên mã
        # quay về công thức cũ: 10 nghìn đồng × 100.000 cổ phiếu = 1 tỷ một phiên.
        bars = {
            "OLD": [
                dict(bar, raw_close=0.0, trade_value=0.0)
                for bar in _bars("2024-12-16", 20, close=10.0, volume=100_000.0)
            ]
        }
        ratios = {"OLD": _shares(5_000_000.0)}
        self.assertEqual(
            ranked_on(day, tapes(bars), ratios, ["OLD"], min_turnover=1_000_000_000.0), ["OLD"]
        )


class YearlyBasketsTest(unittest.TestCase):
    def _baskets(self, **options: Any) -> dict:
        bars = {
            "AAA": _bars("2024-11-01", 70, close=10.0, volume=2_000_000.0),
            "BBB": _bars("2024-11-01", 70, close=8.0, volume=2_000_000.0),
            "CCC": _bars("2024-11-01", 70, close=4.0, volume=2_000_000.0),
            "DYING": _bars("2024-11-01", 70, close=20.0, volume=2_000_000.0),
        }
        ratios = {symbol: _shares(1_000_000.0) for symbol in bars}
        listings = {
            "AAA": {"listed_date": "2010-01-04", "delisted_date": None},
            "BBB": {"listed_date": "2010-01-04", "delisted_date": None},
            "CCC": {"listed_date": "2010-01-04", "delisted_date": None},
            "DYING": {"listed_date": "2010-01-04", "delisted_date": "2024-12-31"},
        }
        index_days = [bar["trade_date"] for bar in bars["AAA"]]
        chosen = {"limit": 3, "trade_limit": 2, "min_names": 2}
        chosen.update(options)
        return baskets_from_bars(index_days, bars, ratios, listings, **chosen)

    def test_the_trade_basket_is_the_top_of_the_year_basket(self) -> None:
        baskets = self._baskets()
        self.assertIn(2024, baskets)
        self.assertIn(2025, baskets)
        self.assertEqual(basket_members(baskets, 2024)[:2], ["DYING", "AAA"])
        self.assertEqual(trade_members(baskets, 2024), ["DYING", "AAA"])
        self.assertEqual(baskets[2025].day, "2025-01-01")
        self.assertEqual(basket_members(baskets, 2025), ["AAA", "BBB", "CCC"])
        self.assertEqual(trade_members(baskets, 2025), ["AAA", "BBB"])

    def test_membership_is_read_on_the_day_being_measured(self) -> None:
        baskets = self._baskets()
        self.assertTrue(member_of(baskets, "DYING", "2024-12-30"))
        self.assertTrue(trade_member_of(baskets, "DYING", "2024-12-30"))
        # Hủy niêm yết ngày cuối 2024 nên mã đó không còn trong rổ nào của 2025.
        self.assertFalse(member_of(baskets, "DYING", "2025-01-05"))
        self.assertTrue(member_of(baskets, "CCC", "2025-01-05"))
        self.assertFalse(trade_member_of(baskets, "CCC", "2025-01-05"))
        self.assertEqual(basket_members(baskets, 2019), [])
        self.assertFalse(member_of(baskets, "AAA", "2019-06-03"))

    def test_a_year_with_too_few_ranked_names_is_left_open(self) -> None:
        self.assertEqual(self._baskets(min_names=10), {})


class IcbMapTest(unittest.TestCase):
    def test_level_three_wins_over_level_two_for_the_same_symbol(self) -> None:
        groups = [
            {"industryLevel": 2, "industryCode": "8300", "englishName": "Banks", "codeList": "AAA,bbb"},
            {"industryLevel": 2, "industryCode": "8600", "englishName": "Real Estate", "codeList": "FFF"},
            {
                "industryLevel": 3,
                "industryCode": "2770",
                "englishName": "Industrial Transportation",
                "codeList": "FFF, CCC",
            },
        ]
        rows = {row[0]: row for row in industry_rows(groups)}
        self.assertEqual(set(rows), {"AAA", "BBB", "CCC", "FFF"})
        self.assertEqual(rows["AAA"][2], "8300")
        self.assertEqual(rows["AAA"][3], "Banks")
        self.assertEqual(rows["AAA"][4], "bank")
        self.assertEqual(rows["FFF"][1], 3)
        self.assertEqual(rows["FFF"][4], "transport")

    def test_a_group_without_a_gate_is_stored_with_an_empty_label(self) -> None:
        rows = {
            row[0]: row
            for row in industry_rows(
                [{"industryLevel": 3, "industryCode": "4530", "englishName": "Health", "codeList": "DHG"}]
            )
        }
        self.assertEqual(rows["DHG"][4], "")

    def test_a_group_without_a_label_never_erases_a_label_that_is_already_there(self) -> None:
        # Cấp 3 không có nhãn đọc sau cấp 2 và sau cấp 3 có nhãn, nên nếu nó ghi đè vô điều
        # kiện thì mã mất nhãn đúng vào lúc nguồn thêm một nhóm cấp 3 mới.
        groups = [
            {"industryLevel": 2, "industryCode": "8300", "englishName": "Banks", "codeList": "AAA,CCC"},
            {
                "industryLevel": 3,
                "industryCode": "2770",
                "englishName": "Industrial Transportation",
                "codeList": "CCC",
            },
            {"industryLevel": 3, "industryCode": "4530", "englishName": "Health", "codeList": "AAA,CCC"},
        ]
        rows = {row[0]: row for row in industry_rows(groups)}
        self.assertEqual((rows["AAA"][1], rows["AAA"][2], rows["AAA"][4]), (2, "8300", "bank"))
        self.assertEqual((rows["CCC"][1], rows["CCC"][2], rows["CCC"][4]), (3, "2770", "transport"))

    def test_codes_are_padded_to_four_digits(self) -> None:
        self.assertEqual(icb_industry("580", 3), "power")
        self.assertEqual(icb_industry("500", 2), "energy")
        # 0580 chỉ có ở bảng cấp 3: đọc theo cấp 2 thì nhóm đó không phải một nhóm cấp 2.
        self.assertIsNone(icb_industry("580", 2))
        self.assertIsNone(icb_industry("", 3))
        self.assertIsNone(icb_industry("4530", 3))

    def test_curated_lists_beat_the_stored_icb_label(self) -> None:
        set_industry_map({"VCB": "materials", "ZZZ": "consumer"})
        try:
            self.assertEqual(industry_of("VCB"), "bank")
            self.assertEqual(industry_of("ZZZ"), "consumer")
            self.assertIsNone(industry_of("YYY"))
        finally:
            set_industry_map({})

    def test_an_empty_label_is_never_injected(self) -> None:
        set_industry_map({"YYY": "", "ZZZ": "tech"})
        try:
            self.assertIsNone(industry_of("YYY"))
            self.assertEqual(industry_of("ZZZ"), "tech")
        finally:
            set_industry_map({})

    def test_labels_come_back_as_a_copy_for_the_worker_processes(self) -> None:
        set_industry_map({"YYY": "", "ZZZ": "tech"})
        try:
            labels = industry_labels()
            self.assertEqual(labels, {"ZZZ": "tech"})
            labels["ZZZ"] = "materials"
            self.assertEqual(industry_of("ZZZ"), "tech")
        finally:
            set_industry_map({})
        self.assertEqual(industry_labels(), {})


class MarketRowTest(unittest.TestCase):
    def test_delisted_rows_without_adjusted_prices_are_skipped(self) -> None:
        rows = [
            {
                "date": "2020-06-29",
                "adOpen": 10.0,
                "adHigh": 11.0,
                "adLow": 9.0,
                "adClose": 10.5,
                "nmVolume": 100,
            },
            {
                "date": "2020-06-30T00:00:00",
                "adOpen": 10.5,
                "adHigh": 10.6,
                "adLow": 10.0,
                "adClose": 10.2,
                "nmVolume": 50,
            },
            {"date": "2020-07-01", "adOpen": None, "adHigh": None, "adLow": None, "adClose": None},
            {"date": "", "adOpen": 1.0, "adHigh": 1.0, "adLow": 1.0, "adClose": 1.0},
            {
                "date": "2020-06-29",
                "adOpen": 10.0,
                "adHigh": 11.0,
                "adLow": 9.0,
                "adClose": 10.4,
                "nmVolume": 900,
            },
        ]
        bars = ingest._bars_from_price_rows(rows)
        self.assertEqual([bar["trade_date"] for bar in bars], ["2020-06-29", "2020-06-30"])
        self.assertEqual(bars[0]["close"], 10.4)  # cùng phiên thì dòng đọc sau thắng
        self.assertEqual(bars[1]["volume"], 50.0)

    def test_real_close_and_traded_value_are_read_from_the_same_rows(self) -> None:
        rows = [
            {"date": "2014-01-02", "close": 47.4, "adClose": 4.934, "nmValue": 9_865_116_000.0},
            # Phiên không khớp lệnh vẫn có giá thật, và giá trị khớp bằng 0.
            {"date": "2014-01-03", "close": 46.0, "adClose": 4.79, "nmValue": 0},
            # Nguồn không có giá thì không ghi gì cho phiên đó.
            {"date": "2014-01-06", "close": None, "adClose": 4.7, "nmValue": 1_000.0},
        ]
        points = ingest._raw_from_price_rows(rows)
        self.assertEqual(
            points, [("2014-01-02", 47.4, 9_865_116_000.0), ("2014-01-03", 46.0, 0.0)]
        )

    def test_a_stale_delisting_date_is_dropped_on_a_floor_change(self) -> None:
        rows = [
            {
                "code": "abc",
                "floor": "hose",
                "status": "DELISTED",
                "listedDate": "2005-01-04",
                "delistedDate": "2019-05-31",
            },
            {
                "code": "ABC",
                "floor": "HNX",
                "status": "LISTED",
                "listedDate": "2019-06-10",
                "delistedDate": "2019-05-31",
            },
            {"code": " pvs ", "floor": "hose", "status": "LISTED"},
            {"code": "", "floor": "hose", "status": "LISTED", "listedDate": "2020-01-01"},
        ]
        out = {row[0]: row for row in ingest.listing_rows(rows)}
        self.assertEqual(set(out), {"ABC", "PVS"})
        self.assertEqual(out["ABC"][1], "HNX")
        self.assertEqual(out["ABC"][3], "2019-06-10")
        self.assertIsNone(out["ABC"][4])
        self.assertIsNone(out["PVS"][3])

    def test_a_real_delisting_date_is_kept(self) -> None:
        rows = ingest.listing_rows(
            [
                {
                    "code": "OLD",
                    "floor": "HOSE",
                    "status": "DELISTED",
                    "listedDate": "2005-01-04",
                    "delistedDate": "2020-06-30",
                }
            ]
        )
        self.assertEqual(rows[0][3], "2005-01-04")
        self.assertEqual(rows[0][4], "2020-06-30")


class _FakeResponse:
    def __init__(self, data: list[dict]) -> None:
        self._data = data

    def json(self) -> dict:
        return {"data": self._data}

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    """Client giả trả từng trang theo số trang, và ghi lại query đã gọi."""

    def __init__(self, pages: list[list[dict]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> _FakeResponse:
        self.calls.append((url, dict(params or {})))
        page = int((params or {}).get("page") or 1)
        data = self.pages[page - 1] if page - 1 < len(self.pages) else []
        return _FakeResponse(data)


class VndirectPageTest(unittest.TestCase):
    def test_paging_stops_at_the_first_empty_page(self) -> None:
        client = _FakeClient([[{"code": "AAA"}], [{"code": "BBB"}], []])
        rows = asyncio.run(ingest._vndirect_pages(client, "u", "q", size=1000))
        self.assertEqual([row["code"] for row in rows], ["AAA", "BBB"])
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(client.calls[0][1]["size"], 1000)
        self.assertEqual(client.calls[2][1]["page"], 3)

    def test_listings_ask_only_for_stocks_on_the_chosen_floors(self) -> None:
        client = _FakeClient([[{"code": "AAA"}]])
        asyncio.run(ingest.fetch_listings(client, ("HOSE", "HNX")))
        self.assertEqual(client.calls[0][1]["q"], "type:STOCK~floor:in(HOSE,HNX)")
        self.assertEqual(client.calls[0][1]["sort"], "code:asc")

    def test_market_bars_page_by_symbol_from_a_start_date(self) -> None:
        client = _FakeClient(
            [
                [
                    {
                        "date": "2007-03-05",
                        "adOpen": 100.0,
                        "adHigh": 110.0,
                        "adLow": 95.0,
                        "adClose": 105.0,
                        "nmVolume": 12_000.0,
                    }
                ]
            ]
        )
        bars = asyncio.run(ingest.fetch_market_bars(client, "OLD", "2007-01-01"))
        self.assertEqual(client.calls[0][1]["q"], "code:OLD~date:gte:2007-01-01")
        self.assertEqual(bars[0]["trade_date"], "2007-03-05")
        self.assertEqual(bars[0]["volume"], 12_000.0)

    def test_raw_tape_asks_the_price_endpoint_for_the_real_side(self) -> None:
        client = _FakeClient(
            [
                [
                    {
                        "date": "2014-01-02",
                        "close": 47.4,
                        "adClose": 4.934,
                        "nmValue": 9_865_116_000.0,
                    }
                ]
            ]
        )
        points = asyncio.run(ingest.fetch_raw_tape(client, "FPT", "2014-01-01"))
        self.assertEqual(client.calls[0][0], ingest.VNDIRECT_PRICES)
        self.assertEqual(client.calls[0][1]["q"], "code:FPT~date:gte:2014-01-01")
        self.assertEqual(points, [("2014-01-02", 47.4, 9_865_116_000.0)])


class RawTapeStoreTest(unittest.TestCase):
    """Cạnh thật ghi vào nến đã có: chỉ hai cột phụ, không chèn phiên mới."""

    def test_the_real_side_is_written_beside_the_bars(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        os.environ["RESEARCH_DB_PATH"] = handle.name
        try:
            await db.init_db()
            await db.replace_bars("AAA", _bars("2024-01-02", 3, close=10.0, volume=1_000.0))
            matched, unmatched = await db.write_raw_tape(
                "AAA",
                [
                    ("2024-01-02", 50.0, 5_000_000_000.0),
                    ("2024-01-03", 51.0, 6_000_000_000.0),
                    ("2024-01-09", 52.0, 7_000_000_000.0),
                ],
            )
            # Phiên 2024-01-09 nguồn có mà kho không có nến, nên chỉ hai phiên được ghi.
            self.assertEqual((matched, unmatched), (2, 1))
            stored = await db.bars("AAA")
            self.assertEqual(len(stored), 3)
            self.assertEqual(stored[0]["raw_close"], 50.0)
            self.assertEqual(stored[0]["trade_value"], 5_000_000_000.0)
            self.assertEqual(stored[1]["raw_close"], 51.0)
            self.assertIsNone(stored[2]["raw_close"])
            # Chạy lại là ghi đè cùng giá trị, nên vẫn khớp đủ và không nhân đôi dòng nào.
            again = await db.write_raw_tape("AAA", [("2024-01-02", 50.0, 5_000_000_000.0)])
            self.assertEqual(again, (1, 0))
            self.assertEqual(len(await db.bars("AAA")), 3)
            # Danh sách việc đọc từ kho: mã có nến mà không nằm trong bảng niêm yết của nguồn
            # không phải việc của lần nạp giá thật, vì rổ không dựng từ nó.
            await db.replace_bars("BBB", _bars("2024-01-02", 1, close=10.0))
            self.assertEqual(await db.raw_tape_missing(), [])
            await db.replace_symbol_meta([("AAA", "HOSE", "listed", "2010-01-01", None)])
            # Phiên thiếu đầu tiên đi kèm, để lần nạp sau chỉ hỏi từ đó chứ không hỏi lại cả
            # lịch sử của mã.
            self.assertEqual(await db.raw_tape_missing(), [("AAA", 3, 1, "2024-01-04")])
            # Lấp nốt phiên còn thiếu thì mã rời khỏi danh sách việc, không cần dấu nào.
            await db.write_raw_tape("AAA", [("2024-01-04", 52.0, 7_000_000_000.0)])
            self.assertEqual(await db.raw_tape_missing(), [])
        finally:
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous


class IndustryMapLoadTest(unittest.TestCase):
    """Tiến trình chấm verdict tự gắn bảng ngành đã lưu, không chỉ tiến trình web."""

    def test_the_stored_table_is_loaded_into_the_process(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        os.environ["RESEARCH_DB_PATH"] = handle.name
        try:
            await db.init_db()
            await db.replace_symbol_industry(
                [("ZZZ", 3, "2770", "Industrial Transportation", "transport")]
            )
            set_industry_map({})
            self.assertIsNone(industry_of("ZZZ"))
            await load_industry_map()
            self.assertEqual(industry_of("ZZZ"), "transport")
        finally:
            set_industry_map({})
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous


class SymbolStoreTest(unittest.TestCase):
    def test_the_stored_listings_and_labels_feed_the_baskets(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await db.close_db()
        previous = os.environ.get("RESEARCH_DB_PATH")
        handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        handle.close()
        os.environ["RESEARCH_DB_PATH"] = handle.name
        try:
            await db.init_db()
            await db.replace_symbol_meta(
                [
                    ("OLD", "HOSE", "DELISTED", "2005-01-04", "2020-06-30"),
                    ("NEW", "HOSE", "LISTED", "2024-01-02", None),
                ]
            )
            await db.replace_symbol_industry(
                [
                    ("OLD", 2, "8300", "Banks", "bank"),
                    ("NEW", 3, "2770", "Industrial Transportation", "transport"),
                ]
            )
            listed = listed_from(await db.symbol_meta())
            self.assertTrue(listed("OLD", "2020-06-30"))
            self.assertFalse(listed("OLD", "2020-07-01"))
            self.assertFalse(listed("NEW", "2023-12-29"))
            self.assertTrue(listed("NEW", "2024-01-02"))
            self.assertFalse(listed("MISSING", "2020-01-01"))
            stored = await db.symbol_industry()
            set_industry_map({symbol: row["industry"] for symbol, row in stored.items()})
            self.assertEqual(industry_of("OLD"), "bank")
            self.assertEqual(industry_of("NEW"), "transport")
            # Ghi lại bảng ngành là cập nhật tại chỗ, mã cũ vẫn giữ nhãn để dựng rổ quá khứ.
            await db.replace_symbol_industry([("NEW", 2, "2700", "Industrial", "industrial")])
            refreshed = await db.symbol_industry()
            self.assertEqual(refreshed["NEW"]["industry"], "industrial")
            self.assertEqual(refreshed["OLD"]["industry"], "bank")
        finally:
            set_industry_map({})
            await db.close_db()
            if previous is None:
                os.environ.pop("RESEARCH_DB_PATH", None)
            else:
                os.environ["RESEARCH_DB_PATH"] = previous
            os.unlink(handle.name)


if __name__ == "__main__":
    unittest.main()
