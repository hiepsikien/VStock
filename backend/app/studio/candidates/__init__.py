"""Candidate-only sentence specs for the Studio pilots.

Nothing in this package is registered with `app.sonify.sentence_specs` at
import. A candidate is loaded straight from JSON into `SentenceSpec` objects and
handed to a preview; it never enters `SENTENCE_SPECS`, so production planners
cannot see it. These are authoring probes, not shipped archetypes.

The JSON file is the authored source. The Barrios builder now lives in the
production owner (`app.sonify.guitar_barrios_period`) and is re-exported here, so
the candidate and the feature-gated production spec cannot drift. The test still
compares the JSON with it.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.guitar_barrios_period import (
    BARRIOS_CATHEDRAL_PERIOD,
    BARRIOS_CATHEDRAL_PERIOD_ID,
)
from app.sonify.sentence_specs import SentenceSpec
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).parent
VILLA_ARPEGGIO_PATH = CANDIDATES_DIR / "villa_arpeggio.json"
BARRIOS_CATHEDRAL_PATH = CANDIDATES_DIR / "barrios_cathedral.json"

__all__ = [
    "BARRIOS_CATHEDRAL_PATH",
    "BARRIOS_CATHEDRAL_PERIOD",
    "BARRIOS_CATHEDRAL_PERIOD_ID",
    "VILLA_ARPEGGIO_PATH",
    "barrios_cathedral_spec",
    "load_barrios_cathedral",
    "load_candidate",
    "load_villa_candidate",
    "villa_candidate_spec",
]


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
