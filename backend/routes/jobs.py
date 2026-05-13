"""Job routes — POST /jobs to start, GET /jobs/{id} for status. SQLite-backed."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.db.job_repo import JobRepo
from backend.models.job import CreateJobRequest, JobState


SUPPORTED_WORKFLOWS = {"full-deep-dive", "earnings-update", "morning-note",
                       "thesis-check", "sector-sweep"}


def build_router(orchestrator, job_repo: JobRepo) -> APIRouter:
    router = APIRouter()

    @router.post("/jobs", response_model=JobState)
    async def create_job(req: CreateJobRequest) -> JobState:
        if req.workflow not in SUPPORTED_WORKFLOWS:
            raise HTTPException(400, f"Unsupported workflow: {req.workflow}")

        # Sector sweep takes a list; everything else takes a single ticker.
        if req.workflow == "sector-sweep":
            if not req.tickers:
                raise HTTPException(400, "sector-sweep requires `tickers`")
            primary_ticker = req.tickers[0].upper()
            kwargs = {"tickers": [t.upper() for t in req.tickers]}
        else:
            if not req.ticker:
                raise HTTPException(400, f"{req.workflow} requires `ticker`")
            primary_ticker = req.ticker.upper()
            kwargs = {"ticker": primary_ticker}

        if req.workflow == "thesis-check":
            if not req.question:
                raise HTTPException(400, "thesis-check requires `question`")
            kwargs["question"] = req.question

        job_id = str(uuid.uuid4())
        state = JobState(id=job_id, ticker=primary_ticker, workflow=req.workflow,
                         status="running",
                         created_at=datetime.now(timezone.utc), stages={})
        await job_repo.create(state)

        try:
            result = await orchestrator.run(workflow=req.workflow,
                                            job_id=job_id, **kwargs)
        except NotImplementedError as exc:
            await job_repo.update(job_id=job_id, status="failed",
                                  error=str(exc),
                                  completed_at=datetime.now(timezone.utc))
            raise HTTPException(501, f"Workflow not yet implemented: {exc}")

        await job_repo.update(
            job_id=job_id,
            status=result.get("status", "complete"),
            current_stage=result.get("current_stage"),
            stages=result.get("stages", {}),
            rating=result.get("rating"),
            error=result.get("error"),
            completed_at=datetime.now(timezone.utc),
        )
        return await job_repo.get(job_id)

    @router.get("/jobs/{job_id}", response_model=JobState)
    async def get_job(job_id: str) -> JobState:
        out = await job_repo.get(job_id)
        if out is None:
            raise HTTPException(404, "Job not found")
        return out

    return router
