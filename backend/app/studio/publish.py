"""Persistent versioned registry for published sentence specs.

Phase 0/1 keeps the runtime on the code specs in `guitar_torroba.py` and
`guitar_sor.py`. Publishing therefore only records the authored JSON in
SQLite; it never writes to `SENTENCE_SPECS` and nothing loads it at runtime.

Versions are monotonic per `(pattern, meter)`. The next version is computed
inside the `INSERT ... SELECT`, so two concurrent publishes of the same key
cannot both claim the same number (the `UNIQUE(pattern, meter, version)`
constraint is the final guard).

Rows are immutable: a rollback copies an existing row's payload into a new
version and records the source in `rollback_of`; it never updates or deletes
the old row.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.sonify.sentence_specs import SentenceSpec
from app.studio.sentence_spec import spec_to_mapping

STATUS_PUBLISHED = "published"

_SUMMARY_COLUMNS = "id, pattern, meter, version, status, created_at, rollback_of"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_summary(row: aiosqlite.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "pattern": row["pattern"],
        "meter": row["meter"],
        "version": row["version"],
        "status": row["status"],
        "createdAt": row["created_at"],
        "rollbackOf": row["rollback_of"],
    }


async def _insert_version(
    db: aiosqlite.Connection,
    *,
    spec: SentenceSpec,
    payload: str,
    rollback_of: str | None,
) -> dict[str, Any]:
    """Insert `payload` as the next version for the spec's key and return it."""
    spec_id = uuid.uuid4().hex
    created_at = _now()
    await db.execute(
        """
        INSERT INTO studio_sentence_specs
            (id, pattern, meter, version, payload, status, created_at, rollback_of)
        SELECT ?, ?, ?, COALESCE(MAX(version), 0) + 1, ?, ?, ?, ?
        FROM studio_sentence_specs
        WHERE pattern = ? AND meter = ?
        """,
        (
            spec_id,
            spec.pattern,
            spec.meter,
            payload,
            STATUS_PUBLISHED,
            created_at,
            rollback_of,
            spec.pattern,
            spec.meter,
        ),
    )
    await db.commit()

    cursor = await db.execute(
        f"""
        SELECT {_SUMMARY_COLUMNS}
        FROM studio_sentence_specs
        WHERE id = ?
        """,
        (spec_id,),
    )
    row = await cursor.fetchone()
    if row is None:  # pragma: no cover - the insert just succeeded
        raise RuntimeError("published sentence row disappeared")
    return _row_to_summary(row)


async def publish_spec(db: aiosqlite.Connection, spec: SentenceSpec) -> dict[str, Any]:
    """Persist one already-parsed spec and return its summary."""
    payload = json.dumps(spec_to_mapping(spec), sort_keys=True)
    return await _insert_version(db, spec=spec, payload=payload, rollback_of=None)


async def rollback_spec(
    db: aiosqlite.Connection,
    spec: SentenceSpec,
    source_id: str,
) -> dict[str, Any] | None:
    """Republish `source_id`'s stored payload as a new version.

    `spec` is the already-parsed and family-validated form of that payload; it
    supplies the `(pattern, meter)` key. The source row is read, never written,
    so a rollback is just another append. Returns ``None`` when `source_id` does
    not exist.
    """
    cursor = await db.execute(
        "SELECT payload FROM studio_sentence_specs WHERE id = ?",
        (source_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return await _insert_version(
        db, spec=spec, payload=row["payload"], rollback_of=source_id
    )


async def list_specs(
    db: aiosqlite.Connection,
    *,
    pattern: str | None = None,
    meter: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List published spec summaries, newest version first, without payloads."""
    clauses: list[str] = []
    params: list[Any] = []
    if pattern is not None:
        clauses.append("pattern = ?")
        params.append(pattern)
    if meter is not None:
        clauses.append("meter = ?")
        params.append(meter)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    cursor = await db.execute(
        f"""
        SELECT {_SUMMARY_COLUMNS}
        FROM studio_sentence_specs
        {where}
        ORDER BY created_at DESC, rowid DESC
        LIMIT ?
        """,
        params,
    )
    return [_row_to_summary(row) for row in await cursor.fetchall()]


async def get_spec(db: aiosqlite.Connection, spec_id: str) -> dict[str, Any] | None:
    """Return one published spec including its payload, or ``None``."""
    cursor = await db.execute(
        f"""
        SELECT {_SUMMARY_COLUMNS}, payload
        FROM studio_sentence_specs
        WHERE id = ?
        """,
        (spec_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    summary = _row_to_summary(row)
    summary["payload"] = json.loads(row["payload"])
    return summary
