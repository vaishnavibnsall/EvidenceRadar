"""Tests for drug-name normalisation and case deduplication."""
import sqlite3

from app.db import SCHEMA
from app.transform.dedupe import apply_dedupe
from app.transform.normalize import normalize_drug, normalize_pt


def test_brand_to_generic():
    assert normalize_drug("LIPITOR") == "ATORVASTATIN"
    assert normalize_drug("Tylenol Extra Strength") == "ACETAMINOPHEN"
    assert normalize_drug("ELIQUIS") == "APIXABAN"


def test_salt_and_form_stripping():
    assert normalize_drug("METFORMIN HYDROCHLORIDE 500 MG TABLETS") == "METFORMIN"
    assert normalize_drug("metformin hcl") == "METFORMIN"
    assert normalize_drug("Ibuprofen 200mg Capsules") == "IBUPROFEN"


def test_junk_dropped():
    assert normalize_drug("UNKNOWN") is None
    assert normalize_drug("") is None
    assert normalize_drug(None) is None
    assert normalize_drug("Not Specified") is None


def test_pt_normalisation():
    assert normalize_pt("  Nausea   ") == "Nausea"
    assert normalize_pt("Vomiting.") == "Vomiting"
    assert normalize_pt("") is None


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def test_dedupe_keeps_latest_version():
    conn = _conn()
    conn.executemany(
        "INSERT INTO faers_cases (case_id, version, is_active, receive_date) VALUES (?,?,1,?)",
        [("C1", 1, "2025-01-01"), ("C1", 2, "2025-02-01"), ("C2", 1, "2025-01-15")],
    )
    stats = apply_dedupe(conn)
    rows = conn.execute(
        "SELECT case_id, version, is_active FROM faers_cases ORDER BY case_id, version"
    ).fetchall()
    active = {(r["case_id"], r["version"]) for r in rows if r["is_active"] == 1}
    assert active == {("C1", 2), ("C2", 1)}
    assert stats["duplicates_removed"] == 1
