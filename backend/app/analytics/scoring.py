"""Composite evidence score for drug-reaction signals.

Transparent, auditable weighting of established disproportionality measures
plus cross-source corroboration.  Components (each scaled to 0..1):

    base    = clip(log2(ROR lower 95% bound), 0, 4) / 4     weight 0.30
    bayes   = clip(EB05, 0, 3) / 3                          weight 0.25
    volume  = clip(log10(cases) / 2.5, 0, 1)                weight 0.15
    trend   = sigmoid(monthly reporting-share slope x1000)  weight 0.15
    support = patient-review corroboration for the drug     weight 0.15

score = 100 * (weighted sum) * label_penalty
        label_penalty = 0.75 when the reaction already appears in the FDA
        label (known effect -> lower novelty), else 1.0.

This is deliberately a simple linear model so every signal can be explained
to a pharmacovigilance reviewer — no black boxes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "base": 0.30,
    "bayes": 0.25,
    "volume": 0.15,
    "trend": 0.15,
    "support": 0.15,
}
LABEL_PENALTY = 0.75


def _sigmoid(x: np.ndarray | pd.Series) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=float), -20, 20)
    return 1.0 / (1.0 + np.exp(-x))


def review_support(mean_rating, severe_share) -> pd.Series:
    """Map patient-review sentiment for a drug to a 0..1 corroboration."""
    rating = pd.Series(mean_rating, dtype=float)
    sev = pd.Series(severe_share, dtype=float).fillna(0.0)
    from_rating = ((10.0 - rating) / 6.0).clip(0, 1)
    return (from_rating * 0.7 + (sev * 2.0).clip(0, 0.3)).clip(0, 1)


def score_signals(df: pd.DataFrame, support_map: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add component + evidence_score columns to a signals DataFrame.

    df must contain: cases, ror_lo, eb05, trend_slope, in_label.
    support_map (optional): columns [drug, support] 0..1.
    """
    out = df.copy()

    base = (np.log2(out["ror_lo"].astype(float).clip(lower=1e-9)) / 4.0).clip(0, 1)
    bayes = (out["eb05"].astype(float).fillna(0.0) / 3.0).clip(0, 1)
    volume = (np.log10(out["cases"].astype(float).clip(lower=1)) / 2.5).clip(0, 1)
    slope = out["trend_slope"].astype(float).fillna(0.0)
    trend = _sigmoid(slope)

    if support_map is not None and not support_map.empty:
        support = out["drug"].map(
            dict(zip(support_map["drug"], support_map["support"]))
        ).astype(float).fillna(0.35)  # neutral when no review data
    else:
        support = pd.Series(0.35, index=out.index)

    raw = (
        WEIGHTS["base"] * base
        + WEIGHTS["bayes"] * bayes
        + WEIGHTS["volume"] * volume
        + WEIGHTS["trend"] * trend
        + WEIGHTS["support"] * support
    )
    penalty = out["in_label"].astype(int).map({0: 1.0, 1: LABEL_PENALTY}).astype(float)
    out["evidence_score"] = (100.0 * raw * penalty).round(2)

    out["component_base"] = base.round(4)
    out["component_bayes"] = bayes.round(4)
    out["component_volume"] = volume.round(4)
    out["component_trend"] = trend.round(4)
    out["component_support"] = support.round(4)
    return out
