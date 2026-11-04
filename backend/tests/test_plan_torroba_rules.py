"""Intent lock for the Torroba primary and contrast tables.

The golden matrix in `test_plan_torroba_parity.py` is the end-to-end lock.
These tests are the fast, direct statement of which meter/mood cell maps to
which id, and why the two plan scopes stay separate without disagreeing on the
primary answer.
"""

from __future__ import annotations

from dataclasses import fields
from types import SimpleNamespace

from app.sonify.guitar_torroba import _torroba_contrast, _torroba_primary
from app.sonify.plan_rules import MACRO, PHRASE
from app.sonify.plan_rules_torroba import (
    TORROBA_CONTRAST_RULES,
    TORROBA_PRIMARY_RULES,
    ContrastInputs,
    PrimaryInputs,
    torroba_contrast,
    torroba_primary,
)

PRIMARY = {
    ("4/4", None): "olite",
    ("4/4", "calm"): "olite",
    ("4/4", "rally"): "olite",
    ("4/4", "selloff"): "olite",
    ("4/4", "volatile"): "olite",
    ("3/4", None): "castillo",
    ("3/4", "calm"): "castillo",
    ("3/4", "rally"): "torroba_tremolo",
    ("3/4", "selloff"): "castillo",
    ("3/4", "volatile"): "danza",
    ("6/8", None): "danza",
    ("6/8", "calm"): "danza",
    ("6/8", "rally"): "alcaniz",
    ("6/8", "selloff"): "fandanguillo",
    ("6/8", "volatile"): "fandanguillo",
    # An unknown meter uses the 4/4 row, and that row's fallback is Olite.
    ("12/8", None): "olite",
    ("12/8", "calm"): "olite",
    ("12/8", "rally"): "olite",
    ("12/8", "selloff"): "olite",
    ("12/8", "volatile"): "olite",
}


def _primary(kind: str, mood: str | None, *, framed_macro: bool = False) -> str:
    return torroba_primary(
        PrimaryInputs(kind=kind, mood=mood, framed_macro=framed_macro)
    )


def _contrast(kind: str, primary: str, mood: str | None = None) -> str:
    return torroba_contrast(ContrastInputs(kind=kind, primary=primary, mood=mood))


def test_primary_map_is_the_meter_mood_table() -> None:
    for (kind, mood), expected in PRIMARY.items():
        assert _primary(kind, mood) == expected, (kind, mood)
        assert _primary(kind, mood, framed_macro=True) == expected, (kind, mood)


def test_unknown_mood_uses_the_row_fallback() -> None:
    # 3/4 is caught by the early guard and stays Castillo.
    assert _primary("3/4", "mystery") == "castillo"
    # 6/8 has a calm cell, so the calm cell is the fallback.
    assert _primary("6/8", "mystery") == "danza"
    # The 4/4 row has no calm cell, so it falls through to Olite.
    assert _primary("4/4", "mystery") == "olite"


def test_the_two_scopes_share_the_primary_answer_but_keep_the_flag() -> None:
    # Every row is registered under both modes, in table order. The flag is
    # still carried by the call sites: phrase passes False, macro passes True.
    assert {rule.mode for rule in TORROBA_PRIMARY_RULES} == {PHRASE, MACRO}
    phrase = [(rule.pattern, rule.why) for rule in TORROBA_PRIMARY_RULES if rule.mode == PHRASE]
    macro = [(rule.pattern, rule.why) for rule in TORROBA_PRIMARY_RULES if rule.mode == MACRO]
    assert phrase == macro
    for kind, mood in PRIMARY:
        assert _primary(kind, mood, framed_macro=False) == _primary(
            kind, mood, framed_macro=True
        )

    # The wrapper keeps the `framed_macro` keyword, so the two production
    # paths cannot drift into one call shape by accident.
    simple = SimpleNamespace(kind="6/8")
    assert _torroba_primary(simple, "rally", framed_macro=False) == "alcaniz"
    assert _torroba_primary(simple, "rally", framed_macro=True) == "alcaniz"


def test_primary_scope_never_reads_the_phrase_only_flags() -> None:
    names = {field.name for field in fields(PrimaryInputs)}
    assert names == {"kind", "mood", "framed_macro"}
    # Phrase-path inputs (trio/bridge), dynamic bands, and hold/running are not
    # part of this chooser. Contrast is a separate step.
    for missing in ("trio", "bridge", "band", "bpm", "quiet_majority", "first_body"):
        assert missing not in names


def test_contrast_map_and_the_primary_fallback() -> None:
    expected = {
        # The legacy cells that today's primary map cannot produce.
        ("4/4", "castillo", None): "olite",
        ("4/4", "sonatina", None): "castillo",
        ("3/4", "sonatina", None): "castillo",
        # The live 4/4 pair.
        ("4/4", "olite", "rally"): "castillo",
        ("4/4", "olite", "calm"): "castillo",
        # The 3/4 pairs, including the missing-contrast fallback.
        ("3/4", "castillo", "calm"): "torroba_tremolo",
        ("3/4", "castillo", "selloff"): "danza",
        ("3/4", "castillo", None): "castillo",
        ("3/4", "castillo", "rally"): "castillo",
        ("3/4", "torroba_tremolo", "rally"): "danza",
        ("3/4", "danza", "volatile"): "torroba_tremolo",
        # The 6/8 pairs.
        ("6/8", "danza", "calm"): "alcaniz",
        ("6/8", "alcaniz", "rally"): "danza",
        ("6/8", "fandanguillo", "volatile"): "danza",
    }
    for (kind, primary, mood), pattern in expected.items():
        assert _contrast(kind, primary, mood) == pattern, (kind, primary, mood)

    # A cell with no row returns the primary id.
    for kind, primary in (
        ("4/4", "torroba_tremolo"),
        ("4/4", "danza"),
        ("3/4", "alcaniz"),
        ("6/8", "castillo"),
        ("6/8", "sonatina"),
        ("6/8", "olite"),
    ):
        assert _contrast(kind, primary, None) == primary, (kind, primary)


def test_missing_contrast_mood_is_the_opening_character() -> None:
    ctx = SimpleNamespace(kind="3/4", character="calm")
    assert _torroba_contrast(ctx, "castillo") == "torroba_tremolo"
    ctx = SimpleNamespace(kind="3/4", character="rally")
    assert _torroba_contrast(ctx, "castillo") == "castillo"


def test_sonatina_is_not_reachable_from_the_primary_map() -> None:
    assert "sonatina" not in {
        _primary(kind, mood) for kind, mood in PRIMARY
    }


def test_every_rule_has_a_reason() -> None:
    assert all(rule.why for rule in TORROBA_PRIMARY_RULES)
    assert all(rule.why for rule in TORROBA_CONTRAST_RULES)
