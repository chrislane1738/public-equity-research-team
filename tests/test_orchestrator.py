import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.orchestrator import Orchestrator


class FakeMsg:
    def __init__(self, text: str):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=100, output_tokens=100)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    client = MagicMock()
    # The MD synthesis and Memo Builder responses will be returned in order
    client.messages.create = AsyncMock(side_effect=[
        FakeMsg(text='{"kpi_one":{"definition":"d","latest_value":1,"unit":"USD"}}'),  # Fundamentals KPI
        FakeMsg(text="# Synthesis\n**Rating:** Buy\n**PT:** $100\n"),                  # MD synthesis
        FakeMsg(text="# Memo\n## Executive Summary\nBuy.\n## Risks\nx\n"),             # Memo Builder
    ])
    return client


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"revenue": 1000}],
        "balance": [{"totalAssets": 2000}],
        "cash": [{"freeCashFlow": 100}],
    })
    return fmp


@pytest.fixture
def mock_edgar():
    edgar = MagicMock()
    edgar.fetch_10k_excerpt = AsyncMock(return_value="Item 1. Business\nbody\n")
    return edgar


@pytest.fixture
def fake_cik_resolver():
    r = MagicMock()
    r.resolve = AsyncMock(return_value="0001045810")
    return r


async def test_run_full_deep_dive_produces_all_artifacts(
    tmp_path, mock_anthropic, mock_fmp, mock_edgar, fake_cik_resolver
):
    orch = Orchestrator(
        anthropic_client=mock_anthropic,
        fmp_client=mock_fmp,
        edgar_client=mock_edgar,
        research_dir=tmp_path,
        cik_resolver=fake_cik_resolver,
        opus_model="claude-opus-4-7",
        sonnet_model="claude-sonnet-4-6",
    )

    state = await orch.run_full_deep_dive(ticker="NVDA")

    ticker_dir = tmp_path / "NVDA"
    assert (ticker_dir / "fundamentals" / "financials.json").exists()
    assert (ticker_dir / "fundamentals" / "kpis.json").exists()
    for name in ["industry", "dcf", "comps", "macro", "risk", "technicals"]:
        assert (ticker_dir / name / "section.md").exists()
    assert (ticker_dir / "synthesis" / "_synthesis.md").exists()
    assert (ticker_dir / "reports" / "memo.docx").exists()
    assert state["status"] == "complete"
    assert state["rating"] == "Buy"


async def test_run_extracts_rating_from_synthesis(
    tmp_path, mock_fmp, mock_edgar, fake_cik_resolver
):
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=[
        FakeMsg(text='{}'),
        FakeMsg(text="# Synthesis\n**Rating:** Hold\n**PT:** $50\n"),
        FakeMsg(text="# Memo\n## Executive Summary\nHold.\n"),
    ])

    orch = Orchestrator(
        anthropic_client=client,
        fmp_client=mock_fmp,
        edgar_client=mock_edgar,
        research_dir=tmp_path,
        cik_resolver=fake_cik_resolver,
        opus_model="claude-opus-4-7",
        sonnet_model="claude-sonnet-4-6",
    )
    state = await orch.run_full_deep_dive(ticker="NVDA")
    assert state["rating"] == "Hold"
