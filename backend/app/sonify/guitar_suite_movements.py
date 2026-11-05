"""Selection order for the four promoted Suite Popular Brasileira movements.

The movement modules own their flags, specs, and renders. This module keeps one
ordered table so the chooser and the render gate always agree on precedence:

    Valsa-Choro -> Gavotta-Choro -> Schottish-Choro -> Choros No. 1

`suite_mazurka` stays ahead of all four in `guitar_patterns`, so enabling the
older flag keeps its historical result. When two of these gates are on at once,
the first eligible movement in this table wins for both selection and render.

Importing this module is inert: it only imports the four owners, and none of
them registers a sentence at import.
"""

from __future__ import annotations

from typing import Any

from app.sonify import (
    guitar_suite_choros1,
    guitar_suite_gavotta,
    guitar_suite_schottish,
    guitar_suite_valsa,
)

# (pattern id, owner module, gate) in selection precedence order. The functions
# are looked up on the module at call time so a caller can instrument one owner.
SUITE_MOVEMENTS = (
    (
        guitar_suite_valsa.SUITE_VALSA_PATTERN,
        guitar_suite_valsa,
        guitar_suite_valsa.SUITE_VALSA_GATE,
    ),
    (
        guitar_suite_gavotta.SUITE_GAVOTTA_PATTERN,
        guitar_suite_gavotta,
        guitar_suite_gavotta.SUITE_GAVOTTA_GATE,
    ),
    (
        guitar_suite_schottish.SUITE_SCHOTTISH_PATTERN,
        guitar_suite_schottish,
        guitar_suite_schottish.SUITE_SCHOTTISH_GATE,
    ),
    (
        guitar_suite_choros1.SUITE_CHOROS1_PATTERN,
        guitar_suite_choros1,
        guitar_suite_choros1.SUITE_CHOROS1_GATE,
    ),
)

SUITE_GATES = tuple(gate for _pattern, _module, gate in SUITE_MOVEMENTS)


def selectable_pattern(ctx: Any) -> str | None:
    """The first enabled, eligible movement id, or None to keep the old ladder."""
    for pattern, module, _gate in SUITE_MOVEMENTS:
        if module.selectable(ctx):
            return pattern
    return None


def render_sentence(ctx: Any):
    """Render the first enabled, eligible movement, or None to fall back."""
    for _pattern, module, _gate in SUITE_MOVEMENTS:
        sentence = module.render_sentence(ctx)
        if sentence is not None:
            return sentence
    return None
