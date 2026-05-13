"""Job routes — POST /jobs to start, GET /jobs/{id} for status."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.models.job import CreateJobRequest, JobState


def build_router(orchestrator) -> APIRouter:
    router = APIRouter()
    jobs: dict[str, JobState] = {}

    @router.post("/jobs", response_model=JobState)
    async def create_job(req: CreateJobRequest) -> JobState:
        job_id = str(uuid.uuid4())
        state = JobState(
            id=job_id,
            ticker=req.ticker.upper(),
            workflow=req.workflow,
            status="running",
            created_at=datetime.now(timezone.utc),
        )
        jobs[job_id] = state

        # Plan A: synchronous within the request. Plan B/C move this to a
        # background task with a /jobs/{id}/stream WebSocket.
        if req.workflow != "full-deep-dive":
            raise HTTPException(400, f"Workflow {req.workflow} not supported in Plan A")

        result = await orchestrator.run_full_deep_dive(ticker=req.ticker)

        state.status = result.get("status", "complete")
        state.current_stage = result.get("current_stage")
        state.stages = result.get("stages", {})
        state.rating = result.get("rating")
        state.error = result.get("error")
        state.completed_at = datetime.now(timezone.utc)
        return state

    @router.get("/jobs/{job_id}", response_model=JobState)
    async def get_job(job_id: str) -> JobState:
        if job_id not in jobs:
            raise HTTPException(404, "Job not found")
        return jobs[job_id]

    return router
