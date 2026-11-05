"""Candidate-only sentence specs for the Studio pilot.

Nothing in this package is registered with `app.sonify.sentence_specs`. A
candidate is loaded straight from JSON into `SentenceSpec` objects and handed to
a preview; it never enters `SENTENCE_SPECS`, so production planners cannot see
it. This is the authoring target for the Villa sentence pilot, not a shipped
archetype.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.sentence_specs import SentenceSpec
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).parent
VILLA_ARPEGGIO_PATH = CANDIDATES_DIR / "villa_arpeggio.json"


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_villa_candidate() -> tuple[SentenceSpec, ...]:
    return load_candidate(VILLA_ARPEGGIO_PATH)


def villa_candidate_spec() -> SentenceSpec:
    """The single candidate spec, or a loud failure if the file drifts."""
    specs = load_villa_candidate()
    if len(specs) != 1:
        raise ValueError(
            f"{VILLA_ARPEGGIO_PATH}: expected exactly one candidate, got {len(specs)}"
        )
    return specs[0]
