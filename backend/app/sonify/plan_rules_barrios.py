"""Barrios' three plan ladders, as ordered rule tables.

Barrios makes its pattern choice at three scopes, and they are deliberately
not one ladder:

* `phrase` -- `_select_body`, one pattern per phrase of an unframed movement.
  The 34-bar 1D body also walks this ladder (see `_assign_macro`), so the
  phrase table is reachable inside a framed movement.
* `macro` -- `_dominant_pattern_auto`, one pattern for a whole body, formal
  slot, or weekly session of a framed movement.
* `palette` -- `_barrios_palette`, the meter row a long (>40 bar) framed
  movement walks: an opening, one guest per middle part, and a reprise from
  the third part. `_barrios_region_patterns` turns the row into one pattern
  per formal slot; it is shared with Bach and stays in `guitar_patterns`.

The tables are ordered: the first matching rule wins. `mode` keeps the phrase
and macro ladders apart, so a rule that belongs to one path cannot leak into
the other. `barrios_pattern` refuses an input type that does not match its
mode, so a macro rule cannot read `hold`, `running`, `band`, or `previous`,
and a phrase rule cannot read the aggregate body counts.

The ladders disagree on purpose for the same raw inputs, and neither should be
unified:

* The phrase ladder answers one phrase at a time and can read the run history
  (`previous`): two tremolo phrases in a row fall back to the andante chorale,
  and a held trio or bridge after that run sings on the thumb. The macro
  ladder sees only aggregate hold/running counts and never the order.
* The phrase ladder reads the apex dynamic band, so a running 6/8 phrase at
  `f` is a hemiola while the same phrase at `p` is a polca. The macro ladder
  reads only a forte majority of the chosen bars, and only in the long 6/8
  row.
* The phrase ladder's slow row is below the tremolo floor (`bpm < 90`). The
  macro ladder's first row is the same floor, but above it the macro ladder
  can lock a whole body to one id, which the phrase ladder never does.
* `first_body` belongs to the phrase ladder only: the opening body phrase
  stays the preludio above the tremolo floor. The macro ladder applies its
  body rules to the opening phrase too.

The 34-bar 1D body is intercepted by `_assign_macro` before this ladder, so
the macro `DAILY` row is unreachable in production: every other 34-bar body
stops at the `bars <= 40` lock. The row is kept because the old ladder had it
and the intent test locks its shape; `_dominant_pattern_auto` would expand the
sentinel through `_daily_barrios_pattern` if it ever appeared. `DAILY` is not
a pattern id and never reaches the renderer.

The palette is a row of ids, not a single id, so it takes its own rule type
(`PaletteRule`) instead of the generic `Rule`. Its last step is always the
same: rotate the opening pattern to the front, because the opening region's
pattern is the only mood decision the row records.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias

from app.sonify.guitar import BARRIOS_TREMOLO_MIN_BPM
from app.sonify.plan_rules import MACRO, PHRASE, Mode, Rule

# The macro sentinel for the 34-bar 1D body. See the module docstring.
DAILY = "daily"

_SIX_EIGHT = "6/8"
_DANCE_METERS = frozenset({"4/4", _SIX_EIGHT})


@dataclass(frozen=True)
class BarriosPhraseInputs:
    """Everything the phrase ladder can read. All fields are required."""

    trio: bool
    bridge: bool
    mood: str | None
    bpm: int
    band: str
    first_body: bool
    kind: str
    hold: bool
    running: bool
    previous: tuple[str, ...]


@dataclass(frozen=True)
class BarriosMacroInputs:
    """Everything the macro ladder can read. All fields are required."""

    mood: str | None
    bpm: int
    kind: str
    bars: int
    framed: bool
    suite_finale: bool
    forte_majority: bool
    phrase_count: int
    hold_count: int
    running_count: int


BarriosInputs: TypeAlias = BarriosPhraseInputs | BarriosMacroInputs

_INPUTS: dict[str, type] = {PHRASE: BarriosPhraseInputs, MACRO: BarriosMacroInputs}


def _tremolo_band(bpm: int) -> bool:
    """The held-phrase window: from the tremolo floor to 140 BPM."""
    return BARRIOS_TREMOLO_MIN_BPM <= bpm <= 140


def _after_two_tremolos(previous: tuple[str, ...]) -> bool:
    return previous[-2:] == ("tremolo", "tremolo")


def _running_dance(case: BarriosPhraseInputs) -> bool:
    """A running phrase in a dance meter, above 100 and not calm."""
    return (
        case.running
        and case.mood is not None
        and case.mood != "calm"
        and case.bpm > 100
        and case.kind in _DANCE_METERS
    )


def _held_majority(case: BarriosMacroInputs) -> bool:
    return bool(case.phrase_count) and (
        case.hold_count / case.phrase_count >= 0.3
        or (case.mood in {"rally", "selloff"} and case.hold_count > 0)
    )


def _running_majority(case: BarriosMacroInputs) -> bool:
    return (
        case.bpm > 100
        and case.mood in {"rally", "volatile"}
        and bool(case.phrase_count)
        and case.running_count * 2 >= case.phrase_count
    )


BARRIOS_RULES: tuple[Rule, ...] = (
    # Phrase path. Rule one owns the shared opening-body value that
    # `_select_body` applied to every ensemble before dispatching to Barrios.
    Rule(
        PHRASE,
        lambda case: case.first_body and case.bpm >= BARRIOS_TREMOLO_MIN_BPM,
        "preludio",
        "the opening body phrase stays the ascending preludio",
    ),
    Rule(
        PHRASE,
        lambda case: (
            case.hold
            and _tremolo_band(case.bpm)
            and _after_two_tremolos(case.previous)
            and (case.trio or case.bridge)
        ),
        "thumb_cantabile",
        "a held trio or bridge answers a tremolo run on the thumb",
    ),
    Rule(
        PHRASE,
        lambda case: case.hold
        and _tremolo_band(case.bpm)
        and _after_two_tremolos(case.previous),
        "andante",
        "a held phrase after two tremolo phrases falls back to the chorale",
    ),
    Rule(
        PHRASE,
        lambda case: case.hold and _tremolo_band(case.bpm),
        "tremolo",
        "a held phrase inside the tremolo band sings Ultimo Tremolo",
    ),
    Rule(
        PHRASE,
        lambda case: case.bpm < BARRIOS_TREMOLO_MIN_BPM and case.bridge,
        "thumb_cantabile",
        "a bridge below the tremolo floor sings the thumb cantabile",
    ),
    Rule(
        PHRASE,
        lambda case: case.bpm < BARRIOS_TREMOLO_MIN_BPM,
        "andante",
        "below the tremolo floor every other phrase walks the andante chorale",
    ),
    Rule(
        PHRASE,
        lambda case: (
            case.running
            and case.mood == "calm"
            and case.trio
            and case.bpm >= BARRIOS_TREMOLO_MIN_BPM
        ),
        "thumb_cantabile",
        "a calm running trio sings the thumb cantabile",
    ),
    Rule(
        PHRASE,
        lambda case: _running_dance(case) and case.kind == "4/4",
        "choro",
        "a running 4/4 phrase above 100 takes the choro",
    ),
    Rule(
        PHRASE,
        lambda case: _running_dance(case) and case.kind == _SIX_EIGHT and case.trio,
        "vals",
        "a running 6/8 trio takes the vals",
    ),
    Rule(
        PHRASE,
        lambda case: (
            _running_dance(case) and case.kind == _SIX_EIGHT and case.band == "f"
        ),
        "hemiola",
        "a running 6/8 phrase at f takes the hemiola",
    ),
    Rule(
        PHRASE,
        lambda case: _running_dance(case) and case.kind == _SIX_EIGHT,
        "polca",
        "a running 6/8 phrase takes the polca",
    ),
    # Macro path. Contrast is not answered here; `_assign_macro` paints it.
    Rule(
        MACRO,
        lambda case: case.bpm < BARRIOS_TREMOLO_MIN_BPM,
        "andante",
        "a body below the tremolo floor walks the andante chorale",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.framed
            and case.kind == "4/4"
            and 90 <= case.bpm <= 100
            and (case.suite_finale or case.mood in {"selloff", "volatile"})
        ),
        "tremolo",
        "a moderato 4/4 body that closes on a long finale (or a selloff/volatile session) sings Ultimo Tremolo",
    ),
    Rule(
        MACRO,
        lambda case: case.framed and case.kind == "4/4" and 90 <= case.bpm <= 100,
        "preludio",
        "a moderato 4/4 body opens La Catedral's preludio",
    ),
    Rule(
        MACRO,
        lambda case: case.mood == "calm",
        "preludio",
        "a calm body keeps the preludio",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.framed
            and case.kind == _SIX_EIGHT
            and case.bpm > 100
            and case.bars > 40
            and case.mood != "calm"
            and case.forte_majority
        ),
        "hemiola",
        "a long loud 6/8 body takes the hemiola",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.framed
            and case.kind == _SIX_EIGHT
            and case.bpm > 100
            and case.bars > 40
            and case.mood != "calm"
        ),
        "polca",
        "a long 6/8 body takes the polca",
    ),
    Rule(
        MACRO,
        lambda case: (
            case.bpm == 120 and case.bars == 34 and case.kind == "4/4"
        ),
        DAILY,
        "the 34-bar 1D body chooses per phrase from its own activity",
    ),
    Rule(
        MACRO,
        lambda case: _held_majority(case),
        "tremolo",
        "a body with held phrases (or a rally/selloff body with one) sings the tremolo",
    ),
    Rule(
        MACRO,
        lambda case: _running_majority(case) and case.kind == _SIX_EIGHT,
        "polca",
        "a running rally/volatile 6/8 body takes the polca",
    ),
    Rule(
        MACRO,
        lambda case: _running_majority(case) and case.kind == "4/4",
        "choro",
        "a running rally/volatile 4/4 body takes the choro",
    ),
    Rule(
        MACRO,
        lambda case: _running_majority(case),
        "preludio",
        "a running rally/volatile body in another meter stays the preludio",
    ),
    Rule(
        MACRO,
        lambda case: case.hold_count > 0,
        "tremolo",
        "any held phrase still sings the tremolo",
    ),
)

BARRIOS_FALLBACK: dict[Mode, str] = {PHRASE: "preludio", MACRO: "preludio"}


def barrios_pattern(mode: Mode, case: BarriosInputs) -> str:
    """First rule for `mode` that matches, else that mode's fallback row.

    The input type must match the mode. The macro ladder may return the
    `DAILY` sentinel; the caller expands it (see the module docstring).
    """
    expected = _INPUTS[mode]
    if not isinstance(case, expected):
        raise TypeError(
            f"{mode} needs {expected.__name__}, got {type(case).__name__}"
        )
    for rule in BARRIOS_RULES:
        if rule.mode == mode and rule.when(case):
            return rule.pattern
    return BARRIOS_FALLBACK[mode]


@dataclass(frozen=True)
class BarriosPaletteInputs:
    """The palette decision: the meter, the tempo, and the opening pattern."""

    bpm: int
    kind: str
    primary: str


@dataclass(frozen=True)
class PaletteRule:
    """One ordered row decision. A row is not an id, so this is not a `Rule`."""

    when: Callable[[BarriosPaletteInputs], bool]
    row: tuple[str, ...]
    why: str


BARRIOS_PALETTE_RULES: tuple[PaletteRule, ...] = (
    PaletteRule(
        lambda case: case.bpm < BARRIOS_TREMOLO_MIN_BPM,
        ("andante", "thumb_cantabile"),
        "a slow movement walks the chorale row",
    ),
    PaletteRule(
        lambda case: (
            case.kind == _SIX_EIGHT
            and case.bpm > 100
            and case.primary == "hemiola"
        ),
        ("hemiola", "vals", "polca", "tremolo"),
        "a 6/8 hemiola opening walks vals, polca, then tremolo",
    ),
    PaletteRule(
        lambda case: (
            case.kind == _SIX_EIGHT
            and case.bpm > 100
            and case.primary == "preludio"
        ),
        ("preludio", "thumb_cantabile", "vals"),
        "a 6/8 preludio opening walks the thumb then the vals",
    ),
    PaletteRule(
        lambda case: case.kind == _SIX_EIGHT and case.bpm > 100,
        ("polca", "vals", "hemiola", "tremolo"),
        "a 6/8 dance opening walks vals, hemiola, then tremolo",
    ),
    PaletteRule(
        lambda case: (
            case.kind == "4/4" and case.bpm > 100 and case.primary == "tremolo"
        ),
        ("tremolo", "choro", "thumb_cantabile"),
        "a 4/4 tremolo opening walks the choro then the thumb",
    ),
    PaletteRule(
        lambda case: (
            case.kind == "4/4" and case.bpm > 100 and case.primary == "preludio"
        ),
        ("preludio", "choro", "andante"),
        "a 4/4 preludio opening walks the choro then the chorale",
    ),
    PaletteRule(
        lambda case: case.kind == "4/4" and case.bpm > 100,
        ("choro", "thumb_cantabile", "andante"),
        "a 4/4 dance opening walks the thumb then the chorale",
    ),
    PaletteRule(
        lambda case: case.primary == "tremolo",
        ("tremolo", "andante"),
        "a tremolo opening at 90-100 BPM walks the chorale",
    ),
)

BARRIOS_PALETTE_FALLBACK: tuple[str, ...] = ("preludio", "andante")


def barrios_palette(case: BarriosPaletteInputs) -> tuple[str, ...]:
    """The first matching row, with its opening pattern rotated to the front.

    Tremolo and framed Preludio never share a 4/4 row: the reprise would put
    the other singing pattern back in the last part, so those rows leave it
    out. An opening id the row does not name is seated in front of it.
    """
    row = next(
        (rule.row for rule in BARRIOS_PALETTE_RULES if rule.when(case)),
        BARRIOS_PALETTE_FALLBACK,
    )
    if case.primary not in row:
        return (case.primary, *[name for name in row if name != case.primary])
    start = row.index(case.primary)
    return row[start:] + row[:start]
