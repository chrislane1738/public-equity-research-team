"""Model engine — forward-projection math for the desk's 3-statement model.

Pure functions, no I/O. Growth rates are fractional (0.10 = 10%); tax rate is
fractional (0.21 = 21%). This module owns the desk's single revenue/FCF
projection — `dcf` consumes its output via `model/projection.json` rather than
projecting independently.
"""


def project_revenue(base: float, growth_path: list[float]) -> list[float]:
    """Compound `base` by each fractional growth in `growth_path` (e.g. 0.10 = 10%)."""
    revs: list[float] = []
    cur = base
    for g in growth_path:
        cur = cur * (1 + g)
        revs.append(cur)
    return revs


def project_segment_revenue(segments: list[dict]) -> dict:
    """Bottom-up revenue build — project each business segment, sum to a total,
    and derive the implied revenue-weighted total growth path.

    Each `segments` entry is a dict {"name": str, "base": float,
    "growth_path": list[float]} with fractional growth rates (0.10 = 10%).
    Every segment must share the same projection horizon. A single-segment
    list is valid (the build degenerates to that segment's own path).

    Returns a dict with:
      segments              per-segment {name, base, growth_path, revenue[]}
      total_base            sum of segment base revenues
      total_revenue         per-year sum across segments
      implied_growth_path   fractional blended growth implied by the segment sum
    """
    if not segments:
        raise ValueError("segments must be non-empty")
    horizon = len(segments[0]["growth_path"])
    if horizon == 0:
        raise ValueError("growth_path must be non-empty")
    if any(len(s["growth_path"]) != horizon for s in segments):
        raise ValueError("all segments must share the same projection horizon")

    projected = [
        {
            "name": s["name"],
            "base": s["base"],
            "growth_path": list(s["growth_path"]),
            "revenue": project_revenue(s["base"], s["growth_path"]),
        }
        for s in segments
    ]

    total_base = sum(s["base"] for s in segments)
    total_revenue = [
        sum(p["revenue"][y] for p in projected) for y in range(horizon)
    ]

    implied_growth_path: list[float] = []
    prev = total_base
    for rev in total_revenue:
        implied_growth_path.append(rev / prev - 1 if prev else float("nan"))
        prev = rev

    return {
        "segments": projected,
        "total_base": total_base,
        "total_revenue": total_revenue,
        "implied_growth_path": implied_growth_path,
    }


def project_fcf_path(
    revenue_path: list[float],
    ebit_margin_path: list[float],
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    wc_change_pct_revenue: float,
) -> list[dict]:
    """Walk an explicit revenue path → EBIT → NOPAT → unlevered FCF per year.

    FCF = EBIT*(1-t) + D&A - Capex - ΔWC.
    """
    if len(revenue_path) != len(ebit_margin_path):
        raise ValueError("revenue_path and ebit_margin_path must have same length")
    out: list[dict] = []
    for rev, margin in zip(revenue_path, ebit_margin_path):
        ebit = rev * margin
        nopat = ebit * (1 - tax_rate)
        da = rev * da_pct_revenue
        capex = rev * capex_pct_revenue
        wc_change = rev * wc_change_pct_revenue
        fcf = nopat + da - capex - wc_change
        out.append({
            "revenue": rev, "ebit": ebit, "nopat": nopat, "da": da,
            "capex": capex, "wc_change": wc_change, "fcf": fcf,
        })
    return out


def project_fcf(
    base_revenue: float,
    growth_path: list[float],
    ebit_margin_path: list[float],
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    wc_change_pct_revenue: float,
) -> list[dict]:
    """Compound `base_revenue` by `growth_path`, then walk revenue → FCF."""
    if len(growth_path) != len(ebit_margin_path):
        raise ValueError("growth_path and ebit_margin_path must have same length")
    revenues = project_revenue(base_revenue, growth_path)
    return project_fcf_path(
        revenues, ebit_margin_path, tax_rate,
        da_pct_revenue, capex_pct_revenue, wc_change_pct_revenue,
    )


def build_projection(
    ticker: str,
    base_year_label: str,
    segment_result: dict,
    ebit_margin_path: list[float],
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    wc_change_pct_revenue: float,
) -> dict:
    """Assemble the base-case projection contract consumed by the `dcf` skill.

    `segment_result` is the dict returned by `project_segment_revenue`. The
    segment-summed total revenue is walked to unlevered FCF; the result is
    packaged into the `model/projection.json` shape: the 5-year revenue / EBIT /
    NOPAT / D&A / capex / ΔWC / unlevered-FCF path, the segment build, and the
    driver set.
    """
    revenue_path = segment_result["total_revenue"]
    walk = project_fcf_path(
        revenue_path, ebit_margin_path, tax_rate,
        da_pct_revenue, capex_pct_revenue, wc_change_pct_revenue,
    )
    return {
        "ticker": ticker,
        "horizon": len(revenue_path),
        "base_year": {"label": base_year_label},
        "revenue": revenue_path,
        "implied_growth": segment_result["implied_growth_path"],
        "ebit": [y["ebit"] for y in walk],
        "nopat": [y["nopat"] for y in walk],
        "da": [y["da"] for y in walk],
        "capex": [y["capex"] for y in walk],
        "wc_change": [y["wc_change"] for y in walk],
        "unlevered_fcf": [y["fcf"] for y in walk],
        "segments": segment_result["segments"],
        "drivers": {
            "ebit_margin_path": list(ebit_margin_path),
            "tax_rate": tax_rate,
            "da_pct_revenue": da_pct_revenue,
            "capex_pct_revenue": capex_pct_revenue,
            "wc_change_pct_revenue": wc_change_pct_revenue,
        },
        "_source": "model skill, phase: build",
    }
