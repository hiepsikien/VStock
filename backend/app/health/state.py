from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ProviderRecord:
    kind: str
    name: str
    status: str = "unknown"
    last_success_at: str | None = None
    last_error_at: str | None = None
    last_error: str | None = None
    last_item_count: int = 0


@dataclass
class JobRecord:
    name: str
    last_run_at: str | None = None
    last_success_at: str | None = None
    last_error_at: str | None = None
    last_error: str | None = None
    last_item_count: int = 0


_records: dict[str, ProviderRecord] = {}
_jobs: dict[str, JobRecord] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_key(kind: str, name: str) -> str:
    return f"{kind}:{name}"


def ensure_provider(kind: str, name: str) -> ProviderRecord:
    key = _provider_key(kind, name)
    if key not in _records:
        _records[key] = ProviderRecord(kind=kind, name=name)
    return _records[key]


def record_provider_success(kind: str, name: str, item_count: int = 0) -> None:
    record = ensure_provider(kind, name)
    record.status = "ok"
    record.last_success_at = _now_iso()
    record.last_item_count = item_count
    record.last_error = None


def record_provider_failure(kind: str, name: str, error: str) -> None:
    record = ensure_provider(kind, name)
    record.status = "down"
    record.last_error_at = _now_iso()
    record.last_error = error[:240]


def record_job_success(name: str, item_count: int = 0) -> None:
    job = _jobs.setdefault(name, JobRecord(name=name))
    now = _now_iso()
    job.last_run_at = now
    job.last_success_at = now
    job.last_item_count = item_count
    job.last_error = None


def record_job_failure(name: str, error: str) -> None:
    job = _jobs.setdefault(name, JobRecord(name=name))
    now = _now_iso()
    job.last_run_at = now
    job.last_error_at = now
    job.last_error = error[:240]


def list_providers() -> list[ProviderRecord]:
    return sorted(_records.values(), key=lambda item: (item.kind, item.name))


def list_jobs() -> list[JobRecord]:
    return sorted(_jobs.values(), key=lambda item: item.name)
