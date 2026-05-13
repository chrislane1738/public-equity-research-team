import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.fundamentals import FundamentalsAgent


class FakeMsg:
    def __init__(self, text: str):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=100, output_tokens=50)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"date": "2024-01-28", "revenue": 60_922_000_000, "grossProfit": 44_301_000_000}],
        "balance": [{"date": "2024-01-28", "totalAssets": 65_728_000_000}],
        "cash": [{"date": "2024-01-28", "freeCashFlow": 27_021_000_000}],
    })
    return fmp


@pytest.fixture
def mock_edgar():
    edgar = MagicMock()
    edgar.fetch_10k_excerpt = AsyncMock(return_value="Item 1. Business\nNVIDIA designs GPUs.\n")
    return edgar


@pytest.fixture
def mock_anthropic():
    client = MagicMock()
    kpi_json = json.dumps({
        "data_center_revenue": {
            "definition": "Revenue from Data Center segment",
            "latest_value": 47525000000,
            "unit": "USD",
        },
        "gross_margin": {
            "definition": "Gross profit divided by revenue",
            "latest_value": 0.727,
            "unit": "ratio",
        },
    })
    client.messages.create = AsyncMock(return_value=FakeMsg(text=kpi_json))
    return client


async def test_fundamentals_writes_three_files(tmp_path, mock_fmp, mock_edgar, mock_anthropic):
    agent = FundamentalsAgent(
        anthropic_client=mock_anthropic,
        fmp_client=mock_fmp,
        edgar_client=mock_edgar,
        model="claude-opus-4-7",
    )
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir(parents=True)

    result = await agent.run(ticker="NVDA", cik="0001045810", ticker_dir=ticker_dir)

    fundamentals_dir = ticker_dir / "fundamentals"
    assert (fundamentals_dir / "financials.json").exists()
    assert (fundamentals_dir / "kpis.json").exists()
    assert (fundamentals_dir / "10k-excerpt.txt").exists()
    assert (fundamentals_dir / "section.md").exists()

    kpis = json.loads((fundamentals_dir / "kpis.json").read_text())
    assert "data_center_revenue" in kpis
    assert kpis["gross_margin"]["latest_value"] == 0.727

    assert result.input_tokens == 100


async def test_fundamentals_raises_when_ticker_not_found(tmp_path, mock_edgar, mock_anthropic):
    bad_fmp = MagicMock()
    bad_fmp.get_financials = AsyncMock(side_effect=RuntimeError("FMP not-found"))

    agent = FundamentalsAgent(
        anthropic_client=mock_anthropic,
        fmp_client=bad_fmp,
        edgar_client=mock_edgar,
        model="claude-opus-4-7",
    )
    ticker_dir = tmp_path / "ZZZZ"
    ticker_dir.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="FMP"):
        await agent.run(ticker="ZZZZ", cik="0000000000", ticker_dir=ticker_dir)
