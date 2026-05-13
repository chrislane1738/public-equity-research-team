"""Async SQLite-backed JobState repository."""
import json
from datetime import datetime, timezone
from typing import Optional

from backend.db.sqlite_client import SqliteClient
from backend.models.job import JobState


class JobRepo:
    def __init__(self, client: SqliteClient):
        self.db = client

    async def create(self, job: JobState) -> None:
        await self.db.execute(
            "INSERT INTO jobs (id, ticker, workflow, status, current_stage, "
            "agents_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job.id, job.ticker, job.workflow, job.status, job.current_stage,
             json.dumps(job.stages or {}),
             (job.created_at or datetime.now(timezone.utc)).isoformat()),
        )

    async def update(
        self,
        job_id: str,
        status: Optional[str] = None,
        current_stage: Optional[str] = None,
        stages: Optional[dict] = None,
        rating: Optional[str] = None,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        existing = await self.get(job_id)
        if existing is None:
            raise RuntimeError(f"job {job_id} not found")

        merged_stages = stages if stages is not None else existing.stages

        await self.db.execute(
            "UPDATE jobs SET status = ?, current_stage = ?, agents_status = ?, "
            "completed_at = ? WHERE id = ?",
            (
                status if status is not None else existing.status,
                current_stage if current_stage is not None else existing.current_stage,
                json.dumps(merged_stages or {}),
                completed_at.isoformat() if completed_at else (
                    existing.completed_at.isoformat() if existing.completed_at else None
                ),
                job_id,
            ),
        )
        # rating + error live as augmented JSON inside agents_status (they are
        # not first-class columns in the Plan A schema). Re-write that JSON to
        # bake them in for retrieval.
        bag = merged_stages or {}
        if rating is not None:
            bag = {**bag, "_rating": rating}
        if error is not None:
            bag = {**bag, "_error": error}
        await self.db.execute(
            "UPDATE jobs SET agents_status = ? WHERE id = ?",
            (json.dumps(bag), job_id),
        )

    async def get(self, job_id: str) -> Optional[JobState]:
        row = await self.db.fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        if row is None:
            return None
        return self._row_to_state(row)

    async def list_recent(self, limit: int = 20) -> list[JobState]:
        rows = await self.db.fetch_all(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [self._row_to_state(r) for r in rows]

    @staticmethod
    def _row_to_state(row: dict) -> JobState:
        bag = json.loads(row.get("agents_status") or "{}")
        rating = bag.pop("_rating", None)
        error = bag.pop("_error", None)
        return JobState(
            id=row["id"],
            ticker=row["ticker"],
            workflow=row["workflow"],
            status=row["status"],
            current_stage=row.get("current_stage"),
            stages=bag,
            rating=rating,
            error=error,
            created_at=_parse_dt(row.get("created_at")),
            completed_at=_parse_dt(row.get("completed_at")),
        )


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None
