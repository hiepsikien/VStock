"""Intent lock for the Brouwer plan ladder.

The golden matrix in `test_plan_brouwer_parity.py` is the end-to-end lock.
These tests are the fast, direct statement of the rule order and of what the
primary chooser deliberately cannot read.
"""

from __future__ import annotations

from dataclasses import fields

from app.sonify.plan_rules import MACRO, PHRASE, PhraseInputs
from app.sonify.plan_rules_brouwer import (
    BROUWER_RULES,
    BrouwerInputs,
    _expand,
    brouwer_pattern,
)


def _inputs(**overrides) -> BrouwerInputs:
    values = dict(mood=None, bpm=100)
    values.update(overrides)
    return BrouwerInputs(**values)


def test_the_primary_ladder_reads_mood_and_tempo_only() -> None:
    names = {field.name for field in fields(BrouwerInputs)}
    assert names == {"mood", "bpm"}


def test_rule_order_is_calm_slow_or_selloff_volatile_then_fallback() -> None:
    # Calm wins even at a slow tempo.
    assert brouwer_pattern(PHRASE, _inputs(mood="calm", bpm=60)) == "noviembre"
    # Slow wins after calm, for every other mood.
    assert brouwer_pattern(PHRASE, _inputs(mood="rally", bpm=72)) == "sarabande"
    # Selloff wins above the slow floor.
    assert brouwer_pattern(PHRASE, _inputs(mood="selloff", bpm=100)) == "sarabande"
    # Volatile is the last named row.
    assert brouwer_pattern(PHRASE, _inputs(mood="volatile", bpm=100)) == "elogio_pizz"
    # None and rally fall through to the etude.
    assert brouwer_pattern(PHRASE, _inputs(mood=None, bpm=100)) == "brouwer_etude"
    assert brouwer_pattern(PHRASE, _inputs(mood="rally", bpm=120)) == "brouwer_etude"


def test_a_mode_specific_row_does_not_leak() -> None:
    rows = _expand(
        (
            (
                (PHRASE,),
                lambda case: True,
                "noviembre",
                "synthetic mode-specific row",
            ),
        )
    )
    assert [rule.mode for rule in rows] == [PHRASE]
    assert [rule.pattern for rule in rows] == ["noviembre"]


def test_phrase_and_macro_ladders_agree_today() -> None:
    # Same question, same inputs. If a future edit splits them, this test is
    # the one that must change together with a rendered intent test.
    for mood in (None, "calm", "rally", "selloff", "volatile"):
        for bpm in (60, 72, 73, 90, 100, 120):
            case = _inputs(mood=mood, bpm=bpm)
            assert brouwer_pattern(PHRASE, case) == brouwer_pattern(MACRO, case)


def test_contrast_is_not_in_the_primary_table() -> None:
    # `_select_body` and `_assign_macro` answer trio/bridge after the primary.
    # No input field can carry that flag into this table.
    names = {field.name for field in fields(BrouwerInputs)}
    assert "trio" not in names
    assert "bridge" not in names
    # The table cannot return a contrast-only decision on its own.
    assert {rule.pattern for rule in BROUWER_RULES} == {
        "noviembre",
        "sarabande",
        "elogio_pizz",
    }


def test_input_type_must_match_the_ladder() -> None:
    try:
        brouwer_pattern(PHRASE, PhraseInputs(
            trio=False,
            bridge=False,
            mood=None,
            bpm=100,
            band="mf",
            first_body=False,
            kind="4/4",
        ))
    except TypeError as error:
        assert "BrouwerInputs" in str(error)
    else:  # pragma: no cover - the guard is the point of this test
        raise AssertionError("a Villa phrase input must not pass as Brouwer input")


def test_every_rule_belongs_to_one_mode_and_has_a_reason() -> None:
    assert {rule.mode for rule in BROUWER_RULES} == {PHRASE, MACRO}
    assert all(rule.why for rule in BROUWER_RULES)
