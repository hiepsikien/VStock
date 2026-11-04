"""Intent lock for Bach's primary and contrast ladders.

The golden matrix in `test_plan_bach_parity.py` is the end-to-end lock. These
tests are the fast, direct statement of why each branch exists.
"""

from __future__ import annotations

from dataclasses import replace

from app.sonify.plan_rules import MACRO, PHRASE
from app.sonify.plan_rules_bach import (
    BACH_CONTRAST_RULES,
    BACH_RULES,
    ContrastInputs,
    PrimaryInputs,
    bach_contrast,
    bach_pattern,
    bach_region_patterns,
)


def _primary(**overrides) -> PrimaryInputs:
    values = dict(
        framed=True,
        daily=False,
        finale=False,
        kind="4/4",
        bpm=96,
        mood=None,
        rel_span=0.0,
        narrow_or_held=False,
        wide=False,
        lively=False,
        has_contrast=False,
        has_material=True,
    )
    values.update(overrides)
    return PrimaryInputs(**values)


def _contrast(**overrides) -> ContrastInputs:
    values = dict(kind="4/4", primary="bach_bourree", mood=None)
    values.update(overrides)
    return ContrastInputs(**values)


def test_phrase_and_macro_share_every_primary_decision() -> None:
    # The two scopes call the same chooser with different aggregations; unlike
    # Villa there is no scope-specific branch to lock apart.
    for case in (
        _primary(),
        _primary(framed=False, mood="volatile"),
        _primary(framed=False, kind="3/4", bpm=60),
        _primary(daily=True, mood="calm", narrow_or_held=True),
        _primary(daily=True, mood="rally", wide=True, lively=True),
        _primary(finale=True, mood="calm"),
        _primary(kind="6/8", mood="calm"),
    ):
        assert bach_pattern(PHRASE, case) == bach_pattern(MACRO, case), case


def test_the_daily_fingerprint_has_its_own_menu() -> None:
    assert bach_pattern(MACRO, _primary(daily=True, mood="volatile")) == "bach_fuga"
    assert bach_pattern(MACRO, _primary(daily=True, mood="selloff")) == "bach_chaconne"
    assert (
        bach_pattern(
            MACRO, _primary(daily=True, mood="calm", narrow_or_held=True)
        )
        == "bach_prelude"
    )
    assert (
        bach_pattern(MACRO, _primary(daily=True, mood="calm")) == "bach_allemande"
    )
    assert bach_pattern(MACRO, _primary(daily=True, wide=False)) == "bach_bourree"
    assert (
        bach_pattern(MACRO, _primary(daily=True, wide=True, lively=True))
        == "bach_courante"
    )
    assert (
        bach_pattern(MACRO, _primary(daily=True, wide=True, lively=False))
        == "bach_gavotte"
    )


def test_the_unframed_slow_row_answers_a_wide_selloff_with_the_chaconne() -> None:
    wide = _primary(
        framed=False,
        kind="3/4",
        bpm=100,
        mood="selloff",
        rel_span=0.02,
        has_contrast=False,
    )
    assert bach_pattern(PHRASE, wide) == "bach_chaconne"
    # A narrow selloff, or one that already has a contrast section, stays the
    # Sarabande; the contrast area takes the Chaconne instead.
    assert (
        bach_pattern(PHRASE, replace(wide, rel_span=0.01)) == "bach_sarabande"
    )
    assert (
        bach_pattern(PHRASE, replace(wide, has_contrast=True)) == "bach_sarabande"
    )


def test_the_finale_menu_is_the_four_four_row_only() -> None:
    # A 6/8 scherzo can share the numeric finale pedal; it keeps its own row.
    assert (
        bach_pattern(MACRO, _primary(finale=True, kind="4/4", mood="calm"))
        == "bach_gavotte"
    )
    assert (
        bach_pattern(MACRO, _primary(finale=True, kind="6/8", mood="calm"))
        == "bach_courante"
    )
    assert (
        bach_pattern(MACRO, _primary(finale=True, kind="6/8", mood="volatile"))
        == "bach_fuga"
    )


def test_contrast_takes_the_guest_before_the_bourree_fallback() -> None:
    assert (
        bach_contrast(PHRASE, _contrast(primary="bach_prelude")) == "bach_allemande"
    )
    assert (
        bach_contrast(PHRASE, _contrast(primary="bach_allemande")) == "bach_courante"
    )
    assert bach_contrast(PHRASE, _contrast(primary="bach_courante")) == "bach_gigue"
    assert (
        bach_contrast(PHRASE, _contrast(kind="6/8", mood="calm")) == "bach_bourree"
    )
    assert bach_contrast(PHRASE, _contrast(kind="6/8")) == "bach_fuga"
    assert (
        bach_contrast(PHRASE, _contrast(kind="3/4", primary="bach_sarabande"))
        == "bach_chaconne"
    )
    assert bach_contrast(PHRASE, _contrast(primary="bach_bourree")) == "bach_fuga"
    assert (
        bach_contrast(PHRASE, _contrast(primary="bach_fuga", mood="rally"))
        == "bach_bourree"
    )
    assert (
        bach_contrast(PHRASE, _contrast(primary="bach_fuga", mood="calm"))
        == "bach_gavotte"
    )


def test_a_suite_row_never_closes_on_prelude_after_another_dance() -> None:
    assert bach_region_patterns(
        ["bach_prelude", "bach_allemande", "bach_prelude"]
    ) == ["bach_prelude", "bach_allemande", "bach_allemande"]
    # A two-part row has no reprise, so Sarabande -- Prelude stays.
    assert bach_region_patterns(["bach_sarabande", "bach_prelude"]) == [
        "bach_sarabande",
        "bach_prelude",
    ]
    assert bach_region_patterns(
        ["bach_bourree", "bach_fuga", "bach_prelude"]
    ) == ["bach_bourree", "bach_fuga", "bach_fuga"]


def test_input_type_must_match_the_table() -> None:
    for call, wrong in (
        (lambda case: bach_pattern(MACRO, case), _contrast()),
        (lambda case: bach_contrast(MACRO, case), _primary()),
    ):
        try:
            call(wrong)
        except TypeError as error:
            assert "Inputs" in str(error)
        else:  # pragma: no cover - the guard is the point of this test
            raise AssertionError("a case from the other table must not pass")


def test_every_rule_belongs_to_one_mode_and_has_a_reason() -> None:
    for table in (BACH_RULES, BACH_CONTRAST_RULES):
        assert {rule.mode for rule in table} == {PHRASE, MACRO}
        assert all(rule.why for rule in table)
