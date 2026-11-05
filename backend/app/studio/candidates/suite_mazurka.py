"""Suite Popular Brasileira candidate: Mazurka-Choro in 3/4.

The authored source is `suite_mazurka.json`; this module is its code twin and
gives the preview a typed spec. Nothing here calls `sentence_specs.register`,
so production planners cannot see the candidate.

The sentence is one four-bar phrase over the existing `villa_pattern` parent,
which already has a real 3/4 branch in `guitar_villa.py`:

    bar 0   figure 1  villa_arpeggio        A
    bar 1   figure 1  villa_arpeggio        A
    bar 2   figure 2  villa_chord_melody    B
    bar 3   figure 1  villa_arpeggio        A

Both figures are the bar-level adapters in `guitar_villa_figures.py`; the note
content still comes from the production writers. `etude1`/`etude11` are left
out because their 16-sixteenth and four-quarter cycles assume a 4/4 bar, and
`thumb_cantabile` is a phrase-level writer, not a bar figure.

The Suite movement id `suite_mazurka` is deliberately *not* used as the
sentence id: it stays a future registered pattern, so this candidate does not
claim a production pattern, its meter variants, or a selection rule.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.guitar_villa_figures import VILLA_ARPEGGIO, VILLA_CHORD_MELODY
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).parent
SUITE_MAZURKA_PATH = CANDIDATES_DIR / "suite_mazurka.json"

SUITE_MAZURKA_AABA_ID = "suite_mazurka_arpeggio_aaba"

# One four-bar 3/4 dance phrase: two bars of the Villa roll, one bar of block
# chords for contrast, then the roll returns. The tile repeats, so an eight-bar
# fixture is the same phrase twice.
SUITE_MAZURKA_AABA = SentenceSpec(
    id=SUITE_MAZURKA_AABA_ID,
    pattern="villa_pattern",
    meter="3/4",
    select=Select(length_min=4),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
    ),
)


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_suite_mazurka(
    path: str | Path = SUITE_MAZURKA_PATH,
) -> tuple[SentenceSpec, ...]:
    """Parse the Suite candidate JSON without touching the global registry."""
    return load_candidate(path)


def suite_mazurka_spec(path: str | Path = SUITE_MAZURKA_PATH) -> SentenceSpec:
    """The single candidate sentence from the authored file."""
    specs = load_suite_mazurka(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
