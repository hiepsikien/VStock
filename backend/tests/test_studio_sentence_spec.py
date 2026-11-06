"""Studio JSON schema, export, and loader parity.

The JSON is an authoring source and test fixture only. These tests prove that
exporting every pilot row, loading it into a fresh registry, and planning from
it reproduces the code registry exactly.
"""

from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path

import pytest

import app.sonify.guitar_sor  # noqa: F401  (registers the galop cycle)
import app.sonify.guitar_torroba  # noqa: F401  (registers the Torroba rows)
from app.sonify.sentence_specs import (
    SENTENCE_SPECS,
    load_specs,
    plan_run,
    plan_sentence,
)
from app.studio.export import (
    PILOT_PATTERNS,
    SPECS_DIR,
    export_specs,
    spec_filename,
    stale_specs,
)
from app.studio.sentence_spec import (
    SCHEMA_VERSION,
    parse_payload,
    parse_spec,
    spec_to_mapping,
    specs_to_payload,
)

PILOT_ROWS = {
    key: specs for key, specs in SENTENCE_SPECS.items() if key[0] in PILOT_PATTERNS
}
METERS = ("3/4", "4/4", "6/8", "*")
PLAN_LENGTHS = range(1, 11)
PLAN_PHASES = range(0, 6)
PLAN_CLOSES = (False, True)
PLAN_RISES = (0, 1, 2)
RUN_LENGTHS = range(1, 13)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Registry edits in these tests must not leak into other tests."""
    saved = dict(SENTENCE_SPECS)
    try:
        yield
    finally:
        SENTENCE_SPECS.clear()
        SENTENCE_SPECS.update(saved)


@pytest.fixture(scope="module")
def pilot_payload() -> dict:
    return specs_to_payload(PILOT_ROWS[("castillo", "3/4")])


def _wrapper(*specs: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "runtime": "code",
        "specs": list(specs),
    }


def _load_exported(directory: Path) -> None:
    for path in sorted(directory.glob("*.json")):
        load_specs(path)


def test_export_load_round_trip(tmp_path: Path) -> None:
    before = dict(SENTENCE_SPECS)
    paths = export_specs(tmp_path)

    assert {path.name for path in paths} == {
        spec_filename(pattern, meter) for pattern, meter in PILOT_ROWS
    }

    SENTENCE_SPECS.clear()
    _load_exported(tmp_path)

    assert dict(SENTENCE_SPECS) == before
    assert {
        key: specs for key, specs in SENTENCE_SPECS.items() if key[0] in PILOT_PATTERNS
    } == PILOT_ROWS


def test_committed_spec_files_are_current() -> None:
    assert stale_specs(SPECS_DIR) == []
    committed = sorted(path.name for path in SPECS_DIR.glob("*.json"))
    assert committed == sorted(
        spec_filename(pattern, meter) for pattern, meter in PILOT_ROWS
    )


def _sentence_matrix() -> dict[tuple[str, str, int, int, bool, int], object]:
    out: dict[tuple[str, str, int, int, bool, int], object] = {}
    for pattern in PILOT_PATTERNS:
        for meter in METERS:
            for length in PLAN_LENGTHS:
                for n in PLAN_PHASES:
                    for closes in PLAN_CLOSES:
                        for rise in PLAN_RISES:
                            out[(pattern, meter, length, n, closes, rise)] = (
                                plan_sentence(
                                    pattern,
                                    meter,
                                    length,
                                    n,
                                    closes=closes,
                                    rise=rise,
                                )
                            )
    return out


def _run_matrix() -> dict[tuple[str, str, int], object]:
    return {
        (pattern, meter, length): plan_run(pattern, meter, length)
        for pattern in PILOT_PATTERNS
        for meter in METERS
        for length in RUN_LENGTHS
    }


def test_plan_outputs_are_unchanged_after_load(tmp_path: Path) -> None:
    before_sentence = _sentence_matrix()
    before_run = _run_matrix()

    export_specs(tmp_path)
    SENTENCE_SPECS.clear()
    _load_exported(tmp_path)

    assert _sentence_matrix() == before_sentence
    assert _run_matrix() == before_run


def test_parse_payload_does_not_touch_the_registry(pilot_payload: dict) -> None:
    before = dict(SENTENCE_SPECS)
    specs = parse_payload(pilot_payload)
    assert dict(SENTENCE_SPECS) == before
    assert specs == PILOT_ROWS[("castillo", "3/4")]


def test_parse_spec_round_trips_every_pilot_row() -> None:
    for specs in PILOT_ROWS.values():
        for spec in specs:
            assert parse_spec(spec_to_mapping(spec)) == spec


def test_rejects_wrong_schema_version(pilot_payload: dict) -> None:
    payload = copy.deepcopy(pilot_payload)
    payload["schema_version"] = 2
    with pytest.raises(ValueError, match=r"^schema_version:"):
        parse_payload(payload)


def test_rejects_wrong_runtime(pilot_payload: dict) -> None:
    payload = copy.deepcopy(pilot_payload)
    payload["runtime"] = "python"
    with pytest.raises(ValueError, match=r"^runtime:"):
        parse_payload(payload)


def test_rejects_bad_figure(pilot_payload: dict) -> None:
    payload = copy.deepcopy(pilot_payload)
    payload["specs"][0]["slots"][0]["figure"] = "8"
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\]\.figure:"):
        parse_payload(payload)


def test_rejects_slot_without_a_realizer(pilot_payload: dict) -> None:
    payload = copy.deepcopy(pilot_payload)
    del payload["specs"][0]["slots"][0]["figure"]
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\].*exactly one"):
        parse_payload(payload)


def test_rejects_unknown_anchor(pilot_payload: dict) -> None:
    payload = copy.deepcopy(pilot_payload)
    payload["specs"][0]["slots"][0]["anchor"] = "left"
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\]\.anchor:"):
        parse_payload(payload)


def test_rejects_bad_cell() -> None:
    payload = specs_to_payload(SENTENCE_SPECS[("galop", "*")])
    payload["specs"][0]["slots"][0]["cell"] = ""
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\]\.cell:"):
        parse_payload(payload)

    payload = specs_to_payload(SENTENCE_SPECS[("galop", "*")])
    payload["specs"][0]["slots"][0]["cell"] = 1
    with pytest.raises(ValueError, match=r"specs\[0\]\.slots\[0\]\.cell:"):
        parse_payload(payload)


def test_changed_spec_needs_replace(tmp_path: Path) -> None:
    before = dict(SENTENCE_SPECS)
    payload = specs_to_payload(SENTENCE_SPECS[("castillo", "3/4")])
    payload["specs"][0]["select"]["length_min"] = 3
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="already registered"):
        load_specs(changed)
    assert dict(SENTENCE_SPECS) == before

    loaded = load_specs(changed, replace=True)
    assert SENTENCE_SPECS[("castillo", "3/4")] == tuple(
        sorted(loaded, key=lambda spec: (spec.select.length_min, spec.id))
    )
    assert any(spec.select.length_min == 3 for spec in loaded)


def test_new_pattern_adds_and_identical_reload_is_a_noop(tmp_path: Path) -> None:
    base = spec_to_mapping(SENTENCE_SPECS[("galop", "*")][0])
    fresh = copy.deepcopy(base)
    fresh["id"] = "studio_unit_cycle"
    fresh["pattern"] = "studio_unit"
    fresh["meter"] = "4/4"
    path = tmp_path / "studio-unit.json"
    path.write_text(json.dumps(_wrapper(fresh)), encoding="utf-8")

    loaded = load_specs(path)
    assert SENTENCE_SPECS[("studio_unit", "4/4")] == loaded
    assert load_specs(path) == loaded
    assert SENTENCE_SPECS[("studio_unit", "4/4")] == loaded


def test_role_round_trips_through_the_spec_schema() -> None:
    base = SENTENCE_SPECS[("galop", "*")][0]
    tagged = dataclasses.replace(base, role="B")
    assert parse_spec(spec_to_mapping(tagged)) == tagged
