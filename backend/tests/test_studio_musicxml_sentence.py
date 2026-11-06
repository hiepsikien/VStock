"""MusicXML passage -> sentence draft endpoint.

The draft copies a committed template, re-keys a new Villa pattern only when the
server has validated it, and previews through the existing family renderers.
Owner scoping and the process-local draft quota are part of the contract too.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio as studio_router
from app.routers import studio_audio as studio_audio_router
from app.routers import studio_export as studio_export_router
from app.routers import studio_musicxml
from app.studio import dispatch, musicxml_sentence
from app.studio.candidates import villa_candidate_spec
from app.studio.sentence_spec import parse_spec
from app.studio.villa_preview import validate_villa_spec

_AUDIO_URL = re.compile(r"^/v1/studio/sentence/audio/[0-9a-f]{64}\.wav$")
_SESSION = "X-Studio-Session"


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("VSTOCK_STUDIO_DIR", str(tmp_path / "studio"))
    monkeypatch.setenv("VSTOCK_STUDIO_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.delenv("VSTOCK_STUDIO_MUSICXML_DRAFTS_PER_DAY", raising=False)
    monkeypatch.delenv("VSTOCK_STUDIO_MUSICXML_TTL_SECONDS", raising=False)
    monkeypatch.delenv(
        "VSTOCK_STUDIO_MUSICXML_PASSAGE_TTL_SECONDS", raising=False
    )
    studio_musicxml.clear_store()
    yield
    studio_musicxml.clear_store()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_musicxml.router)
    app.include_router(studio_audio_router.router)
    app.include_router(studio_export_router.router)
    app.include_router(studio_router.router)
    return TestClient(app, headers={"X-Studio-Session": "test-musicxml"})


def _score(measures: str) -> bytes:
    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        f'</part-list><part id="P1">{measures}</part></score-partwise>'
    ).encode("utf-8")


def _waltz_fixture(bars: int = 4) -> bytes:
    """Clean 3/4 bars: one dotted-half note per bar."""
    measures = []
    for index in range(bars):
        attributes = (
            "<attributes><divisions>2</divisions>"
            "<time><beats>3</beats><beat-type>4</beat-type></time>"
            "</attributes>"
            if index == 0
            else ""
        )
        measures.append(
            f"""<measure number="{index + 1}">{attributes}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>6</duration><voice>1</voice><type>half</type>
                <dot/></note>
            </measure>"""
        )
    return _score("".join(measures))


def _two_four_fixture(bars: int = 4) -> bytes:
    measures = []
    for index in range(bars):
        attributes = (
            "<attributes><divisions>2</divisions>"
            "<time><beats>2</beats><beat-type>4</beat-type></time>"
            "</attributes>"
            if index == 0
            else ""
        )
        measures.append(
            f"""<measure number="{index + 1}">{attributes}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>4</duration><voice>1</voice><type>half</type></note>
            </measure>"""
        )
    return _score("".join(measures))


def _six_eight_fixture(bars: int = 2) -> bytes:
    measures = []
    for index in range(bars):
        attributes = (
            "<attributes><divisions>2</divisions>"
            "<time><beats>6</beats><beat-type>8</beat-type></time></attributes>"
            if index == 0
            else ""
        )
        measures.append(
            f"""<measure number="{index + 1}">{attributes}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>6</duration><voice>1</voice><type>half</type>
                <dot/></note>
            </measure>"""
        )
    return _score("".join(measures))


def _upload(
    client: TestClient,
    data: bytes | None = None,
    *,
    session: str | None = None,
    filename: str = "study.musicxml",
):
    headers = {_SESSION: session} if session is not None else {}
    return client.post(
        "/v1/studio/import/musicxml",
        files={
            "file": (
                filename,
                _waltz_fixture() if data is None else data,
                "application/xml",
            )
        },
        headers=headers,
    )


def _draft(client: TestClient, import_id: str, *, session: str | None = None, **body):
    headers = {_SESSION: session} if session is not None else {}
    return client.post(
        f"/v1/studio/import/musicxml/{import_id}/sentence-draft",
        json=body,
        headers=headers,
    )


def _new_pattern(**overrides):
    payload = {
        "id": "villa_choro_mazurka",
        "label": "Choro-Mazurka",
        "composer": "Villa-Lobos",
        "renderer": "villa",
        "templateId": "suite_mazurka_arpeggio_aaba",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Existing pattern drafts


def test_existing_castillo_three_four_draft_previews_and_saves_audio() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    response = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True, body["errors"]
    assert body["mode"] == "existing"
    assert body["productionReady"] is True
    assert body["templateId"] in {"castillo_34_cadence", "castillo_34_walk"}

    spec = parse_spec(body["spec"])
    assert spec.pattern == "castillo"
    assert spec.meter == "3/4"
    assert spec.id.startswith("musicxml_")
    assert body["spec"]["id"] == spec.id

    assert body["fixture"]["pattern"] == "castillo"
    assert body["fixture"]["meter"] == "3/4"
    assert body["fixture"]["length"] == 4
    assert body["fixture"]["n"] in (0, 1)
    assert body["fixture"]["closes"] is False
    assert body["fixture"]["rise"] == 0

    preview = body["preview"]
    assert preview["renderHash"].startswith("sha256:")
    assert _AUDIO_URL.match(preview["audioUrl"] or "")
    assert preview["durationSec"] > 0.0
    assert preview["notes"] > 0
    assert any("spans 9 bars" in warning for warning in body["warnings"])

    audio = client.get(preview["audioUrl"])
    assert audio.status_code == 200
    assert audio.content[:4] == b"RIFF"


def test_blank_template_id_is_the_auto_option_for_existing_mode() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    for blank in ("", "   "):
        body = _draft(
            client,
            import_id,
            barStart=1,
            barEnd=4,
            mode="existing",
            pattern="castillo",
            templateId=blank,
        ).json()
        assert body["ok"] is True, body["errors"]
        assert body["templateId"] in {"castillo_34_cadence", "castillo_34_walk"}


def test_explicit_template_id_is_honoured() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
        templateId="castillo_34_walk",
    ).json()
    assert body["ok"] is True, body["errors"]
    assert body["templateId"] == "castillo_34_walk"
    assert [slot["figure"] for slot in body["spec"]["slots"]] == [13]


def test_a_partial_beat_range_drafts_whole_bars_with_a_warning() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        beatStart=1,
        barEnd=2,
        beatEnd=2,
        mode="existing",
        pattern="castillo",
    ).json()
    assert body["ok"] is True, body["errors"]
    assert body["fixture"]["length"] == 2
    assert any("bar-based" in warning for warning in body["warnings"])


def test_mixed_meter_range_is_a_structured_error() -> None:
    client = _client()
    uploaded = _upload(
        client,
        b"""<score-partwise version="4.0"><part-list>
          <score-part id="P1"><part-name>Guitar</part-name></score-part>
        </part-list><part id="P1">
          <measure number="1"><attributes><divisions>1</divisions>
            <time><beats>3</beats><beat-type>4</beat-type></time>
          </attributes><note><pitch><step>E</step><octave>4</octave></pitch>
            <duration>3</duration><voice>1</voice></note></measure>
          <measure number="2"><attributes><divisions>1</divisions>
            <time><beats>4</beats><beat-type>4</beat-type></time>
          </attributes><note><pitch><step>E</step><octave>4</octave></pitch>
            <duration>4</duration><voice>1</voice></note></measure>
        </part></score-partwise>""",
        filename="mixed.musicxml",
    ).json()

    body = _draft(
        client,
        uploaded["importId"],
        barStart=1,
        barEnd=2,
        mode="existing",
        pattern="castillo",
    ).json()
    assert body["ok"] is False
    assert [error["path"] for error in body["errors"]] == ["meter"]
    assert "constant meter" in body["errors"][0]["message"]


def test_suite_patterns_are_rejected_before_preview() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="suite_mazurka",
    ).json()
    assert body["ok"] is False
    assert [error["path"] for error in body["errors"]] == ["pattern"]
    assert "single-sentence suite gate" in body["errors"][0]["message"]


def test_unknown_existing_patterns_are_rejected() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="villa_pattern",
    ).json()
    assert body["ok"] is False
    assert [error["path"] for error in body["errors"]] == ["pattern"]


def test_no_template_for_the_passage_meter_is_a_clear_error() -> None:
    client = _client()
    uploaded = _upload(client, _six_eight_fixture()).json()

    body = _draft(
        client,
        uploaded["importId"],
        barStart=1,
        barEnd=2,
        mode="existing",
        pattern="castillo",
    ).json()
    assert body["ok"] is False
    assert [error["path"] for error in body["errors"]] == ["pattern"]
    assert "6/8" in body["errors"][0]["message"]


def test_existing_template_meter_mismatch_is_rejected() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
        templateId="castillo_44_short",
    ).json()
    assert body["ok"] is False
    assert [error["path"] for error in body["errors"]] == ["templateId"]
    assert "4/4" in body["errors"][0]["message"]
    assert "3/4" in body["errors"][0]["message"]


# ---------------------------------------------------------------------------
# New Villa pattern drafts


def test_new_villa_pattern_previews_with_the_draft_family_override() -> None:
    client = _client()
    import_id = _upload(client, _waltz_fixture(5)).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=2,
        barEnd=5,
        mode="new",
        newPattern=_new_pattern(),
    ).json()
    assert body["ok"] is True, body["errors"]
    assert body["mode"] == "new"
    assert body["productionReady"] is False
    assert body["templateId"] == "suite_mazurka_arpeggio_aaba"
    assert body["spec"]["pattern"] == "villa_choro_mazurka"
    assert body["spec"]["meter"] == "3/4"
    assert body["fixture"]["pattern"] == "villa_choro_mazurka"
    assert _AUDIO_URL.match(body["preview"]["audioUrl"] or "")
    assert body["preview"]["notes"] > 0

    spec = parse_spec(body["spec"])
    assert spec.pattern == "villa_choro_mazurka"

    # The new pattern is invisible to the production dispatcher until a caller
    # supplies the draft family explicitly.
    assert dispatch.family_for(spec.pattern) is None
    assert dispatch.validate(spec)[0].path == "pattern"
    assert dispatch.validate(spec, family="villa") == []
    assert dispatch.preview_sentence(
        spec, body["fixture"], family="villa"
    ).ok is True
    assert dispatch.resolve_fixture(
        spec, body["fixture"], family="villa"
    )["pattern"] == "villa_choro_mazurka"

    # Production routes must not expose the draft family override. A new
    # pattern is previewable only through the MusicXML sentence-draft endpoint.
    audio = client.post(
        "/v1/studio/sentence/audio",
        json={
            "spec": body["spec"],
            "fixture": body["fixture"],
            "family": "villa",
        },
    ).json()
    assert audio["ok"] is False

    exported = client.post(
        "/v1/studio/sentence/export",
        json={
            "spec": body["spec"],
            "fixture": body["fixture"],
            "family": "villa",
        },
    ).json()
    assert exported["ok"] is False


def test_blank_template_ids_auto_pick_a_villa_template() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="new",
        templateId="",
        newPattern=_new_pattern(templateId=""),
    ).json()
    assert body["ok"] is True, body["errors"]
    assert body["templateId"] == "suite_mazurka_arpeggio_aaba"
    assert body["spec"]["pattern"] == "villa_choro_mazurka"
    assert body["preview"]["notes"] > 0


def test_new_pattern_ids_collide_with_existing_registries() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    for pattern_id, expected in (
        ("castillo", "already in the pattern registry"),
        ("villa_pattern", "already in the pattern registry"),
        ("suite_mazurka", "single-sentence suite gate"),
    ):
        body = _draft(
            client,
            import_id,
            barStart=1,
            barEnd=4,
            mode="new",
            newPattern=_new_pattern(id=pattern_id),
        ).json()
        assert body["ok"] is False
        errors = body["errors"]
        assert [error["path"] for error in errors] == ["newPattern.id"]
        assert expected in errors[0]["message"]


def test_new_pattern_requires_the_mvp_renderer_and_known_template() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    bad_renderer = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="new",
        newPattern=_new_pattern(renderer="torroba_sor"),
    ).json()
    assert bad_renderer["ok"] is False
    assert [error["path"] for error in bad_renderer["errors"]] == [
        "newPattern.renderer"
    ]

    unknown_template = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="new",
        newPattern=_new_pattern(templateId="no_such_template"),
    ).json()
    assert unknown_template["ok"] is False
    assert [error["path"] for error in unknown_template["errors"]] == [
        "newPattern.templateId"
    ]


def test_new_pattern_meter_mismatch_is_rejected() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="new",
        newPattern=_new_pattern(meter="4/4"),
    ).json()
    assert body["ok"] is False
    assert [error["path"] for error in body["errors"]] == ["newPattern.meter"]


# ---------------------------------------------------------------------------
# Owner scoping


def test_imports_are_owner_scoped_and_content_ids_include_the_owner() -> None:
    client = _client()
    first = _upload(client, session="owner-a").json()
    second = _upload(client, session="owner-b").json()
    assert first["importId"] != second["importId"]

    missing = client.get(
        f"/v1/studio/import/musicxml/{first['importId']}",
        headers={_SESSION: "owner-b"},
    )
    assert missing.status_code == 404

    foreign_passage = client.post(
        f"/v1/studio/import/musicxml/{first['importId']}/passage",
        json={"barStart": 1, "barEnd": 2},
        headers={_SESSION: "owner-b"},
    )
    assert foreign_passage.status_code == 404

    foreign_draft = _draft(
        client,
        first["importId"],
        session="owner-b",
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
    )
    assert foreign_draft.status_code == 404

    owned = _draft(
        client,
        first["importId"],
        session="owner-a",
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
    )
    assert owned.status_code == 200
    assert owned.json()["ok"] is True

    passage = client.post(
        f"/v1/studio/import/musicxml/{first['importId']}/passage",
        json={"barStart": 1, "barEnd": 2},
        headers={_SESSION: "owner-a"},
    ).json()
    passage_id = passage["passageId"]
    assert client.get(
        f"/v1/studio/import/musicxml/passages/{passage_id}",
        headers={_SESSION: "owner-b"},
    ).status_code == 404
    assert client.get(
        f"/v1/studio/import/musicxml/passages/{passage_id}",
        headers={_SESSION: "owner-a"},
    ).status_code == 200


def test_missing_records_after_ttl_are_404() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    passage = client.post(
        f"/v1/studio/import/musicxml/{import_id}/passage",
        json={"barStart": 1, "barEnd": 2},
    ).json()
    passage_id = passage["passageId"]

    studio_musicxml.clear_store()

    assert client.get(
        f"/v1/studio/import/musicxml/{import_id}"
    ).status_code == 404
    assert client.post(
        f"/v1/studio/import/musicxml/{import_id}/passage",
        json={"barStart": 1, "barEnd": 2},
    ).status_code == 404
    assert client.get(
        f"/v1/studio/import/musicxml/passages/{passage_id}"
    ).status_code == 404
    assert _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
    ).status_code == 404


# ---------------------------------------------------------------------------
# Quota and seams


def test_draft_quota_is_per_owner_and_returns_429(monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_MUSICXML_DRAFTS_PER_DAY", "1")
    client = _client()
    import_id = _upload(client).json()["importId"]

    body = {
        "barStart": 1,
        "barEnd": 4,
        "mode": "existing",
        "pattern": "castillo",
    }
    first = _draft(client, import_id, **body)
    assert first.status_code == 200
    assert first.json()["ok"] is True

    second = _draft(client, import_id, **body)
    assert second.status_code == 429
    payload = second.json()
    assert payload["ok"] is False
    assert [error["path"] for error in payload["errors"]] == ["quota"]
    assert payload["limit"] == 1
    assert second.headers["Retry-After"]

    # Another owner has their own counter.
    other = _upload(client, session="owner-b").json()
    third = _draft(
        client, other["importId"], session="owner-b", **body
    )
    assert third.status_code == 200
    assert third.json()["ok"] is True


def test_malformed_requests_do_not_spend_quota(monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_MUSICXML_DRAFTS_PER_DAY", "1")
    client = _client()
    import_id = _upload(client).json()["importId"]

    bad = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="suite_mazurka",
    )
    assert bad.status_code == 200
    assert bad.json()["ok"] is False

    good = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=4,
        mode="existing",
        pattern="castillo",
    )
    assert good.status_code == 200
    assert good.json()["ok"] is True


def test_villa_whitelist_seam_is_opt_in() -> None:
    spec = replace(
        villa_candidate_spec(),
        id="draft_villa_pattern",
        pattern="draft_villa_pattern",
    )
    assert validate_villa_spec(spec)[0].path == "pattern"
    assert validate_villa_spec(spec, allowed_patterns={spec.pattern}) == []
    assert validate_villa_spec(spec, allow_draft_pattern=True) == []


def test_template_choice_is_deterministic() -> None:
    first, first_errors = musicxml_sentence.choose_template(
        "castillo", "3/4", 4
    )
    second, second_errors = musicxml_sentence.choose_template(
        "castillo", "3/4", 4
    )
    assert first_errors == second_errors == []
    assert first is not None and second is not None
    assert first.id == second.id


def _two_four_fixture(bars: int = 2) -> bytes:
    measures = []
    for index in range(bars):
        attributes = (
            "<attributes><divisions>2</divisions>"
            "<time><beats>2</beats><beat-type>4</beat-type></time>"
            "</attributes>"
            if index == 0
            else ""
        )
        measures.append(
            f"""<measure number="{index + 1}">{attributes}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>4</duration><voice>1</voice><type>half</type></note>
            </measure>"""
        )
    return _score("".join(measures))


def test_new_two_four_pattern_uses_the_default_villa_template() -> None:
    client = _client()
    import_id = _upload(client, _two_four_fixture()).json()["importId"]

    body = _draft(
        client,
        import_id,
        barStart=1,
        barEnd=2,
        mode="new",
        newPattern=_new_pattern(
            id="villa_schottish_choro",
            label="Schottish-Choro",
            meter="2/4",
            templateId="",
        ),
    ).json()

    assert body["ok"] is True, body["errors"]
    assert body["spec"]["meter"] == "2/4"
    assert body["spec"]["pattern"] == "villa_schottish_choro"
    assert body["templateId"] == "villa_2_4_arpeggio"
    assert body["fixture"]["meter"] == "2/4"
    assert _AUDIO_URL.match(body["preview"]["audioUrl"] or "")
    assert body["preview"]["notes"] > 0
