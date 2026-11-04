"""Equivalence test for the first sentence migration (castillo 3/4)."""

from __future__ import annotations

from app.sonify.guitar_torroba import _castillo_34_spans
from app.sonify.sentence_specs import plan_sentence


def test_castillo_34_planner_matches_legacy() -> None:
    for length in range(0, 13):
        for n in range(0, 4):
            assert plan_sentence("castillo", "3/4", length, n) == _castillo_34_spans(
                length, n
            ), (length, n)


def test_other_castillo_meters_stay_on_the_code_path() -> None:
    for meter in ("4/4", "6/8"):
        assert plan_sentence("castillo", meter, 9, 0) is None


def test_castillo_34_length_one_is_unsupported() -> None:
    assert plan_sentence("castillo", "3/4", 1, 0) == []
