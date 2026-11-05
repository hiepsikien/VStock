"""Feature-gated production home for Villa-Lobos's Schottish-Choro.

The Studio candidate `suite_schottish_arpeggio_abab` is a four-bar folded 4/4
phrase over the existing Villa figures: one engine bar stands for two folded
2/4 source bars. This module promotes it from the preview-only candidate behind
its own default-off flag.

Flag
----
`VSTOCK_SUITE_SCHOTTISH` is read through :mod:`app.sonify.production_flags` at
call time. Missing, empty, falsy, unknown, and rollback values keep the
historical Villa path byte for byte, and selection never returns
`suite_schottish`.

Registration
------------
The pattern id is `suite_schottish`, its engine meter is `4/4`, and its printed
title is `Schottish-Choro`. The sentence is registered as
`("suite_schottish", "4/4")` with `valid_figures=VILLA_FIGURES` only when the
flag is on. Importing this module never mutates `SENTENCE_SPECS`.

Caveat
------
``SUITE_SCHOTTISH_CAVEAT`` keeps the audit's 4/4 fold stand-in: the source is
2/4, `form.Meter` has no 2/4, and the fold is not landed in `span.py`. The
promotion renders the existing 4/4 engine as a meter proxy, not a transcription.
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
from app.sonify.production_flags import (
    suite_schottish_enabled,
    use_suite_schottish,
)
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span

SUITE_SCHOTTISH_PATTERN = "suite_schottish"
SUITE_SCHOTTISH_METER = "4/4"
SUITE_SCHOTTISH_MIN_BARS = 4
SUITE_SCHOTTISH_ABAB_ID = "suite_schottish_arpeggio_abab"
SUITE_SCHOTTISH_TITLE = "Schottish-Choro"
SUITE_SCHOTTISH_LEVEL = "topic"
SUITE_SCHOTTISH_NAME_SOURCE = "dance"
SUITE_SCHOTTISH_CAVEAT = (
    "The source is 2/4 and form.Meter has no 2/4. This candidate uses the "
    "existing 4/4 engine as a stand-in: one engine bar stands for two folded "
    "2/4 source bars (fold: 2). The fold is not landed in span.py, so the "
    "preview is a meter proxy, not a transcription of the score."
)

# The code twin of `app/studio/candidates/suite_schottish.json`, re-keyed to
# the production pattern id. A test compares the slot geometry with the JSON.
SUITE_SCHOTTISH_ABAB = SentenceSpec(
    id=SUITE_SCHOTTISH_ABAB_ID,
    pattern=SUITE_SCHOTTISH_PATTERN,
    meter=SUITE_SCHOTTISH_METER,
    select=Select(length_min=SUITE_SCHOTTISH_MIN_BARS),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=2, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=3, bars=1, figure=VILLA_CHORD_MELODY),
    ),
)
SUITE_SCHOTTISH_SPECS = (SUITE_SCHOTTISH_ABAB,)
SUITE_SCHOTTISH_KEY = (SUITE_SCHOTTISH_PATTERN, SUITE_SCHOTTISH_METER)

SUITE_SCHOTTISH_GATE = SuiteGate(
    pattern=SUITE_SCHOTTISH_PATTERN,
    meter=SUITE_SCHOTTISH_METER,
    title=SUITE_SCHOTTISH_TITLE,
    name_source=SUITE_SCHOTTISH_NAME_SOURCE,
    min_bars=SUITE_SCHOTTISH_MIN_BARS,
    sentence_id=SUITE_SCHOTTISH_ABAB_ID,
    spec=SUITE_SCHOTTISH_ABAB,
    caveat=SUITE_SCHOTTISH_CAVEAT,
    enabled=suite_schottish_enabled,
    use_flag=use_suite_schottish,
)
SUITE_SCHOTTISH_META = SUITE_SCHOTTISH_GATE.meta


def enabled() -> bool:
    """The production flag, read at call time."""
    return SUITE_SCHOTTISH_GATE.enabled()


def ensure_registered() -> bool:
    """Register the folded phrase if the table does not already hold it."""
    return _ensure_registered(SUITE_SCHOTTISH_GATE)


def unregister() -> bool:
    """Remove exactly the spec this module owns, leaving anything else alone."""
    return _unregister(SUITE_SCHOTTISH_GATE)


def use_suite_schottish_abab(enabled: bool = True):
    """Pin the flag and own this module's registry entry for the context."""
    return use_gate(SUITE_SCHOTTISH_GATE, enabled)


def eligible(ctx) -> bool:
    """A whole 4/4 Villa movement of at least four bars with no pedal bar."""
    return _eligible(SUITE_SCHOTTISH_GATE, ctx)


def selectable(ctx) -> bool:
    """Whether selection may return `suite_schottish` for this movement."""
    return _selectable(SUITE_SCHOTTISH_GATE, ctx)


def render_sentence(ctx):
    """Render the folded phrase for an eligible movement, or None to fall back."""
    return _render_sentence(SUITE_SCHOTTISH_GATE, ctx, render_villa_figure)
