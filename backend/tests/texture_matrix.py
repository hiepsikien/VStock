"""Deterministic builders for the Phase 0 selection and render matrices.

The three fixtures are golden artifacts, not runtime inputs:

* `sentence_selection_matrix.json` records what `plan_sentence`/`plan_run` pick
  for every registered `(pattern, meter)` over one bounded grid, plus one row
  per Villa/Barrios/Brouwer candidate from its preview plan.
* `pattern_selection_matrix.json` drives the pattern-level chooser
  (`_select_body` or the real `_patterns` path) with one deterministic witness
  per `(ensemble, pattern)` in `PROFILES`, plus the frame-path `pedal` id.
* `render_matrix.json` renders one canonical selection per registered
  archetype and per candidate through the real Studio preview path. Notes are
  never hand-built here.

All builders are pure functions of the committed code. The tests compare the
committed JSON with a fresh build; there is no `--update` path on purpose, so a
drift must be reviewed and committed by hand.
"""

from __future__ import annotations

import importlib
from typing import Any, Mapping

from app.sonify import sentence_specs
from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _patterns, _select_body
from app.sonify.guitar_wave import PROFILES
from app.sonify.params import DEFAULT_PARAMS, compose_params
from app.sonify.sentence_specs import SENTENCE_SPECS, SentenceSpec
from app.studio import barrios_preview, brouwer_preview, preview, villa_preview
from app.studio.barrios_preview import preview_barrios_period
from app.studio.brouwer_preview import preview_brouwer_sentence
from app.studio.candidates import barrios_cathedral_spec, villa_candidate_spec
from app.studio.candidates.brouwer import brouwer_aba_spec
from app.studio.candidates.suite_choros1 import suite_choros1_spec
from app.studio.candidates.suite_gavotta import suite_gavotta_spec
from app.studio.candidates.suite_mazurka import suite_mazurka_spec
from app.studio.candidates.suite_schottish import suite_schottish_spec
from app.studio.candidates.suite_valsa import suite_valsa_spec
from app.studio.villa_preview import preview_villa_sentence
from tests.guitar_fixture import meter_named, pattern_case

MATRIX_VERSION = 1
FIXTURE_VERSION = 1
RENDERER_VERSION = 1
SELECTION_KIND = "sentence-selection"
PATTERN_SELECTION_KIND = "pattern-selection"
RENDER_KIND = "sentence-render"
PATTERN_MATRIX_VERSION = 1
PATTERN_PHASE = "current"

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
            "villa",
            suite_mazurka_spec(),
            preview_villa_sentence,
            villa_preview._resolve_fixture,
        ),
        (
            "villa",
            suite_valsa_spec(),
            preview_villa_sentence,
            villa_preview._resolve_fixture,
        ),
        (
            "villa",
            suite_schottish_spec(),
            preview_villa_sentence,
            villa_preview._resolve_fixture,
        ),
        (
            "villa",
            suite_gavotta_spec(),
            preview_villa_sentence,
            villa_preview._resolve_fixture,
        ),
        (
            "villa",
            suite_choros1_spec(),
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
# pattern selection matrix

# The witness grid is walked in this exact order; the first input that makes
# the real chooser return a profile id becomes that id's row. Reordering an
# axis rewrites the fixture, which is a review event, not a silent update.
PATTERN_METERS = ("3/4", "4/4", "6/8")
PATTERN_MOODS: tuple[str | None, ...] = ("calm", "rally", "selloff", "volatile", None)
PATTERN_BANDS = ("mf", "p", "f")
PATTERN_BPMS = (96, 84, 108, 72, 60, 120)
PATTERN_FIRST_BODY = (True, False)
PATTERN_PREVIOUS = ((), ("tremolo", "tremolo"))
PATTERN_REL_SPANS = (0.02, 0.004)
PATTERN_BARS = 8
PATTERN_DRIVERS = ("select_body", "patterns")
PATTERN_SECTION_VARIANTS = ("none", "trio", "bridge", "framed", "pedal")

# `pedal` is the frame path, not an ensemble-owned body row. The star keeps it
# out of the PROFILES pair coverage while still recording a real `_patterns`
# hit; the id itself is in `_FAMILY`, so leaving it out would be dead data.
FRAME_ENSEMBLE = "*"
PROBE_PATTERN = "probe"

# An id in `PROFILES` that no selection rule can emit. The dead-code test
# requires a reason here; the row records the deterministic probe it ran and
# the pattern that probe actually selected, so the gap stays inspectable.
PATTERN_UNREACHABLE_REASONS = {
    "sonatina": (
        "no Torroba selector emits sonatina: TORROBA_PRIMARY_RULES and "
        "TORROBA_CONTRAST_RULES never return it, and the technique knob in "
        "_dominant_pattern returns castillo/torroba_tremolo/danza. The only "
        "sonatina returns are naming fallbacks in _owning_pattern, "
        "_fallback_body_pattern, and headline_id, not selection. Its sentence "
        "specs belong to the sentence-level matrix."
    ),
    "suite_mazurka": (
        "Villa returns suite_mazurka only when VSTOCK_SUITE_MAZURKA is on and "
        "the movement is a whole 3/4 Villa body with no pedal bars. This "
        "matrix runs with the flag off, so the historical Villa ladder answers."
    ),
    "suite_valsa": (
        "Villa returns suite_valsa only when VSTOCK_SUITE_VALSA is on and the "
        "movement is a whole 3/4 Villa body of at least eight bars with no "
        "pedal bars. This matrix runs with the flag off, so the historical "
        "Villa ladder answers."
    ),
    "suite_gavotta": (
        "Villa returns suite_gavotta only when VSTOCK_SUITE_GAVOTTA is on and "
        "the movement is a whole 4/4 Villa body of at least four bars with no "
        "pedal bars. This matrix runs with the flag off, so the historical "
        "Villa ladder answers."
    ),
    "suite_schottish": (
        "Villa returns suite_schottish only when VSTOCK_SUITE_SCHOTTISH is on "
        "and the movement is a whole 4/4 Villa body of at least four bars with "
        "no pedal bars. This matrix runs with the flag off, so the historical "
        "Villa ladder answers."
    ),
    "suite_choros1": (
        "Villa returns suite_choros1 only when VSTOCK_SUITE_CHOROS1 is on and "
        "the movement is a whole 4/4 Villa body of at least four bars with no "
        "pedal bars. This matrix runs with the flag off, so the historical "
        "Villa ladder answers."
    ),
}


def _section_row(section: FormSection) -> dict[str, Any]:
    return {
        "start": section.start,
        "end": section.end,
        "kind": section.kind,
        "regime_slot": section.regime_slot,
        "bridge": bool(section.bridge),
        "trio": bool(section.trio),
    }


def _section_from_row(row: Mapping[str, Any]) -> FormSection:
    return FormSection(
        int(row["start"]),
        int(row["end"]),
        str(row["kind"]),
        int(row["regime_slot"]),
        bridge=bool(row["bridge"]),
        trio=bool(row["trio"]),
    )


def _variant(
    name: str, bars: int, first_body: bool
) -> tuple[dict | None, list[dict] | None]:
    """One form variant, as JSON-able rows: a single section or a whole form."""
    slot = 0 if first_body else 1
    if name == "none":
        return None, None
    if name == "trio":
        return _section_row(FormSection(0, bars, "phrase", slot, trio=True)), None
    if name == "bridge":
        return _section_row(FormSection(0, bars, "phrase", slot, bridge=True)), None
    if name == "framed":
        return None, [
            _section_row(FormSection(0, 1, "intro", 0)),
            _section_row(FormSection(1, bars, "phrase", slot)),
        ]
    if name == "pedal":
        return None, [_section_row(FormSection(0, bars, "intro", slot))]
    raise AssertionError(f"unknown pattern-matrix section variant {name!r}")


def _pattern_inputs(ensemble: str):
    """Deterministic candidate inputs for one ensemble, in witness order.

    A single phrase is enough: the phrase selector reads `first_body`,
    `previous`, and the section beside the context, and the macro selector
    reads the framed form. `sections=` is only used with the full `_patterns`
    path; `section=` only with `_select_body`, mirroring production.
    """
    for driver in PATTERN_DRIVERS:
        for meter in PATTERN_METERS:
            for mood in PATTERN_MOODS:
                for band in PATTERN_BANDS:
                    for bpm in PATTERN_BPMS:
                        for first_body in PATTERN_FIRST_BODY:
                            for previous in PATTERN_PREVIOUS:
                                for rel_span in PATTERN_REL_SPANS:
                                    for variant in PATTERN_SECTION_VARIANTS:
                                        if driver == "select_body" and variant in {
                                            "framed",
                                            "pedal",
                                        }:
                                            continue
                                        if driver == "patterns" and variant not in {
                                            "framed",
                                            "pedal",
                                        }:
                                            continue
                                        section, sections = _variant(
                                            variant, PATTERN_BARS, first_body
                                        )
                                        yield {
                                            "ensemble": ensemble,
                                            "pattern": PROBE_PATTERN,
                                            "driver": driver,
                                            "meter": meter,
                                            "mood": mood,
                                            "band": band,
                                            "bpm": bpm,
                                            "bars": PATTERN_BARS,
                                            "first_body": first_body,
                                            "previous": list(previous),
                                            "section": section,
                                            "sections": sections,
                                            "rel_span": rel_span,
                                        }


def _ctx_from_input(row: Mapping[str, Any]):
    section = (
        _section_from_row(row["section"]) if row["section"] is not None else None
    )
    sections = (
        [_section_from_row(item) for item in row["sections"]]
        if row["sections"] is not None
        else None
    )
    return pattern_case(
        str(row["pattern"]),
        meter_named(str(row["meter"])),
        ensemble=str(row["ensemble"]),
        mood=row["mood"],
        band=str(row["band"]),
        bpm=int(row["bpm"]),
        bars=int(row["bars"]),
        first_body=bool(row["first_body"]),
        previous=[str(item) for item in row["previous"]],
        section=section,
        sections=sections,
        rel_span=float(row["rel_span"]),
    )


def run_pattern_input(row: Mapping[str, Any]) -> tuple[str, str]:
    """Run one matrix row through the real chooser; return `(selected, ctx_kind)`.

    `select_body` is the per-phrase selector and takes the three selection
    inputs explicitly. `patterns` is the renderer's dispatcher, so a framed
    row reaches `_assign_macro`/`_dominant_pattern_auto` unchanged.
    """
    data = row["input"]
    driver = row["driver"]
    ctx, phrases = _ctx_from_input(data)
    if driver == "select_body":
        section = ctx.section(phrases[0].start // max(ctx.epb, 1))
        selected = _select_body(
            ctx,
            phrases[0],
            first_body=bool(data["first_body"]),
            previous=[str(item) for item in data["previous"]],
            section=section,
        )
    elif driver == "patterns":
        chosen = _patterns(ctx)
        if len(chosen) != 1:
            raise AssertionError(
                f"pattern matrix expects one phrase, got {len(chosen)} selections"
            )
        selected = chosen[0]
    else:
        raise AssertionError(f"unknown pattern-matrix driver {driver!r}")
    return selected, ctx.kind


def _run_probe(probe: Mapping[str, Any]) -> tuple[str, str]:
    """Run a flat candidate input by wrapping it in the matrix row shape."""
    return run_pattern_input({"driver": probe["driver"], "input": probe})


def _pattern_witnesses(ensemble: str) -> dict[str, tuple[dict[str, Any], str]]:
    """First deterministic input that selects each id, for one ensemble."""
    found: dict[str, tuple[dict[str, Any], str]] = {}
    for probe in _pattern_inputs(ensemble):
        selected, kind = _run_probe(probe)
        found.setdefault(selected, (probe, kind))
    return found


def _pattern_row(
    probe: Mapping[str, Any],
    *,
    target: str,
    selected: str | None,
    ctx_kind: str,
    expected_empty: bool,
    observed: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "phase": PATTERN_PHASE,
        "driver": str(probe["driver"]),
        "input": {
            **{key: value for key, value in probe.items() if key != "driver"},
            "pattern": target,
        },
        "ctx_kind": ctx_kind,
        "selected_pattern": selected,
        "selected_sentence": None,
        "expected_empty": expected_empty,
    }
    if expected_empty:
        row["observed_pattern"] = observed
        row["reason"] = reason
    return row


def _pattern_rows() -> list[dict[str, Any]]:
    witnesses: dict[str, dict[str, tuple[dict[str, Any], str]]] = {}
    rows: list[dict[str, Any]] = []
    for ensemble, pattern in sorted(PROFILES):
        if ensemble not in witnesses:
            witnesses[ensemble] = _pattern_witnesses(ensemble)
        found = witnesses[ensemble]
        if pattern in found:
            probe, kind = found[pattern]
            rows.append(
                _pattern_row(
                    probe,
                    target=pattern,
                    selected=pattern,
                    ctx_kind=kind,
                    expected_empty=False,
                )
            )
            continue
        reason = PATTERN_UNREACHABLE_REASONS.get(pattern)
        if reason is None:
            raise AssertionError(
                f"{(ensemble, pattern)} has no witness and no expected_empty reason"
            )
        canonical = next(_pattern_inputs(ensemble))
        observed, kind = _run_probe(canonical)
        rows.append(
            _pattern_row(
                canonical,
                target=pattern,
                selected=None,
                ctx_kind=kind,
                expected_empty=True,
                observed=observed,
                reason=reason,
            )
        )

    frame = _pattern_witnesses(FRAME_ENSEMBLE)
    if "pedal" not in frame:
        raise AssertionError("the frame path no longer selects pedal")
    probe, kind = frame["pedal"]
    rows.append(
        _pattern_row(
            probe,
            target="pedal",
            selected="pedal",
            ctx_kind=kind,
            expected_empty=False,
        )
    )
    rows.sort(key=lambda row: (row["input"]["ensemble"], row["input"]["pattern"]))
    return rows


def pattern_payload() -> dict[str, Any]:
    """The exact JSON body for `pattern_selection_matrix.json`."""
    with compose_params(DEFAULT_PARAMS):
        rows = _pattern_rows()
    return {
        "version": PATTERN_MATRIX_VERSION,
        "kind": PATTERN_SELECTION_KIND,
        "phase": PATTERN_PHASE,
        "grid": {
            "drivers": list(PATTERN_DRIVERS),
            "meters": list(PATTERN_METERS),
            "moods": list(PATTERN_MOODS),
            "bands": list(PATTERN_BANDS),
            "bpms": list(PATTERN_BPMS),
            "first_body": list(PATTERN_FIRST_BODY),
            "previous": [list(item) for item in PATTERN_PREVIOUS],
            "rel_span": list(PATTERN_REL_SPANS),
            "bars": PATTERN_BARS,
            "sections": list(PATTERN_SECTION_VARIANTS),
        },
        "rows": rows,
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


def candidate_ids() -> dict[str, tuple[str, ...]]:
    """Candidate ids grouped by family; a family may own more than one meter.

    Villa already owns six preview candidates (the 4/4 arpeggio, the two 3/4
    Suite movements Mazurka and Valsa, and the three 4/4 Suite movements
    Schottish, Gavotta, and Choros No. 1), so this cannot be a
    one-id-per-family map.
    """
    grouped: dict[str, list[str]] = {}
    for family, spec, _preview, _resolve in candidate_cases():
        grouped.setdefault(family, []).append(spec.id)
    return {
        family: tuple(sorted(ids)) for family, ids in sorted(grouped.items())
    }
