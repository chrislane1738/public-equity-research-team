"""Canonical eval — every expected artifact lands on disk for each fixture ticker.

This is a wiring test, not a quality test. It uses _canonical_helpers to drive
the deterministic helpers (charts, dcf_engine, html_writer) with fixture data
in place of live FMP/EDGAR/WebSearch + LLM. Catches structural regressions
(e.g., a helper stops writing peer-multiples.json).
"""
from pathlib import Path

import pytest

from tests._canonical_helpers import run_canonical_pipeline


FIXTURES_ROOT = Path(__file__).parent / "canonical"

TICKERS = ["NVDA", "AAPL", "JPM", "XOM"]

EXPECTED_FILES = [
    "fundamentals/financials.json",
    "fundamentals/kpis.json",
    "fundamentals/10k-excerpt.txt",
    "fundamentals/section.md",
    "industry/section.md",
    "industry/peer-share-chart.png",
    "dcf/section.md",
    "dcf/dcf.xlsx",
    "dcf/football-field.png",
    "dcf/sensitivity.png",
    "comps/section.md",
    "comps/comps.xlsx",
    "comps/peer-multiples.json",
    "comps/box-plot.png",
    "macro/section.md",
    "macro/catalyst-timeline.png",
    "risk/section.md",
    "technicals/section.md",
    "technicals/price-chart.png",
    "synthesis/_synthesis.md",
    "reports/memo.docx",
    "reports/pitch.pptx",
    "reports/onepager.pdf",
    "report.html",
]


@pytest.mark.parametrize("ticker", TICKERS)
def test_canonical_artifacts_land_on_disk(ticker, tmp_path):
    fixture_dir = FIXTURES_ROOT / ticker
    # Harness gracefully degrades when fixture files are missing — stubs default content
    # so we still produce the structural tree. fixture_dir doesn't need to exist.
    ticker_dir = tmp_path / ticker
    manifest = run_canonical_pipeline(ticker, ticker_dir, fixture_dir)

    for rel in EXPECTED_FILES:
        assert (ticker_dir / rel).exists(), f"missing artifact: {rel} for {ticker}"

    # Sanity check: report.html is non-trivial and self-contained
    html = manifest["report_html"].read_text()
    assert "<html" in html
    assert "<style>" in html
    assert "@media print" in html


def test_canonical_report_html_embeds_charts_as_data_uris(tmp_path):
    """Verify that html_writer base64-embeds chart PNGs referenced in section.md files.

    tests/canonical/NVDA/dcf_section.md includes an <img> tag referencing
    football-field.png so that a single pipeline run produces a report.html that
    contains an embedded data URI for that chart.
    """
    fixture_dir = FIXTURES_ROOT / "NVDA"
    ticker_dir = tmp_path / "NVDA"
    manifest = run_canonical_pipeline("NVDA", ticker_dir, fixture_dir)
    html = manifest["report_html"].read_text()
    assert "data:image/png;base64," in html
