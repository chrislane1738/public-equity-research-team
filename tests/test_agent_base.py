from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.base import Agent, AgentResult


class FakeAnthropicMessage:
    def __init__(self, text: str, input_tokens: int = 100, output_tokens: int = 50):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic_client():
    client = MagicMock()
    client.messages.create = AsyncMock(
        return_value=FakeAnthropicMessage(text="hello from the test")
    )
    return client


async def test_agent_run_returns_assistant_text(mock_anthropic_client):
    agent = Agent(
        name="test-agent",
        system_prompt="You are a test agent.",
        model="claude-opus-4-7",
        anthropic_client=mock_anthropic_client,
        tools=[],
    )
    result = await agent.run(prompt="hi")

    assert isinstance(result, AgentResult)
    assert result.content == "hello from the test"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    assert result.cost_usd > 0


async def test_agent_run_passes_system_prompt_and_model(mock_anthropic_client):
    agent = Agent(
        name="test-agent",
        system_prompt="You are a test agent.",
        model="claude-opus-4-7",
        anthropic_client=mock_anthropic_client,
        tools=[],
    )
    await agent.run(prompt="hi")

    call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-7"
    assert call_kwargs["system"] == "You are a test agent."
    assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]
