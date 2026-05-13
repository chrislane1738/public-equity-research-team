import json
from pathlib import Path

from backend.agents.base import AgentResult
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
