from datetime import datetime, timezone

import pytest

from backend.db.job_repo import JobRepo
from backend.db.sqlite_client import SqliteClient
from backend.models.job import JobState


@pytest.fixture
async def repo(tmp_path):
    client = SqliteClient(tmp_path / "test.sqlite")
    await client.connect()
    await client.init_schema()
    yield JobRepo(client)
    await client.close()


async def test_create_then_get_returns_job(repo):
    js = JobState(id="job-1", ticker="NVDA", workflow="full-deep-dive",
                  status="running", current_stage="fundamentals", stages={})
    await repo.create(js)
    out = await repo.get("job-1")
    assert out.id == "job-1"
    assert out.ticker == "NVDA"
    assert out.status == "running"


async def test_update_status_persists_changes(repo):
    js = JobState(id="job-2", ticker="AAPL", workflow="full-deep-dive",
                  status="running", stages={})
    await repo.create(js)
    await repo.update(job_id="job-2", status="complete",
                      current_stage=None,
                      stages={"fundamentals": "complete"},
                      rating="Buy",
                      completed_at=datetime.now(timezone.utc))
    out = await repo.get("job-2")
    assert out.status == "complete"
    assert out.rating == "Buy"
    assert out.stages == {"fundamentals": "complete"}
    assert out.completed_at is not None


async def test_get_returns_none_for_unknown_id(repo):
    out = await repo.get("nope")
    assert out is None


async def test_list_recent_returns_descending_by_created_at(repo):
    for i in range(3):
        await repo.create(JobState(id=f"job-{i}", ticker=f"T{i}",
                                   workflow="full-deep-dive", status="running",
                                   stages={}))
    rows = await repo.list_recent(limit=10)
    ids = [r.id for r in rows]
    assert "job-0" in ids and "job-2" in ids
    assert len(rows) == 3
