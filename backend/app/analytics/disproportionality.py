"""Disproportionality analysis for FAERS signal detection.

Implements the standard pharmacovigilance measures computed on the
drug x reaction 2x2 contingency table within the FAERS corpus:

    a = cases reporting drug+reaction      b = cases reporting drug only
    c = cases reporting reaction only      d = all other cases

- PRR  — proportional reporting ratio (+ 95% CI on log scale)
- ROR  — reporting odds ratio (+ 95% CI)
- chi2 — Yates-corrected chi-square + p-value
- IC   — Bayesian information component, log2((a+0.5)/(E+0.5))
- EBGM — empirical Bayes geometric mean via a gamma-Poisson prior fitted
         by EM (DuMouchel-style MGPS); EB05 is the posterior 5th percentile,
         the conservative "lower bound" used to flag strong signals.

Everything is vectorised with numpy for corpus-scale speed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, special, stats

Z = 1.96  # 95% confidence


def _fit_gamma_prior(a: np.ndarray, e: np.ndarray) -> tuple[float, float]:
    """Fit Gamma(alpha, beta) prior on reporting rate ratios via EM.

    Model:  a_i ~ Poisson(e_i * theta_i),  theta_i ~ Gamma(alpha, beta).
    EM fixed point for alpha:  digamma(alpha) - ln(alpha) = mubar_l - ln(mubar_t)
    then beta = alpha / mean(E[theta]).
    """
    keep = e >= 1.0
    if keep.sum() < 30:
        # small corpus: fall back to a weakly-informative Gamma(1, 1) prior
        # (simple additive shrinkage towards no disproportionality)
        return 1.0, 1.0
    a_k, e_k = a[keep], e[keep]

    alpha, beta = 2.0, 1.0
    for _ in range(30):
        m_t = (a_k + alpha) / (e_k + beta)            # E[theta_i]
        l_t = special.digamma(a_k + alpha) - np.log(e_k + beta)  # E[ln theta_i]
        mubar_t, mubar_l = float(m_t.mean()), float(l_t.mean())
        target = mubar_l - np.log(mubar_t)

        def solve(x: float) -> float:
            return special.digamma(x) - np.log(x) - target

        try:
            new_alpha = optimize.brentq(solve, 1e-3, 1e4, xtol=1e-8, maxiter=200)
        except (ValueError, RuntimeError):
            break
        new_beta = new_alpha / max(mubar_t, 1e-12)
        if abs(new_alpha - alpha) < 1e-6 and abs(new_beta - beta) < 1e-6:
            alpha, beta = new_alpha, new_beta
            break
        alpha, beta = new_alpha, new_beta
    return float(alpha), float(beta)


def compute_disproportionality(
    pair_counts: pd.DataFrame,
    drug_totals: pd.Series,
    reaction_totals: pd.Series,
    total_cases: int,
) -> pd.DataFrame:
    """Compute disproportionality metrics for each (drug, reaction) pair.

    Parameters
    ----------
    pair_counts : DataFrame with columns [drug, reaction, cases]
    drug_totals : Series indexed by drug  -> number of cases for the drug
    reaction_totals : Series indexed by reaction -> cases for the reaction
    total_cases : N, total active FAERS cases in the corpus
    """
    df = pair_counts.copy()
    a = df["cases"].to_numpy(dtype=float)
    n = float(total_cases)
    b = df["drug"].map(drug_totals).to_numpy(dtype=float) - a
    c = df["reaction"].map(reaction_totals).to_numpy(dtype=float) - a
    d = n - a - b - c

    # Haldane-Anscombe correction wherever a cell is zero
    zero = (b <= 0) | (c <= 0) | (d <= 0)
    a_c = np.where(zero, a + 0.5, a)
    b_c = np.where(zero, b + 0.5, b)
    c_c = np.where(zero, c + 0.5, c)
    d_c = np.where(zero, d + 0.5, d)

    # -------------------------------------------------- PRR + 95% CI
    prr = (a_c / (a_c + b_c)) / (c_c / (c_c + d_c))
    se_log_prr = np.sqrt(1.0 / a_c - 1.0 / (a_c + b_c) + 1.0 / c_c - 1.0 / (c_c + d_c))
    df["prr"] = prr
    df["prr_lo"] = np.exp(np.log(prr) - Z * se_log_prr)
    df["prr_hi"] = np.exp(np.log(prr) + Z * se_log_prr)

    # -------------------------------------------------- ROR + 95% CI
    ror = (a_c / b_c) / (c_c / d_c)
    se_log_ror = np.sqrt(1.0 / a_c + 1.0 / b_c + 1.0 / c_c + 1.0 / d_c)
    df["ror"] = ror
    df["ror_lo"] = np.exp(np.log(ror) - Z * se_log_ror)
    df["ror_hi"] = np.exp(np.log(ror) + Z * se_log_ror)

    # --------------------------- Yates-corrected chi-square (2x2 table)
    num = n * (np.abs(a_c * d_c - b_c * c_c) - n / 2.0) ** 2
    den = (a_c + b_c) * (c_c + d_c) * (a_c + c_c) * (b_c + d_c)
    chi2 = np.where(den > 0, num / np.where(den > 0, den, 1), 0.0)
    df["chi2"] = chi2
    df["p_value"] = stats.chi2.sf(chi2, df=1)

    # ------------------------------------- expected count + IC (Bayes)
    expected = (a_c + b_c) * (a_c + c_c) / n
    df["expected"] = expected
    df["ic"] = np.log2((a_c + 0.5) / (expected + 0.5))

    # ------------------------------------------- EBGM / EB05 (MGPS)
    alpha, beta = _fit_gamma_prior(a, expected)
    if np.isfinite(alpha) and np.isfinite(beta):
        df["ebgm"] = (a + alpha) / (expected + beta)
        df["eb05"] = stats.gamma.ppf(0.05, a + alpha, scale=1.0 / (expected + beta))
    else:
        df["ebgm"] = np.nan
        df["eb05"] = np.nan

    for col in ("prr", "prr_lo", "prr_hi", "ror", "ror_lo", "ror_hi",
                "chi2", "p_value", "ic", "ebgm", "eb05", "expected"):
        df[col] = df[col].astype(float).round(6)
    return df
