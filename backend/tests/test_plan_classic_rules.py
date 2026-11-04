"""Intent lock for the two classic ladders.

The golden matrix in `test_plan_classic_parity.py` is the end-to-end lock.
These tests are the fast, direct statement of why the two ladders stay
separate.
"""

from __future__ import annotations

from dataclasses import fields

from app.sonify.plan_rules import MACRO, PHRASE
from app.sonify.plan_rules_classic import (
    CLASSIC_RULES,
    ClassicMacroInputs,
    ClassicPhraseInputs,
    classic_pattern,
)


def _phrase(**overrides) -> ClassicPhraseInputs:
    values = dict(trio=False, mood=None, bpm=100, minor=False)
    values.update(overrides)
    return ClassicPhraseInputs(**values)


def _macro(**overrides) -> ClassicMacroInputs:
    values = dict(
        mood=None,
        bpm=100,
        character=None,
        rel_span=0.0,
        minor=False,
        rally_marked=False,
    )
    values.update(overrides)
    return ClassicMacroInputs(**values)


def test_minor_trio_holds_the_elegy_only_in_the_phrase_ladder() -> None:
    assert classic_pattern(PHRASE, _phrase(trio=True, minor=True)) == "elegiaque"
    # A major trio is not the elegy; the flag needs the minor mode.
    assert classic_pattern(PHRASE, _phrase(trio=True, minor=False)) == "study"

    # The macro ladder cannot read the flag at all; it leaves the contrast to
    # `_assign_macro` / `_contrast_pattern`.
    macro_fields = {field.name for field in fields(ClassicMacroInputs)}
    assert "trio" not in macro_fields
    assert "bridge" not in macro_fields
    assert classic_pattern(MACRO, _macro()) == "study"


def test_the_phrase_ladder_never_dances() -> None:
    # A wide major rally phrase still falls back to the study: galop is a
    # whole-body macro decision.
    assert (
        classic_pattern(
            PHRASE, _phrase(mood="rally", bpm=100, minor=False)
        )
        == "study"
    )
    assert (
        classic_pattern(
            MACRO,
            _macro(mood="rally", bpm=100, character="rally", rel_span=0.05),
        )
        == "galop"
    )


def test_galop_needs_a_wide_major_rally_body() -> None:
    wide = dict(mood="rally", bpm=100, character="rally", rel_span=0.05)
    assert classic_pattern(MACRO, _macro(**wide)) == "galop"
    # A narrow span, the minor mode, and a character-less body that was never
    # marked as rally all keep the study.
    assert (
        classic_pattern(MACRO, _macro(**{**wide, "rel_span": 0.011})) == "study"
    )
    assert classic_pattern(MACRO, _macro(**{**wide, "minor": True})) == "study"
    assert (
        classic_pattern(
            MACRO,
            _macro(mood="rally", bpm=100, character=None, rel_span=0.05),
        )
        == "study"
    )
    # A body marked as rally at the bar level may dance even without a
    # movement character.
    assert (
        classic_pattern(
            MACRO,
            _macro(
                mood="rally",
                bpm=100,
                character=None,
                rel_span=0.05,
                rally_marked=True,
            ),
        )
        == "galop"
    )


def test_mood_and_slow_floor_share_the_macro_order() -> None:
    assert classic_pattern(MACRO, _macro(bpm=72)) == "elegiaque"
    assert classic_pattern(MACRO, _macro(mood="selloff")) == "elegiaque"
    assert classic_pattern(MACRO, _macro(mood="calm")) == "cantabile"
    assert classic_pattern(MACRO, _macro(mood="volatile")) == "mozart_var"
    assert classic_pattern(MACRO, _macro()) == "study"

    # The phrase ladder reads the same moods above the slow floor.
    assert classic_pattern(PHRASE, _phrase(bpm=72)) == "elegiaque"
    assert classic_pattern(PHRASE, _phrase(mood="selloff", bpm=100)) == "elegiaque"
    assert classic_pattern(PHRASE, _phrase(mood="calm", bpm=100)) == "cantabile"
    assert classic_pattern(PHRASE, _phrase(mood="volatile", bpm=100)) == "mozart_var"


def test_input_type_must_match_the_mode() -> None:
    try:
        classic_pattern(MACRO, _phrase())
    except TypeError as error:
        assert "ClassicMacroInputs" in str(error)
    else:  # pragma: no cover - the guard is the point of this test
        raise AssertionError("a phrase input must not pass as a macro input")


def test_every_rule_belongs_to_one_mode_and_has_a_reason() -> None:
    assert {rule.mode for rule in CLASSIC_RULES} == {PHRASE, MACRO}
    assert all(rule.why for rule in CLASSIC_RULES)
