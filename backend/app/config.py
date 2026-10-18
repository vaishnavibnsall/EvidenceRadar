"""EvidenceRadar configuration: paths, source endpoints, tunable constants.

All paths are resolved relative to the repository root so the pipeline works
identically on Windows/Linux and in CI.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- paths ----
# backend/app/config.py -> repo root is two levels up.
ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
DATA_DIR = Path(os.environ.get("EVIDENCERADAR_DATA", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLE_DIR = DATA_DIR / "sample"
DB_PATH = Path(os.environ.get("EVIDENCERADAR_DB", BACKEND_DIR / "evidenceradar.db"))

for _d in (RAW_DIR, PROCESSED_DIR, SAMPLE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------- openFDA / FAERS ---
# The FDA Adverse Event Reporting System (FAERS) quarterly data is republished
# as a public, queryable API at api.fda.gov/drug/event.json.  We page through
# it in receive-date windows so deep pagination stays reliable.
OPENFDA_BASE = "https://api.fda.gov"
FAERS_EVENT_URL = f"{OPENFDA_BASE}/drug/event.json"
FAERS_LABEL_URL = f"{OPENFDA_BASE}/drug/label.json"
USER_AGENT = "EvidenceRadar/0.1 (real-world-evidence research project)"

# Pull the most recent FAERS months, leaving a lag for FDA processing.
FAERS_LAG_MONTHS = 3
FAERS_MONTHS = 18          # how many months of receive-date windows to pull
FAERS_PER_MONTH = 2500     # max cases sampled per month (pages of 1000)
FAERS_PAGE_SIZE = 750       # openFDA caps keyless requests below 1000/page
HTTP_SLEEP_S = 0.35        # politeness delay between API calls
HTTP_RETRIES = 4

# Raw + processed file locations
FAERS_RAW_DIR = RAW_DIR / "faers"
FAERS_RAW_JSONL = FAERS_RAW_DIR / "faers_cases.jsonl"
LABELS_RAW_JSONL = RAW_DIR / "drug_labels.jsonl"
TRIALS_RAW_JSONL = RAW_DIR / "clinicaltrials_studies.jsonl"
REVIEWS_ZIP = RAW_DIR / "drug_review_dataset.zip"
REVIEWS_DIR = RAW_DIR / "drug_reviews"

# Kaggle mirror (used automatically when the kaggle CLI + credentials exist)
KAGGLE_REVIEWS = ("paultimothymooney", "drug-review-dataset-drugscom")
KAGGLE_DATASETS = {"reviews": KAGGLE_REVIEWS}

# ------------------------------------------------- ClinicalTrials.gov v2 ---
CTGOV_STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
# Therapeutic areas that overlap with the highest-volume FAERS drug classes.
TRIAL_CONDITIONS = [
    "type 2 diabetes mellitus",
    "asthma",
    "rheumatoid arthritis",
    "migraine",
    "major depressive disorder",
    "hypertension",
    "breast cancer",
    "non-small cell lung cancer",
    "Alzheimer disease",
    "multiple sclerosis",
    "psoriasis",
    "chronic kidney disease",
    "Parkinson disease",
    "ulcerative colitis",
    "schizophrenia",
    "opioid use disorder",
    "atopic dermatitis",
    "heart failure",
    "chronic obstructive pulmonary disease",
    "systemic lupus erythematosus",
    "chronic spontaneous urticaria",
    "type 1 diabetes mellitus",
]
TRIALS_PER_CONDITION = 140

# ------------------------------------------------------- drug reviews -------
# Authoritative no-credential mirror: UCI ML Repository dataset 461
# "Drug Review Dataset (Druglib.com)", CC BY 4.0.
UCI_DRUGLIB_URL = (
    "https://archive.ics.uci.edu/static/public/461/drug+review+dataset+druglib+com.zip"
)
DRUGLIB_FILES = ["drugLibTrain_raw.tsv", "drugLibTest_raw.tsv"]
DRUGSCOM_FILES = ["drugsComTrain_raw.tsv", "drugsComTest_raw.tsv"]

# ------------------------------------------------------------ analytics -----
MIN_CASES_PER_PAIR = 3       # min drug-reaction co-reports to test a signal
TOP_DRUGS_FOR_PAIRS = 80     # co-reported drug pair analysis scope
MAX_DRUGS_IN_SUMMARY = 150   # drugs tracked in drug_summaries
MIN_DRUG_CASES = 15          # min FAERS cases for a drug to be analysed
SIGNIFICANCE_Z = 1.96        # 95% confidence
