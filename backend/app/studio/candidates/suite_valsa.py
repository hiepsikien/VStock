"""Suite Popular Brasileira candidate: Valsa-Choro in 3/4.

The authored source is `suite_valsa.json`; this module is its code twin and
gives the preview a typed spec. Nothing here calls `sentence_specs.register`,
so production planners cannot see the candidate.

The sentence is one eight-bar 3/4 waltz period over the existing
`villa_pattern` parent, which already has a real 3/4 branch in
`guitar_villa.py`:

    phrase 1 (open)      phrase 2 (closed)
    bar 0  A  arpeggio   bar 4  A  arpeggio
    bar 1  A  arpeggio   bar 5  A  arpeggio
    bar 2  B  chord      bar 6  B  chord
    bar 3  A  arpeggio   bar 7  B  chord

The two four-bar halves are a parallel period: the antecedent ends on the open
roll, the consequent repeats the first three bars and closes on the block
chords. That is deliberately a different shape from the four-bar
`suite_mazurka_arpeggio_aaba` (A A B A), so the two 3/4 movements are not the
same sentence under two names.

Both figures are the bar-level adapters in `guitar_villa_figures.py`; the note
content still comes from the production writers. `etude1`/`etude11` are left
out because their 16-sixteenth and four-quarter cycles assume a 4/4 bar, and
`thumb_cantabile` is a phrase-level writer, not a bar figure. The waltz
therefore shares the existing 3/4 figures instead of asking for a new one.

The Suite movement id `suite_valsa` is deliberately *not* used as the sentence
id: it stays a future registered pattern, so this candidate does not claim a
production pattern, its meter variants, or a selection rule.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.guitar_villa_figures import VILLA_ARPEGGIO, VILLA_CHORD_MELODY
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).parent
SUITE_VALSA_PATH = CANDIDATES_DIR / "suite_valsa.json"

SUITE_VALSA_PERIOD_ID = "suite_valsa_arpeggio_period"

# One eight-bar 3/4 waltz period: A A B A (open) answered by A A B B (closed).
# The tile repeats, so a sixteen-bar fixture is the period twice.
SUITE_VALSA_PERIOD = SentenceSpec(
    id=SUITE_VALSA_PERIOD_ID,
    pattern="villa_pattern",
    meter="3/4",
    select=Select(length_min=8),
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


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_suite_valsa(
    path: str | Path = SUITE_VALSA_PATH,
) -> tuple[SentenceSpec, ...]:
    """Parse the Suite Valsa candidate JSON without touching the registry."""
    return load_candidate(path)


def suite_valsa_spec(path: str | Path = SUITE_VALSA_PATH) -> SentenceSpec:
    """The single candidate sentence from the authored file."""
    specs = load_suite_valsa(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
