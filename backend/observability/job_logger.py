"""Per-job JSONL telemetry. One line per logged event.

Plan C: also publishes each event to a JobEventBus when one is supplied,
so WebSocket subscribers can receive live updates.
"""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.observability.event_bus import JobEventBus


class JobLogger:
    def __init__(self, job_id: str, log_dir: Path,
                 event_bus: Optional[JobEventBus] = None):
        self.job_id = job_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"{job_id}.jsonl"
        self._total_cost = 0.0
        self._bus = event_bus

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append(self, record: dict) -> None:
        with self.path.open("a") as fh:
            fh.write(json.dumps(record))
            fh.write("\n")
        if self._bus is not None:
            self._publish(record)

    def _publish(self, record: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._bus.publish(self.job_id, record))

    def log_agent(self, agent_name: str, result) -> None:
        cost = float(getattr(result, "cost_usd", 0.0) or 0.0)
        self._total_cost += cost
        self._append({
            "ts": self._now(),
            "type": "agent_completed",
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
            "type": "agent_failed",
            "job_id": self.job_id,
            "agent": agent_name,
            "error": error,
        })

    def log_stage(self, stage: str, status: str) -> None:
        """Emit a stage transition (e.g. 'stage_2a' -> 'started')."""
        self._append({
            "ts": self._now(),
            "type": "stage",
            "job_id": self.job_id,
            "stage": stage,
            "status": status,
        })

    def total_cost_usd(self) -> float:
        return self._total_cost
