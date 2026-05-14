"""Canonical-eval harness — exercises deterministic helpers without invoking the LLM.

Skills are not directly callable from Python — they're loaded by Claude. This
harness simulates the deterministic half of every skill (the Python helpers it
would invoke) using canonical fixture data in place of live FMP/EDGAR/WebSearch
calls. The result: a fully-populated <TICKER>/ tree on disk, ready for the
test to assert against.
"""
import json
from pathlib import Path
from typing import Any

from tools import charts, dcf_engine
from tools.html_writer import write_report_html


def _load_fixture(fixture_dir: Path, name: str) -> Any:
    """Load a fixture file. Returns parsed JSON if .json, raw text if .md/.txt, None if missing."""
    p = fixture_dir / name
    if not p.exists():
        return None
    if p.suffix == ".json":
        return json.loads(p.read_text())
    return p.read_text()


def _write_fundamentals(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "fundamentals"
    out.mkdir(parents=True, exist_ok=True)

    financials = _load_fixture(fixture_dir, "financials.json") or {}
    kpis = _load_fixture(fixture_dir, "kpis.json") or {}
    excerpt = _load_fixture(fixture_dir, "10k-excerpt.txt") or ""
    section = (
        _load_fixture(fixture_dir, "fundamentals_section.md")
        or "# Fundamentals\n\nStub.\n"
    )

    (out / "financials.json").write_text(json.dumps(financials, indent=2))
    (out / "kpis.json").write_text(json.dumps(kpis, indent=2))
    (out / "10k-excerpt.txt").write_text(excerpt)
    (out / "section.md").write_text(section)


def _write_industry(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "industry"
    out.mkdir(parents=True, exist_ok=True)

    (out / "section.md").write_text(
        _load_fixture(fixture_dir, "industry_section.md") or "# Industry\n\nStub.\n"
    )

    chart_path = out / "peer-share-chart.png"
    # peers.json in fixtures is a list of ticker symbols; build list[dict] for charts API
    raw_peers = _load_fixture(fixture_dir, "peers.json")
    if isinstance(raw_peers, list) and raw_peers and isinstance(raw_peers[0], str):
        # Convert ["AMD", "INTC", ...] → [{"symbol": "AMD", "share": 0.25}, ...]
        n = len(raw_peers)
        peers_data = [{"symbol": sym, "share": round(1.0 / n, 4)} for sym in raw_peers]
    elif isinstance(raw_peers, list):
        peers_data = raw_peers  # already list[dict]
    else:
        peers_data = [
            {"symbol": "AMD", "share": 0.25},
            {"symbol": "AVGO", "share": 0.20},
            {"symbol": "INTC", "share": 0.15},
        ]

    # charts.peer_share_chart(peers: list[dict], path: Path, title: str = "Peer share")
    charts.peer_share_chart(peers_data, chart_path)


def _write_dcf(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "dcf"
    out.mkdir(parents=True, exist_ok=True)

    # Exercise dcf_engine.compute_wacc with a realistic NVDA-ish WACC
    dcf_engine.compute_wacc(
        beta=1.5,
        rf=4.5,
        cost_of_debt=5.0,
        tax_rate=21.0,
        weight_equity=0.95,
        weight_debt=0.05,
        erp=5.5,
    )

    # football_field(scenarios: list[tuple[str, float, float]], current_price: float, path)
    charts.football_field(
        scenarios=[("DCF GGM", 100.0, 200.0), ("Comps", 90.0, 180.0)],
        current_price=130.0,
        path=out / "football-field.png",
    )

    # sensitivity_heatmap(grid: dict[tuple[float,float], float], x_axis_name, y_axis_name, path)
    # Keys are (y_value, x_value) → (wacc, terminal_growth)
    grid = {
        (9.0, 1.5): 100.0,  (9.0, 2.5): 110.0,  (9.0, 3.5): 120.0,
        (10.0, 1.5): 115.0, (10.0, 2.5): 130.0, (10.0, 3.5): 145.0,
        (11.0, 1.5): 130.0, (11.0, 2.5): 150.0, (11.0, 3.5): 170.0,
    }
    charts.sensitivity_heatmap(
        grid=grid,
        x_axis_name="Terminal growth (%)",
        y_axis_name="WACC (%)",
        path=out / "sensitivity.png",
    )

    (out / "dcf.xlsx").write_bytes(b"")
    (out / "section.md").write_text(
        _load_fixture(fixture_dir, "dcf_section.md") or "# DCF\n\nStub.\n"
    )


def _write_comps(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "comps"
    out.mkdir(parents=True, exist_ok=True)

    peer_multiples = _load_fixture(fixture_dir, "peer_multiples.json") or {
        "peer_median_ev_ebitda": 18.0,
        "peer_p75_ev_ebitda": 24.0,
        "peers": ["AMD", "AVGO", "ARM"],
    }
    (out / "peer-multiples.json").write_text(json.dumps(peer_multiples, indent=2))
    (out / "comps.xlsx").write_bytes(b"")

    # box_plot(metric_name: str, peer_values: list[float], target_value: float|None, path)
    charts.box_plot(
        metric_name="EV/EBITDA",
        peer_values=[15.0, 18.0, 22.0, 24.0, 27.0],
        target_value=20.0,
        path=out / "box-plot.png",
    )

    (out / "section.md").write_text(
        _load_fixture(fixture_dir, "comps_section.md") or "# Comps\n\nStub.\n"
    )


def _write_macro(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "macro"
    out.mkdir(parents=True, exist_ok=True)

    (out / "section.md").write_text(
        _load_fixture(fixture_dir, "macro_section.md") or "# Macro\n\nStub.\n"
    )

    # catalyst_timeline expects "%Y-%m-%d" format
    charts.catalyst_timeline(
        events=[("2026-08-01", "Q2 earnings"), ("2026-11-15", "GTC")],
        path=out / "catalyst-timeline.png",
    )


def _write_risk(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "risk"
    out.mkdir(parents=True, exist_ok=True)
    (out / "section.md").write_text(
        _load_fixture(fixture_dir, "risk_section.md") or "# Risk\n\nStub.\n"
    )


def _write_technicals(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "technicals"
    out.mkdir(parents=True, exist_ok=True)

    (out / "section.md").write_text(
        _load_fixture(fixture_dir, "technicals_section.md")
        or "# Technicals\n\nStub.\n"
    )

    # historical.json fixture shape: {"symbol": "NVDA", "historical": [{"date": ..., "close": ..., "volume": ...}]}
    raw_historical = _load_fixture(fixture_dir, "historical.json")
    if isinstance(raw_historical, dict) and "historical" in raw_historical:
        bars = raw_historical["historical"]
    elif isinstance(raw_historical, list):
        bars = raw_historical
    else:
        bars = [
            {"date": "2025-01-01", "close": 100.0, "volume": 1_000_000},
            {"date": "2025-01-02", "close": 102.0, "volume": 1_100_000},
        ]

    # price_chart(prices: list[dict], sma_windows: list[int], path, title="Price")
    charts.price_chart(bars, sma_windows=[], path=out / "price-chart.png")


def _write_synthesis(ticker_dir: Path, fixture_dir: Path) -> None:
    out = ticker_dir / "synthesis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "_synthesis.md").write_text(
        _load_fixture(fixture_dir, "synthesis.md")
        or "# Synthesis\n\nRating: Buy. PT: $200.\n"
    )


def _write_reports(ticker_dir: Path, fixture_dir: Path) -> None:  # noqa: ARG001
    out = ticker_dir / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "memo.docx").write_bytes(b"")
    (out / "pitch.pptx").write_bytes(b"")
    (out / "onepager.pdf").write_bytes(b"")


def run_canonical_pipeline(
    ticker: str, ticker_dir: Path, fixture_dir: Path
) -> dict[str, Path]:
    """Simulate the deterministic side of a full deep-dive. Returns a manifest.

    Args:
        ticker:      Ticker symbol (e.g. "NVDA").
        ticker_dir:  Root directory where the full ticker tree will be written.
        fixture_dir: Directory containing canonical fixture files for this ticker.
                     Files missing from fixture_dir are replaced with stubs so
                     the structure is always complete.

    Returns:
        dict with keys ``"report_html"`` (Path to written report.html) and
        ``"ticker_dir"`` (Path to the root ticker directory).
    """
    ticker_dir = Path(ticker_dir)
    fixture_dir = Path(fixture_dir)
    ticker_dir.mkdir(parents=True, exist_ok=True)

    _write_fundamentals(ticker_dir, fixture_dir)
    _write_industry(ticker_dir, fixture_dir)
    _write_dcf(ticker_dir, fixture_dir)
    _write_comps(ticker_dir, fixture_dir)
    _write_macro(ticker_dir, fixture_dir)
    _write_risk(ticker_dir, fixture_dir)
    _write_technicals(ticker_dir, fixture_dir)
    _write_synthesis(ticker_dir, fixture_dir)
    _write_reports(ticker_dir, fixture_dir)

    html = write_report_html(ticker_dir, ticker)
    return {"report_html": html, "ticker_dir": ticker_dir}
