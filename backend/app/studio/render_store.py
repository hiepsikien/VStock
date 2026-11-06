"""Small on-disk cache for Studio Render Piece MusicXML output.

Phase C1 only stores the score text. Production audio gets its own store and
hash later (``docs/studio-render-piece-plan.md`` W1/W4). The cache is content
addressed: one ``renderHash`` names one ``.musicxml`` file and one sidecar.

Rules:

* the directory is ``VSTOCK_STUDIO_RENDER_DIR`` or ``backend/var/studio-render``;
* a hash must be 64 lowercase hex characters, optionally prefixed by
  ``sha256:``; nothing else is accepted as a path component;
* writes are atomic (temp file + ``os.replace``);
* entries expire after 24 hours and the directory keeps at most 256 files;
* a missing/expired/partial pair is a miss, never an exception.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "CACHE_TTL_SECONDS",
    "MAX_CACHE_FILES",
    "CachedRender",
    "load_render",
    "load_render_meta",
    "musicxml_path",
    "normalize_hash",
    "render_root",
    "update_render_meta",
    "write_render",
]

CACHE_TTL_SECONDS = 24 * 60 * 60
MAX_CACHE_FILES = 256

_HASH_RE = re.compile(r"^(?:sha256:)?([0-9a-f]{64})$")
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def normalize_hash(value: str) -> str | None:
    """Return the bare 64-char hex digest, or ``None`` for an unsafe value."""
    if not isinstance(value, str):
        return None
    match = _HASH_RE.fullmatch(value.strip().lower())
    return match.group(1) if match is not None else None


def _display_hash(digest: str) -> str:
    return f"sha256:{digest}"


def render_root() -> Path:
    raw = os.environ.get("VSTOCK_STUDIO_RENDER_DIR", "").strip()
    path = (
        Path(raw)
        if raw
        else Path(__file__).resolve().parents[2] / "var" / "studio-render"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


def _lock_for(digest: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(digest)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[digest] = lock
        return lock


def musicxml_path(value: str) -> Path | None:
    """Resolve one safe ``<hash>.musicxml`` path; ``None`` means invalid name."""
    digest = normalize_hash(value)
    if digest is None:
        return None
    return render_root() / f"{digest}.musicxml"


def _sidecar_path(digest: str) -> Path:
    return render_root() / f"{digest}.json"


def _is_expired(path: Path, now: float) -> bool:
    try:
        modified = path.stat().st_mtime
    except OSError:
        return True
    return modified < now - CACHE_TTL_SECONDS


def _prune(now: float | None = None) -> None:
    """Drop expired files and keep the newest ``MAX_CACHE_FILES`` scores."""
    root = render_root()
    now = time.time() if now is None else now
    entries: list[tuple[float, str]] = []
    for path in root.glob("*.musicxml"):
        digest = normalize_hash(path.stem)
        if digest is None:
            continue
        if _is_expired(path, now):
            path.unlink(missing_ok=True)
            _sidecar_path(digest).unlink(missing_ok=True)
            continue
        try:
            entries.append((path.stat().st_mtime, digest))
        except OSError:
            continue
    entries.sort()
    for _modified, digest in entries[: max(0, len(entries) - MAX_CACHE_FILES)]:
        (root / f"{digest}.musicxml").unlink(missing_ok=True)
        _sidecar_path(digest).unlink(missing_ok=True)
    # A crash between the score and the sidecar leaves an orphan sidecar.
    for path in root.glob("*.json"):
        if normalize_hash(path.stem) is None:
            path.unlink(missing_ok=True)


def _atomic_write(path: Path, data: bytes) -> None:
    root = path.parent
    root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=root, prefix=f".{path.stem}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class CachedRender:
    """One score plus its sidecar metadata."""

    render_hash: str
    path: Path
    musicxml: bytes
    meta: Mapping[str, Any]


def load_render(value: str) -> CachedRender | None:
    """Read a cached score. Missing, expired, or malformed entries are misses."""
    digest = normalize_hash(value)
    if digest is None:
        return None
    root = render_root()
    score = root / f"{digest}.musicxml"
    sidecar = _sidecar_path(digest)
    if not score.is_file() or not sidecar.is_file():
        return None
    if _is_expired(score, time.time()):
        score.unlink(missing_ok=True)
        sidecar.unlink(missing_ok=True)
        return None
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        xml = score.read_bytes()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict):
        return None
    stored = normalize_hash(str(meta.get("renderHash", "")))
    if stored != digest or not xml:
        return None
    return CachedRender(
        render_hash=_display_hash(digest),
        path=score,
        musicxml=xml,
        meta=meta,
    )


def write_render(
    value: str,
    musicxml: str | bytes,
    meta: Mapping[str, Any],
) -> CachedRender:
    """Atomically store one score and its sidecar; returns the cached record."""
    digest = normalize_hash(value)
    if digest is None:
        raise ValueError("renderHash must be 64 lowercase hex characters")
    payload = musicxml.encode("utf-8") if isinstance(musicxml, str) else bytes(musicxml)
    if not payload:
        raise ValueError("musicxml must not be empty")
    if not isinstance(meta, Mapping):
        raise ValueError("meta must be a mapping")

    root = render_root()
    score = root / f"{digest}.musicxml"
    sidecar = _sidecar_path(digest)
    record = dict(meta)
    record["renderHash"] = _display_hash(digest)
    record.setdefault(
        "createdAt", datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    with _lock_for(digest):
        _atomic_write(score, payload)
        _atomic_write(
            sidecar,
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            ),
        )
        _prune()
    return CachedRender(
        render_hash=_display_hash(digest),
        path=score,
        musicxml=payload,
        meta=record,
    )


def load_render_meta(value: str) -> dict[str, Any] | None:
    """Read one sidecar without reading the score; missing/invalid is ``None``."""
    digest = normalize_hash(value)
    if digest is None:
        return None
    sidecar = _sidecar_path(digest)
    if not sidecar.is_file():
        return None
    try:
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict):
        return None
    if normalize_hash(str(meta.get("renderHash", ""))) != digest:
        return None
    return meta


def update_render_meta(
    value: str,
    updates: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Merge audio fields into an existing score sidecar, atomically.

    The score file stays untouched (and keeps its cache TTL). A missing
    sidecar is a miss rather than an implicit write.
    """
    digest = normalize_hash(value)
    if digest is None:
        raise ValueError("renderHash must be 64 lowercase hex characters")
    if not isinstance(updates, Mapping):
        raise ValueError("updates must be a mapping")
    sidecar = _sidecar_path(digest)
    with _lock_for(digest):
        if not sidecar.is_file():
            return None
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(meta, dict):
            return None
        if normalize_hash(str(meta.get("renderHash", ""))) != digest:
            return None
        record = dict(meta)
        record.update(dict(updates))
        record["renderHash"] = _display_hash(digest)
        _atomic_write(
            sidecar,
            json.dumps(record, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            ),
        )
        return record
