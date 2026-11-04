"""Villa's two plan ladders, as one ordered rule table.

Villa has two documented plan scopes, and they are deliberately not the same
ladder:

* `phrase` -- `_select_body`, one pattern per phrase of an unframed movement.
* `macro` -- `_dominant_pattern_auto`, one pattern for a whole body, formal
  slot, or weekly session of a framed movement.

The tables below are ordered: the first matching rule wins. `mode` keeps the
two paths apart, so a rule that belongs to the phrase path can never leak into
the macro path (or the other way around). The difference is documented in the
model doc section 6: an unframed movement chooses per phrase, a framed movement
chooses once and resolves trio/bridge contrast through `_assign_macro` and
`_contrast_pattern`.

The two ladders disagree on purpose for the same raw inputs, and neither
should be unified:

* A trio or bridge sings on the thumb in the phrase path. The macro path does
  not read that flag; `_assign_macro` paints the contrast area with
  `_contrast_pattern` instead, so the primary chooser must not pre-empt it.
* A single `p` bar is enough for the phrase path. The macro path asks for a
  quiet majority of the body.
* `first_body` belongs to the phrase path only, where the opening body phrase
  stays the eighth-note roll below the tremolo floor. The macro path applies
  the etude rules to the whole body, opening phrase included.

`trio`/`bridge` are carried by `VillaInputs` for the phrase rules. The macro
rules ignore them by design (see above), and `_dominant_pattern_auto` is only
called for non-contrast material.

Villa never reads `_has_hold` or `_running`; those predicates feed the Barrios
branches of `_select_body`, so they are not inputs to this table.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.sonify.guitar import BARRIOS_TREMOLO_MIN_BPM

PHRASE = "phrase"
MACRO = "macro"


@dataclass(frozen=True)
class VillaInputs:
    """Everything either Villa ladder can read. Unused fields keep their default."""

    trio: bool = False
    bridge: bool = False
    mood: str | None = None
    bpm: int = 0
    band: str = "mf"
    first_body: bool = False
    kind: str = "4/4"
    quiet_majority: bool = False


@dataclass(frozen=True)
class Rule:
    """One ordered decision: `when` -> `pattern`, with the reason kept as data."""

    mode: str
    when: Callable[[VillaInputs], bool]
    pattern: str
    why: str


VILLA_RULES: tuple[Rule, ...] = (
    # Phrase path. This first rule is the shared opening-body rule that
    # `_select_body` used to apply before dispatching to Villa: above the
    # tremolo floor the opening body phrase stays the eighth-note roll.
    Rule(
        PHRASE,
        lambda case: case.first_body and case.bpm >= BARRIOS_TREMOLO_MIN_BPM,
        "villa_pattern",
        "the opening body phrase stays the eighth-note roll",
    ),
    Rule(
        PHRASE,
        lambda case: case.trio or case.bridge or case.mood == "selloff",
        "thumb_cantabile",
        "a trio, bridge, or selloff sings on the thumb",
    ),
    Rule(
        PHRASE,
        lambda case: case.bpm <= 72 or case.band == "p" or case.mood == "calm",
        "chord_melody",
        "slow, quiet, or calm phrases keep the block chords",
    ),
    Rule(
        PHRASE,
        lambda case: (
            not case.first_body
            and case.kind == "4/4"
            and case.bpm > 72
            and case.mood == "rally"
        ),
        "etude1",
        "an interior 4/4 rally phrase takes Etude 1",
    ),
    Rule(
        PHRASE,
        lambda case: (
            not case.first_body
            and case.kind == "4/4"
            and case.bpm > 72
            and case.mood == "volatile"
        ),
        "etude11",
        "an interior 4/4 volatile phrase takes Etude 11",
    ),
    # Macro path. Contrast is not answered here; `_assign_macro` does it.
    Rule(
        MACRO,
        lambda case: case.mood == "selloff",
        "thumb_cantabile",
        "a selloff body sings Prelude No. 1 on the thumb",
    ),
    Rule(
        MACRO,
        lambda case: case.bpm <= 72,
        "chord_melody",
        "a slow body keeps the block chords",
    ),
    Rule(
        MACRO,
        lambda case: case.mood == "calm" or case.quiet_majority,
        "chord_melody",
        "a calm or quiet-majority body keeps the block chords",
    ),
    Rule(
        MACRO,
        lambda case: case.kind == "6/8",
        "villa_pattern",
        "6/8 stays the eighth-note roll for every mood",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.kind == "4/4" and case.bpm > 72 and case.mood == "rally"
        ),
        "etude1",
        "a 4/4 rally body locks Etude 1 across the whole body",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.kind == "4/4" and case.bpm > 72 and case.mood == "volatile"
        ),
        "etude11",
        "a 4/4 volatile body locks Etude 11 across the whole body",
    ),
)

VILLA_FALLBACK = {PHRASE: "villa_pattern", MACRO: "villa_pattern"}


def villa_pattern(mode: str, case: VillaInputs) -> str:
    """First rule for `mode` that matches, else that mode's fallback row."""
    for rule in VILLA_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return VILLA_FALLBACK[mode]
