"""Fire-and-forget orchestrator dispatch.

Plan B's POST /jobs blocked the HTTP request for the full pipeline (~7 min for
deep-dive). The browser UI can't keep an HTTP connection open that long, so
Plan C runs jobs in the background: POST /jobs returns the job_id immediately,
and the WebSocket /jobs/{id}/stream endpoint streams progress.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db.job_repo import JobRepo
from backend.models.job import JobState
from backend.observability.event_bus import JobEventBus

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, orchestrator, job_repo: JobRepo,
                 event_bus: Optional[JobEventBus] = None) -> None:
        self._orch = orchestrator
        self._repo = job_repo
        self._bus = event_bus
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self, workflow: str, **kwargs: Any) -> str:
        if workflow == "sector-sweep":
            primary = (kwargs["tickers"][0]).upper()
            kwargs["tickers"] = [t.upper() for t in kwargs["tickers"]]
        else:
            primary = (kwargs["ticker"]).upper()
            kwargs["ticker"] = primary

        job_id = str(uuid.uuid4())
        state = JobState(
            id=job_id, ticker=primary, workflow=workflow, status="running",
            created_at=datetime.now(timezone.utc), stages={},
        )
        await self._repo.create(state)
        task = asyncio.create_task(self._run(job_id, workflow, kwargs))
        self._tasks[job_id] = task
        return job_id

    async def _run(self, job_id: str, workflow: str,
                   kwargs: dict[str, Any]) -> None:
        try:
            result = await self._orch.run(workflow=workflow, job_id=job_id,
                                          **kwargs)
            final_status = result.get("status", "complete")
            await self._repo.update(
                job_id=job_id,
                status=final_status,
                current_stage=result.get("current_stage"),
                stages=result.get("stages", {}),
                rating=result.get("rating"),
                error=result.get("error"),
                completed_at=datetime.now(timezone.utc),
            )
            if self._bus is not None:
                await self._bus.publish(job_id, {
                    "type": "job_terminal",
                    "job_id": job_id,
                    "status": final_status,
                })
        except Exception as exc:  # broad: any orchestrator failure → failed job
            logger.exception("Job %s crashed", job_id)
            await self._repo.update(
                job_id=job_id, status="failed", error=str(exc),
                completed_at=datetime.now(timezone.utc),
            )
            if self._bus is not None:
                await self._bus.publish(job_id, {
                    "type": "job_terminal",
                    "job_id": job_id,
                    "status": "failed",
                })
        finally:
            self._tasks.pop(job_id, None)

    async def wait_for(self, job_id: str) -> None:
        """Test helper: block until the background task finishes."""
        task = self._tasks.get(job_id)
        if task is not None:
            try:
                await task
            except Exception:
                pass
