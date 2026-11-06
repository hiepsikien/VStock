"""MusicXML import → TextureSpec → preview audio through the Studio API.

The fixture is a synthetic solo-guitar score so the test does not depend on a
committed engraving: four 4/4 measures, a written-octave transpose, a tie across
a barline, a chord, two voices, a slur, tab metadata, and a tempo marking.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_audio as studio_audio_router
from app.routers import studio_musicxml
from app.studio import audio as studio_audio
from app.studio import musicxml_source
from app.studio.texture_spec import (
    parse_texture_spec,
    texture_spec_to_mapping,
    validate_texture_spec,
)

_AUDIO_URL = re.compile(r"^/v1/studio/sentence/audio/[0-9a-f]{64}\.wav$")


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("VSTOCK_STUDIO_DIR", str(tmp_path / "studio"))
    monkeypatch.setenv("VSTOCK_STUDIO_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.delenv("VSTOCK_STUDIO_MUSICXML_MAX_BYTES", raising=False)
    monkeypatch.delenv("VSTOCK_STUDIO_MUSICXML_TTL_SECONDS", raising=False)
    monkeypatch.delenv("VSTOCK_STUDIO_MUSICXML_PASSAGE_TTL_SECONDS", raising=False)
    studio_musicxml.clear_store()
    yield
    studio_musicxml.clear_store()


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_musicxml.router)
    app.include_router(studio_audio_router.router)
    return TestClient(app)


def _fixture(meter: str = "4/4") -> bytes:
    beats, beat_type = meter.split("/")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <work><work-title>Study in E minor</work-title></work>
  <part-list>
    <score-part id="P1"><part-name>Guitar</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>2</divisions>
        <key><fifths>0</fifths><mode>minor</mode></key>
        <time><beats>{beats}</beats><beat-type>{beat_type}</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
        <transpose><chromatic>-12</chromatic></transpose>
      </attributes>
      <direction placement="above">
        <direction-type>
          <metronome><beat-unit>quarter</beat-unit><per-minute>96</per-minute></metronome>
        </direction-type>
        <sound tempo="96"/>
      </direction>
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type><staff>1</staff>
        <tie type="start"/>
        <notations>
          <tied type="start"/>
          <articulations><accent/></articulations>
          <technical><string>1</string><fret>0</fret></technical>
        </notations>
      </note>
      <note><rest/><duration>4</duration><voice>1</voice><type>half</type></note>
    </measure>
    <measure number="2">
      <note>
        <pitch><step>E</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type>
        <tie type="stop"/><notations><tied type="stop"/></notations>
      </note>
      <note>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type>
      </note>
    </measure>
    <measure number="3">
      <note>
        <pitch><step>G</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type>
      </note>
      <note>
        <chord/>
        <pitch><step>B</step><octave>4</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type>
      </note>
      <note><rest/><duration>4</duration><voice>1</voice><type>half</type></note>
    </measure>
    <measure number="4">
      <note>
        <pitch><step>C</step><octave>5</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type>
        <notations>
          <slur type="start" number="1"/>
          <technical><string>2</string><fret>1</fret></technical>
        </notations>
      </note>
      <note>
        <pitch><step>D</step><octave>5</octave></pitch>
        <duration>4</duration><voice>1</voice><type>half</type>
        <notations>
          <slur type="stop" number="1"/>
          <articulations><staccato/></articulations>
        </notations>
      </note>
      <backup><duration>8</duration></backup>
      <note>
        <pitch><step>A</step><octave>3</octave></pitch>
        <duration>8</duration><voice>2</voice><type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>
""".encode("utf-8")


def _compound_fixture() -> bytes:
    """Two clean 6/8 bars: one dotted-half note per bar (3 quarter beats)."""
    attributes = (
        "<attributes><divisions>2</divisions>"
        "<time><beats>6</beats><beat-type>8</beat-type></time></attributes>"
    )
    measures = []
    for index in range(2):
        measures.append(
            f"""<measure number="{index + 1}">{attributes if index == 0 else ''}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>6</duration><voice>1</voice><type>half</type>
                <dot/></note>
            </measure>"""
        )
    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        f'</part-list><part id="P1">{"".join(measures)}</part></score-partwise>'
    ).encode("utf-8")


def _meter_change_fixture() -> bytes:
    """Bar 1 is 1/4; bars 2..5 change to 2/4 (bars 3..5 inherit it)."""
    meters = ("1/4", "2/4", "2/4", "2/4", "2/4")
    measures = []
    for index, meter in enumerate(meters):
        beats, beat_type = meter.split("/")
        time = (
            f"<time><beats>{beats}</beats><beat-type>{beat_type}</beat-type>"
            "</time>"
            if index in (0, 1)
            else ""
        )
        measure_meter = (
            f"<attributes><divisions>1</divisions>{time}</attributes>"
            if time
            else ""
        )
        measures.append(
            f"""<measure number="{index + 1}">{measure_meter}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>{beats}</duration><voice>1</voice></note>
            </measure>"""
        )
    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        f'</part-list><part id="P1">{"".join(measures)}</part></score-partwise>'
    ).encode("utf-8")


def _waltz_fixture() -> bytes:
    """Three clean 3/4 bars: one dotted-half note per bar (3 quarter beats)."""
    measures = []
    for index in range(3):
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
    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        f'</part-list><part id="P1">{"".join(measures)}</part></score-partwise>'
    ).encode("utf-8")


def _upload(
    client: TestClient,
    data: bytes | None = None,
    filename: str = "study.musicxml",
):
    return client.post(
        "/v1/studio/import/musicxml",
        files={
            "file": (
                filename,
                _fixture() if data is None else data,
                "application/xml",
            )
        },
    )


def _long_fixture(bars: int = 40) -> bytes:
    """Whole notes in 4/4: long enough that the 45 s synth cap must reject it."""
    measures = []
    for index in range(bars):
        attributes = (
            "<attributes><divisions>2</divisions>"
            "<time><beats>4</beats><beat-type>4</beat-type></time></attributes>"
            if index == 0
            else ""
        )
        measures.append(
            f"""<measure number="{index + 1}">{attributes}
              <note><pitch><step>E</step><octave>4</octave></pitch>
                <duration>8</duration><voice>1</voice><type>whole</type></note>
            </measure>"""
        )
    return (
        '<score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>Guitar</part-name></score-part>'
        f'</part-list><part id="P1">{"".join(measures)}</part></score-partwise>'
    ).encode("utf-8")


def _passage(client: TestClient, import_id: str, **body):
    return client.post(f"/v1/studio/import/musicxml/{import_id}/passage", json=body)


# ---------------------------------------------------------------------------
# Parser seam


def test_parser_seam_exposes_the_contract() -> None:
    score = musicxml_source.parse_musicxml(_fixture(), filename="study.musicxml")
    summary = musicxml_source.score_summary(score)
    assert score.measure_count == 4
    assert score.meter == "4/4"
    assert score.title == "Study in E minor"
    assert summary["noteCount"] == 8
    assert len(score.notes) == 10  # 8 pitched + 2 explicit rests
    sliced = musicxml_source.slice_score(score, bar_start=1, bar_end=2)
    assert len(sliced) < len(score.notes)
    assert all(0 <= note["bar"] <= 1 for note in sliced)


# ---------------------------------------------------------------------------
# Upload + read


def test_upload_returns_summary_notes_and_warnings() -> None:
    client = _client()
    response = _upload(client)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["ok"] is True
    assert body["importId"].startswith("mxi_")
    assert body["filename"] == "study.musicxml"
    assert body["summary"]["meter"] == "4/4"
    assert body["summary"]["measureCount"] == 4
    assert body["summary"]["noteCount"] == 8
    assert body["summary"]["keyMode"] == "minor"
    assert body["summary"]["tempo"] == 96.0
    assert body["summary"]["meterSupported"] is True
    assert body["summary"]["measureMeters"] == ["4/4"] * 4
    assert body["summary"]["meterChanges"] == []
    assert body["summary"]["sourceHash"].startswith("sha256:")
    assert isinstance(body["warnings"], list)

    notes = body["notes"]
    assert len(notes) == 10  # explicit rests stay in the event stream
    first = notes[0]
    assert first["bar"] == 0
    assert first["beat"] == 0.0
    assert first["duration"] == 2.0
    assert first["midi"] == 52  # written E4, guitar transpose -12
    assert first["written_pitch"] == "E4"
    assert first["sounding_pitch"] == "E3"
    assert first["voice"] == 1
    assert first["staff"] == 1
    assert first["tie"] == "start"
    assert first["accent"] is True
    assert first["string"] == 1 and first["fret"] == 0


def test_upload_is_idempotent_by_content() -> None:
    client = _client()
    first = _upload(client).json()
    second = _upload(client).json()
    assert first["importId"] == second["importId"]
    assert first["summary"] == second["summary"]


def test_get_import_returns_the_stored_score() -> None:
    client = _client()
    uploaded = _upload(client).json()
    response = client.get(f"/v1/studio/import/musicxml/{uploaded['importId']}")
    assert response.status_code == 200
    assert response.json()["notes"] == uploaded["notes"]
    assert response.json()["summary"] == uploaded["summary"]


def test_get_unknown_import_is_404() -> None:
    client = _client()
    response = client.get("/v1/studio/import/musicxml/mxi_0000000000000000")
    assert response.status_code == 404


def test_upload_rejects_a_non_musicxml_extension() -> None:
    client = _client()
    response = _upload(client, b"<score-partwise/>", filename="score.txt")
    assert response.status_code == 415
    assert response.json()["errors"][0]["path"] == "file"


def test_upload_rejects_malformed_xml() -> None:
    client = _client()
    response = _upload(client, b"<score-partwise><part>", filename="broken.musicxml")
    assert response.status_code == 400
    body = response.json()
    assert body["ok"] is False
    assert body["errors"][0]["path"] == "file"


def test_upload_rejects_a_score_without_notes() -> None:
    client = _client()
    empty = b"""<score-partwise version="4.0"><part-list>
      <score-part id="P1"><part-name>Guitar</part-name></score-part></part-list>
      <part id="P1"><measure number="1">
        <attributes><divisions>1</divisions></attributes>
        <note><rest/><duration>4</duration><voice>1</voice></note>
      </measure></part></score-partwise>"""
    response = _upload(client, empty, filename="empty.xml")
    assert response.status_code == 400


def test_upload_rejects_oversized_files(monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_MUSICXML_MAX_BYTES", "128")
    client = _client()
    response = _upload(client, b"x" * 256, filename="big.musicxml")
    assert response.status_code == 413
    assert response.json()["ok"] is False


# ---------------------------------------------------------------------------
# Passage → TextureSpec → audio


def test_passage_builds_a_round_trippable_spec_and_audio() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]

    response = _passage(client, import_id, barStart=1, barEnd=4)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True, body["errors"]
    assert body["errors"] == []
    assert body["passageId"].startswith("mxp_")
    assert _AUDIO_URL.match(body["audioUrl"] or "")
    assert body["durationSec"] > 0.0

    spec = body["spec"]
    parsed = parse_texture_spec(spec)
    assert texture_spec_to_mapping(parsed) == spec
    assert validate_texture_spec(parsed, meter=parsed.meter_variants[0].meter) == ()

    variant = spec["meter_variants"][0]
    assert variant["meter"]["id"] == "4/4"
    assert variant["meter"]["beats"] == 4
    assert variant["unsupported"] is True

    events = spec["authored"]["events"]
    assert len(events) == 8
    assert {event["bar"] for event in events} == {0, 1, 2, 3}
    assert all(event["pitch"]["kind"] == "literal_midi" for event in events)
    assert all(event["review"] == "edited" for event in events)
    assert all(isinstance(event["pitch"]["value"], int) for event in events)
    assert events[0]["bar"] == 0
    assert events[0]["beat"] == 0.0
    assert events[0]["pitch"]["value"] == 52
    assert events[0]["written_pitch"] == "E4"
    assert events[0]["sounding_pitch"] == "E3"
    assert events[0]["tie"] == "start"
    assert events[0]["accent"] is True
    assert any(event["tie"] == "stop" for event in events)
    assert any(event["slur"] == "start" for event in events)
    assert any(event["staccato"] for event in events)
    assert any(
        event.get("string") == 2 and event.get("fret") == 1 for event in events
    )

    # Simultaneous chord tones are spread over authored voices so no voice
    # overlaps, which is what the validator requires.
    voices = sorted({event["voice"] for event in events})
    assert voices == [1, 2]

    notes = body["notes"]
    assert len(notes) == 8
    assert {note["bar"] for note in notes} == {0, 1, 2, 3}
    assert all(
        set(note) == {
            "bar",
            "beat",
            "duration",
            "midi",
            "voice",
            "velocity",
            "accent",
            "staccato",
        }
        for note in notes
    )
    assert all(note["velocity"] == 64 for note in notes)
    assert {note["midi"] for note in notes} == {52, 59, 55, 60, 62, 45}

    audio = client.get(body["audioUrl"])
    assert audio.status_code == 200
    assert audio.content[:4] == b"RIFF"
    assert audio.headers["content-type"].startswith("audio/wav")


def test_passage_keeps_rests_out_of_the_authored_events() -> None:
    """An empty cell is a rest: it stays in notes, never in the spec."""
    client = _client()
    import_id = _upload(client).json()["importId"]
    body = _passage(client, import_id, barStart=1, barEnd=2).json()

    assert body["ok"] is True, body["errors"]
    assert not any("without a MIDI pitch" in item for item in body["warnings"])
    rest_events = [note for note in body["notes"] if note.get("rest")]
    assert rest_events == []
    authored = body["spec"]["authored"]["events"]
    assert all(event["duration_beats"] > 0 for event in authored)


def test_passage_is_deterministic() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    first = _passage(client, import_id, barStart=1, barEnd=4).json()
    second = _passage(client, import_id, barStart=1, barEnd=4).json()
    assert first["passageId"] == second["passageId"]
    assert first["audioUrl"] == second["audioUrl"]
    assert first["durationSec"] == second["durationSec"]
    assert first["notes"] == second["notes"]


def test_get_passage_returns_the_same_payload() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    created = _passage(client, import_id, barStart=1, barEnd=2).json()
    fetched = client.get(
        f"/v1/studio/import/musicxml/passages/{created['passageId']}"
    )
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_passage_rebases_bars_and_filters_voices() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    body = _passage(client, import_id, barStart=3, barEnd=4, voices=[1]).json()
    assert body["ok"] is True, body["errors"]
    assert {event["bar"] for event in body["spec"]["authored"]["events"]} == {0, 1}
    assert {note["bar"] for note in body["notes"]} == {0, 1}
    assert all(note["midi"] != 45 for note in body["notes"])


def test_slicing_a_pickup_tie_at_the_passage_edge_is_clean() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    # Bars 2-4 cut the E tie open at bar 2: only the stop would remain.
    body = _passage(client, import_id, barStart=2, barEnd=4).json()
    assert body["ok"] is True, body["errors"]
    events = body["spec"]["authored"]["events"]
    assert events[0]["bar"] == 0
    assert events[0]["tie"] == "none"
    assert all(event["tie"] != "stop" for event in events)
    assert validate_texture_spec(
        parse_texture_spec(body["spec"]),
        meter=parse_texture_spec(body["spec"]).meter_variants[0].meter,
    ) == ()


def test_passage_rejects_invalid_ranges() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    for body, path in (
        ({"barStart": 0, "barEnd": 2}, "barStart"),
        ({"barStart": 1, "barEnd": 5}, "barEnd"),
        ({"barStart": 4, "barEnd": 2}, "barEnd"),
    ):
        response = _passage(client, import_id, **body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is False
        assert path in {error["path"] for error in payload["errors"]}
        assert payload["spec"] is None


def test_passage_rejects_invalid_voices() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    for voices, path in (([0], "voices[0]"), ([5], "voices[0]"), ([], "voices")):
        payload = _passage(
            client, import_id, barStart=1, barEnd=2, voices=voices
        ).json()
        assert payload["ok"] is False
        assert path in {error["path"] for error in payload["errors"]}


def test_passage_unknown_import_is_404() -> None:
    client = _client()
    response = _passage(client, "mxi_ffffffffffffffff", barStart=1, barEnd=1)
    assert response.status_code == 404


def test_get_unknown_passage_is_404() -> None:
    client = _client()
    response = client.get(
        "/v1/studio/import/musicxml/passages/mxp_ffffffffffffffff"
    )
    assert response.status_code == 404


def test_unsupported_meter_returns_an_error_and_no_audio() -> None:
    client = _client()
    uploaded = _upload(client, _fixture("5/4")).json()
    assert uploaded["summary"]["meterSupported"] is False

    body = _passage(client, uploaded["importId"], barStart=1, barEnd=1).json()
    assert body["ok"] is False
    assert body["spec"] is None
    assert body["audioUrl"] is None
    assert body["notes"] == []
    assert [error["path"] for error in body["errors"]] == ["meter"]


def test_six_eight_uses_three_quarter_beats_for_audio() -> None:
    client = _client()
    uploaded = _upload(client, _compound_fixture()).json()
    assert uploaded["summary"]["meter"] == "6/8"
    assert uploaded["summary"]["meterSupported"] is True

    body = _passage(client, uploaded["importId"], barStart=1, barEnd=2).json()
    assert body["ok"] is True, body["errors"]
    variant = body["spec"]["meter_variants"][0]
    assert variant["meter"]["id"] == "6/8"
    assert variant["meter"]["eighths_per_bar"] == 6
    assert body["audioUrl"] is not None
    # Two bars × 3 quarter beats at 96 BPM ≈ 3.75 s, plus the 0.5 s tail.
    assert body["durationSec"] == pytest.approx(4.25, abs=0.05)


def test_summary_reports_per_measure_meters_and_one_based_changes() -> None:
    client = _client()
    uploaded = _upload(client, _meter_change_fixture()).json()
    summary = uploaded["summary"]

    assert summary["meter"] == "1/4"
    assert summary["measureCount"] == 5
    assert summary["measureMeters"] == ["1/4", "2/4", "2/4", "2/4", "2/4"]
    assert summary["meterChanges"] == [{"bar": 2, "meter": "2/4"}]
    assert summary["meterSupported"] is True


def test_two_four_passage_builds_spec_and_audio() -> None:
    client = _client()
    import_id = _upload(client, _meter_change_fixture()).json()["importId"]

    body = _passage(client, import_id, barStart=2, barEnd=5).json()
    assert body["ok"] is True, body["errors"]
    assert body["meter"] == "2/4"
    assert body["beatsPerBar"] == 2
    assert _AUDIO_URL.match(body["audioUrl"] or "")
    # Four 2/4 bars at 96 BPM (2 quarter beats each) plus the 0.5 s tail.
    assert body["durationSec"] == pytest.approx(5.5, abs=0.05)

    variant = body["spec"]["meter_variants"][0]
    assert variant["meter"]["id"] == "2/4"
    assert variant["meter"]["beats"] == 2
    assert variant["meter"]["eighths_per_bar"] == 4
    assert {event["bar"] for event in body["spec"]["authored"]["events"]} == {
        0,
        1,
        2,
        3,
    }
    assert len(body["notes"]) == 4


def test_one_four_pickup_passage_builds_spec_and_audio() -> None:
    client = _client()
    import_id = _upload(client, _meter_change_fixture()).json()["importId"]

    body = _passage(client, import_id, barStart=1, barEnd=1).json()
    assert body["ok"] is True, body["errors"]
    assert body["meter"] == "1/4"
    assert body["beatsPerBar"] == 1
    assert _AUDIO_URL.match(body["audioUrl"] or "")
    # One 1/4 bar at 96 BPM plus the 0.5 s tail.
    assert body["durationSec"] == pytest.approx(1.125, abs=0.05)

    variant = body["spec"]["meter_variants"][0]
    assert variant["meter"]["id"] == "1/4"
    assert variant["meter"]["beats"] == 1
    assert variant["meter"]["eighths_per_bar"] == 2
    assert {event["bar"] for event in body["spec"]["authored"]["events"]} == {0}


def test_mixed_meter_range_is_rejected_honestly() -> None:
    client = _client()
    import_id = _upload(client, _meter_change_fixture()).json()["importId"]

    response = _passage(client, import_id, barStart=1, barEnd=2)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["spec"] is None
    assert body["audioUrl"] is None
    assert body["notes"] == []
    assert body["meter"] is None
    assert body["beatsPerBar"] is None
    assert [error["path"] for error in body["errors"]] == ["meter"]
    message = body["errors"][0]["message"]
    assert "1/4" in message and "2/4" in message
    assert "constant meter" in message


def test_three_four_waltz_passage_still_works() -> None:
    client = _client()
    uploaded = _upload(client, _waltz_fixture()).json()
    assert uploaded["summary"]["meter"] == "3/4"
    assert uploaded["summary"]["measureMeters"] == ["3/4"] * 3
    assert uploaded["summary"]["meterChanges"] == []

    body = _passage(client, uploaded["importId"], barStart=1, barEnd=3).json()
    assert body["ok"] is True, body["errors"]
    assert body["meter"] == "3/4"
    assert body["beatsPerBar"] == 3
    assert body["spec"]["meter_variants"][0]["meter"]["id"] == "3/4"
    assert _AUDIO_URL.match(body["audioUrl"] or "")
    # Three 3/4 bars at 96 BPM (3 quarter beats each) plus the 0.5 s tail.
    assert body["durationSec"] == pytest.approx(6.125, abs=0.05)


def test_ensure_audio_accepts_one_and_two_beat_bars() -> None:
    def note(duration: float) -> list[dict]:
        return [
            {
                "bar": 0,
                "beat": 0.0,
                "duration": duration,
                "midi": 64,
                "voice": 1,
                "velocity": 64,
            }
        ]

    one = studio_audio.ensure_audio("sha256:" + "a" * 64, note(1.0), 1)
    two = studio_audio.ensure_audio("sha256:" + "b" * 64, note(2.0), 2)
    assert _AUDIO_URL.match(one.audio_url)
    assert _AUDIO_URL.match(two.audio_url)
    assert one.audio_url != two.audio_url
    assert one.duration_sec == pytest.approx(0.625 + 0.5, abs=0.01)
    assert two.duration_sec == pytest.approx(1.25 + 0.5, abs=0.01)

    with pytest.raises(studio_audio.AudioUnavailable, match="1, 2, 3, or 4"):
        studio_audio.ensure_audio("sha256:" + "c" * 64, note(1.0), 5)


def test_passage_keeps_the_spec_when_the_synth_cap_rejects_audio() -> None:
    client = _client()
    uploaded = _upload(client, _long_fixture()).json()
    assert uploaded["summary"]["measureCount"] == 40

    body = _passage(client, uploaded["importId"], barStart=1, barEnd=40).json()
    assert body["ok"] is False
    assert body["spec"] is not None
    assert len(body["notes"]) == 40
    assert body["audioUrl"] is None
    assert [error["path"] for error in body["errors"]] == ["audio"]


def test_upload_rejects_too_many_notes(monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_MUSICXML_MAX_NOTES", "3")
    client = _client()
    response = _upload(client)
    assert response.status_code == 413
    assert response.json()["ok"] is False


def test_upload_rejects_entity_declarations() -> None:
    client = _client()
    payload = (
        b'<!DOCTYPE score-partwise [<!ENTITY a "boom">]><score-partwise/>'
    )
    response = _upload(client, payload, filename="entity.musicxml")
    assert response.status_code == 400


def test_router_is_registered_on_the_app() -> None:
    from app.main import app as main_app

    paths = {route.path for route in main_app.routes}
    assert "/v1/studio/import/musicxml" in paths
    assert "/v1/studio/import/musicxml/{import_id}" in paths
    assert "/v1/studio/import/musicxml/{import_id}/passage" in paths
    assert "/v1/studio/import/musicxml/passages/{passage_id}" in paths


def test_passage_spec_and_notes_are_json_serialisable() -> None:
    client = _client()
    import_id = _upload(client).json()["importId"]
    body = _passage(client, import_id, barStart=1, barEnd=1).json()
    # json.dumps is what the store already does, but keep the assertion so a
    # future parser value (e.g. Decimal) cannot leak into the response.
    assert json.loads(json.dumps(body)) == body
