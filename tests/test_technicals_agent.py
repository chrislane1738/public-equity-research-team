from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.technicals import TechnicalsAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=80, output_tokens=150)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    md = ("# Technicals — NVDA\n\nUptrend, RSI 62, suggested stop $95.\n"
          "(Note: this section informs entry timing only; rating is unchanged.)\n")
    c = MagicMock()
    c.messages.create = AsyncMock(return_value=FakeMsg(text=md))
    return c


@pytest.fixture
def mock_fmp():
    f = MagicMock()
    rows = [{"date": f"2026-04-{d:02d}", "close": 100 + d * 0.5,
             "volume": 1_000_000} for d in range(1, 31)]
    f.get_historical_prices = AsyncMock(return_value=rows)
    return f


async def test_technicals_writes_section_and_chart(tmp_path, mock_anthropic, mock_fmp):
    td = tmp_path / "NVDA"
    td.mkdir()
    agent = TechnicalsAgent(anthropic_client=mock_anthropic, fmp_client=mock_fmp,
                            model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td)

    assert (td / "technicals" / "price-chart.png").exists()
    assert (td / "technicals" / "section.md").exists()
    body = (td / "technicals" / "section.md").read_text()
    assert "Technicals" in body


async def test_technicals_section_includes_rating_disclaimer_in_prompt(
    tmp_path, mock_anthropic, mock_fmp
):
    td = tmp_path / "NVDA"
    td.mkdir()
    agent = TechnicalsAgent(anthropic_client=mock_anthropic, fmp_client=mock_fmp,
                            model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td)
    sys_prompt = mock_anthropic.messages.create.call_args.kwargs["system"]
    assert "rating" in sys_prompt.lower()
    assert "timing" in sys_prompt.lower()
