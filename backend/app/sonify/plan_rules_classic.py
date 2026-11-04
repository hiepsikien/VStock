"""Classic's two plan ladders, as one ordered rule table.

Classic has the same two documented plan scopes as Villa, but the ladders are
not the same shape:

* `phrase` -- `_select_body`, one pattern per phrase of an unframed movement.
* `macro` -- `_dominant_pattern_auto` -> `_classic_macro`, one pattern for a
  whole body, formal slot, or weekly session of a framed movement.

The tables are ordered: the first matching rule wins. `mode` keeps the two
paths apart, so a phrase rule can never leak into the macro path (or the other
way around). The difference is the one documented in the model doc section 6:
an unframed movement chooses per phrase, a framed movement chooses once and
resolves trio/bridge contrast through `_assign_macro` and `_contrast_pattern`.

The two ladders disagree on purpose for the same raw inputs, and neither
should be unified:

* The phrase path reads `trio` only together with the minor mode: a minor trio
  holds the elegy. The macro path never reads `trio` or `bridge`; the formal
  contrast is painted by `_contrast_pattern`, so the primary chooser must not
  pre-empt it.
* The phrase path never dances. The rally galop belongs to the macro path,
  where a wide major body -- or one marked as rally at the bar level -- can
  carry it across a whole movement.
* The opening body above the tremolo floor is a shared `study` branch in
  `_select_body`, above the classic dispatch. The macro path applies the rules
  to the whole body, opening phrase included.

`bridge` is not an input anywhere in classic: the phrase path ignores it, and
the macro path answers it through `_contrast_pattern`. `band` is not an input
either; classic's plan is a mood/tempo decision. The two ladders take different
input types on purpose: a macro rule cannot read `trio` because that field is
not in `ClassicMacroInputs`, and `classic_pattern` refuses an input type that
does not match its mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from app.sonify.plan_rules import MACRO, PHRASE, Mode, Rule


@dataclass(frozen=True)
class ClassicPhraseInputs:
    """Everything the classic phrase ladder can read. All fields are required."""

    trio: bool
    mood: str | None
    bpm: int
    minor: bool


@dataclass(frozen=True)
class ClassicMacroInputs:
    """Everything the classic macro ladder can read. All fields are required."""

    mood: str | None
    bpm: int
    character: str | None
    rel_span: float
    minor: bool
    rally_marked: bool


ClassicInputs: TypeAlias = ClassicPhraseInputs | ClassicMacroInputs

_INPUTS: dict[Mode, type] = {PHRASE: ClassicPhraseInputs, MACRO: ClassicMacroInputs}


CLASSIC_RULES: tuple[Rule, ...] = (
    # Phrase path.
    Rule(
        PHRASE,
        lambda case: (
            case.bpm <= 72 or case.mood == "selloff" or (case.trio and case.minor)
        ),
        "elegiaque",
        "a slow phrase, a selloff, or a minor trio holds the elegy",
    ),
    Rule(
        PHRASE,
        lambda case: case.mood == "calm" and case.bpm > 72,
        "cantabile",
        "a calm phrase above the slow floor sings Cantabile",
    ),
    Rule(
        PHRASE,
        lambda case: case.mood == "volatile",
        "mozart_var",
        "a volatile phrase takes the Mozart variations",
    ),
    # Macro path. Contrast is not answered here; `_assign_macro` does it.
    Rule(
        MACRO,
        lambda case: case.mood == "selloff" or case.bpm <= 72,
        "elegiaque",
        "a selloff or slow body holds the elegy",
    ),
    Rule(
        MACRO,
        lambda case: case.mood == "calm",
        "cantabile",
        "a calm body sings Cantabile",
    ),
    Rule(
        MACRO,
        lambda case: case.mood == "volatile",
        "mozart_var",
        "a volatile body takes the Mozart variations",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.mood == "rally" and case.character is None and not case.rally_marked
        ),
        "study",
        "a character-less rally body that was never marked stays the study",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.mood == "rally" and case.rel_span >= 0.012 and not case.minor
        ),
        "galop",
        "a wide major rally body dances Galop Op. 32 No. 6",
    ),
)

CLASSIC_FALLBACK: dict[Mode, str] = {PHRASE: "study", MACRO: "study"}


def classic_pattern(mode: Mode, case: ClassicInputs) -> str:
    """First rule for `mode` that matches, else that mode's fallback row.

    The input type must match the mode: a macro call cannot smuggle in phrase
    fields, and a phrase call cannot silently default them.
    """
    expected = _INPUTS[mode]
    if not isinstance(case, expected):
        raise TypeError(
            f"{mode} needs {expected.__name__}, got {type(case).__name__}"
        )
    for rule in CLASSIC_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return CLASSIC_FALLBACK[mode]
