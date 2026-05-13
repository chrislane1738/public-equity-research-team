import math

import pytest

from backend.tools.dcf_engine import (
    compute_wacc,
    project_revenue,
    project_fcf,
    terminal_ggm,
    terminal_exit_multiple,
    blend_terminal,
    discount_to_pv,
    equity_value,
    sensitivity_grid_ggm,
    sensitivity_grid_exit,
    EXIT_MULT_HAIRCUT,
)


def test_compute_wacc_capm():
    # equity 80%, debt 20%, beta 1.2, rf 4%, erp 5.5%, cost_debt 5%, tax 21%
    # cost_equity = 4 + 1.2 * 5.5 = 10.6
    # after_tax_kd = 5 * (1 - 0.21) = 3.95
    # wacc = 0.8 * 10.6 + 0.2 * 3.95 = 8.48 + 0.79 = 9.27
    wacc = compute_wacc(
        beta=1.2, rf=4.0, erp=5.5,
        cost_of_debt=5.0, tax_rate=0.21,
        weight_equity=0.8, weight_debt=0.2,
    )
    assert math.isclose(wacc, 9.27, rel_tol=1e-3)


def test_compute_wacc_uses_default_erp_5_5():
    wacc = compute_wacc(beta=1.0, rf=4.0,
                        cost_of_debt=5.0, tax_rate=0.21,
                        weight_equity=1.0, weight_debt=0.0)
    # cost_equity = 4 + 1.0 * 5.5 = 9.5; debt weight 0 → wacc = 9.5
    assert math.isclose(wacc, 9.5, rel_tol=1e-6)


def test_project_revenue_compounds_growth_path():
    revs = project_revenue(base=1000, growth_path=[0.20, 0.15, 0.10, 0.08, 0.05])
    assert math.isclose(revs[0], 1200)
    assert math.isclose(revs[1], 1380)
    assert math.isclose(revs[-1], 1200 * 1.15 * 1.10 * 1.08 * 1.05)


def test_project_fcf_walks_revenue_through_ebit_to_fcf():
    out = project_fcf(
        base_revenue=1000,
        growth_path=[0.10, 0.10],
        ebit_margin_path=[0.30, 0.30],
        tax_rate=0.21,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.07,
        wc_change_pct_revenue=0.01,
    )
    # year 1: rev 1100, ebit 330, ebit*(1-t)=260.7, +da 55, -capex 77, -wc 11 → 227.7
    assert len(out) == 2
    assert math.isclose(out[0]["revenue"], 1100)
    assert math.isclose(out[0]["ebit"], 330)
    assert math.isclose(out[0]["fcf"], 260.7 + 55 - 77 - 11, rel_tol=1e-6)


def test_terminal_ggm_perpetuity_formula():
    # FCF_t = 100, g=2%, wacc=10% → TV = 100 * 1.02 / (0.10 - 0.02) = 1275
    tv = terminal_ggm(fcf_t=100, growth=2.0, wacc=10.0)
    assert math.isclose(tv, 1275, rel_tol=1e-6)


def test_terminal_ggm_caps_growth_at_min_rf_and_3pct():
    # rf=4%, requested g=5% → cap to min(4, 3) = 3
    tv = terminal_ggm(fcf_t=100, growth=5.0, wacc=10.0, rf=4.0)
    expected = 100 * 1.03 / (0.10 - 0.03)
    assert math.isclose(tv, expected, rel_tol=1e-6)


def test_terminal_exit_multiple_applies_haircut_by_default():
    # peer median EV/EBITDA = 20, haircut to 0.85 → 17. EBITDA_T=200 → TV=3400
    tv = terminal_exit_multiple(ebitda_t=200, peer_median_multiple=20)
    assert math.isclose(tv, 200 * 20 * EXIT_MULT_HAIRCUT)


def test_terminal_exit_multiple_caps_at_sector_p75():
    # peer median 30, p75 cap 22 → effective multiple = min(30 * haircut, 22) = 22
    tv = terminal_exit_multiple(ebitda_t=100, peer_median_multiple=30,
                                sector_p75_cap=22)
    assert math.isclose(tv, 100 * 22)


def test_blend_terminal_default_50_50():
    assert math.isclose(blend_terminal(ggm=100, exit_mult=200), 150)


def test_blend_terminal_custom_weight():
    assert math.isclose(blend_terminal(ggm=100, exit_mult=200, weight_ggm=0.7), 130)


def test_discount_to_pv_returns_explicit_terminal_and_ev():
    cashflows = [100, 110, 121]
    out = discount_to_pv(cashflows=cashflows, terminal=1000, wacc=10.0)
    expected_explicit = 100 / 1.1 + 110 / 1.1**2 + 121 / 1.1**3
    expected_terminal = 1000 / 1.1**3
    assert math.isclose(out["pv_explicit"], expected_explicit, rel_tol=1e-6)
    assert math.isclose(out["pv_terminal"], expected_terminal, rel_tol=1e-6)
    assert math.isclose(out["ev"], expected_explicit + expected_terminal, rel_tol=1e-6)


def test_equity_value_subtracts_net_debt_then_divides_by_shares():
    out = equity_value(ev=1000, net_debt=200, shares=10)
    assert math.isclose(out["equity_value"], 800)
    assert math.isclose(out["implied_price"], 80)


def test_sensitivity_grid_ggm_returns_2d_dict():
    grid = sensitivity_grid_ggm(
        wacc_axis=[8.0, 10.0, 12.0],
        growth_axis=[1.5, 2.5, 3.5],
        fcf_t=100,
    )
    assert (10.0, 2.5) in grid
    expected = 100 * 1.025 / (0.10 - 0.025)
    assert math.isclose(grid[(10.0, 2.5)], expected, rel_tol=1e-6)


def test_sensitivity_grid_exit_returns_2d_dict():
    grid = sensitivity_grid_exit(
        wacc_axis=[8.0, 10.0],
        multiple_axis=[15.0, 20.0],
        ebitda_t=100,
        explicit_pv=500,
        years_to_terminal=5,
        net_debt=0,
        shares=10,
    )
    assert (10.0, 20.0) in grid
    # implied price for (10%, 20x)
    tv = 100 * 20
    pv_tv = tv / (1.10 ** 5)
    ev = 500 + pv_tv
    expected_price = (ev - 0) / 10
    assert math.isclose(grid[(10.0, 20.0)], expected_price, rel_tol=1e-6)
