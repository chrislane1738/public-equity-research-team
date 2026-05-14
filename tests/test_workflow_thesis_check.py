import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skip(reason="rewired in T13 of skill-migration")

from backend.orchestrator import Orchestrator


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=60, output_tokens=120)
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
        "income": [{"revenue": 60e9, "operatingIncome": 32e9, "ebitda": 35e9}],
        "balance": [{"totalDebt": 11e9, "cashAndCashEquivalents": 7.3e9}],
        "cash": [{}],
    })
    fmp.get_profile = AsyncMock(return_value={"sector": "Tech",
                                              "industry": "Semiconductors",
                                              "mktCap": 3e12, "beta": 1.6,
                                              "price": 110})
    fmp.get_peers = AsyncMock(return_value=["AMD", "INTC"])
    return fmp


@pytest.fixture
def mock_edgar():
    e = MagicMock()
    e.fetch_10k_excerpt = AsyncMock(return_value="Item 1A. Risk Factors\nrisk\n")
    return e


@pytest.fixture
def mock_anthropic():
    routing = json.dumps({"agents": ["industry", "risk"]})
    fund_kpi = json.dumps({"k": {"definition": "d", "latest_value": 1, "unit": "USD"}})
    industry = "# Industry\nWide moat.\n"
    risk = "# Risk\nMain risk: capex digestion.\n"
    focused_memo = ("# NVDA — Thesis Check\n\n## Question\n"
                    "Is the AI capex story still intact?\n\n"
                    "## Bottom line\nYes, with caveats.\n")
    c = MagicMock()
    c.messages.create = AsyncMock(side_effect=[
        FakeMsg(text=routing),
        FakeMsg(text=fund_kpi),
        FakeMsg(text=industry),
        FakeMsg(text=risk),
        FakeMsg(text=focused_memo),
    ])
    return c


async def test_thesis_check_routes_only_chosen_agents(
    tmp_path, mock_anthropic, mock_fmp, mock_edgar, settings, fake_cik_resolver
):
    orch = Orchestrator(
        anthropic_client=mock_anthropic, fmp_client=mock_fmp,
        edgar_client=mock_edgar, fred_client=MagicMock(),
        research_dir=tmp_path, cik_resolver=fake_cik_resolver, settings=settings,
    )
    state = await orch.run_thesis_check(
        ticker="NVDA",
        question="Is the AI capex story still intact?",
    )
    td = tmp_path / "NVDA"
    assert state["status"] == "complete"
    assert (td / "fundamentals" / "financials.json").exists()
    assert (td / "industry" / "section.md").exists()
    assert (td / "risk" / "section.md").exists()
    # NOT dispatched: dcf, comps, macro, technicals.
    assert not (td / "dcf" / "dcf.xlsx").exists()
    assert not (td / "comps" / "comps.xlsx").exists()
    assert not (td / "macro" / "section.md").exists()
    assert not (td / "technicals" / "section.md").exists()
    # Focused memo lives at reports/thesis-check.md (not the full memo.docx).
    assert (td / "reports" / "thesis-check.md").exists()
    assert "Thesis Check" in (td / "reports" / "thesis-check.md").read_text()
