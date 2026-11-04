"""Intent lock for the three Barrios ladders.

The golden matrix in `test_plan_barrios_parity.py` is the end-to-end lock.
These tests are the fast, direct statement of why the phrase, macro, and
palette tables stay separate.
"""

from __future__ import annotations

from dataclasses import fields

from app.sonify.plan_rules import MACRO, PHRASE
from app.sonify.plan_rules_barrios import (
    BARRIOS_FALLBACK,
    BARRIOS_PALETTE_FALLBACK,
    BARRIOS_PALETTE_RULES,
    BARRIOS_RULES,
    DAILY,
    BarriosMacroInputs,
    BarriosPaletteInputs,
    BarriosPhraseInputs,
    barrios_palette,
    barrios_pattern,
)


def _phrase(**overrides) -> BarriosPhraseInputs:
    values = dict(
        trio=False,
        bridge=False,
        mood=None,
        bpm=100,
        band="mf",
        first_body=False,
        kind="4/4",
        hold=False,
        running=False,
        previous=(),
    )
    values.update(overrides)
    return BarriosPhraseInputs(**values)


def _macro(**overrides) -> BarriosMacroInputs:
    values = dict(
        mood=None,
        bpm=100,
        kind="4/4",
        bars=96,
        framed=True,
        suite_finale=False,
        forte_majority=False,
        phrase_count=4,
        hold_count=0,
        running_count=0,
    )
    values.update(overrides)
    return BarriosMacroInputs(**values)


def _palette(primary: str, **overrides) -> tuple[str, ...]:
    values = dict(bpm=120, kind="4/4", primary=primary)
    values.update(overrides)
    return barrios_palette(BarriosPaletteInputs(**values))


def test_the_opening_body_phrase_stays_the_preludio() -> None:
    # Above the tremolo floor the opening body phrase is always the arpeggio,
    # even for a rally or a held line.
    for bpm in (90, 120):
        assert (
            barrios_pattern(
                PHRASE, _phrase(first_body=True, bpm=bpm, mood="rally", hold=True)
            )
            == "preludio"
        )

    # An interior running rally phrase takes the choro instead.
    assert (
        barrios_pattern(
            PHRASE, _phrase(first_body=False, bpm=120, mood="rally", running=True)
        )
        == "choro"
    )


def test_a_held_phrase_sings_tremolo_and_two_in_a_row_fall_back() -> None:
    assert barrios_pattern(PHRASE, _phrase(hold=True, bpm=120)) == "tremolo"
    assert (
        barrios_pattern(
            PHRASE, _phrase(hold=True, bpm=120, previous=("preludio", "tremolo", "tremolo"))
        )
        == "andante"
    )
    assert (
        barrios_pattern(
            PHRASE,
            _phrase(
                hold=True,
                bpm=120,
                trio=True,
                previous=("preludio", "tremolo", "tremolo"),
            ),
        )
        == "thumb_cantabile"
    )

    # The held window is 90-140. Below it the slow row answers; above it the
    # phrase falls through to the arpeggio.
    assert barrios_pattern(PHRASE, _phrase(hold=True, bpm=89)) == "andante"
    assert barrios_pattern(PHRASE, _phrase(hold=True, bpm=140)) == "tremolo"
    assert barrios_pattern(PHRASE, _phrase(hold=True, bpm=141)) == "preludio"


def test_a_slow_bridge_sings_on_the_thumb_but_a_slow_trio_does_not() -> None:
    # The slow row reads only the bridge flag; a slow trio keeps the chorale.
    assert barrios_pattern(PHRASE, _phrase(bpm=72, bridge=True)) == "thumb_cantabile"
    assert barrios_pattern(PHRASE, _phrase(bpm=72, trio=True)) == "andante"
    assert barrios_pattern(PHRASE, _phrase(bpm=72)) == "andante"


def test_the_phrase_ladder_reads_the_apex_band() -> None:
    dance = dict(mood="rally", bpm=120, running=True, kind="6/8")
    assert barrios_pattern(PHRASE, _phrase(**dance, band="p")) == "polca"
    assert barrios_pattern(PHRASE, _phrase(**dance, band="mf")) == "polca"
    assert barrios_pattern(PHRASE, _phrase(**dance, band="f")) == "hemiola"
    # The trio rule sits above the band rule.
    assert barrios_pattern(PHRASE, _phrase(**dance, band="f", trio=True)) == "vals"
    # The dance row needs a tempo above 100.
    assert barrios_pattern(PHRASE, _phrase(**{**dance, "bpm": 100})) == "preludio"
    # A calm running trio sings on the thumb above the floor.
    assert (
        barrios_pattern(
            PHRASE, _phrase(mood="calm", bpm=120, running=True, trio=True)
        )
        == "thumb_cantabile"
    )


def test_the_macro_ladder_applies_its_rows_to_the_opening_too() -> None:
    # There is no first_body field on the macro inputs: the body rule applies
    # to the opening phrase as well.
    macro_fields = {field.name for field in fields(BarriosMacroInputs)}
    assert "first_body" not in macro_fields
    assert "band" not in macro_fields
    assert "hold" not in macro_fields
    assert "running" not in macro_fields
    assert "previous" not in macro_fields
    assert barrios_pattern(MACRO, _macro(bpm=120, mood="rally")) == "preludio"


def test_the_slow_body_walks_the_chorale() -> None:
    for mood in (None, "calm", "rally", "selloff", "volatile"):
        assert (
            barrios_pattern(MACRO, _macro(bpm=89, mood=mood, hold_count=2))
            == "andante"
        )
        assert barrios_pattern(MACRO, _macro(bpm=72, mood=mood)) == "andante"


def test_the_moderato_four_four_row_needs_the_frame_and_the_finale() -> None:
    moderato = dict(bpm=96, kind="4/4", mood="rally")
    assert barrios_pattern(MACRO, _macro(**moderato)) == "preludio"
    assert (
        barrios_pattern(MACRO, _macro(**moderato, suite_finale=True)) == "tremolo"
    )
    assert (
        barrios_pattern(MACRO, _macro(**{**moderato, "mood": "selloff"})) == "tremolo"
    )
    assert (
        barrios_pattern(MACRO, _macro(**{**moderato, "mood": "volatile"})) == "tremolo"
    )
    # The rule is framed-only: an unframed body at the same tempo falls back
    # to the quiet rows instead of taking the moderato opening.
    assert barrios_pattern(MACRO, _macro(**moderato, framed=False)) == "preludio"


def test_a_calm_body_keeps_the_preludio_even_with_holds() -> None:
    assert (
        barrios_pattern(MACRO, _macro(bpm=120, mood="calm", hold_count=4))
        == "preludio"
    )


def test_the_long_six_eight_row_reads_a_forte_majority() -> None:
    long = dict(kind="6/8", bpm=120, bars=108, mood="rally")
    assert barrios_pattern(MACRO, _macro(**long, forte_majority=True)) == "hemiola"
    assert barrios_pattern(MACRO, _macro(**long, forte_majority=False)) == "polca"
    # A short 6/8 body never reaches that row.
    assert (
        barrios_pattern(MACRO, _macro(**{**long, "bars": 40}, forte_majority=True))
        == "preludio"
    )


def test_the_daily_body_is_a_sentinel_not_an_id() -> None:
    # Unreachable in production: _assign_macro intercepts the 34-bar 1D body
    # before _dominant_pattern_auto. Kept because the old ladder had this row.
    assert barrios_pattern(MACRO, _macro(bpm=120, bars=34, kind="4/4")) == DAILY
    # The fingerprint is the 120/34/4/4 body, not the meter alone.
    assert barrios_pattern(MACRO, _macro(bpm=120, bars=34, kind="6/8")) != DAILY
    assert barrios_pattern(MACRO, _macro(bpm=120, bars=32, kind="4/4")) != DAILY
    assert barrios_pattern(MACRO, _macro(bpm=100, bars=34, kind="4/4")) != DAILY
    # The phrase ladder never returns the sentinel.
    for bpm in (72, 90, 120):
        assert barrios_pattern(PHRASE, _phrase(bpm=bpm)) != DAILY


def test_held_and_running_majorities_stay_apart() -> None:
    # A held third of the body is enough; a single held phrase needs a
    # rally or selloff mood.
    assert barrios_pattern(MACRO, _macro(bpm=120, hold_count=2)) == "tremolo"
    assert barrios_pattern(MACRO, _macro(bpm=120, hold_count=1)) == "tremolo"
    assert (
        barrios_pattern(MACRO, _macro(bpm=120, hold_count=1, mood="rally"))
        == "tremolo"
    )
    # A running majority only wins for rally/volatile above 100, in the
    # dance meters.
    running = dict(bpm=120, mood="rally", running_count=3)
    assert barrios_pattern(MACRO, _macro(**running, kind="4/4")) == "choro"
    assert barrios_pattern(MACRO, _macro(**running, kind="6/8")) == "polca"
    assert barrios_pattern(MACRO, _macro(**running, kind="3/4")) == "preludio"
    assert (
        barrios_pattern(MACRO, _macro(**{**running, "bpm": 100})) == "preludio"
    )
    assert (
        barrios_pattern(MACRO, _macro(**{**running, "mood": "calm"})) == "preludio"
    )


def test_the_palette_rows_are_the_recorded_ones() -> None:
    assert _palette("tremolo") == ("tremolo", "choro", "thumb_cantabile")
    assert _palette("preludio") == ("preludio", "choro", "andante")
    assert _palette("choro") == ("choro", "thumb_cantabile", "andante")

    # 6/8 at >100.
    assert _palette("hemiola", kind="6/8") == (
        "hemiola",
        "vals",
        "polca",
        "tremolo",
    )
    assert _palette("preludio", kind="6/8") == ("preludio", "thumb_cantabile", "vals")
    assert _palette("polca", kind="6/8") == ("polca", "vals", "hemiola", "tremolo")

    # 4/4 at 90-100 reads only the tremolo opening.
    assert _palette("tremolo", bpm=96) == ("tremolo", "andante")
    assert _palette("preludio", bpm=96) == ("preludio", "andante")

    # Below the tremolo floor every opening walks the slow row.
    assert _palette("tremolo", bpm=72) == (
        "tremolo",
        "andante",
        "thumb_cantabile",
    )
    assert _palette("andante", bpm=72) == ("andante", "thumb_cantabile")

    # A meter outside 4/4 and 6/8 uses the 4/4 tempo gate, then the tremolo
    # row, then the preludio row.
    assert _palette("tremolo", kind="3/4") == ("tremolo", "andante")
    assert _palette("polca", kind="3/4") == ("polca", "preludio", "andante")


def test_the_palette_rotates_the_opening_to_the_front() -> None:
    # The row's opening pattern is the only mood decision. Later slots walk
    # the guests from wherever the opening sits.
    assert _palette("vals", kind="6/8") == ("vals", "hemiola", "tremolo", "polca")
    assert _palette("andante", kind="6/8") == (
        "andante",
        "polca",
        "vals",
        "hemiola",
        "tremolo",
    )


def test_input_type_must_match_the_mode() -> None:
    try:
        barrios_pattern(MACRO, _phrase())
    except TypeError as error:
        assert "BarriosMacroInputs" in str(error)
    else:  # pragma: no cover - the guard is the point of this test
        raise AssertionError("a phrase input must not pass as a macro input")

    try:
        barrios_pattern(PHRASE, _macro())
    except TypeError as error:
        assert "BarriosPhraseInputs" in str(error)
    else:  # pragma: no cover
        raise AssertionError("a macro input must not pass as a phrase input")


def test_every_rule_belongs_to_one_mode_and_has_a_reason() -> None:
    assert {rule.mode for rule in BARRIOS_RULES} == {PHRASE, MACRO}
    assert all(rule.why for rule in BARRIOS_RULES)
    assert all(rule.why for rule in BARRIOS_PALETTE_RULES)
    assert BARRIOS_FALLBACK == {PHRASE: "preludio", MACRO: "preludio"}
    assert BARRIOS_PALETTE_FALLBACK == ("preludio", "andante")
