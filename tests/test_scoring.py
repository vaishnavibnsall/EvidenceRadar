"""Tests for the composite evidence score."""
import pandas as pd
import pytest

from app.analytics.scoring import LABEL_PENALTY, score_signals


def _df(**overrides):
    base = {
        "drug": ["D"],
        "reaction": ["R"],
        "cases": [50],
        "ror_lo": [2.5],
        "eb05": [1.8],
        "trend_slope": [0.5],
        "in_label": [0],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_unlabelled_beats_labelled():
    unlabelled = score_signals(_df(in_label=[0])).iloc[0]["evidence_score"]
    labelled = score_signals(_df(in_label=[1])).iloc[0]["evidence_score"]
    assert labelled == pytest.approx(unlabelled * LABEL_PENALTY, rel=1e-3)


def test_score_monotonic_in_case_count():
    low = score_signals(_df(cases=[5])).iloc[0]["evidence_score"]
    high = score_signals(_df(cases=[500])).iloc[0]["evidence_score"]
    assert high > low


def test_score_monotonic_in_ror_lower_bound():
    weak = score_signals(_df(ror_lo=[1.05])).iloc[0]["evidence_score"]
    strong = score_signals(_df(ror_lo=[8.0])).iloc[0]["evidence_score"]
    assert strong > weak


def test_support_map_applied():
    support = pd.DataFrame({"drug": ["D"], "support": [1.0]})
    with_support = score_signals(_df(), support_map=support).iloc[0]["evidence_score"]
    without = score_signals(_df(), support_map=None).iloc[0]["evidence_score"]
    assert with_support > without


def test_score_bounds():
    hot = score_signals(
        _df(cases=[5000], ror_lo=[50.0], eb05=[9.0], trend_slope=[3.0], in_label=[0])
    ).iloc[0]["evidence_score"]
    assert 0 <= hot <= 100
