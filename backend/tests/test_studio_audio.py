"""Studio audio preview: deterministic WAV synthesis and its cache.

The preview must stay a pure function of the authored spec plus a bounded
fixture: no MuseScore, no export queue, no global registry mutation.
"""

from __future__ import annotations

import hashlib
import json
import wave

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import studio_audio as studio_audio_router
from app.sonify import sentence_specs
from app.sonify.guitar_torroba import CASTILLO_34_WALK
from app.studio import audio as studio_audio
from app.studio.export import SPECS_DIR


@pytest.fixture(autouse=True)
def _audio_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VSTOCK_STUDIO_AUDIO_DIR", str(tmp_path / "audio"))


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(studio_audio_router.router)
    return TestClient(app)


def _castillo_payload() -> dict:
    return json.loads(
        (SPECS_DIR / "castillo-3-4.json").read_text(encoding="utf-8")
    )["specs"][0]


def test_wav_header_and_duration() -> None:
    result = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 9, "bars": 9}
    )
    assert result.ok, result.errors
    asset = result.asset
    assert asset is not None

    with wave.open(str(asset.path)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == studio_audio.SAMPLE_RATE
        assert wav.getnframes() > 0
        measured = wav.getnframes() / wav.getframerate()

    assert asset.path.read_bytes()[:4] == b"RIFF"
    assert asset.path.read_bytes()[8:12] == b"WAVE"
    assert measured == pytest.approx(asset.duration_sec, abs=1e-6)
    assert 0.0 < asset.duration_sec <= studio_audio.MAX_AUDIO_SEC


def test_the_same_spec_produces_identical_bytes() -> None:
    first = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 9, "bars": 9}
    )
    assert first.ok and first.asset is not None
    first_bytes = first.asset.path.read_bytes()

    for path in studio_audio.audio_root().iterdir():
        path.unlink()

    second = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 9, "bars": 9}
    )
    assert second.ok and second.asset is not None
    assert second.asset.key == first.asset.key
    assert second.asset.render_hash == first.asset.render_hash
    assert second.asset.path.read_bytes() == first_bytes
    assert hashlib.sha256(first_bytes).hexdigest() == hashlib.sha256(
        second.asset.path.read_bytes()
    ).hexdigest()


def test_a_cache_hit_does_not_synthesize_again(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []
    original = studio_audio._synthesize_pcm

    def counted(notes, beats):
        calls.append((len(notes), beats))
        return original(notes, beats)

    monkeypatch.setattr(studio_audio, "_synthesize_pcm", counted)
    first = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 9, "bars": 9}
    )
    second = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 9, "bars": 9}
    )

    assert first.ok and second.ok
    assert first.asset is not None and second.asset is not None
    assert len(calls) == 1
    assert second.asset.audio_url == first.asset.audio_url
    assert len(list(studio_audio.audio_root().glob("*.wav"))) == 1


def test_candidate_audio_uses_the_dispatched_preview() -> None:
    from app.studio.candidates import villa_candidate_spec

    result = studio_audio.preview_audio(
        villa_candidate_spec(), {"length": 6, "n": 0}
    )
    assert result.ok, result.errors
    assert result.asset is not None
    assert result.render_hash is not None


def test_audio_rejects_when_synthesis_slots_are_full(monkeypatch) -> None:
    import threading

    monkeypatch.setattr(studio_audio, "_SLOTS", threading.BoundedSemaphore(1))
    studio_audio._SLOTS.acquire()
    try:
        result = studio_audio.preview_audio(
            CASTILLO_34_WALK, {"length": 9, "bars": 9}
        )
        assert not result.ok
        assert result.errors[0][0] == "audio"
        assert "busy" in result.errors[0][1]
    finally:
        studio_audio._SLOTS.release()


def test_an_invalid_spec_returns_path_errors_and_writes_nothing() -> None:
    from dataclasses import replace

    bad = replace(
        CASTILLO_34_WALK,
        slots=(replace(CASTILLO_34_WALK.slots[0], figure=999),),
    )
    result = studio_audio.preview_audio(bad)
    assert result.ok is False
    assert result.asset is None
    assert result.errors == (("slots[0].figure", "figure 999 is not in _FIGURES"),)
    assert list(studio_audio.audio_root().glob("*.wav")) == []


def test_preview_does_not_mutate_the_global_registry() -> None:
    before = dict(sentence_specs.SENTENCE_SPECS)
    before_object = sentence_specs.SENTENCE_SPECS
    result = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 9, "bars": 9}
    )
    assert result.ok
    assert sentence_specs.SENTENCE_SPECS is before_object
    assert sentence_specs.SENTENCE_SPECS == before


def test_audio_is_capped_to_the_preview_bar_limit() -> None:
    result = studio_audio.preview_audio(
        CASTILLO_34_WALK, {"length": 16, "bars": 99}
    )
    assert result.ok, result.errors
    assert result.asset is not None
    # 16 bars of 3/4 at the fixed preview tempo, plus the release tail.
    assert result.asset.duration_sec == pytest.approx(16 * 3 * 0.625 + 0.5, abs=0.02)
    assert result.asset.duration_sec <= studio_audio.MAX_AUDIO_SEC


def test_the_api_synthesizes_serves_and_reuses_by_render_hash() -> None:
    client = _client()
    payload = _castillo_payload()

    created = client.post(
        "/v1/studio/sentence/audio",
        json={"spec": payload, "fixture": {"length": 9, "bars": 9}},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["ok"] is True
    assert body["errors"] == []
    assert body["renderHash"].startswith("sha256:")
    assert body["durationSec"] > 0

    served = client.get(body["audioUrl"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "audio/wav"
    assert served.content[:4] == b"RIFF"

    reused = client.post(
        "/v1/studio/sentence/audio", json={"renderHash": body["renderHash"]}
    )
    assert reused.status_code == 200
    assert reused.json()["audioUrl"] == body["audioUrl"]
    assert reused.json()["durationSec"] == body["durationSec"]

    assert client.get("/v1/studio/sentence/audio/not-a-key.wav").status_code == 404
    assert (
        client.get(f"/v1/studio/sentence/audio/{'a' * 64}.wav").status_code == 404
    )


def test_the_api_reports_an_invalid_fixture() -> None:
    client = _client()
    response = client.post(
        "/v1/studio/sentence/audio",
        json={"spec": _castillo_payload(), "fixture": {"meter": "7/8"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["audioUrl"] is None
    assert body["errors"][0]["path"] == "fixture"


def test_the_api_requires_a_spec_or_a_cached_hash() -> None:
    client = _client()

    missing = client.post("/v1/studio/sentence/audio", json={})
    assert missing.status_code == 200
    assert missing.json()["ok"] is False
    assert missing.json()["errors"][0]["path"] == "spec"

    malformed = client.post(
        "/v1/studio/sentence/audio", json={"renderHash": "sha256:nope"}
    )
    assert malformed.json()["ok"] is False
    assert malformed.json()["errors"][0]["path"] == "renderHash"

    unknown = client.post(
        "/v1/studio/sentence/audio", json={"renderHash": "sha256:" + "b" * 64}
    )
    assert unknown.json()["ok"] is False
    assert unknown.json()["errors"][0]["path"] == "renderHash"
    assert "no cached preview audio" in unknown.json()["errors"][0]["message"]


def test_the_api_preview_and_audio_share_a_render_hash() -> None:
    from app.routers import studio as studio_router

    app = FastAPI()
    app.include_router(studio_router.router)
    app.include_router(studio_audio_router.router)
    client = TestClient(app)
    payload = _castillo_payload()
    fixture = {"length": 9, "bars": 9}

    previewed = client.post(
        "/v1/studio/sentence/preview", json={"spec": payload, "fixture": fixture}
    )
    expected = previewed.json()["renderHash"]

    body = client.post(
        "/v1/studio/sentence/audio", json={"spec": payload, "fixture": fixture}
    ).json()
    assert body["renderHash"] == expected
