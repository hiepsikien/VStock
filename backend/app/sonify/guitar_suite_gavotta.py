"""Feature-gated production home for Villa-Lobos's Gavotta-Choro.

The Studio candidate `suite_gavotta_arpeggio_baab` is a four-bar 4/4 gavotte
cell over the existing Villa figures: chordal frame, two bars of the Villa roll,
then the chordal close (B-A-A-B). This module promotes it from the preview-only
candidate behind its own default-off flag.

Flag
----
`VSTOCK_SUITE_GAVOTTA` is read through :mod:`app.sonify.production_flags` at
call time. Missing, empty, falsy, unknown, and rollback values keep the
historical Villa path byte for byte, and selection never returns `suite_gavotta`.

Registration
------------
The pattern id is `suite_gavotta`, its meter is `4/4`, and its printed title is
`Gavotta-Choro`. The sentence is registered as `("suite_gavotta", "4/4")` with
`valid_figures=VILLA_FIGURES` only when the flag is on. Importing this module
never mutates `SENTENCE_SPECS`.

Caveat
------
``SUITE_GAVOTTA_CAVEAT`` keeps the candidate's bar-0 warning: the pickup is
unconfirmed, the cell is anchored on a downbeat, and a real pickup would shift
every bar index. The promotion does not claim the score's bar 0.
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
from app.sonify.production_flags import suite_gavotta_enabled, use_suite_gavotta
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

SUITE_GAVOTTA_PATTERN = "suite_gavotta"
SUITE_GAVOTTA_METER = "4/4"
SUITE_GAVOTTA_MIN_BARS = 4
SUITE_GAVOTTA_BAAB_ID = "suite_gavotta_arpeggio_baab"
SUITE_GAVOTTA_TITLE = "Gavotta-Choro"
SUITE_GAVOTTA_LEVEL = "topic"
SUITE_GAVOTTA_NAME_SOURCE = "dance"
SUITE_GAVOTTA_CAVEAT = (
    "The 4/4 signature is the working one, but the gavotte pickup is "
    "unconfirmed. This candidate is anchored at bar 0 (a downbeat); a real "
    "pickup would shift every bar index and is not expressible in the current "
    "spec, so the preview does not claim the score's bar 0."
)

# The code twin of `app/studio/candidates/suite_gavotta.json`, re-keyed to the
# production pattern id. A test compares the slot geometry with the JSON.
SUITE_GAVOTTA_BAAB = SentenceSpec(
    id=SUITE_GAVOTTA_BAAB_ID,
    pattern=SUITE_GAVOTTA_PATTERN,
    meter=SUITE_GAVOTTA_METER,
    select=Select(length_min=SUITE_GAVOTTA_MIN_BARS),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=3, bars=1, figure=VILLA_CHORD_MELODY),
    ),
)
SUITE_GAVOTTA_SPECS = (SUITE_GAVOTTA_BAAB,)
SUITE_GAVOTTA_KEY = (SUITE_GAVOTTA_PATTERN, SUITE_GAVOTTA_METER)

SUITE_GAVOTTA_GATE = SuiteGate(
    pattern=SUITE_GAVOTTA_PATTERN,
    meter=SUITE_GAVOTTA_METER,
    title=SUITE_GAVOTTA_TITLE,
    name_source=SUITE_GAVOTTA_NAME_SOURCE,
    min_bars=SUITE_GAVOTTA_MIN_BARS,
    sentence_id=SUITE_GAVOTTA_BAAB_ID,
    spec=SUITE_GAVOTTA_BAAB,
    caveat=SUITE_GAVOTTA_CAVEAT,
    enabled=suite_gavotta_enabled,
    use_flag=use_suite_gavotta,
)
SUITE_GAVOTTA_META = SUITE_GAVOTTA_GATE.meta


def enabled() -> bool:
    """The production flag, read at call time."""
    return SUITE_GAVOTTA_GATE.enabled()


def ensure_registered() -> bool:
    """Register the cell if the table does not already hold it."""
    return _ensure_registered(SUITE_GAVOTTA_GATE)


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    return _unregister(SUITE_GAVOTTA_GATE)


def use_suite_gavotta_baab(enabled: bool = True):
    """Pin the flag and own this module's registry entry for the context."""
    return use_gate(SUITE_GAVOTTA_GATE, enabled)


def eligible(ctx) -> bool:
    """A whole 4/4 Villa movement of at least four bars with no pedal bar."""
    return _eligible(SUITE_GAVOTTA_GATE, ctx)


def selectable(ctx) -> bool:
    """Whether selection may return `suite_gavotta` for this movement."""
    return _selectable(SUITE_GAVOTTA_GATE, ctx)


def render_sentence(ctx):
    """Render the cell for an eligible movement, or None to fall back."""
    return _render_sentence(SUITE_GAVOTTA_GATE, ctx, render_villa_figure)
