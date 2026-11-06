"""Production audio store + async job tests for Phase C2 Studio Render Piece.

MuseScore is replaced by a tiny WAV writer. The tests cover:

* render -> queued job -> ready -> fetchable WAV;
* cache hit without a second export;
* explicit ``POST .../audio`` dedupe;
* missing hash/job 404s;
* export failure and timeout error codes, with no synth fallback;
* the audio hash changing with params and ``AUDIO_REVISION``;
* the route/store not reusing the 45-second ``/sentence/audio`` preview.
"""

from __future__ import annotations

import threading
import time
import wave
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_render
from app.sonify import audio as sonify_audio
from app.studio import render_audio, render_jobs
from app.studio.render_audio import StudioAudioError

PATTERN = "studio_render_audio"
HASH = "a" * 64


@pytest.fixture(autouse=True)
def _studio_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("VSTOCK_STUDIO_RENDER_DIR", str(tmp_path / "renders"))
    monkeypatch.setenv(
        "VSTOCK_STUDIO_RENDER_AUDIO_DIR", str(tmp_path / "renders" / "audio")
    )
    monkeypatch.setenv("VSTOCK_MUSESCORE_VERSION", "test-musescore")
    monkeypatch.setenv("VSTOCK_STUDIO_SOUNDFONT_VERSION", "test-soundfont")
    render_jobs.reset_registry()
    registry = render_jobs.get_registry()
    yield tmp_path
    registry.shutdown(wait=True)
    render_jobs.reset_registry()


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_render.router)
    return TestClient(app)


def _write_wav(path: Path, *, frames: int = 800) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * frames)


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


def _texture(cell_id: str, bars: int, meter: str = "4/4") -> dict[str, Any]:
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
                    "pitch": {"kind": "chord_root"},
                    "confidence": 0.9,
                    "review": "pending",
                }
                for bar in range(bars)
            ]
        },
    }


def _figure(
    figure_id: str, cell_id: str, bars: int, tags: list[str]
) -> dict[str, Any]:
    return {
        "id": figure_id,
        "cellId": cell_id,
        "bars": bars,
        "tags": tags,
        "spec": _texture(cell_id, bars),
    }


def _body(*, start: float = 100.0, title: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "pattern": PATTERN,
        "meter": "4/4",
        "figures": [
            _figure("fig_key", "cell_key", 4, ["key"]),
            _figure("fig_in2", "cell_in2", 2, ["intro.short"]),
            _figure("fig_in4", "cell_in4", 4, ["intro.long"]),
            _figure("fig_out2", "cell_out2", 2, ["outro.short"]),
            _figure("fig_out4", "cell_out4", 4, ["outro.long"]),
            _figure("fig_b", "cell_b", 4, ["contrast"]),
            _figure("fig_close", "cell_close", 2, ["close"]),
        ],
        "plan": "auto_aaba",
        "series": {
            "kind": "bars",
            "bars": [
                {"close": start + (index % 7) * 3.0, "volume": 250.0}
                for index in range(40)
            ],
        },
        "form": {"span": "1W"},
        "options": {"includeDoors": True},
    }
    if title is not None:
        body["title"] = title
    return body


def _poll(
    client: TestClient,
    render_hash: str,
    job_id: str,
    *,
    timeout: float = 10.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    url = f"/v1/studio/figure/render/{render_hash}/audio/{job_id}"
    while time.monotonic() < deadline:
        response = client.get(url)
        assert response.status_code == 200, response.text
        body = response.json()
        if body["status"] in ("ready", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError("audio job did not finish")


def _submit_render(client: TestClient, body: dict[str, Any] | None = None) -> dict:
    response = client.post(
        "/v1/studio/figure/render", json=body or _body()
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True, payload
    return payload


def test_render_queues_then_serves_wav_and_cache_hit_skips_export(
    client: TestClient, monkeypatch
) -> None:
    calls: list[tuple[str, Path]] = []

    def export(xml_path: Path, wav_path: Path) -> None:
        calls.append((xml_path.read_text(encoding="utf-8"), wav_path))
        _write_wav(wav_path)

    monkeypatch.setattr(render_audio, "musescore_export", export)

    first = _submit_render(client)
    audio = first["audio"]
    assert audio["status"] == "queued", audio
    assert audio["jobId"].startswith("audio_")

    ready = _poll(client, first["renderHash"], audio["jobId"])
    assert ready["status"] == "ready", ready
    assert ready["audioUrl"].endswith(".wav")
    assert ready["audioHash"].startswith("sha256:")
    assert ready["durationSec"] > 0
    assert len(calls) == 1
    xml_text, exported_path = calls[0]
    assert "<note" in xml_text
    assert exported_path.suffix == ".wav"

    wav = client.get(ready["audioUrl"])
    assert wav.status_code == 200
    assert wav.headers["content-type"].startswith("audio/wav")
    payload = wav.content
    assert payload[:4] == b"RIFF" and payload[8:12] == b"WAVE"
    assert len(payload) > 44

    second = _submit_render(client)
    assert second["audio"]["status"] == "ready", second["audio"]
    assert second["audio"]["audioUrl"] == ready["audioUrl"]
    assert len(calls) == 1, "a cache hit must not launch MuseScore again"


def test_post_audio_deduplicates_the_active_job(
    client: TestClient, monkeypatch
) -> None:
    release = threading.Event()

    def export(_xml_path: Path, wav_path: Path) -> None:
        assert release.wait(timeout=10)
        _write_wav(wav_path)

    monkeypatch.setattr(render_audio, "musescore_export", export)

    rendered = _submit_render(client)
    digest = rendered["renderHash"].split(":", 1)[1]
    assert rendered["audio"]["status"] == "queued"

    first = client.post(f"/v1/studio/figure/render/{digest}/audio")
    second = client.post(f"/v1/studio/figure/render/{digest}/audio")
    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert first.json()["jobId"] == rendered["audio"]["jobId"]
    assert second.json()["jobId"] == first.json()["jobId"]

    release.set()
    ready = _poll(client, rendered["renderHash"], first.json()["jobId"])
    assert ready["status"] == "ready"

    third = client.post(f"/v1/studio/figure/render/{digest}/audio")
    assert third.status_code == 202
    assert third.json()["jobId"] == first.json()["jobId"]


def test_missing_hash_and_job_are_404(client: TestClient) -> None:
    missing = client.post(f"/v1/studio/figure/render/{HASH}/audio")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "render_not_found"

    bad = client.post("/v1/studio/figure/render/not-a-hash/audio")
    assert bad.status_code == 404

    job = client.get(f"/v1/studio/figure/render/{HASH}/audio/audio_missing")
    assert job.status_code == 404
    assert job.json()["detail"]["code"] in (
        "audio_job_not_found",
        "render_not_found",
    )

    wav = client.get(f"/v1/studio/figure/render/{HASH}.wav")
    assert wav.status_code == 404
    assert wav.json()["detail"]["code"] == "audio_not_found"


def test_export_failure_fails_without_synth_fallback(
    client: TestClient, monkeypatch
) -> None:
    def export(_xml_path: Path, _wav_path: Path) -> None:
        raise sonify_audio.RecapUnavailable("MuseScore export exploded")

    monkeypatch.setattr(render_audio, "musescore_export", export)

    rendered = _submit_render(client)
    failed = _poll(client, rendered["renderHash"], rendered["audio"]["jobId"])
    assert failed["status"] == "failed", failed
    assert failed["audioUrl"] is None
    assert failed["errors"][0]["code"] == "audio_failed"

    root = Path(render_audio.audio_root())
    assert list(root.glob("*.wav")) == []


def test_export_timeout_sets_piece_timeout_and_reports_audio_timeout(
    client: TestClient, monkeypatch
) -> None:
    seen: list[float] = []

    def export(_xml_path: Path, _wav_path: Path) -> None:
        seen.append(float(getattr(sonify_audio._export_timeout, "seconds", 0.0)))
        raise sonify_audio.RecapUnavailable("MuseScore export timed out")

    monkeypatch.setattr(render_audio, "musescore_export", export)

    rendered = _submit_render(client)
    failed = _poll(client, rendered["renderHash"], rendered["audio"]["jobId"])
    assert failed["status"] == "failed", failed
    assert failed["errors"][0]["code"] == "audio_timeout"
    assert seen and seen[0] >= 180


def test_export_can_be_patched_on_sonify_module(
    client: TestClient, monkeypatch
) -> None:
    """The store resolves the live ``app.sonify.audio`` symbol, not a copy."""
    calls: list[Path] = []

    def export(_xml_path: Path, wav_path: Path) -> None:
        calls.append(wav_path)
        _write_wav(wav_path)

    monkeypatch.setattr(sonify_audio, "musescore_export", export)

    rendered = _submit_render(client)
    ready = _poll(client, rendered["renderHash"], rendered["audio"]["jobId"])
    assert ready["status"] == "ready"
    assert calls


def test_zero_length_wav_is_a_failure_not_a_truncated_preview(
    client: TestClient, monkeypatch
) -> None:
    def export(_xml_path: Path, wav_path: Path) -> None:
        _write_wav(wav_path, frames=0)

    monkeypatch.setattr(render_audio, "musescore_export", export)

    rendered = _submit_render(client)
    failed = _poll(client, rendered["renderHash"], rendered["audio"]["jobId"])
    assert failed["status"] == "failed"
    assert failed["errors"][0]["code"] == "audio_failed"
    assert list(Path(render_audio.audio_root()).glob("*.wav")) == []


def test_audio_hash_changes_with_params_and_revision(monkeypatch) -> None:
    base = {"tempo": 1.0}
    other = {"tempo": 1.1}

    first = render_audio.audio_hash_for(HASH, base)
    second = render_audio.audio_hash_for(HASH, other)
    assert first != second

    monkeypatch.setattr(render_audio, "AUDIO_REVISION", 999)
    revised = render_audio.audio_hash_for(HASH, base)
    assert revised != first


def test_audio_store_is_not_the_45s_sentence_preview() -> None:
    source = Path(render_audio.__file__).read_text(encoding="utf-8")
    router = Path(studio_render.__file__).read_text(encoding="utf-8")
    assert "/sentence/audio" not in source
    assert "/sentence/audio" not in router
    assert "MAX_AUDIO_SEC" not in source
    assert "from app.sonify.audio import recap_store" not in source


def test_coded_errors_are_stable() -> None:
    assert render_audio.StudioAudioUnavailable("x").code == "audio_unavailable"
    assert render_audio.StudioAudioTimeout("x").code == "audio_timeout"
    assert render_audio.StudioAudioFailed("x").code == "audio_failed"
    assert issubclass(StudioAudioError, RuntimeError)
