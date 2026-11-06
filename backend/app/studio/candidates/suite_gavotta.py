"""Suite Popular Brasileira candidate: Gavotta-Choro in 4/4, no pickup.

The working signature is 4/4, but the movement's pickup is unconfirmed. The
current `SentenceSpec` has no pickup offset, so this candidate is anchored at
bar 0 (a downbeat). `BAR_ZERO_CAVEAT` records that a real pickup would shift
every bar index and that the preview does not claim the score's bar 0.

The authored source is `suite_gavotta.json`; this module is its code twin and
gives the preview a typed spec. Nothing here calls `sentence_specs.register`,
so production planners cannot see the candidate.

The sentence is one four-bar 4/4 gavotte cell over the existing `villa_pattern`
parent, which already has a real 4/4 branch in `guitar_villa.py`:

    bar 0   B  chord melody
    bar 1   A  arpeggio
    bar 2   A  arpeggio
    bar 3   B  chord melody

The chordal frame is the gavotte's steady stance; the two arpeggio bars in the
middle make the cell A-B-B-A rather than repeating the existing 4/4
`villa_arpeggio_aba` (A B A) or the Suite's 3/4 shapes. Both figures are the
bar-level adapters in `guitar_villa_figures.py`; the note content still comes
from the production writers. `etude1`/`etude11` are left out because their
study cycles are not evidence for a gavotte, and `thumb_cantabile` is a
phrase-level writer, not a bar figure.

The Suite movement id `suite_gavotta` is deliberately *not* used as the
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
SUITE_GAVOTTA_PATH = CANDIDATES_DIR / "suite_gavotta.json"

SUITE_GAVOTTA_BAAB_ID = "suite_gavotta_arpeggio_baab"

# Bar 0 is a working anchor, not a score reading. A test asserts this caveat
# exists so the preview cannot silently be treated as pickup-correct.
BAR_ZERO_CAVEAT = (
    "The 4/4 signature is the working one, but the gavotte pickup is "
    "unconfirmed. This candidate is anchored at bar 0 (a downbeat); a real "
    "pickup would shift every bar index and is not expressible in the current "
    "spec, so the preview does not claim the score's bar 0."
)

# One four-bar 4/4 gavotte cell: chordal frame, two bars of the Villa roll,
# then the chordal close. The tile repeats, so an eight-bar fixture is the
# cell twice.
SUITE_GAVOTTA_BAAB = SentenceSpec(
    id=SUITE_GAVOTTA_BAAB_ID,
    pattern="villa_pattern",
    meter="4/4",
    select=Select(length_min=4),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=1, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=2, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=3, bars=1, figure=VILLA_CHORD_MELODY),
    ),
)


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_suite_gavotta(
    path: str | Path = SUITE_GAVOTTA_PATH,
) -> tuple[SentenceSpec, ...]:
    """Parse the Suite Gavotta candidate JSON without touching the registry."""
    return load_candidate(path)


def suite_gavotta_spec(path: str | Path = SUITE_GAVOTTA_PATH) -> SentenceSpec:
    """The single candidate sentence from the authored file."""
    specs = load_suite_gavotta(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
