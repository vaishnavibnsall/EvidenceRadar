# EvidenceRadar REST API

Base URL: `http://localhost:8000` — all endpoints under `/api`. JSON only.

## GET /api/health
```json
{ "status": "ok", "database": true, "signals": 1234, "version": "0.1.0" }
```

## GET /api/overview
```json
{
  "cases": 45210, "unique_drugs": 812, "unique_reactions": 4310,
  "trials": 3080, "reviews": 7943, "signals": 5123, "strong_signals": 42,
  "drug_pairs": 380,
  "date_range": { "from": "2025-04", "to": "2026-09" },
  "global_trend": [ { "month": "2025-04", "cases": 2510 } ],
  "top_drugs": [ { "drug": "METFORMIN", "cases": 1204 } ],
  "source": "raw",
  "last_refresh": "2026-10-18T12:00:00+00:00"
}
```

## GET /api/signals
Query: `min_cases` (default 3), `min_score` (default 0), `q` (drug/reaction substring),
`sort` ∈ {evidence_score, cases, ror, eb05, p_value} (default evidence_score),
`limit` (default 50, max 500), `offset` (default 0).
```json
{
  "total": 5123,
  "signals": [
    {
      "drug": "METFORMIN", "reaction": "NAUSEA", "cases": 87,
      "drug_cases": 900, "reaction_cases": 1500, "total_cases": 45210,
      "expected": 29.8, "prr": 3.1, "prr_lo": 2.5, "prr_hi": 3.8,
      "ror": 3.2, "ror_lo": 2.6, "ror_hi": 3.9, "chi2": 210.5, "p_value": 0.0,
      "ic": 1.4, "ebgm": 2.8, "eb05": 2.1,
      "in_label": true, "first_seen": "2025-04", "last_seen": "2026-09",
      "trend_slope": 0.85, "evidence_score": 71.2
    }
  ]
}
```

## GET /api/drugs
Query: `q`, `limit` (50), `offset` (0), `sort` ∈ {cases, max_score, reviews, trials}.
```json
{ "total": 150, "drugs": [ { "drug": "METFORMIN", "cases": 900, "reactions": 120,
    "top_reaction": "NAUSEA", "top_reaction_cases": 87, "max_score": 78.4,
    "trials": 24, "reviews": 310, "mean_rating": 6.8, "label_present": true } ] }
```

## GET /api/drugs/{name}   (404 if unknown)
```json
{
  "drug": "METFORMIN",
  "summary": { ...same object as /api/drugs item... },
  "reactions": [ { "reaction": "NAUSEA", "cases": 87, "prr": 3.1, "ror": 3.2,
      "ror_lo": 2.6, "eb05": 2.1, "ic": 1.4, "evidence_score": 71.2,
      "in_label": true, "trend_slope": 0.85 } ],
  "trend": [ { "month": "2025-04", "cases": 40 } ],
  "pairs": [ { "drug": "INSULIN GLARGINE", "co_reports": 66, "lift": 2.4 } ],
  "reviews": { "reviews": 310, "mean_rating": 6.8, "low_rating_share": 0.22,
      "neg_share": 0.18, "pos_share": 0.55,
      "adr_terms": [ { "term": "nausea", "count": 44 } ] },
  "label": { "has_label": true, "brand_name": "Glucophage", "generic_name": "METFORMIN",
      "indications": "…", "adverse_reactions": "…", "warnings": "…",
      "boxed_warning": false, "source_url": "https://api.fda.gov/drug/label.json?…" },
  "trials": [ { "nct_id": "NCT01234567", "brief_title": "…", "overall_status": "COMPLETED",
      "phase": "PHASE3", "enrollment": 1200, "conditions": ["Type 2 Diabetes"] } ]
}
```

## GET /api/reactions/{pt}
```json
{ "reaction": "NAUSEA", "total_cases": 1500,
  "drugs": [ { "drug": "METFORMIN", "cases": 87, "ror": 3.2, "eb05": 2.1, "evidence_score": 71.2 } ],
  "monthly": [ { "month": "2025-04", "cases": 120 } ] }
```

## GET /api/trials
Query: `condition`, `status`, `phase`, `q`, `limit` (50), `offset` (0).
```json
{ "total": 312, "trials": [ {
    "nct_id": "NCT01234567", "brief_title": "…", "overall_status": "RECRUITING",
    "phase": "PHASE2", "conditions": ["Asthma"], "interventions": ["Drug: Budesonide"],
    "sponsor": "…", "enrollment": 340, "start_date": "2025-01-15",
    "completion_date": "2026-12-31", "study_type": "INTERVENTIONAL",
    "location_count": 12, "countries": ["United States", "Germany"] } ] }
```

## GET /api/trials/geo
Query: `condition` (optional). Points grouped on a ~0.5° grid.
```json
{ "points": [ { "lat": 38.9, "lon": -77.0, "count": 14,
    "countries": ["United States"], "conditions": ["Asthma"], "statuses": { "RECRUITING": 6 } } ] }
```

## GET /api/trials/facets
```json
{ "statuses": [ { "value": "RECRUITING", "count": 812 } ],
  "phases": [ { "value": "PHASE2", "count": 400 } ],
  "conditions": [ { "value": "Asthma", "count": 140 } ] }
```

## GET /api/reviews/stats
Query: `limit` (50), `sort` ∈ {reviews, mean_rating, low_rating_share}.
```json
{ "drugs": [ { "drug": "METFORMIN", "reviews": 310, "mean_rating": 6.8,
    "low_rating_share": 0.22, "neg_share": 0.18, "pos_share": 0.55,
    "adr_terms": [ { "term": "nausea", "count": 44 } ] } ] }
```

## GET /api/methodology
```json
{ "disproportionality": [ { "title": "PRR", "formula": "…", "description": "…" } ],
  "scoring": { "weights": { "base": 0.3, "bayes": 0.25, "volume": 0.15, "trend": 0.15, "support": 0.15 },
               "label_penalty": 0.75, "formula": "…" },
  "sources": [ { "name": "FAERS (openFDA)", "url": "…", "description": "…", "records": "…" } ],
  "limitations": [ "…" ] }
```

All list endpoints cap `limit` at 500. Unknown drug/PT → `404` with
`{ "detail": "..." }`. Floats may be `null` when not computable.
