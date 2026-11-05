"""Golden pattern-level selection matrix for every `(ensemble, pattern)`.

`tests/fixtures/pattern_selection_matrix.json` records one deterministic input
per `PROFILES` row and the id the real chooser picks for it:

* `driver: "select_body"` calls `_select_body` with the row's `first_body`,
  `previous`, and section.
* `driver: "patterns"` calls the renderer's `_patterns` dispatcher, so a framed
  row walks `_assign_macro` and `_dominant_pattern_auto` unchanged.

The frame path `pedal` is a `_FAMILY`-only id, so it gets a `*` ensemble row
rather than pretending to own a `PROFILES` pair. `sonatina` is registered in
`PROFILES` but no selector emits it; its row is `expected_empty` with a reason
and the pattern its probe actually selected.

Drift is a review event: this test never rewrites the fixture. Rebuild the
JSON by hand, read the diff, and commit both if the selector really changed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _FAMILY
from app.sonify.guitar_wave import PROFILES
from app.sonify.params import DEFAULT_PARAMS, compose_params
from tests.guitar_fixture import meter_named, pattern_case
from tests.texture_matrix import (
    FRAME_ENSEMBLE,
    PATTERN_MATRIX_VERSION,
    PATTERN_METERS,
    PATTERN_PHASE,
    PATTERN_SELECTION_KIND,
    PATTERN_UNREACHABLE_REASONS,
    pattern_payload,
    run_pattern_input,
)

FIXTURE = Path(__file__).parent / "fixtures" / "pattern_selection_matrix.json"


def _load() -> dict:
    if not FIXTURE.exists():
        pytest.fail(
            f"{FIXTURE} is missing; this matrix is a required Phase 0 artifact"
        )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _rows_by_target(rows: list[dict]) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    for row in rows:
        found.setdefault(row["input"]["pattern"], []).append(row)
    return found


def test_committed_pattern_matrix_matches_the_code() -> None:
    expected = _load()
    actual = pattern_payload()
    assert actual["version"] == expected["version"] == PATTERN_MATRIX_VERSION
    assert actual["kind"] == expected["kind"] == PATTERN_SELECTION_KIND
    assert actual["phase"] == expected["phase"] == PATTERN_PHASE
    assert actual["grid"] == expected["grid"]
    assert actual["rows"] == expected["rows"]


def test_every_profiles_pair_has_exactly_one_row() -> None:
    rows = _load()["rows"]
    pairs = [
        (row["input"]["ensemble"], row["input"]["pattern"])
        for row in rows
        if row["input"]["ensemble"] != FRAME_ENSEMBLE
    ]
    assert len(pairs) == len(set(pairs)), "duplicate PROFILES pair in the matrix"
    assert set(PROFILES) == set(pairs)


def test_rows_are_sorted_deterministically() -> None:
    rows = _load()["rows"]
    keys = [
        (
            row["input"]["ensemble"],
            row["input"]["pattern"],
            row["input"]["meter"],
            row["driver"],
        )
        for row in rows
    ]
    assert keys == sorted(keys)


def test_every_row_replays_through_the_real_chooser() -> None:
    with compose_params(DEFAULT_PARAMS):
        for row in _load()["rows"]:
            selected, kind = run_pattern_input(row)
            assert kind == row["ctx_kind"], row
            assert row["selected_sentence"] is None, row
            target = row["input"]["pattern"]
            if row["expected_empty"]:
                assert row["selected_pattern"] is None, row
                assert row["reason"].strip(), row
                assert selected == row["observed_pattern"], row
                assert selected != target, row
            else:
                assert row["selected_pattern"] == target, row
                assert selected == row["selected_pattern"], row


def test_supported_meters_never_produce_other_ctx_kind() -> None:
    for row in _load()["rows"]:
        meter = row["input"]["meter"]
        assert meter in PATTERN_METERS, row
        assert row["ctx_kind"] != "other", row
        assert row["ctx_kind"] == meter, row


def test_selected_ids_exist_in_family_and_profiles() -> None:
    for row in _load()["rows"]:
        selected = row["selected_pattern"]
        if selected is None:
            continue
        assert selected in _FAMILY, row
        if row["input"]["ensemble"] == FRAME_ENSEMBLE:
            assert selected == "pedal", row
            continue
        assert (row["input"]["ensemble"], selected) in PROFILES, row


def test_expected_empty_rows_require_a_reason() -> None:
    for row in _load()["rows"]:
        if not row["expected_empty"]:
            continue
        assert row["selected_pattern"] is None, row
        assert isinstance(row["reason"], str) and row["reason"].strip(), row
        assert row["observed_pattern"] != row["input"]["pattern"], row


def test_unreachable_reasons_are_used_only_by_expected_empty_rows() -> None:
    rows = _load()["rows"]
    expected_empty_targets = {
        row["input"]["pattern"] for row in rows if row["expected_empty"]
    }
    assert expected_empty_targets == set(PATTERN_UNREACHABLE_REASONS)
    for pattern in PATTERN_UNREACHABLE_REASONS:
        found = [row for row in rows if row["input"]["pattern"] == pattern]
        assert found, pattern
        assert all(row["expected_empty"] for row in found), pattern


def test_every_profile_pattern_is_selected_or_explained() -> None:
    rows_by_target = _rows_by_target(_load()["rows"])
    profile_patterns = sorted({pattern for _ensemble, pattern in PROFILES})
    for pattern in profile_patterns:
        found = rows_by_target.get(pattern, [])
        assert found, f"{pattern} is dead data: no matrix row targets it"
        assert any(row["selected_pattern"] == pattern for row in found) or any(
            row["expected_empty"] and row["reason"].strip() for row in found
        ), f"{pattern} is neither selected nor explained"


def test_family_only_patterns_are_not_dead_data() -> None:
    profile_patterns = {pattern for _ensemble, pattern in PROFILES}
    family_only = sorted(set(_FAMILY) - profile_patterns)
    rows_by_target = _rows_by_target(_load()["rows"])
    for pattern in family_only:
        found = rows_by_target.get(pattern, [])
        assert found, f"{pattern} is in _FAMILY but no matrix row targets it"
        assert any(row["selected_pattern"] == pattern for row in found) or any(
            row["expected_empty"] and row["reason"].strip() for row in found
        ), f"{pattern} is neither selected nor explained"


def test_pattern_case_builds_a_framed_macro_context_deterministically() -> None:
    sections = [
        FormSection(0, 1, "intro", 0),
        FormSection(1, 8, "phrase", 0),
    ]
    kwargs = dict(
        ensemble="bach",
        mood="calm",
        band="mf",
        bpm=96,
        bars=8,
        first_body=True,
        previous=[],
        sections=sections,
        rel_span=0.004,
    )
    ctx, phrases = pattern_case("probe", meter_named("4/4"), **kwargs)
    again, again_phrases = pattern_case("probe", meter_named("4/4"), **kwargs)
    assert ctx == again
    assert phrases == again_phrases
    assert ctx.sections == tuple(sections)
    assert ctx.kind_at[0] == "intro"
    assert ctx.kind_at[1] == "phrase"
    assert phrases[0].start == 1 * ctx.epb
    assert phrases[0].end == 8 * ctx.epb
    assert ctx.rel_span == 0.004

    with pytest.raises(ValueError):
        pattern_case(
            "probe",
            meter_named("4/4"),
            ensemble="bach",
            mood="calm",
            band="mf",
            bpm=96,
            section=sections[1],
            sections=sections,
        )
