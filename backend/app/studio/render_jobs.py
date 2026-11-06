"""In-memory bounded job queue for Studio Render Piece production audio.

This registry is deliberately separate from :mod:`app.studio.jobs` (the
validate/preview worker) and from the recap MuseScore queue:

* one process-local registry with a small TTL and a hard job cap;
* one global ``ThreadPoolExecutor`` for Studio audio jobs, while
  :mod:`app.studio.render_audio` owns the actual MuseScore semaphore
  (``VSTOCK_STUDIO_RENDER_SLOTS``);
* ``queued -> running -> ready|failed`` states;
* per-owner and global active caps plus an optional daily quota (W10), so a
  preview namespace cannot exhaust the box with long exports;
* jobs are content-addressed by ``renderHash`` and deduplicated per owner while
  queued/running or once ready. A failed job can be submitted again.

The registry is not persistent. Restarting the API drops queued jobs and a
client simply submits again. Audio files themselves stay in the WAV store.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.studio import render_audio, render_store

__all__ = [
    "READY",
    "FAILED",
    "QUEUED",
    "RUNNING",
    "AudioJobQueueFull",
    "AudioJobOwnerFull",
    "AudioJobQuotaExceeded",
    "AudioJobStatus",
    "AudioJobRegistry",
    "get_registry",
    "reset_registry",
]

QUEUED = "queued"
RUNNING = "running"
READY = "ready"
FAILED = "failed"
TERMINAL = frozenset({READY, FAILED})
ACTIVE = frozenset({QUEUED, RUNNING})

DEFAULT_MAX_JOBS = max(
    1, int(os.environ.get("VSTOCK_STUDIO_RENDER_AUDIO_JOBS_MAX", "64"))
)
DEFAULT_TTL_SECONDS = max(
    1.0, float(os.environ.get("VSTOCK_STUDIO_RENDER_AUDIO_JOBS_TTL_SECONDS", "3600"))
)
DEFAULT_MAX_PER_OWNER = max(
    1, int(os.environ.get("VSTOCK_STUDIO_RENDER_AUDIO_PER_OWNER", "4"))
)
DEFAULT_MAX_ACTIVE = max(
    1, int(os.environ.get("VSTOCK_STUDIO_RENDER_AUDIO_ACTIVE", "16"))
)
DEFAULT_PER_DAY = max(
    1, int(os.environ.get("VSTOCK_STUDIO_RENDER_PER_DAY", "32"))
)
DEFAULT_GLOBAL_PER_DAY = max(
    1, int(os.environ.get("VSTOCK_STUDIO_RENDER_GLOBAL_PER_DAY", "512"))
)
# First poll after a 202. The worker may already be running, so the client can
# back off from here.
RETRY_AFTER_SECONDS = 1


class AudioJobQueueFull(RuntimeError):
    """The bounded registry has no room for another active job."""

    def __init__(self, message: str, *, retry_after: int = RETRY_AFTER_SECONDS) -> None:
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))


class AudioJobOwnerFull(AudioJobQueueFull):
    """One owner already holds its share of active job slots."""


class AudioJobQuotaExceeded(AudioJobQueueFull):
    """One owner (or the server) used its daily production-audio allowance."""


@dataclass
class _AudioJob:
    id: str
    render_hash: str
    owner_id: str
    created_at: float
    status: str = QUEUED
    started_at: float | None = None
    finished_at: float | None = None
    audio_hash: str | None = None
    duration_sec: float = 0.0
    errors: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class AudioJobStatus:
    """Thread-safe snapshot of one audio job."""

    id: str
    render_hash: str
    owner_id: str
    status: str
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    audio_hash: str | None = None
    duration_sec: float = 0.0
    errors: tuple[dict[str, str], ...] = ()

    @property
    def done(self) -> bool:
        return self.status in TERMINAL

    @property
    def audio_url(self) -> str | None:
        digest = render_store.normalize_hash(self.audio_hash or "")
        return f"/v1/studio/figure/render/{digest}.wav" if digest else None


def _snapshot(job: _AudioJob) -> AudioJobStatus:
    return AudioJobStatus(
        id=job.id,
        render_hash=job.render_hash,
        owner_id=job.owner_id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        audio_hash=job.audio_hash,
        duration_sec=job.duration_sec,
        errors=job.errors,
    )


def _error(code: str, message: str) -> dict[str, str]:
    return {"path": "audio", "code": code, "message": message}


def _utc_day(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).date().isoformat()


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(minimum, float(raw))
    except ValueError:
        return default


class AudioJobRegistry:
    """Thread-safe bounded registry with its own worker thread."""

    def __init__(
        self,
        *,
        max_jobs: int | None = None,
        ttl_seconds: float | None = None,
        max_per_owner: int | None = None,
        max_active: int | None = None,
        per_day: int | None = None,
        global_per_day: int | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._max_jobs = max(
            1,
            int(
                DEFAULT_MAX_JOBS
                if max_jobs is not None
                else _env_int("VSTOCK_STUDIO_RENDER_AUDIO_JOBS_MAX", DEFAULT_MAX_JOBS)
            ),
        )
        self._ttl_seconds = max(
            0.0,
            float(
                DEFAULT_TTL_SECONDS
                if ttl_seconds is not None
                else _env_float(
                    "VSTOCK_STUDIO_RENDER_AUDIO_JOBS_TTL_SECONDS",
                    DEFAULT_TTL_SECONDS,
                )
            ),
        )
        self._max_per_owner = max(
            1,
            int(
                DEFAULT_MAX_PER_OWNER
                if max_per_owner is not None
                else _env_int(
                    "VSTOCK_STUDIO_RENDER_AUDIO_PER_OWNER", DEFAULT_MAX_PER_OWNER
                )
            ),
        )
        self._max_active = max(
            1,
            int(
                DEFAULT_MAX_ACTIVE
                if max_active is not None
                else _env_int(
                    "VSTOCK_STUDIO_RENDER_AUDIO_ACTIVE", DEFAULT_MAX_ACTIVE
                )
            ),
        )
        self._per_day = max(
            1,
            int(
                DEFAULT_PER_DAY
                if per_day is not None
                else _env_int("VSTOCK_STUDIO_RENDER_PER_DAY", DEFAULT_PER_DAY)
            ),
        )
        self._global_per_day = max(
            1,
            int(
                DEFAULT_GLOBAL_PER_DAY
                if global_per_day is not None
                else _env_int(
                    "VSTOCK_STUDIO_RENDER_GLOBAL_PER_DAY", DEFAULT_GLOBAL_PER_DAY
                )
            ),
        )
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.Lock()
        self._jobs: dict[str, _AudioJob] = {}
        self._daily_owners: dict[tuple[str, str], int] = {}
        self._daily_global: dict[str, int] = {}
        self._owns_executor = executor is None
        # One worker is enough: MuseScore itself is serialized by the store's
        # semaphore, and a single worker keeps queue order predictable.
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="studio-render-audio"
        )

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._jobs)

    @property
    def max_jobs(self) -> int:
        return self._max_jobs

    @property
    def max_per_owner(self) -> int:
        return self._max_per_owner

    def submit(
        self,
        render_hash: str,
        *,
        owner_id: str = "anonymous",
    ) -> AudioJobStatus:
        """Register and schedule one export, or return the deduplicated job."""
        digest = render_store.normalize_hash(render_hash)
        if digest is None:
            raise ValueError("renderHash must be 64 lowercase hex characters")
        display = f"sha256:{digest}"
        now = self._clock()
        wall = self._wall_clock()

        with self._lock:
            self._prune_locked(now)
            for job in self._jobs.values():
                if (
                    job.owner_id == owner_id
                    and render_store.normalize_hash(job.render_hash) == digest
                    and job.status in (ACTIVE | {READY})
                ):
                    if job.status == READY and job.audio_hash:
                        # A stale job whose file was pruned must not answer
                        # with a dead audioUrl.
                        if render_audio.load_audio(job.audio_hash) is None:
                            continue
                    return _snapshot(job)

            active_for_owner = sum(
                1
                for job in self._jobs.values()
                if job.owner_id == owner_id and job.status in ACTIVE
            )
            if active_for_owner >= self._max_per_owner:
                raise AudioJobOwnerFull(
                    f"Studio audio owner already has {self._max_per_owner} active jobs"
                )
            active_total = sum(
                1 for job in self._jobs.values() if job.status in ACTIVE
            )
            if active_total >= self._max_active:
                raise AudioJobQueueFull(
                    f"Studio audio queue is full ({self._max_active} active jobs)",
                    retry_after=2,
                )

            day = _utc_day(wall)
            owner_key = (owner_id, day)
            if self._daily_owners.get(owner_key, 0) >= self._per_day:
                raise AudioJobQuotaExceeded(
                    f"Studio audio daily quota reached ({self._per_day}/day)",
                    retry_after=self._seconds_until_utc_midnight(wall),
                )
            if self._daily_global.get(day, 0) >= self._global_per_day:
                raise AudioJobQuotaExceeded(
                    f"Studio audio global daily quota reached ({self._global_per_day}/day)",
                    retry_after=self._seconds_until_utc_midnight(wall),
                )

            self._make_room_locked(now)
            job = _AudioJob(
                id=f"audio_{uuid.uuid4().hex[:24]}",
                render_hash=display,
                owner_id=owner_id,
                created_at=now,
            )
            self._jobs[job.id] = job
            self._daily_owners[owner_key] = self._daily_owners.get(owner_key, 0) + 1
            self._daily_global[day] = self._daily_global.get(day, 0) + 1
            snapshot = _snapshot(job)

        try:
            self._executor.submit(self._run, job.id)
        except Exception:
            with self._lock:
                self._jobs.pop(job.id, None)
            raise
        return snapshot

    def get(
        self, job_id: str, *, owner_id: str | None = None
    ) -> AudioJobStatus | None:
        """One snapshot, pruning finished jobs first.

        A job owned by another namespace reads as missing (404) when
        ``owner_id`` is supplied, so a job id cannot be polled across sessions.
        """
        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if owner_id is not None and job.owner_id != owner_id:
                return None
            return _snapshot(job)

    def prune(self) -> int:
        now = self._clock()
        with self._lock:
            return self._prune_locked(now)

    def shutdown(self, wait: bool = False) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # worker

    def _run(self, job_id: str) -> None:
        now = self._clock()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = RUNNING
            job.started_at = now
            render_hash = job.render_hash

        errors: tuple[dict[str, str], ...] = ()
        audio_hash: str | None = None
        duration = 0.0
        status = FAILED
        try:
            xml_path = render_store.musicxml_path(render_hash)
            if xml_path is None or not xml_path.is_file():
                errors = (
                    _error("render_not_found", "no cached MusicXML for that renderHash"),
                )
            else:
                meta = render_store.load_render_meta(render_hash) or {}
                asset = render_audio.render_studio_wav(
                    xml_path,
                    render_hash=render_hash,
                    params=str(meta.get("paramsHash") or "") or None,
                    title=str(meta.get("title") or ""),
                    meter=str(meta.get("meter") or "") or None,
                    bars=int(meta.get("bars") or 0) or None,
                    bpm=float(meta.get("bpm") or 0) or None,
                )
                status = READY
                audio_hash = asset.audio_hash
                duration = asset.duration_sec
                try:
                    render_store.update_render_meta(
                        render_hash,
                        {
                            "audioHash": asset.audio_hash,
                            "audioRevision": render_audio.AUDIO_REVISION,
                            "audioDurationSec": round(asset.duration_sec, 3),
                        },
                    )
                except (OSError, ValueError):
                    pass
        except render_audio.StudioAudioError as exc:
            errors = (_error(exc.code, str(exc)),)
        except Exception as exc:  # never leave a job running forever
            errors = (
                _error(
                    "audio_failed",
                    f"{type(exc).__name__}: {exc}"[:400],
                ),
            )

        finished_at = self._clock()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # pruned while running
                return
            job.status = status
            job.finished_at = finished_at
            job.audio_hash = audio_hash
            job.duration_sec = duration
            job.errors = errors

    # ------------------------------------------------------------------
    # bounds, always called with the lock held

    def _prune_locked(self, now: float) -> int:
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status in TERMINAL
            and job.finished_at is not None
            and now - job.finished_at >= self._ttl_seconds
        ]
        for job_id in expired:
            del self._jobs[job_id]
        return len(expired)

    def _make_room_locked(self, now: float) -> None:
        self._prune_locked(now)
        while len(self._jobs) >= self._max_jobs:
            victim = next(
                (job for job in self._jobs.values() if job.status in TERMINAL),
                None,
            )
            if victim is None:
                raise AudioJobQueueFull(
                    f"Studio audio job registry is full ({self._max_jobs} jobs)",
                    retry_after=2,
                )
            del self._jobs[victim.id]

    @staticmethod
    def _seconds_until_utc_midnight(epoch: float) -> int:
        current = datetime.fromtimestamp(epoch, timezone.utc)
        tomorrow = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return max(1, int((tomorrow - current).total_seconds()))


_REGISTRY: AudioJobRegistry | None = None
_REGISTRY_GUARD = threading.Lock()


def get_registry() -> AudioJobRegistry:
    """The process-wide registry the router uses."""
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_GUARD:
            if _REGISTRY is None:
                _REGISTRY = AudioJobRegistry()
    return _REGISTRY


def reset_registry(
    registry: AudioJobRegistry | None = None,
) -> AudioJobRegistry:
    """Replace the process-wide registry (tests, shutdown)."""
    global _REGISTRY
    with _REGISTRY_GUARD:
        previous = _REGISTRY
        _REGISTRY = registry if registry is not None else AudioJobRegistry()
        current = _REGISTRY
    if previous is not None and previous is not current:
        previous.shutdown(wait=False)
    return current
