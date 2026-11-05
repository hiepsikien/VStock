"""Serve the committed example specs so the Studio UI does not copy JSON.

`GET /v1/studio/sentence/examples` returns one entry per authored spec:

    {"pattern": "villa_pattern", "meter": "4/4", "id": "villa_arpeggio_aba",
     "payload": {...}}

The sources are the committed files: `app/studio/specs/*.json` (Torroba/Sor,
written by `app.studio.export`) and `app/studio/candidates/*.json` (the Villa
and Barrios pilots). `payload` is one single-spec mapping, rebuilt with
`sentence_spec.spec_to_mapping`, so it is a valid body for `/validate` and the
`{spec, fixture}` half of `/preview`.

Order is deterministic: `(pattern, meter, id)`. Reading is uncached: the files
are small and a developer editing one should see it immediately.

This module only reads. It never registers a spec, so a candidate served here
still cannot reach the production planners.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.studio.candidates import CANDIDATES_DIR
from app.studio.export import SPECS_DIR
from app.studio.sentence_spec import parse_payload, spec_to_mapping

# Torroba/Sor first, then the candidate pilots. The final order does not depend
# on this tuple: entries are sorted by `(pattern, meter, id)`.
EXAMPLE_DIRS = (SPECS_DIR, CANDIDATES_DIR)


@dataclass(frozen=True)
class Example:
    pattern: str
    meter: str
    id: str
    payload: dict[str, Any]

    def as_response(self) -> dict[str, Any]:
        return {
            "pattern": self.pattern,
            "meter": self.meter,
            "id": self.id,
            "payload": self.payload,
        }


def _load() -> tuple[Example, ...]:
    found: list[Example] = []
    seen: dict[tuple[str, str, str], Path] = {}
    for directory in EXAMPLE_DIRS:
        for path in sorted(Path(directory).glob("*.json")):
            wrapper = json.loads(path.read_text(encoding="utf-8"))
            for spec in parse_payload(wrapper):
                key = (spec.pattern, spec.meter, spec.id)
                if key in seen:
                    raise ValueError(
                        f"{path}: duplicate example {spec.id!r} for "
                        f"{spec.pattern}/{spec.meter} (already in {seen[key]})"
                    )
                seen[key] = path
                found.append(
                    Example(
                        pattern=spec.pattern,
                        meter=spec.meter,
                        id=spec.id,
                        payload=spec_to_mapping(spec),
                    )
                )
    return tuple(sorted(found, key=lambda item: (item.pattern, item.meter, item.id)))


def examples() -> tuple[Example, ...]:
    """Every committed example spec, sorted deterministically."""
    return _load()


def examples_for(pattern: str) -> tuple[Example, ...]:
    """The committed example specs for one pattern (possibly empty)."""
    return tuple(item for item in _load() if item.pattern == pattern)
