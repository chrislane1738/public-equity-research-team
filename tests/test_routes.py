import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from backend.db.sqlite_client import SqliteClient
from backend.main import build_app
from backend.observability.event_bus import JobEventBus


@pytest.fixture
def app_ctx(tmp_path):
    sqlite = SqliteClient(tmp_path / "test.sqlite")
    bus = JobEventBus()

    async def fake_run(workflow, job_id, **kwargs):
        # Emit one event before completing so WS tests have something to receive.
        await bus.publish(job_id, {"type": "agent_completed", "agent": "fundamentals",
                                    "job_id": job_id})
        await asyncio.sleep(0.01)
        await bus.publish(job_id, {"type": "stage", "stage": "stage_4",
                                    "status": "complete", "job_id": job_id})
        return {"status": "complete", "current_stage": None,
                "stages": {"fundamentals": "complete"}, "rating": "Buy"}

    orch = type("O", (), {})()
    orch.run = fake_run

    app = build_app(orchestrator=orch, research_dir=tmp_path,
                    sqlite_client=sqlite, event_bus=bus)
    with TestClient(app) as client:
        yield client


def _wait(client, job_id, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/jobs/{job_id}")
        if r.status_code == 200 and r.json()["status"] in ("complete", "failed"):
            return r.json()
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish in {timeout}s")


def test_post_jobs_returns_202_with_job_id(app_ctx):
    r = app_ctx.post("/jobs", json={"ticker": "NVDA", "workflow": "morning-note"})
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "running"
    assert body["workflow"] == "morning-note"


def test_post_jobs_rejects_unknown_workflow(app_ctx):
    r = app_ctx.post("/jobs", json={"ticker": "NVDA", "workflow": "bogus"})
    assert r.status_code == 400


def test_post_jobs_then_get_returns_complete_state(app_ctx):
    r = app_ctx.post("/jobs", json={"ticker": "NVDA", "workflow": "morning-note"})
    job_id = r.json()["job_id"]
    final = _wait(app_ctx, job_id)
    assert final["status"] == "complete"
    assert final["rating"] == "Buy"


def test_get_unknown_job_returns_404(app_ctx):
    r = app_ctx.get("/jobs/does-not-exist")
    assert r.status_code == 404


def test_thesis_check_requires_question(app_ctx):
    r = app_ctx.post("/jobs", json={"ticker": "NVDA", "workflow": "thesis-check"})
    assert r.status_code == 400


def test_sector_sweep_requires_tickers(app_ctx):
    r = app_ctx.post("/jobs", json={"workflow": "sector-sweep"})
    assert r.status_code == 400


def test_ws_stream_emits_state_then_events(app_ctx):
    r = app_ctx.post("/jobs", json={"ticker": "NVDA", "workflow": "morning-note"})
    job_id = r.json()["job_id"]
    with app_ctx.websocket_connect(f"/jobs/{job_id}/stream") as ws:
        first = ws.receive_json()
        assert first["type"] == "state"
        assert first["state"]["id"] == job_id
        # Subsequent frames are agent_completed and/or stage events.
        # We expect at least one more before the socket closes on the terminal frame.
        second = ws.receive_json()
        assert second["type"] in ("agent_completed", "stage")


def test_ws_stream_rejects_unknown_job(app_ctx):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with app_ctx.websocket_connect("/jobs/no-such-id/stream") as ws:
            ws.receive_json()
