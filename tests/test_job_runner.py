import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from backend.db.job_repo import JobRepo
from backend.db.sqlite_client import SqliteClient
from backend.job_runner import JobRunner
from backend.models.job import JobState


async def test_start_job_returns_immediately_and_runs_in_background(tmp_path: Path):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    await sqlite.connect()
    await sqlite.init_schema()
    repo = JobRepo(sqlite)

    orch = MagicMock()
    completed = asyncio.Event()

    async def fake_run(workflow, job_id, **kwargs):
        await asyncio.sleep(0.05)
        completed.set()
        return {"status": "complete", "stages": {"fundamentals": "complete"},
                "rating": "Buy"}

    orch.run = fake_run

    runner = JobRunner(orch, repo)
    job_id = await runner.start("full-deep-dive", ticker="NVDA")
    assert job_id  # non-empty uuid

    # Repo immediately reflects "running"
    state = await repo.get(job_id)
    assert state.status == "running"

    # After background task finishes, repo reflects "complete"
    await completed.wait()
    await runner.wait_for(job_id)
    state = await repo.get(job_id)
    assert state.status == "complete"
    assert state.rating == "Buy"
    await sqlite.close()


async def test_start_job_persists_failure_on_orchestrator_exception(tmp_path: Path):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    await sqlite.connect()
    await sqlite.init_schema()
    repo = JobRepo(sqlite)

    orch = MagicMock()
    async def fake_run(workflow, job_id, **kwargs):
        raise RuntimeError("kaboom")
    orch.run = fake_run

    runner = JobRunner(orch, repo)
    job_id = await runner.start("morning-note", ticker="NVDA")
    await runner.wait_for(job_id)
    state = await repo.get(job_id)
    assert state.status == "failed"
    assert "kaboom" in (state.error or "")
    await sqlite.close()


async def test_sector_sweep_uses_first_ticker_for_state(tmp_path: Path):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    await sqlite.connect()
    await sqlite.init_schema()
    repo = JobRepo(sqlite)

    orch = MagicMock()
    orch.run = AsyncMock(return_value={"status": "complete", "stages": {}})

    runner = JobRunner(orch, repo)
    job_id = await runner.start("sector-sweep", tickers=["NVDA", "AMD"])
    await runner.wait_for(job_id)
    state = await repo.get(job_id)
    assert state.ticker == "NVDA"
    assert state.workflow == "sector-sweep"
    await sqlite.close()
