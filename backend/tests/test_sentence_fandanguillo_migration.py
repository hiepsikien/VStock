"""Fandanguillo migration: equivalence, middle anchor, wildcard meter, integration."""

from __future__ import annotations

from types import SimpleNamespace

import app.sonify.guitar_torroba as torroba
from app.sonify.guitar_torroba import _fandanguillo_spans
from app.sonify.sentence_specs import plan_sentence


def _ctx(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, epb=6)


def _phrase(bars: int, closes: bool = False, rise: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        start=0, end=bars * 6, closes=closes, rise=rise
    )


def test_fandanguillo_planner_matches_legacy() -> None:
    for length in range(0, 21):
        for n in range(0, 6):
            for closes in (False, True):
                for rise in (0, 1, 2):
                    assert plan_sentence(
                        "fandanguillo", "4/4", length, n, closes=closes, rise=rise
                    ) == _fandanguillo_spans(
                        SimpleNamespace(rise=rise), length, n, closes
                    ), (length, n, closes, rise)


def test_fandanguillo_ignores_the_meter() -> None:
    for meter in ("3/4", "4/4", "6/8"):
        for length in range(0, 13):
            for n in range(0, 4):
                for closes in (False, True):
                    assert plan_sentence(
                        "fandanguillo", meter, length, n, closes=closes, rise=1
                    ) == _fandanguillo_spans(
                        SimpleNamespace(rise=1), length, n, closes
                    ), (meter, length, n, closes)


def test_fandanguillo_needs_a_rise() -> None:
    assert plan_sentence("fandanguillo", "4/4", 4, 0, rise=0) == []
    assert plan_sentence("fandanguillo", "4/4", 2, 1, rise=0) == []
    assert plan_sentence("fandanguillo", "4/4", 4, 0, rise=1) == [(5, (0, 1, 2, 3))]


def test_even_turn_needs_room_for_four_bars() -> None:
    # `room` is `length - 1` on a close, so an open phrase enters at L4 and a
    # closing one only at L5.
    assert plan_sentence("fandanguillo", "4/4", 3, 0, closes=False, rise=1) == []
    assert plan_sentence("fandanguillo", "4/4", 4, 0, closes=False, rise=1) == [
        (5, (0, 1, 2, 3))
    ]
    assert plan_sentence("fandanguillo", "4/4", 4, 0, closes=True, rise=1) == []
    assert plan_sentence("fandanguillo", "4/4", 5, 0, closes=True, rise=1) == [
        (5, (0, 1, 2, 3))
    ]


def test_odd_turn_is_centred_on_the_phrase() -> None:
    # The two-bar type 2 starts at max(0, length // 2 - 1), which the middle
    # anchor expresses as `start=-1` from `length // 2`.
    assert plan_sentence("fandanguillo", "4/4", 2, 1, closes=False, rise=1) == [(2, (0, 1))]
    assert plan_sentence("fandanguillo", "4/4", 4, 1, closes=False, rise=1) == [(2, (1, 2))]
    assert plan_sentence("fandanguillo", "4/4", 8, 1, closes=False, rise=1) == [(2, (3, 4))]
    assert plan_sentence("fandanguillo", "4/4", 3, 1, closes=True, rise=1) == [(2, (0, 1))]
    assert plan_sentence("fandanguillo", "4/4", 6, 1, closes=True, rise=1) == [(2, (2, 3))]
    # room < 2 on a close: L2 leaves no room once the closing bar is reserved.
    assert plan_sentence("fandanguillo", "4/4", 2, 1, closes=True, rise=1) == []


def test_phrase_spans_uses_registry_for_fandanguillo(monkeypatch) -> None:
    expected_even = _fandanguillo_spans(SimpleNamespace(rise=1), 4, 0, False)
    expected_odd = _fandanguillo_spans(SimpleNamespace(rise=1), 8, 1, False)
    expected_close = _fandanguillo_spans(SimpleNamespace(rise=1), 5, 0, True)

    def boom(*_args, **_kwargs):
        raise AssertionError("fandanguillo used the code path")

    monkeypatch.setattr(torroba, "_fandanguillo_spans", boom)

    assert torroba._phrase_spans(
        _ctx("4/4"), _phrase(4), "fandanguillo", 0
    ) == expected_even
    assert torroba._phrase_spans(
        _ctx("3/4"), _phrase(8), "fandanguillo", 1
    ) == expected_odd
    assert torroba._phrase_spans(
        _ctx("6/8"), _phrase(5, closes=True), "fandanguillo", 0
    ) == expected_close


def test_phrase_spans_falls_back_to_empty_without_a_rise(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("fandanguillo used the code path")

    monkeypatch.setattr(torroba, "_fandanguillo_spans", boom)
    assert torroba._phrase_spans(
        _ctx("4/4"), _phrase(4, rise=0), "fandanguillo", 0
    ) == []
