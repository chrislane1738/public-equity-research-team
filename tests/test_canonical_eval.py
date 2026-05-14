import json
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.skip(reason="rewired in T16 of skill-migration")

from backend.orchestrator import Orchestrator
from tests.conftest_canonical import (build_fixture_edgar, build_fixture_fmp,
                                       build_fixture_fred, load)


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
    r.resolve = AsyncMock(side_effect=lambda t: load(t.upper(), "profile.json")["cik"].zfill(10))
    return r


def _make_responder():
    """Return an AsyncMock returning sensible canned text for every agent in the
    full-deep-dive pipeline (11 calls including deck builder)."""
    fund_kpi = json.dumps({"k": {"definition": "d", "latest_value": 1, "unit": "USD"}})
    industry = "# Industry\nWide moat.\n"
    comps_md = "# Comps\nIn line with peers.\n"
    dcf_assumptions = json.dumps({
        "growth_path": [0.10] * 5, "ebit_margin_path": [0.30] * 5,
        "tax_rate": 0.21, "da_pct_revenue": 0.05, "capex_pct_revenue": 0.07,
        "wc_change_pct_revenue": 0.01, "terminal_growth_pct": 2.5,
        "blend_weight_ggm": 0.5, "weight_equity": 0.95, "weight_debt": 0.05,
        "cost_of_debt_pct": 5.0,
    })
    dcf_section = "# DCF\nBlended PT $X.\n"
    macro = "# Macro\nNeutral.\n"
    risk = "# Risk\nBear.\n**Bear-case PT: $80**\n"
    tech = "# Technicals\nUptrend.\n"
    synthesis = "# Synthesis\n**Rating:** Buy\n**PT:** $150\n"
    memo = "# Memo\n## Executive Summary\nBuy.\n"
    deck_pack = json.dumps({
        "thesis_bullets": ["a", "b", "c"],
        "triangulation_rows": [["DCF Blend", 150, 0.5], ["Comps", 145, 0.5]],
        "top_risks": ["x", "y", "z"],
        "slide_bodies": {t: f"Body for {t}" for t in [
            "Investment Thesis", "Business Snapshot", "Industry & Moat",
            "Bespoke KPIs", "Financial Performance", "Forecast", "DCF",
            "Comps", "Valuation Triangulation", "Catalysts",
            "Risks / Bear Case", "Technical Setup", "Recommendation"]},
    })

    c = MagicMock()
    c.messages.create = AsyncMock(side_effect=[
        FakeMsg(fund_kpi),                               # Fundamentals
        FakeMsg(industry), FakeMsg(comps_md),
        FakeMsg(macro), FakeMsg(risk), FakeMsg(tech),
        FakeMsg(dcf_assumptions), FakeMsg(dcf_section),  # DCF (2 calls)
        FakeMsg(synthesis),                              # MD synth
        FakeMsg(memo), FakeMsg(deck_pack),               # Stage 4
    ])
    return c


@pytest.mark.parametrize("ticker", ["NVDA", "AAPL", "JPM", "XOM"])
async def test_full_deep_dive_runs_against_canonical_fixture(
    tmp_path, ticker, settings, fake_cik_resolver
):
    orch = Orchestrator(
        anthropic_client=_make_responder(),
        fmp_client=build_fixture_fmp(ticker),
        edgar_client=build_fixture_edgar(ticker),
        fred_client=build_fixture_fred(ticker),
        research_dir=tmp_path,
        cik_resolver=fake_cik_resolver,
        settings=settings,
    )
    state = await orch.run_full_deep_dive(ticker=ticker)

    assert state["status"] == "complete", f"{ticker}: {state}"
    td = tmp_path / ticker
    assert (td / "fundamentals" / "financials.json").exists()
    assert (td / "industry" / "section.md").exists()
    assert (td / "comps" / "comps.xlsx").exists()
    assert (td / "dcf" / "dcf.xlsx").exists()
    assert (td / "macro" / "section.md").exists()
    assert (td / "risk" / "section.md").exists()
    assert (td / "technicals" / "section.md").exists()
    assert (td / "synthesis" / "_synthesis.md").exists()
    assert (td / "reports" / "memo.docx").exists()
    assert (td / "reports" / "pitch.pptx").exists()
    assert (td / "reports" / "onepager.pdf").exists()
