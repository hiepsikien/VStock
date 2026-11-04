"""Parity lock for the Torroba span selectors and the galop cycle.

This is the gate the sentence migration runs against: every archetype in
`docs/sonify-guitar-model.md` §13.6 must reproduce these outputs exactly.
Changing a selector on purpose means regenerating the fixture in the same
commit, so the diff is reviewable.
"""

from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

from app.sonify.guitar_sor import _galop_body_index
from app.sonify.guitar_torroba import (
    _castillo_34_spans,
    _castillo_spans,
    _danza_spans,
    _fandanguillo_spans,
    _sonatina_close_spans,
    _sonatina_open_spans,
)

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sentence_plan.json"
LENGTHS = range(0, 13)
PHASES = range(0, 4)


def _norm(value):
    """Tuples become lists so the fixture can be plain JSON."""
    return json.loads(json.dumps(value))


def _galop_ctx(bars: int, patterns: list[str]) -> SimpleNamespace:
    ctx = SimpleNamespace()
    ctx.kind_at = {bar: "phrase" for bar in range(bars)}
    ctx._pattern_source = None
    ctx._pattern_signature = None
    ctx._pattern_cache = {}
    ctx.epb = 8
    ctx.phrases = [
        SimpleNamespace(start=bar * 8, end=(bar + 1) * 8) for bar in range(bars)
    ]
    return ctx


def _cases() -> dict[str, object]:
    out: dict[str, object] = {}
    for length in LENGTHS:
        for n in PHASES:
            out[f"castillo_34|{length}|{n}"] = _castillo_34_spans(length, n)
            for kind in ("3/4", "4/4", "6/8"):
                out[f"castillo|{length}|{n}|{kind}"] = _castillo_spans(length, n, kind)
            out[f"sonatina_open|{length}|{n}"] = _sonatina_open_spans(length, n)
            out[f"sonatina_close|{length}|{n}"] = _sonatina_close_spans(length, n)
            for closes in (False, True):
                for kind in ("3/4", "4/4", "6/8"):
                    out[f"danza|{length}|{closes}|{kind}"] = _danza_spans(
                        SimpleNamespace(kind=kind), length, closes
                    )
                for rise in (0, 1, 2):
                    out[f"fandanguillo|{length}|{n}|{closes}|{rise}"] = _fandanguillo_spans(
                        SimpleNamespace(rise=rise), length, n, closes
                    )

    for bars in range(1, 31):
        patterns = ["galop"] * bars
        out[f"galop|{bars}"] = _galop_body_index(_galop_ctx(bars, patterns), bars - 1, patterns)

    for cut in range(0, 10):
        bars = 10
        patterns = ["galop"] * bars
        patterns[cut] = "study"
        out[f"galop_reset|{cut}"] = _galop_body_index(
            _galop_ctx(bars, patterns), bars - 1, patterns
        )
    return out


def test_selectors_match_the_fixture() -> None:
    cases = _cases()
    expected = json.loads(FIXTURE.read_text())
    missing = sorted(set(cases) - set(expected))
    extra = sorted(set(expected) - set(cases))
    assert not missing and not extra, (missing[:5], extra[:5])

    mismatched = {
        name: (_norm(value), expected[name])
        for name, value in cases.items()
        if _norm(value) != expected[name]
    }
    assert not mismatched, list(mismatched)[:3]


def test_fixture_covers_every_family() -> None:
    expected = json.loads(FIXTURE.read_text())
    for family in (
        "castillo_34",
        "castillo",
        "sonatina_open",
        "sonatina_close",
        "danza",
        "fandanguillo",
        "galop",
        "galop_reset",
    ):
        assert any(name.startswith(f"{family}|") for name in expected), family
