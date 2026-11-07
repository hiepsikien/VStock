"""Contract and service tests for Phase C1 Studio Render Piece.

The API is preview-only: it validates a tagged figure pool, renders MusicXML
through the ``studio_piece`` seam, stores it by content hash, and never writes
``TEXTURE_CELLS``, ``SENTENCE_SPECS`` or ``STUDIO_DOORS``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_render
from app.sonify.model import Bar
from app.sonify.pattern_doors import STUDIO_DOOR_METERS, STUDIO_DOORS
from app.sonify.pattern_figures import PatternFigure
from app.sonify.sentence_specs import SENTENCE_SPECS
from app.sonify.texture_figure import TEXTURE_CELLS
from app.studio import render_audio as render_audio_module
from app.studio import render_jobs, render_piece as render_piece_module
from app.studio.render_piece import RenderPieceRequest, render_piece
from app.studio.texture_spec import parse_texture_spec

PATTERN = "studio_render_api"
FORM_BARS = 32


@pytest.fixture(autouse=True)
def _render_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("VSTOCK_STUDIO_RENDER_DIR", str(tmp_path / "renders"))
    monkeypatch.setenv(
        "VSTOCK_STUDIO_RENDER_AUDIO_DIR", str(tmp_path / "renders" / "audio")
    )
    monkeypatch.setenv("VSTOCK_MUSESCORE_VERSION", "test")
    monkeypatch.setenv("VSTOCK_STUDIO_SOUNDFONT_VERSION", "test")

    def _no_export(*_args, **_kwargs):
        raise render_audio_module.StudioAudioUnavailable("test: no MuseScore")

    monkeypatch.setattr(render_audio_module, "musescore_export", _no_export)
    render_jobs.reset_registry()
    registry = render_jobs.get_registry()
    yield
    registry.shutdown(wait=True)
    render_jobs.reset_registry()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_render.router)
    return TestClient(app)


def _meter_fields(meter: str) -> dict[str, Any]:
    if meter == "2/4":
        return {
            "id": "2/4",
            "beats": 2,
            "beat_type": 4,
            "eighths_per_bar": 4,
            "strong_eighths": [0],
            "subbar_breaks": [2],
        }
    return {
        "id": "4/4",
        "beats": 4,
        "beat_type": 4,
        "eighths_per_bar": 8,
        "strong_eighths": [0, 4],
        "subbar_breaks": [4],
    }


def _texture(
    cell_id: str,
    bars: int,
    *,
    meter: str = "4/4",
    pitch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": cell_id,
        "composer": "villa",
        "kind": "pattern",
        "level": "topic",
        "runtime": "code",
        "status": "draft",
        "meter_variants": [
            {
                "meter": _meter_fields(meter),
                "materializer": f"grid_{meter.replace('/', '_')}",
                "transform": "none",
                "unsupported": False,
                "reason": None,
                "sentences": [],
            }
        ],
        "authored": {
            "events": [
                {
                    "bar": bar,
                    "beat": 0.0,
                    "duration_beats": 1.0,
                    "voice": 1,
                    "pitch": pitch or {"kind": "chord_root"},
                    "confidence": 0.9,
                    "review": "pending",
                }
                for bar in range(bars)
            ]
        },
    }


def _figure(
    figure_id: str,
    cell_id: str,
    bars: int,
    tags: list[str],
    *,
    meter: str = "4/4",
    pitch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": figure_id,
        "cellId": cell_id,
        "bars": bars,
        "tags": tags,
        "spec": _texture(cell_id, bars, meter=meter, pitch=pitch),
    }


def _pool(*, meter: str = "4/4", key_pitch: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [
        _figure("fig_key", "cell_key", 4, ["key"], meter=meter, pitch=key_pitch),
        _figure("fig_in2", "cell_in2", 2, ["intro.short"], meter=meter),
        _figure("fig_in4", "cell_in4", 4, ["intro.long"], meter=meter),
        _figure("fig_out2", "cell_out2", 2, ["outro.short"], meter=meter),
        _figure("fig_out4", "cell_out4", 4, ["outro.long"], meter=meter),
        _figure("fig_b", "cell_b", 4, ["contrast"], meter=meter),
        _figure("fig_close", "cell_close", 2, ["close"], meter=meter),
    ]


def _bars(count: int = 40, *, start: float = 100.0) -> list[dict[str, float]]:
    return [
        {"close": start + (index % 7) * 3.0, "volume": 250.0}
        for index in range(count)
    ]


def _body(
    *,
    meter: str = "4/4",
    plan: Any = "auto_aaba",
    series_bars: list[dict[str, float]] | None = None,
    pattern: str = PATTERN,
    title: str | None = None,
    figures: list[dict[str, Any]] | None = None,
    key_pitch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "pattern": pattern,
        "meter": meter,
        "figures": _pool(meter=meter, key_pitch=key_pitch)
        if figures is None
        else figures,
        "plan": plan,
        "series": {"kind": "bars", "bars": series_bars or _bars()},
        "form": {"span": "1W"},
        "options": {"includeDoors": True},
    }
    if title is not None:
        body["title"] = title
    return body


def _errors(response) -> list[dict[str, str]]:
    return response.json()["errors"]


@pytest.mark.parametrize("meter", ["2/4", "4/4"])
def test_render_returns_hash_and_fetchable_musicxml(
    client: TestClient, meter: str
) -> None:
    response = client.post("/v1/studio/figure/render", json=_body(meter=meter))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True, body
    assert body["renderHash"].startswith("sha256:")
    assert body["musicxmlUrl"].endswith(".musicxml")
    assert body["meter"] == meter
    assert body["bars"] == FORM_BARS
    assert body["notes"] > 0
    assert body["plan"] == "auto_aaba"
    assert body["audio"]["status"] in ("queued", "ready"), body["audio"]
    if body["audio"]["status"] == "queued":
        assert body["audio"]["jobId"]
    else:
        assert body["audio"]["audioUrl"].endswith(".wav")

    xml = client.get(body["musicxmlUrl"])
    assert xml.status_code == 200
    assert "<note" in xml.text
    assert f"{PATTERN} Studio Piece" in xml.text


def test_plan_object_id_is_accepted(client: TestClient) -> None:
    body = _body(plan={"id": "trio"})
    response = client.post("/v1/studio/figure/render", json=body)

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["plan"] == "trio"


def test_missing_required_tag_is_a_structural_error(client: TestClient) -> None:
    figures = [figure for figure in _pool() if figure["id"] != "fig_key"]
    response = client.post(
        "/v1/studio/figure/render", json=_body(figures=figures)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["renderHash"] is None
    assert any("missing figure tags" in item["message"] for item in body["errors"])


def test_unknown_plan_is_an_error(client: TestClient) -> None:
    response = client.post("/v1/studio/figure/render", json=_body(plan="abab"))

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert any(item["path"] == "plan" for item in body["errors"])


def test_short_series_is_an_error_without_truncation(client: TestClient) -> None:
    response = client.post(
        "/v1/studio/figure/render",
        json=_body(series_bars=_bars(8)),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert any("series has 8 bars" in item["message"] for item in body["errors"])


def test_literal_midi_is_allowed_with_a_warning(client: TestClient) -> None:
    response = client.post(
        "/v1/studio/figure/render",
        json=_body(key_pitch={"kind": "literal_midi", "value": 60}),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert any("literal_midi is preview-only" in item for item in body["warnings"])


def test_plan_sentence_by_role_is_rejected_as_unimplemented(client: TestClient) -> None:
    response = client.post(
        "/v1/studio/figure/render",
        json=_body(plan={"id": "trio", "sentenceByRole": {"A": "fig_key"}}),
    )
    body = response.json()
    assert body["ok"] is False
    assert any("sentenceByRole" in item["message"] for item in body["errors"])


def test_same_request_hits_the_cache(client: TestClient, monkeypatch) -> None:
    first = client.post("/v1/studio/figure/render", json=_body())
    assert first.json()["ok"] is True

    def _should_not_render(*_args, **_kwargs):
        raise AssertionError("cache miss: render() was called twice")

    monkeypatch.setattr(render_piece_module, "render", _should_not_render)
    second = client.post("/v1/studio/figure/render", json=_body())

    assert second.status_code == 200
    assert second.json()["ok"] is True
    assert second.json()["renderHash"] == first.json()["renderHash"]
    assert second.json()["notes"] == first.json()["notes"]


def test_changed_series_changes_the_hash(client: TestClient) -> None:
    first = client.post("/v1/studio/figure/render", json=_body())
    second = client.post(
        "/v1/studio/figure/render",
        json=_body(series_bars=_bars(start=101.0)),
    )

    assert first.json()["ok"] is True
    assert second.json()["ok"] is True
    assert first.json()["renderHash"] != second.json()["renderHash"]


def test_unknown_pattern_title_does_not_keyerror(client: TestClient) -> None:
    response = client.post(
        "/v1/studio/figure/render",
        json=_body(pattern="studio_unknown_pattern_xyz"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True, body
    xml = client.get(body["musicxmlUrl"])
    assert "<work-title>studio_unknown_pattern_xyz Studio Piece</work-title>" in xml.text


def test_render_does_not_mutate_the_registries(client: TestClient) -> None:
    before_cells = deepcopy(TEXTURE_CELLS)
    before_specs = dict(SENTENCE_SPECS)
    before_doors = dict(STUDIO_DOORS)
    before_meters = dict(STUDIO_DOOR_METERS)

    response = client.post("/v1/studio/figure/render", json=_body())

    assert response.json()["ok"] is True
    assert TEXTURE_CELLS == before_cells
    assert SENTENCE_SPECS == before_specs
    assert STUDIO_DOORS == before_doors
    assert STUDIO_DOOR_METERS == before_meters


def _service_request(meter: str = "4/4") -> RenderPieceRequest:
    figures: list[tuple[PatternFigure, Any]] = []
    for raw in _pool(meter=meter):
        figures.append(
            (
                PatternFigure(
                    id=raw["id"],
                    cell_id=raw["cellId"],
                    bars=raw["bars"],
                    tags=tuple(raw["tags"]),
                ),
                parse_texture_spec(raw["spec"]),
            )
        )
    return RenderPieceRequest(
        pattern=PATTERN,
        meter=meter,
        figures=tuple(figures),
        plan="auto_aaba",
        bars=tuple(Bar(close=value["close"], volume=value["volume"]) for value in _bars()),
        span="1W",
        title="Service Test Piece",
    )


def test_service_result_and_title() -> None:
    result = render_piece(_service_request("2/4"))

    assert result.meter == "2/4"
    assert result.bars == FORM_BARS
    assert result.title == "Service Test Piece"
    assert result.render_hash.startswith("sha256:")
    assert "<note" in result.musicxml
    assert result.musicxml_url.endswith(".musicxml")
    assert result.audio_status == "unavailable"


def test_audio_can_be_disabled(client: TestClient) -> None:
    body = _body()
    body["options"] = {"includeDoors": True, "audio": False}
    response = client.post("/v1/studio/figure/render", json=body)
    payload = response.json()
    assert payload["ok"] is True
    assert payload["audio"]["status"] == "unavailable"
    assert any("audio disabled" in item for item in payload["warnings"])


def test_symbol_series_kind_is_rejected(client: TestClient) -> None:
    body = _body()
    body["series"] = {"kind": "symbol", "symbol": "VIC", "bars": _bars()}
    response = client.post("/v1/studio/figure/render", json=body)
    payload = response.json()
    assert payload["ok"] is False
    assert any("series.kind" in item["path"] for item in payload["errors"])


def test_body_only_render_does_not_require_door_tags(client: TestClient) -> None:
    body = _body()
    body["figures"] = [
        figure
        for figure in body["figures"]
        if not any(tag.startswith(("intro.", "outro.")) for tag in figure["tags"])
    ]
    body["options"] = {"includeDoors": False, "audio": False}
    response = client.post("/v1/studio/figure/render", json=body)
    payload = response.json()
    assert payload["ok"] is True
    assert payload["audio"]["status"] == "unavailable"
