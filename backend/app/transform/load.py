"""ETL loader: raw downloads / sample CSVs -> SQLite.

Two sources are supported so a fresh clone works instantly:

- ``raw``   — live pulls (openFDA FAERS JSONL, ClinicalTrials.gov JSONL,
              drug-review TSVs, FDA labels JSONL) under data/raw/,
- ``sample`` — the committed, curated sample CSVs under data/sample/.

Both paths converge on the same schema, so the analytics and API layers do
not care which source built the database.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from app import config
from app.ingest.faers import iter_raw_records, parse_record
from app.ingest.labels import iter_labels
from app.ingest.reviews import iter_reviews
from app.ingest.trials import iter_raw_studies, parse_study
from app.transform.dedupe import apply_dedupe
from app.transform.normalize import normalize_drug, normalize_pt

CASE_COLS = ["case_id", "version", "receive_date", "event_date", "reporter_country",
             "patient_age", "patient_sex", "weight_kg"]
DRUG_COLS = ["case_id", "version", "drug_name", "drug_normalized", "role_codename", "route"]
REACTION_COLS = ["case_id", "version", "pt"]

TRIAL_COLS = ["nct_id", "brief_title", "official_title", "overall_status", "phase",
              "conditions", "interventions", "sponsor", "enrollment", "study_type",
              "start_date", "completion_date", "has_geo", "locations"]

REVIEW_COLS = ["review_id", "drug_name", "drug_normalized", "condition", "rating",
               "review_date", "review_text", "useful_count", "side_effect_severity"]


def _clear(conn: sqlite3.Connection) -> None:
    for table in ("faers_case_drugs", "faers_reactions", "faers_cases", "ct_studies",
                  "reviews", "drug_labels", "signals", "drug_summaries", "drug_pairs",
                  "monthly_reports", "review_stats"):
        conn.execute(f"DELETE FROM {table}")
    conn.commit()


def _insert_df(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    df = df.where(pd.notna(df), None)
    df.to_sql(table, conn, if_exists="append", index=False, method="multi", chunksize=500)
    return len(df)


# ------------------------------------------------------------ FAERS -------

def _load_faers_raw(conn: sqlite3.Connection, verbose: bool = True) -> dict:
    cases, drugs, reactions = [], [], []
    seen: set[tuple[str, int]] = set()
    for rec in iter_raw_records():
        parsed = parse_record(rec)
        case = parsed["case"]
        if not case["case_id"]:
            continue
        key = (case["case_id"], case["version"])
        if key in seen:
            continue
        seen.add(key)
        case["is_active"] = 1
        case["source"] = "openfda"
        cases.append(case)
        for d in parsed["drugs"]:
            d = dict(d, drug_normalized=normalize_drug(d["drug_name"]))
            drugs.append(d)
        for r in parsed["reactions"]:
            r = dict(r, pt=normalize_pt(r["pt"]))
            if r["pt"]:
                reactions.append(r)
    n_cases = _insert_df(conn, "faers_cases", pd.DataFrame(cases, columns=CASE_COLS + ["is_active", "source"]))
    drug_df = (
        pd.DataFrame(drugs, columns=DRUG_COLS).drop_duplicates(
            subset=["case_id", "version", "drug_name", "role_codename"]
        )
        if drugs else pd.DataFrame(columns=DRUG_COLS)
    )
    reac_df = (
        pd.DataFrame(reactions, columns=REACTION_COLS).drop_duplicates()
        if reactions else pd.DataFrame(columns=REACTION_COLS)
    )
    _insert_df(conn, "faers_case_drugs", drug_df)
    _insert_df(conn, "faers_reactions", reac_df)
    if verbose:
        print(f"  FAERS (openFDA): {len(cases)} case versions, {len(drug_df)} drug rows, {len(reac_df)} reactions")
    return {"cases": len(cases), "drugs": len(drug_df), "reactions": len(reac_df)}


def _load_faers_sample(conn: sqlite3.Connection, path: Path, verbose: bool = True) -> dict:
    df = pd.read_csv(path, dtype={"case_id": str})
    case_df = df[CASE_COLS].drop_duplicates(subset=["case_id", "version"]).copy()
    case_df["is_active"] = 1
    case_df["source"] = "sample"
    drug_df = df.dropna(subset=["drug_normalized"])[DRUG_COLS].drop_duplicates()
    reac_df = df.dropna(subset=["pt"])[REACTION_COLS].drop_duplicates()
    _insert_df(conn, "faers_cases", case_df)
    _insert_df(conn, "faers_case_drugs", drug_df)
    _insert_df(conn, "faers_reactions", reac_df)
    if verbose:
        print(f"  FAERS (sample): {len(case_df)} cases, {len(drug_df)} drug rows, {len(reac_df)} reactions")
    return {"cases": len(case_df), "drugs": len(drug_df), "reactions": len(reac_df)}


# ----------------------------------------------------------- trials -------

def _load_trials_raw(conn: sqlite3.Connection, verbose: bool = True) -> int:
    rows = []
    seen: set[str] = set()
    for study in iter_raw_studies():
        row = parse_study(study)
        if not row["nct_id"] or row["nct_id"] in seen:
            continue
        seen.add(row["nct_id"])
        rows.append(row)
    n = _insert_df(conn, "ct_studies", pd.DataFrame(rows, columns=TRIAL_COLS))
    if verbose:
        print(f"  ClinicalTrials.gov: {n} studies")
    return n


def _load_trials_sample(conn: sqlite3.Connection, path: Path, verbose: bool = True) -> int:
    df = pd.read_csv(path, dtype={"nct_id": str})
    n = _insert_df(conn, "ct_studies", df[TRIAL_COLS])
    if verbose:
        print(f"  Trials (sample): {n} studies")
    return n


# ---------------------------------------------------------- reviews -------

def _load_reviews_files(conn: sqlite3.Connection, verbose: bool = True) -> int:
    rows = []
    for rev in iter_reviews():
        rows.append(dict(rev, drug_normalized=normalize_drug(rev["drug_name"])))
    df = pd.DataFrame(rows, columns=REVIEW_COLS).drop_duplicates(subset=["review_id"])
    n = _insert_df(conn, "reviews", df)
    if verbose:
        print(f"  Reviews: {n}")
    return n


def _load_reviews_sample(conn: sqlite3.Connection, path: Path, verbose: bool = True) -> int:
    df = pd.read_csv(path, dtype={"review_id": str})
    n = _insert_df(conn, "reviews", df[REVIEW_COLS])
    if verbose:
        print(f"  Reviews (sample): {n}")
    return n


# ----------------------------------------------------------- labels -------

def _load_labels_raw(conn: sqlite3.Connection, verbose: bool = True) -> int:
    rows = list(iter_labels())
    n = _insert_df(conn, "drug_labels", pd.DataFrame(rows))
    if verbose:
        print(f"  Labels: {n}")
    return n


def _load_labels_sample(conn: sqlite3.Connection, path: Path, verbose: bool = True) -> int:
    df = pd.read_csv(path)
    n = _insert_df(conn, "drug_labels", df)
    if verbose:
        print(f"  Labels (sample): {n}")
    return n


# ------------------------------------------------------------ driver ------

def load_all(conn: sqlite3.Connection, source: str = "auto", verbose: bool = True) -> dict:
    """Load all datasets into SQLite. source: auto | raw | sample."""
    _clear(conn)

    faers_raw_ok = config.FAERS_RAW_JSONL.exists() and config.FAERS_RAW_JSONL.stat().st_size > 0
    trials_raw_ok = config.TRIALS_RAW_JSONL.exists() and config.TRIALS_RAW_JSONL.stat().st_size > 0
    reviews_raw_ok = any(
        (config.REVIEWS_DIR / f).exists() for f in (config.DRUGLIB_FILES + config.DRUGSCOM_FILES)
    )
    labels_raw_ok = config.LABELS_RAW_JSONL.exists() and config.LABELS_RAW_JSONL.stat().st_size > 0

    sample_faers = config.SAMPLE_DIR / "sample_faers.csv"
    sample_trials = config.SAMPLE_DIR / "sample_trials.csv"
    sample_reviews = config.SAMPLE_DIR / "sample_reviews.csv"
    sample_labels = config.SAMPLE_DIR / "sample_labels.csv"

    if source == "auto":
        source = "raw" if (faers_raw_ok or trials_raw_ok or reviews_raw_ok) else "sample"
    if verbose:
        print(f"Loading datasets (source={source}) ...")

    stats: dict = {"source": source}
    if source == "raw":
        stats["faers"] = _load_faers_raw(conn) if faers_raw_ok else _load_faers_sample(conn, sample_faers) if sample_faers.exists() else {}
        stats["trials"] = _load_trials_raw(conn) if trials_raw_ok else (_load_trials_sample(conn, sample_trials) if sample_trials.exists() else 0)
        stats["reviews"] = _load_reviews_files(conn) if reviews_raw_ok else (_load_reviews_sample(conn, sample_reviews) if sample_reviews.exists() else 0)
        stats["labels"] = _load_labels_raw(conn) if labels_raw_ok else (_load_labels_sample(conn, sample_labels) if sample_labels.exists() else 0)
    else:
        if not sample_faers.exists():
            raise FileNotFoundError(
                "data/sample/sample_faers.csv missing — run `evidenceradar download` first."
            )
        stats["faers"] = _load_faers_sample(conn, sample_faers)
        stats["trials"] = _load_trials_sample(conn, sample_trials) if sample_trials.exists() else 0
        stats["reviews"] = _load_reviews_sample(conn, sample_reviews) if sample_reviews.exists() else 0
        stats["labels"] = _load_labels_sample(conn, sample_labels) if sample_labels.exists() else 0

    stats["dedupe"] = apply_dedupe(conn)

    ranges = conn.execute(
        "SELECT MIN(receive_date) AS first, MAX(receive_date) AS last FROM faers_cases WHERE is_active=1"
    ).fetchone()
    from app.db import set_meta
    set_meta(conn, "source", source)
    set_meta(conn, "faers_date_range", f"{ranges['first']}..{ranges['last']}")
    conn.commit()
    if verbose:
        print(f"Load complete: {stats['dedupe']}")
    return stats
