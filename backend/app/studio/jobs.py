"""In-memory bounded job queue for Studio validate/preview.

Phase 1 gives the sentence editor a pollable job instead of a request that
blocks for the whole render. The contract is intentionally small:

* one process-local registry, capped at ``VSTOCK_STUDIO_JOBS_MAX`` jobs
  (default 64) with a ``VSTOCK_STUDIO_JOBS_TTL_SECONDS`` TTL (default 600 s)
  for finished jobs;
* one global ``ThreadPoolExecutor(max_workers=1)`` for every validate/preview
  job, separate from the audio slots and the MuseScore export queue, so a slow
  preview cannot occupy the HTTP event loop or another queue's workers;
* ``queued -> running -> ok|error`` states.

``ok`` means the job finished and produced a result. The result itself can be
``{"ok": false, "errors": [...]}``; a rejected spec is a successful job, not a
failed one. ``error`` is reserved for an unexpected renderer exception (the
worker still records a job-level error instead of leaving the job running
forever).

The registry is deliberately not persistent: restarting the API drops queued
jobs and clients simply submit again. Nothing here touches the database, the
global ``SENTENCE_SPECS`` registry, publish, or Gemini.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Mapping

from app.sonify.sentence_specs import SentenceSpec
from app.studio import dispatch
from app.studio.sentence_spec import parse_spec

VALIDATE = "validate"
PREVIEW = "preview"
KINDS = frozenset({VALIDATE, PREVIEW})

QUEUED = "queued"
RUNNING = "running"
OK = "ok"
ERROR = "error"
TERMINAL = frozenset({OK, ERROR})

# `Retry-After` for a job that is still queued/running. The worker is a single
# thread, so one second is a reasonable first poll and the client backs off
# from there.
RETRY_AFTER_SECONDS = 1

DEFAULT_MAX_JOBS = max(1, int(os.environ.get("VSTOCK_STUDIO_JOBS_MAX", "64")))
DEFAULT_TTL_SECONDS = max(
    1.0, float(os.environ.get("VSTOCK_STUDIO_JOBS_TTL_SECONDS", "600"))
)
DEFAULT_MAX_PER_OWNER = max(
    1, int(os.environ.get("VSTOCK_STUDIO_JOBS_PER_OWNER", "8"))
)

_PARSE_ERRORS = (ValueError, KeyError, TypeError)


class JobQueueFull(RuntimeError):
    """The bounded registry has no room for another job."""


class JobOwnerFull(JobQueueFull):
    """One owner already holds its share of the active job slots."""


@dataclass
class _Job:
    """Mutable registry entry; only the registry lock mutates it."""

    id: str
    kind: str
    spec: SentenceSpec | Mapping[str, Any]
    fixture: dict[str, Any]
    owner_id: str
    created_at: float
    status: str = QUEUED
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    errors: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class JobStatus:
    """A thread-safe snapshot of one job at the moment ``get`` observed it."""

    id: str
    kind: str
    status: str
    result: dict[str, Any] | None
    errors: tuple[dict[str, str], ...]
    created_at: float
    finished_at: float | None = None

    @property
    def done(self) -> bool:
        return self.status in TERMINAL


def _snapshot(job: _Job) -> JobStatus:
    return JobStatus(
        id=job.id,
        kind=job.kind,
        status=job.status,
        result=job.result,
        errors=job.errors,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


def _error_payload(kind: str, errors: list[dict[str, str]]) -> dict[str, Any]:
    """A parse failure in the same spelling as a normal family response."""
    if kind == PREVIEW:
        return {
            "ok": False,
            "errors": errors,
            "plan": None,
            "row": None,
            "notes": [],
            "renderHash": None,
            "matrix": [],
        }
    return {"ok": False, "errors": errors}


def _execute(
    kind: str,
    spec: SentenceSpec | Mapping[str, Any],
    fixture: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Parse then validate/preview. Always returns one JSON-safe result."""
    try:
        parsed = spec if isinstance(spec, SentenceSpec) else parse_spec(spec)
    except _PARSE_ERRORS as exc:
        return _error_payload(kind, [{"path": "spec", "message": str(exc)}])

    if kind == VALIDATE:
        errors = [
            {"path": error.path, "message": error.message}
            for error in dispatch.validate(parsed)
        ]
        return {"ok": not errors, "errors": errors}

    return dispatch.preview_sentence(parsed, fixture).as_response()


class JobRegistry:
    """Thread-safe bounded registry with one worker thread."""

    def __init__(
        self,
        *,
        max_jobs: int | None = None,
        ttl_seconds: float | None = None,
        max_per_owner: int | None = None,
        clock: Any = time.monotonic,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        self._max_jobs = max(1, int(DEFAULT_MAX_JOBS if max_jobs is None else max_jobs))
        self._ttl_seconds = max(
            0.0, float(DEFAULT_TTL_SECONDS if ttl_seconds is None else ttl_seconds)
        )
        self._max_per_owner = max(
            1, int(DEFAULT_MAX_PER_OWNER if max_per_owner is None else max_per_owner)
        )
        self._clock = clock
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}
        self._owns_executor = executor is None
        # One worker for all validate/preview jobs. A second job waits in the
        # executor while the registry still shows it as `queued`.
        self._executor = executor or ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="studio-jobs"
        )

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._jobs)

    @property
    def max_jobs(self) -> int:
        return self._max_jobs

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    @property
    def max_per_owner(self) -> int:
        return self._max_per_owner

    def submit(
        self,
        kind: str,
        spec: SentenceSpec | Mapping[str, Any],
        fixture: Mapping[str, Any] | None = None,
        *,
        owner_id: str = "anonymous",
    ) -> JobStatus:
        """Register and schedule one job, returning its initial snapshot.

        Raises ``ValueError`` for an unknown kind and ``JobQueueFull`` when all
        admitted jobs are still active. Finished jobs are evicted oldest-first
        to make room before the queue is declared full.
        """
        if kind not in KINDS:
            raise ValueError(f"unknown Studio job kind {kind!r}")
        now = self._clock()
        job = _Job(
            id=f"job_{uuid.uuid4().hex[:24]}",
            kind=kind,
            # Detach from the request body; nested values are already plain
            # JSON data and are never mutated by the worker.
            spec=spec if isinstance(spec, SentenceSpec) else dict(spec),
            fixture=dict(fixture or {}),
            owner_id=owner_id,
            created_at=now,
        )
        with self._lock:
            self._make_room_locked(now)
            active_for_owner = sum(
                1
                for existing in self._jobs.values()
                if existing.owner_id == owner_id and existing.status not in TERMINAL
            )
            if active_for_owner >= self._max_per_owner:
                raise JobOwnerFull(
                    f"Studio job owner already has {self._max_per_owner} active jobs"
                )
            self._jobs[job.id] = job
            snapshot = _snapshot(job)

        try:
            self._executor.submit(self._run, job.id)
        except Exception:
            with self._lock:
                self._jobs.pop(job.id, None)
            raise
        return snapshot

    def get(self, job_id: str) -> JobStatus | None:
        """One snapshot, pruning expired finished jobs first."""
        now = self._clock()
        with self._lock:
            self._prune_locked(now)
            job = self._jobs.get(job_id)
            return None if job is None else _snapshot(job)

    def prune(self) -> int:
        """Drop finished jobs older than the TTL; return how many were dropped."""
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
            kind = job.kind
            spec = job.spec
            fixture = job.fixture

        status = OK
        result: dict[str, Any] | None
        errors: tuple[dict[str, str], ...] = ()
        try:
            result = _execute(kind, spec, fixture)
        except Exception as exc:  # renderer bug: record it, never hang the job
            status = ERROR
            result = None
            errors = (
                {
                    "path": kind,
                    "message": f"{type(exc).__name__}: {exc}",
                },
            )

        finished_at = self._clock()
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:  # pruned while running; nothing left to update
                return
            job.status = status
            job.finished_at = finished_at
            job.result = result
            job.errors = errors
            # Terminal jobs keep only the response; the submitted spec/fixture
            # can be large and no longer needs to sit in memory until TTL.
            job.spec = {}
            job.fixture = {}

    # ------------------------------------------------------------------
    # pruning and bounds, always called with the lock held

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
                raise JobQueueFull(
                    f"Studio job queue is full ({self._max_jobs} active jobs)"
                )
            del self._jobs[victim.id]


_REGISTRY: JobRegistry | None = None
_REGISTRY_GUARD = threading.Lock()


def get_registry() -> JobRegistry:
    """The process-wide registry the router uses."""
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_GUARD:
            if _REGISTRY is None:
                _REGISTRY = JobRegistry()
    return _REGISTRY


def reset_registry(registry: JobRegistry | None = None) -> JobRegistry:
    """Replace the process-wide registry (tests, shutdown)."""
    global _REGISTRY
    with _REGISTRY_GUARD:
        previous = _REGISTRY
        _REGISTRY = registry if registry is not None else JobRegistry()
        current = _REGISTRY
    if previous is not None and previous is not current:
        previous.shutdown(wait=False)
    return current
