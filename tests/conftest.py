"""Shared pytest fixtures and helpers for the tests/ package."""
import time


def wait_for_job(client, job_id: str, timeout: float = 5.0):
    """Poll GET /jobs/{id} until it reaches a terminal state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/jobs/{job_id}")
        if r.status_code == 200 and r.json()["status"] in ("complete", "failed"):
            return r.json()
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")
