"""The small client telemetry sink."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers.stocks import post_sonify_events


def test_events_append_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("VSTOCK_SONIFY_EVENT_LOG", str(path))
    result = asyncio.run(
        post_sonify_events(
            {
                "events": [
                    {"name": "ab_toggle", "at": 10.0, "payload": {"side": "B"}},
                    {"name": "profile_save", "payload": {"knobs": 2}},
                    {"name": "unknown", "payload": {}},
                ]
            }
        )
    )
    assert result == {"accepted": 2}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["name"] for row in rows] == ["ab_toggle", "profile_save"]
    assert rows[0]["payload"] == {"side": "B"}


def test_events_reject_empty_and_oversize(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VSTOCK_SONIFY_EVENT_LOG", "/tmp/unused-events.jsonl")
    with pytest.raises(HTTPException):
        asyncio.run(post_sonify_events({"events": []}))
    with pytest.raises(HTTPException):
        asyncio.run(post_sonify_events({"events": [{"name": "ab_toggle"}] * 101}))
