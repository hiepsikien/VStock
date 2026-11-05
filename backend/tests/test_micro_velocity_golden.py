"""Exact zero-diff oracle for the micro-velocity carrier contours.

Section 6.9 of `docs/sonify-texture-studio.md` keeps the production patterns
(Tremolo, Galop, Cathedral Preludio, Etude 1, Etude 11) out of the Studio
`renderHash` comparison. Their baseline is the exact `NoteEvent` list plus a
digest of the real render. `tests/fixtures/micro_velocity_golden.json` is that
baseline, built by `tests/micro_velocity_golden.py` from the production
`render_patterned_voices` path.

There is deliberately no update mode and no tolerance. A mismatch means the
extracted contour, its application order, or the renderer changed; review it
by hand and regenerate the artifact in the same commit only when the change is
intended.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from app.sonify.model import NoteEvent
from tests.micro_velocity_golden import (
    EVENT_FIELDS,
    FIXTURES,
    FIXTURE_VERSION,
    KIND,
    NOTE_SORT,
    REGISTER,
    RENDERER,
    REQUIRED_FIGURES,
    VERSION,
    build_fixture,
    build_manifest,
    digest,
)

FIXTURE = Path(__file__).parent / "fixtures" / "micro_velocity_golden.json"
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


def _load() -> dict[str, Any]:
    if not FIXTURE.exists():
        pytest.fail(
            f"{FIXTURE} is missing; the micro-velocity oracle is a required artifact"
        )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in manifest["fixtures"]}


def _first_mismatch(expected: list, actual: list) -> str | None:
    """A reviewable diff for the first differing event, or None."""
    if len(expected) != len(actual):
        return f"length {len(actual)} != expected {len(expected)}"
    for index, (want, got) in enumerate(zip(expected, actual)):
        if want == got:
            continue
        low = max(0, index - 2)
        high = min(len(expected), index + 3)
        expected_window = [expected[position] for position in range(low, high)]
        actual_window = [actual[position] for position in range(low, high)]
        return (
            f"first difference at index {index}\n"
            f"  expected {EVENT_FIELDS}\n"
            f"           {want!r}\n"
            f"  actual   {EVENT_FIELDS}\n"
            f"           {got!r}\n"
            f"  expected[{low}:{high}] = {expected_window!r}\n"
            f"  actual[{low}:{high}]   = {actual_window!r}"
        )
    return None


def test_the_committed_manifest_matches_the_code_exactly() -> None:
    expected = _load()
    actual = build_manifest()
    assert actual == expected, (
        "micro-velocity goldens drifted from the production render. "
        "There is no update mode: review the NoteEvent/digest diff by hand."
    )


def test_every_fixture_rerenders_to_the_exact_event_list() -> None:
    expected = _by_id(_load())
    for fixture_id, row in _by_id(build_manifest()).items():
        want = expected.get(fixture_id)
        assert want is not None, f"{fixture_id}: missing from the committed artifact"
        if row.get("expected_uncovered"):
            continue
        for voice in ("lead", "support", "low"):
            mismatch = _first_mismatch(want["voices"][voice], row["voices"][voice])
            assert mismatch is None, f"{fixture_id} voice {voice}: {mismatch}"
        assert row["patterns"] == want["patterns"], fixture_id
        assert row["divisions"] == want["divisions"], fixture_id
        assert row["note_counts"] == want["note_counts"], fixture_id


def test_every_stored_event_is_the_full_note_event_surface() -> None:
    surface = {field.name for field in fields(NoteEvent)}
    assert set(EVENT_FIELDS) == surface, (
        "EVENT_FIELDS is not the full NoteEvent surface: "
        f"missing {sorted(surface - set(EVENT_FIELDS))}, "
        f"extra {sorted(set(EVENT_FIELDS) - surface)}"
    )
    manifest = _load()
    assert len(manifest["event_fields"]) == len(EVENT_FIELDS)
    for index, (stored, expected) in enumerate(
        zip(manifest["event_fields"], EVENT_FIELDS)
    ):
        assert stored == expected, f"event field {index}: {stored!r} != {expected!r}"
    width = len(EVENT_FIELDS)
    for row in manifest["fixtures"]:
        if row.get("expected_uncovered"):
            continue
        for voice in ("lead", "support", "low"):
            for event in row["voices"][voice]:
                assert len(event) == width, (row["id"], voice, event)
                assert event[4] in (1, 2, 3, 4), (row["id"], voice, event)
                assert event[2] is None or isinstance(event[2], int), (row["id"], voice, event)
                assert event[5] is None or isinstance(event[5], int), (row["id"], voice, event)


def test_digests_are_sha256_and_recompute_from_the_stored_events() -> None:
    manifest = _load()
    for row in manifest["fixtures"]:
        if row.get("expected_uncovered"):
            continue
        fixture_payload = {
            "descriptor": row["descriptor"],
            "patterns": row["patterns"],
            "divisions": row["divisions"],
        }
        notes_payload = {
            "voices": row["voices"],
            "note_counts": row["note_counts"],
        }
        assert SHA256.match(row["fixture_digest"]), row["id"]
        assert SHA256.match(row["notes_digest"]), row["id"]
        assert SHA256.match(row["score_digest"]), row["id"]
        assert row["fixture_digest"] == digest(fixture_payload), row["id"]
        assert row["notes_digest"] == digest(notes_payload), row["id"]
        assert row["score_digest"] == digest({**fixture_payload, **notes_payload}), row["id"]
        assert row["notes_digest"] == "sha256:" + hashlib.sha256(
            json.dumps(
                notes_payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()


def test_the_artifact_is_a_note_event_oracle_not_a_render_hash() -> None:
    manifest = _load()
    assert manifest["renderer"] == RENDERER
    assert manifest["kind"] == KIND
    assert manifest["version"] == VERSION
    assert manifest["fixture_version"] == FIXTURE_VERSION
    assert manifest["register"] == REGISTER
    assert manifest["note_sort"] == NOTE_SORT
    for row in manifest["fixtures"]:
        assert "renderHash" not in row, row["id"]
        assert "render_hash" not in row, row["id"]
        if not row.get("expected_uncovered"):
            assert row["voices"], row["id"]
            assert row["note_counts"]["total"] > 0, row["id"]


def test_each_required_figure_is_covered() -> None:
    expected = _by_id(_load())
    assert set(REQUIRED_FIGURES) <= set(expected), (
        "required figure fixture missing: "
        f"{sorted(set(REQUIRED_FIGURES) - set(expected))}"
    )
    covered: set[str] = set()
    for fixture_id in REQUIRED_FIGURES:
        row = expected[fixture_id]
        assert not row.get("expected_uncovered"), (
            f"{fixture_id} is unexpectedly uncovered: {row.get('reason')!r}"
        )
        assert row.get("covered") is True, fixture_id
        covered.update(REQUIRED_FIGURES[fixture_id])
    assert covered == {
        "tremolo",
        "galop1",
        "galop2",
        "catedral_preludio",
        "etude1",
        "etude11",
    }, sorted(covered)


def test_an_expected_uncovered_fixture_needs_a_precise_reason() -> None:
    recipe = {**FIXTURES[0], "expected_uncovered": True}
    with pytest.raises(ValueError, match="expected_uncovered needs a reason"):
        build_fixture(recipe)
    row = build_fixture(
        {**recipe, "reason": "needs a form the bounded pattern_case cannot build"}
    )
    assert row["covered"] is False
    assert row["expected_uncovered"] is True
    assert row["reason"] == "needs a form the bounded pattern_case cannot build"
    assert not row.get("voices")
    assert not row.get("score_digest")


def test_the_galop_cycle_fixtures_exercise_both_cells() -> None:
    expected = _load()
    rows = _by_id(expected)
    first = rows["galop_1"]["cells"]
    second = rows["galop_2"]["cells"]
    assert set(first) == {"galop1"}, first
    assert set(second) == {"galop1", "galop2"}, second
    assert second["galop2"] == [5, 6, 7, 8], second


def test_the_manifest_is_deterministic() -> None:
    assert build_manifest() == build_manifest()


def test_the_manifest_has_no_environment_or_clock_fields() -> None:
    manifest = _load()
    forbidden = {"timestamp", "generated_at", "time", "date", "seed", "random", "env", "host"}
    assert not (forbidden & set(manifest)), sorted(forbidden & set(manifest))
    for row in manifest["fixtures"]:
        assert not (forbidden & set(row)), (row["id"], sorted(forbidden & set(row)))
        descriptor = row["descriptor"]
        assert not (forbidden & set(descriptor)), (row["id"], sorted(forbidden & set(descriptor)))
