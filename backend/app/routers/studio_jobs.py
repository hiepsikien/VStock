"""Pollable Studio validate/preview jobs (Phase 1).

The synchronous endpoints in ``app.routers.studio`` stay the contract for a
quick request. These endpoints add the queue path the UI uses for a render that
may wait behind the single Studio worker:

* ``POST /v1/studio/jobs`` -> ``202 {ok, jobId, status}``;
* ``GET /v1/studio/jobs/{id}``:
  * ``404`` when the id is unknown or its finished job expired;
  * ``409`` while queued/running, with ``Retry-After``;
  * ``200`` with ``{ok, jobId, status, result}`` once done, where ``ok`` is the
    job status (``status == "ok"``) and ``result.ok`` is the spec result;
  * ``200`` with ``{ok: false, jobId, status: "error", errors}`` when the
    renderer raised unexpectedly.

No auth, database, or persistence: the registry is process-local and a restart
drops jobs. The synchronous routes are untouched, so both paths stay usable.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.studio import jobs, session as studio_session

router = APIRouter(prefix="/v1/studio/jobs", tags=["studio"])

JobKind = Literal["validate", "preview"]


class JobRequest(BaseModel):
    kind: JobKind
    spec: dict[str, Any]
    fixture: dict[str, Any] = Field(default_factory=dict)


class JobErrorOut(BaseModel):
    path: str
    message: str


class JobAcceptedResponse(BaseModel):
    ok: bool = True
    jobId: str
    status: str


class JobResultResponse(BaseModel):
    ok: bool
    jobId: str
    status: str
    result: dict[str, Any] | None = None
    errors: list[JobErrorOut] = Field(default_factory=list)


def _missing(job_id: str) -> JSONResponse:
    body = JobResultResponse(
        ok=False,
        jobId=job_id,
        status="missing",
        errors=[JobErrorOut(path="job", message="unknown or expired job")],
    )
    return JSONResponse(
        status_code=404, content=body.model_dump(exclude={"result"})
    )


@router.post("", status_code=202, response_model=JobAcceptedResponse)
def submit_job(
    body: JobRequest,
    owner_id: str = Depends(studio_session.owner_or_anonymous),
) -> JobAcceptedResponse:
    """Admit one validate/preview job to the global Studio worker."""
    try:
        job = jobs.get_registry().submit(
            body.kind, body.spec, body.fixture, owner_id=owner_id
        )
    except jobs.JobQueueFull as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(jobs.RETRY_AFTER_SECONDS)},
        ) from exc
    return JobAcceptedResponse(ok=True, jobId=job.id, status=job.status)


@router.get(
    "/{job_id}",
    response_model=JobResultResponse,
    responses={
        200: {"description": "Finished job (ok result or renderer error)"},
        404: {"description": "Unknown or expired job"},
        409: {"description": "Still queued or running; see Retry-After"},
    },
)
def get_job(job_id: str) -> JSONResponse:
    """Poll one job. This handler is sync so FastAPI keeps it off the loop."""
    status = jobs.get_registry().get(job_id)
    if status is None:
        return _missing(job_id)

    if not status.done:
        body = JobResultResponse(ok=False, jobId=status.id, status=status.status)
        return JSONResponse(
            status_code=409,
            content=body.model_dump(exclude={"result", "errors"}),
            headers={"Retry-After": str(jobs.RETRY_AFTER_SECONDS)},
        )

    if status.status == jobs.ERROR:
        body = JobResultResponse(
            ok=False,
            jobId=status.id,
            status=jobs.ERROR,
            errors=[JobErrorOut(path=item["path"], message=item["message"]) for item in status.errors],
        )
        return JSONResponse(
            status_code=200, content=body.model_dump(exclude={"result"})
        )

    body = JobResultResponse(
        ok=True,
        jobId=status.id,
        status=jobs.OK,
        result=status.result,
    )
    return JSONResponse(
        status_code=200, content=body.model_dump(exclude={"errors"})
    )
