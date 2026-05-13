import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.dcf import DCFAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=200, output_tokens=400)
        self.stop_reason = "end_turn"


@pytest.fixture
def mock_anthropic():
    """LLM returns assumption JSON for the deterministic engine, then prose section."""
    assumptions = json.dumps({
        "growth_path": [0.20, 0.15, 0.10, 0.08, 0.05],
        "ebit_margin_path": [0.40, 0.40, 0.40, 0.40, 0.40],
        "tax_rate": 0.21,
        "da_pct_revenue": 0.05,
        "capex_pct_revenue": 0.07,
        "wc_change_pct_revenue": 0.01,
        "terminal_growth_pct": 2.5,
        "blend_weight_ggm": 0.5,
        "weight_equity": 0.95,
        "weight_debt": 0.05,
        "cost_of_debt_pct": 5.0,
    })
    section = "# DCF — NVDA\n\nWACC 10.5%, terminal g 2.5%, blended PT $158.\n"
    c = MagicMock()
    c.messages.create = AsyncMock(side_effect=[
        FakeMsg(text=assumptions),
        FakeMsg(text=section),
    ])
    return c


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_profile = AsyncMock(return_value={"beta": 1.6, "sector": "Technology"})
    fmp.get_quote = AsyncMock(return_value={"price": 110.0, "sharesOutstanding": 2.5e9})
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"revenue": 60_000_000_000, "operatingIncome": 32_000_000_000,
                    "ebitda": 35_000_000_000}],
        "balance": [{"totalDebt": 11_000_000_000, "cashAndCashEquivalents": 7_300_000_000}],
        "cash": [{}],
    })
    fmp.get_10y_treasury_rate = AsyncMock(return_value=4.25)
    return fmp


@pytest.fixture
def ticker_dir_with_peer_multiples(tmp_path):
    td = tmp_path / "NVDA"
    (td / "comps").mkdir(parents=True)
    (td / "comps" / "peer-multiples.json").write_text(json.dumps({
        "ev_to_ebitda": {"median": 22.0, "p25": 18.0, "p75": 26.0, "n": 5},
        "pe": {"median": 35.0, "p25": 28.0, "p75": 45.0, "n": 5},
        "ev_to_sales": {"median": 9.0, "p25": 6.0, "p75": 12.0, "n": 5},
    }))
    return td


async def test_dcf_writes_xlsx_and_charts_and_section(tmp_path, mock_anthropic,
                                                     mock_fmp,
                                                     ticker_dir_with_peer_multiples):
    td = ticker_dir_with_peer_multiples
    agent = DCFAgent(anthropic_client=mock_anthropic, fmp_client=mock_fmp,
                     model="claude-opus-4-7")
    result = await agent.run(ticker="NVDA", ticker_dir=td)

    assert (td / "dcf" / "dcf.xlsx").exists()
    assert (td / "dcf" / "football-field.png").exists()
    assert (td / "dcf" / "sensitivity.png").exists()
    assert (td / "dcf" / "section.md").exists()
    assert "DCF" in (td / "dcf" / "section.md").read_text()
    assert result.input_tokens > 0


async def test_dcf_uses_peer_median_for_exit_multiple(tmp_path, mock_anthropic,
                                                     mock_fmp,
                                                     ticker_dir_with_peer_multiples):
    td = ticker_dir_with_peer_multiples
    agent = DCFAgent(anthropic_client=mock_anthropic, fmp_client=mock_fmp,
                     model="claude-opus-4-7")
    await agent.run(ticker="NVDA", ticker_dir=td)
    # The prose-call prompt should reference the multiple it actually applied
    prose_prompt = mock_anthropic.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
    # peer median 22 * haircut 0.85 = 18.7
    assert "18.7" in prose_prompt or "18.70" in prose_prompt or "applied multiple" in prose_prompt.lower()
