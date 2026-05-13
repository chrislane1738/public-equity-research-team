"""Job routes — POST /jobs to start, GET /jobs/{id} for status. SQLite-backed."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.db.job_repo import JobRepo
from backend.models.job import CreateJobRequest, JobState


SUPPORTED_WORKFLOWS = {"full-deep-dive"}


def build_router(orchestrator, job_repo: JobRepo) -> APIRouter:
    router = APIRouter()

    @router.post("/jobs", response_model=JobState)
    async def create_job(req: CreateJobRequest) -> JobState:
        if req.workflow not in SUPPORTED_WORKFLOWS:
            raise HTTPException(400, f"Workflow {req.workflow} not supported yet")

        job_id = str(uuid.uuid4())
        state = JobState(id=job_id, ticker=req.ticker.upper(),
                         workflow=req.workflow, status="running",
                         created_at=datetime.now(timezone.utc), stages={})
        await job_repo.create(state)

        result = await orchestrator.run_full_deep_dive(
            ticker=req.ticker, job_id=job_id
        )

        await job_repo.update(
            job_id=job_id,
            status=result.get("status", "complete"),
            current_stage=result.get("current_stage"),
            stages=result.get("stages", {}),
            rating=result.get("rating"),
            error=result.get("error"),
            completed_at=datetime.now(timezone.utc),
        )
        out = await job_repo.get(job_id)
        return out

    @router.get("/jobs/{job_id}", response_model=JobState)
    async def get_job(job_id: str) -> JobState:
        out = await job_repo.get(job_id)
        if out is None:
            raise HTTPException(404, "Job not found")
        return out

    return router
