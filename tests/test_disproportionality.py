"""Tests for disproportionality statistics against hand-computed values."""
import numpy as np
import pandas as pd
import pytest

from app.analytics.disproportionality import _fit_gamma_prior, compute_disproportionality


@pytest.fixture
def simple_table():
    # N=10000 cases. Drug D in 100 cases, reaction R in 200 cases, both in 50.
    pair_counts = pd.DataFrame({"drug": ["D"], "reaction": ["R"], "cases": [50]})
    drug_totals = pd.Series({"D": 100})
    reaction_totals = pd.Series({"R": 200})
    return pair_counts, drug_totals, reaction_totals, 10000


def test_ror_and_prr_match_hand_calculation(simple_table):
    pair_counts, drug_totals, reaction_totals, n = simple_table
    out = compute_disproportionality(pair_counts, drug_totals, reaction_totals, n)
    row = out.iloc[0]
    # a=50 b=50 c=150 d=9750
    assert row["prr"] == pytest.approx((50 / 100) / (150 / 9900), rel=1e-4)
    assert row["ror"] == pytest.approx((50 / 50) / (150 / 9750), rel=1e-4)
    assert row["expected"] == pytest.approx(2.0)  # (100*200)/10000


def test_confidence_intervals_bracket_estimate(simple_table):
    pair_counts, drug_totals, reaction_totals, n = simple_table
    out = compute_disproportionality(pair_counts, drug_totals, reaction_totals, n)
    row = out.iloc[0]
    assert row["ror_lo"] < row["ror"] < row["ror_hi"]
    assert row["prr_lo"] < row["prr"] < row["prr_hi"]
    assert row["ror_lo"] > 1  # strong signal: lower bound above 1


def test_chi_square_significance(simple_table):
    pair_counts, drug_totals, reaction_totals, n = simple_table
    out = compute_disproportionality(pair_counts, drug_totals, reaction_totals, n)
    row = out.iloc[0]
    assert row["chi2"] > 3.84  # p < 0.05 for 1 df
    assert row["p_value"] < 0.05
    assert row["ic"] > 0  # more reports than expected


def test_ebgm_shrinkage_orders_signals():
    # strong (a=80) vs weak (a=3) signal over the same exposures
    pair_counts = pd.DataFrame(
        {"drug": ["D", "D"], "reaction": ["STRONG", "WEAK"], "cases": [80, 3]}
    )
    drug_totals = pd.Series({"D": 100})
    reaction_totals = pd.Series({"STRONG": 100, "WEAK": 100})
    out = compute_disproportionality(pair_counts, drug_totals, reaction_totals, 10000)
    strong = out[out["reaction"] == "STRONG"].iloc[0]
    weak = out[out["reaction"] == "WEAK"].iloc[0]
    assert strong["eb05"] > weak["eb05"]
    assert strong["ebgm"] > weak["ebgm"]
    # EBGM shrinks towards 1 relative to the raw ratio for small counts
    assert weak["ebgm"] >= 1.0


def test_zero_cell_correction():
    pair_counts = pd.DataFrame({"drug": ["D"], "reaction": ["R"], "cases": [10]})
    drug_totals = pd.Series({"D": 10})   # every drug case reports R -> b = 0
    reaction_totals = pd.Series({"R": 50})
    out = compute_disproportionality(pair_counts, drug_totals, reaction_totals, 1000)
    row = out.iloc[0]
    assert np.isfinite(row["ror"]) and np.isfinite(row["prr"])


def test_gamma_prior_fit_recovers_synthetic():
    rng = np.random.default_rng(42)
    theta = rng.gamma(shape=2.0, scale=0.5, size=400)  # true prior
    e = rng.uniform(1, 20, size=400)
    a = rng.poisson(e * theta)
    alpha, beta = _fit_gamma_prior(a.astype(float), e)
    assert np.isfinite(alpha) and np.isfinite(beta)
    assert alpha > 0 and beta > 0
