"""Candidate-only sentence specs for the Studio pilots.

Nothing in this package is registered with `app.sonify.sentence_specs`. A
candidate is loaded straight from JSON into `SentenceSpec` objects and handed to
a preview; it never enters `SENTENCE_SPECS`, so production planners cannot see
it. These are authoring probes, not shipped archetypes.

The JSON file is the authored source; the Barrios builder is the code twin used
to prove the file round-trips. Keep them in sync and let the test compare them.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.guitar_barrios_figures import BARRIOS_PRELUDIO, BARRIOS_TREMOLO
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).parent
VILLA_ARPEGGIO_PATH = CANDIDATES_DIR / "villa_arpeggio.json"
BARRIOS_CATHEDRAL_PATH = CANDIDATES_DIR / "barrios_cathedral.json"

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


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_villa_candidate() -> tuple[SentenceSpec, ...]:
    return load_candidate(VILLA_ARPEGGIO_PATH)


def villa_candidate_spec() -> SentenceSpec:
    """The single Villa candidate spec, or a loud failure if the file drifts."""
    specs = load_villa_candidate()
    if len(specs) != 1:
        raise ValueError(
            f"{VILLA_ARPEGGIO_PATH}: expected exactly one candidate, got {len(specs)}"
        )
    return specs[0]


def load_barrios_cathedral(
    path: str | Path = BARRIOS_CATHEDRAL_PATH,
) -> tuple[SentenceSpec, ...]:
    """Parse the Barrios candidate JSON without touching the global registry."""
    return load_candidate(path)


def barrios_cathedral_spec(
    path: str | Path = BARRIOS_CATHEDRAL_PATH,
) -> SentenceSpec:
    """The single candidate period from the authored file."""
    specs = load_barrios_cathedral(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
