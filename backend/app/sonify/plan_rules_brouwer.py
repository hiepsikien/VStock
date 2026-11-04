"""Brouwer's plan ladder, as one ordered rule table.

Brouwer has the same two documented plan scopes as Villa:

* `phrase` -- `_select_body`, one pattern per phrase of an unframed movement.
* `macro` -- `_dominant_pattern_auto`, one pattern for a whole body, formal
  slot, or weekly session of a framed movement.

Both scopes ask the same question -- which primary texture is this? -- and read
exactly two inputs: the mood at the decision point and the tempo. They differ
only in where the mood comes from: the phrase path reads the apex bar of the
phrase, the macro path reads the majority mood of the body or slot. The ordered
ladder below is therefore the same row list for both modes, materialised once
per mode so a future rule can diverge without leaking into the other scope.
The two ladders agree today for every raw input; that is not a reason to
collapse them, because the mood source and the contrast step stay different.

Contrast is deliberately not in this table:

* The phrase path chooses a primary first and then answers a trio or bridge
  with `_brouwer_contrast` inside `_select_body`.
* The macro path never reads trio/bridge here; `_assign_macro` paints those
  areas through `_contrast_pattern`, which calls `_brouwer_contrast`.

Putting contrast in the primary table would pre-empt both steps. `band`, meter
(`kind`), and phrase shape are absent for the same reason: the Brouwer primary
never reads them, and the parity matrix shows they cannot change the row.

`brouwer_pattern` refuses an input type that does not match its mode. Today
both modes share `BrouwerInputs`, so the guard only catches a Villa or other
ensemble record smuggled in; if a mode grows its own fields, give it its own
dataclass and the guard becomes strict.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.sonify.plan_rules import MACRO, PHRASE, Mode, Rule


@dataclass(frozen=True)
class BrouwerInputs:
    """Everything the Brouwer primary ladder can read. All fields are required."""

    mood: str | None
    bpm: int


# Ordered: the first matching rule wins. The shared row list is materialised
# for both modes below, so a mode-specific rule must be added explicitly.
_LADDER: tuple[tuple[Callable[[BrouwerInputs], bool], str, str], ...] = (
    (
        lambda case: case.mood == "calm",
        "noviembre",
        "a calm phrase or body keeps the November ballad",
    ),
    (
        lambda case: case.mood == "selloff" or case.bpm <= 72,
        "sarabande",
        "a selloff or slow phrase or body takes the Sarabande",
    ),
    (
        lambda case: case.mood == "volatile",
        "elogio_pizz",
        "a volatile phrase or body takes the Elogio pizzicato",
    ),
)

BROUWER_RULES: tuple[Rule, ...] = tuple(
    Rule(mode, when, pattern, why)
    for mode in (PHRASE, MACRO)
    for when, pattern, why in _LADDER
)

BROUWER_FALLBACK: dict[Mode, str] = {
    PHRASE: "brouwer_etude",
    MACRO: "brouwer_etude",
}

_INPUTS: dict[Mode, type] = {PHRASE: BrouwerInputs, MACRO: BrouwerInputs}


def brouwer_pattern(mode: Mode, case: BrouwerInputs) -> str:
    """First rule for `mode` that matches, else that mode's fallback row.

    The input type must match the mode, so a record from another ensemble (or a
    future per-mode record) cannot be read as the wrong ladder.
    """
    expected = _INPUTS[mode]
    if not isinstance(case, expected):
        raise TypeError(
            f"{mode} needs {expected.__name__}, got {type(case).__name__}"
        )
    for rule in BROUWER_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return BROUWER_FALLBACK[mode]
