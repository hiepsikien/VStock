"""Golden selection matrix for the implemented sentence registry.

`tests/fixtures/sentence_selection_matrix.json` records what
`plan_sentence`/`plan_run` choose for every registered `(pattern, meter)` over a
bounded `(length, n, closes, rise)` grid, plus one row per Villa/Barrios/Brouwer
candidate from its Studio preview plan.

Drift is a review event: this test never rewrites the fixture. If a selector
changes, regenerate the JSON by hand, read the diff, and commit both.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.sonify import sentence_specs
from app.sonify.form import FormSection
from app.sonify.guitar_patterns import _FAMILY, _select_body
from app.sonify.guitar_wave import PROFILES
from tests.guitar_fixture import meter_named, pattern_case
from tests.texture_matrix import (
    FAMILY_OWNER,
    candidate_families,
    candidate_ids,
    registered_pairs,
    selection_payload,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "sentence_selection_matrix.json"
)


def _load() -> dict:
    if not FIXTURE.exists():
        pytest.fail(
            f"{FIXTURE} is missing; this matrix is a required Phase 0 artifact"
        )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _row_key(row: dict) -> tuple:
    return (
        row["pattern"],
        row["meter"],
        row["length"],
        row["n"],
        row["closes"],
        row["rise"],
    )


def _compare_rows(actual: list[dict], expected: list[dict]) -> None:
    actual_by_key = {_row_key(row): row for row in actual}
    expected_by_key = {_row_key(row): row for row in expected}
    missing = sorted(set(expected_by_key) - set(actual_by_key))
    extra = sorted(set(actual_by_key) - set(expected_by_key))
    assert not missing, f"matrix rows missing from the code output: {missing[:5]}"
    assert not extra, f"matrix rows missing from the committed fixture: {extra[:5]}"
    mismatched = [
        key
        for key in expected_by_key.keys() & actual_by_key.keys()
        if expected_by_key[key] != actual_by_key[key]
    ]
    assert not mismatched, [
        (key, expected_by_key[key], actual_by_key[key]) for key in mismatched[:3]
    ]


def test_committed_selection_matrix_matches_the_code() -> None:
    expected = _load()
    actual = selection_payload()
    assert actual["version"] == expected["version"]
    assert actual["kind"] == expected["kind"]
    assert actual["grid"] == expected["grid"]
    _compare_rows(actual["rows"], expected["rows"])
    assert actual["candidates"] == expected["candidates"]


def test_every_registered_pair_appears_at_least_once() -> None:
    expected = _load()
    present = {(row["pattern"], row["meter"]) for row in expected["rows"]}
    selected = {
        (row["pattern"], row["meter"])
        for row in expected["rows"]
        if row["selected"]
    }
    pairs = registered_pairs()
    assert pairs <= present, sorted(pairs - present)
    assert pairs <= selected, sorted(pairs - selected)


def test_every_registered_archetype_selects_at_least_once() -> None:
    """A spec that no grid point can select is dead data, not coverage."""
    expected = _load()
    seen: set[str] = set()
    for row in expected["rows"]:
        if not row["selected"]:
            continue
        key = (row["pattern"], row["meter"])
        for spec in sentence_specs.SENTENCE_SPECS[key]:
            if spec.span.cycle:
                if row["kind"] == "cell" and row["cells"]:
                    seen.add(spec.id)
            elif sentence_specs._matches(
                spec,
                row["length"],
                row["n"],
                row["closes"],
                row["rise"],
            ):
                seen.add(spec.id)
                break
    expected_ids = {
        spec.id
        for specs in sentence_specs.SENTENCE_SPECS.values()
        for spec in specs
    }
    assert expected_ids <= seen, sorted(expected_ids - seen)


def test_candidate_rows_cover_every_preview() -> None:
    expected = _load()
    found = {row["family"]: row["id"] for row in expected["candidates"]}
    assert found == candidate_ids()
    assert set(found) == candidate_families() == {"villa", "barrios", "brouwer"}
    for row in expected["candidates"]:
        assert row["selected"] is True, row["id"]
        assert row["spans"], row["id"]


def test_pattern_case_is_deterministic_and_drives_select_body() -> None:
    """The shared fixture builds an equal context twice and feeds `_select_body`."""
    known = set(_FAMILY) | {pattern for _ensemble, pattern in PROFILES}
    for pattern, meter in sorted(registered_pairs()):
        ensemble = FAMILY_OWNER[pattern]
        args = dict(
            ensemble=ensemble,
            mood="calm",
            band="mf",
            bpm=96,
            bars=8,
            first_body=True,
            previous=["castillo"],
            section=None,
        )
        ctx, phrases = pattern_case(pattern, meter_named(meter), **args)
        again, again_phrases = pattern_case(pattern, meter_named(meter), **args)
        assert ctx == again
        assert phrases == again_phrases
        assert len(phrases) == 1

        chosen = _select_body(
            ctx,
            phrases[0],
            first_body=args["first_body"],
            previous=args["previous"],
            section=ctx.sections[0],
        )
        assert chosen in known, (pattern, meter, chosen)


def test_pattern_case_folds_meter_and_section_into_the_context() -> None:
    region = FormSection(2, 6, "intro", 1)
    ctx, phrases = pattern_case(
        "danza",
        meter_named("3/4"),
        ensemble="torroba",
        mood="calm",
        band="mp",
        bpm=96,
        bars=8,
        first_body=False,
        previous=["castillo"],
        section=region,
    )
    assert ctx.epb == 6
    assert len(ctx.melody) == len(ctx.raw) == 8 * 6
    assert phrases == [ctx.phrases[0]]
    assert phrases[0].start == 0 and phrases[0].end == 8 * 6
    assert ctx.sections == (region,)
    assert ctx.kind_at[0] == "phrase"
    assert ctx.kind_at[2] == "intro"
    assert ctx.kind_at[6] == "phrase"
    assert ctx.band_at[0] == "mp" and ctx.character == "calm"

    unframed, _phrases = pattern_case(
        "danza",
        meter_named("3/4"),
        ensemble="torroba",
        mood="calm",
        band="mf",
        bpm=96,
        bars=8,
        first_body=False,
    )
    assert unframed.sections[0].regime_slot == 1
