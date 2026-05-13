"""Wraps an Anthropic client so all `messages.create` calls share an asyncio.Semaphore.

The orchestrator constructs the wrapper once (with capacity = MAX_CONCURRENT_AGENTS)
and passes it to every Agent in place of the raw client. Agents see the same
attribute surface they used in Plan A — `client.messages.create(**kwargs)` — so
no agent code changes."""
import asyncio


class _SemaphoredMessages:
    def __init__(self, inner_messages, semaphore: asyncio.Semaphore):
        self._inner = inner_messages
        self._sem = semaphore

    async def create(self, **kwargs):
        async with self._sem:
            return await self._inner.create(**kwargs)


class SemaphoredAnthropicClient:
    def __init__(self, inner_client, semaphore: asyncio.Semaphore):
        self._inner = inner_client
        self.messages = _SemaphoredMessages(inner_client.messages, semaphore)
