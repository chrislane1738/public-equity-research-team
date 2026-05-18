import math

import pytest

from tools.model_engine import (
    project_revenue,
    project_segment_revenue,
    project_fcf,
    project_fcf_path,
    build_projection,
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


def test_build_projection_assembles_the_dcf_contract():
    seg = project_segment_revenue([
        {"name": "Core", "base": 800, "growth_path": [0.10, 0.10]},
        {"name": "Legacy", "base": 200, "growth_path": [-0.05, -0.05]},
    ])
    proj = build_projection(
        ticker="TEST",
        base_year_label="TTM ending 2026-03-31",
        segment_result=seg,
        ebit_margin_path=[0.25, 0.26],
        tax_rate=0.21,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.07,
        wc_change_pct_revenue=0.01,
    )
    assert proj["ticker"] == "TEST"
    assert proj["horizon"] == 2
    assert proj["base_year"]["label"] == "TTM ending 2026-03-31"
    # revenue path is the segment-summed total, not a re-derived growth path
    assert proj["revenue"] == seg["total_revenue"]
    assert proj["implied_growth"] == seg["implied_growth_path"]
    # year 1: Core 800*1.10=880, Legacy 200*0.95=190 → rev 1070
    #         ebit 1070*0.25=267.5, nopat 267.5*0.79=211.325,
    #         da 53.5, capex 74.9, wc 10.7 → fcf 211.325+53.5-74.9-10.7=179.225
    assert math.isclose(proj["revenue"][0], 1070)
    assert math.isclose(proj["ebit"][0], 267.5)
    assert math.isclose(proj["unlevered_fcf"][0], 179.225, rel_tol=1e-9)
    assert proj["segments"] == seg["segments"]
    assert proj["drivers"]["tax_rate"] == 0.21
    assert proj["drivers"]["ebit_margin_path"] == [0.25, 0.26]
    assert "model skill" in proj["_source"]


def test_build_projection_rejects_margin_path_horizon_mismatch():
    seg = project_segment_revenue([
        {"name": "Solo", "base": 500, "growth_path": [0.10, 0.10]},
    ])
    with pytest.raises(ValueError, match="same length"):
        build_projection(
            ticker="X", base_year_label="TTM", segment_result=seg,
            ebit_margin_path=[0.25],  # 1 vs horizon 2
            tax_rate=0.21, da_pct_revenue=0.05,
            capex_pct_revenue=0.07, wc_change_pct_revenue=0.01,
        )
