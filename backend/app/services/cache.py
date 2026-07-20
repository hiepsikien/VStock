from __future__ import annotations

import time
from threading import Lock
from typing import Any, TypeVar

T = TypeVar("T")


class TTLCache:
    """Simple in-memory TTL cache (thread-safe enough for local MVP)."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.monotonic() >= expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + ttl_seconds, value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


cache = TTLCache()

QUOTE_TTL = 15
HISTORY_TTL = 3600
FUNDAMENTALS_TTL = 6 * 3600
PROFILE_TTL = 24 * 3600
