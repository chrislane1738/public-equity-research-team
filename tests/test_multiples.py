import math

import pytest

from tools.multiples import (
    enterprise_value,
    ev_to_ebitda,
    pe_ratio,
    ev_to_sales,
    ev_to_crpo,
    price_to_ffo,
    aggregate_peer_multiples,
)


def test_enterprise_value_adds_debt_subtracts_cash():
    ev = enterprise_value(market_cap=1000, total_debt=200, cash=50)
    assert ev == 1150


def test_ev_to_ebitda_divides_ev_by_ebitda():
    assert ev_to_ebitda(ev=1000, ebitda=100) == 10.0


def test_ev_to_ebitda_returns_nan_when_ebitda_nonpositive():
    assert math.isnan(ev_to_ebitda(ev=1000, ebitda=0))
    assert math.isnan(ev_to_ebitda(ev=1000, ebitda=-50))


def test_pe_divides_price_by_eps():
    assert pe_ratio(price=100, eps=5) == 20.0


def test_pe_returns_nan_when_eps_nonpositive():
    assert math.isnan(pe_ratio(price=100, eps=0))
    assert math.isnan(pe_ratio(price=100, eps=-2))


def test_ev_to_sales_divides_ev_by_revenue():
    assert ev_to_sales(ev=1000, revenue=200) == 5.0


def test_ev_to_crpo_divides_ev_by_crpo():
    assert ev_to_crpo(ev=1000, crpo=400) == 2.5


def test_ev_to_crpo_returns_nan_when_crpo_zero():
    assert math.isnan(ev_to_crpo(ev=1000, crpo=0))


def test_price_to_ffo_divides_price_by_ffo_per_share():
    assert price_to_ffo(price=50, ffo_per_share=5) == 10.0


def test_aggregate_peer_multiples_returns_median_and_quartiles():
    peers = [
        {"symbol": "A", "market_cap": 1000, "total_debt": 100, "cash": 50,
         "ebitda": 100, "revenue": 500, "eps": 5, "price": 100},
        {"symbol": "B", "market_cap": 2000, "total_debt": 200, "cash": 100,
         "ebitda": 250, "revenue": 1000, "eps": 8, "price": 80},
        {"symbol": "C", "market_cap": 3000, "total_debt": 0, "cash": 200,
         "ebitda": 300, "revenue": 1500, "eps": 12, "price": 120},
    ]
    out = aggregate_peer_multiples(peers)
    # EV/EBITDA per peer: A 10.5, B 8.4, C 9.333... → median ~9.33
    assert "ev_to_ebitda" in out
    assert math.isclose(out["ev_to_ebitda"]["median"], 9.333333, rel_tol=1e-3)
    assert "p25" in out["ev_to_ebitda"]
    assert "p75" in out["ev_to_ebitda"]


def test_aggregate_peer_multiples_drops_nans():
    peers = [
        {"symbol": "A", "market_cap": 1000, "total_debt": 0, "cash": 0,
         "ebitda": 100, "revenue": 500, "eps": 5, "price": 100},
        {"symbol": "B", "market_cap": 1000, "total_debt": 0, "cash": 0,
         "ebitda": 0, "revenue": 500, "eps": 0, "price": 100},  # nan-producing
    ]
    out = aggregate_peer_multiples(peers)
    assert math.isclose(out["ev_to_ebitda"]["median"], 10.0)
    assert math.isclose(out["pe"]["median"], 20.0)


def test_aggregate_peer_multiples_p25_p75_have_correct_values():
    # EV/EBITDA per peer for these 3: A=10.5, B=8.4, C=9.333...
    # Sorted: [8.4, 9.333..., 10.5]
    # p25 with linear interp at k=0.5 → 8.4 + (9.333-8.4)*0.5 ≈ 8.867
    # p75 with linear interp at k=1.5 → 9.333 + (10.5-9.333)*0.5 ≈ 9.917
    peers = [
        {"symbol": "A", "market_cap": 1000, "total_debt": 100, "cash": 50,
         "ebitda": 100, "revenue": 500, "eps": 5, "price": 100},
        {"symbol": "B", "market_cap": 2000, "total_debt": 200, "cash": 100,
         "ebitda": 250, "revenue": 1000, "eps": 8, "price": 80},
        {"symbol": "C", "market_cap": 3000, "total_debt": 0, "cash": 200,
         "ebitda": 300, "revenue": 1500, "eps": 12, "price": 120},
    ]
    out = aggregate_peer_multiples(peers)
    assert math.isclose(out["ev_to_ebitda"]["p25"], 8.867, rel_tol=1e-3)
    assert math.isclose(out["ev_to_ebitda"]["p75"], 9.917, rel_tol=1e-3)
    assert out["ev_to_ebitda"]["n"] == 3


def test_aggregate_peer_multiples_includes_crpo_when_any_peer_has_it():
    peers_with = [
        {"symbol": "A", "market_cap": 1000, "total_debt": 0, "cash": 0,
         "ebitda": 100, "revenue": 500, "eps": 5, "price": 100, "crpo": 400},
    ]
    peers_without = [
        {"symbol": "A", "market_cap": 1000, "total_debt": 0, "cash": 0,
         "ebitda": 100, "revenue": 500, "eps": 5, "price": 100},
    ]
    assert "ev_to_crpo" in aggregate_peer_multiples(peers_with)
    assert "ev_to_crpo" not in aggregate_peer_multiples(peers_without)
    assert "price_to_ffo" not in aggregate_peer_multiples(peers_with)


def test_aggregate_peer_multiples_handles_empty_peer_list():
    out = aggregate_peer_multiples([])
    # Always-present keys still emit summaries with n=0
    assert out["ev_to_ebitda"]["n"] == 0
    assert math.isnan(out["ev_to_ebitda"]["median"])
    assert "ev_to_crpo" not in out  # conditional keys absent when no peers
