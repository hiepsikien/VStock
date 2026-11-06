"""Feature-gated production home for Villa-Lobos's Schottish-Choro.

The Studio candidate `suite_schottish_arpeggio_abab` is a four-bar folded 4/4
phrase over the existing Villa figures: one engine bar stands for two folded
2/4 source bars. This module promotes it from the preview-only candidate behind
its own default-off flag.

Phase 3 adds the native 2/4 twin of the same tile. The week and movement III of
a month/quarter take the 2/4 gate; the 4/4 gate is kept as the rollback and
regression path. Both gates share `SCHOTTISH_SCOPES`, so a direct render that
carries no movement span/index can never select either one.

Flag
----
`VSTOCK_SUITE_SCHOTTISH` is read through :mod:`app.sonify.production_flags` at
call time. Missing, empty, falsy, unknown, and rollback values keep the
historical Villa path byte for byte, and selection never returns
`suite_schottish`.

Registration
------------
The pattern id is `suite_schottish`, its printed title is `Schottish-Choro`, and
it registers under both `(suite_schottish, 4/4)` and `(suite_schottish, 2/4)`
with `valid_figures=VILLA_FIGURES` only when the flag is on. Importing this
module never mutates `SENTENCE_SPECS`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

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
    VILLA_CADENCE,
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
SUITE_SCHOTTISH_METER_24 = "2/4"
SUITE_SCHOTTISH_MIN_BARS = 4
SUITE_SCHOTTISH_ABAB_ID = "suite_schottish_arpeggio_abab"
SUITE_SCHOTTISH_TITLE = "Schottish-Choro"
SUITE_SCHOTTISH_LEVEL = "topic"
SUITE_SCHOTTISH_NAME_SOURCE = "dance"
# Schottish is movement III of a month/quarter and the whole of a week. A year
# keeps its own programme, so `1Y` is deliberately absent.
SCHOTTISH_SCOPES = frozenset({("1W", 0), ("1M", 2), ("3M", 2)})
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
    role="A",
)
# The phrase-plan variants. A stays the historical ABAB tile; B swaps the
# arpeggio/chord order for contrast; close ends on the sustained cadence.
SUITE_SCHOTTISH_B_ID = "suite_schottish_contrast_b"
SUITE_SCHOTTISH_CLOSE_ID = "suite_schottish_close_cadence"
SUITE_SCHOTTISH_B = replace(
    SUITE_SCHOTTISH_ABAB,
    id=SUITE_SCHOTTISH_B_ID,
    role="B",
    slots=(
        Slot(start=0, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
    ),
)
SUITE_SCHOTTISH_CLOSE = replace(
    SUITE_SCHOTTISH_ABAB,
    id=SUITE_SCHOTTISH_CLOSE_ID,
    role="close",
    select=Select(
        length_min=SUITE_SCHOTTISH_MIN_BARS,
        closes="close",
    ),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=2, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=3, bars=1, figure=VILLA_CADENCE),
    ),
)
SUITE_SCHOTTISH_SPECS = (
    SUITE_SCHOTTISH_ABAB,
    SUITE_SCHOTTISH_B,
    SUITE_SCHOTTISH_CLOSE,
)
SUITE_SCHOTTISH_KEY = (SUITE_SCHOTTISH_PATTERN, SUITE_SCHOTTISH_METER)

# The native 2/4 twin of the same role tiles. The meter is the only change.
SUITE_SCHOTTISH_ABAB_24 = replace(
    SUITE_SCHOTTISH_ABAB, meter=SUITE_SCHOTTISH_METER_24
)
SUITE_SCHOTTISH_B_24 = replace(
    SUITE_SCHOTTISH_B, meter=SUITE_SCHOTTISH_METER_24
)
SUITE_SCHOTTISH_CLOSE_24 = replace(
    SUITE_SCHOTTISH_CLOSE, meter=SUITE_SCHOTTISH_METER_24
)
SUITE_SCHOTTISH_SPECS_24 = (
    SUITE_SCHOTTISH_ABAB_24,
    SUITE_SCHOTTISH_B_24,
    SUITE_SCHOTTISH_CLOSE_24,
)
SUITE_SCHOTTISH_KEY_24 = (
    SUITE_SCHOTTISH_PATTERN,
    SUITE_SCHOTTISH_METER_24,
)

# The 4/4 row stays as the rollback/fallback gate. It shares the movement scope
# with the native 2/4 row; because their meters differ, only one is eligible in
# a given movement.
GATE_44 = SuiteGate(
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
    # A real Schottish movement carries an intro/outro frame. The body is what
    # the ABAB tile covers; the door keeps the historical render.
    partial=True,
    movement_scopes=SCHOTTISH_SCOPES,
    extra_specs=(SUITE_SCHOTTISH_B, SUITE_SCHOTTISH_CLOSE),
)
GATE_24 = SuiteGate(
    pattern=SUITE_SCHOTTISH_PATTERN,
    meter=SUITE_SCHOTTISH_METER_24,
    title=SUITE_SCHOTTISH_TITLE,
    name_source=SUITE_SCHOTTISH_NAME_SOURCE,
    min_bars=SUITE_SCHOTTISH_MIN_BARS,
    sentence_id=SUITE_SCHOTTISH_ABAB_ID,
    spec=SUITE_SCHOTTISH_ABAB_24,
    caveat=SUITE_SCHOTTISH_CAVEAT,
    enabled=suite_schottish_enabled,
    use_flag=use_suite_schottish,
    partial=True,
    movement_scopes=SCHOTTISH_SCOPES,
    extra_specs=(SUITE_SCHOTTISH_B_24, SUITE_SCHOTTISH_CLOSE_24),
)
GATES = (GATE_44, GATE_24)
# Kept for callers that name the original 4/4 gate directly.
SUITE_SCHOTTISH_GATE = GATE_44
SUITE_SCHOTTISH_META = GATE_44.meta


def enabled() -> bool:
    """The production flag, read at call time."""
    return SUITE_SCHOTTISH_GATE.enabled()


def ensure_registered() -> bool:
    """Register both the 4/4 rollback tile and the native 2/4 tile."""
    added = False
    for gate in GATES:
        added = _ensure_registered(gate) or added
    return added


def unregister() -> bool:
    """Remove exactly the specs this module owns, not anything else."""
    removed = False
    for gate in GATES:
        removed = _unregister(gate) or removed
    return removed


@contextmanager
def use_suite_schottish_abab(enabled: bool = True) -> Iterator[None]:
    """Pin the flag and own both registry entries for the context."""
    with use_gate(GATE_44, enabled):
        with use_gate(GATE_24, enabled):
            yield


def eligible(ctx) -> bool:
    """Whether either Schottish gate can carry this scoped movement."""
    return any(_eligible(gate, ctx) for gate in GATES)


def selectable(ctx) -> bool:
    """Whether selection may return `suite_schottish` for this movement."""
    return any(_selectable(gate, ctx) for gate in GATES)


def render_sentence(ctx):
    """Render the first eligible meter's phrase, or None to fall back."""
    for gate in GATES:
        sentence = _render_sentence(gate, ctx, render_villa_figure)
        if sentence is not None:
            return sentence
    return None
