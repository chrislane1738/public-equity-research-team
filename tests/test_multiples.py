import math

import pytest

from backend.tools.multiples import (
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
