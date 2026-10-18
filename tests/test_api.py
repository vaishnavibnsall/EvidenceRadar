"""API contract tests against a tiny synthetic database."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import config
from app.db import SCHEMA


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)

    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO faers_cases (case_id, version, is_active, receive_date) VALUES (?,?,1,?)",
        [("C1", 1, "2025-05-01"), ("C2", 1, "2025-06-01")],
    )
    conn.executemany(
        "INSERT INTO signals (drug, reaction, cases, drug_cases, reaction_cases, total_cases, "
        "ror, ror_lo, eb05, in_label, evidence_score) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("METFORMIN", "NAUSEA", 50, 100, 200, 1000, 3.2, 2.1, 1.9, 1, 72.5),
            ("METFORMIN", "HEADACHE", 10, 100, 300, 1000, 1.2, 0.8, 1.0, 0, 31.0),
        ],
    )
    conn.execute(
        "INSERT INTO drug_summaries (drug, cases, reactions, top_reaction, max_score, trials, reviews, mean_rating, label_present) "
        "VALUES ('METFORMIN', 100, 2, 'NAUSEA', 72.5, 1, 2, 6.5, 1)"
    )
    conn.execute(
        "INSERT INTO monthly_reports (drug, month, cases) VALUES ('METFORMIN','2025-05',30)"
    )
    conn.execute(
        "INSERT INTO drug_pairs (drug_a, drug_b, co_reports, lift) VALUES ('METFORMIN','INSULIN',20,2.5)"
    )
    conn.execute(
        "INSERT INTO review_stats (drug, reviews, mean_rating, low_rating_share, neg_share, pos_share, adr_terms) "
        "VALUES ('METFORMIN', 2, 6.5, 0.1, 0.2, 0.6, '[{\"term\": \"nausea\", \"count\": 3}]')"
    )
    conn.execute(
        "INSERT INTO ct_studies (nct_id, brief_title, overall_status, phase, conditions, interventions, "
        "sponsor, enrollment, has_geo, locations) VALUES "
        "('NCT1','Study of metformin','RECRUITING','PHASE3','[\"Diabetes\"]',"
        "'[{\"name\": \"METFORMIN\"}]','Acme Pharma',500,1,"
        "'[{\"country\": \"United States\", \"city\": \"Boston\", \"lat\": 42.36, \"lon\": -71.06}]')"
    )
    conn.execute(
        "INSERT INTO drug_labels (drug_normalized, generic_name, indications, boxed_warning) "
        "VALUES ('METFORMIN','METFORMIN','Type 2 diabetes',0)"
    )
    conn.commit()
    conn.close()

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["signals"] == 2


def test_overview(client):
    body = client.get("/api/overview").json()
    for key in ("cases", "unique_drugs", "trials", "reviews", "signals",
                "strong_signals", "global_trend", "top_drugs", "date_range"):
        assert key in body


def test_signals_list_and_filters(client):
    body = client.get("/api/signals").json()
    assert body["total"] == 2
    assert body["signals"][0]["drug"] == "METFORMIN"
    filtered = client.get("/api/signals", params={"min_score": 50}).json()
    assert filtered["total"] == 1
    searched = client.get("/api/signals", params={"q": "headache"}).json()
    assert searched["total"] == 1


def test_drug_detail_and_404(client):
    body = client.get("/api/drugs/METFORMIN").json()
    assert body["drug"] == "METFORMIN"
    assert len(body["reactions"]) == 2
    assert body["trend"][0]["month"] == "2025-05"
    assert body["pairs"][0]["drug"] == "INSULIN"
    assert body["reviews"]["adr_terms"][0]["term"] == "nausea"
    assert body["label"]["has_label"] is True
    assert body["trials"][0]["nct_id"] == "NCT1"
    assert client.get("/api/drugs/NOPE").status_code == 404


def test_trials_endpoints(client):
    body = client.get("/api/trials").json()
    assert body["total"] == 1
    assert body["trials"][0]["countries"] == ["United States"]
    geo = client.get("/api/trials/geo").json()
    assert geo["points"][0]["count"] == 1
    assert abs(geo["points"][0]["lat"] - 42.5) < 0.6
    facets = client.get("/api/trials/facets").json()
    assert any(f["value"] == "RECRUITING" for f in facets["statuses"])


def test_reviews_and_methodology(client):
    stats = client.get("/api/reviews/stats").json()
    assert stats["drugs"][0]["drug"] == "METFORMIN"
    m = client.get("/api/methodology").json()
    assert {d["title"] for d in m["disproportionality"]} >= {
        "Proportional Reporting Ratio (PRR)", "Reporting Odds Ratio (ROR)"
    }
    assert m["scoring"]["weights"]["base"] == 0.30
    assert len(m["sources"]) == 4
    assert m["limitations"]
