"""Per-owner daily counters for Studio uploads/analyses/specs.

Counters live in SQLite (``studio_quota``) so they survive a process restart
within the same database and behave the same in tests and on Fly. The clock is
injectable: callers pass ``now=`` and tests pin a day without sleeping.

The window is UTC calendar day. Over-limit calls are rejected without
incrementing the counter, and the response carries seconds until the next UTC
midnight for ``Retry-After``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiosqlite

KIND_UPLOAD = "upload"
KIND_ANALYZE = "analyze"
KIND_SPEC = "spec"
KINDS = (KIND_UPLOAD, KIND_ANALYZE, KIND_SPEC)


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    kind: str
    day: str
    used: int
    limit: int
    remaining: int
    retry_after_seconds: int


def _now(now: datetime | None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def current_day(now: datetime | None = None) -> str:
    return _now(now).astimezone(timezone.utc).date().isoformat()


def seconds_until_reset(now: datetime | None = None) -> int:
    moment = _now(now).astimezone(timezone.utc)
    tomorrow = (moment + timedelta(days=1)).date()
    reset = datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc
    )
    return max(1, int((reset - moment).total_seconds()))


async def used(
    db: aiosqlite.Connection,
    owner_id: str,
    kind: str,
    *,
    now: datetime | None = None,
) -> int:
    cursor = await db.execute(
        "SELECT used FROM studio_quota WHERE owner_id = ? AND kind = ? AND day = ?",
        (owner_id, kind, current_day(now)),
    )
    row = await cursor.fetchone()
    return int(row[0]) if row is not None else 0


async def consume(
    db: aiosqlite.Connection,
    owner_id: str,
    kind: str,
    limit: int,
    *,
    now: datetime | None = None,
) -> QuotaDecision:
    """Spend one unit of ``kind`` for ``owner_id`` today, or report 429 data."""
    if kind not in KINDS:
        raise ValueError(f"unknown quota kind {kind!r}")
    day = current_day(now)
    retry_after = seconds_until_reset(now)
    limit = max(0, int(limit))

    await db.execute(
        "INSERT INTO studio_quota (owner_id, kind, day, used) VALUES (?, ?, ?, 0) "
        "ON CONFLICT(owner_id, kind, day) DO NOTHING",
        (owner_id, kind, day),
    )
    cursor = await db.execute(
        "UPDATE studio_quota SET used = used + 1 "
        "WHERE owner_id = ? AND kind = ? AND day = ? AND used < ?",
        (owner_id, kind, day, limit),
    )
    allowed = cursor.rowcount > 0
    await db.commit()

    current = await used(db, owner_id, kind, now=now)
    return QuotaDecision(
        allowed=allowed,
        kind=kind,
        day=day,
        used=current,
        limit=limit,
        remaining=max(0, limit - current),
        retry_after_seconds=retry_after,
    )


async def reset(
    db: aiosqlite.Connection,
    owner_id: str | None = None,
) -> None:
    """Clear counters (tests and operator tooling; not exposed over HTTP)."""
    if owner_id is None:
        await db.execute("DELETE FROM studio_quota")
    else:
        await db.execute("DELETE FROM studio_quota WHERE owner_id = ?", (owner_id,))
    await db.commit()
