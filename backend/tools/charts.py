"""Matplotlib renderers for deck/report charts. Transparent backgrounds, no
external style — output PNGs are deck-embed friendly."""
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _fig_save(fig, path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, transparent=True, bbox_inches="tight", dpi=150)
    plt.close(fig)


def peer_share_chart(peers: list[dict], path: Path, title: str = "Peer share") -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    symbols = [p["symbol"] for p in peers]
    shares = [p["share"] for p in peers]
    ax.bar(symbols, shares)
    ax.set_title(title)
    ax.set_ylabel("Share")
    _fig_save(fig, path)


def box_plot(metric_name: str, peer_values: list[float],
             target_value: float | None, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.boxplot(peer_values, vert=True, showmeans=True, tick_labels=[metric_name])
    if target_value is not None:
        ax.axhline(target_value, linestyle="--", color="red",
                   label=f"target = {target_value:.1f}")
        ax.legend(loc="best")
    ax.set_title(f"{metric_name} — peer distribution")
    _fig_save(fig, path)


def football_field(scenarios: list[tuple[str, float, float]],
                   current_price: float, path: Path) -> None:
    """Horizontal bars showing low–high range per scenario, plus current price line."""
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [s[0] for s in scenarios]
    lows = np.array([s[1] for s in scenarios])
    highs = np.array([s[2] for s in scenarios])
    widths = highs - lows
    y = np.arange(len(labels))
    ax.barh(y, widths, left=lows, height=0.55)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.axvline(current_price, color="black", linestyle="--",
               label=f"current = ${current_price:.0f}")
    ax.set_xlabel("Implied price ($)")
    ax.set_title("Football field — valuation triangulation")
    ax.legend(loc="best")
    _fig_save(fig, path)


def sensitivity_heatmap(grid: dict[tuple[float, float], float],
                        x_axis_name: str, y_axis_name: str, path: Path) -> None:
    """Render a 2-D dict as a heatmap. Keys are (y_value, x_value)."""
    ys = sorted({k[0] for k in grid.keys()})
    xs = sorted({k[1] for k in grid.keys()})
    matrix = np.array([[grid.get((y, x), float("nan")) for x in xs] for y in ys])

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn")
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([f"{x:g}" for x in xs])
    ax.set_yticks(range(len(ys)))
    ax.set_yticklabels([f"{y:g}" for y in ys])
    ax.set_xlabel(x_axis_name)
    ax.set_ylabel(y_axis_name)
    ax.set_title("Sensitivity")
    for i in range(len(ys)):
        for j in range(len(xs)):
            v = matrix[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax)
    _fig_save(fig, path)


def catalyst_timeline(events: list[tuple[str, str]], path: Path) -> None:
    """Plot date-labeled catalysts as points on a horizontal time axis."""
    fig, ax = plt.subplots(figsize=(10, 3.5))
    dates = [datetime.strptime(d, "%Y-%m-%d") for d, _ in events]
    labels = [lbl for _, lbl in events]
    ax.scatter(dates, [1] * len(dates), s=80)
    for d, lbl in zip(dates, labels):
        ax.annotate(lbl, (d, 1), xytext=(0, 12), textcoords="offset points",
                    ha="center", rotation=20, fontsize=8)
    ax.set_yticks([])
    ax.set_title("Catalyst timeline")
    fig.autofmt_xdate()
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
    ax.plot(dates, closes, label="Close")
    for w in sma_windows:
        if len(closes) < w:
            continue
        sma = np.convolve(closes, np.ones(w) / w, mode="valid")
        ax.plot(dates[w - 1:], sma, label=f"SMA{w}")
    ax.set_title(title)
    ax.legend(loc="best")
    fig.autofmt_xdate()
    _fig_save(fig, path)
