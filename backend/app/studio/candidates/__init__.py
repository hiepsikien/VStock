"""Candidate-only sentence specs.

These specs are authoring probes, not runtime data. Nothing here calls
`sentence_specs.register()` and nothing is added to `SENTENCE_SPECS`, so a
production plan cannot see a candidate. Preview them with
`app.studio.barrios_preview.preview_barrios_period`.

The JSON file is the authored source; the builder is the code twin used to
prove the file round-trips. Keep the two in sync and let the test compare them.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.guitar_barrios_figures import BARRIOS_PRELUDIO, BARRIOS_TREMOLO
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).with_name("barrios_cathedral.json")

BARRIOS_CATHEDRAL_PERIOD_ID = "barrios_cathedral_period"

# Preludio Saudade -> the tremolo apex -> the opening frame again. The middle
# slot is the guest; the outer slots are the same texture, which is what makes
# it a period rather than a one-way movement.
BARRIOS_CATHEDRAL_PERIOD = SentenceSpec(
    id=BARRIOS_CATHEDRAL_PERIOD_ID,
    pattern="preludio",
    meter="4/4",
    select=Select(length_min=12, length_max=12),
    span=Span(tile=12, exact=True, remainder="exact"),
    slots=(
        Slot(start=0, bars=4, figure=BARRIOS_PRELUDIO),
        Slot(start=4, bars=4, figure=BARRIOS_TREMOLO),
        Slot(start=8, bars=4, figure=BARRIOS_PRELUDIO),
    ),
)


def load_barrios_cathedral(
    path: str | Path = CANDIDATES_DIR,
) -> tuple[SentenceSpec, ...]:
    """Parse the candidate JSON without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def barrios_cathedral_spec(path: str | Path = CANDIDATES_DIR) -> SentenceSpec:
    """The single candidate period from the authored file."""
    specs = load_barrios_cathedral(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
