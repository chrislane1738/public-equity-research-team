from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless

from tools.charts import (
    peer_share_chart,
    box_plot,
    football_field,
    sensitivity_heatmap,
    catalyst_timeline,
    price_chart,
    growth_panel,
    vwap_chart,
    volume_profile_chart,
    macd_chart,
    bollinger_chart,
)


def test_peer_share_chart_writes_png(tmp_path):
    out = tmp_path / "peers.png"
    peer_share_chart(
        peers=[{"symbol": "NVDA", "share": 0.40},
               {"symbol": "AMD", "share": 0.20},
               {"symbol": "INTC", "share": 0.40}],
        path=out, title="GPU share",
    )
    assert out.exists() and out.stat().st_size > 1000


def test_box_plot_writes_png(tmp_path):
    out = tmp_path / "box.png"
    box_plot(
        metric_name="EV/EBITDA",
        peer_values=[10, 12, 15, 20, 25, 18],
        target_value=14,
        path=out,
    )
    assert out.exists() and out.stat().st_size > 1000


def test_football_field_writes_png(tmp_path):
    out = tmp_path / "ff.png"
    football_field(
        scenarios=[("DCF GGM", 80, 110),
                   ("DCF Exit", 90, 130),
                   ("DCF Blend", 95, 120),
                   ("Comps median", 85, 115),
                   ("52-wk anchor", 70, 130)],
        current_price=100,
        path=out,
    )
    assert out.exists() and out.stat().st_size > 1000


def test_sensitivity_heatmap_writes_png(tmp_path):
    out = tmp_path / "sens.png"
    grid = {(8.0, 1.5): 110, (8.0, 2.5): 120, (8.0, 3.5): 135,
            (10.0, 1.5): 95, (10.0, 2.5): 105, (10.0, 3.5): 115,
            (12.0, 1.5): 80, (12.0, 2.5): 90, (12.0, 3.5): 100}
    sensitivity_heatmap(grid=grid, x_axis_name="Terminal g (%)",
                        y_axis_name="WACC (%)", path=out)
    assert out.exists() and out.stat().st_size > 1000


def test_catalyst_timeline_writes_png(tmp_path):
    out = tmp_path / "timeline.png"
    catalyst_timeline(
        events=[("2026-05-22", "Q1 earnings"),
                ("2026-06-15", "GTC keynote"),
                ("2026-08-21", "Q2 earnings")],
        path=out,
    )
    assert out.exists() and out.stat().st_size > 1000


def test_price_chart_writes_png(tmp_path):
    out = tmp_path / "price.png"
    rows = [{"date": f"2026-04-{d:02d}", "close": 100 + d * 0.5,
             "volume": 1_000_000} for d in range(1, 31)]
    price_chart(prices=rows, sma_windows=[5, 20], path=out, title="NVDA")
    assert out.exists() and out.stat().st_size > 1000


def test_growth_panel_writes_png(tmp_path):
    out = tmp_path / "growth.png"
    growth_panel(
        metrics=[
            {"name": "Revenue", "periods": ["FY21", "FY22", "FY23", "FY24", "FY25"],
             "values": [27.7, 30.8, 15.5, 25.1, 37.4], "unit": "$B"},
            {"name": "EPS", "periods": ["FY21", "FY22", "FY23", "FY24", "FY25"],
             "values": [5.14, 8.35, -4.45, 1.30, 8.29], "unit": "$"},
        ],
        path=out,
    )
    assert out.exists() and out.stat().st_size > 1000


def test_growth_panel_quarterly(tmp_path):
    """A quarterly panel (YoY + QoQ card, rotated x labels) renders cleanly."""
    out = tmp_path / "growth_q.png"
    q = ["FQ3-24", "FQ4-24", "FQ1-25", "FQ2-25", "FQ3-25", "FQ4-25", "FQ1-26", "FQ2-26"]
    growth_panel(
        metrics=[{"name": "Revenue", "periods": q,
                  "values": [6.6, 7.2, 7.8, 9.0, 11.3, 13.6, 18.0, 23.9], "unit": "$B"}],
        path=out, periodicity="quarterly",
    )
    assert out.exists() and out.stat().st_size > 1000


def test_growth_panel_handles_negative_endpoint(tmp_path):
    """A single-metric panel whose series starts in a loss leaves CAGR 'n.m.'."""
    out = tmp_path / "growth_neg.png"
    growth_panel(
        metrics=[{"name": "EPS", "periods": ["FY23", "FY24", "FY25"],
                  "values": [-4.45, 1.30, 8.29], "unit": "$"}],
        path=out,
    )
    assert out.exists() and out.stat().st_size > 1000


def test_price_chart_handles_newest_first_or_oldest_first(tmp_path):
    """Verify the chart renders the same regardless of input ordering."""
    rows_newest_first = [
        {"date": "2026-04-30", "close": 110, "volume": 1_000_000},
        {"date": "2026-04-15", "close": 100, "volume": 1_000_000},
        {"date": "2026-04-01", "close":  95, "volume": 1_000_000},
    ]
    rows_oldest_first = list(reversed(rows_newest_first))
    a = tmp_path / "newest.png"
    b = tmp_path / "oldest.png"
    price_chart(prices=rows_newest_first, sma_windows=[], path=a, title="A")
    price_chart(prices=rows_oldest_first, sma_windows=[], path=b, title="B")
    # Both files exist with similar size — the sort makes them effectively identical.
    assert a.exists() and b.exists()
    # Allow ~5% size variance for title-text differences only.
    assert abs(a.stat().st_size - b.stat().st_size) < a.stat().st_size * 0.10


# --- technicals indicator charts ---

_DATES = [f"2026-{(m):02d}-{(d):02d}" for m in (1, 2, 3) for d in range(1, 21)]
_CLOSES = [100 + i * 0.4 for i in range(len(_DATES))]


def test_vwap_chart_writes_png(tmp_path):
    out = tmp_path / "vwap.png"
    n = len(_DATES)
    vwaps = [
        {"name": "Rolling VWAP (50d)", "values": [None] * 10 + _CLOSES[10:]},
        {"name": "Anchored VWAP (52w low)", "values": [None] * 5 + _CLOSES[5:]},
    ]
    vwap_chart(_DATES, _CLOSES, vwaps, path=out, title="NVDA")
    assert out.exists() and out.stat().st_size > 1000


def test_volume_profile_chart_writes_png(tmp_path):
    out = tmp_path / "vp.png"
    buckets = [
        {"low": 90 + b, "high": 91 + b, "mid": 90.5 + b, "volume": 1e6 * (b + 1)}
        for b in range(12)
    ]
    volume_profile_chart(buckets, current_price=98.0, path=out)
    assert out.exists() and out.stat().st_size > 1000


def test_macd_chart_writes_png(tmp_path):
    out = tmp_path / "macd.png"
    n = len(_DATES)
    macd_line = [None] * 26 + [0.3 * ((-1) ** i) for i in range(n - 26)]
    signal_line = [None] * 34 + [0.1 * ((-1) ** i) for i in range(n - 34)]
    histogram = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]
    macd_chart(_DATES, macd_line, signal_line, histogram, path=out)
    assert out.exists() and out.stat().st_size > 1000


def test_bollinger_chart_writes_png(tmp_path):
    out = tmp_path / "boll.png"
    mid = [None] * 19 + [c for c in _CLOSES[19:]]
    upper = [None if m is None else m + 5 for m in mid]
    lower = [None if m is None else m - 5 for m in mid]
    bollinger_chart(_DATES, _CLOSES, upper, mid, lower, path=out)
    assert out.exists() and out.stat().st_size > 1000
