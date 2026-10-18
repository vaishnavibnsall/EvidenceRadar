# Datasets

EvidenceRadar is built on real, public, citable data sources. No synthetic or
scraped proprietary data is committed to this repository; the `sample/`
directory contains a small, reproducibly-extracted slice so a fresh clone can
run the platform offline in seconds.

| Dataset | Source | License / terms | How it is obtained |
|---|---|---|---|
| FAERS adverse-event reports | [openFDA drug/event API](https://open.fda.gov/apis/drug/event/) (FDA Adverse Event Reporting System) | Public domain (US Government) | `python -m app.cli download` — receive-date month windows |
| FDA Structured Product Labels | [openFDA drug/label API](https://open.fda.gov/apis/drug/label/) | Public domain (US Government) | `python -m app.cli labels --top 60` |
| Clinical studies | [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/about-api) | Public domain (US Government) | `python -m app.cli download` |
| Patient drug reviews | Kaggle: [drug review dataset (drugs.com)](https://www.kaggle.com/datasets/paultimothymooney/drug-review-dataset-drugscom) (used when Kaggle credentials exist) | Dataset license as stated on Kaggle | `python -m app.cli download` |
| Patient drug reviews (mirror) | [UCI ML Repository #461 — Drug Review Dataset (Druglib.com)](https://archive.ics.uci.edu/dataset/461) | CC BY 4.0 | automatic fallback, no credentials required |

## Notes

- FAERS reports are *spontaneous* reports with no denominator: they support
  signal **detection**, never incidence estimation or causality claims.
  See the in-app Methodology page for the full limitations list.
- The committed `sample/` CSVs are a random, seeded slice of the full local
  build (see `evidenceradar sample` in the CLI) — statistically representative
  of the corpus that produced them.
- `data/raw/` and `data/processed/` are gitignored; rebuild them with
  `python -m app.cli run`.
