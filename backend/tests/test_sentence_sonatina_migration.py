"""Sonatina migration: equivalence, wildcard meter, end anchor, integration."""

from __future__ import annotations

from types import SimpleNamespace

import app.sonify.guitar_torroba as torroba
from app.sonify.guitar_torroba import _sonatina_close_spans, _sonatina_open_spans
from app.sonify.sentence_specs import plan_sentence


def _ctx(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, epb=6)


def _phrase(bars: int, closes: bool) -> SimpleNamespace:
    return SimpleNamespace(start=0, end=bars * 6, closes=closes, rise=1)


def test_sonatina_open_matches_legacy() -> None:
    for length in range(0, 21):
        for n in range(0, 6):
            assert plan_sentence(
                "sonatina", "4/4", length, n, closes=False
            ) == _sonatina_open_spans(length, n), (length, n)


def test_sonatina_close_matches_legacy() -> None:
    for length in range(0, 21):
        for n in range(0, 6):
            assert plan_sentence(
                "sonatina", "4/4", length, n, closes=True
            ) == _sonatina_close_spans(length, n), (length, n)


def test_sonatina_is_meter_independent() -> None:
    for meter in ("3/4", "4/4", "6/8"):
        assert plan_sentence(
            "sonatina", meter, 7, 0, closes=False
        ) == _sonatina_open_spans(7, 0)


def test_close_tail_anchors_to_the_phrase_end() -> None:
    assert plan_sentence("sonatina", "4/4", 7, 0, closes=True) == [
        (4, (0, 1)),
        (3, (4, 5, 6)),
    ]
    assert plan_sentence("sonatina", "4/4", 9, 0, closes=True) == [
        (4, (0, 1)),
        (3, (6, 7, 8)),
    ]


def test_close_short_phrases_clip_the_three_bar_tail() -> None:
    assert plan_sentence("sonatina", "4/4", 1, 0, closes=True) == [(3, (0,))]
    assert plan_sentence("sonatina", "4/4", 2, 0, closes=True) == [(3, (0, 1))]
    assert plan_sentence("sonatina", "4/4", 3, 0, closes=True) == [(3, (0, 1, 2))]


def test_phrase_spans_uses_registry_for_sonatina(monkeypatch) -> None:
    # Capture the oracle before patching, so the assertion is clearly against
    # the legacy output and not the patched binding.
    expected_open = _sonatina_open_spans(7, 0)
    expected_close = _sonatina_close_spans(7, 0)

    def boom(*_args, **_kwargs):
        raise AssertionError("sonatina used the code path")

    monkeypatch.setattr(torroba, "_sonatina_open_spans", boom)
    monkeypatch.setattr(torroba, "_sonatina_close_spans", boom)

    assert torroba._phrase_spans(
        _ctx("4/4"), _phrase(7, closes=False), "sonatina", 0
    ) == expected_open
    assert torroba._phrase_spans(
        _ctx("4/4"), _phrase(7, closes=True), "sonatina", 0
    ) == expected_close
