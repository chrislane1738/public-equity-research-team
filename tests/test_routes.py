from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.main import build_app


@pytest.fixture
def app(tmp_path):
    fake_orchestrator = MagicMock()
    fake_orchestrator.run_full_deep_dive = AsyncMock(return_value={
        "ticker": "NVDA",
        "status": "complete",
        "stages": {"fundamentals": "complete", "memo_builder": "complete"},
        "rating": "Buy",
    })
    app = build_app(orchestrator=fake_orchestrator, research_dir=tmp_path)
    return app, fake_orchestrator


def test_post_jobs_returns_job_id(app):
    fastapi_app, orch = app
    client = TestClient(fastapi_app)

    resp = client.post("/jobs", json={"ticker": "NVDA", "workflow": "full-deep-dive"})

    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["ticker"] == "NVDA"
    assert body["workflow"] == "full-deep-dive"


def test_post_jobs_runs_orchestrator(app):
    fastapi_app, orch = app
    client = TestClient(fastapi_app)
    resp = client.post("/jobs", json={"ticker": "NVDA"})
    assert resp.status_code == 200
    orch.run_full_deep_dive.assert_called_once_with(ticker="NVDA")


def test_get_jobs_status_after_run(app):
    fastapi_app, orch = app
    client = TestClient(fastapi_app)
    post_resp = client.post("/jobs", json={"ticker": "NVDA"})
    job_id = post_resp.json()["id"]

    get_resp = client.get(f"/jobs/{job_id}")

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["status"] == "complete"
    assert body["rating"] == "Buy"


def test_get_jobs_404_for_unknown_id(app):
    fastapi_app, _ = app
    client = TestClient(fastapi_app)
    resp = client.get("/jobs/nonexistent")
    assert resp.status_code == 404
