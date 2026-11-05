"""Persistent versioned registry for published sentence specs.

Phase 0/1 keeps the runtime on the code specs in `guitar_torroba.py` and
`guitar_sor.py`. Publishing therefore only records the authored JSON in
SQLite; it never writes to `SENTENCE_SPECS` and nothing loads it at runtime.

Versions are monotonic per `(pattern, meter)`. The next version is computed
inside the `INSERT ... SELECT`, so two concurrent publishes of the same key
cannot both claim the same number (the `UNIQUE(pattern, meter, version)`
constraint is the final guard). The sequence is deliberately global: owner
scoping only changes who can read/roll back a row, not the numbering.

Rows are immutable: a rollback copies an existing row's payload into a new
version and records the source in `rollback_of`; it never updates or deletes
the old row.

Owner/visibility (docs §10.2, §11.4)
------------------------------------
`X-Studio-Session` hashes to an opaque `owner_id`; a missing/blank header
resolves to the literal `"anonymous"` namespace so pre-scoping clients and rows
keep working. This is a namespace, not auth: anyone can choose a session.

* `private` (default) rows are readable by their owner only.
* `public` rows are readable by every namespace, including `anonymous`.
* A row can only be rolled back by its owner, even when it is public. The new
  version keeps the source's visibility and belongs to the caller.
* Older rows migrate to (`anonymous`, `private`), so a headerless client still
  sees exactly the rows it used to. A caller that does send a header no longer
  sees another session's private rows — that is the intended behaviour change.
* Summaries expose `visibility` but never `ownerId`, so listing public rows
  cannot leak which namespace authored them.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.sonify.sentence_specs import SentenceSpec
from app.studio.sentence_spec import spec_to_mapping
from app.studio.session import ANONYMOUS_OWNER

STATUS_PUBLISHED = "published"

OWNER_ANONYMOUS = ANONYMOUS_OWNER
VISIBILITY_PRIVATE = "private"
VISIBILITY_PUBLIC = "public"
VISIBILITIES = frozenset({VISIBILITY_PRIVATE, VISIBILITY_PUBLIC})

_SUMMARY_COLUMNS = (
    "id, pattern, meter, version, status, created_at, rollback_of, "
    "owner_id, visibility"
)


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
        "visibility": row["visibility"],
    }


async def _insert_version(
    db: aiosqlite.Connection,
    *,
    spec: SentenceSpec,
    payload: str,
    rollback_of: str | None,
    owner_id: str,
    visibility: str,
) -> dict[str, Any]:
    """Insert `payload` as the next version for the spec's key and return it."""
    spec_id = uuid.uuid4().hex
    created_at = _now()
    await db.execute(
        """
        INSERT INTO studio_sentence_specs
            (id, pattern, meter, version, payload, status, created_at,
             rollback_of, owner_id, visibility)
        SELECT ?, ?, ?, COALESCE(MAX(version), 0) + 1, ?, ?, ?, ?, ?, ?
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
            owner_id,
            visibility,
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


async def publish_spec(
    db: aiosqlite.Connection,
    spec: SentenceSpec,
    *,
    owner_id: str = OWNER_ANONYMOUS,
    visibility: str = VISIBILITY_PRIVATE,
) -> dict[str, Any]:
    """Persist one already-parsed spec and return its summary.

    `visibility` must be ``private`` or ``public``; the router validates it
    before calling, and the default keeps headerless legacy callers private.
    """
    if visibility not in VISIBILITIES:
        raise ValueError(f"unknown visibility {visibility!r}")
    payload = json.dumps(spec_to_mapping(spec), sort_keys=True)
    return await _insert_version(
        db,
        spec=spec,
        payload=payload,
        rollback_of=None,
        owner_id=owner_id,
        visibility=visibility,
    )


async def rollback_spec(
    db: aiosqlite.Connection,
    spec: SentenceSpec,
    source_id: str,
    *,
    owner_id: str = OWNER_ANONYMOUS,
) -> dict[str, Any] | None:
    """Republish `source_id`'s stored payload as a new version.

    `spec` is the already-parsed and family-validated form of that payload; it
    supplies the `(pattern, meter)` key. The source row is read, never written,
    so a rollback is just another append. Only the row's owner may roll it
    back, even when the row is public. The new version keeps the source's
    visibility and belongs to the caller. Returns ``None`` when `source_id`
    does not exist or belongs to another namespace.
    """
    cursor = await db.execute(
        """
        SELECT payload, visibility
        FROM studio_sentence_specs
        WHERE id = ? AND owner_id = ?
        """,
        (source_id, owner_id),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return await _insert_version(
        db,
        spec=spec,
        payload=row["payload"],
        rollback_of=source_id,
        owner_id=owner_id,
        visibility=row["visibility"],
    )


async def list_specs(
    db: aiosqlite.Connection,
    *,
    pattern: str | None = None,
    meter: str | None = None,
    limit: int = 100,
    owner_id: str | None = None,
) -> list[dict[str, Any]]:
    """List published spec summaries, newest version first, without payloads.

    With `owner_id`, only that namespace's rows plus every ``public`` row are
    returned. `owner_id=None` keeps the unscoped listing for internal callers.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if pattern is not None:
        clauses.append("pattern = ?")
        params.append(pattern)
    if meter is not None:
        clauses.append("meter = ?")
        params.append(meter)
    if owner_id is not None:
        clauses.append("(owner_id = ? OR visibility = ?)")
        params.extend([owner_id, VISIBILITY_PUBLIC])
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


async def get_spec(
    db: aiosqlite.Connection,
    spec_id: str,
    *,
    owner_id: str | None = None,
) -> dict[str, Any] | None:
    """Return one published spec including its payload, or ``None``.

    With `owner_id`, a private row owned by another namespace reads as missing.
    """
    clauses = ["id = ?"]
    params: list[Any] = [spec_id]
    if owner_id is not None:
        clauses.append("(owner_id = ? OR visibility = ?)")
        params.extend([owner_id, VISIBILITY_PUBLIC])

    cursor = await db.execute(
        f"""
        SELECT {_SUMMARY_COLUMNS}, payload
        FROM studio_sentence_specs
        WHERE {' AND '.join(clauses)}
        """,
        params,
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    summary = _row_to_summary(row)
    summary["payload"] = json.loads(row["payload"])
    return summary
