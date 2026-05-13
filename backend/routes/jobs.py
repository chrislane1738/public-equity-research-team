"""Jobs routes — async fire-and-forget POST + WebSocket stream."""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse

from backend.db.job_repo import JobRepo
from backend.job_runner import JobRunner
from backend.models.job import CreateJobRequest, JobState
from backend.observability.event_bus import JobEventBus


SUPPORTED_WORKFLOWS = {"full-deep-dive", "earnings-update", "morning-note",
                       "thesis-check", "sector-sweep"}


def build_router(runner: JobRunner, job_repo: JobRepo,
                 event_bus: JobEventBus) -> APIRouter:
    router = APIRouter()

    @router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
    async def create_job(req: CreateJobRequest):
        if req.workflow not in SUPPORTED_WORKFLOWS:
            raise HTTPException(400, f"Unsupported workflow: {req.workflow}")

        kwargs: dict = {}
        if req.workflow == "sector-sweep":
            if not req.tickers:
                raise HTTPException(400, "sector-sweep requires `tickers`")
            kwargs["tickers"] = req.tickers
        else:
            if not req.ticker:
                raise HTTPException(400, f"{req.workflow} requires `ticker`")
            kwargs["ticker"] = req.ticker

        if req.workflow == "thesis-check":
            if not req.question:
                raise HTTPException(400, "thesis-check requires `question`")
            kwargs["question"] = req.question

        job_id = await runner.start(req.workflow, **kwargs)
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "status": "running",
                     "workflow": req.workflow},
        )

    @router.get("/jobs/{job_id}", response_model=JobState)
    async def get_job(job_id: str) -> JobState:
        out = await job_repo.get(job_id)
        if out is None:
            raise HTTPException(404, "Job not found")
        return out

    @router.websocket("/jobs/{job_id}/stream")
    async def stream_job(ws: WebSocket, job_id: str) -> None:
        existing = await job_repo.get(job_id)
        if existing is None:
            await ws.close(code=1008, reason="job not found")
            return
        await ws.accept()
        q = event_bus.subscribe(job_id)
        try:
            await ws.send_json({"type": "state",
                                "state": existing.model_dump(mode="json")})
            while True:
                event = await q.get()
                await ws.send_json(event)
                # Persisted state catches up only on terminal: re-emit and exit.
                if event.get("type") == "stage" and event.get("status") == "complete":
                    final = await job_repo.get(job_id)
                    if final is not None:
                        await ws.send_json({"type": "state",
                                            "state": final.model_dump(mode="json")})
                    break
        except WebSocketDisconnect:
            pass
        finally:
            event_bus.unsubscribe(job_id, q)

    return router
