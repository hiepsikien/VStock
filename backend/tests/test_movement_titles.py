"""The curated movement-title table and its wiring into the span plan.

A printed guitar name is now an identity of the movement, not a readout of the
pattern the macro chooser happened to pick. The table is total for the four
spans that render movements (`1D`, `1W`, `1M`, `3M`); a missing key is a bug,
not a blank line.
"""

from __future__ import annotations

import pytest

from app.sonify.movement_titles import TITLES, movement_title
from app.sonify.span import _planned_title, plan_month, plan_quarter, plan_week

ENSEMBLES = ("classic", "villa", "barrios", "brouwer", "bach", "torroba")
SPANS = {"1D": 1, "1W": 1, "1M": 4, "3M": 3}


def test_table_is_total_for_every_ensemble_and_span():
    expected = {
        (ensemble, span, index)
        for ensemble in ENSEMBLES
        for span, count in SPANS.items()
        for index in range(count)
    }
    assert set(TITLES) == expected
    assert all(TITLES[key].strip() for key in expected)


def test_a_missing_key_raises_instead_of_printing_blank():
    with pytest.raises(KeyError):
        movement_title("classic", "1M", 4)
    with pytest.raises(KeyError):
        movement_title("violin", "1M", 0)


def test_plan_fills_the_title_for_guitar_only():
    assert [movement.title for movement in plan_week(5, "guitar", "bach")] == ["Bourree"]
    assert [movement.title for movement in plan_month([1, 1, 1, 1], "guitar", "barrios")] == [
        "Cathedral",
        "Andante",
        "Polka",
        "Ultimo Tremolo",
    ]
    assert [movement.title for movement in plan_quarter([1, 1, 1], "guitar", "torroba")] == [
        "Olite",
        "Castillo",
        "Danza",
    ]
    assert all(movement.title == "" for movement in plan_month([1, 1, 1, 1], "symphony"))


def test_a_year_reuses_the_month_programme_by_calendar_month():
    # January, April, July, October cycle the four month titles; December takes IV.
    assert _planned_title("guitar", "bach", "1Y", 0) == "Allemande"
    assert _planned_title("guitar", "bach", "1Y", 11) == "Gigue"
    assert _planned_title("symphony", "classic", "1Y", 0) == ""
