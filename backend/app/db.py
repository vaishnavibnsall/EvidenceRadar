"""SQLite storage layer for EvidenceRadar.

sqlite3 (stdlib) keeps the platform standalone: no external database server is
required to run the full pipeline or the API.  The schema is deliberately
normalised for FAERS cases, trials, reviews and derived analytics tables.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS etl_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    stage      TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status     TEXT NOT NULL DEFAULT 'running',
    detail     TEXT
);

-- FAERS spontaneous reports.  All case versions are stored; deduplication
-- marks the latest version of each case as active (is_active = 1).
CREATE TABLE IF NOT EXISTS faers_cases (
    case_id          TEXT NOT NULL,
    version          INTEGER NOT NULL DEFAULT 1,
    is_active        INTEGER NOT NULL DEFAULT 1,
    receive_date     TEXT,          -- YYYY-MM-DD
    event_date       TEXT,
    reporter_country TEXT,
    patient_age      REAL,          -- years
    patient_sex      TEXT,          -- M / F / I (other/unknown)
    weight_kg        REAL,
    source           TEXT NOT NULL DEFAULT 'openfda',
    PRIMARY KEY (case_id, version)
);

CREATE TABLE IF NOT EXISTS faers_case_drugs (
    case_id         TEXT NOT NULL,
    version         INTEGER NOT NULL,
    drug_name       TEXT,           -- verbatim reported name
    drug_normalized TEXT,           -- canonical name used for analytics
    role_codename   TEXT,           -- PS = suspect, SS = concomitant, C = concomitant
    route           TEXT,
    PRIMARY KEY (case_id, version, drug_name, role_codename)
);

CREATE TABLE IF NOT EXISTS faers_reactions (
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    pt      TEXT NOT NULL,          -- MedDRA preferred term
    PRIMARY KEY (case_id, version, pt)
);

CREATE TABLE IF NOT EXISTS ct_studies (
    nct_id          TEXT PRIMARY KEY,
    brief_title     TEXT,
    official_title  TEXT,
    overall_status  TEXT,
    phase           TEXT,
    conditions      TEXT,           -- JSON array
    interventions   TEXT,           -- JSON array
    sponsor         TEXT,
    enrollment      INTEGER,
    study_type      TEXT,
    start_date      TEXT,
    completion_date TEXT,
    has_geo         INTEGER NOT NULL DEFAULT 0,
    locations       TEXT            -- JSON array of {country, city, lat, lon}
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id            TEXT PRIMARY KEY,
    drug_name            TEXT,
    drug_normalized      TEXT,
    condition            TEXT,
    rating               INTEGER,
    review_date          TEXT,
    review_text          TEXT,
    useful_count         INTEGER,
    side_effect_severity TEXT          -- Mild / Moderate / Severe / None (druglib)
);

CREATE TABLE IF NOT EXISTS drug_labels (
    drug_normalized  TEXT PRIMARY KEY,
    brand_name       TEXT,
    generic_name     TEXT,
    indications      TEXT,
    adverse_reactions TEXT,
    warnings         TEXT,
    boxed_warning    INTEGER NOT NULL DEFAULT 0,
    source_url       TEXT
);

-- ------------------------------------------------------------ analytics ---
CREATE TABLE IF NOT EXISTS signals (
    drug           TEXT NOT NULL,
    reaction       TEXT NOT NULL,
    cases          INTEGER,          -- drug+reaction co-reports (a)
    drug_cases     INTEGER,          -- all cases for the drug (a+b)
    reaction_cases INTEGER,          -- all cases for the reaction (a+c)
    total_cases    INTEGER,          -- N
    expected       REAL,             -- (a+b)(a+c)/N
    prr            REAL,
    prr_lo         REAL,
    prr_hi         REAL,
    ror            REAL,
    ror_lo         REAL,
    ror_hi         REAL,
    chi2           REAL,
    p_value        REAL,
    ic             REAL,             -- information component, log2 offset
    ebgm           REAL,             -- empirical Bayes geometric mean (gamma-Poisson)
    eb05           REAL,             -- 5th percentile of the posterior
    in_label       INTEGER NOT NULL DEFAULT 0,
    first_seen     TEXT,             -- YYYY-MM
    last_seen      TEXT,
    trend_slope    REAL,             -- slope of monthly reporting share x1000
    evidence_score REAL,             -- composite 0-100
    PRIMARY KEY (drug, reaction)
);

CREATE TABLE IF NOT EXISTS drug_summaries (
    drug               TEXT PRIMARY KEY,
    cases              INTEGER,
    reactions          INTEGER,
    top_reaction       TEXT,
    top_reaction_cases INTEGER,
    max_score          REAL,
    trials             INTEGER,
    reviews            INTEGER,
    mean_rating        REAL,
    label_present      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS drug_pairs (
    drug_a     TEXT NOT NULL,
    drug_b     TEXT NOT NULL,
    co_reports INTEGER,
    lift       REAL,
    PRIMARY KEY (drug_a, drug_b)
);

CREATE TABLE IF NOT EXISTS monthly_reports (
    drug  TEXT NOT NULL,
    month TEXT NOT NULL,   -- YYYY-MM
    cases INTEGER,
    PRIMARY KEY (drug, month)
);

CREATE TABLE IF NOT EXISTS review_stats (
    drug            TEXT PRIMARY KEY,
    reviews         INTEGER,
    mean_rating     REAL,
    low_rating_share REAL,
    neg_share       REAL,
    pos_share       REAL,
    adr_terms       TEXT              -- JSON [{term, count}]
);

CREATE INDEX IF NOT EXISTS idx_signals_score  ON signals (evidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_signals_drug   ON signals (drug);
CREATE INDEX IF NOT EXISTS idx_signals_pt     ON signals (reaction);
CREATE INDEX IF NOT EXISTS idx_drugs_drug     ON faers_case_drugs (drug_normalized);
CREATE INDEX IF NOT EXISTS idx_reactions_pt   ON faers_reactions (pt);
CREATE INDEX IF NOT EXISTS idx_cases_active   ON faers_cases (is_active);
CREATE INDEX IF NOT EXISTS idx_reviews_drug   ON reviews (drug_normalized);
CREATE INDEX IF NOT EXISTS idx_pairs_a        ON drug_pairs (drug_a);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with sane defaults (row factory, WAL)."""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        init_schema(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def start_run(conn: sqlite3.Connection, stage: str) -> int:
    cur = conn.execute(
        "INSERT INTO etl_runs (stage, started_at, status) VALUES (?, ?, 'running')",
        (stage, now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str = "success",
    detail: str = "",
) -> None:
    conn.execute(
        "UPDATE etl_runs SET finished_at = ?, status = ?, detail = ? WHERE id = ?",
        (now_iso(), status, detail[:2000], run_id),
    )
    conn.commit()


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def get_meta(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in (
        "faers_cases",
        "faers_case_drugs",
        "faers_reactions",
        "ct_studies",
        "reviews",
        "drug_labels",
        "signals",
        "drug_pairs",
        "monthly_reports",
        "review_stats",
    ):
        out[table] = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
    out["active_cases"] = conn.execute(
        "SELECT COUNT(*) AS n FROM faers_cases WHERE is_active = 1"
    ).fetchone()["n"]
    return out
