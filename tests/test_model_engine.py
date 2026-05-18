import math

import pytest

from tools.model_engine import (
    project_revenue,
    project_segment_revenue,
    project_fcf,
    project_fcf_path,
)


def test_project_revenue_compounds_growth_path():
    revs = project_revenue(base=1000, growth_path=[0.20, 0.15, 0.10, 0.08, 0.05])
    assert math.isclose(revs[0], 1200)
    assert math.isclose(revs[1], 1380)
    assert math.isclose(revs[-1], 1200 * 1.15 * 1.10 * 1.08 * 1.05)


def test_project_segment_revenue_sums_segments_and_implies_blended_growth():
    out = project_segment_revenue([
        {"name": "A", "base": 800, "growth_path": [0.10, 0.10]},
        {"name": "B", "base": 200, "growth_path": [0.05, 0.05]},
    ])
    assert math.isclose(out["total_base"], 1000)
    assert math.isclose(out["total_revenue"][0], 1090)
    assert math.isclose(out["total_revenue"][1], 1188.5)
    assert math.isclose(out["implied_growth_path"][0], 0.09, rel_tol=1e-9)
    assert math.isclose(out["implied_growth_path"][1], 1188.5 / 1090 - 1, rel_tol=1e-9)
    assert math.isclose(out["segments"][0]["revenue"][0], 880, rel_tol=1e-9)
    assert math.isclose(out["segments"][0]["revenue"][1], 968, rel_tol=1e-9)


def test_project_segment_revenue_single_segment_matches_its_own_path():
    out = project_segment_revenue([
        {"name": "Solo", "base": 500, "growth_path": [0.20, 0.10]},
    ])
    assert out["total_revenue"] == [600, 660]
    assert math.isclose(out["implied_growth_path"][0], 0.20)
    assert math.isclose(out["implied_growth_path"][1], 0.10)


def test_project_segment_revenue_blends_a_grower_and_a_decliner():
    out = project_segment_revenue([
        {"name": "Grower", "base": 900, "growth_path": [0.10]},
        {"name": "Runoff", "base": 100, "growth_path": [-0.10]},
    ])
    assert math.isclose(out["total_revenue"][0], 1080)
    assert math.isclose(out["implied_growth_path"][0], 0.08, rel_tol=1e-9)


def test_project_segment_revenue_rejects_mismatched_horizons():
    with pytest.raises(ValueError, match="same projection horizon"):
        project_segment_revenue([
            {"name": "A", "base": 100, "growth_path": [0.1, 0.1]},
            {"name": "B", "base": 100, "growth_path": [0.1]},
        ])


def test_project_segment_revenue_rejects_empty():
    with pytest.raises(ValueError, match="non-empty"):
        project_segment_revenue([])


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
    assert len(out) == 2
    assert math.isclose(out[0]["revenue"], 1100)
    assert math.isclose(out[0]["ebit"], 330)
    assert math.isclose(out[0]["fcf"], 260.7 + 55 - 77 - 11, rel_tol=1e-6)


def test_project_fcf_path_matches_project_fcf_on_equivalent_revenue():
    explicit = project_fcf_path(
        revenue_path=[1100, 1210],
        ebit_margin_path=[0.30, 0.30],
        tax_rate=0.21,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.07,
        wc_change_pct_revenue=0.01,
    )
    compounded = project_fcf(
        base_revenue=1000, growth_path=[0.10, 0.10],
        ebit_margin_path=[0.30, 0.30], tax_rate=0.21,
        da_pct_revenue=0.05, capex_pct_revenue=0.07, wc_change_pct_revenue=0.01,
    )
    for e, c in zip(explicit, compounded):
        assert math.isclose(e["fcf"], c["fcf"], rel_tol=1e-9)


def test_project_fcf_path_rejects_length_mismatch():
    with pytest.raises(ValueError, match="same length"):
        project_fcf_path(
            revenue_path=[100, 110],
            ebit_margin_path=[0.30],
            tax_rate=0.21, da_pct_revenue=0.05,
            capex_pct_revenue=0.07, wc_change_pct_revenue=0.01,
        )
