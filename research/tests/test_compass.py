"""Cửa Compass: biên gộp, PIT, ngưỡng dầu và spread. Không gọi mạng."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from app.compass import (
    GROSS_PROFIT_ITEM,
    HEURISTIC_SIGN,
    LAG_HORIZONS,
    MIN_EVENTS,
    MIN_PAIRS,
    NET_REVENUE_ITEM,
    SCORED_NAMES,
    MarginPair,
    basket_spread,
    beta_on,
    choose_theta,
    classify,
    event_starts,
    forward_return,
    gross_margins,
    heuristic_scores,
    margin_pairs,
    ols,
    price_beta,
    projection_beta,
    projection_pairs,
    shock_by_session,
    verdict,
)


def _days(count: int, start: str = "2021-01-04") -> list[str]:
    cursor = date.fromisoformat(start)
    return [(cursor + timedelta(days=offset)).isoformat() for offset in range(count)]


class GrossMarginTests(unittest.TestCase):
    def test_items_are_gross_profit_over_net_revenue(self):
        self.assertEqual(GROSS_PROFIT_ITEM, "23100")
        self.assertEqual(NET_REVENUE_ITEM, "21001")
        self.assertNotIn("NT2", SCORED_NAMES)
        self.assertNotIn("NT2", HEURISTIC_SIGN)

    def test_margin_uses_both_lines_and_drops_nonpositive_sales(self):
        margins = gross_margins(
            [("2020-03-31", 100.0), ("2020-06-30", 0.0), ("2020-09-30", 200.0)],
            [("2020-03-31", 18.0), ("2020-06-30", 5.0), ("2020-09-30", 50.0)],
        )
        self.assertEqual(margins, [("2020-03-31", 0.18), ("2020-09-30", 0.25)])

    def test_pair_skips_a_missing_quarter_and_stamps_the_lag(self):
        margins = [("2020-03-31", 0.20), ("2020-06-30", 0.25), ("2020-12-31", 0.10)]
        shock = [("2020-06-30", 0.12), ("2020-12-31", -0.30)]
        pairs = margin_pairs(margins, shock, lag_days=45)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].fiscal_end, "2020-06-30")
        self.assertEqual(pairs[0].visible_from, "2020-08-14")
        self.assertAlmostEqual(pairs[0].delta, 0.05)
        self.assertAlmostEqual(pairs[0].shock, 0.12)


def _quarter_ends(count: int) -> list[str]:
    months = (3, 6, 9, 12)
    year = 2014
    slot = 0
    ends = []
    while len(ends) < count:
        month = months[slot]
        day = 30 if month in (6, 9) else 31
        ends.append(date(year, month, day).isoformat())
        slot += 1
        if slot == 4:
            slot = 0
            year += 1
    return ends


class LagPathTests(unittest.TestCase):
    def test_horizons_are_locked_through_four_quarters(self):
        self.assertEqual(LAG_HORIZONS, (0, 1, 2, 3, 4))

    def test_response_arrives_two_quarters_later(self):
        ends = _quarter_ends(10)
        margins = [(day, 0.20) for day in ends]
        shock = [(day, 0.0) for day in ends]
        shock[3] = (ends[3], 0.50)
        margins[5] = (ends[5], 0.30)
        same_quarter, same_n = projection_beta(margins, shock, 0, ends[-1])
        delayed, delayed_n = projection_beta(margins, shock, 2, ends[-1])
        self.assertGreaterEqual(same_n, 2)
        self.assertGreaterEqual(delayed_n, 2)
        self.assertIsNotNone(same_quarter)
        self.assertGreater(delayed, 0.0)
        self.assertGreater(delayed, same_quarter)
        self.assertLess(len(projection_pairs(margins, shock, 2, ends[5])), delayed_n)

    def test_broken_quarter_is_dropped(self):
        margins = [("2020-03-31", 0.20), ("2020-06-30", 0.20), ("2020-12-31", 0.30)]
        shock = [("2020-06-30", 0.20), ("2020-12-31", 0.20)]
        self.assertEqual(projection_pairs(margins, shock, 1, "2020-12-31"), [])


class PitBetaTests(unittest.TestCase):
    def test_future_quarter_does_not_change_today(self):
        early = [
            MarginPair("2019-03-31", "2019-05-15", 0.01 * (index - 6), 0.05 * (index - 6))
            for index in range(MIN_PAIRS)
        ]
        flipped = MarginPair("2020-12-31", "2021-02-14", -0.50, 0.10)
        slope = beta_on(early, "2021-01-04")
        self.assertIsNotNone(slope)
        self.assertAlmostEqual(beta_on([*early, flipped], "2021-01-04"), slope)
        self.assertNotAlmostEqual(beta_on([*early, flipped], "2021-02-14"), slope)

    def test_short_sample_has_no_beta(self):
        pairs = [MarginPair("2020-03-31", "2020-05-15", 0.01, 0.05)] * (MIN_PAIRS - 1)
        self.assertIsNone(beta_on(pairs, "2021-01-04"))

    def test_ols_slope(self):
        self.assertAlmostEqual(ols([1.0, 2.0, 3.0], [-2.0, -4.0, -6.0]), -2.0)
        self.assertIsNone(ols([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))


class EventClockTests(unittest.TestCase):
    def test_open_already_above_the_line_is_not_a_new_cross(self):
        sessions = _days(200)
        shock = {day: 0.30 for day in sessions}
        self.assertEqual(event_starts(sessions, shock, 0.15, sessions[10], sessions[-1]), [])

    def test_lock_skips_a_second_cross_inside_the_forward_window(self):
        sessions = _days(400)
        shock = {day: 0.0 for day in sessions}
        shock[sessions[20]] = 0.20
        shock[sessions[21]] = 0.0
        shock[sessions[50]] = 0.20
        shock[sessions[90]] = 0.20
        starts = event_starts(sessions, shock, 0.15, sessions[0], sessions[-1])
        self.assertEqual(starts, [sessions[20], sessions[90]])

    def test_largest_theta_with_enough_oil_events_wins(self):
        sessions = _days(900)
        shock = {day: 0.0 for day in sessions}
        for index in range(0, MIN_EVENTS * 70, 70):
            shock[sessions[index + 30]] = 0.19
        theta = choose_theta(sessions, shock, sessions[0], sessions[-1])
        self.assertEqual(theta, 0.18)
        self.assertGreaterEqual(
            len(event_starts(sessions, shock, theta, sessions[0], sessions[-1])),
            MIN_EVENTS,
        )

    def test_grid_is_not_widened_when_every_theta_is_short(self):
        sessions = _days(200)
        shock = {day: 0.0 for day in sessions}
        shock[sessions[30]] = 0.50
        self.assertIsNone(choose_theta(sessions, shock, sessions[0], sessions[-1]))


class SpreadTests(unittest.TestCase):
    def test_forward_return_buys_the_next_close(self):
        sessions = _days(80)
        closes = {day: 100.0 + index for index, day in enumerate(sessions)}
        # Mua phiên 1 giá 101, bán phiên 61 giá 161.
        self.assertAlmostEqual(forward_return(closes, sessions, sessions[0]), 161 / 101 - 1)

    def test_heuristic_flips_with_the_oil_sign_and_keeps_two_names_a_side(self):
        up = classify(heuristic_scores(0.20))
        down = classify(heuristic_scores(-0.20))
        self.assertEqual(up, {"PVD": 1, "GAS": 1, "DCM": -1, "DPM": -1})
        self.assertEqual(down, {"PVD": -1, "GAS": -1, "DCM": 1, "DPM": 1})

    def test_one_side_short_is_not_scored(self):
        self.assertIsNone(classify({"PVD": 1.0, "GAS": 1.0, "DCM": 1.0, "DPM": 0.2}))

    def test_verdict_needs_all_three_and_enough_events(self):
        wins = [0.02] * MIN_EVENTS
        loses = [-0.01] * MIN_EVENTS
        self.assertEqual(verdict(wins, loses, [0.0] * MIN_EVENTS), "qua")
        self.assertEqual(verdict(loses, [-0.02] * MIN_EVENTS, [-0.03] * MIN_EVENTS), "truot")
        self.assertEqual(verdict(wins[: MIN_EVENTS - 1], loses[: MIN_EVENTS - 1], loses[: MIN_EVENTS - 1]), "chua_du")

    def test_basket_spread_is_the_mean_gap(self):
        signs = {"PVD": 1, "GAS": 1, "DCM": -1, "DPM": -1}
        forwards = {"PVD": 0.10, "GAS": 0.20, "DCM": -0.10, "DPM": 0.00}
        self.assertAlmostEqual(basket_spread(signs, forwards), 0.15 - (-0.05))

    def test_price_beta_stops_before_the_signal_day(self):
        days = _days(800)
        oil = {day: (0.01 if index % 2 == 0 else -0.01) for index, day in enumerate(days)}
        stock = {day: -2.0 * oil[day] for day in days}
        self.assertAlmostEqual(price_beta(stock, oil, days[-1], sessions=756), -2.0)
        stock[days[-1]] = 5.0
        oil[days[-1]] = 1.0
        self.assertAlmostEqual(price_beta(stock, oil, days[-1], sessions=756), -2.0)

    def test_session_shock_uses_the_last_oil_print(self):
        sessions = ["2021-01-04", "2021-01-05"]
        attached = shock_by_session(sessions, [("2021-01-03", 0.11), ("2021-01-05", 0.40)])
        self.assertEqual(attached["2021-01-04"], 0.11)
        self.assertEqual(attached["2021-01-05"], 0.40)


if __name__ == "__main__":
    unittest.main()
