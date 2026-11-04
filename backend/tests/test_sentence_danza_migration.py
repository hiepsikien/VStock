"""Danza migration: equivalence, meter-specific registry, integration."""

from __future__ import annotations

from types import SimpleNamespace

import app.sonify.guitar_torroba as torroba
from app.sonify.guitar_torroba import _danza_spans
from app.sonify.sentence_specs import plan_sentence


def _ctx(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, epb=6)


def _phrase(bars: int, closes: bool = False) -> SimpleNamespace:
    return SimpleNamespace(start=0, end=bars * 6, closes=closes, rise=1)


def test_danza_planner_matches_legacy() -> None:
    for meter in ("3/4", "6/8"):
        for length in range(0, 21):
            for closes in (False, True):
                assert plan_sentence(
                    "danza", meter, length, 0, closes=closes
                ) == _danza_spans(
                    SimpleNamespace(kind=meter), length, closes
                ), (meter, length, closes)


def test_danza_44_stays_on_the_code_path() -> None:
    # No 4/4 key, so `plan_sentence` reports "not migrated" and the legacy
    # selector answers `[]` at every length.
    for length in range(0, 21):
        for closes in (False, True):
            assert plan_sentence("danza", "4/4", length, 0, closes=closes) is None
            assert _danza_spans(SimpleNamespace(kind="4/4"), length, closes) == []


def test_danza_short_phrases_and_the_closing_four_bar_stay_on_the_grid() -> None:
    for meter in ("3/4", "6/8"):
        for length in (0, 1, 2, 3):
            assert plan_sentence("danza", meter, length, 0) == []
        assert plan_sentence("danza", meter, 4, 0, closes=False) == [
            (6, (0, 1, 2, 3))
        ]
        assert plan_sentence("danza", meter, 4, 0, closes=True) == []
        assert plan_sentence("danza", meter, 5, 0, closes=True) == [
            (6, (0, 1, 2, 3))
        ]


def test_phrase_spans_uses_registry_for_danza(monkeypatch) -> None:
    expected_open = _danza_spans(SimpleNamespace(kind="3/4"), 6, False)
    expected_close = _danza_spans(SimpleNamespace(kind="6/8"), 6, True)

    def boom(*_args, **_kwargs):
        raise AssertionError("danza used the code path")

    monkeypatch.setattr(torroba, "_danza_spans", boom)

    assert torroba._phrase_spans(
        _ctx("3/4"), _phrase(6), "danza", 0
    ) == expected_open
    assert torroba._phrase_spans(
        _ctx("6/8"), _phrase(6, closes=True), "danza", 0
    ) == expected_close


def test_phrase_spans_falls_back_for_danza_44(monkeypatch) -> None:
    def fake(ctx, length: int, closes: bool):
        del ctx, length, closes
        return [("legacy", (0,))]

    monkeypatch.setattr(torroba, "_danza_spans", fake)
    assert torroba._phrase_spans(_ctx("4/4"), _phrase(6), "danza", 0) == [
        ("legacy", (0,))
    ]
