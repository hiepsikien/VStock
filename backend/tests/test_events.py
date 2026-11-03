"""The small client telemetry sink and A/B cache pin."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers.stocks import pin_params, post_sonify_events
from app.sonify.audio import recap_store


def test_events_append_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("VSTOCK_SONIFY_EVENT_LOG", str(path))
    result = asyncio.run(
        post_sonify_events(
            {
                "events": [
                    {"name": "play", "eventId": "e1", "at": 10.0, "payload": {"span": "1D"}},
                    {"name": "ab_toggle", "eventId": "e2", "payload": {"side": "B"}},
                    {"name": "profile_save", "eventId": "e3", "payload": {"knobs": 2}},
                    {"name": "unknown", "payload": {}},
                ]
            }
        )
    )
    assert result == {"accepted": 3}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["name"] for row in rows] == ["play", "ab_toggle", "profile_save"]
    assert rows[0]["eventId"] == "e1"
    assert rows[1]["payload"] == {"side": "B"}


def test_events_reject_empty_oversize_and_bad_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VSTOCK_SONIFY_EVENT_LOG", "/tmp/unused-events.jsonl")
    with pytest.raises(HTTPException):
        asyncio.run(post_sonify_events({"events": []}))
    with pytest.raises(HTTPException):
        asyncio.run(post_sonify_events({"events": [{"name": "play"}] * 101}))
    with pytest.raises(HTTPException):
        asyncio.run(
            post_sonify_events(
                {"events": [{"name": "play", "payload": {"blob": "x" * 70_000}}]}
            )
        )


def test_pin_params_keeps_a_and_b_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    result = asyncio.run(pin_params({"hashes": ["a123", "b456"], "ttlSec": 30}))
    assert result["pinned"] == 2
    assert recap_store()._pinned("a123")
    assert recap_store()._pinned("b456")
