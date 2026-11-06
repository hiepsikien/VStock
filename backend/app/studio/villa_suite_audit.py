"""Phase 2 audit data for Villa-Lobos's *Suite Popular Brasileira*.

This is a data-only ledger: five frozen movement records, a coverage helper,
and validation. It does not render, register a `SentenceSpec`, or add a
candidate JSON. The next sprint reads it to choose a movement from meter
evidence instead of guessing.

Meter policy follows `docs/sonify-texture-studio.md` §3.2 and §4.4.1:

* `meter` is the meter the *pattern* would see after `resolve_runtime_form()`.
* `meter_uncertain` is true when the score's signature or bar-0 alignment is
  not confirmed. `meter_note` says what is still unknown.
* `form.Meter` has no 2/4. A 2/4 movement must be folded to 4/4 at the form
  layer (`fold: 2`, owned by `span.py`/`FormSpec`) before any pattern is
  chosen. This audit records the folded meter and flags the derivation.

`validate()` is deliberately not called at import: importing this module stays
inert. Tests call it explicitly, because validation reads the printed-title
table in `program.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.sonify.form import METER_34, METER_44, Meter
from app.sonify.pattern_registry import PATTERN_META

# The ten Villa rows in `guitar_wave.PROFILES`; a test checks this set against
# the real table so an invented id cannot survive.
VILLA_PATTERN_IDS = frozenset(
    {
        "villa_pattern",
        "chord_melody",
        "etude1",
        "etude11",
        "thumb_cantabile",
        "suite_mazurka",
        "suite_valsa",
        "suite_gavotta",
        "suite_schottish",
        "suite_choros1",
    }
)

# Movements that have since been promoted to a production pattern id. Their
# ids and printed titles now deliberately collide with `PATTERN_META`; the
# ledger keeps the row, but the "unshipped" collision guard skips these.
PROMOTED_MOVEMENT_IDS = frozenset(
    {
        "suite_mazurka",
        "suite_valsa",
        "suite_gavotta",
        "suite_schottish",
        "suite_choros1",
    }
)


SentenceVerdict = Literal["yes", "no", "unknown"]
SENTENCE_VERDICTS = frozenset({"yes", "no", "unknown"})

# Every ensemble a known pattern id can print under. `pattern_title` has one
# ensemble-specific special case (`thumb_cantabile` for Villa), so the title
# guard does not assume a single global title per id.
_TITLE_ENSEMBLES = ("villa", "classic", "barrios", "bach", "brouwer", "torroba")


@dataclass(frozen=True)
class SuiteMovement:
    """One movement of the Suite as palette data, not as a shipped pattern.

    `meter` is the engine meter after any form-level fold. `meter_source` is
    the short evidence string; `meter_note` carries the caveat. `pattern_overlap`
    names only existing Villa pattern ids that have a branch for this meter.
    `sentence_plausible` is a three-way judgement, not a promise: `yes` means
    the movement's phrase shape can carry an N-bar sentence, `unknown` means
    the score or the anchor has not been checked.
    """

    id: str
    title: str
    meter: Meter | None
    meter_source: str
    meter_uncertain: bool
    meter_note: str
    pattern_overlap: tuple[str, ...]
    sentence_plausible: SentenceVerdict
    rationale: str
    gaps: tuple[str, ...]


SUITE_MOVEMENTS: tuple[SuiteMovement, ...] = (
    SuiteMovement(
        id="suite_mazurka",
        title="Mazurka-Choro",
        meter=METER_34,
        meter_source="form.METER_34 (3/4)",
        meter_uncertain=False,
        meter_note=(
            "The doc gives 3/4 and the Villa bar writer already has a 3/4 "
            "branch; no form-level fold is involved."
        ),
        pattern_overlap=("villa_pattern", "chord_melody", "thumb_cantabile", "suite_mazurka"),
        sentence_plausible="yes",
        rationale=(
            "First movement and the cleanest 3/4 case: `_villa_bass` keeps the "
            "root/fifth on its 3/4 path, `_render_villa_bar` accents eighths "
            "{0, 3} at f, and `_thumb_offsets` returns (2, 4). A 3/4 dance with "
            "a repeating phrase can carry a sentence; that is a plausibility "
            "judgement, not a transcription. The existing `villa_arpeggio_aba` "
            "candidate is 4/4, so a 3/4 sentence is still new work."
        ),
        gaps=(
            "Read the score and confirm phrase boundaries; no note content is "
            "authored here.",
            "Author a preview-only 3/4 sentence from the existing Villa figures.",
            "Choose the opening texture: `villa_pattern`, `chord_melody`, or "
            "`thumb_cantabile`.",
        ),
    ),
    SuiteMovement(
        id="suite_schottish",
        title="Schottish-Choro",
        meter=METER_44,
        meter_source="form.METER_44 after fold=2 from a 2/4 source",
        meter_uncertain=True,
        meter_note=(
            "The doc gives 2/4, but `form.Meter` has no 2/4. Two 2/4 bars must "
            "fold into one 4/4 bar before a pattern is chosen (§4.4.1). Confirm "
            "the score and the fold before authoring."
        ),
        pattern_overlap=("villa_pattern", "chord_melody"),
        sentence_plausible="unknown",
        rationale=(
            "A schottische is a 2/4 dance; the engine can only see it after the "
            "form-level fold. Until the fold is accepted, a sentence could span "
            "two 2/4 bars or one folded 4/4 bar, and those are different "
            "templates. `villa_pattern` and `chord_melody` are the only 4/4 "
            "Villa branches that survive the fold without a new figure."
        ),
        gaps=(
            "Verify the source signature is 2/4.",
            "Land or accept the `fold: 2` form path in `span.py`.",
            "Audit the phrase under the fold before choosing a sentence tile.",
        ),
    ),
    SuiteMovement(
        id="suite_valsa",
        title="Valsa-Choro",
        meter=METER_34,
        meter_source="form.METER_34 (3/4)",
        meter_uncertain=False,
        meter_note=(
            "The doc gives 3/4; the same exact Villa 3/4 branches as Mazurka "
            "apply, with no form-level fold."
        ),
        pattern_overlap=("villa_pattern", "chord_melody", "thumb_cantabile"),
        sentence_plausible="yes",
        rationale=(
            "A 3/4 waltz with the same exact METER_34 as Mazurka. The doc's "
            "`suite_valsa` selection example is a post-patch expectation, not "
            "current behavior: `guitar_patterns` still returns `chord_melody` "
            "for a calm Villa phrase today. Reusing the 3/4 branches is real; "
            "claiming the waltz already selects `suite_valsa` would not be."
        ),
        gaps=(
            "Read the score and confirm the waltz phrase boundaries.",
            "Decide whether the waltz needs a distinct 3/4 figure or can share "
            "Mazurka's.",
            "Author a preview-only 3/4 sentence; do not wire selection yet.",
        ),
    ),
    SuiteMovement(
        id="suite_gavotta",
        title="Gavotta-Choro",
        meter=METER_44,
        meter_source="form.METER_44 (4/4 nominal)",
        meter_uncertain=True,
        meter_note=(
            "4/4 is the working signature, but the doc says the start/pickup is "
            "unconfirmed. Bar 0 cannot be fixed until the score is read."
        ),
        pattern_overlap=("villa_pattern", "chord_melody"),
        sentence_plausible="unknown",
        rationale=(
            "A gavotte is 4/4, but a pickup shifts every bar index and the "
            "sentence anchor. `villa_pattern` and `chord_melody` have 4/4 "
            "branches; `etude1`/`etude11` are also 4/4 but are perpetual-study "
            "textures, not evidence for a gavotte. The existing 4/4 "
            "`villa_arpeggio_aba` candidate may be a starting point only after "
            "the pickup is fixed."
        ),
        gaps=(
            "Confirm the pickup and bar-0 alignment.",
            "Author a 4/4 sentence once the anchor is fixed.",
            "Check whether `villa_arpeggio_aba` is a usable starting point.",
        ),
    ),
    SuiteMovement(
        id="suite_choros1",
        title="Choros No. 1",
        meter=METER_44,
        meter_source="form.METER_44 (provisional; source may be 2/4)",
        meter_uncertain=True,
        meter_note=(
            "The doc leaves 2/4 vs 4/4 open. This record uses 4/4 as the "
            "provisional engine meter; if the score is 2/4 it needs the same "
            "fold=2 path as Schottish rather than a new Meter."
        ),
        pattern_overlap=("villa_pattern", "chord_melody"),
        sentence_plausible="unknown",
        rationale=(
            "Choros No. 1 is treated as the fifth palette movement, not as a "
            "confirmed 4/4 piece. Both the signature and the phrase start are "
            "open, so a sentence cannot be anchored yet. Do not invent a 2/4 "
            "Meter to make authoring start sooner."
        ),
        gaps=(
            "Confirm 2/4 vs 4/4 from the score.",
            "If 2/4, reuse the Schottish fold decision.",
            "Author the sentence only after meter and bar 0 are fixed.",
        ),
    ),
)


def coverage() -> dict[str, tuple[str, ...]]:
    """Every existing Villa pattern -> the movements whose overlap names it.

    Empty tuples stay in the result. They are the audit finding, not missing
    keys: `etude1` and `etude11` currently overlap no Suite movement in this
    ledger.
    """
    found: dict[str, list[str]] = {pattern: [] for pattern in VILLA_PATTERN_IDS}
    for movement in SUITE_MOVEMENTS:
        for pattern in movement.pattern_overlap:
            found[pattern].append(movement.id)
    return {pattern: tuple(ids) for pattern, ids in found.items()}


def first_movement() -> SuiteMovement:
    """The suite-order first movement, for the next sprint's starting point."""
    return SUITE_MOVEMENTS[0]


def _known_titles() -> frozenset[str]:
    """Every printed pattern title, across ensembles that use the id."""
    from app.sonify.program import pattern_title

    return frozenset(
        title
        for pattern in PATTERN_META
        for ensemble in _TITLE_ENSEMBLES
        if (title := pattern_title(pattern, ensemble))
    )


def validate(movements: Sequence[SuiteMovement] = SUITE_MOVEMENTS) -> None:
    """Raise `ValueError` if the audit data is duplicate, invented, or empty.

    `movements` is injectable so a test can prove a collision is rejected
    without mutating the module's frozen tuple.
    """
    if len(movements) != 5:
        raise ValueError(
            f"Suite Popular Brasileira has 5 movements, got {len(movements)}"
        )

    ids = [movement.id for movement in movements]
    titles = [movement.title for movement in movements]
    duplicate_ids = sorted({value for value in ids if ids.count(value) > 1})
    duplicate_titles = sorted({value for value in titles if titles.count(value) > 1})
    if duplicate_ids:
        raise ValueError(f"duplicate movement ids: {duplicate_ids}")
    if duplicate_titles:
        raise ValueError(f"duplicate movement titles: {duplicate_titles}")

    existing_ids = frozenset(PATTERN_META)
    existing_titles = _known_titles()

    for movement in movements:
        if movement.id in existing_ids and movement.id not in PROMOTED_MOVEMENT_IDS:
            raise ValueError(f"{movement.id!r}: collides with an existing pattern id")
        if not movement.id.startswith("suite_"):
            raise ValueError(f"{movement.id!r}: a Suite id must start with 'suite_'")
        if (
            movement.title in existing_titles
            and movement.id not in PROMOTED_MOVEMENT_IDS
        ):
            raise ValueError(
                f"{movement.title!r}: collides with an existing pattern title"
            )
        if not movement.meter_source.strip():
            raise ValueError(f"{movement.id}: meter_source must not be empty")
        if movement.meter is None:
            if not movement.meter_uncertain:
                raise ValueError(
                    f"{movement.id}: a missing meter must be marked uncertain"
                )
        elif not isinstance(movement.meter, Meter):
            raise ValueError(f"{movement.id}: meter must be a form.Meter or None")
        if movement.meter_uncertain and not movement.meter_note.strip():
            raise ValueError(
                f"{movement.id}: an uncertain meter needs a non-empty note"
            )
        if movement.sentence_plausible not in SENTENCE_VERDICTS:
            raise ValueError(
                f"{movement.id}: sentence_plausible must be one of "
                f"{sorted(SENTENCE_VERDICTS)}"
            )
        if not movement.pattern_overlap:
            raise ValueError(f"{movement.id}: pattern_overlap must not be empty")
        unknown = sorted(set(movement.pattern_overlap) - VILLA_PATTERN_IDS)
        if unknown:
            raise ValueError(f"{movement.id}: unknown Villa patterns {unknown}")
        if not movement.rationale.strip():
            raise ValueError(f"{movement.id}: rationale must not be empty")
        if not movement.gaps:
            raise ValueError(f"{movement.id}: gaps must not be empty")
