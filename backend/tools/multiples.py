"""Manually computed valuation multiples — does NOT trust FMP's pre-computed ratios.

All inputs in raw currency units (USD). Ratios that would divide by zero or by a
non-positive denominator return float('nan'); aggregators drop NaNs before
computing percentiles.
"""
import math
from statistics import median
from typing import Iterable


def enterprise_value(market_cap: float, total_debt: float, cash: float) -> float:
    return market_cap + total_debt - cash


def _safe_div(num: float, denom: float) -> float:
    if denom is None or denom <= 0 or math.isnan(num) or math.isnan(denom):
        return float("nan")
    return num / denom


def ev_to_ebitda(ev: float, ebitda: float) -> float:
    return _safe_div(ev, ebitda)


def pe_ratio(price: float, eps: float) -> float:
    return _safe_div(price, eps)


def ev_to_sales(ev: float, revenue: float) -> float:
    return _safe_div(ev, revenue)


def ev_to_crpo(ev: float, crpo: float) -> float:
    """SaaS-flavored multiple: EV / current Remaining Performance Obligations."""
    return _safe_div(ev, crpo)


def price_to_ffo(price: float, ffo_per_share: float) -> float:
    """REIT-flavored multiple: Price / Funds From Operations per share."""
    return _safe_div(price, ffo_per_share)


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (pct in [0, 100])."""
    if not values:
        return float("nan")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _summary(values: Iterable[float]) -> dict[str, float]:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return {"median": float("nan"), "p25": float("nan"),
                "p75": float("nan"), "n": 0}
    return {
        "median": median(clean),
        "p25": _percentile(clean, 25),
        "p75": _percentile(clean, 75),
        "n": len(clean),
    }


def aggregate_peer_multiples(peers: list[dict]) -> dict[str, dict[str, float]]:
    """Compute per-peer multiples then aggregate to median / p25 / p75.

    Each peer dict expects: market_cap, total_debt, cash, ebitda, revenue,
    eps, price. Optional: crpo, ffo_per_share.
    """
    ev_ebitda, pe, ev_sales, ev_crpo, p_ffo = [], [], [], [], []
    for p in peers:
        ev = enterprise_value(p.get("market_cap", 0),
                              p.get("total_debt", 0),
                              p.get("cash", 0))
        ev_ebitda.append(ev_to_ebitda(ev, p.get("ebitda", float("nan"))))
        pe.append(pe_ratio(p.get("price", float("nan")), p.get("eps", float("nan"))))
        ev_sales.append(ev_to_sales(ev, p.get("revenue", float("nan"))))
        if p.get("crpo") is not None:
            ev_crpo.append(ev_to_crpo(ev, p["crpo"]))
        if p.get("ffo_per_share") is not None:
            p_ffo.append(price_to_ffo(p.get("price", float("nan")), p["ffo_per_share"]))

    out: dict[str, dict[str, float]] = {
        "ev_to_ebitda": _summary(ev_ebitda),
        "pe": _summary(pe),
        "ev_to_sales": _summary(ev_sales),
    }
    if ev_crpo:
        out["ev_to_crpo"] = _summary(ev_crpo)
    if p_ffo:
        out["price_to_ffo"] = _summary(p_ffo)
    return out
