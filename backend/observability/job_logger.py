"""Per-job JSONL telemetry. One line per logged event."""
import json
from datetime import datetime, timezone
from pathlib import Path


class JobLogger:
    def __init__(self, job_id: str, log_dir: Path):
        self.job_id = job_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"{job_id}.jsonl"
        self._total_cost = 0.0

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append(self, record: dict) -> None:
        with self.path.open("a") as fh:
            fh.write(json.dumps(record))
            fh.write("\n")

    def log_agent(self, agent_name: str, result) -> None:
        cost = float(getattr(result, "cost_usd", 0.0) or 0.0)
        self._total_cost += cost
        self._append({
            "ts": self._now(),
            "job_id": self.job_id,
            "agent": agent_name,
            "input_tokens": int(getattr(result, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(result, "output_tokens", 0) or 0),
            "cost_usd": cost,
            "stop_reason": getattr(result, "stop_reason", None),
        })

    def log_error(self, agent_name: str, error: str) -> None:
        self._append({
            "ts": self._now(),
            "job_id": self.job_id,
            "agent": agent_name,
            "error": error,
        })

    def total_cost_usd(self) -> float:
        return self._total_cost
