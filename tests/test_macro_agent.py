from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.macro import MacroAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=80, output_tokens=200)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    md = "# Macro — NVDA\n\n10Y at 4.25%, CPI cooling. Goldilocks for high-multiple growth.\n"
    c = MagicMock()
    c.messages.create = AsyncMock(return_value=FakeMsg(text=md))
    return c


@pytest.fixture
def mock_fred():
    f = MagicMock()
    f.get_series = AsyncMock(side_effect=lambda series_id, limit=12: {
        "DGS10":     [{"date": "2026-05-09", "value": 4.25}],
        "CPIAUCSL":  [{"date": "2026-04-01", "value": 320.5}],
        "UNRATE":    [{"date": "2026-04-01", "value": 4.0}],
    }[series_id])
    return f


async def test_macro_writes_section_and_timeline(tmp_path, mock_anthropic, mock_fred):
    td = tmp_path / "NVDA"
    td.mkdir()
    agent = MacroAgent(anthropic_client=mock_anthropic, fred_client=mock_fred,
                       model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td,
                    catalysts=[("2026-05-22", "Q1 earnings"),
                               ("2026-06-15", "FOMC meeting")])

    assert (td / "macro" / "section.md").exists()
    assert (td / "macro" / "catalyst-timeline.png").exists()
    assert "Macro" in (td / "macro" / "section.md").read_text()


async def test_macro_prompt_includes_dgs10_and_cpi(tmp_path, mock_anthropic, mock_fred):
    td = tmp_path / "NVDA"
    td.mkdir()
    agent = MacroAgent(anthropic_client=mock_anthropic, fred_client=mock_fred,
                       model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=td, catalysts=[])
    prompt = mock_anthropic.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "DGS10" in prompt
    assert "CPIAUCSL" in prompt
