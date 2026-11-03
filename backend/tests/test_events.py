"""The small client telemetry sink and A/B cache pin."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.routers import stocks
from app.routers.stocks import post_sonify_events, pin_params
from app.sonify.audio import recap_store
from app.sonify.events import EventStore, RateLimiter


def _db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "events.sqlite3"
    monkeypatch.setenv("VSTOCK_SONIFY_EVENTS_DB", str(path))
    return path


def test_events_store_and_mirror_jsonl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path, monkeypatch)
    mirror = tmp_path / "events.jsonl"
    monkeypatch.setenv("VSTOCK_SONIFY_EVENT_LOG", str(mirror))
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
    rows = [json.loads(line) for line in mirror.read_text().splitlines()]
    assert [row["name"] for row in rows] == ["play", "ab_toggle", "profile_save"]
    assert rows[0]["eventId"] == "e1"
    assert rows[1]["payload"] == {"side": "B"}
    summary = EventStore(db).summary()
    assert summary["total"] == 3
    assert summary["byName"] == {"ab_toggle": 1, "play": 1, "profile_save": 1}


def test_events_reject_empty_oversize_and_bad_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _db(tmp_path, monkeypatch)
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


def test_events_dedupe_event_id_across_store_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path, monkeypatch)
    payload = {"events": [{"name": "play", "eventId": "same-id", "payload": {}}]}
    assert asyncio.run(post_sonify_events(payload)) == {"accepted": 1}
    assert asyncio.run(post_sonify_events(payload)) == {"accepted": 0}
    # A new process/store still sees the primary key.
    assert EventStore(db).summary()["total"] == 1


def test_events_drop_unknown_and_pii_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path, monkeypatch)
    asyncio.run(
        post_sonify_events(
            {
                "events": [
                    {
                        "name": "play",
                        "eventId": "pii",
                        "payload": {
                            "sessionId": "s_1",
                            "span": "1D",
                            "variant": "symphony",
                            "email": "nobody@example.com",
                            "message": "free text",
                            "blob": {"nested": True},
                        },
                    },
                    {
                        "name": "profile_save",
                        "eventId": "profile",
                        "payload": {
                            "changedKeys": ["harmony", "email", "unknown"],
                            "enabledTiers": ["A", "B", "X"],
                            "source": "save",
                        },
                    },
                ]
            }
        )
    )
    connection = sqlite3.connect(db)
    rows = connection.execute("SELECT payload FROM events ORDER BY event_id").fetchall()
    connection.close()
    play = json.loads(rows[0][0])
    assert play == {"sessionId": "s_1", "span": "1D", "variant": "symphony"}
    profile = json.loads(rows[1][0])
    assert profile["changedKeys"] == ["harmony"]
    assert profile["enabledTiers"] == ["A", "B"]


def test_event_summary_answers_gate_questions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _db(tmp_path, monkeypatch)
    asyncio.run(
        post_sonify_events(
            {
                "events": [
                    {"name": "play", "eventId": "p1", "at": 10, "payload": {"sessionId": "s1"}},
                    {"name": "play", "eventId": "p2", "at": 20, "payload": {"sessionId": "s2"}},
                    {"name": "ab_toggle", "eventId": "a1", "at": 11, "payload": {"sessionId": "s1"}},
                    {
                        "name": "profile_save",
                        "eventId": "f1",
                        "at": 30,
                        "payload": {"changedKeys": ["harmony"], "knobs": 1},
                    },
                    {
                        "name": "profile_save",
                        "eventId": "f2",
                        "at": 40,
                        "payload": {"changedKeys": ["tempo"], "knobs": 1},
                    },
                ]
            }
        )
    )
    summary = EventStore(db).summary()
    assert summary["sessions"] == {"replay": 2, "ab": 1, "abRatio": 0.5}
    assert summary["profiles"] == {"saved": 2, "withBc": 1, "withBcRatio": 0.5}
    assert summary["byDay"]


def test_event_endpoint_rate_limit_uses_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _db(tmp_path, monkeypatch)
    monkeypatch.setenv("VSTOCK_SONIFY_EVENTS_RATE_PER_MIN", "1")
    stocks._EVENT_LIMITER = None
    stocks._EVENT_LIMITER_LIMIT = None
    first = {"events": [{"name": "play", "eventId": "rate-1", "payload": {}}]}
    second = {"events": [{"name": "play", "eventId": "rate-2", "payload": {}}]}
    assert asyncio.run(post_sonify_events(first)) == {"accepted": 1}
    with pytest.raises(HTTPException) as error:
        asyncio.run(post_sonify_events(second))
    assert error.value.status_code == 429


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = RateLimiter(2, window_sec=60)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)
    assert limiter.allow("a", now=61)


def test_pin_params_keeps_a_and_b_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    result = asyncio.run(pin_params({"hashes": ["a123", "b456"], "ttlSec": 30}))
    assert result["pinned"] == 2
    assert recap_store()._pinned("a123")
    assert recap_store()._pinned("_pa123")
    assert recap_store()._pinned("b456")


def test_pinned_hash_survives_prune(tmp_path: Path) -> None:
    import os
    import time
    from app.sonify.audio import RECAP_REVISION, RecapStore

    store = RecapStore(root=tmp_path)
    hashes = ["aaaa00000001", "aaaa00000002", "aaaa00000003", "aaaa00000004", "aaaa00000005"]
    for index, value in enumerate(hashes):
        path = tmp_path / f"VNM_2026-01-01_symphony_{RECAP_REVISION}_30_p{value}.m4a"
        path.write_bytes(b"x")
        stamp = time.time() - (len(hashes) - index) * 10
        os.utime(path, (stamp, stamp))
    oldest = tmp_path / f"VNM_2026-01-01_symphony_{RECAP_REVISION}_30_p{hashes[0]}.m4a"
    store.pin_hashes([hashes[0]], ttl_sec=60)
    store.prune()
    assert oldest.exists()
    assert len(list(tmp_path.glob("*_p*.m4a"))) == 5
