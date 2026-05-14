import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skip(reason="rewired in T13 of skill-migration")

from backend.orchestrator import Orchestrator


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=50, output_tokens=50)
        self.stop_reason = "end_turn"


@pytest.fixture
def settings():
    s = MagicMock()
    s.model_for = MagicMock(side_effect=lambda a: "claude-opus-4-7")
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
        "income": [{"revenue": 70_000_000_000, "operatingIncome": 35_000_000_000,
                    "ebitda": 38_000_000_000, "eps": 13.50}],
        "balance": [{"totalDebt": 11_000_000_000,
                     "cashAndCashEquivalents": 8_000_000_000}],
        "cash": [{}],
    })
    fmp.get_profile = AsyncMock(return_value={"beta": 1.6, "sector": "Tech"})
    fmp.get_quote = AsyncMock(return_value={"price": 130.0, "sharesOutstanding": 2.5e9})
    fmp.get_peers = AsyncMock(return_value=["AMD"])
    fmp.get_10y_treasury_rate = AsyncMock(return_value=4.25)
    return fmp


@pytest.fixture
def mock_edgar():
    e = MagicMock()
    e.fetch_10k_excerpt = AsyncMock(return_value="Item 1A. Risk Factors\nx\n")
    return e


@pytest.fixture
def mock_anthropic():
    fund_kpi = json.dumps({"k": {"definition": "d", "latest_value": 1, "unit": "USD"}})
    dcf_assumptions = json.dumps({
        "growth_path": [0.10] * 5, "ebit_margin_path": [0.40] * 5,
        "tax_rate": 0.21, "da_pct_revenue": 0.05, "capex_pct_revenue": 0.07,
        "wc_change_pct_revenue": 0.01, "terminal_growth_pct": 2.5,
        "blend_weight_ggm": 0.5, "weight_equity": 0.95, "weight_debt": 0.05,
        "cost_of_debt_pct": 5.0,
    })
    c = MagicMock()
    c.messages.create = AsyncMock(side_effect=[
        FakeMsg(text=fund_kpi),                                    # Fundamentals
        FakeMsg(text=dcf_assumptions),                              # DCF assumptions
        FakeMsg(text="# DCF — NVDA\nUpdated PT $172.\n"),           # DCF prose
        FakeMsg(text="# Risk\nUpdated bear case.\n"),               # Risk
        FakeMsg(text="# Synthesis\n**Rating:** Buy\n**PT:** $172\n"),  # MD synth
        FakeMsg(text="# Memo\n## Executive Summary\nUpdated.\n"),    # Memo
    ])
    return c


async def test_earnings_update_runs_only_fund_dcf_risk_md_memo(
    tmp_path, mock_anthropic, mock_fmp, mock_edgar, settings, fake_cik_resolver
):
    # Pre-seed Comps peer-multiples.json so DCF can read it (Earnings Update
    # doesn't re-run Comps).
    td = tmp_path / "NVDA"
    (td / "comps").mkdir(parents=True)
    (td / "comps" / "peer-multiples.json").write_text(json.dumps({
        "ev_to_ebitda": {"median": 22, "p25": 18, "p75": 26, "n": 5},
    }))

    orch = Orchestrator(
        anthropic_client=mock_anthropic, fmp_client=mock_fmp,
        edgar_client=mock_edgar, fred_client=MagicMock(),
        research_dir=tmp_path, cik_resolver=fake_cik_resolver, settings=settings,
    )
    state = await orch.run_earnings_update(ticker="NVDA")

    assert state["status"] == "complete"
    assert (td / "fundamentals" / "financials.json").exists()
    assert (td / "dcf" / "dcf.xlsx").exists()
    assert (td / "risk" / "section.md").exists()
    assert (td / "synthesis" / "_synthesis.md").exists()
    assert (td / "reports" / "memo.docx").exists()
    # Earnings Update produces NO deck/onepager.
    assert not (td / "reports" / "pitch.pptx").exists()
    assert not (td / "reports" / "onepager.pdf").exists()
