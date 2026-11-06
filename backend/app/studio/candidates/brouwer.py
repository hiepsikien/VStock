"""Brouwer sentence candidate: an A-B-A pilot built from existing textures.

The authored source is `brouwer_aba.json`; this module is the code twin used to
prove the file round-trips and to give the preview a typed spec. Nothing here
calls `sentence_specs.register`, so production planners cannot see the
candidate.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.sonify.guitar_brouwer_figures import (
    BROUWER_ETUDE,
    BROUWER_NOVIEMBRE,
)
from app.sonify.sentence_specs import Select, SentenceSpec, Slot, Span
from app.studio.sentence_spec import parse_payload

CANDIDATES_DIR = Path(__file__).parent
BROUWER_ABA_PATH = CANDIDATES_DIR / "brouwer_aba.json"

BROUWER_ABA_ID = "brouwer_etude_noviembre_aba"

# Etude motor -> the lyrical ballad -> the motor again. The outer slots are the
# same texture, which is what makes the sentence an A-B-A rather than a
# one-way contrast.
BROUWER_ABA = SentenceSpec(
    id=BROUWER_ABA_ID,
    pattern="brouwer_etude",
    meter="4/4",
    select=Select(length_min=3),
    span=Span(tile=3, remainder="same_figure", truncate_to_length=True),
    slots=(
        Slot(start=0, bars=1, figure=BROUWER_ETUDE),
        Slot(start=1, bars=1, figure=BROUWER_NOVIEMBRE),
        Slot(start=2, bars=1, figure=BROUWER_ETUDE),
    ),
)


def load_candidate(path: str | Path) -> tuple[SentenceSpec, ...]:
    """Parse one v1 wrapper without touching the global registry."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_payload(payload)


def load_brouwer_aba(path: str | Path = BROUWER_ABA_PATH) -> tuple[SentenceSpec, ...]:
    """Parse the Brouwer candidate JSON without touching the global registry."""
    return load_candidate(path)


def brouwer_aba_spec(path: str | Path = BROUWER_ABA_PATH) -> SentenceSpec:
    """The single candidate sentence from the authored file."""
    specs = load_brouwer_aba(path)
    if len(specs) != 1:
        raise ValueError(f"{path}: expected one candidate spec, found {len(specs)}")
    return specs[0]
