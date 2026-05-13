from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.db.job_repo import JobRepo
from backend.db.sqlite_client import SqliteClient
from backend.main import build_app


@pytest.fixture
def fake_orch():
    o = type("O", (), {})()
    o.run_full_deep_dive = AsyncMock(return_value={
        "status": "complete", "current_stage": None,
        "stages": {"fundamentals": "complete"}, "rating": "Buy",
    })
    o.run = AsyncMock(return_value={
        "status": "complete", "current_stage": None,
        "stages": {"fundamentals": "complete"}, "rating": "Buy",
    })
    return o


def test_post_jobs_persists_then_get_returns_state(tmp_path, fake_orch):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    app = build_app(orchestrator=fake_orch, research_dir=tmp_path, sqlite_client=sqlite)
    with TestClient(app) as client:
        resp = client.post("/jobs", json={"ticker": "NVDA", "workflow": "full-deep-dive"})
        assert resp.status_code == 200
        job_id = resp.json()["id"]

        resp2 = client.get(f"/jobs/{job_id}")
        assert resp2.status_code == 200
        assert resp2.json()["rating"] == "Buy"
        assert resp2.json()["status"] == "complete"


def test_get_unknown_job_returns_404(tmp_path, fake_orch):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    app = build_app(orchestrator=fake_orch, research_dir=tmp_path, sqlite_client=sqlite)
    with TestClient(app) as client:
        resp = client.get("/jobs/does-not-exist")
        assert resp.status_code == 404


def test_unsupported_workflow_returns_400(tmp_path, fake_orch):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    app = build_app(orchestrator=fake_orch, research_dir=tmp_path, sqlite_client=sqlite)
    with TestClient(app) as client:
        resp = client.post("/jobs", json={"ticker": "NVDA", "workflow": "bogus"})
        assert resp.status_code == 400
