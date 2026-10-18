"""Drug-drug co-reporting analysis.

Spontaneous reports list multiple suspect/concomitant drugs.  Pairs that
co-occur far more often than independence predicts are candidate drug-drug
interaction signals.  Lift = observed / expected under independence.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd


def compute_drug_pairs(
    case_drugs: pd.DataFrame,
    top_n: int = 80,
    min_co_reports: int = 5,
    max_drugs_per_case: int = 8,
) -> pd.DataFrame:
    """Compute co-report lift for the top-N most reported drugs.

    case_drugs: DataFrame with columns [case_id, drug] (active cases only).
    """
    drug_totals = case_drugs.groupby("drug")["case_id"].nunique()
    top_drugs = set(drug_totals.nlargest(top_n).index)
    filtered = case_drugs[case_drugs["drug"].isin(top_drugs)]

    per_case = filtered.groupby("case_id")["drug"].agg(lambda s: sorted(set(s)))
    n_cases = filtered["case_id"].nunique()

    counter: Counter[tuple[str, str]] = Counter()
    for drugs in per_case:
        if len(drugs) < 2 or len(drugs) > max_drugs_per_case:
            # too many concomitants (polypharmacy noise) -> skip the case
            if len(drugs) < 2:
                continue
            drugs = drugs[:max_drugs_per_case]
        for pair in combinations(drugs, 2):
            counter[pair] += 1

    rows = []
    for (d1, d2), co in counter.items():
        if co < min_co_reports:
            continue
        expected = drug_totals[d1] * drug_totals[d2] / max(n_cases, 1)
        lift = co / expected if expected > 0 else float("nan")
        if lift <= 1.0:
            continue
        rows.append({"drug_a": d1, "drug_b": d2, "co_reports": co, "lift": round(lift, 4)})

    out = pd.DataFrame(rows, columns=["drug_a", "drug_b", "co_reports", "lift"])
    if not out.empty:
        out = out.sort_values(["co_reports", "lift"], ascending=False).reset_index(drop=True)
    return out
