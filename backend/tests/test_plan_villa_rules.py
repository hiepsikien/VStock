"""Intent lock for the two Villa ladders.

The golden matrix in `test_plan_villa_parity.py` is the end-to-end lock. These
tests are the fast, direct statement of why the two ladders stay separate.
"""

from __future__ import annotations

from dataclasses import fields

from app.sonify.plan_rules import (
    MACRO,
    PHRASE,
    MacroInputs,
    PhraseInputs,
    VILLA_RULES,
    villa_pattern,
)


def _phrase(**overrides) -> PhraseInputs:
    values = dict(
        trio=False,
        bridge=False,
        mood=None,
        bpm=100,
        band="mf",
        first_body=False,
        kind="4/4",
    )
    values.update(overrides)
    return PhraseInputs(**values)


def _macro(**overrides) -> MacroInputs:
    values = dict(mood=None, bpm=100, kind="4/4", quiet_majority=False)
    values.update(overrides)
    return MacroInputs(**values)


def test_trio_and_bridge_sing_on_the_thumb_only_in_the_phrase_ladder() -> None:
    assert villa_pattern(PHRASE, _phrase(trio=True)) == "thumb_cantabile"
    assert villa_pattern(PHRASE, _phrase(bridge=True)) == "thumb_cantabile"

    # The macro ladder cannot read the flags at all; it leaves the contrast to
    # `_assign_macro` / `_contrast_pattern`.
    macro_fields = {field.name for field in fields(MacroInputs)}
    assert "trio" not in macro_fields
    assert "bridge" not in macro_fields
    assert villa_pattern(MACRO, _macro()) == "villa_pattern"


def test_one_quiet_bar_is_enough_for_phrase_but_not_for_macro() -> None:
    assert villa_pattern(PHRASE, _phrase(band="p")) == "chord_melody"

    macro_fields = {field.name for field in fields(MacroInputs)}
    assert "band" not in macro_fields
    assert villa_pattern(MACRO, _macro(quiet_majority=False)) == "villa_pattern"
    assert villa_pattern(MACRO, _macro(quiet_majority=True)) == "chord_melody"


def test_first_body_only_guards_the_phrase_ladder() -> None:
    # Opening body above the tremolo floor stays the roll, even for rally.
    assert (
        villa_pattern(PHRASE, _phrase(first_body=True, bpm=100, mood="rally"))
        == "villa_pattern"
    )
    # An interior rally phrase takes Etude 1.
    assert (
        villa_pattern(PHRASE, _phrase(first_body=False, bpm=100, mood="rally"))
        == "etude1"
    )

    # The macro ladder applies the etude to the whole body, opening included.
    macro_fields = {field.name for field in fields(MacroInputs)}
    assert "first_body" not in macro_fields
    assert villa_pattern(MACRO, _macro(mood="rally", bpm=100)) == "etude1"


def test_input_type_must_match_the_mode() -> None:
    try:
        villa_pattern(MACRO, _phrase())
    except TypeError as error:
        assert "MacroInputs" in str(error)
    else:  # pragma: no cover - the guard is the point of this test
        raise AssertionError("a phrase input must not pass as a macro input")


def test_every_rule_belongs_to_one_mode_and_have_a_reason() -> None:
    assert {rule.mode for rule in VILLA_RULES} == {PHRASE, MACRO}
    assert all(rule.why for rule in VILLA_RULES)
