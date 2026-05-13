import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.orchestrator import Orchestrator


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=100, output_tokens=100)
        self.stop_reason = "end_turn"


@pytest.fixture
def settings():
    s = MagicMock()
    s.model_for = MagicMock(side_effect=lambda agent: "claude-opus-4-7")
    return s


@pytest.fixture
def fake_cik_resolver():
    r = MagicMock()
    r.resolve = AsyncMock(return_value="0001045810")
    return r


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"revenue": 60_000_000_000, "operatingIncome": 32_000_000_000,
                    "ebitda": 35_000_000_000, "eps": 11.93}],
        "balance": [{"totalDebt": 11_000_000_000,
                     "cashAndCashEquivalents": 7_300_000_000}],
        "cash": [{"freeCashFlow": 27_000_000_000}],
    })
    fmp.get_profile = AsyncMock(return_value={
        "sector": "Technology", "industry": "Semiconductors",
        "mktCap": 3_000_000_000_000, "beta": 1.6, "price": 110.0,
    })
    fmp.get_quote = AsyncMock(return_value={"price": 110.0,
                                            "sharesOutstanding": 2.5e9,
                                            "yearHigh": 1200, "yearLow": 400})
    fmp.get_peers = AsyncMock(return_value=["AMD", "INTC"])
    rows = [{"date": f"2026-04-{d:02d}", "close": 100 + d * 0.5,
             "volume": 1_000_000} for d in range(1, 31)]
    fmp.get_historical_prices = AsyncMock(return_value=rows)
    fmp.get_10y_treasury_rate = AsyncMock(return_value=4.25)
    return fmp


@pytest.fixture
def mock_edgar():
    e = MagicMock()
    e.fetch_10k_excerpt = AsyncMock(return_value=(
        "Item 1. Business\nNVIDIA designs GPUs.\n"
        "Item 1A. Risk Factors\nSupply chain concentration.\n"
        "Item 7. MD&A\nRevenue grew.\n"))
    return e


@pytest.fixture
def mock_fred():
    f = MagicMock()
    f.get_series = AsyncMock(return_value=[{"date": "2026-05-09", "value": 4.25}])
    return f


@pytest.fixture
def mock_anthropic():
    """Generic responder — every call returns innocuous text or JSON the agents accept."""
    c = MagicMock()
    fund_kpi = json.dumps({"kpi_a": {"definition": "d", "latest_value": 1, "unit": "USD"}})
    industry = "# Industry & Moat — NVDA\nWide moat.\n"
    comps_md = "# Comps — NVDA\nIn line with peers.\n"
    dcf_assumptions = json.dumps({
        "growth_path": [0.10, 0.10, 0.10, 0.10, 0.10],
        "ebit_margin_path": [0.30, 0.30, 0.30, 0.30, 0.30],
        "tax_rate": 0.21, "da_pct_revenue": 0.05,
        "capex_pct_revenue": 0.07, "wc_change_pct_revenue": 0.01,
        "terminal_growth_pct": 2.5, "blend_weight_ggm": 0.5,
        "weight_equity": 0.95, "weight_debt": 0.05, "cost_of_debt_pct": 5.0,
    })
    dcf_section = "# DCF — NVDA\nBlended PT $158.\n"
    macro = "# Macro — NVDA\nGoldilocks.\n"
    risk = "# Risk & Upside — NVDA\nBear case.\n**Bear-case PT: $80**\n"
    tech = "# Technicals — NVDA\nUptrend.\n"
    synthesis = "# Synthesis\n**Rating:** Buy\n**PT:** $158\n"
    memo = "# NVDA Memo\n## Executive Summary\nBuy.\n"

    c.messages.create = AsyncMock(side_effect=[
        FakeMsg(text=fund_kpi),
        FakeMsg(text=industry),
        FakeMsg(text=comps_md),
        FakeMsg(text=macro),
        FakeMsg(text=risk),
        FakeMsg(text=tech),
        FakeMsg(text=dcf_assumptions),
        FakeMsg(text=dcf_section),
        FakeMsg(text=synthesis),
        FakeMsg(text=memo),
    ])
    return c


async def test_full_deep_dive_dispatches_real_agents(
    tmp_path, mock_anthropic, mock_fmp, mock_edgar, mock_fred,
    settings, fake_cik_resolver,
):
    orch = Orchestrator(
        anthropic_client=mock_anthropic, fmp_client=mock_fmp,
        edgar_client=mock_edgar, fred_client=mock_fred,
        research_dir=tmp_path, cik_resolver=fake_cik_resolver, settings=settings,
    )
    state = await orch.run_full_deep_dive(ticker="NVDA")

    td = tmp_path / "NVDA"
    assert (td / "fundamentals" / "financials.json").exists()
    assert (td / "industry" / "section.md").exists()
    assert (td / "comps" / "peer-multiples.json").exists()
    assert (td / "comps" / "comps.xlsx").exists()
    assert (td / "dcf" / "dcf.xlsx").exists()
    assert (td / "macro" / "section.md").exists()
    assert (td / "risk" / "section.md").exists()
    assert (td / "technicals" / "section.md").exists()
    assert (td / "synthesis" / "_synthesis.md").exists()
    assert (td / "reports" / "memo.docx").exists()
    assert state["status"] == "complete"
    assert state["rating"] == "Buy"
    assert state["stages"]["dcf"] == "complete"
