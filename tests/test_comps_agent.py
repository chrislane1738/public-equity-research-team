import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.agents.comps import CompsAgent


class FakeMsg:
    def __init__(self, text):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=120, output_tokens=200)
        self.stop_reason = "end_turn"


def _peer_profile(symbol, mc, debt, cash):
    return {"symbol": symbol, "mktCap": mc, "totalDebt": debt,
            "cashAndCashEquivalents": cash, "price": 100.0}


def _peer_income(rev, ebitda, eps):
    return [{"revenue": rev, "ebitda": ebitda, "eps": eps}]


@pytest.fixture
def mock_anthropic():
    md = ("# Comps — NVDA\n\nPeers trade at 30x EV/EBITDA median; NVDA at 45x is a "
          "premium to AMD (30x) but justified by margin profile.\n")
    c = MagicMock()
    c.messages.create = AsyncMock(return_value=FakeMsg(text=md))
    return c


@pytest.fixture
def mock_fmp():
    fmp = MagicMock()
    fmp.get_peers = AsyncMock(return_value=["AMD", "INTC"])

    profiles = {
        "NVDA": _peer_profile("NVDA", 3e12, 11e9, 7.3e9),
        "AMD":  _peer_profile("AMD",  250e9, 3e9, 6e9),
        "INTC": _peer_profile("INTC", 150e9, 50e9, 25e9),
    }
    incomes = {
        "NVDA": {"income": _peer_income(60e9, 35e9, 11.93),
                 "balance": [{"totalDebt": 11e9, "cashAndCashEquivalents": 7.3e9}],
                 "cash": [{}]},
        "AMD":  {"income": _peer_income(23e9, 5e9, 4.0),
                 "balance": [{"totalDebt": 3e9, "cashAndCashEquivalents": 6e9}],
                 "cash": [{}]},
        "INTC": {"income": _peer_income(54e9, 12e9, 1.4),
                 "balance": [{"totalDebt": 50e9, "cashAndCashEquivalents": 25e9}],
                 "cash": [{}]},
    }
    fmp.get_profile = AsyncMock(side_effect=lambda t: profiles[t.upper()])
    fmp.get_financials = AsyncMock(side_effect=lambda t: incomes[t.upper()])
    return fmp


async def test_comps_writes_peer_multiples_and_comps_xlsx(tmp_path, mock_anthropic, mock_fmp):
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir()

    agent = CompsAgent(anthropic_client=mock_anthropic, fmp_client=mock_fmp,
                       model="claude-opus-4-7")
    await agent.run(ticker="NVDA", ticker_dir=ticker_dir)

    pm_path = ticker_dir / "comps" / "peer-multiples.json"
    assert pm_path.exists()
    pm = json.loads(pm_path.read_text())
    assert "ev_to_ebitda" in pm
    assert "median" in pm["ev_to_ebitda"]
    assert (ticker_dir / "comps" / "comps.xlsx").exists()
    assert (ticker_dir / "comps" / "box-plot.png").exists()
    assert (ticker_dir / "comps" / "section.md").exists()


async def test_comps_prompt_includes_peer_records_and_aggregate(tmp_path,
                                                                mock_anthropic, mock_fmp):
    ticker_dir = tmp_path / "NVDA"
    ticker_dir.mkdir()
    agent = CompsAgent(anthropic_client=mock_anthropic, fmp_client=mock_fmp,
                       model="claude-opus-4-7")
    await agent.run(ticker="NVDA", ticker_dir=ticker_dir)

    prompt = mock_anthropic.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "peer_records" in prompt
    assert "aggregate" in prompt
    assert '"NVDA"' in prompt
    assert '"AMD"' in prompt
    assert '"INTC"' in prompt
    # The aggregate summary's median key should appear in the prompt body too.
    assert "median" in prompt
