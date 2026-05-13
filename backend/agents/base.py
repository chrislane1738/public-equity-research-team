"""Base Agent class wrapping the Anthropic SDK."""
from dataclasses import dataclass, field
from typing import Any, Optional


# Token prices (USD per 1M tokens) for claude-opus-4-7. Sonnet is cheaper.
# These are placeholders for cost tracking — update in Plan B when finalized.
PRICE_PER_M_INPUT = {
    "claude-opus-4-7": 15.0,
    "claude-sonnet-4-6": 3.0,
    "claude-haiku-4-5-20251001": 0.80,
}
PRICE_PER_M_OUTPUT = {
    "claude-opus-4-7": 75.0,
    "claude-sonnet-4-6": 15.0,
    "claude-haiku-4-5-20251001": 4.0,
}


@dataclass
class AgentResult:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    stop_reason: Optional[str] = None


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in = PRICE_PER_M_INPUT.get(model, 0.0) / 1_000_000
    p_out = PRICE_PER_M_OUTPUT.get(model, 0.0) / 1_000_000
    return input_tokens * p_in + output_tokens * p_out


class Agent:
    """Thin Anthropic SDK wrapper with a system prompt, tools, and a non-streaming run()."""

    def __init__(
        self,
        name: str,
        system_prompt: str,
        model: str,
        anthropic_client,
        tools: Optional[list[dict[str, Any]]] = None,
        max_tokens: int = 4096,
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.client = anthropic_client
        self.tools = tools or []
        self.max_tokens = max_tokens

    async def run(self, prompt: str) -> AgentResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.tools:
            kwargs["tools"] = self.tools

        msg = await self.client.messages.create(**kwargs)

        text_blocks = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        tool_blocks = [
            {"name": b.name, "input": b.input, "id": b.id}
            for b in msg.content
            if getattr(b, "type", None) == "tool_use"
        ]
        content = "".join(text_blocks)

        return AgentResult(
            content=content,
            tool_calls=tool_blocks,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            cost_usd=_compute_cost(self.model, msg.usage.input_tokens, msg.usage.output_tokens),
            stop_reason=msg.stop_reason,
        )
