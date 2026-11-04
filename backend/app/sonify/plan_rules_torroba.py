"""Torroba's plan as one primary table and one contrast table.

Torroba chooses a texture from the meter and the mood, then a separate
contrast step chooses the other texture for the formal area. The two steps are
deliberately two tables:

* `TORROBA_PRIMARY_RULES` is the meter/mood map. The phrase path
  (`_select_body`) and the macro path (`_assign_torroba`) both use it.
* `TORROBA_CONTRAST_RULES` is the pair map. The phrase path calls it for a
  `trio` or `bridge` phrase; the macro path calls it once for the A-B-A
  contrast area.

The two plan scopes do not disagree on the primary id. `framed_macro` is still
carried through the chooser because the two call sites pass it (`False` from
`_select_body`, `True` from the macro path), and the primary rows are
registered under both `Mode`s so a future split has a seam. Today both modes
return the same answer for every input: the old framed-only 6/8 rule was
replaced by the 6/8 mood row below, and the phrase path's 6/8 answer is the
same map. Do not collapse the flag at the call sites; it is what keeps the two
scopes explicit.

The table stays pure and does not pick the mood. Each scope keeps its own
source: `_select_body` passes the mood of the phrase's apex bar,
`_dominant_pattern_auto` passes the body/slot/session majority mood, and
`_assign_torroba` passes the opening region's mood. Moving any of those into
this module would be a behavior change.

The API is `torroba_primary(PrimaryInputs(...))` / `torroba_contrast(...)`,
not `(mode, case)` like Villa or Brouwer: the wrapper keeps its old signature
and derives the mode from `framed_macro`, which the existing call sites already
pass. Do not "fix" this to match the other modules without updating those call
sites and the parity matrix.

What *does* differ by scope is contrast, and it must stay that way:

* The phrase path reads `trio`/`bridge` and answers immediately with
  `torroba_contrast`. Those flags are not inputs to the primary table.
* The macro path does not feed the flags to the primary chooser. `_assign_torroba`
  paints the contrast area with `torroba_contrast`, whether the section carries
  a flag or the body is split into A-B-A by bar count.

The contrast table is shared by both scopes, so its rows carry no `mode`. It
keeps the `castillo` + 4/4, `sonatina` + 4/4, and `sonatina` + 3/4 cells even
though today's primary map never produces those pairs: direct callers and the
golden tests still lock them, and deleting them would be a behavior change.

Unlike Villa, Torroba's choosers do not read `bpm`, `band`, `quiet_majority`,
`first_body`, or the hold/running predicates. Tempo and meter are retargeted
before the plan runs, so the table only needs `kind` and `mood`. The band and
the row are still recorded by the parity fixture because a retarget or a
dispatch change can move them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.sonify.plan_rules import MACRO, PHRASE, Mode, Rule

_FAST_THREE_FOUR = frozenset({"rally", "selloff", "volatile"})


@dataclass(frozen=True)
class PrimaryInputs:
    """Everything the primary ladder can read. `framed_macro` picks the mode."""

    kind: str
    mood: str | None
    framed_macro: bool


@dataclass(frozen=True)
class ContrastInputs:
    """Everything the contrast ladder can read. Both scopes share it.

    `mood` must already be resolved: `None` means unknown here, not "use the
    opening character". `_torroba_contrast` performs that resolution before
    building the input.
    """

    kind: str
    primary: str
    mood: str | None


@dataclass(frozen=True)
class ContrastRule:
    """One contrast decision: `when` -> `pattern`, with the reason as data.

    The generic `Rule` carries a phrase/macro `mode`; contrast is shared by
    both scopes, so it does not belong to either one.
    """

    when: Callable[[ContrastInputs], bool]
    pattern: str
    why: str


_LADDER: tuple[tuple[Callable[[PrimaryInputs], bool], str, str], ...] = (
    # The early 3/4 guard. Calm, a missing mood, and every mood outside the
    # fast set stay Castillo at every tempo; the old `bpm > 72` Sonatina gate
    # is gone because the Juglar density follows the tempo by itself.
    (
        lambda case: case.kind == "3/4" and case.mood not in _FAST_THREE_FOUR,
        "castillo",
        "a 3/4 body outside the fast moods keeps Castillo",
    ),
    # The 4/4 row. Only rally and volatile are named; a calm or selloff has
    # already been retargeted to 3/4, so a 4/4 calm that still arrives is Olite.
    (
        lambda case: case.kind == "4/4" and case.mood == "rally",
        "olite",
        "a 4/4 rally body is Olite, not Sonatina",
    ),
    (
        lambda case: case.kind == "4/4" and case.mood == "volatile",
        "olite",
        "a 4/4 volatile body is Olite",
    ),
    # The 3/4 fast cells.
    (
        lambda case: case.kind == "3/4" and case.mood == "rally",
        "torroba_tremolo",
        "a 3/4 rally body sings Juglar",
    ),
    (
        lambda case: case.kind == "3/4" and case.mood == "selloff",
        "castillo",
        "a 3/4 selloff body stays Castillo",
    ),
    (
        lambda case: case.kind == "3/4" and case.mood == "volatile",
        "danza",
        "a 3/4 volatile body is Danza",
    ),
    # The 6/8 row. Calm is named and is also the fallback for a missing or
    # unknown mood, so Danza is the default scherzo.
    (
        lambda case: case.kind == "6/8" and case.mood == "calm",
        "danza",
        "a 6/8 calm body is Danza",
    ),
    (
        lambda case: case.kind == "6/8" and case.mood == "rally",
        "alcaniz",
        "a 6/8 rally body is Alcaniz",
    ),
    (
        lambda case: case.kind == "6/8" and case.mood == "volatile",
        "fandanguillo",
        "a 6/8 volatile body is Fandanguillo",
    ),
    (
        lambda case: case.kind == "6/8" and case.mood == "selloff",
        "fandanguillo",
        "a 6/8 selloff body is Fandanguillo",
    ),
    (
        lambda case: case.kind == "6/8",
        "danza",
        "the 6/8 row falls back to its calm cell, Danza",
    ),
)

TORROBA_PRIMARY_RULES: tuple[Rule, ...] = tuple(
    Rule(mode, when, pattern, why)
    for mode in (PHRASE, MACRO)
    for when, pattern, why in _LADDER
)

TORROBA_PRIMARY_FALLBACK: dict[Mode, str] = {PHRASE: "olite", MACRO: "olite"}

TORROBA_CONTRAST_RULES: tuple[ContrastRule, ...] = (
    ContrastRule(
        lambda case: case.primary == "castillo" and case.kind == "4/4",
        "olite",
        "a 4/4 Castillo answers with Olite",
    ),
    ContrastRule(
        lambda case: (
            case.primary == "castillo" and case.kind == "3/4" and case.mood == "calm"
        ),
        "torroba_tremolo",
        "a calm 3/4 Castillo answers with Juglar",
    ),
    ContrastRule(
        lambda case: (
            case.primary == "castillo" and case.kind == "3/4" and case.mood == "selloff"
        ),
        "danza",
        "a 3/4 selloff Castillo answers with Danza",
    ),
    ContrastRule(
        lambda case: case.primary == "olite" and case.kind == "4/4",
        "castillo",
        "a 4/4 Olite answers with Castillo, not Sonatina",
    ),
    ContrastRule(
        lambda case: case.primary == "sonatina" and case.kind == "4/4",
        "castillo",
        "a 4/4 Sonatina answers with Castillo",
    ),
    ContrastRule(
        lambda case: case.primary == "sonatina" and case.kind == "3/4",
        "castillo",
        "a 3/4 Sonatina answers with Castillo",
    ),
    ContrastRule(
        lambda case: case.primary == "torroba_tremolo" and case.kind == "3/4",
        "danza",
        "a 3/4 Juglar answers with Danza",
    ),
    ContrastRule(
        lambda case: case.primary == "danza" and case.kind == "3/4",
        "torroba_tremolo",
        "a 3/4 Danza answers with Juglar",
    ),
    ContrastRule(
        lambda case: case.primary == "danza" and case.kind == "6/8",
        "alcaniz",
        "a 6/8 Danza answers with Alcaniz",
    ),
    ContrastRule(
        lambda case: case.primary == "alcaniz" and case.kind == "6/8",
        "danza",
        "a 6/8 Alcaniz answers with Danza",
    ),
    ContrastRule(
        lambda case: case.primary == "fandanguillo" and case.kind == "6/8",
        "danza",
        "a 6/8 Fandanguillo answers with Danza",
    ),
)


def _primary_mode(framed_macro: bool) -> Mode:
    return MACRO if framed_macro else PHRASE


def torroba_primary(case: PrimaryInputs) -> str:
    """First primary rule for the requested scope, else that scope's fallback."""
    mode = _primary_mode(case.framed_macro)
    for rule in TORROBA_PRIMARY_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return TORROBA_PRIMARY_FALLBACK[mode]


def torroba_contrast(case: ContrastInputs) -> str:
    """First contrast rule that matches, else the primary id (no contrast cell)."""
    for rule in TORROBA_CONTRAST_RULES:
        if rule.when(case):
            return rule.pattern
    return case.primary
