from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.chart import (
    CHART_HEIGHT,
    CHART_PAD,
    VOLUME_GAP,
    VOLUME_HEIGHT,
    VOLUME_TICK_COUNT,
    build_chart,
    _volume_text,
)


def bars(rows: list[tuple[float, float, float]]) -> list[dict]:
    """(open, close, volume) per session, a thin wick around the body."""
    start = date(2026, 1, 1)
    out = []
    for index, (open_price, close_price, volume) in enumerate(rows):
        high = max(open_price, close_price) * 1.005
        low = min(open_price, close_price) * 0.995
        out.append(
            {
                "trade_date": (start + timedelta(days=index)).isoformat(),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close_price,
                "volume": volume,
            }
        )
    return out


def rising(count: int, volume: float = 1000.0) -> list[tuple[float, float, float]]:
    return [(100.0 + index, 100.0 + index + 1, volume) for index in range(count)]


class VolumePaneTest(unittest.TestCase):
    def test_volume_text_shortens_to_the_label_column(self) -> None:
        # Đổi đơn vị đúng ngưỡng, để không nhãn nào phải nới khe chữ bên phải.
        self.assertEqual(_volume_text(2_400_000), "2.4tr")
        self.assertEqual(_volume_text(999_999), "1.0tr")
        self.assertEqual(_volume_text(18_500), "18.5k")
        self.assertEqual(_volume_text(9_950), "9,950")

    def test_every_session_gets_a_column_under_its_candle(self) -> None:
        # Two heavy sessions and one red candle, so both colours and the tallest bar are covered.
        rows = rising(30)
        rows[7] = (108.0, 107.0, 5000.0)
        rows[20] = (121.0, 122.0, 9000.0)
        chart = build_chart(bars(rows), None)
        self.assertIsNotNone(chart)
        volume = chart["volume"]
        bars_in_pane = volume["bars"]
        self.assertEqual(len(bars_in_pane), len(chart["candles"]))
        self.assertEqual(len(bars_in_pane), 30)
        for candle, column in zip(chart["candles"], bars_in_pane):
            self.assertEqual(column["x"], candle["x"])
            self.assertEqual(column["width"], candle["width"])
            self.assertEqual(column["up"], candle["up"])
            self.assertGreaterEqual(column["y"], volume["top"])
            self.assertLessEqual(column["y"] + column["height"], volume["floor"])
        self.assertFalse(bars_in_pane[7]["up"])
        # The heaviest session sets the scale, so it reaches the top of the pane.
        self.assertEqual(bars_in_pane[20]["y"], volume["top"])
        self.assertEqual(bars_in_pane[20]["height"], VOLUME_HEIGHT)
        self.assertEqual(bars_in_pane[0]["height"], round(VOLUME_HEIGHT * 1000 / 9000, 2))

    def test_a_session_with_no_volume_keeps_its_slot(self) -> None:
        rows = rising(10)
        rows[4] = (104.0, 104.0, 0.0)
        chart = build_chart(bars(rows), None)
        columns = chart["volume"]["bars"]
        self.assertEqual(columns[4]["height"], 0.0)
        self.assertEqual(columns[4]["x"], chart["candles"][4]["x"])

    def test_axis_labels_cover_the_pane(self) -> None:
        chart = build_chart(bars(rising(30, volume=2_400_000)), None)
        volume = chart["volume"]
        self.assertEqual(volume["label"], "KL")
        self.assertEqual(volume["max_text"], "2.4tr")
        self.assertEqual(len(volume["ticks"]), VOLUME_TICK_COUNT)
        self.assertEqual(volume["ticks"][-1]["y"], volume["top"])
        self.assertEqual(volume["ticks"][-1]["text"], "2.4tr")
        self.assertEqual(volume["ticks"][0]["y"], round(volume["top"] + VOLUME_HEIGHT / 2, 2))
        self.assertEqual(volume["ticks"][0]["text"], "1.2tr")

    def test_volume_never_reaches_into_the_price_plot(self) -> None:
        chart = build_chart(bars(rising(30)), None)
        volume = chart["volume"]
        self.assertEqual(volume["top"], CHART_HEIGHT - CHART_PAD["bottom"] - VOLUME_HEIGHT)
        self.assertEqual(volume["floor"], CHART_HEIGHT - CHART_PAD["bottom"])
        # Nhãn giá xếp từ thấp lên, nên tick cuối là mức cao nhất của khung giá.
        self.assertEqual(chart["ticks"][0]["y"], volume["top"] - VOLUME_GAP)
        self.assertEqual(chart["ticks"][-1]["y"], CHART_PAD["top"])
        self.assertLessEqual(max(candle["low_y"] for candle in chart["candles"]), volume["top"])

    def test_a_series_without_volume_drops_the_pane(self) -> None:
        chart = build_chart(bars(rising(30, volume=0.0)), None)
        self.assertIsNone(chart["volume"])
        # With no pane to draw, the price plot runs down to the bottom pad instead of leaving a gap.
        self.assertEqual(chart["ticks"][0]["y"], CHART_HEIGHT - CHART_PAD["bottom"])
        self.assertEqual(chart["ticks"][-1]["y"], CHART_PAD["top"])

    def test_candle_tooltip_carries_the_session_volume(self) -> None:
        chart = build_chart(bars(rising(3, volume=2_400_000)), None)
        self.assertIn("· V 2.4tr", chart["candles"][0]["title"])
        self.assertTrue(chart["volume"]["bars"][0]["title"].endswith("· KL 2.4tr"))


if __name__ == "__main__":
    unittest.main()
