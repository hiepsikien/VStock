from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.pattern import (
    Pattern,
    atr,
    failed_breakout,
    ma_now,
    pattern_score,
    recognise_patterns,
    zigzag_pivots,
)


def interp(waypoints: list[tuple[int, float]], length: int) -> list[float]:
    values = [0.0] * length
    for (start_index, start_value), (end_index, end_value) in zip(waypoints, waypoints[1:]):
        for index in range(start_index, end_index + 1):
            span = end_index - start_index
            step = (index - start_index) / span if span > 0 else 0
            values[index] = start_value + (end_value - start_value) * step
    return values


def bars(prices: list[float], volumes: list[float] | None = None, spread: float = 0.004) -> list[dict]:
    start = date(2026, 1, 1)
    rows = []
    for index, close in enumerate(prices):
        volume = volumes[index] if volumes is not None else 100.0
        rows.append(
            {
                "trade_date": (start + timedelta(days=index)).isoformat(),
                "open": close,
                "high": close * (1 + spread),
                "low": close * (1 - spread),
                "close": close,
                "volume": volume,
            }
        )
    return rows


WARM = [(0, 100.0), (25, 100.0)]


class StructureTest(unittest.TestCase):
    def test_zigzag_marks_swing_highs_and_lows(self) -> None:
        prices = interp(WARM + [(25, 100), (30, 112), (40, 90), (50, 104), (56, 99)], 57)
        pivots = zigzag_pivots(bars(prices))
        self.assertEqual([pivot.kind for pivot in pivots], ["H", "L", "H"])
        self.assertAlmostEqual(pivots[1].price, 89.6, places=0)

    def test_short_series_has_no_pivots(self) -> None:
        self.assertEqual(zigzag_pivots(bars([100.0] * 10)), [])

    def test_double_bottom_is_named(self) -> None:
        prices = interp(
            WARM + [(25, 100), (30, 112), (40, 90), (50, 104), (60, 90.5), (70, 104), (80, 114)],
            81,
        )
        series = bars(prices)
        names, notes = recognise_patterns(series, zigzag_pivots(series), atr(series))
        self.assertIn("Đáy đôi", names)
        self.assertIn("đã vượt", notes[0])

    def test_vcp_needs_three_contracting_pullbacks(self) -> None:
        prices = interp(
            WARM
            + [(25, 100), (33, 112), (41, 100), (49, 111), (57, 104), (65, 110), (73, 106.5), (81, 113)],
            82,
        )
        series = bars(prices)
        names, _notes = recognise_patterns(series, zigzag_pivots(series), atr(series))
        self.assertIn("VCP", names)

    def test_abcd_matches_fibonacci_ratios(self) -> None:
        prices = interp(
            WARM + [(25, 90), (35, 110), (45, 100), (57, 115), (63, 109)],
            64,
        )
        series = bars(prices)
        names, notes = recognise_patterns(series, zigzag_pivots(series), atr(series))
        self.assertIn("ABCD", names)
        self.assertIn("duỗi", notes[0])

    def test_flag_needs_a_pole_and_dry_consolidation(self) -> None:
        prices = interp(
            [(0, 100), (10, 95), (20, 102), (30, 100), (38, 125), (44, 122), (50, 124), (56, 123)],
            57,
        )
        volumes = [300.0 if 30 <= index <= 38 else 100.0 for index in range(len(prices))]
        series = bars(prices, volumes)
        names, _notes = recognise_patterns(series, zigzag_pivots(series), atr(series))
        self.assertIn("Cờ", names)

    def test_no_pattern_in_a_plain_downtrend(self) -> None:
        prices = interp([(0, 120), (20, 95), (40, 100), (60, 88)], 61)
        series = bars(prices)
        names, _notes = recognise_patterns(series, zigzag_pivots(series), atr(series))
        self.assertEqual(names, ())

    def test_score_rewards_contraction_breakout_and_names(self) -> None:
        bare = pattern_score(
            contraction=True, dry=True, breakout=True, higher_low=False, names=()
        )
        with_names = pattern_score(
            contraction=True, dry=True, breakout=True, higher_low=True, names=("VCP", "Cờ")
        )
        self.assertEqual(bare, 65)
        self.assertEqual(with_names, 100)
        self.assertEqual(
            pattern_score(contraction=False, dry=False, breakout=False, higher_low=False, names=()),
            0,
        )

    def test_indicators_use_the_tail(self) -> None:
        series = bars([100.0] * 20 + [110.0] * 5)
        self.assertAlmostEqual(ma_now(series, 5) or 0, 110.0, places=4)
        self.assertIsNotNone(atr(series))
        self.assertIsNone(ma_now(series, 40))

    def test_pattern_keeps_old_positional_arguments(self) -> None:
        pattern = Pattern(True, "Phá nền", 0.08, 90)
        self.assertEqual(pattern.stop, 90)
        self.assertEqual(pattern.patterns, ())
        self.assertEqual(pattern.score, 0)


class FailedBreakoutTest(unittest.TestCase):
    """A base broken through and lost again, and what a later breakout does to that verdict."""

    def test_a_breakout_today_puts_the_earlier_failure_behind_the_name(self) -> None:
        self.assertIsNone(failed_breakout(_failed_breakout_bars()))

    def test_a_failure_within_the_window_is_reported(self) -> None:
        # The same series without today's session: the breakout of three sessions ago still
        # counts as failed, so the check did not simply stop looking.
        self.assertIn("phá nền thất bại", failed_breakout(_failed_breakout_bars()[:27]) or "")

    def test_a_close_exactly_on_the_level_holds(self) -> None:
        rows = _failed_breakout_bars()[:27]
        rows[26]["close"] = 100.5
        self.assertIsNone(failed_breakout(rows))


def _failed_breakout_bars() -> list[dict]:
    """25 flat sessions, a breakout, a close back under it, then a fresh breakout today.

    The breakout at 25 clears the 100.5 ceiling of the flat base; 26 closes at 99, back under
    it; 27 closes at 105, through the 103 ceiling of the two sessions before it. So the failure
    of 26 is three sessions old on the day of the new breakout.
    """
    start = date(2026, 1, 1)
    closes = [100.0] * 25 + [102.0, 99.0, 105.0]
    highs = [100.5] * 25 + [103.0, 101.0, 106.0]
    return [
        {
            "trade_date": (start + timedelta(days=index)).isoformat(),
            "open": close,
            "high": high,
            "low": close - 0.5,
            "close": close,
            "volume": 100.0,
        }
        for index, (close, high) in enumerate(zip(closes, highs))
    ]


if __name__ == "__main__":
    unittest.main()
