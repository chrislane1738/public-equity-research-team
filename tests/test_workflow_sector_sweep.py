import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.orchestrator import Orchestrator


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=80, output_tokens=120)
        self.stop_reason = "end_turn"


@pytest.fixture
def settings():
    s = MagicMock()
    s.model_for = MagicMock(side_effect=lambda a: "claude-opus-4-7")
    return s


@pytest.fixture
def fake_cik_resolver():
    r = MagicMock()
    r.resolve = AsyncMock(side_effect=lambda t: {
        "NVDA": "0001045810", "AMD": "0000002488",
    }[t.upper()])
    return r


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"revenue": 50e9, "operatingIncome": 20e9, "ebitda": 22e9, "eps": 5.0}],
        "balance": [{"totalDebt": 5e9, "cashAndCashEquivalents": 5e9}],
        "cash": [{}],
    })
    fmp.get_profile = AsyncMock(return_value={"sector": "Technology",
                                              "industry": "Semiconductors",
                                              "mktCap": 1e12, "beta": 1.5,
                                              "price": 100})
    fmp.get_peers = AsyncMock(return_value=["AMD", "INTC"])
    return fmp


@pytest.fixture
def mock_fred():
    f = MagicMock()
    f.get_series = AsyncMock(return_value=[{"date": "2026-05-09", "value": 4.25}])
    return f


@pytest.fixture
def mock_anthropic():
    fund_kpi = json.dumps({"k": {"definition": "d", "latest_value": 1, "unit": "USD"}})
    industry = "# Industry — X\nbody\n"
    comps_md = "# Comps — X\nbody\n"
    macro = "# Macro — X\nbody\n"
    overview = ("# Sector Overview — Technology\n\n"
                "Top picks: NVDA, AMD.\nBottom: TBD.\n")
    c = MagicMock()
    # Per ticker: fundamentals KPI + industry + comps + macro = 4 calls
    # Times 2 tickers = 8, plus 1 sector overview = 9
    c.messages.create = AsyncMock(side_effect=[
        FakeMsg(fund_kpi), FakeMsg(industry), FakeMsg(comps_md), FakeMsg(macro),
        FakeMsg(fund_kpi), FakeMsg(industry), FakeMsg(comps_md), FakeMsg(macro),
        FakeMsg(overview),
    ])
    return c


async def test_sector_sweep_runs_per_ticker_then_writes_overview(
    tmp_path, mock_anthropic, mock_fmp, mock_fred, settings, fake_cik_resolver
):
    edgar = MagicMock()
    edgar.fetch_10k_excerpt = AsyncMock(return_value="Item 1.\nx\n")

    orch = Orchestrator(
        anthropic_client=mock_anthropic, fmp_client=mock_fmp,
        edgar_client=edgar, fred_client=mock_fred,
        research_dir=tmp_path, cik_resolver=fake_cik_resolver, settings=settings,
    )
    state = await orch.run_sector_sweep(tickers=["NVDA", "AMD"])

    for t in ["NVDA", "AMD"]:
        assert (tmp_path / t / "industry" / "section.md").exists()
        assert (tmp_path / t / "comps" / "comps.xlsx").exists()
        assert (tmp_path / t / "macro" / "section.md").exists()
    sector_dir = tmp_path / "_sector" / "technology"
    assert (sector_dir / "sector-overview.md").exists()
    assert state["status"] == "complete"
    assert state["tickers"] == ["NVDA", "AMD"]
