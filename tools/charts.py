"""Matplotlib renderers for deck/report charts.

House style — an institutional sell-side look matching the report.html redesign:
restrained navy/gold palette, clean sans-serif type, despined axes, light
horizontal gridlines, direct data labels, formatted axes. Output PNGs have
transparent backgrounds so they sit cleanly on the report's cream page and on
white deck slides.

Chart titles are intentionally NOT baked into the PNG — the report wraps each
chart in a <figure> with a caption, and deck slides carry their own titles.
The `title` parameters are retained for call-site compatibility but unused.
"""
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# --- house palette (tied to the report.html institutional theme) ---
NAVY = "#16243f"   # primary series
GOLD = "#b8893a"   # accent — target lines, highlights
SLATE = "#5b6b85"  # secondary series
MIST = "#9aa6bc"   # tertiary series
RULE = "#d8d8d8"   # gridlines / spines
INK = "#2b2b2b"    # primary text
MUTED = "#6b7280"  # secondary text / axis labels

_SMA_COLORS = [GOLD, SLATE, MIST]

# Restrained diverging ramp for the sensitivity grid — muted brick / cream /
# muted green, replacing matplotlib's saturated RdYlGn rainbow.
_DIVERGING = LinearSegmentedColormap.from_list(
    "house_diverging", ["#b04a3f", "#f3f1ec", "#3f7d5a"]
)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "text.color": INK,
    "axes.edgecolor": RULE,
    "axes.labelcolor": MUTED,
    "axes.labelsize": 10,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.grid": False,
})


def _style_axes(ax, grid_axis: str | None = "y") -> None:
    """Apply the house axis treatment: despined, light gridlines, no tick marks."""
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
    if grid_axis:
        ax.grid(axis=grid_axis, color=RULE, linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def _fig_save(fig, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, transparent=True, bbox_inches="tight", dpi=200)
    plt.close(fig)


def peer_share_chart(peers: list[dict], path: Path, title: str = "Peer share") -> None:
    """Vertical bar chart of each peer's market share. `share` is a fraction (0-1)."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    symbols = [p["symbol"] for p in peers]
    shares = [p["share"] for p in peers]
    bars = ax.bar(symbols, shares, color=NAVY, width=0.62)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0))
    ax.set_ylabel("Market share")
    ax.set_xlabel("Peer")
    ax.set_ylim(0, max(shares) * 1.18 if shares else 1)
    for bar, share in zip(bars, shares):
        ax.annotate(f"{share * 100:.0f}%",
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, fontweight="bold", color=INK)
    _style_axes(ax)
    _fig_save(fig, path)


def box_plot(metric_name: str, peer_values: list[float],
             target_value: float | None, path: Path) -> None:
    """Box plot of a peer-multiple distribution, with the target marked."""
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.boxplot(
        peer_values, orientation="vertical", widths=0.5, showmeans=True,
        patch_artist=True, tick_labels=[metric_name],
        boxprops=dict(facecolor="#e3e7ee", edgecolor=NAVY, linewidth=1.2),
        medianprops=dict(color=NAVY, linewidth=1.6),
        whiskerprops=dict(color=SLATE, linewidth=1.1),
        capprops=dict(color=SLATE, linewidth=1.1),
        flierprops=dict(marker="o", markersize=4, markerfacecolor=MIST,
                        markeredgecolor=SLATE),
        meanprops=dict(marker="D", markersize=6, markerfacecolor=GOLD,
                       markeredgecolor=GOLD),
    )
    if target_value is not None:
        ax.axhline(target_value, linestyle="--", color=GOLD, linewidth=1.5,
                   label=f"Target = {target_value:,.1f}")
        ax.legend(loc="best", frameon=False, fontsize=9)
    ax.set_ylabel(metric_name)
    _style_axes(ax)
    _fig_save(fig, path)


def football_field(scenarios: list[tuple[str, float, float]],
                   current_price: float, path: Path) -> None:
    """Horizontal low–high range bars per valuation method, plus the spot line."""
    fig, ax = plt.subplots(figsize=(9, 0.7 * len(scenarios) + 1.7))
    labels = [s[0] for s in scenarios]
    lows = np.array([s[1] for s in scenarios], dtype=float)
    highs = np.array([s[2] for s in scenarios], dtype=float)
    y = np.arange(len(labels))
    ax.barh(y, highs - lows, left=lows, height=0.5, color=NAVY)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()

    # x-limits with margin; endpoint labels go outside the bar, but flip to
    # inside (white) when an endpoint sits too close to an axis edge to fit.
    span = float(highs.max() - lows.min()) or 1.0
    xlo, xhi = lows.min() - span * 0.08, highs.max() + span * 0.08
    ax.set_xlim(xlo, xhi)
    edge = span * 0.14
    for yi, lo, hi in zip(y, lows, highs):
        if lo - xlo < edge:  # near left edge — label inside the bar
            ax.annotate(f"${lo:,.0f}", (lo, yi), xytext=(6, 0),
                        textcoords="offset points", ha="left", va="center",
                        fontsize=8, fontweight="bold", color="#ffffff")
        else:
            ax.annotate(f"${lo:,.0f}", (lo, yi), xytext=(-6, 0),
                        textcoords="offset points", ha="right", va="center",
                        fontsize=8, color=MUTED)
        if xhi - hi < edge:  # near right edge — label inside the bar
            ax.annotate(f"${hi:,.0f}", (hi, yi), xytext=(-6, 0),
                        textcoords="offset points", ha="right", va="center",
                        fontsize=8, fontweight="bold", color="#ffffff")
        else:
            ax.annotate(f"${hi:,.0f}", (hi, yi), xytext=(6, 0),
                        textcoords="offset points", ha="left", va="center",
                        fontsize=8, color=MUTED)
    ax.axvline(current_price, color=GOLD, linestyle="--", linewidth=1.5)
    ax.annotate(f"Current  ${current_price:,.0f}",
                xy=(current_price, 1), xycoords=("data", "axes fraction"),
                xytext=(0, 5), textcoords="offset points",
                ha="center", va="bottom", fontsize=9, fontweight="bold", color=GOLD)
    ax.set_xlabel("Implied share price (US$)")
    ax.xaxis.set_major_formatter("${x:,.0f}")
    _style_axes(ax, grid_axis="x")
    _fig_save(fig, path)


def sensitivity_heatmap(grid: dict[tuple[float, float], float],
                        x_axis_name: str, y_axis_name: str, path: Path) -> None:
    """Render a 2-D dict as a heatmap. Keys are (y_value, x_value), values priced."""
    ys = sorted({k[0] for k in grid.keys()})
    xs = sorted({k[1] for k in grid.keys()})
    matrix = np.array([[grid.get((y, x), float("nan")) for x in xs] for y in ys])

    fig, ax = plt.subplots(figsize=(7.5, 5))
    im = ax.imshow(matrix, aspect="auto", cmap=_DIVERGING)
    ax.set_xticks(range(len(xs)), [f"{x:g}" for x in xs])
    ax.set_yticks(range(len(ys)), [f"{y:g}" for y in ys])
    ax.set_xlabel(x_axis_name)
    ax.set_ylabel(y_axis_name)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    for i in range(len(ys)):
        for j in range(len(xs)):
            v = matrix[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"${v:,.0f}", ha="center", va="center",
                        fontsize=8, color=INK)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(length=0, labelsize=8)
    _fig_save(fig, path)


def catalyst_timeline(events: list[tuple[str, str]], path: Path) -> None:
    """Plot date-labeled catalysts as points on a horizontal time axis."""
    fig, ax = plt.subplots(figsize=(10, 3.6))
    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in events]
    labels = [lbl for _, lbl in events]
    ax.axhline(1, color=RULE, linewidth=1.2, zorder=1)
    ax.scatter(dates, [1] * len(dates), s=70, color=NAVY, zorder=3)
    # alternate label height so adjacent (possibly close-dated) labels never collide
    for i, (d, lbl) in enumerate(zip(dates, labels)):
        tier = 1.40 if i % 2 else 1.18
        ax.plot([d, d], [1, tier], color=RULE, linewidth=0.8, zorder=2)
        ax.annotate(lbl, (d, tier + 0.02), ha="center", va="bottom",
                    fontsize=8, color=INK)
        ax.annotate(d.strftime("%b %d"), (d, 0.86), ha="center", va="top",
                    fontsize=7.5, color=MUTED)
    ax.set_ylim(0.55, 1.78)
    ax.margins(x=0.08)
    ax.set_yticks([])
    ax.set_xticks([])
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    _fig_save(fig, path)


def price_chart(prices: list[dict], sma_windows: list[int],
                path: Path, title: str = "Price") -> None:
    """Line chart of close price with optional SMA overlays.

    Sorts `prices` by date ascending before plotting. The input may be in any
    order (FMP's historical-prices endpoint returns newest-first, but the
    function does not rely on that contract).
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    sorted_rows = sorted(prices, key=lambda p: p["date"])
    dates = [datetime.strptime(p["date"], "%Y-%m-%d") for p in sorted_rows]
    closes = np.array([p["close"] for p in sorted_rows])
    ax.plot(dates, closes, color=NAVY, linewidth=1.7, label="Close")
    for window, color in zip(sma_windows, _SMA_COLORS):
        if len(closes) < window:
            continue
        sma = np.convolve(closes, np.ones(window) / window, mode="valid")
        ax.plot(dates[window - 1:], sma, color=color, linewidth=1.2,
                label=f"SMA {window}")
    ax.set_ylabel("Share price (US$)")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter("${x:,.0f}")
    ax.legend(loc="best", frameon=False, fontsize=9)
    _style_axes(ax)
    _fig_save(fig, path)
