from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from docx import Document

from backend.agents.memo_builder import MemoBuilderAgent


class FakeMsg:
    def __init__(self, text: str):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=150, output_tokens=400)
        self.stop_reason = "end_turn"


MEMO_MD = """# NVDA — Initiation

## Executive Summary

We rate NVDA Buy with a $1,200 PT.

## Investment Thesis

Three reasons we like the name.

## Risks

Top risk is AI capex pullback.
"""


@pytest.fixture
def mock_anthropic():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=FakeMsg(text=MEMO_MD))
    return client


async def test_memo_builder_writes_docx(tmp_path, mock_anthropic):
    ticker_dir = tmp_path / "NVDA"
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        (ticker_dir / sub).mkdir(parents=True)
        (ticker_dir / sub / "section.md").write_text(f"# {sub}\nstub\n")
    (ticker_dir / "synthesis").mkdir()
    (ticker_dir / "synthesis" / "_synthesis.md").write_text("# Synthesis\nBuy. $1,200 PT.\n")

    agent = MemoBuilderAgent(anthropic_client=mock_anthropic, model="claude-sonnet-4-6")
    result = await agent.run(ticker="NVDA", ticker_dir=ticker_dir, rating="Buy")

    memo_path = ticker_dir / "reports" / "memo.docx"
    assert memo_path.exists()
    doc = Document(memo_path)
    paragraphs = [p.text for p in doc.paragraphs]
    assert any("Executive Summary" in p for p in paragraphs)
    assert any("We rate NVDA Buy" in p for p in paragraphs)
    assert result.input_tokens == 150


async def test_memo_builder_prompt_includes_synthesis_and_sections(tmp_path, mock_anthropic):
    ticker_dir = tmp_path / "NVDA"
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        (ticker_dir / sub).mkdir(parents=True)
        (ticker_dir / sub / "section.md").write_text(f"unique-{sub}-marker")
    (ticker_dir / "synthesis").mkdir()
    (ticker_dir / "synthesis" / "_synthesis.md").write_text("unique-synthesis-marker")

    agent = MemoBuilderAgent(anthropic_client=mock_anthropic, model="claude-sonnet-4-6")
    await agent.run(ticker="NVDA", ticker_dir=ticker_dir, rating="Buy")

    user_prompt = mock_anthropic.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "unique-synthesis-marker" in user_prompt
    for sub in ["fundamentals", "industry", "dcf", "comps", "macro", "risk", "technicals"]:
        assert f"unique-{sub}-marker" in user_prompt
