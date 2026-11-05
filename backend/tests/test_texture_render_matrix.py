"""Golden render matrix for the sentence selections.

`tests/fixtures/render_matrix.json` has one row per registered archetype and per
Villa/Barrios/Brouwer candidate. Every row is produced by the real Studio
preview path (`preview_spec` / `preview_villa_sentence` /
`preview_barrios_period` / `preview_brouwer_sentence`); the notes are never
hand-built. The test rerenders each committed row from its own fixture and
compares the note count, per-voice counts and render hash.

Drift is a review event: there is deliberately no update mode.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.studio import preview
from tests.texture_matrix import (
    FAMILY_OWNER,
    FIXTURE_VERSION,
    RENDERER_VERSION,
    candidate_families,
    candidate_ids,
    candidate_previews,
    registered_pairs,
    registered_spec_ids,
    render_payload,
    spec_by_id,
    voice_counts,
)

FIXTURE = Path(__file__).parent / "fixtures" / "render_matrix.json"


def _load() -> dict:
    if not FIXTURE.exists():
        pytest.fail(f"{FIXTURE} is missing; this matrix is a required Phase 0 artifact")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _replay(row: dict):
    spec = spec_by_id()[row["id"]]
    preview_fn = candidate_previews().get(row["id"], preview.preview_spec)
    return preview_fn(spec, row["fixture"])


def test_committed_render_matrix_matches_the_code() -> None:
    expected = _load()
    actual = render_payload()
    assert actual == expected


def test_every_row_rerenders_to_the_same_counts_and_hash() -> None:
    expected = _load()
    for row in expected["rows"]:
        result = _replay(row)
        assert result.ok, (row["id"], result.errors)
        if row.get("expected_empty"):
            assert row["note_count"] == 0
            assert not result.notes
        else:
            assert row["note_count"] > 0, row["id"]
            assert row["note_count"] == len(result.notes), row["id"]
            assert row["voice_counts"] == voice_counts(list(result.notes)), row["id"]
        assert row["renderHash"] == result.render_hash, row["id"]


def test_no_registered_family_is_silently_missing() -> None:
    expected = _load()
    rows = expected["rows"]
    registry = [row for row in rows if row["source"] == "registry"]
    candidates = [row for row in rows if row["source"] == "candidate"]

    assert {(row["pattern"], row["meter"]) for row in registry} == registered_pairs()
    assert {row["id"] for row in registry} == registered_spec_ids()
    assert {row["family"] for row in registry} == {
        FAMILY_OWNER[pattern] for pattern, _meter in registered_pairs()
    }
    assert {row["family"] for row in candidates} == candidate_families()
    found: dict[str, list[str]] = {}
    for row in candidates:
        found.setdefault(row["family"], []).append(row["id"])
    assert {
        family: tuple(sorted(ids)) for family, ids in found.items()
    } == candidate_ids()
    assert len(rows) == len({row["id"] for row in rows})


def test_expected_empty_rows_carry_a_reason() -> None:
    expected = _load()
    for row in expected["rows"]:
        if row.get("expected_empty"):
            assert isinstance(row.get("reason"), str) and row["reason"].strip(), row[
                "id"
            ]
        else:
            assert "reason" not in row, row["id"]


def test_versions_are_recorded_on_the_body_and_every_row() -> None:
    expected = _load()
    assert expected["renderer_version"] == RENDERER_VERSION
    assert expected["fixture_version"] == FIXTURE_VERSION
    for row in expected["rows"]:
        assert row["renderer_version"] == RENDERER_VERSION, row["id"]
        assert row["fixture_version"] == FIXTURE_VERSION, row["id"]
        assert isinstance(row["renderHash"], str), row["id"]
        assert row["renderHash"].startswith("sha256:"), row["id"]
