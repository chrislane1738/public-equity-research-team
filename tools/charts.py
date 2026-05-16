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
from matplotlib.patches import Rectangle

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


# --- growth-panel helpers ---
_UNIT_AXIS = {"$B": "US$bn", "$": "US$", "%": "%", "x": "x", "": ""}


def _fmt_metric_value(v: float, unit: str) -> str:
    """Format a metric value for an on-bar data label."""
    if unit == "$B":
        return f"${v:,.1f}B"
    if unit == "$":
        return f"${v:,.2f}"
    if unit == "%":
        return f"{v:,.1f}%"
    if unit == "x":
        return f"{v:,.1f}x"
    return f"{v:,.0f}"


def _signed_pct(frac: float) -> str:
    """Format a fraction as a signed percent, collapsing -0%/+0% to a clean 0%."""
    s = f"{frac:+.0%}"
    return "0%" if s in ("+0%", "-0%") else s


def _growth_figures(values: list[float],
                    periodicity: str) -> tuple[str, str, str, str]:
    """Compute the two growth figures shown on a metric's card.

    Returns (headline, headline_label, sub, sub_label):
      annual    -> headline = 3-year CAGR, sub = YoY
      quarterly -> headline = YoY,         sub = QoQ
      ttm       -> headline = YoY,         sub = QoQ
    Any figure is 'n.m.' when a zero/negative base makes it meaningless. The
    annual CAGR targets 3 years and falls back to the longest whole-year
    window when fewer years of data exist, labelling its actual span.
    """
    def pct(new: float, base: float) -> str:
        return _signed_pct(new / base - 1) if base > 0 and new > 0 else "n.m."

    if periodicity == "annual":
        step = 3 if len(values) > 3 else max(len(values) - 1, 0)
        if step >= 1 and values[-1] > 0 and values[-1 - step] > 0:
            headline = _signed_pct((values[-1] / values[-1 - step]) ** (1 / step) - 1)
        else:
            headline = "n.m."
        yoy = pct(values[-1], values[-2]) if len(values) >= 2 else "n.m."
        return headline, f"{step}-yr CAGR", yoy, "YoY"

    # quarterly / ttm — YoY (vs four periods back) headline, QoQ sub-figure
    yoy = pct(values[-1], values[-5]) if len(values) >= 5 else "n.m."
    qoq = pct(values[-1], values[-2]) if len(values) >= 2 else "n.m."
    return yoy, "YoY", qoq, "QoQ"


def growth_panel(metrics: list[dict], path: Path,
                 periodicity: str = "annual") -> None:
    """Small-multiple growth exhibit — one bar chart per metric across periods,
    each capped with a navy card. The card shows two growth rates: a 3-year
    CAGR and YoY for an annual panel, or YoY and QoQ for a quarterly/TTM panel.

    Each metric dict carries:
      name:    str         — metric label, e.g. "Revenue"
      periods: list[str]   — period labels, e.g. ["FY21", "FY22", ..., "FY25"]
      values:  list[float] — value per period, in the metric's display unit
      unit:    str         — one of "$B", "$", "%", "x", "" (drives formatting)

    periodicity: "annual", "quarterly", or "ttm" — sets the YoY and CAGR
    lookback (1 / 4 / 4 periods per year). All metrics in one panel share it.
    """
    n = len(metrics)
    fig, axes = plt.subplots(
        2, n, figsize=(3.4 * n, 4.7),
        gridspec_kw={"height_ratios": [1, 3.6], "hspace": 0.12, "wspace": 0.34},
    )
    axes = np.asarray(axes).reshape(2, n)

    for i, metric in enumerate(metrics):
        periods = metric["periods"]
        values = metric["values"]
        unit = metric.get("unit", "")
        headline, head_label, sub, sub_label = _growth_figures(values, periodicity)

        # --- growth card ---
        card = axes[0, i]
        card.axis("off")
        card.set_xlim(0, 1)
        card.set_ylim(0, 1)
        card.add_patch(Rectangle((0.03, 0.06), 0.94, 0.88, transform=card.transAxes,
                                 facecolor=NAVY, edgecolor="none", clip_on=False))
        card.text(0.5, 0.76, metric["name"].upper(), transform=card.transAxes,
                  ha="center", va="center", fontsize=9, fontweight="bold",
                  color="#aab6cd")
        card.text(0.5, 0.50, headline, transform=card.transAxes,
                  ha="center", va="center", fontsize=19, fontweight="bold", color=GOLD)
        card.text(0.5, 0.26, f"{head_label}   ·   {sub_label} {sub}",
                  transform=card.transAxes, ha="center", va="center",
                  fontsize=7.5, color="#aab6cd")

        # --- metric bars ---
        ax = axes[1, i]
        bars = ax.bar(periods, values, color=NAVY, width=0.6)
        if values:
            bars[-1].set_color(GOLD)  # highlight the most recent period
        ax.set_ylabel(_UNIT_AXIS.get(unit, ""))
        for bar, v in zip(bars, values):
            ax.annotate(_fmt_metric_value(v, unit),
                        (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 2 if v >= 0 else -2), textcoords="offset points",
                        ha="center", va="bottom" if v >= 0 else "top",
                        fontsize=7.5, color=MUTED)
        if any(v < 0 for v in values):
            ax.axhline(0, color=RULE, linewidth=0.8)
        if values and all(v >= 0 for v in values):
            ax.set_ylim(0, max(values) * 1.18)
        else:
            ax.margins(y=0.15)
        _style_axes(ax)
        # rotate x labels when there are many of them, or they run long
        if len(periods) > 6 or max((len(p) for p in periods), default=0) > 7:
            for label in ax.get_xticklabels():
                label.set_rotation(45)
                label.set_horizontalalignment("right")

    _fig_save(fig, path)
