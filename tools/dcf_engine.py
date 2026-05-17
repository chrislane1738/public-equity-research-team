"""DCF engine — WACC, FCF projection, terminal value, sensitivity grids.

All rates expressed as percent (e.g. 10.0 = 10%, not 0.10). Internally
divided by 100 where formulas need a decimal.
"""
from collections.abc import Iterable


# Mid-cycle haircut applied to peer median EV/EBITDA when picking the exit multiple
EXIT_MULT_HAIRCUT = 0.85
DEFAULT_ERP = 5.5
DEFAULT_TERMINAL_GROWTH_CAP = 3.0  # the "min(Rf, 3%)" floor


def compute_wacc(
    beta: float,
    rf: float,
    cost_of_debt: float,
    tax_rate: float,
    weight_equity: float,
    weight_debt: float,
    erp: float = DEFAULT_ERP,
) -> float:
    """CAPM-based WACC. Inputs as percent; output as percent."""
    cost_equity = rf + beta * erp
    after_tax_kd = cost_of_debt * (1 - tax_rate)
    return weight_equity * cost_equity + weight_debt * after_tax_kd


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

    This is the first step of a segment-driven DCF: rather than assuming one
    top-level growth path, total revenue is built from the parts. Each segment
    carries its own justified growth path; the blended total growth is an
    *output*, weighted automatically by segment size.

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


def project_fcf(
    base_revenue: float,
    growth_path: list[float],
    ebit_margin_path: list[float],
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    wc_change_pct_revenue: float,
) -> list[dict]:
    """Walk revenue → EBIT → NOPAT → FCF for each forecast year.

    FCF = EBIT*(1-t) + D&A - Capex - ΔWC.
    """
    if len(growth_path) != len(ebit_margin_path):
        raise ValueError("growth_path and ebit_margin_path must have same length")
    revenues = project_revenue(base_revenue, growth_path)
    out: list[dict] = []
    for rev, margin in zip(revenues, ebit_margin_path):
        ebit = rev * margin
        nopat = ebit * (1 - tax_rate)
        da = rev * da_pct_revenue
        capex = rev * capex_pct_revenue
        wc_change = rev * wc_change_pct_revenue
        fcf = nopat + da - capex - wc_change
        out.append({
            "revenue": rev,
            "ebit": ebit,
            "nopat": nopat,
            "da": da,
            "capex": capex,
            "wc_change": wc_change,
            "fcf": fcf,
        })
    return out


def terminal_ggm(fcf_t: float, growth: float, wacc: float, rf: float | None = None) -> float:
    """Gordon Growth: FCF_T * (1+g) / (WACC - g). g capped at min(Rf, 3%)."""
    cap = DEFAULT_TERMINAL_GROWTH_CAP
    if rf is not None:
        cap = min(cap, rf)
    g = min(growth, cap)
    g_dec = g / 100.0
    w_dec = wacc / 100.0
    if w_dec <= g_dec:
        raise ValueError(f"WACC ({wacc}%) must exceed growth ({g}%) for GGM")
    return fcf_t * (1 + g_dec) / (w_dec - g_dec)


def terminal_exit_multiple(
    ebitda_t: float,
    peer_median_multiple: float,
    sector_p75_cap: float | None = None,
    haircut: float = EXIT_MULT_HAIRCUT,
) -> float:
    """Exit Multiple TV = EBITDA_T * multiple.

    `multiple` defaults to peer_median * haircut. If `sector_p75_cap` is given,
    the multiple is further capped at that value to prevent bubble-period
    multiples from poisoning the terminal.
    """
    multiple = peer_median_multiple * haircut
    if sector_p75_cap is not None:
        multiple = min(multiple, sector_p75_cap)
    return ebitda_t * multiple


def blend_terminal(ggm: float, exit_mult: float, weight_ggm: float = 0.5) -> float:
    return weight_ggm * ggm + (1 - weight_ggm) * exit_mult


def discount_to_pv(cashflows: list[float], terminal: float, wacc: float) -> dict:
    """Return PV of explicit cashflows, PV of terminal value, and total EV.

    Terminal is discounted to year 0 from the END of the explicit period
    (year = len(cashflows))."""
    w = wacc / 100.0
    pv_explicit = sum(cf / ((1 + w) ** (i + 1)) for i, cf in enumerate(cashflows))
    pv_terminal = terminal / ((1 + w) ** len(cashflows))
    return {"pv_explicit": pv_explicit, "pv_terminal": pv_terminal,
            "ev": pv_explicit + pv_terminal}


def equity_value(ev: float, net_debt: float, shares: float) -> dict:
    eq = ev - net_debt
    return {"equity_value": eq, "implied_price": eq / shares if shares > 0 else float("nan")}


def sensitivity_grid_ggm(
    wacc_axis: Iterable[float],
    growth_axis: Iterable[float],
    fcf_t: float,
) -> dict[tuple[float, float], float]:
    """Return TV at each (WACC, growth) combination."""
    out: dict[tuple[float, float], float] = {}
    for w in wacc_axis:
        for g in growth_axis:
            try:
                out[(w, g)] = terminal_ggm(fcf_t=fcf_t, growth=g, wacc=w)
            except ValueError:
                out[(w, g)] = float("nan")
    return out


def sensitivity_grid_exit(
    wacc_axis: Iterable[float],
    multiple_axis: Iterable[float],
    ebitda_t: float,
    explicit_pv: float,
    years_to_terminal: int,
    net_debt: float,
    shares: float,
) -> dict[tuple[float, float], float]:
    """Return implied price per share at each (WACC, exit multiple) combination.

    `multiple_axis` values are applied directly to EBITDA_T as-is — NO haircut
    or sector cap is applied here. Callers should pre-haircut their multiples
    (e.g. via `terminal_exit_multiple`) before passing them in if a scenario
    grid relative to a peer median is desired.
    """
    out: dict[tuple[float, float], float] = {}
    for w in wacc_axis:
        for m in multiple_axis:
            tv = ebitda_t * m
            pv_tv = tv / ((1 + w / 100.0) ** years_to_terminal)
            ev = explicit_pv + pv_tv
            eq = ev - net_debt
            out[(w, m)] = eq / shares if shares > 0 else float("nan")
    return out
