"""End-to-end integration test for the full-deep-dive pipeline.

Tests the full pipeline: FmpClient + EdgarClient + FundamentalsAgent +
stub research pods + MDAgent + MemoBuilderAgent, called through the
FastAPI TestClient.

HTTP calls (FMP + EDGAR) are mocked via respx at the AsyncClient transport
level. The TestClient uses httpx.Client (sync) with an ASGITransport, so it
is not affected by the AsyncClient patching.
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from docx import Document
from fastapi.testclient import TestClient
from httpx import AsyncClient, MockTransport, Response

from backend.cik_resolver import FmpProfileCikResolver
from backend.main import build_app
from backend.orchestrator import Orchestrator
from backend.tools.edgar_client import EdgarClient
from backend.tools.fmp_client import FmpClient


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


async def test_full_deep_dive_e2e_produces_memo_docx(tmp_path):
    """Full pipeline test: HTTP mocked at AsyncClient transport level, routed through TestClient."""
    fixture_html = (Path(__file__).parent / "fixtures" / "edgar_nvda_10k.html").read_text()

    # Build the respx router for external HTTP calls (FMP + EDGAR)
    router = respx.MockRouter(assert_all_mocked=True, assert_all_called=False)
    router.get("https://financialmodelingprep.com/stable/income-statement").mock(
        return_value=Response(200, json=[{"date": "2024-01-28", "revenue": 60_922_000_000, "grossProfit": 44_301_000_000}])
    )
    router.get("https://financialmodelingprep.com/stable/balance-sheet-statement").mock(
        return_value=Response(200, json=[{"date": "2024-01-28", "totalAssets": 65_728_000_000}])
    )
    router.get("https://financialmodelingprep.com/stable/cash-flow-statement").mock(
        return_value=Response(200, json=[{"date": "2024-01-28", "freeCashFlow": 27_021_000_000}])
    )
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

    # ---- Anthropic mock (3 sequential calls: Fundamentals KPIs, MD synthesis, Memo) ----
    kpi_json = json.dumps({
        "data_center_revenue": {"definition": "DC revenue", "latest_value": 47_525_000_000, "unit": "USD"},
        "gross_margin": {"definition": "GP/Revenue", "latest_value": 0.727, "unit": "ratio"},
    })
    anthropic = MagicMock()
    anthropic.messages.create = AsyncMock(side_effect=[
        FakeAnthropicMsg(text=kpi_json),
        FakeAnthropicMsg(text=SYNTHESIS_OUT),
        FakeAnthropicMsg(text=MEMO_OUT),
    ])

    fmp = FmpClient(api_key="fake", cache_dir=tmp_path / "_fmp_cache")
    edgar = EdgarClient(user_agent="Test test@example.com")

    cik_resolver = MagicMock()
    cik_resolver.resolve = AsyncMock(return_value="0001045810")
    orch = Orchestrator(
        anthropic_client=anthropic,
        fmp_client=fmp,
        edgar_client=edgar,
        research_dir=tmp_path,
        cik_resolver=cik_resolver,
        opus_model="claude-opus-4-7",
        sonnet_model="claude-sonnet-4-6",
    )

    app = build_app(orchestrator=orch, research_dir=tmp_path)

    # Patch AsyncClient to inject the respx router's mock transport.
    # This leaves httpx.Client (used by TestClient's ASGITransport) untouched.
    mock_transport = MockTransport(router.handler)
    _original_async_client_init = AsyncClient.__init__

    def _patched_async_client_init(self_inner, *args, **kwargs):
        kwargs["transport"] = mock_transport
        _original_async_client_init(self_inner, *args, **kwargs)

    with patch.object(AsyncClient, "__init__", new=_patched_async_client_init):
        client = TestClient(app)
        resp = client.post("/jobs", json={"ticker": "NVDA", "workflow": "full-deep-dive"})

    assert resp.status_code == 200, f"status={resp.status_code} body={resp.text!r}"
    body = resp.json()
    assert body["status"] == "complete"
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
    for sub in ["industry", "dcf", "comps", "macro", "risk", "technicals"]:
        assert (ticker_dir / sub / "section.md").exists()
    assert (ticker_dir / "synthesis" / "_synthesis.md").exists()
