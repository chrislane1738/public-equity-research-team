from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.md import MDAgent


class FakeMsg:
    def __init__(self, text: str):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=200, output_tokens=300)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    synthesis_md = (
        "# Synthesis — NVDA\n"
        "**Rating:** Buy\n"
        "**Price Target:** $1,200\n\n"
        "## Triangulation\n"
        "- DCF (Blended): $1,150 — weight 50%\n"
        "- Comps median: $1,250 — weight 50%\n"
        "- Final PT: $1,200\n\n"
        "## Application logic\nDCF leads on long-term thesis...\n"
    )
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=FakeMsg(text=synthesis_md))
    return client


async def test_md_synthesis_reads_sections_and_writes_synthesis(tmp_path, mock_anthropic):
    ticker_dir = tmp_path / "NVDA"
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        (ticker_dir / sub).mkdir(parents=True)
        (ticker_dir / sub / "section.md").write_text(f"# {sub.title()}\nStub content.\n")

    agent = MDAgent(anthropic_client=mock_anthropic, model="claude-opus-4-7")
    result = await agent.synthesize(ticker="NVDA", ticker_dir=ticker_dir)

    synthesis_path = ticker_dir / "synthesis" / "_synthesis.md"
    assert synthesis_path.exists()
    body = synthesis_path.read_text()
    assert "Rating" in body
    assert "Buy" in body
    assert "$1,200" in body
    assert result.input_tokens == 200


async def test_md_synthesis_prompt_includes_all_section_bodies(tmp_path, mock_anthropic):
    ticker_dir = tmp_path / "NVDA"
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        (ticker_dir / sub).mkdir(parents=True)
        (ticker_dir / sub / "section.md").write_text(
            f"# {sub.title()}\nUnique-{sub}-content\n"
        )

    agent = MDAgent(anthropic_client=mock_anthropic, model="claude-opus-4-7")
    await agent.synthesize(ticker="NVDA", ticker_dir=ticker_dir)

    call_kwargs = mock_anthropic.messages.create.call_args.kwargs
    user_prompt = call_kwargs["messages"][0]["content"]
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        assert f"Unique-{sub}-content" in user_prompt
