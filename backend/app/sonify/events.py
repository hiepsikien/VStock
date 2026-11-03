"""Small, boring telemetry store for the listening room.

The gate in the params roadmap only needs counts by day, event name, session
and saved profile. Keep the rows local and disposable: no account ids, no free
text. SQLite is the default because it gives us a persistent `eventId` index
(dedupe across retries) and a file a single instance can share through a
volume. A JSONL mirror stays available for existing log collectors.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
import time
import uuid
from collections import deque
from contextlib import closing
from pathlib import Path
from typing import Any, Mapping

from app.sonify.params import FIELD_BY_KEY

EVENT_NAMES = frozenset(
    {"ab_toggle", "profile_save", "knob_change", "prefetch_fail", "play"}
)
SPANS = frozenset({"1D", "1W", "1M", "3M", "1Y"})
TIERS = frozenset({"A", "B", "C"})
BC_KEYS = frozenset(
    key for key, field in FIELD_BY_KEY.items() if field.tier in ("B", "C")
)

_EVENT_STRING_FIELDS = {
    "play": {"sessionId": 64, "span": 8, "variant": 16, "ensemble": 16},
    "ab_toggle": {"sessionId": 64, "side": 1, "span": 8},
    "knob_change": {"key": 32},
    "prefetch_fail": {"span": 8, "source": 32},
    "profile_save": {"source": 32},
}
_EVENT_NUMBER_FIELDS = {
    "prefetch_fail": {"index", "attempt"},
    "profile_save": {"knobs", "schema"},
}


def _default_db_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "sonify-events.sqlite3"


def _string(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:limit]


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return value


def _string_list(value: Any, *, limit: int, allowed: frozenset[str] | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value[:limit]:
        text = _string(item, 32)
        if text is None:
            continue
        if allowed is not None and text not in allowed:
            continue
        out.append(text)
    return out


def sanitize_payload(name: str, payload: Any) -> dict[str, Any]:
    """Drop every field the gate does not need. This is the PII boundary."""
    if not isinstance(payload, Mapping):
        return {}
    out: dict[str, Any] = {}
    strings = _EVENT_STRING_FIELDS.get(name, {})
    numbers = _EVENT_NUMBER_FIELDS.get(name, set())
    for key, limit in strings.items():
        text = _string(payload.get(key), limit)
        if text is None:
            continue
        if key == "span" and text not in SPANS:
            continue
        if key == "side" and text not in ("A", "B"):
            continue
        if key == "key" and text not in FIELD_BY_KEY:
            continue
        out[key] = text
    for key in numbers:
        number = _number(payload.get(key))
        if number is not None:
            out[key] = number
    if name == "profile_save":
        changed = _string_list(
            payload.get("changedKeys"), limit=64, allowed=frozenset(FIELD_BY_KEY)
        )
        if changed:
            out["changedKeys"] = changed
        tiers = _string_list(payload.get("enabledTiers"), limit=4, allowed=TIERS)
        if tiers:
            out["enabledTiers"] = tiers
    return out


def sanitize_event(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    name = item.get("name")
    if name not in EVENT_NAMES:
        return None
    event_id = _string(item.get("eventId"), 96) or f"anon_{uuid.uuid4().hex}"
    at = _number(item.get("at"))
    if at is None:
        at = time.time()
    return {
        "name": name,
        "eventId": event_id,
        "at": float(at),
        "payload": sanitize_payload(name, item.get("payload")),
    }


class RateLimiter:
    """A tiny in-process token window. A proxy still owns the global limit."""

    def __init__(self, limit: int, window_sec: float = 60.0) -> None:
        self.limit = max(0, int(limit))
        self.window_sec = max(1.0, float(window_sec))
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.limit <= 0:
            return True
        stamp = time.monotonic() if now is None else float(now)
        cutoff = stamp - self.window_sec
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(stamp)
            if len(self._hits) > 10_000:
                for name in [name for name, hits in self._hits.items() if not hits]:
                    self._hits.pop(name, None)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class EventStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = os.environ.get("VSTOCK_SONIFY_EVENTS_DB")
        self.path = Path(path or configured or _default_db_path())

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10.0)
        connection.isolation_level = None
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                at REAL NOT NULL,
                session_id TEXT,
                payload TEXT NOT NULL,
                received_at REAL NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS events_at ON events(at)")
        connection.execute("CREATE INDEX IF NOT EXISTS events_name_at ON events(name, at)")
        connection.execute("CREATE INDEX IF NOT EXISTS events_session ON events(session_id)")
        return connection

    def _mirror_jsonl(self, rows: list[dict[str, Any]]) -> None:
        configured = os.environ.get("VSTOCK_SONIFY_EVENT_LOG")
        if not configured or not rows:
            return
        path = Path(configured)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(
                        json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
                    )
        except OSError:
            # SQLite already has the row; an optional log collector must not
            # turn a successful ingest into a retry storm.
            pass

    def append(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        inserted_rows: list[dict[str, Any]] = []
        with closing(self._connect()) as connection:
            for row in rows:
                payload = row.get("payload") or {}
                session_id = payload.get("sessionId")
                if not isinstance(session_id, str):
                    session_id = None
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO events
                        (event_id, name, at, session_id, payload, received_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["eventId"],
                        row["name"],
                        float(row["at"]),
                        session_id,
                        json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                        time.time(),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted_rows.append(row)
            connection.commit()
        self._mirror_jsonl(inserted_rows)
        return len(inserted_rows)

    def summary(
        self,
        *,
        since: float | None = None,
        until: float | None = None,
    ) -> dict[str, Any]:
        where: list[str] = []
        args: list[float] = []
        if since is not None:
            where.append("at >= ?")
            args.append(float(since))
        if until is not None:
            where.append("at < ?")
            args.append(float(until))
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with closing(self._connect()) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM events {clause}", args
            ).fetchone()[0]
            by_name = dict(
                connection.execute(
                    f"SELECT name, COUNT(*) FROM events {clause} GROUP BY name",
                    args,
                ).fetchall()
            )
            by_day = dict(
                connection.execute(
                    f"""
                    SELECT date(at, 'unixepoch') AS day, COUNT(*)
                    FROM events {clause}
                    GROUP BY day ORDER BY day
                    """,
                    args,
                ).fetchall()
            )
            play_sessions = connection.execute(
                f"""
                SELECT COUNT(DISTINCT session_id) FROM events
                {clause} {'AND' if clause else 'WHERE'}
                name = 'play' AND session_id IS NOT NULL
                """,
                args,
            ).fetchone()[0]
            ab_sessions = connection.execute(
                f"""
                SELECT COUNT(DISTINCT session_id) FROM events
                {clause} {'AND' if clause else 'WHERE'}
                name = 'ab_toggle' AND session_id IS NOT NULL
                """,
                args,
            ).fetchone()[0]
            profile_rows = connection.execute(
                f"SELECT payload FROM events {clause} {'AND' if clause else 'WHERE'} name = 'profile_save'",
                args,
            ).fetchall()
        saved = len(profile_rows)
        with_bc = 0
        for (payload_text,) in profile_rows:
            try:
                payload = json.loads(payload_text)
            except (TypeError, ValueError):
                continue
            changed = payload.get("changedKeys")
            if isinstance(changed, list) and any(key in BC_KEYS for key in changed):
                with_bc += 1
        return {
            "total": total,
            "byName": by_name,
            "byDay": by_day,
            "sessions": {
                "replay": play_sessions,
                "ab": ab_sessions,
                "abRatio": (ab_sessions / play_sessions) if play_sessions else 0.0,
            },
            "profiles": {
                "saved": saved,
                "withBc": with_bc,
                "withBcRatio": (with_bc / saved) if saved else 0.0,
            },
        }


def event_store() -> EventStore:
    return EventStore()


def events_rate_limit() -> int:
    raw = os.environ.get("VSTOCK_SONIFY_EVENTS_RATE_PER_MIN", "120")
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 120
