# EvidenceRadar — Automated Real-World Evidence (RWE) Intelligence Platform

EvidenceRadar ingests **real pharmacovigilance and clinical-research data**,
computes established signal-detection statistics, and presents the results as
a polished intelligence dashboard: which drug–reaction pairs are disproportionately
reported, which are already labelled, where trials are running, and what
patients actually report.

Built to be a genuinely **stand-alone platform** — no LLM calls, no mock data,
no black-box scoring: every number is derived from public datasets by
auditable pharmacoepidemiology methods.

---

## Highlights

- **FAERS signal detection at scale** — pulls real adverse-event reports from
  the FDA's openFDA API (42,500 deduplicated cases in the current build),
  computes **PRR, ROR (95% CI), Yates χ², Bayesian IC, and empirical-Bayes
  EBGM/EB05** (gamma-Poisson shrinkage fitted by EM) for every drug–reaction
  pair.
- **Label novelty cross-check** — each signal is matched against FDA
  structured product labels: strong **unlabelled** signals are surfaced for
  review (classic pharmacovigilance triage).
- **Patient-reported outcomes** — drug review dataset (Kaggle/UCI) analysed
  with a transparent adverse-event lexicon: rating distributions, severity
  mix, sentiment, and corroborating terms per drug.
- **Clinical trials intelligence** — ClinicalTrials.gov API v2: 3,080 studies
  across 22 therapeutic areas with phase/status/enrollment filters and a
  **geolocated investigator-site map**.
- **Composite evidence score** — a documented, linear, explainable score
  (ROR lower bound + EB05 + volume + trend + patient corroboration, penalised
  when the label already lists the reaction). See the in-app Methodology page.
- **Full pipeline as code** — `download → build → labels → analyze → serve`
  CLI, idempotent and resumable, with run provenance in SQLite.

## Tech stack

| Layer | Technology |
|---|---|
| Ingestion | Python 3.12, httpx — openFDA, ClinicalTrials.gov v2, UCI/Kaggle |
| Analytics | pandas, numpy, scipy (EM prior fitting, χ², gamma posteriors) |
| Storage | SQLite (stdlib `sqlite3` — zero external services) |
| API | FastAPI + Pydantic, auto OpenAPI docs at `/docs` |
| Frontend | React 18 + TypeScript, Vite, Recharts, Leaflet, React Router |
| Quality | pytest (statistical tests against hand-computed values), GitHub Actions CI |
| Packaging | Docker / docker-compose (single container serves API + dashboard) |

## Quick start

### 1. Backend

```powershell
cd EvidenceRadar
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt

# Option A — instant demo from the committed sample dataset:
cd backend
python -m app.cli build --source sample
python -m app.cli analyze

# Option B — full live pull (FAERS ~45k cases, trials, reviews, labels):
python -m app.cli run

# Serve API + dashboard
python -m app.cli serve
```

### 2. Frontend (dev)

```powershell
cd EvidenceRadar\frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api to :8000)
```

For a single-process production demo: `npm run build`, then
`python -m app.cli serve` — the API serves `frontend/dist` at `/`.

### Docker

```powershell
docker compose up --build     # http://localhost:8000
```

## Data sources (all real, public, citable)

| Dataset | Source | Scale in build |
|---|---|---|
| FAERS adverse-event reports | [openFDA drug/event](https://open.fda.gov/apis/drug/event/) | 42,500 active cases, 16 months of receive dates |
| FDA Structured Product Labels | [openFDA drug/label](https://open.fda.gov/apis/drug/label/) | 60 top-drug labels for novelty cross-check |
| Clinical studies | [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/about-api) | 3,080 studies, 22 conditions, site geo-points |
| Patient drug reviews | [Kaggle drugs.com crawl](https://www.kaggle.com/datasets/paultimothymooney/drug-review-dataset-drugscom) / [UCI #461](https://archive.ics.uci.edu/dataset/461) | 4,143 reviews with ratings + side-effect severity |

Kaggle credentials are optional (used automatically when present); every
dataset has a no-credential mirror. Full provenance and licensing:
[`data/README.md`](data/README.md).

## Architecture

```
openFDA (FAERS) ─┐
ClinicalTrials ──┤   app/ingest/*      app/transform/*       SQLite (app/db.py)
Drug reviews  ───┼─► download JSONL ─► normalise, dedupe ─► cases/drugs/reactions/
FDA labels    ───┘        ▲                   │                trials/reviews/labels
                          │                   ▼
                   CLI: download        app/analytics/*
                   CLI: build           PRR·ROR·χ²·IC·EBGM · pair lift · trends
                   CLI: labels          label cross-check · evidence score
                   CLI: analyze                    │
                   CLI: serve                      ▼
                                        FastAPI (app/api/*) ──► React dashboard
```

- `backend/app/ingest/` — acquisition: openFDA paging, CT.gov v2 pagination,
  Kaggle/UCI review mirrors, label fetcher, bulk FAERS-ASCII zip parser.
- `backend/app/transform/` — normalisation (auditable brand→generic map,
  dosage-form stripping), case-version dedup, ETL loader (raw **or** sample).
- `backend/app/analytics/` — the statistics: vectorised 2×2 disproportionality,
  EM-fitted gamma-Poisson EBGM, trend slopes, co-report lift, lexicon review
  analytics, composite scoring.
- `backend/app/api/` — query layer + FastAPI routers (contract in [`docs/api.md`](docs/api.md)).
- `frontend/` — dashboard: Overview, Signals, Drug detail, Trials map,
  Reviews, Methodology.

## API

Interactive OpenAPI docs: `http://localhost:8000/docs`

| Endpoint | Description |
|---|---|
| `GET /api/overview` | Corpus KPIs, monthly volume, top drugs |
| `GET /api/signals` | Ranked drug–reaction signals with full statistics |
| `GET /api/drugs/{name}` | Drug dossier: reactions, trend, pairs, reviews, label, trials |
| `GET /api/reactions/{pt}` | Reaction detail ranked by drug |
| `GET /api/trials` `/geo` `/facets` | Study search, map points, filter facets |
| `GET /api/reviews/stats` | Patient-reported outcome statistics per drug |
| `GET /api/methodology` | Formulas, weights, sources, limitations |

## Statistical methodology (short version)

For each (drug, reaction) pair on the 2×2 table `a,b,c,d` within the FAERS
corpus:

- **PRR** = `[a/(a+b)] / [c/(c+d)]`, **ROR** = `(a/b)/(c/d)` with 95% CIs on
  the log scale; **Yates χ²** for independence; **IC** = `log₂((a+0.5)/(E+0.5))`.
- **EBGM/EB05**: `a ~ Poisson(E·θ)`, `θ ~ Gamma(α,β)` with the prior fitted by
  EM on the corpus (DuMouchel-style MGPS); EB05 is the conservative posterior
  5th percentile used for ranking.
- **Trend**: slope of the monthly reporting *share* (count ÷ drug total),
  controlling for overall report volume.
- **Evidence score**: `100·(0.30·base + 0.25·bayes + 0.15·volume + 0.15·trend +
  0.15·support)·label_penalty` — fully documented in-app.

**Limitations** (also surfaced in-app): FAERS is spontaneous reporting with
no denominator — signals are associations for review, never incidence or
causality; stimulated reporting and duplication biases apply.

## Testing & CI

```powershell
pytest tests -q        # 22 tests: statistics, transforms, scoring, API contract
```

GitHub Actions runs the backend suite and the strict TypeScript build on every
push.

## Repository layout

```
EvidenceRadar/
├── backend/app/           # ingestion, transform, analytics, API, CLI
├── backend/requirements.txt
├── frontend/              # React + TS dashboard (Vite)
├── data/                  # provenance docs + committed sample dataset
├── docs/                  # API contract
├── tests/                 # pytest suites
├── Dockerfile / docker-compose.yml
└── .github/workflows/ci.yml
```

## License

MIT — see [LICENSE](LICENSE). Dataset licenses and attribution:
[data/README.md](data/README.md).
