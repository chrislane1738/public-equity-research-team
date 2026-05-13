"""End-to-end integration test for the full-deep-dive pipeline.

Tests the full pipeline through the FastAPI TestClient. HTTP calls to EDGAR
are mocked via respx; the FMP client is a MagicMock (real agent dispatch
makes too many FMP calls to enumerate individually in a respx router).
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from docx import Document
from fastapi.testclient import TestClient
from httpx import AsyncClient, MockTransport, Response

from backend.db.sqlite_client import SqliteClient
from backend.main import build_app
from backend.orchestrator import Orchestrator
from backend.tools.edgar_client import EdgarClient

from .helpers import wait_for_job


class FakeAnthropicMsg:
    def __init__(self, text: str):
        self.content = [MagicMock(type="text", text=text)]
        self.usage = MagicMock(input_tokens=100, output_tokens=100)
        self.stop_reason = "end_turn"


SYNTHESIS_OUT = """# Synthesis — NVDA
**Rating:** Buy
**Price Target:** $1,200

## Triangulation
- DCF Blended: $1,150 — 50%
- Comps median: $1,250 — 50%
- Final PT: $1,200

## Application logic
DCF leads on long-term thesis.
"""

MEMO_OUT = """# NVDA — Initiation

## Executive Summary
We rate NVDA Buy with a $1,200 PT.

## Investment Thesis
AI compute demand remains the structural driver.

## Risks
Top risk: AI capex pullback.
"""

DECK_SLIDE_PACK_JSON = json.dumps({
    "thesis_bullets": ["a", "b", "c"],
    "triangulation_rows": [["DCF Blend", 1200, 0.5], ["Comps", 1250, 0.5]],
    "top_risks": ["x", "y", "z"],
    "slide_bodies": {t: f"Body for {t}" for t in [
        "Investment Thesis", "Business Snapshot", "Industry & Moat",
        "Bespoke KPIs", "Financial Performance", "Forecast", "DCF",
        "Comps", "Valuation Triangulation", "Catalysts",
        "Risks / Bear Case", "Technical Setup", "Recommendation"]},
})


async def test_full_deep_dive_e2e_produces_memo_docx(tmp_path):
    """Full pipeline test: EDGAR HTTP mocked at AsyncClient transport level,
    FMP mocked via MagicMock, routed through TestClient."""
    fixture_html = (Path(__file__).parent / "fixtures" / "edgar_nvda_10k.html").read_text()

    # Build the respx router for EDGAR HTTP calls only
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    router.get("https://data.sec.gov/submissions/CIK0001045810.json").mock(
        return_value=Response(200, json={
            "filings": {"recent": {
                "form": ["10-K"],
                "accessionNumber": ["0001045810-24-000029"],
                "primaryDocument": ["nvda-20240128.htm"],
            }}
        })
    )
    router.get(
        "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/nvda-20240128.htm"
    ).mock(return_value=Response(200, text=fixture_html))

    # ---- FMP mock — covers all agent calls ----
    fmp = MagicMock()
    fmp.get_financials = AsyncMock(return_value={
        "income": [{"revenue": 60_922_000_000, "grossProfit": 44_301_000_000,
                    "operatingIncome": 32_000_000_000, "ebitda": 35_000_000_000,
                    "eps": 11.93}],
        "balance": [{"totalAssets": 65_728_000_000, "totalDebt": 11_000_000_000,
                     "cashAndCashEquivalents": 7_300_000_000}],
        "cash": [{"freeCashFlow": 27_021_000_000}],
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

    # ---- Fred mock ----
    fred = MagicMock()
    fred.get_series = AsyncMock(return_value=[{"date": "2026-05-09", "value": 4.25}])

    # ---- Settings mock ----
    settings = MagicMock()
    settings.model_for = MagicMock(side_effect=lambda agent: "claude-opus-4-7")

    # ---- Anthropic mock ----
    kpi_json = json.dumps({
        "data_center_revenue": {"definition": "DC revenue", "latest_value": 47_525_000_000, "unit": "USD"},
        "gross_margin": {"definition": "GP/Revenue", "latest_value": 0.727, "unit": "ratio"},
    })
    dcf_assumptions = json.dumps({
        "growth_path": [0.20, 0.18, 0.15, 0.12, 0.10],
        "ebit_margin_path": [0.55, 0.56, 0.57, 0.57, 0.58],
        "tax_rate": 0.13, "da_pct_revenue": 0.03,
        "capex_pct_revenue": 0.05, "wc_change_pct_revenue": 0.01,
        "terminal_growth_pct": 3.0, "blend_weight_ggm": 0.4,
        "weight_equity": 0.99, "weight_debt": 0.01, "cost_of_debt_pct": 4.5,
    })
    anthropic = MagicMock()
    # NOTE: Stage 2a (Industry, Comps, Macro, Risk, Technicals) runs via
    # asyncio.gather — actual LLM-call order is governed by how many pre-LLM
    # awaits each agent does, NOT submission order. Concretely the order is
    # roughly: risk (0 awaits) → technicals (1) → industry (2) → macro (3) →
    # comps (~7). All five Stage 2a responses are intentionally interchangeable
    # markdown; do NOT add structural validation to any of them without
    # switching the test to a callable side_effect that matches by call args.
    anthropic.messages.create = AsyncMock(side_effect=[
        FakeAnthropicMsg(text=kpi_json),                                  # Fundamentals KPI
        FakeAnthropicMsg(text="# Industry & Moat — NVDA\nWide moat.\n"),  # Industry
        FakeAnthropicMsg(text="# Comps — NVDA\nIn line.\n"),              # Comps
        FakeAnthropicMsg(text="# Macro — NVDA\nGoldilocks.\n"),           # Macro
        FakeAnthropicMsg(text="# Risk — NVDA\n**Bear-case PT: $80**\n"),  # Risk
        FakeAnthropicMsg(text="# Technicals — NVDA\nUptrend.\n"),         # Technicals
        FakeAnthropicMsg(text=dcf_assumptions),                            # DCF assumptions
        FakeAnthropicMsg(text="# DCF — NVDA\nBlended PT $1,150.\n"),      # DCF section
        FakeAnthropicMsg(text=SYNTHESIS_OUT),                              # MD synthesis
        FakeAnthropicMsg(text=MEMO_OUT),                                   # Memo Builder
        FakeAnthropicMsg(text=DECK_SLIDE_PACK_JSON),                       # Deck Builder
    ])

    edgar = EdgarClient(user_agent="Test test@example.com")

    cik_resolver = MagicMock()
    cik_resolver.resolve = AsyncMock(return_value="0001045810")
    orch = Orchestrator(
        anthropic_client=anthropic,
        fmp_client=fmp,
        edgar_client=edgar,
        fred_client=fred,
        research_dir=tmp_path,
        cik_resolver=cik_resolver,
        settings=settings,
    )

    app = build_app(orchestrator=orch, research_dir=tmp_path,
                    sqlite_client=SqliteClient(tmp_path / "test.sqlite"))

    # Patch AsyncClient to inject the respx router's mock transport for EDGAR calls.
    mock_transport = MockTransport(router.handler)
    _original_async_client_init = AsyncClient.__init__

    def _patched_async_client_init(self_inner, *args, **kwargs):
        kwargs["transport"] = mock_transport
        _original_async_client_init(self_inner, *args, **kwargs)

    with patch.object(AsyncClient, "__init__", new=_patched_async_client_init):
        with TestClient(app) as client:
            resp = client.post("/jobs", json={"ticker": "NVDA", "workflow": "full-deep-dive"})
            assert resp.status_code == 202, f"status={resp.status_code} body={resp.text!r}"
            job_id = resp.json()["job_id"]

            body = wait_for_job(client, job_id, timeout=60.0)

    assert body["status"] == "complete", f"body={body!r}"
    assert body["rating"] == "Buy"

    ticker_dir = tmp_path / "NVDA"
    memo_path = ticker_dir / "reports" / "memo.docx"
    assert memo_path.exists()

    doc = Document(memo_path)
    paragraphs = [p.text for p in doc.paragraphs]
    assert any("Executive Summary" in p for p in paragraphs)
    assert any("Buy" in p for p in paragraphs)
    assert any("AI capex pullback" in p for p in paragraphs)

    # Confirm intermediate state on disk
    assert (ticker_dir / "fundamentals" / "financials.json").exists()
    assert (ticker_dir / "fundamentals" / "kpis.json").exists()
    assert (ticker_dir / "fundamentals" / "10k-excerpt.txt").exists()
    assert (ticker_dir / "industry" / "section.md").exists()
    assert (ticker_dir / "comps" / "peer-multiples.json").exists()
    assert (ticker_dir / "comps" / "comps.xlsx").exists()
    assert (ticker_dir / "dcf" / "dcf.xlsx").exists()
    assert (ticker_dir / "macro" / "section.md").exists()
    assert (ticker_dir / "risk" / "section.md").exists()
    assert (ticker_dir / "technicals" / "section.md").exists()
    assert (ticker_dir / "synthesis" / "_synthesis.md").exists()
