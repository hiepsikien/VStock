"""Feature-gated production home for Villa-Lobos's Choros No. 1.

The Studio candidate `suite_choros1_arpeggio_abba` is a four-bar 4/4 choro cell
over the existing Villa figures: roll, two chord-melody bars, roll (A-B-B-A).
This module promotes it from the preview-only candidate behind its own
default-off flag.

Flag
----
`VSTOCK_SUITE_CHOROS1` is read through :mod:`app.sonify.production_flags` at
call time. Missing, empty, falsy, unknown, and rollback values keep the
historical Villa path byte for byte, and selection never returns
`suite_choros1`.

Registration
------------
The pattern id is `suite_choros1`, its provisional engine meter is `4/4`, and
its printed title is `Choros No. 1`. The sentence is registered as
`("suite_choros1", "4/4")` with `valid_figures=VILLA_FIGURES` only when the
flag is on. Importing this module never mutates `SENTENCE_SPECS`.

Caveat
------
``SUITE_CHOROS1_CAVEAT`` keeps the audit's provisional meter: the score may be
2/4, in which case it needs the same fold decision as Schottish rather than a
new `Meter`. The promotion is a texture probe, not a transcription.
"""

from __future__ import annotations

from app.sonify.guitar_suite_gate import (
    SuiteGate,
    eligible as _eligible,
    ensure_registered as _ensure_registered,
    render_sentence as _render_sentence,
    selectable as _selectable,
    unregister as _unregister,
    use_gate,
)
from app.sonify.guitar_villa_figures import (
    VILLA_ARPEGGIO,
    VILLA_CHORD_MELODY,
    render_villa_figure,
)
from app.sonify.production_flags import suite_choros1_enabled, use_suite_choros1
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

SUITE_CHOROS1_PATTERN = "suite_choros1"
SUITE_CHOROS1_METER = "4/4"
SUITE_CHOROS1_MIN_BARS = 4
SUITE_CHOROS1_ABBA_ID = "suite_choros1_arpeggio_abba"
SUITE_CHOROS1_TITLE = "Choros No. 1"
SUITE_CHOROS1_LEVEL = "topic"
SUITE_CHOROS1_NAME_SOURCE = "genre"
SUITE_CHOROS1_CAVEAT = (
    "Choros No. 1 is authored at a provisional 4/4 because the score's 2/4 vs "
    "4/4 is still open. If the source is 2/4 it needs the same fold: 2 "
    "decision as Schottish rather than a new Meter, so this candidate is a "
    "texture probe, not a transcription."
)

# The code twin of `app/studio/candidates/suite_choros1.json`, re-keyed to the
# production pattern id. A test compares the slot geometry with the JSON.
SUITE_CHOROS1_ABBA = SentenceSpec(
    id=SUITE_CHOROS1_ABBA_ID,
    pattern=SUITE_CHOROS1_PATTERN,
    meter=SUITE_CHOROS1_METER,
    select=Select(length_min=SUITE_CHOROS1_MIN_BARS),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
    ),
)
SUITE_CHOROS1_SPECS = (SUITE_CHOROS1_ABBA,)
SUITE_CHOROS1_KEY = (SUITE_CHOROS1_PATTERN, SUITE_CHOROS1_METER)

SUITE_CHOROS1_GATE = SuiteGate(
    pattern=SUITE_CHOROS1_PATTERN,
    meter=SUITE_CHOROS1_METER,
    title=SUITE_CHOROS1_TITLE,
    name_source=SUITE_CHOROS1_NAME_SOURCE,
    min_bars=SUITE_CHOROS1_MIN_BARS,
    sentence_id=SUITE_CHOROS1_ABBA_ID,
    spec=SUITE_CHOROS1_ABBA,
    caveat=SUITE_CHOROS1_CAVEAT,
    enabled=suite_choros1_enabled,
    use_flag=use_suite_choros1,
)
SUITE_CHOROS1_META = SUITE_CHOROS1_GATE.meta


def enabled() -> bool:
    """The production flag, read at call time."""
    return SUITE_CHOROS1_GATE.enabled()


def ensure_registered() -> bool:
    """Register the cell if the table does not already hold it."""
    return _ensure_registered(SUITE_CHOROS1_GATE)


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    return _unregister(SUITE_CHOROS1_GATE)


def use_suite_choros1_abba(enabled: bool = True):
    """Pin the flag and own this module's registry entry for the context."""
    return use_gate(SUITE_CHOROS1_GATE, enabled)


def eligible(ctx) -> bool:
    """A whole 4/4 Villa movement of at least four bars with no pedal bar."""
    return _eligible(SUITE_CHOROS1_GATE, ctx)


def selectable(ctx) -> bool:
    """Whether selection may return `suite_choros1` for this movement."""
    return _selectable(SUITE_CHOROS1_GATE, ctx)


def render_sentence(ctx):
    """Render the cell for an eligible movement, or None to fall back."""
    return _render_sentence(SUITE_CHOROS1_GATE, ctx, render_villa_figure)
