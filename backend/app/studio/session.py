"""Studio session namespace, access shape, and signed media tokens.

Studio has no auth: the app sends a random ``X-Studio-Session`` header, the
server hashes it into an opaque ``owner_id``, and every upload/spec/quota row is
scoped by that hash. This is a namespace, not a security boundary — anyone who
chooses to forge a session can use their own namespace. It does stop accidental
cross-session deletes and per-session quota burn.

``GET /access`` must work before a session exists (the app reads it to decide
whether to show the Studio pill), so only upload/analyze/spec endpoints require
the header.

Media (<img>, <audio>, download links) cannot send custom headers. Those GETs
take a short-lived HMAC token instead: the token carries the owner claim, is
signed together with the resource id, and the route still compares the claim
with the stored row's owner.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException

SESSION_HEADER = "X-Studio-Session"
OWNER_HASH_PREFIX = "vstock-studio-owner-v1:"
# A missing env secret must not fall back to a public constant. Generate one
# per process instead: tokens stop working after a restart/worker change, which
# is safer than a known key. Production should always set
# VSTOCK_STUDIO_SECRET.
_FALLBACK_SECRET = secrets.token_hex(32)
DEFAULT_TOKEN_TTL_SECONDS = 600
MIN_TOKEN_TTL_SECONDS = 300
MAX_TOKEN_TTL_SECONDS = 900

ACCESS_REASONS = ("open_beta", "entitled", "disabled")


def owner_id_for(session: str | None) -> str | None:
    """Stable, opaque owner id for one session string; blank/missing is None."""
    if session is None:
        return None
    value = session.strip()
    if not value:
        return None
    digest = hashlib.sha256((OWNER_HASH_PREFIX + value).encode("utf-8"))
    return digest.hexdigest()


def require_owner(
    x_studio_session: str | None = Header(default=None, alias=SESSION_HEADER),
) -> str:
    """FastAPI dependency: resolve the owner or reject with 400."""
    owner_id = owner_id_for(x_studio_session)
    if owner_id is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "studio_session_required",
                "message": f"Missing or blank {SESSION_HEADER} header",
            },
        )
    return owner_id


# Namespace used by clients/tests that predate the session header. Sentence
# publish keeps accepting them so old rows stay readable.
ANONYMOUS_OWNER = "anonymous"


def owner_or_anonymous(
    x_studio_session: str | None = Header(default=None, alias=SESSION_HEADER),
) -> str:
    """FastAPI dependency: resolve the owner, falling back to `anonymous`."""
    return owner_id_for(x_studio_session) or ANONYMOUS_OWNER


@dataclass(frozen=True)
class StudioQuota:
    uploads_per_day: int = 20
    analyses_per_day: int = 100
    specs_per_day: int = 50
    max_image_mb: int = 20
    previews_concurrent: int = 1

    def as_dict(self) -> dict[str, int]:
        return {
            "uploadsPerDay": self.uploads_per_day,
            "analysesPerDay": self.analyses_per_day,
            "specsPerDay": self.specs_per_day,
            "maxImageMb": self.max_image_mb,
            "previewsConcurrent": self.previews_concurrent,
        }

    @property
    def max_image_bytes(self) -> int:
        return max(1, self.max_image_mb) * 1024 * 1024


def _int_env(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def quota_limits() -> StudioQuota:
    """Read quota overrides per call so tests and deploys can tune them."""
    defaults = StudioQuota()
    return StudioQuota(
        uploads_per_day=_int_env(
            "VSTOCK_STUDIO_UPLOADS_PER_DAY", defaults.uploads_per_day
        ),
        analyses_per_day=_int_env(
            "VSTOCK_STUDIO_ANALYSES_PER_DAY", defaults.analyses_per_day
        ),
        specs_per_day=_int_env(
            "VSTOCK_STUDIO_SPECS_PER_DAY", defaults.specs_per_day
        ),
        max_image_mb=_int_env("VSTOCK_STUDIO_MAX_IMAGE_MB", defaults.max_image_mb),
        previews_concurrent=_int_env(
            "VSTOCK_STUDIO_PREVIEWS_CONCURRENT", defaults.previews_concurrent
        ),
    )


@dataclass(frozen=True)
class StudioGlobalQuota:
    uploads_per_day: int = 1000
    analyses_per_day: int = 5000


def global_quota_limits() -> StudioGlobalQuota:
    """Server-wide caps that make session rotation stop buying work."""
    defaults = StudioGlobalQuota()
    return StudioGlobalQuota(
        uploads_per_day=_int_env(
            "VSTOCK_STUDIO_GLOBAL_UPLOADS_PER_DAY", defaults.uploads_per_day
        ),
        analyses_per_day=_int_env(
            "VSTOCK_STUDIO_GLOBAL_ANALYSES_PER_DAY", defaults.analyses_per_day
        ),
    )


def _enabled() -> bool:
    raw = os.environ.get("VSTOCK_STUDIO_ENABLED", "").strip().lower()
    if not raw:
        return True
    return raw not in {"0", "false", "no", "off"}


def access_payload() -> dict:
    """The `/access` JSON exactly as §10.2.1 describes it."""
    enabled = _enabled()
    reason = os.environ.get("VSTOCK_STUDIO_ACCESS_REASON", "").strip()
    if reason not in ACCESS_REASONS or (not enabled and reason != "disabled"):
        reason = "open_beta" if enabled else "disabled"
    return {
        "enabled": enabled,
        "reason": reason,
        "quota": quota_limits().as_dict(),
    }


def require_enabled() -> None:
    if not _enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "studio_disabled",
                "message": "Studio is disabled for this deployment",
            },
        )


class TokenError(ValueError):
    """A media token is malformed, tampered with, or expired."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _secret() -> bytes:
    raw = os.environ.get("VSTOCK_STUDIO_SECRET", "").strip()
    return (raw or _FALLBACK_SECRET).encode("utf-8")


def token_ttl_seconds() -> int:
    raw = os.environ.get("VSTOCK_STUDIO_TOKEN_TTL_SECONDS", "").strip()
    try:
        ttl = int(raw) if raw else DEFAULT_TOKEN_TTL_SECONDS
    except ValueError:
        ttl = DEFAULT_TOKEN_TTL_SECONDS
    return max(MIN_TOKEN_TTL_SECONDS, min(MAX_TOKEN_TTL_SECONDS, ttl))


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _mac(owner_id: str, resource_id: str, expires_at: int) -> bytes:
    message = f"{owner_id}|{resource_id}|{expires_at}".encode("utf-8")
    return hmac.new(_secret(), message, hashlib.sha256).digest()


def sign_media_token(
    owner_id: str,
    resource_id: str,
    *,
    now: int | None = None,
    ttl_seconds: int | None = None,
) -> tuple[str, int]:
    """Return ``(token, expires_at_epoch_seconds)`` for one media resource."""
    issued = int(time.time()) if now is None else int(now)
    ttl = token_ttl_seconds() if ttl_seconds is None else int(ttl_seconds)
    expires_at = issued + ttl
    payload = _b64(f"{owner_id}:{expires_at}".encode("utf-8"))
    signature = _b64(_mac(owner_id, resource_id, expires_at))
    return f"{payload}.{signature}", expires_at


def verify_media_token(
    token: str,
    resource_id: str,
    *,
    now: int | None = None,
) -> str:
    """Return the owner claim, or raise ``TokenError``."""
    payload_text, separator, signature_text = (token or "").partition(".")
    if not separator or not payload_text or not signature_text:
        raise TokenError("malformed", "Token is malformed")
    try:
        payload = _unb64(payload_text).decode("utf-8")
        owner_id, _, expires_text = payload.partition(":")
        expires_at = int(expires_text)
        signature = _unb64(signature_text)
    except (ValueError, UnicodeDecodeError) as exc:
        raise TokenError("malformed", "Token is malformed") from exc
    if not owner_id:
        raise TokenError("malformed", "Token is malformed")
    if not hmac.compare_digest(signature, _mac(owner_id, resource_id, expires_at)):
        raise TokenError("bad_signature", "Token signature does not match")
    current = int(time.time()) if now is None else int(now)
    if expires_at < current:
        raise TokenError("expired", "Token has expired")
    return owner_id
