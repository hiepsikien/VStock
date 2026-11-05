"""Studio candidate API: one preview URL for Torroba/Sor, Villa, and Barrios.

The UI posts every authored spec to `/v1/studio/sentence/preview`. The router
must dispatch by the spec's pattern, keep the response shape identical across
families, and serve the committed example specs instead of making the UI copy
JSON by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio as studio_router
from app.sonify import sentence_specs as specs

# Import both production owners so the registry snapshot is complete before a
# candidate preview checks that it did not change.
import app.sonify.guitar_sor  # noqa: F401
import app.sonify.guitar_torroba  # noqa: F401
from app.studio import dispatch
from app.studio.barrios_preview import preview_barrios_period
from app.studio.candidates import (
    BARRIOS_CATHEDRAL_PATH,
    VILLA_ARPEGGIO_PATH,
    barrios_cathedral_spec,
    villa_candidate_spec,
)
from app.studio.candidates.suite_choros1 import (
    SUITE_CHOROS1_PATH,
    suite_choros1_spec,
)
from app.studio.candidates.suite_gavotta import (
    SUITE_GAVOTTA_PATH,
    suite_gavotta_spec,
)
from app.studio.candidates.suite_mazurka import (
    SUITE_MAZURKA_PATH,
    suite_mazurka_spec,
)
from app.studio.candidates.suite_schottish import (
    SUITE_SCHOTTISH_PATH,
    suite_schottish_spec,
)
from app.studio.candidates.suite_valsa import (
    SUITE_VALSA_PATH,
    suite_valsa_spec,
)
from app.studio.export import PILOT_PATTERNS, SPECS_DIR
from app.studio.sentence_spec import parse_spec
from app.studio.villa_preview import preview_villa_sentence

PREVIEW = "/v1/studio/sentence/preview"
VALIDATE = "/v1/studio/sentence/validate"
EXAMPLES = "/v1/studio/sentence/examples"
SHAPE = {"ok", "errors", "plan", "row", "notes", "renderHash", "matrix"}


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_router.router)
    return TestClient(app)


def _examples(client: TestClient) -> list[dict]:
    body = client.get(EXAMPLES).json()
    assert body["ok"] is True
    return body["examples"]


def _example(client: TestClient, pattern: str) -> dict:
    body = client.get(f"{EXAMPLES}/{pattern}").json()
    assert body["ok"] is True, body
    return body["examples"][0]


def _preview(client: TestClient, payload: dict, fixture: dict | None = None) -> dict:
    response = client.post(PREVIEW, json={"spec": payload, "fixture": fixture or {}})
    assert response.status_code == 200
    return response.json()


def _castillo_payload() -> dict:
    wrapper = json.loads((SPECS_DIR / "castillo-3-4.json").read_text(encoding="utf-8"))
    walk = next(spec for spec in wrapper["specs"] if spec["id"] == "castillo_34_walk")
    return walk


# ---------------------------------------------------------------------------
# dispatch table


def test_the_three_families_cover_their_patterns() -> None:
    assert dispatch.family_for("castillo") == dispatch.TORROBA_SOR
    assert dispatch.family_for("galop") == dispatch.TORROBA_SOR
    for pattern in PILOT_PATTERNS:
        assert dispatch.family_for(pattern) == dispatch.TORROBA_SOR
    for pattern in ("villa_pattern", "chord_melody", "etude1", "etude11"):
        assert dispatch.family_for(pattern) == dispatch.VILLA
    assert dispatch.family_for("preludio") == dispatch.BARRIOS
    assert dispatch.family_for("bogus") is None
    assert dispatch.family_for(None) is None


def test_the_families_do_not_overlap() -> None:
    """A pattern must have exactly one owner, or dispatch order would matter."""
    from app.studio.barrios_preview import BARRIOS_PATTERNS
    from app.studio.villa_preview import VILLA_PATTERNS

    pilot = set(PILOT_PATTERNS)
    assert not pilot & set(VILLA_PATTERNS)
    assert not pilot & set(BARRIOS_PATTERNS)
    assert not set(VILLA_PATTERNS) & set(BARRIOS_PATTERNS)


def test_every_registered_pattern_dispatches_to_torroba_sor() -> None:
    registered = {pattern for pattern, _ in specs.SENTENCE_SPECS}
    assert registered == set(PILOT_PATTERNS)
    for pattern in registered:
        assert dispatch.family_for(pattern) == dispatch.TORROBA_SOR


# ---------------------------------------------------------------------------
# preview per family


def test_preview_torroba_spec_uses_the_preview_family() -> None:
    client = _client()
    body = _preview(client, _castillo_payload())
    assert set(body) == SHAPE
    assert body["ok"] is True
    assert body["plan"]["kind"] == "figure"
    assert body["row"] == ["castillo"] * 9
    assert body["renderHash"].startswith("sha256:")
    assert body["notes"]


def test_preview_villa_candidate_through_the_api() -> None:
    client = _client()
    payload = json.loads(VILLA_ARPEGGIO_PATH.read_text(encoding="utf-8"))["specs"][0]
    body = _preview(client, payload)

    assert set(body) == SHAPE
    assert body["ok"] is True
    assert body["plan"]["kind"] == "figure"
    assert body["row"] == [
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
    ]
    # The API must not re-spell the candidate result.
    direct = preview_villa_sentence(villa_candidate_spec())
    assert body["renderHash"] == direct.render_hash
    assert body["notes"] == list(direct.notes)


def test_preview_suite_mazurka_candidate_through_the_api() -> None:
    client = _client()
    payload = json.loads(SUITE_MAZURKA_PATH.read_text(encoding="utf-8"))["specs"][0]
    assert payload["meter"] == "3/4"

    body = _preview(client, payload)

    assert set(body) == SHAPE
    assert body["ok"] is True
    assert body["plan"]["kind"] == "figure"
    assert body["plan"]["length"] == 4
    assert body["row"] == [
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
    ]
    # A 3/4 preview must stay inside three quarter beats per bar.
    assert all(
        note["beat"] + note["duration"] <= 3.0 for note in body["notes"]
    )
    direct = preview_villa_sentence(suite_mazurka_spec())
    assert body["renderHash"] == direct.render_hash
    assert body["notes"] == list(direct.notes)


def test_preview_suite_valsa_candidate_through_the_api() -> None:
    client = _client()
    payload = json.loads(SUITE_VALSA_PATH.read_text(encoding="utf-8"))["specs"][0]
    assert payload["meter"] == "3/4"

    body = _preview(client, payload)

    assert set(body) == SHAPE
    assert body["ok"] is True
    assert body["plan"]["kind"] == "figure"
    assert body["plan"]["length"] == 8
    assert body["row"] == [
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_arpeggio",
        "villa_chord_melody",
        "villa_chord_melody",
    ]
    # A 3/4 preview must stay inside three quarter beats per bar.
    assert all(
        note["beat"] + note["duration"] <= 3.0 for note in body["notes"]
    )
    direct = preview_villa_sentence(suite_valsa_spec())
    assert body["renderHash"] == direct.render_hash
    assert body["notes"] == list(direct.notes)


@pytest.mark.parametrize(
    ("path", "spec_fn", "expected_row"),
    [
        (
            SUITE_SCHOTTISH_PATH,
            suite_schottish_spec,
            [
                "villa_arpeggio",
                "villa_chord_melody",
                "villa_arpeggio",
                "villa_chord_melody",
            ],
        ),
        (
            SUITE_GAVOTTA_PATH,
            suite_gavotta_spec,
            [
                "villa_chord_melody",
                "villa_arpeggio",
                "villa_arpeggio",
                "villa_chord_melody",
            ],
        ),
        (
            SUITE_CHOROS1_PATH,
            suite_choros1_spec,
            [
                "villa_arpeggio",
                "villa_chord_melody",
                "villa_chord_melody",
                "villa_arpeggio",
            ],
        ),
    ],
)
def test_preview_the_remaining_suite_candidates_through_the_api(
    path: Path, spec_fn, expected_row: list[str]
) -> None:
    client = _client()
    payload = json.loads(path.read_text(encoding="utf-8"))["specs"][0]

    # All three are 4/4 candidates: the 2/4 source and the provisional
    # signatures are engine-level caveats recorded in their modules, not a
    # fourth meter for the preview to invent.
    assert payload["meter"] == "4/4"
    assert payload["pattern"] == "villa_pattern"

    body = _preview(client, payload)

    assert set(body) == SHAPE
    assert body["ok"] is True
    assert body["plan"]["kind"] == "figure"
    assert body["plan"]["length"] == 4
    assert body["row"] == expected_row
    # A 4/4 preview must stay inside four quarter beats per bar and reach the
    # barline at least once, so the 4/4 branch really rendered.
    assert all(
        note["beat"] + note["duration"] <= 4.0 for note in body["notes"]
    )
    assert any(
        note["beat"] + note["duration"] == 4.0 for note in body["notes"]
    )
    direct = preview_villa_sentence(spec_fn())
    assert body["renderHash"] == direct.render_hash
    assert body["notes"] == list(direct.notes)


def test_preview_barrios_candidate_through_the_api() -> None:
    client = _client()
    payload = json.loads(BARRIOS_CATHEDRAL_PATH.read_text(encoding="utf-8"))["specs"][0]
    body = _preview(client, payload)

    assert set(body) == SHAPE
    assert body["ok"] is True
    assert body["plan"]["kind"] == "barrios_period"
    assert body["plan"]["length"] == 12
    assert [span["pattern"] for span in body["plan"]["spans"]] == [
        "preludio",
        "tremolo",
        "preludio",
    ]
    assert body["row"] == (
        ["preludio"] * 4 + ["tremolo"] * 4 + ["preludio"] * 4
    )
    assert {note["bar"] for note in body["notes"]} == set(range(12))
    direct = preview_barrios_period(barrios_cathedral_spec())
    assert body["renderHash"] == direct.render_hash
    assert body["notes"] == list(direct.notes)


def test_candidate_previews_leave_the_registry_untouched() -> None:
    client = _client()
    before = dict(specs.SENTENCE_SPECS)
    for path in (
        VILLA_ARPEGGIO_PATH,
        SUITE_MAZURKA_PATH,
        SUITE_VALSA_PATH,
        SUITE_SCHOTTISH_PATH,
        SUITE_GAVOTTA_PATH,
        SUITE_CHOROS1_PATH,
        BARRIOS_CATHEDRAL_PATH,
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))["specs"][0]
        assert _preview(client, payload)["ok"] is True
    assert specs.SENTENCE_SPECS == before
    assert specs.SENTENCE_SPECS is not before


def test_villa_preview_errors_keep_the_shared_shape() -> None:
    client = _client()
    payload = json.loads(VILLA_ARPEGGIO_PATH.read_text(encoding="utf-8"))["specs"][0]
    # length 1 is below the candidate's length_min, so nothing is selected.
    body = _preview(client, payload, {"length": 1})
    assert set(body) == SHAPE
    assert body["ok"] is False
    assert body["errors"] == [
        {
            "path": "fixture",
            "message": (
                "this fixture (length/n/closes/rise) is not selected by the spec"
            ),
        }
    ]
    assert body["plan"] is None and body["renderHash"] is None


def test_barrios_preview_errors_keep_the_shared_shape() -> None:
    client = _client()
    payload = json.loads(BARRIOS_CATHEDRAL_PATH.read_text(encoding="utf-8"))["specs"][0]
    body = _preview(client, payload, {"length": 8})
    assert set(body) == SHAPE
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "fixture"
    assert "exact period length 12" in body["errors"][0]["message"]
    assert body["plan"] is None and body["renderHash"] is None


# ---------------------------------------------------------------------------
# unknown pattern


def test_preview_rejects_an_unknown_pattern_at_spec_dot_pattern() -> None:
    client = _client()
    payload = {**_castillo_payload(), "pattern": "nope"}
    body = _preview(client, payload)

    assert set(body) == SHAPE
    assert body["ok"] is False
    assert body["errors"] == [
        {
            "path": "pattern",
            "message": (
                "unknown pattern 'nope'; expected a Torroba/Sor, Villa, "
                "Barrios, or Brouwer pattern"
            ),
        }
    ]
    assert body["plan"] is None
    assert body["row"] is None
    assert body["matrix"] == []


def test_validate_rejects_an_unknown_pattern_at_spec_dot_pattern() -> None:
    client = _client()
    payload = {**_castillo_payload(), "pattern": "nope"}
    body = client.post(VALIDATE, json=payload).json()
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "pattern"


# ---------------------------------------------------------------------------
# validate per family


def test_validate_dispatches_to_each_family() -> None:
    client = _client()
    response = client.post(VALIDATE, json=_castillo_payload())
    assert response.json() == {"ok": True, "errors": []}

    for path in (
        VILLA_ARPEGGIO_PATH,
        SUITE_MAZURKA_PATH,
        SUITE_VALSA_PATH,
        SUITE_SCHOTTISH_PATH,
        SUITE_GAVOTTA_PATH,
        SUITE_CHOROS1_PATH,
        BARRIOS_CATHEDRAL_PATH,
    ):
        payload = json.loads(path.read_text(encoding="utf-8"))["specs"][0]
        body = client.post(VALIDATE, json=payload).json()
        assert body == {"ok": True, "errors": []}, (path, body)


def test_validate_accepts_a_candidate_v1_wrapper() -> None:
    client = _client()
    for path in (
        VILLA_ARPEGGIO_PATH,
        SUITE_MAZURKA_PATH,
        SUITE_VALSA_PATH,
        SUITE_SCHOTTISH_PATH,
        SUITE_GAVOTTA_PATH,
        SUITE_CHOROS1_PATH,
        BARRIOS_CATHEDRAL_PATH,
    ):
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        body = client.post(VALIDATE, json=wrapper).json()
        assert body == {"ok": True, "errors": []}, (path, body)


def test_validate_reports_candidate_family_errors() -> None:
    client = _client()
    payload = json.loads(BARRIOS_CATHEDRAL_PATH.read_text(encoding="utf-8"))["specs"][0]
    payload["slots"][0]["figure"] = 99
    body = client.post(VALIDATE, json=payload).json()
    assert body["ok"] is False
    assert any(error["path"] == "slots[0].figure" for error in body["errors"])


# ---------------------------------------------------------------------------
# examples


def test_examples_include_torroba_sor_villa_barrios_and_brouwer() -> None:
    client = _client()
    rows = _examples(client)
    patterns = {row["pattern"] for row in rows}

    assert set(PILOT_PATTERNS) <= patterns
    assert {"villa_pattern", "preludio", "brouwer_etude"} <= patterns
    # 38 Torroba/Sor + 8 generic candidates (the 4/4 Villa arpeggio, the two
    # 3/4 Suite movements, the three 4/4 Suite movements, Barrios, Brouwer).
    # The procedure-only Bach candidate is skipped by this endpoint.
    assert len(rows) == 46
    suite = next(
        row for row in rows if row["id"] == "suite_mazurka_arpeggio_aaba"
    )
    assert suite["pattern"] == "villa_pattern"
    assert suite["meter"] == "3/4"
    valsa = next(
        row for row in rows if row["id"] == "suite_valsa_arpeggio_period"
    )
    assert valsa["pattern"] == "villa_pattern"
    assert valsa["meter"] == "3/4"
    for row in rows:
        assert set(row) == {"pattern", "meter", "id", "payload"}
        assert row["payload"]["pattern"] == row["pattern"]
        assert row["payload"]["meter"] == row["meter"]
        assert row["payload"]["id"] == row["id"]


def test_examples_are_sorted_deterministically() -> None:
    client = _client()
    rows = _examples(client)
    keys = [(row["pattern"], row["meter"], row["id"]) for row in rows]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    assert _examples(_client()) == rows


def test_examples_can_be_filtered_by_pattern() -> None:
    client = _client()
    villa = client.get(f"{EXAMPLES}/villa_pattern").json()
    assert villa == {
        "ok": True,
        "examples": [
            row
            for row in _examples(client)
            if row["pattern"] == "villa_pattern"
        ],
    }
    # All Villa candidates share the parent pattern and split across meters.
    assert {row["meter"] for row in villa["examples"]} == {"3/4", "4/4"}
    assert {row["id"] for row in villa["examples"]} == {
        "suite_choros1_arpeggio_abba",
        "suite_gavotta_arpeggio_baab",
        "suite_mazurka_arpeggio_aaba",
        "suite_schottish_arpeggio_abab",
        "suite_valsa_arpeggio_period",
        "villa_arpeggio_aba",
    }
    barrios = client.get(f"{EXAMPLES}/preludio").json()
    assert [row["id"] for row in barrios["examples"]] == ["barrios_cathedral_period"]
    brouwer = client.get(f"{EXAMPLES}/brouwer_etude").json()
    assert [row["id"] for row in brouwer["examples"]] == [
        "brouwer_etude_noviembre_aba"
    ]

    unknown = client.get(f"{EXAMPLES}/nope").json()
    assert unknown["ok"] is False
    assert unknown["errors"] == [
        {
            "path": "pattern",
            "message": "no committed example spec for pattern 'nope'",
        }
    ]


def test_every_example_payload_validates_through_the_api() -> None:
    client = _client()
    for row in _examples(client):
        body = client.post(VALIDATE, json=row["payload"]).json()
        assert body == {"ok": True, "errors": []}, (row["pattern"], row["id"], body)


def test_every_example_payload_previews_through_the_api() -> None:
    """No example may be served that the preview URL cannot render."""
    client = _client()
    for row in _examples(client):
        body = _preview(client, row["payload"])
        assert body["ok"] is True, (row["pattern"], row["id"], body["errors"])
        assert body["renderHash"].startswith("sha256:")


def test_example_payloads_parse_as_single_specs() -> None:
    client = _client()
    for row in _examples(client):
        spec = parse_spec(row["payload"])
        assert dispatch.family_for(spec.pattern) is not None
