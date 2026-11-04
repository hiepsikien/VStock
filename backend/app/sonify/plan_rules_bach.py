"""Bach's plan ladders as ordered rule tables.

Bach has one primary menu, reached from both documented plan scopes:

* `phrase` -- `_select_body`, one dance per phrase of an unframed movement.
* `macro` -- `_dominant_pattern_auto`, one dance for a whole body, formal
  slot, or weekly session of a framed movement.

Unlike Villa, the two scopes do not disagree on purpose. They call the same
chooser with different aggregations: the phrase scope passes one phrase and one
bar, the macro scope passes a region's phrases and bars. The split that really
matters is `framed`, which is an input, not a scope. Each decision is therefore
projected into both modes so `Rule.mode` still keeps the paths apart and a
future scope-specific rule has a place to live without changing the shape of
the table. The fallback is the Bourrée for both modes.

Three nested ladders from the old code are flattened into this one ordered
table, and the first matching rule wins:

* the unframed scheduler (`_bach_unframed_primary`),
* the framed menu (`_bach_framed_primary`), including the 1D daily
  fingerprint and the 4/4 suite finale,
* every branch of those two, in their original order.

The region row is a separate post-pass (`bach_region_patterns`): Bach walks
the same opening/guest/reprise row as Barrios, then refuses to close on a
Prelude that follows another dance.

Contrast is a second table. It takes the primary dance already chosen, so it
cannot live in the primary ladder. Both plan scopes use it, with no difference
between them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from app.sonify.plan_rules import MACRO, PHRASE, Mode, Rule

# A selloff at this span or wider is a Chaconne in the slow unframed row.
BACH_CHACONNE_SPAN = 0.016
# The meters the primary ladder knows by name. Any other meter is only reached
# through the empty-material guard or the final Bourrée fallback.
BACH_KINDS = frozenset({"4/4", "3/4", "6/8"})


@dataclass(frozen=True)
class PrimaryInputs:
    """Everything the primary ladder can read. All fields are required.

    The derived flags (`daily`, `finale`, `narrow_or_held`, `wide`, `lively`)
    keep the renderer's existing predicates where they are; this table only
    orders the decisions they feed.
    """

    framed: bool
    daily: bool
    finale: bool
    kind: str
    bpm: int
    mood: str | None
    rel_span: float
    narrow_or_held: bool
    wide: bool
    lively: bool
    has_contrast: bool
    has_material: bool


@dataclass(frozen=True)
class ContrastInputs:
    """Everything the contrast ladder can read. All fields are required."""

    kind: str
    primary: str
    mood: str | None


BachInputs: TypeAlias = PrimaryInputs | ContrastInputs

# (predicate, pattern, why). Order is the rule: first match wins.
_PRIMARY_DECISIONS: tuple[
    tuple[Callable[[PrimaryInputs], bool], str, str], ...
] = (
    (
        lambda case: (
            not case.has_material
            and case.mood is None
            and case.kind not in BACH_KINDS
        ),
        "bach_bourree",
        "nothing to plan on an unknown meter falls back to the Bourrée",
    ),
    # Unframed scheduler.
    (
        lambda case: (
            not case.framed
            and (case.kind == "3/4" or case.bpm <= 72)
            and case.mood == "selloff"
            and case.rel_span >= BACH_CHACONNE_SPAN
            and not case.has_contrast
        ),
        "bach_chaconne",
        "a wide slow selloff without a contrast section is the Chaconne",
    ),
    (
        lambda case: not case.framed and (case.kind == "3/4" or case.bpm <= 72),
        "bach_sarabande",
        "the slow or 3/4 unframed row is the Sarabande",
    ),
    (
        lambda case: not case.framed and case.mood == "volatile",
        "bach_fuga",
        "a volatile unframed phrase is the Fugue",
    ),
    (
        lambda case: not case.framed and case.mood == "selloff",
        "bach_chaconne",
        "a selloff unframed phrase is the Chaconne",
    ),
    (
        lambda case: not case.framed and case.kind == "6/8",
        "bach_gigue",
        "6/8 unframed is the Gigue",
    ),
    (
        lambda case: not case.framed and case.mood == "calm",
        "bach_gavotte",
        "a calm unframed phrase is the Gavotte",
    ),
    (
        lambda case: not case.framed,
        "bach_bourree",
        "the unframed row otherwise stays the Bourrée",
    ),
    # Framed 1D daily fingerprint: 34 bars, 96 BPM, 4/4.
    (
        lambda case: case.framed and case.daily and case.mood == "volatile",
        "bach_fuga",
        "the daily fingerprint answers volatility with the Fugue",
    ),
    (
        lambda case: case.framed and case.daily and case.mood == "selloff",
        "bach_chaconne",
        "the daily fingerprint answers a selloff with the Chaconne",
    ),
    (
        lambda case: (
            case.framed and case.daily and case.mood == "calm" and case.narrow_or_held
        ),
        "bach_prelude",
        "a calm, narrow or held daily line keeps the Prelude",
    ),
    (
        lambda case: case.framed and case.daily and case.mood == "calm",
        "bach_allemande",
        "a calm daily line with room to move is the Allemande",
    ),
    (
        lambda case: case.framed and case.daily and not case.wide,
        "bach_bourree",
        "a daily line under the wide mark stays the Bourrée",
    ),
    (
        lambda case: case.framed and case.daily and case.lively,
        "bach_courante",
        "a wide, lively daily line is the Courante",
    ),
    (
        lambda case: case.framed and case.daily,
        "bach_gavotte",
        "a wide daily line that is not lively is the Gavotte",
    ),
    # Framed 4/4 suite finale.
    (
        lambda case: (
            case.framed
            and case.finale
            and case.kind == "4/4"
            and case.mood == "volatile"
        ),
        "bach_fuga",
        "a volatile 4/4 finale is the Fugue",
    ),
    (
        lambda case: (
            case.framed
            and case.finale
            and case.kind == "4/4"
            and case.mood == "selloff"
        ),
        "bach_chaconne",
        "a selloff 4/4 finale is the Chaconne",
    ),
    (
        lambda case: (
            case.framed
            and case.finale
            and case.kind == "4/4"
            and case.mood == "calm"
        ),
        "bach_gavotte",
        "a calm 4/4 finale is the Gavotte",
    ),
    (
        lambda case: case.framed and case.finale and case.kind == "4/4",
        "bach_bourree",
        "the 4/4 finale menu otherwise stays the Bourrée",
    ),
    # Framed 6/8.
    (
        lambda case: (
            case.framed and case.kind == "6/8" and case.mood == "volatile"
        ),
        "bach_fuga",
        "a volatile 6/8 body is the Fugue",
    ),
    (
        lambda case: case.framed and case.kind == "6/8" and case.mood == "selloff",
        "bach_chaconne",
        "a selloff 6/8 body is the Chaconne",
    ),
    (
        lambda case: case.framed and case.kind == "6/8" and case.mood == "calm",
        "bach_courante",
        "a calm 6/8 body is the Courante",
    ),
    (
        lambda case: case.framed and case.kind == "6/8",
        "bach_gigue",
        "the 6/8 row otherwise stays the Gigue",
    ),
    # Framed 4/4.
    (
        lambda case: (
            case.framed and case.kind == "4/4" and case.mood == "volatile"
        ),
        "bach_fuga",
        "a volatile 4/4 body is the Fugue",
    ),
    (
        lambda case: case.framed and case.kind == "4/4" and case.mood == "selloff",
        "bach_chaconne",
        "a selloff 4/4 body is the Chaconne",
    ),
    (
        lambda case: (
            case.framed
            and case.kind == "4/4"
            and case.mood == "calm"
            and case.narrow_or_held
        ),
        "bach_prelude",
        "a calm, narrow or held 4/4 body keeps the Prelude",
    ),
    (
        lambda case: case.framed and case.kind == "4/4" and case.mood == "calm",
        "bach_allemande",
        "a calm 4/4 body with room to move is the Allemande",
    ),
    (
        lambda case: case.framed and case.kind == "4/4" and case.wide,
        "bach_bourree",
        "a wide 4/4 body is the Bourrée",
    ),
    (
        lambda case: case.framed and case.kind == "4/4",
        "bach_allemande",
        "the other 4/4 bodies are the Allemande",
    ),
    (
        lambda case: case.framed and (case.kind == "3/4" or case.bpm <= 72),
        "bach_sarabande",
        "a slow or 3/4 framed body is the Sarabande",
    ),
    (
        lambda case: case.framed,
        "bach_bourree",
        "the framed fallback is the Bourrée",
    ),
)

_CONTRAST_DECISIONS: tuple[
    tuple[Callable[[ContrastInputs], bool], str, str], ...
] = (
    (
        lambda case: case.primary == "bach_prelude",
        "bach_allemande",
        "a Prelude trio or bridge answers with the Allemande",
    ),
    (
        lambda case: case.primary == "bach_allemande",
        "bach_courante",
        "an Allemande trio or bridge answers with the Courante",
    ),
    (
        lambda case: case.primary == "bach_courante",
        "bach_gigue",
        "a Courante trio or bridge answers with the Gigue",
    ),
    (
        lambda case: (
            (case.kind == "6/8" or case.primary == "bach_gigue")
            and case.mood == "calm"
        ),
        "bach_bourree",
        "a calm 6/8 or Gigue contrast returns to the Bourrée",
    ),
    (
        lambda case: case.kind == "6/8" or case.primary == "bach_gigue",
        "bach_fuga",
        "the other 6/8 or Gigue contrast is the Fugue",
    ),
    (
        lambda case: case.kind == "3/4" or case.primary == "bach_sarabande",
        "bach_chaconne",
        "a 3/4 or Sarabande contrast is the Chaconne",
    ),
    (
        lambda case: case.primary in {"bach_bourree", "bach_gavotte"},
        "bach_fuga",
        "a Bourrée or Gavotte contrast is the Fugue",
    ),
    (
        lambda case: case.primary in {"bach_fuga", "bach_chaconne"} and case.mood == "rally",
        "bach_bourree",
        "a rally Fugue or Chaconne contrast returns to the Bourrée",
    ),
    (
        lambda case: case.primary in {"bach_fuga", "bach_chaconne"},
        "bach_gavotte",
        "the other Fugue or Chaconne contrast is the Gavotte",
    ),
    (
        lambda case: True,
        "bach_bourree",
        "the contrast fallback is the Bourrée",
    ),
)


def _project(
    decisions: tuple[tuple[Callable, str, str], ...],
) -> tuple[Rule, ...]:
    """One ordered table carrying both scope modes.

    Bach's phrase and macro scopes share every decision, so each row is
    projected into both modes instead of pretending they differ.
    """
    return tuple(
        Rule(mode, when, pattern, why)
        for mode in (PHRASE, MACRO)
        for when, pattern, why in decisions
    )


BACH_RULES: tuple[Rule, ...] = _project(_PRIMARY_DECISIONS)
BACH_CONTRAST_RULES: tuple[Rule, ...] = _project(_CONTRAST_DECISIONS)

BACH_FALLBACK: dict[Mode, str] = {PHRASE: "bach_bourree", MACRO: "bach_bourree"}
BACH_CONTRAST_FALLBACK: dict[Mode, str] = {
    PHRASE: "bach_bourree",
    MACRO: "bach_bourree",
}


def bach_pattern(mode: Mode, case: PrimaryInputs) -> str:
    """First primary rule for `mode` that matches, else that mode's fallback."""
    if not isinstance(case, PrimaryInputs):
        raise TypeError(
            f"primary Bach rules need PrimaryInputs, got {type(case).__name__}"
        )
    for rule in BACH_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return BACH_FALLBACK[mode]


def bach_contrast(mode: Mode, case: ContrastInputs) -> str:
    """First contrast rule for `mode` that matches, else the Bourrée."""
    if not isinstance(case, ContrastInputs):
        raise TypeError(
            f"contrast Bach rules need ContrastInputs, got {type(case).__name__}"
        )
    for rule in BACH_CONTRAST_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return BACH_CONTRAST_FALLBACK[mode]


def bach_region_patterns(row: list[str]) -> list[str]:
    """Bach's suite-row close: never end on a Prelude that follows a dance.

    Barrios still returns to its opening. Bach does too, except when that
    return would put Prelude last in a row that already has another dance.
    The close then repeats the dance already playing in front of it. A
    two-part row has no reprise, so Sarabande -- Prelude stays.
    """
    if (
        len(row) >= 3
        and row[-1] == "bach_prelude"
        and any(item != "bach_prelude" for item in row[:-1])
    ):
        row[-1] = row[-2]
    return row
