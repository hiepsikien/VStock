"""Studio image blob storage under ``VSTOCK_STUDIO_DIR`` plus SQLite rows.

Files are content-addressed: ``uploads/<sha256>.<ext>``. One ``studio_blobs``
row per digest carries a refcount, so two uploads (same or different owners)
share a single file and deleting one upload never deletes the other's bytes.
The physical file disappears only when the refcount reaches zero.

The repository never stores image bytes: the default root is ``backend/var/
studio`` (git-ignored local dev), overridden in production by
``VSTOCK_STUDIO_DIR=/data/studio`` and in tests by ``tmp_path``.

Image validation is deliberately dependency-free: magic bytes decide the MIME,
and small header parsers read PNG/JPEG/WebP dimensions. That is enough to
reject non-images, mislabelled uploads, and absurd pixel counts without pulling
Pillow into the API image.
"""

from __future__ import annotations

import hashlib
import os
import re
import struct
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

MIME_WHITELIST = ("image/png", "image/jpeg", "image/webp")
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
DEFAULT_MAX_PIXELS = 40_000_000
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


class UploadError(ValueError):
    """One upload is rejected; the router maps ``status_code`` to HTTP."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class UploadInUse(UploadError):
    def __init__(self, message: str = "Upload is referenced by a spec") -> None:
        super().__init__("upload_in_use", message, 409)


@dataclass(frozen=True)
class UploadRecord:
    id: str
    owner_id: str
    sha256: str
    filename: str
    mime: str
    width: int | None
    height: int | None
    size_bytes: int
    path: Path
    created_at: str


def studio_root() -> Path:
    raw = os.environ.get("VSTOCK_STUDIO_DIR", "").strip()
    root = (
        Path(raw)
        if raw
        else Path(__file__).resolve().parents[2] / "var" / "studio"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def upload_root() -> Path:
    path = studio_root() / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def max_pixels() -> int:
    raw = os.environ.get("VSTOCK_STUDIO_MAX_PIXELS", "").strip()
    try:
        return max(1, int(raw)) if raw else DEFAULT_MAX_PIXELS
    except ValueError:
        return DEFAULT_MAX_PIXELS


def detect_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def image_dimensions(data: bytes, mime: str) -> tuple[int | None, int | None]:
    """Best-effort width/height from the container header (no decode)."""
    try:
        if mime == "image/png" and len(data) >= 24 and data[12:16] == b"IHDR":
            width, height = struct.unpack(">II", data[16:24])
            return int(width), int(height)
        if mime == "image/jpeg":
            return _jpeg_dimensions(data)
        if mime == "image/webp" and len(data) >= 30:
            return _webp_dimensions(data)
    except (struct.error, ValueError, IndexError):
        return None, None
    return None, None


def _jpeg_dimensions(data: bytes) -> tuple[int | None, int | None]:
    index = 2
    sof_markers = {
        0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
        0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
    }
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        segment_length = struct.unpack(">H", data[index : index + 2])[0]
        if marker in sof_markers and index + 7 <= len(data):
            height = struct.unpack(">H", data[index + 3 : index + 5])[0]
            width = struct.unpack(">H", data[index + 5 : index + 7])[0]
            return int(width), int(height)
        if segment_length < 2:
            break
        index += segment_length
    return None, None


def _webp_dimensions(data: bytes) -> tuple[int | None, int | None]:
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        width, height = struct.unpack("<HH", data[26:30])
        return int(width & 0x3FFF), int(height & 0x3FFF)
    if chunk == b"VP8L" and len(data) >= 25:
        bits = struct.unpack("<I", data[21:25])[0]
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return int(width), int(height)
    if chunk == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    return None, None


def _safe_filename(raw: str | None, fallback: str) -> str:
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    name = _SAFE_NAME.sub("_", name).strip(" .")
    return (name or fallback)[:200]


def _iso_now(now: datetime | None) -> str:
    moment = now if now is not None else datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def blob_path(relative: str) -> Path:
    root = studio_root().resolve()
    candidate = (root / relative).resolve()
    if root != candidate and root not in candidate.parents:
        raise UploadError("bad_blob_path", "Blob path escapes the studio root")
    return candidate


async def _store_blob(
    db: aiosqlite.Connection,
    digest: str,
    data: bytes,
    mime: str,
) -> str:
    relative = f"uploads/{digest}{_EXTENSIONS[mime]}"
    target = blob_path(relative)
    await db.execute(
        "INSERT INTO studio_blobs (sha256, path, refcount) VALUES (?, ?, 1) "
        "ON CONFLICT(sha256) DO UPDATE SET refcount = refcount + 1",
        (digest, relative),
    )
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, target)
    return relative


def validate_image(
    data: bytes,
    declared_mime: str | None,
    *,
    max_bytes: int,
    max_image_pixels: int | None = None,
) -> tuple[str, int, int]:
    """Return ``(mime, width, height)`` or raise ``UploadError``."""
    if not data:
        raise UploadError("empty_image", "Uploaded file is empty")
    if len(data) > max_bytes:
        raise UploadError(
            "image_too_large",
            f"Image exceeds the {max_bytes} byte limit",
            status_code=413,
        )

    detected = detect_image_mime(data)
    declared = (declared_mime or "").split(";", 1)[0].strip().lower()
    if declared in {"", "application/octet-stream", "binary/octet-stream"}:
        declared = ""
    if detected is None or detected not in MIME_WHITELIST:
        raise UploadError(
            "unsupported_mime",
            "Only PNG, JPEG, and WebP images are accepted",
            status_code=415,
        )
    if declared and declared != detected:
        raise UploadError(
            "mime_mismatch",
            f"Declared {declared} but the bytes are {detected}",
        )

    width, height = image_dimensions(data, detected)
    if width is None or height is None or width <= 0 or height <= 0:
        raise UploadError("unreadable_image", "Could not read image dimensions")
    pixel_limit = max_pixels() if max_image_pixels is None else max_image_pixels
    if width * height > pixel_limit:
        raise UploadError(
            "image_too_large",
            f"Image is {width}x{height}; the limit is {pixel_limit} pixels",
            status_code=413,
        )
    return detected, width, height


async def save_upload(
    db: aiosqlite.Connection,
    owner_id: str,
    data: bytes,
    *,
    filename: str | None,
    declared_mime: str | None,
    max_bytes: int,
    max_image_pixels: int | None = None,
    now: datetime | None = None,
) -> UploadRecord:
    """Validate, dedupe by sha256, and insert one ``studio_uploads`` row."""
    detected, width, height = validate_image(
        data,
        declared_mime,
        max_bytes=max_bytes,
        max_image_pixels=max_image_pixels,
    )

    digest = hashlib.sha256(data).hexdigest()
    await _store_blob(db, digest, data, detected)
    upload_id = uuid.uuid4().hex
    created_at = _iso_now(now)
    name = _safe_filename(filename, f"upload{_EXTENSIONS[detected]}")
    await db.execute(
        "INSERT INTO studio_uploads "
        "(id, owner_id, blob_sha256, filename, mime, width, height, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (upload_id, owner_id, digest, name, detected, width, height, created_at),
    )
    await db.commit()

    relative = f"uploads/{digest}{_EXTENSIONS[detected]}"
    return UploadRecord(
        id=upload_id,
        owner_id=owner_id,
        sha256=digest,
        filename=name,
        mime=detected,
        width=width,
        height=height,
        size_bytes=len(data),
        path=blob_path(relative),
        created_at=created_at,
    )


def _record(row: aiosqlite.Row) -> UploadRecord:
    relative = str(row["path"])
    path = blob_path(relative)
    size = path.stat().st_size if path.is_file() else 0
    return UploadRecord(
        id=str(row["id"]),
        owner_id=str(row["owner_id"]),
        sha256=str(row["blob_sha256"]),
        filename=str(row["filename"] or ""),
        mime=str(row["mime"] or ""),
        width=row["width"],
        height=row["height"],
        size_bytes=size,
        path=path,
        created_at=str(row["created_at"]),
    )


async def get_upload(
    db: aiosqlite.Connection,
    upload_id: str,
) -> UploadRecord | None:
    cursor = await db.execute(
        "SELECT u.*, b.path AS path FROM studio_uploads u "
        "JOIN studio_blobs b ON b.sha256 = u.blob_sha256 "
        "WHERE u.id = ?",
        (upload_id,),
    )
    row = await cursor.fetchone()
    return _record(row) if row is not None else None


async def has_spec_reference(
    db: aiosqlite.Connection,
    upload_id: str,
    owner_id: str,
) -> bool:
    """True when a spec row of this owner points at the upload.

    Phase 1 has no ``studio_specs`` table yet; the check is a forward-compatible
    seam so DELETE already returns 409 the day specs start storing upload ids.
    """
    cursor = await db.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'studio_specs'"
    )
    if await cursor.fetchone() is None:
        return False
    cursor = await db.execute(
        "SELECT 1 FROM studio_specs WHERE owner_id = ? AND json LIKE ? LIMIT 1",
        (owner_id, f"%{upload_id}%"),
    )
    return await cursor.fetchone() is not None


async def blob_refcount(db: aiosqlite.Connection, sha256: str) -> int:
    cursor = await db.execute(
        "SELECT refcount FROM studio_blobs WHERE sha256 = ?", (sha256,)
    )
    row = await cursor.fetchone()
    return int(row[0]) if row is not None else 0


async def delete_upload(
    db: aiosqlite.Connection,
    upload_id: str,
    owner_id: str,
) -> UploadRecord | None:
    """Delete one owner's upload row; unlink bytes only at refcount zero.

    Returns ``None`` when the upload does not exist *or* belongs to another
    owner: the router answers 404 either way so it cannot be used to probe
    another session's ids.
    """
    record = await get_upload(db, upload_id)
    if record is None or record.owner_id != owner_id:
        return None
    if await has_spec_reference(db, upload_id, owner_id):
        raise UploadInUse()

    await db.execute("DELETE FROM studio_uploads WHERE id = ?", (upload_id,))
    await db.execute(
        "UPDATE studio_blobs SET refcount = refcount - 1 WHERE sha256 = ?",
        (record.sha256,),
    )
    remaining = await blob_refcount(db, record.sha256)
    if remaining <= 0:
        await db.execute(
            "DELETE FROM studio_blobs WHERE sha256 = ?", (record.sha256,)
        )
    await db.commit()

    if remaining <= 0 and record.path.is_file():
        record.path.unlink()
    return record
