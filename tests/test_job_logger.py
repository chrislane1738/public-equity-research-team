import asyncio
import json
from pathlib import Path

from backend.agents.base import AgentResult
from backend.observability.event_bus import JobEventBus
from backend.observability.job_logger import JobLogger


def test_job_logger_writes_one_line_per_log_call(tmp_path):
    log_dir = tmp_path / "_logs"
    logger = JobLogger(job_id="job-abc", log_dir=log_dir)

    logger.log_agent("fundamentals", AgentResult(content="ok",
        input_tokens=100, output_tokens=50, cost_usd=0.01, stop_reason="end_turn"))
    logger.log_agent("industry", AgentResult(content="ok",
        input_tokens=200, output_tokens=80, cost_usd=0.02, stop_reason="end_turn"))

    log_file = log_dir / "job-abc.jsonl"
    assert log_file.exists()
    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    a = json.loads(lines[0])
    assert a["agent"] == "fundamentals"
    assert a["input_tokens"] == 100
    assert a["cost_usd"] == 0.01
    assert "ts" in a


def test_job_logger_aggregate_cost(tmp_path):
    logger = JobLogger(job_id="job-xyz", log_dir=tmp_path / "_logs")
    logger.log_agent("a", AgentResult(content="", cost_usd=0.10))
    logger.log_agent("b", AgentResult(content="", cost_usd=0.25))
    assert logger.total_cost_usd() == 0.35


def test_job_logger_handles_exception_log(tmp_path):
    logger = JobLogger(job_id="job-err", log_dir=tmp_path / "_logs")
    logger.log_error("dcf", "missing peer-multiples.json")
    line = json.loads((tmp_path / "_logs" / "job-err.jsonl").read_text().splitlines()[0])
    assert line["agent"] == "dcf"
    assert line["error"] == "missing peer-multiples.json"


class _StubResult:
    def __init__(self, cost=0.01, in_t=100, out_t=50, stop="end_turn"):
        self.cost_usd = cost
        self.input_tokens = in_t
        self.output_tokens = out_t
        self.stop_reason = stop


async def test_log_agent_publishes_event(tmp_path: Path):
    bus = JobEventBus()
    q = bus.subscribe("job-1")
    logger = JobLogger("job-1", tmp_path, event_bus=bus)
    logger.log_agent("dcf", _StubResult())
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["agent"] == "dcf"
    assert event["job_id"] == "job-1"
    assert event["cost_usd"] == 0.01
    assert event["type"] == "agent_completed"


async def test_log_error_publishes_event(tmp_path: Path):
    bus = JobEventBus()
    q = bus.subscribe("job-1")
    logger = JobLogger("job-1", tmp_path, event_bus=bus)
    logger.log_error("dcf", "boom")
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event["agent"] == "dcf"
    assert event["error"] == "boom"
    assert event["type"] == "agent_failed"


def test_event_bus_is_optional(tmp_path: Path):
    logger = JobLogger("job-1", tmp_path)  # no bus
    logger.log_agent("dcf", _StubResult())  # must not raise
    assert (tmp_path / "job-1.jsonl").exists()
