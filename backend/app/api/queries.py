"""Query layer: all SQL used by the REST API lives here.

Kept separate from the routers so the same queries can be unit-tested and
reused (e.g. by CLI reporting) without HTTP.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from app import config

SORTABLE_SIGNAL_COLS = {
    "evidence_score", "cases", "ror", "eb05", "p_value", "prr", "chi2",
}


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _boolify(rec: dict, *keys: str) -> dict:
    for k in keys:
        if k in rec and rec[k] is not None:
            rec[k] = bool(rec[k])
    return rec


# ------------------------------------------------------------- overview ---

def overview(conn: sqlite3.Connection) -> dict[str, Any]:
    c = conn
    active = c.execute("SELECT COUNT(*) n FROM faers_cases WHERE is_active=1").fetchone()["n"]
    drugs = c.execute(
        "SELECT COUNT(DISTINCT drug_normalized) n FROM faers_case_drugs WHERE drug_normalized IS NOT NULL"
    ).fetchone()["n"]
    pts = c.execute("SELECT COUNT(DISTINCT pt) n FROM faers_reactions WHERE pt IS NOT NULL").fetchone()["n"]
    trials = c.execute("SELECT COUNT(*) n FROM ct_studies").fetchone()["n"]
    reviews = c.execute("SELECT COUNT(*) n FROM reviews").fetchone()["n"]
    signals = c.execute("SELECT COUNT(*) n FROM signals").fetchone()["n"]
    strong = c.execute("SELECT COUNT(*) n FROM signals WHERE evidence_score >= 70").fetchone()["n"]
    pairs = c.execute("SELECT COUNT(*) n FROM drug_pairs").fetchone()["n"]
    rng = c.execute(
        "SELECT MIN(receive_date) f, MAX(receive_date) l FROM faers_cases WHERE is_active=1"
    ).fetchone()

    trend = _rows(c.execute(
        """
        SELECT substr(COALESCE(c.receive_date, c.event_date, ''),1,7) AS month,
               COUNT(DISTINCT c.case_id) AS cases
        FROM faers_cases c WHERE c.is_active=1 AND month != ''
        GROUP BY month ORDER BY month
        """
    ))
    top_drugs = _rows(c.execute(
        "SELECT drug, cases FROM drug_summaries ORDER BY cases DESC LIMIT 10"
    ))
    source = c.execute("SELECT value FROM meta WHERE key='source'").fetchone()
    refresh = c.execute(
        "SELECT MAX(finished_at) f FROM etl_runs WHERE status='success'"
    ).fetchone()
    return {
        "cases": active,
        "unique_drugs": drugs,
        "unique_reactions": pts,
        "trials": trials,
        "reviews": reviews,
        "signals": signals,
        "strong_signals": strong,
        "drug_pairs": pairs,
        "date_range": {
            "from": (rng["f"] or "")[:7] or None,
            "to": (rng["l"] or "")[:7] or None,
        },
        "global_trend": trend,
        "top_drugs": top_drugs,
        "source": source["value"] if source else None,
        "last_refresh": refresh["f"] if refresh else None,
    }


# -------------------------------------------------------------- signals ---

def list_signals(
    conn: sqlite3.Connection,
    min_cases: int = 3,
    min_score: float = 0.0,
    q: str | None = None,
    sort: str = "evidence_score",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    sort = sort if sort in SORTABLE_SIGNAL_COLS else "evidence_score"
    where = ["cases >= ?", "evidence_score >= ?"]
    params: list[Any] = [min_cases, min_score]
    if q:
        where.append("(UPPER(drug) LIKE ? OR UPPER(reaction) LIKE ?)")
        like = f"%{q.upper()}%"
        params += [like, like]
    where_sql = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) n FROM signals WHERE {where_sql}", params
    ).fetchone()["n"]
    direction = "ASC" if sort == "p_value" else "DESC"
    cur = conn.execute(
        f"SELECT * FROM signals WHERE {where_sql} "
        f"ORDER BY {sort} {direction}, cases DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    signals = [_boolify(dict(r), "in_label") for r in cur.fetchall()]
    return {"total": total, "signals": signals}


# ---------------------------------------------------------------- drugs ---

DRUG_SORTS = {"cases", "max_score", "reviews", "trials", "mean_rating"}


def list_drugs(
    conn: sqlite3.Connection,
    q: str | None = None,
    sort: str = "cases",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    sort = sort if sort in DRUG_SORTS else "cases"
    where, params = [], []
    if q:
        where.append("UPPER(drug) LIKE ?")
        params.append(f"%{q.upper()}%")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) n FROM drug_summaries {where_sql}", params).fetchone()["n"]
    rows = _rows(conn.execute(
        f"SELECT * FROM drug_summaries {where_sql} ORDER BY {sort} DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ))
    for r in rows:
        _boolify(r, "label_present")
    return {"total": total, "drugs": rows}


def drug_detail(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    summary = conn.execute(
        "SELECT * FROM drug_summaries WHERE UPPER(drug) = UPPER(?)", (name,)
    ).fetchone()
    if summary is None:
        return None
    drug = summary["drug"]
    summary = dict(summary)
    _boolify(summary, "label_present")

    reactions = [
        _boolify(dict(r), "in_label")
        for r in conn.execute(
            "SELECT reaction, cases, prr, ror, ror_lo, eb05, ic, evidence_score, "
            "in_label, trend_slope FROM signals WHERE drug = ? "
            "ORDER BY evidence_score DESC LIMIT 30", (drug,)
        )
    ]
    trend = _rows(conn.execute(
        "SELECT month, cases FROM monthly_reports WHERE drug = ? ORDER BY month", (drug,)
    ))
    pairs = _rows(conn.execute(
        "SELECT CASE WHEN drug_a = ? THEN drug_b ELSE drug_a END AS drug, "
        "co_reports, lift FROM drug_pairs WHERE drug_a = ? OR drug_b = ? "
        "ORDER BY co_reports DESC LIMIT 20", (drug, drug, drug)
    ))

    rstat = conn.execute("SELECT * FROM review_stats WHERE drug = ?", (drug,)).fetchone()
    if rstat:
        reviews = dict(rstat)
        try:
            reviews["adr_terms"] = json.loads(reviews.get("adr_terms") or "[]")
        except json.JSONDecodeError:
            reviews["adr_terms"] = []
    else:
        reviews = {"reviews": 0, "mean_rating": None, "low_rating_share": None,
                   "neg_share": None, "pos_share": None, "adr_terms": []}

    label_row = conn.execute("SELECT * FROM drug_labels WHERE drug_normalized = ?", (drug,)).fetchone()
    if label_row:
        label = dict(label_row)
        _boolify(label, "boxed_warning")
        label["has_label"] = True
    else:
        label = {"has_label": False}

    like = f"%{drug.lower()}%"
    trial_rows = conn.execute(
        "SELECT nct_id, brief_title, overall_status, phase, enrollment, conditions "
        "FROM ct_studies WHERE LOWER(interventions) LIKE ? OR LOWER(conditions) LIKE ? "
        "ORDER BY COALESCE(enrollment, 0) DESC LIMIT 20", (like, like)
    ).fetchall()
    trials = []
    for r in trial_rows:
        d = dict(r)
        try:
            d["conditions"] = json.loads(d["conditions"] or "[]")
        except json.JSONDecodeError:
            d["conditions"] = []
        trials.append(d)

    return {
        "drug": drug,
        "summary": summary,
        "reactions": reactions,
        "trend": trend,
        "pairs": pairs,
        "reviews": reviews,
        "label": label,
        "trials": trials,
    }


# ----------------------------------------------------------- reactions ---

def reaction_detail(conn: sqlite3.Connection, pt: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT COUNT(*) n, SUM(cases) s FROM signals WHERE UPPER(reaction) = UPPER(?)", (pt,)
    ).fetchone()
    if not row or row["n"] == 0:
        return None
    drugs = _rows(conn.execute(
        "SELECT drug, cases, ror, eb05, evidence_score FROM signals "
        "WHERE UPPER(reaction) = UPPER(?) ORDER BY evidence_score DESC LIMIT 50", (pt,)
    ))
    monthly = _rows(conn.execute(
        """
        SELECT substr(COALESCE(c.receive_date, c.event_date, ''),1,7) AS month,
               COUNT(DISTINCT cd.case_id) AS cases
        FROM faers_reactions r
        JOIN faers_cases c ON c.case_id = r.case_id AND c.version = r.version AND c.is_active = 1
        JOIN faers_case_drugs cd ON cd.case_id = r.case_id AND cd.version = r.version
        WHERE UPPER(r.pt) = UPPER(?) AND month != ''
        GROUP BY month ORDER BY month
        """, (pt,)
    ))
    return {"reaction": pt.upper(), "total_cases": row["s"] or 0, "drugs": drugs, "monthly": monthly}


# -------------------------------------------------------------- trials ---

TRIAL_SORTS = {"enrollment", "start_date", "completion_date", "nct_id"}


def _parse_trial_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("conditions", "interventions", "locations"):
        try:
            d[key] = json.loads(d[key] or "[]")
        except json.JSONDecodeError:
            d[key] = []
    d["location_count"] = len(d["locations"])
    d["countries"] = sorted({x.get("country") for x in d["locations"] if x.get("country")})
    d.pop("locations", None)
    d.pop("official_title", None)
    d.pop("has_geo", None)
    return d


def list_trials(
    conn: sqlite3.Connection,
    condition: str | None = None,
    status: str | None = None,
    phase: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    where, params = [], []
    if condition:
        where.append("UPPER(conditions) LIKE ?")
        params.append(f"%{condition.upper()}%")
    if status:
        where.append("UPPER(overall_status) = UPPER(?)")
        params.append(status)
    if phase:
        where.append("UPPER(phase) = UPPER(?)")
        params.append(phase)
    if q:
        where.append("(UPPER(brief_title) LIKE ? OR UPPER(sponsor) LIKE ? OR UPPER(interventions) LIKE ?)")
        like = f"%{q.upper()}%"
        params += [like, like, like]
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) n FROM ct_studies {where_sql}", params).fetchone()["n"]
    rows = conn.execute(
        f"SELECT nct_id, brief_title, overall_status, phase, conditions, interventions, "
        f"sponsor, enrollment, study_type, start_date, completion_date, locations "
        f"FROM ct_studies {where_sql} ORDER BY COALESCE(enrollment,0) DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return {"total": total, "trials": [_parse_trial_row(r) for r in rows]}


def trials_geo(conn: sqlite3.Connection, condition: str | None = None) -> dict[str, Any]:
    where = "WHERE has_geo = 1"
    params: list[Any] = []
    if condition:
        where += " AND UPPER(conditions) LIKE ?"
        params.append(f"%{condition.upper()}%")
    cells: dict[tuple[float, float], dict] = {}
    for row in conn.execute(
        f"SELECT locations, conditions, overall_status FROM ct_studies {where} LIMIT 6000", params
    ):
        try:
            locs = json.loads(row["locations"] or "[]")
            conds = json.loads(row["conditions"] or "[]")
        except json.JSONDecodeError:
            continue
        for loc in locs:
            lat, lon = loc.get("lat"), loc.get("lon")
            if lat is None or lon is None:
                continue
            key = (round(lat * 2) / 2, round(lon * 2) / 2)
            cell = cells.setdefault(
                key, {"lat": key[0], "lon": key[1], "count": 0,
                      "countries": set(), "conditions": set(), "statuses": {}}
            )
            cell["count"] += 1
            if loc.get("country"):
                cell["countries"].add(loc["country"])
            for cond in conds:
                cell["conditions"].add(cond)
            st = row["overall_status"] or "UNKNOWN"
            cell["statuses"][st] = cell["statuses"].get(st, 0) + 1
    points = []
    for cell in cells.values():
        points.append({
            "lat": cell["lat"], "lon": cell["lon"], "count": cell["count"],
            "countries": sorted(cell["countries"])[:8],
            "conditions": sorted(cell["conditions"])[:8],
            "statuses": cell["statuses"],
        })
    points.sort(key=lambda p: -p["count"])
    return {"points": points[:1500]}


def trials_facets(conn: sqlite3.Connection) -> dict[str, Any]:
    statuses = _rows(conn.execute(
        "SELECT overall_status AS value, COUNT(*) AS count FROM ct_studies "
        "GROUP BY overall_status ORDER BY count DESC"
    ))
    phases = _rows(conn.execute(
        "SELECT phase AS value, COUNT(*) AS count FROM ct_studies "
        "WHERE phase IS NOT NULL GROUP BY phase ORDER BY count DESC"
    ))
    cond_counter: dict[str, int] = {}
    for row in conn.execute("SELECT conditions FROM ct_studies"):
        try:
            for cond in json.loads(row["conditions"] or "[]"):
                cond_counter[cond] = cond_counter.get(cond, 0) + 1
        except json.JSONDecodeError:
            continue
    conditions = [
        {"value": v, "count": c}
        for v, c in sorted(cond_counter.items(), key=lambda kv: -kv[1])[:40]
    ]
    return {"statuses": statuses, "phases": phases, "conditions": conditions}


# -------------------------------------------------------------- reviews ---

REVIEW_SORTS = {"reviews", "mean_rating", "low_rating_share", "neg_share"}


def review_stats(conn: sqlite3.Connection, limit: int = 50, sort: str = "reviews") -> dict[str, Any]:
    sort = sort if sort in REVIEW_SORTS else "reviews"
    rows = _rows(conn.execute(
        f"SELECT * FROM review_stats ORDER BY {sort} DESC LIMIT ?", (limit,)
    ))
    for r in rows:
        try:
            r["adr_terms"] = json.loads(r.get("adr_terms") or "[]")
        except json.JSONDecodeError:
            r["adr_terms"] = []
    return {"drugs": rows}


# ---------------------------------------------------------- methodology ---

def methodology(conn: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        "faers": conn.execute("SELECT COUNT(*) n FROM faers_cases WHERE is_active=1").fetchone()["n"],
        "trials": conn.execute("SELECT COUNT(*) n FROM ct_studies").fetchone()["n"],
        "reviews": conn.execute("SELECT COUNT(*) n FROM reviews").fetchone()["n"],
        "labels": conn.execute("SELECT COUNT(*) n FROM drug_labels").fetchone()["n"],
    }
    rng = conn.execute(
        "SELECT MIN(receive_date) f, MAX(receive_date) l FROM faers_cases WHERE is_active=1"
    ).fetchone()
    date_span = f"{(rng['f'] or '?')[:7]} to {(rng['l'] or '?')[:7]}"
    from app.analytics.scoring import LABEL_PENALTY, WEIGHTS

    return {
        "disproportionality": [
            {
                "title": "Proportional Reporting Ratio (PRR)",
                "formula": "PRR = [a/(a+b)] / [c/(c+d)]",
                "description": (
                    "Ratio of the reporting frequency of a reaction among reports of a drug "
                    "versus all other drugs. PRR >= 2 with chi-square >= 4 is the classic "
                    "screening criterion (Evans et al.). 95% CI computed on the log scale."
                ),
            },
            {
                "title": "Reporting Odds Ratio (ROR)",
                "formula": "ROR = (a/b) / (c/d),  95% CI = exp(ln(ROR) ± 1.96·√(1/a+1/b+1/c+1/d))",
                "description": (
                    "Odds of the reaction being reported for the drug versus all other drugs. "
                    "A signal is conventionally present when the lower 95% bound exceeds 1."
                ),
            },
            {
                "title": "Yates-corrected chi-square",
                "formula": "χ² = N·(|ad − bc| − N/2)² / [(a+b)(c+d)(a+c)(b+d)]",
                "description": "2×2 contingency test of independence with continuity correction.",
            },
            {
                "title": "Information Component (IC)",
                "formula": "IC = log2((a + 0.5) / (E + 0.5)),  E = (a+b)(a+c)/N",
                "description": (
                    "Bayesian shrinkage measure (BCPNN): IC > 0 means more reports than expected; "
                    "IC025 (lower credible bound) > 0 is a signal criterion."
                ),
            },
            {
                "title": "EBGM / EB05 (gamma-Poisson shrinkage)",
                "formula": "a_i ~ Poisson(E_i·θ_i), θ_i ~ Gamma(α, β) fitted by EM; EBGM = E[θ|a]",
                "description": (
                    "Empirical Bayes Geometric Mean (DuMouchel MGPS). EB05 is the 5th percentile "
                    "of the posterior — a conservative lower bound used to rank signals."
                ),
            },
        ],
        "scoring": {
            "weights": WEIGHTS,
            "label_penalty": LABEL_PENALTY,
            "formula": (
                "evidence_score = 100 · (0.30·base + 0.25·bayes + 0.15·volume + "
                "0.15·trend + 0.15·support) · label_penalty  —  base = clip(log2(ROR_lo),0,4)/4, "
                "bayes = clip(EB05,0,3)/3, volume = clip(log10(cases)/2.5,0,1), "
                "trend = σ(monthly reporting-share slope × 1000), "
                "support = patient-review corroboration for the drug, "
                "label_penalty = 0.75 when the reaction already appears in the FDA label."
            ),
        },
        "sources": [
            {
                "name": "FDA Adverse Event Reporting System (FAERS)",
                "url": "https://open.fda.gov/apis/drug/event/",
                "description": (
                    "Spontaneous adverse-event reports republished as the openFDA drug/event API; "
                    "receive-date windows with case-version deduplication."
                ),
                "records": f"{counts['faers']} active cases ({date_span})",
            },
            {
                "name": "FDA Structured Product Labels",
                "url": "https://open.fda.gov/apis/drug/label/",
                "description": "Label sections used to classify signals as labelled vs unlabelled.",
                "records": f"{counts['labels']} labels",
            },
            {
                "name": "ClinicalTrials.gov API v2",
                "url": "https://clinicaltrials.gov/data-api/about-api",
                "description": "Registered studies with investigator-site geolocation, phase and status.",
                "records": f"{counts['trials']} studies",
            },
            {
                "name": "Patient drug reviews (Kaggle / UCI ML Repository)",
                "url": "https://www.kaggle.com/datasets/paultimothymooney/drug-review-dataset-drugscom",
                "description": (
                    "Patient-reported outcomes: ratings, side-effect severity and narratives; "
                    "lexicon-based adverse-event extraction."
                ),
                "records": f"{counts['reviews']} reviews",
            },
        ],
        "limitations": [
            "FAERS reports are spontaneous: no denominator, no causality — reporting rates are not incidence rates.",
            "Reporting is subject to stimulated reporting, notoriety bias and duplication; deduplication is by case version only.",
            "Disproportionality flags statistical association for review, not confirmed adverse drug reactions.",
            "Patient reviews are self-selected and unverified; lexicon extraction misses paraphrases.",
            "Drug-name normalisation merges salts and dosage forms; rare brands may still fragment.",
        ],
    }
