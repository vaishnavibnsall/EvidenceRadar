"""Signal table builder: orchestrates the full analytics pass.

Pipeline:
  1. load active (deduplicated) FAERS case-drug-reaction pairs,
  2. restrict to drugs with sufficient support (MIN_DRUG_CASES),
  3. compute disproportionality (PRR/ROR/chi2/IC/EBGM),
  4. cross-check each pair against the FDA label (in_label),
  5. compute monthly reporting-share trend per pair,
  6. compute patient-review corroboration per drug,
  7. score signals, then write signals, drug_summaries, monthly_reports,
     drug_pairs and review_stats tables.
"""
from __future__ import annotations

import json
import re
import sqlite3

import numpy as np
import pandas as pd

from app import config
from app.analytics.disproportionality import compute_disproportionality
from app.analytics.pairs import compute_drug_pairs
from app.analytics.reviews_analytics import compute_review_stats
from app.analytics.scoring import review_support, score_signals

PAIRS_SQL = """
SELECT cd.drug_normalized AS drug, r.pt AS reaction, cd.case_id AS case_id
FROM faers_case_drugs cd
JOIN faers_reactions r   ON r.case_id = cd.case_id AND r.version = cd.version
JOIN faers_cases c       ON c.case_id = cd.case_id AND c.version = cd.version
WHERE c.is_active = 1 AND cd.drug_normalized IS NOT NULL AND r.pt IS NOT NULL
"""


def _label_regex(pt: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(pt.lower()).replace(r"\ ", r"\s+") + r"\b")


def _load_label_texts(conn: sqlite3.Connection) -> dict[str, str]:
    labels: dict[str, str] = {}
    for row in conn.execute("SELECT drug_normalized, indications, adverse_reactions, warnings FROM drug_labels"):
        blob = " ".join(x for x in (row["indications"], row["adverse_reactions"], row["warnings"]) if x)
        labels[row["drug_normalized"]] = blob.lower()
    return labels


def build_signals(conn: sqlite3.Connection, verbose: bool = True) -> dict:
    """(Re)compute all analytics tables. Returns a stats dict."""
    if verbose:
        print("Loading active FAERS pairs ...")
    pairs = pd.read_sql(PAIRS_SQL, conn)
    if pairs.empty:
        return {"signals": 0, "detail": "no FAERS data loaded"}

    # one (drug, reaction, case) contributes once
    pairs = pairs.drop_duplicates(subset=["drug", "reaction", "case_id"])
    active_cases = conn.execute(
        "SELECT COUNT(*) AS n FROM faers_cases WHERE is_active = 1"
    ).fetchone()["n"]
    total_cases = max(active_cases, pairs["case_id"].nunique())

    drug_totals_all = pairs.groupby("drug")["case_id"].nunique()
    eligible_drugs = drug_totals_all[drug_totals_all >= config.MIN_DRUG_CASES]
    eligible_drugs = eligible_drugs.nlargest(config.MAX_DRUGS_IN_SUMMARY)
    pairs = pairs[pairs["drug"].isin(eligible_drugs.index)]

    drug_totals = pairs.groupby("drug")["case_id"].nunique()
    reaction_totals = pairs.groupby("reaction")["case_id"].nunique()

    pair_counts = (
        pairs.groupby(["drug", "reaction"]).size().reset_index(name="cases")
    )
    pair_counts = pair_counts[pair_counts["cases"] >= config.MIN_CASES_PER_PAIR]
    if verbose:
        print(f"  {len(eligible_drugs)} drugs, {len(pair_counts)} candidate pairs "
              f"(of {len(pairs)} case-pairs, N={total_cases})")

    if pair_counts.empty:
        return {"signals": 0, "detail": "no pairs above minimum case count"}

    stats = compute_disproportionality(pair_counts, drug_totals, reaction_totals, total_cases)
    stats["drug_cases"] = stats["drug"].map(drug_totals).astype(int)
    stats["reaction_cases"] = stats["reaction"].map(reaction_totals).astype(int)
    stats["total_cases"] = total_cases

    # ------------------------------------------------------- label check
    if verbose:
        print("Cross-checking FDA labels ...")
    label_texts = _load_label_texts(conn)
    in_label = []
    regex_cache: dict[str, re.Pattern] = {}
    for drug, reaction in zip(stats["drug"], stats["reaction"]):
        text = label_texts.get(drug)
        if not text:
            in_label.append(0)
            continue
        rx = regex_cache.get(reaction)
        if rx is None:
            rx = regex_cache[reaction] = _label_regex(reaction)
        in_label.append(1 if rx.search(text) else 0)
    stats["in_label"] = in_label

    # ------------------------------------------------------------- trend
    if verbose:
        print("Computing monthly reporting-share trends ...")
    trend_map: dict[tuple[str, str], float] = {}
    first_seen: dict[tuple[str, str], str] = {}
    last_seen: dict[tuple[str, str], str] = {}
    pr = pd.read_sql(
        "SELECT cd.drug_normalized AS drug, r.pt AS reaction, "
        "substr(COALESCE(c.receive_date, c.event_date, ''), 1, 7) AS month, cd.case_id "
        "FROM faers_case_drugs cd "
        "JOIN faers_reactions r ON r.case_id = cd.case_id AND r.version = cd.version "
        "JOIN faers_cases c ON c.case_id = cd.case_id AND c.version = cd.version "
        "WHERE c.is_active = 1", conn,
    )
    pr = pr[pr["month"].str.len() == 7]
    monthly = pd.DataFrame() if pr.empty else pr[["drug", "month", "case_id"]].drop_duplicates()
    if not pr.empty:
        drug_month_cases = monthly.groupby(["drug", "month"]).size().rename("total")
        pm = (
            pr.drop_duplicates(["drug", "reaction", "case_id"])
            .groupby(["drug", "reaction", "month"]).size().rename("cnt").reset_index()
        )
        pm = pm.merge(drug_month_cases.reset_index(), on=["drug", "month"], how="left")
        pm["share"] = pm["cnt"] / pm["total"]

        # first/last seen per pair via groupby (not per-pair filtering)
        span = pm.groupby(["drug", "reaction"])["month"].agg(["min", "max"])
        first_seen = {(d, r): v for (d, r), v in span["min"].items()}
        last_seen = {(d, r): v for (d, r), v in span["max"].items()}

        for (drug, reaction), grp in pm.groupby(["drug", "reaction"]):
            grp = grp.sort_values("month").tail(12)
            if len(grp) >= 3:
                x = np.arange(len(grp), dtype=float)
                slope = float(np.polyfit(x, grp["share"].to_numpy(dtype=float), 1)[0]) * 1000.0
            else:
                slope = 0.0
            trend_map[(drug, reaction)] = round(slope, 4)
    stats["trend_slope"] = [
        trend_map.get((d, r), 0.0) for d, r in zip(stats["drug"], stats["reaction"])
    ]
    stats["first_seen"] = [first_seen.get((d, r)) for d, r in zip(stats["drug"], stats["reaction"])]
    stats["last_seen"] = [last_seen.get((d, r)) for d, r in zip(stats["drug"], stats["reaction"])]

    # --------------------------------------------- review corroboration
    review_df = pd.read_sql("SELECT drug_normalized, rating, review_text, side_effect_severity FROM reviews", conn)
    rs_df, _hist = compute_review_stats(review_df)
    if not rs_df.empty:
        support = review_support(rs_df["mean_rating"], rs_df.get("severe_share"))
        support_map = rs_df[["drug_normalized"]].rename(columns={"drug_normalized": "drug"})
        support_map["support"] = support
    else:
        support_map = None

    # ----------------------------------------------------------- scoring
    scored = score_signals(stats, support_map)
    signal_cols = [
        "drug", "reaction", "cases", "drug_cases", "reaction_cases", "total_cases",
        "expected", "prr", "prr_lo", "prr_hi", "ror", "ror_lo", "ror_hi",
        "chi2", "p_value", "ic", "ebgm", "eb05", "in_label",
        "first_seen", "last_seen", "trend_slope", "evidence_score",
    ]
    out = scored[signal_cols].copy()
    out = out.replace({np.nan: None})

    if verbose:
        print(f"Writing {len(out)} signals ...")
    conn.execute("DELETE FROM signals")
    out.to_sql("signals", conn, if_exists="append", index=False, method="multi", chunksize=500)

    # ------------------------------------------------- drug pairs
    if verbose:
        print("Computing drug-drug co-report pairs ...")
    case_drugs = pd.read_sql(
        "SELECT DISTINCT cd.case_id, cd.drug_normalized AS drug "
        "FROM faers_case_drugs cd JOIN faers_cases c "
        "ON c.case_id = cd.case_id AND c.version = cd.version "
        "WHERE c.is_active = 1 AND cd.drug_normalized IS NOT NULL", conn,
    )
    pairs_df = compute_drug_pairs(case_drugs, top_n=config.TOP_DRUGS_FOR_PAIRS)
    conn.execute("DELETE FROM drug_pairs")
    if not pairs_df.empty:
        pairs_df.to_sql("drug_pairs", conn, if_exists="append", index=False, method="multi", chunksize=500)

    # ------------------------------------------------ monthly reports
    monthly_top = pd.read_sql(
        "SELECT cd.drug_normalized AS drug, substr(COALESCE(c.receive_date, c.event_date, ''),1,7) AS month, "
        "cd.case_id FROM faers_case_drugs cd "
        "JOIN faers_cases c ON c.case_id = cd.case_id AND c.version = cd.version "
        "WHERE c.is_active = 1", conn,
    )
    monthly_top = monthly_top[monthly_top["month"].str.len() == 7]
    top_drug_set = list(drug_totals.nlargest(config.MAX_DRUGS_IN_SUMMARY).index)
    monthly_top = monthly_top[monthly_top["drug"].isin(top_drug_set)]
    mt = (
        monthly_top.drop_duplicates(["drug", "case_id"]).groupby(["drug", "month"]).size()
        .reset_index(name="cases")
    )
    conn.execute("DELETE FROM monthly_reports")
    mt.to_sql("monthly_reports", conn, if_exists="append", index=False, method="multi", chunksize=500)

    # ------------------------------------------------ review stats
    conn.execute("DELETE FROM review_stats")
    if not rs_df.empty:
        rs_out = rs_df.rename(columns={"drug_normalized": "drug"})[
            ["drug", "reviews", "mean_rating", "low_rating_share", "neg_share", "pos_share", "adr_terms"]
        ]
        rs_out["adr_terms"] = rs_out["adr_terms"].map(
            lambda t: t if isinstance(t, str) else json.dumps(t)
        )
        rs_out.to_sql("review_stats", conn, if_exists="append", index=False, method="multi", chunksize=500)

    # ------------------------------------------------ drug summaries
    if verbose:
        print("Building drug summaries ...")
    conn.execute("DELETE FROM drug_summaries")
    summary_rows = []
    trials = pd.read_sql("SELECT interventions, conditions FROM ct_studies", conn)
    trial_blob = (
        (trials["interventions"].fillna("") + " " + trials["conditions"].fillna("")).str.lower()
    )
    review_index = {}
    if not rs_df.empty:
        review_index = {
            row["drug_normalized"]: row
            for _, row in rs_df.iterrows()
        }
    top_signal = scored.sort_values("evidence_score", ascending=False).drop_duplicates("drug")
    top_signal = top_signal.set_index("drug")
    for drug in drug_totals.nlargest(config.MAX_DRUGS_IN_SUMMARY).index:
        dsig = scored[scored["drug"] == drug]
        top = dsig.sort_values("cases", ascending=False).iloc[0] if not dsig.empty else None
        rstat = review_index.get(drug)
        label_present = 1 if drug in label_texts else 0
        summary_rows.append(
            {
                "drug": drug,
                "cases": int(drug_totals[drug]),
                "reactions": int(dsig.shape[0]),
                "top_reaction": top["reaction"] if top is not None else None,
                "top_reaction_cases": int(top["cases"]) if top is not None else None,
                "max_score": float(dsig["evidence_score"].max()) if not dsig.empty else 0.0,
                "trials": int(trial_blob.str.contains(re.escape(drug.lower()), regex=True).sum()),
                "reviews": int(rstat["reviews"]) if rstat is not None else 0,
                "mean_rating": float(rstat["mean_rating"]) if rstat is not None and rstat["mean_rating"] is not None else None,
                "label_present": label_present,
            }
        )
    pd.DataFrame(summary_rows).to_sql(
        "drug_summaries", conn, if_exists="append", index=False, method="multi", chunksize=500
    )

    conn.commit()
    result = {
        "signals": len(out),
        "strong_signals": int((out["evidence_score"] >= 70).sum()),
        "drugs": len(summary_rows),
        "pairs": len(pairs_df),
        "total_cases": total_cases,
        "months": monthly["month"].nunique() if not monthly.empty else 0,
    }
    if verbose:
        print(f"Analytics complete: {result}")
    return result
