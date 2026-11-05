"""Deterministic builders for the Phase 0 selection and render matrices.

The two fixtures are golden artifacts, not runtime inputs:

* `sentence_selection_matrix.json` records what `plan_sentence`/`plan_run` pick
  for every registered `(pattern, meter)` over one bounded grid, plus one row
  per Villa/Barrios/Brouwer candidate from its preview plan.
* `render_matrix.json` renders one canonical selection per registered
  archetype and per candidate through the real Studio preview path. Notes are
  never hand-built here.

Both builders are pure functions of the committed code. The tests compare the
committed JSON with a fresh build; there is no `--update` path on purpose, so a
drift must be reviewed and committed by hand.
"""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from app.sonify import sentence_specs
from app.sonify.sentence_specs import SENTENCE_SPECS, SentenceSpec
from app.studio import barrios_preview, brouwer_preview, preview, villa_preview
from app.studio.barrios_preview import preview_barrios_period
from app.studio.brouwer_preview import preview_brouwer_sentence
from app.studio.candidates import barrios_cathedral_spec, villa_candidate_spec
from app.studio.candidates.brouwer import brouwer_aba_spec
from app.studio.villa_preview import preview_villa_sentence

MATRIX_VERSION = 1
FIXTURE_VERSION = 1
RENDERER_VERSION = 1
SELECTION_KIND = "sentence-selection"
RENDER_KIND = "sentence-render"

LENGTHS = tuple(range(1, 13))
NS = (0, 1, 2, 3)
CLOSES = (False, True)
RISES = (0, 1, 2)

VOICES = (1, 2, 3, 4)

FAMILY_OWNER = {
    "castillo": "torroba",
    "danza": "torroba",
    "fandanguillo": "torroba",
    "sonatina": "torroba",
    "galop": "classic",
    "villa_pattern": "villa",
    "preludio": "barrios",
    "brouwer_etude": "brouwer",
}


def _load_owners() -> None:
    for name in sentence_specs._OWNER_MODULES:
        importlib.import_module(name)


def _grid_axes() -> dict[str, list[Any]]:
    return {
        "lengths": list(LENGTHS),
        "n": list(NS),
        "closes": list(CLOSES),
        "rise": list(RISES),
    }


def _norm_spans(spans: list[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep only the stable placement fields; Barrios adds a pattern name."""
    return [
        {"figure": int(span["figure"]), "bars": [int(bar) for bar in span["bars"]]}
        for span in (spans or [])
    ]


# ---------------------------------------------------------------------------
# selection matrix


def _registered_rows() -> list[dict[str, Any]]:
    _load_owners()
    rows: list[dict[str, Any]] = []
    for (pattern, meter), specs in sorted(SENTENCE_SPECS.items()):
        kinds = {bool(spec.span.cycle) for spec in specs}
        if len(kinds) != 1:
            raise AssertionError(
                f"registered pair {(pattern, meter)} mixes cycle and figure specs"
            )
        cycle = kinds.pop()
        for length in LENGTHS:
            for n in NS:
                for closes in CLOSES:
                    for rise in RISES:
                        base = {
                            "pattern": pattern,
                            "meter": meter,
                            "length": length,
                            "n": n,
                            "closes": closes,
                            "rise": rise,
                        }
                        if cycle:
                            cells = sentence_specs.plan_run(pattern, meter, length)
                            if cells is None:
                                raise AssertionError(
                                    f"registered pair {(pattern, meter)} has no run plan"
                                )
                            rows.append(
                                {
                                    **base,
                                    "kind": "cell",
                                    "selected": bool(cells),
                                    "cells": list(cells),
                                }
                            )
                        else:
                            plan = sentence_specs.plan_sentence(
                                pattern,
                                meter,
                                length,
                                n,
                                closes=closes,
                                rise=rise,
                            )
                            if plan is None:
                                raise AssertionError(
                                    f"registered pair {(pattern, meter)} has no plan"
                                )
                            rows.append(
                                {
                                    **base,
                                    "kind": "figure",
                                    "selected": bool(plan),
                                    "spans": _norm_spans(
                                        [
                                            {"figure": figure, "bars": bars}
                                            for figure, bars in plan
                                        ]
                                    ),
                                }
                            )
    return rows


def candidate_cases() -> list[tuple[str, SentenceSpec, Any, Any]]:
    """`(family, spec, preview, resolve_fixture)` in a stable order."""
    return [
        (
            "villa",
            villa_candidate_spec(),
            preview_villa_sentence,
            villa_preview._resolve_fixture,
        ),
        (
            "barrios",
            barrios_cathedral_spec(),
            preview_barrios_period,
            barrios_preview._resolve_fixture,
        ),
        (
            "brouwer",
            brouwer_aba_spec(),
            preview_brouwer_sentence,
            brouwer_preview._resolve_fixture,
        ),
    ]


def _selection_axes(resolved: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "length": int(resolved["length"]),
        "n": int(resolved["n"]),
        "closes": bool(resolved["closes"]),
        "rise": int(resolved["rise"]),
    }


def _candidate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, spec, preview_fn, resolve in candidate_cases():
        resolved = resolve(spec, None)
        result = preview_fn(spec)
        if not result.ok:
            raise AssertionError(f"{spec.id}: preview failed: {result.errors}")
        plan = result.plan or {}
        rows.append(
            {
                "source": "candidate",
                "family": family,
                "id": spec.id,
                "pattern": spec.pattern,
                "meter": spec.meter,
                "kind": str(plan.get("kind")),
                **_selection_axes(resolved),
                "selected": bool(plan.get("selected")),
                "spans": _norm_spans(plan.get("spans")),
            }
        )
    return sorted(rows, key=lambda row: (row["family"], row["id"]))


def selection_payload() -> dict[str, Any]:
    """The exact JSON body for `sentence_selection_matrix.json`."""
    return {
        "version": MATRIX_VERSION,
        "kind": SELECTION_KIND,
        "grid": _grid_axes(),
        "rows": _registered_rows(),
        "candidates": _candidate_rows(),
    }


# ---------------------------------------------------------------------------
# render matrix


def _render_fixture(
    spec: SentenceSpec, resolved: Mapping[str, Any]
) -> dict[str, Any]:
    """The fixture actually handed to the preview (and replayable from JSON)."""
    return {
        "length" if not spec.span.cycle else "run_length": int(resolved["length"]),
        "n": int(resolved["n"]),
        "closes": bool(resolved["closes"]),
        "rise": int(resolved["rise"]),
        "bars": int(resolved["bars"]),
    }


def _voice_counts(notes: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {str(voice): 0 for voice in VOICES}
    for note in notes:
        key = str(int(note["voice"]))
        counts[key] = counts.get(key, 0) + 1
    return counts


def voice_counts(notes: list[Mapping[str, Any]]) -> dict[str, int]:
    """Public alias used by the render test to recompute per-voice counts."""
    return _voice_counts(notes)


def _render_row(
    *,
    source: str,
    family: str,
    spec: SentenceSpec,
    fixture: Mapping[str, Any],
    result,
) -> dict[str, Any]:
    notes = list(result.notes)
    row: dict[str, Any] = {
        "source": source,
        "family": family,
        "id": spec.id,
        "pattern": spec.pattern,
        "meter": spec.meter,
        "fixture": dict(fixture),
        "note_count": len(notes),
        "voice_counts": _voice_counts(notes),
        "renderHash": result.render_hash,
        "renderer_version": RENDERER_VERSION,
        "fixture_version": FIXTURE_VERSION,
    }
    if not result.ok or not notes:
        row["expected_empty"] = True
        row["reason"] = (
            "preview returned no notes"
            if result.ok
            else "; ".join(error.message for error in result.errors)
        )
    return row


def _registered_render_rows() -> list[dict[str, Any]]:
    _load_owners()
    rows: list[dict[str, Any]] = []
    for (pattern, meter), specs in sorted(SENTENCE_SPECS.items()):
        for spec in specs:
            resolved = preview._resolve_fixture(spec, None)
            fixture = _render_fixture(spec, resolved)
            result = preview.preview_spec(spec, fixture)
            rows.append(
                _render_row(
                    source="registry",
                    family=FAMILY_OWNER[pattern],
                    spec=spec,
                    fixture=fixture,
                    result=result,
                )
            )
    return rows


def _candidate_render_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, spec, preview_fn, resolve in candidate_cases():
        resolved = resolve(spec, None)
        fixture = _render_fixture(spec, resolved)
        result = preview_fn(spec, fixture)
        rows.append(
            _render_row(
                source="candidate",
                family=family,
                spec=spec,
                fixture=fixture,
                result=result,
            )
        )
    return rows


def render_payload() -> dict[str, Any]:
    """The exact JSON body for `render_matrix.json`."""
    rows = _registered_render_rows() + _candidate_render_rows()
    rows.sort(key=lambda row: (row["source"], row["family"], row["id"]))
    return {
        "version": MATRIX_VERSION,
        "kind": RENDER_KIND,
        "renderer_version": RENDERER_VERSION,
        "fixture_version": FIXTURE_VERSION,
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# replay helpers shared by both tests


def spec_by_id() -> dict[str, SentenceSpec]:
    _load_owners()
    found: dict[str, SentenceSpec] = {}
    for specs in SENTENCE_SPECS.values():
        for spec in specs:
            found[spec.id] = spec
    for _family, spec, _preview, _resolve in candidate_cases():
        found[spec.id] = spec
    return found


def registered_pairs() -> set[tuple[str, str]]:
    _load_owners()
    return set(SENTENCE_SPECS)


def registered_spec_ids() -> set[str]:
    _load_owners()
    return {spec.id for specs in SENTENCE_SPECS.values() for spec in specs}


def candidate_families() -> set[str]:
    return {family for family, _spec, _preview, _resolve in candidate_cases()}


def candidate_previews() -> dict[str, Any]:
    """The preview entry point for each candidate id, so a test can replay it."""
    return {
        spec.id: preview_fn
        for _family, spec, preview_fn, _resolve in candidate_cases()
    }


def candidate_ids() -> dict[str, str]:
    return {family: spec.id for family, spec, _preview, _resolve in candidate_cases()}
