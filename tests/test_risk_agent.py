from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.risk import RiskAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=100, output_tokens=200)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    md = ("# Risk & Upside — NVDA\n\n"
          "## Bear case\nAI capex digestion → revenue -25%.\n\n"
          "## Bull case\nNVL system reaccelerates DC.\n\n"
          "**Bear-case PT: $80**\n")
    c = MagicMock()
    c.messages.create = AsyncMock(return_value=FakeMsg(text=md))
    return c


async def test_risk_reads_10k_excerpt_and_writes_section(tmp_path, mock_anthropic):
    td = tmp_path / "NVDA"
    (td / "fundamentals").mkdir(parents=True)
    (td / "fundamentals" / "10k-excerpt.txt").write_text(
        "Item 1A. Risk Factors\nWe face supply chain concentration risk.\n"
    )
    agent = RiskAgent(anthropic_client=mock_anthropic, model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td)

    assert (td / "risk" / "section.md").exists()
    body = (td / "risk" / "section.md").read_text()
    assert "Bear case" in body
    assert "$80" in body


async def test_risk_prompt_includes_risk_factors_text(tmp_path, mock_anthropic):
    td = tmp_path / "NVDA"
    (td / "fundamentals").mkdir(parents=True)
    (td / "fundamentals" / "10k-excerpt.txt").write_text(
        "Item 1A. Risk Factors\nMARKER-RISK-CONTENT\n"
    )
    agent = RiskAgent(anthropic_client=mock_anthropic, model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td)
    prompt = mock_anthropic.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "MARKER-RISK-CONTENT" in prompt


async def test_risk_handles_missing_10k_excerpt(tmp_path, mock_anthropic):
    td = tmp_path / "NVDA"
    td.mkdir()
    agent = RiskAgent(anthropic_client=mock_anthropic, model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td)
    assert (td / "risk" / "section.md").exists()
