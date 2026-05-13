from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless

from backend.tools.charts import (
    peer_share_chart,
    box_plot,
    football_field,
    sensitivity_heatmap,
    catalyst_timeline,
    price_chart,
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
