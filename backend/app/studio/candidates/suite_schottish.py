"""Suite Popular Brasileira candidate: Schottish-Choro, a folded 4/4 probe.

The source signature is 2/4 and `form.Meter` has no 2/4. This candidate
therefore uses the existing 4/4 engine as a stand-in: one rendered bar stands
for **two folded 2/4 source bars** (`fold: 2`, §4.4.1). The fold itself is not
landed in `span.py`, so `METER_CAVEAT` records that the preview is a meter
proxy, not a transcription, and the bar count is a folded count.

The authored source is `suite_schottish.json`; this module is its code twin and
gives the preview a typed spec. Nothing here calls `sentence_specs.register`,
so production planners cannot see the candidate.

The sentence is one four-bar folded phrase over the existing `villa_pattern`
parent, which already has a real 4/4 branch in `guitar_villa.py`:

    folded bar 0   A  arpeggio    (source bars 0-1)
    folded bar 1   B  chord       (source bars 2-3)
    folded bar 2   A  arpeggio    (source bars 4-5)
    folded bar 3   B  chord       (source bars 6-7)

The alternation is deliberate: each engine bar is one source bar-pair, so the
phrase reads as a two-bar 2/4 cell repeated, not as a four-bar 4/4 melody. Both
figures are the bar-level adapters in `guitar_villa_figures.py`; the note
content still comes from the production writers. `etude1`/`etude11` are left
out because their study cycles are not evidence for a schottische, and
`thumb_cantabile` is a phrase-level writer, not a bar figure.

The Suite movement id `suite_schottish` is deliberately *not* used as the
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
SUITE_SCHOTTISH_PATH = CANDIDATES_DIR / "suite_schottish.json"

SUITE_SCHOTTISH_ABAB_ID = "suite_schottish_arpeggio_abab"

# The 2/4 source and the stand-in the preview can actually render. Keeping
# these as data lets a test assert the caveat instead of reading prose.
SOURCE_METER = "2/4"
ENGINE_METER = "4/4"
FORM_FOLD = 2
METER_CAVEAT = (
    "The source is 2/4 and form.Meter has no 2/4. This candidate uses the "
    "existing 4/4 engine as a stand-in: one engine bar stands for two folded "
    "2/4 source bars (fold: 2). The fold is not landed in span.py, so the "
    "preview is a meter proxy, not a transcription of the score."
)

# One four-bar folded phrase: two source bar-pairs of the Villa roll answered
# by two source bar-pairs of block chords. The tile repeats, so an eight-bar
# fixture is the phrase twice in folded bars.
SUITE_SCHOTTISH_ABAB = SentenceSpec(
    id=SUITE_SCHOTTISH_ABAB_ID,
    pattern="villa_pattern",
    meter=ENGINE_METER,
    select=Select(length_min=4),
    span=Span(tile=4, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=1, bars=1, figure=VILLA_CHORD_MELODY),
        Slot(start=2, bars=1, figure=VILLA_ARPEGGIO),
        Slot(start=3, bars=1, figure=VILLA_CHORD_MELODY),
    ),
    role="A",
)


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_suite_schottish(
    path: str | Path = SUITE_SCHOTTISH_PATH,
) -> tuple[SentenceSpec, ...]:
    """Parse the Suite Schottish candidate JSON without touching the registry."""
    return load_candidate(path)


def suite_schottish_spec(path: str | Path = SUITE_SCHOTTISH_PATH) -> SentenceSpec:
    """The single candidate sentence from the authored file."""
    specs = load_suite_schottish(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
