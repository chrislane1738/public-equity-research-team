from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.industry import IndustryAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=120, output_tokens=300)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    text = (
        "# Industry & Moat — NVDA\n\n"
        "## Porter's 5 forces\n- Rivalry: high vs AMD/INTC.\n\n"
        "## Moat verdict\nWide — CUDA ecosystem lock-in.\n"
    )
    c = MagicMock()
    c.messages.create = AsyncMock(return_value=FakeMsg(text=text))
    return c


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_profile = AsyncMock(return_value={"sector": "Technology",
                                                "industry": "Semiconductors",
                                                "mktCap": 3e12})
    fmp.get_peers = AsyncMock(return_value=["AMD", "INTC", "AVGO"])
    return fmp


async def test_industry_writes_section_md(tmp_path, mock_anthropic, mock_fmp):
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir()
    agent = IndustryAgent(anthropic_client=mock_anthropic,
                          fmp_client=mock_fmp,
                          model="claude-opus-4-7")
    result = await agent.run(ticker="NVDA", ticker_dir=ticker_dir)

    section = ticker_dir / "industry" / "section.md"
    assert section.exists()
    body = section.read_text()
    assert "Industry & Moat" in body
    assert "CUDA" in body
    assert result.input_tokens == 120


async def test_industry_prompt_includes_sector_and_peers(tmp_path,
                                                         mock_anthropic, mock_fmp):
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir()
    agent = IndustryAgent(anthropic_client=mock_anthropic,
                          fmp_client=mock_fmp, model="claude-opus-4-7")
    await agent.run(ticker="NVDA", ticker_dir=ticker_dir)

    prompt = mock_anthropic.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Semiconductors" in prompt
    assert "AMD" in prompt
    assert "AVGO" in prompt
