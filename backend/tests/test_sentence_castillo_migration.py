"""Castillo 3/4 migration: equivalence, integration, and registry validation."""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from types import SimpleNamespace

import pytest

import app.sonify.guitar_torroba as torroba
from app.sonify.guitar_torroba import _castillo_34_spans
from app.sonify.sentence_specs import (
    Select,
    SentenceSpec,
    Slot,
    Span,
    plan_sentence,
    register,
)


def _ctx(kind: str) -> SimpleNamespace:
    return SimpleNamespace(kind=kind, epb=6)


def _phrase(bars: int = 9, closes: bool = False, rise: int = 1) -> SimpleNamespace:
    return SimpleNamespace(start=0, end=bars * 6, closes=closes, rise=rise)


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


def test_phrase_spans_uses_registry_for_castillo_34(monkeypatch) -> None:
    """The 3/4 branch must not reach the legacy selector."""

    def boom(*_args, **_kwargs):
        raise AssertionError("castillo 3/4 used the code path")

    monkeypatch.setattr(torroba, "_castillo_spans", boom)
    spans = torroba._phrase_spans(_ctx("3/4"), _phrase(9), "castillo", 0)
    assert spans == _castillo_34_spans(9, 0)


def test_phrase_spans_falls_back_for_other_meters(monkeypatch) -> None:
    monkeypatch.setattr(
        torroba, "_castillo_spans", lambda length, n, kind: [("legacy", (0,))]
    )
    assert torroba._phrase_spans(_ctx("4/4"), _phrase(9), "castillo", 0) == [
        ("legacy", (0,))
    ]


def _bad_spec(**span_kwargs) -> SentenceSpec:
    return SentenceSpec(
        id="bad",
        pattern="bad",
        meter="3/4",
        select=Select(),
        span=Span(**span_kwargs),
        slots=(Slot(0, 1, 1),),
    )


def test_register_rejects_tile_zero() -> None:
    with pytest.raises(ValueError, match="tile"):
        register("bad", "3/4", _bad_spec(tile=0))


def test_register_rejects_overlapping_slots() -> None:
    spec = SentenceSpec(
        id="bad",
        pattern="bad",
        meter="3/4",
        select=Select(),
        span=Span(tile=9),
        slots=(Slot(0, 5, 1), Slot(4, 2, 2)),
    )
    with pytest.raises(ValueError, match="overlap"):
        register("bad", "3/4", spec)


def test_register_rejects_unknown_parity() -> None:
    spec = SentenceSpec(
        id="bad",
        pattern="bad",
        meter="3/4",
        select=Select(n_parity="evan"),
        span=Span(tile=9),
        slots=(Slot(0, 1, 1),),
    )
    with pytest.raises(ValueError, match="n_parity"):
        register("bad", "3/4", spec)


def test_register_rejects_duplicate_key() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register("castillo", "3/4", torroba.CASTILLO_34_WALK)


def test_plan_sentence_loads_the_owner_module() -> None:
    """A caller that imports only sentence_specs still plans castillo 3/4."""
    backend = pathlib.Path(__file__).resolve().parents[1]
    code = (
        "from app.sonify.sentence_specs import plan_sentence;"
        "print(plan_sentence('castillo', '3/4', 9, 0))"
    )
    env = {**os.environ, "PYTHONPATH": str(backend)}
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert out == "[(13, (0, 1, 2, 3, 4, 5, 6, 7, 8))]"
