import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.observability.semaphore_client import SemaphoredAnthropicClient


async def test_semaphore_caps_concurrent_creates():
    inner = MagicMock()
    in_flight = 0
    max_seen = 0

    async def slow_create(**kwargs):
        nonlocal in_flight, max_seen
        in_flight += 1
        max_seen = max(max_seen, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return MagicMock(content=[MagicMock(type="text", text="ok")],
                         usage=MagicMock(input_tokens=1, output_tokens=1),
                         stop_reason="end_turn")

    inner.messages.create = slow_create
    sem = asyncio.Semaphore(2)
    wrapped = SemaphoredAnthropicClient(inner, sem)

    await asyncio.gather(*(wrapped.messages.create() for _ in range(6)))
    assert max_seen <= 2


async def test_semaphore_passes_through_kwargs():
    inner = MagicMock()
    inner.messages.create = AsyncMock(return_value="result-sentinel")
    wrapped = SemaphoredAnthropicClient(inner, asyncio.Semaphore(5))

    out = await wrapped.messages.create(model="m", system="s",
                                        messages=[{"role": "user", "content": "x"}])
    assert out == "result-sentinel"
    inner.messages.create.assert_awaited_once_with(
        model="m", system="s", messages=[{"role": "user", "content": "x"}]
    )
