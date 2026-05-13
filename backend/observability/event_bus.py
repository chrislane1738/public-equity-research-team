"""In-process pub/sub for job events. One bus instance per backend process."""
import asyncio
from typing import Any


class JobEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        subs = self._subscribers.get(job_id)
        if not subs:
            return
        if q in subs:
            subs.remove(q)
        if not subs:
            self._subscribers.pop(job_id, None)

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        for q in list(self._subscribers.get(job_id, [])):
            await q.put(event)
