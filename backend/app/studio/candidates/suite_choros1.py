"""Suite Popular Brasileira candidate: Choros No. 1, provisional 4/4.

The score's 2/4 vs 4/4 is still open, so this candidate uses 4/4 as the
provisional engine meter, matching the audit's working assumption. If the
source turns out to be 2/4 it needs the same `fold: 2` decision as Schottish,
not a new `Meter`. `METER_CAVEAT` records that the cell is a texture probe
rather than a transcription.

The authored source is `suite_choros1.json`; this module is its code twin and
gives the preview a typed spec. Nothing here calls `sentence_specs.register`,
so production planners cannot see the candidate.

The sentence is one four-bar 4/4 choro cell over the existing `villa_pattern`
parent, which already has a real 4/4 branch in `guitar_villa.py`:

    bar 0   A  arpeggio
    bar 1   B  chord melody
    bar 2   B  chord melody
    bar 3   A  arpeggio

The A-B-B-A cell keeps the choro's bass-and-chord texture and closes on the
same roll it opened with. That is deliberately different from the other 4/4
candidates: `villa_arpeggio_aba` is A-B-A, Schottish is folded A-B-A-B, and
Gavotta is chordal B-A-A-B. Both figures are the bar-level adapters in
`guitar_villa_figures.py`; the note content still comes from the production
writers. `etude1`/`etude11` are left out because their study cycles are not
evidence for a choro, and `thumb_cantabile` is a phrase-level writer, not a bar
figure.

The Suite movement id `suite_choros1` is deliberately *not* used as the
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
SUITE_CHOROS1_PATH = CANDIDATES_DIR / "suite_choros1.json"

SUITE_CHOROS1_ABBA_ID = "suite_choros1_arpeggio_abba"

# 4/4 is provisional, not evidence. If the score is 2/4 this reuses the
# Schottish fold decision rather than inventing a 2/4 Meter.
PROVISIONAL_METER = True
METER_CAVEAT = (
    "Choros No. 1 is authored at a provisional 4/4 because the score's 2/4 vs "
    "4/4 is still open. If the source is 2/4 it needs the same fold: 2 "
    "decision as Schottish rather than a new Meter, so this candidate is a "
    "texture probe, not a transcription."
)

# One four-bar 4/4 choro cell: roll, two chord-melody bars, roll. The tile
# repeats, so an eight-bar fixture is the cell twice.
SUITE_CHOROS1_ABBA = SentenceSpec(
    id=SUITE_CHOROS1_ABBA_ID,
    pattern="villa_pattern",
    meter="4/4",
    select=Select(length_min=4),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=2, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=3, bars=1, figure=VILLA_ARPEGGIO),
    ),
)


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_suite_choros1(
    path: str | Path = SUITE_CHOROS1_PATH,
) -> tuple[SentenceSpec, ...]:
    """Parse the Choros No. 1 candidate JSON without touching the registry."""
    return load_candidate(path)


def suite_choros1_spec(path: str | Path = SUITE_CHOROS1_PATH) -> SentenceSpec:
    """The single candidate sentence from the authored file."""
    specs = load_suite_choros1(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
