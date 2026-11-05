"""Feature-gated production home for Villa-Lobos's Valsa-Choro.

The Studio candidate `suite_valsa_arpeggio_period` is an eight-bar 3/4 waltz
period over the existing Villa figures: A A B A (open) answered by A A B B
(closed). This module promotes it from the preview-only candidate behind its own
default-off flag.

Flag
----
`VSTOCK_SUITE_VALSA` is read through :mod:`app.sonify.production_flags` at call
time. Missing, empty, falsy, unknown, and rollback values keep the historical
Villa path byte for byte, and selection never returns `suite_valsa`.

Registration
------------
The pattern id is `suite_valsa`, its meter is `3/4`, and its printed title is
`Valsa-Choro`. The sentence is registered as `("suite_valsa", "3/4")` with
`valid_figures=VILLA_FIGURES` only when the flag is on. Importing this module
never mutates `SENTENCE_SPECS`.

Caveat
------
``SUITE_VALSA_CAVEAT`` keeps the audit's distinction: the 3/4 branch is exact
(no fold), while the eight-bar period is the candidate's working shape rather
than a score transcription.
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
from app.sonify.production_flags import suite_valsa_enabled, use_suite_valsa
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

SUITE_VALSA_PATTERN = "suite_valsa"
SUITE_VALSA_METER = "3/4"
SUITE_VALSA_MIN_BARS = 8
SUITE_VALSA_PERIOD_ID = "suite_valsa_arpeggio_period"
SUITE_VALSA_TITLE = "Valsa-Choro"
SUITE_VALSA_LEVEL = "topic"
SUITE_VALSA_NAME_SOURCE = "dance"
SUITE_VALSA_CAVEAT = (
    "The engine meter is the exact 3/4 branch, not a fold. The eight-bar "
    "A-A-B-A / A-A-B-B period is the candidate's working shape; the score's "
    "phrase boundaries are not claimed as a transcription."
)

# The code twin of `app/studio/candidates/suite_valsa.json`, re-keyed to the
# production pattern id. A test compares the slot geometry with the JSON.
SUITE_VALSA_PERIOD = SentenceSpec(
    id=SUITE_VALSA_PERIOD_ID,
    pattern=SUITE_VALSA_PATTERN,
    meter=SUITE_VALSA_METER,
    select=Select(length_min=SUITE_VALSA_MIN_BARS),
    span=Span(tile=8, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=4, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=5, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=6, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=7, bars=1, figure=VILLA_CHORD_MELODY),
    ),
)
SUITE_VALSA_SPECS = (SUITE_VALSA_PERIOD,)
SUITE_VALSA_KEY = (SUITE_VALSA_PATTERN, SUITE_VALSA_METER)

SUITE_VALSA_GATE = SuiteGate(
    pattern=SUITE_VALSA_PATTERN,
    meter=SUITE_VALSA_METER,
    title=SUITE_VALSA_TITLE,
    name_source=SUITE_VALSA_NAME_SOURCE,
    min_bars=SUITE_VALSA_MIN_BARS,
    sentence_id=SUITE_VALSA_PERIOD_ID,
    spec=SUITE_VALSA_PERIOD,
    caveat=SUITE_VALSA_CAVEAT,
    enabled=suite_valsa_enabled,
    use_flag=use_suite_valsa,
)
SUITE_VALSA_META = SUITE_VALSA_GATE.meta


def enabled() -> bool:
    """The production flag, read at call time."""
    return SUITE_VALSA_GATE.enabled()


def ensure_registered() -> bool:
    """Register the period if the table does not already hold it."""
    return _ensure_registered(SUITE_VALSA_GATE)


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    return _unregister(SUITE_VALSA_GATE)


def use_suite_valsa_period(enabled: bool = True):
    """Pin the flag and own this module's registry entry for the context."""
    return use_gate(SUITE_VALSA_GATE, enabled)


def eligible(ctx) -> bool:
    """A whole 3/4 Villa movement of at least eight bars with no pedal bar."""
    return _eligible(SUITE_VALSA_GATE, ctx)


def selectable(ctx) -> bool:
    """Whether selection may return `suite_valsa` for this movement."""
    return _selectable(SUITE_VALSA_GATE, ctx)


def render_sentence(ctx):
    """Render the period for an eligible movement, or None to fall back."""
    return _render_sentence(SUITE_VALSA_GATE, ctx, render_villa_figure)
