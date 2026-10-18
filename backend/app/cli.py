"""EvidenceRadar command-line interface.

Usage (from backend/):
    python -m app.cli download            # pull FAERS, trials and reviews
    python -m app.cli build               # load raw data (or sample) into SQLite
    python -m app.cli labels --top 60     # fetch FDA labels for top drugs
    python -m app.cli analyze             # run the analytics pass
    python -m app.cli run                 # download + build + labels + analyze
    python -m app.cli sample              # export committed sample CSVs from DB
    python -m app.cli serve               # run the API + dashboard server
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from app import config
from app.db import connect, finish_run, init_schema, now_iso, set_meta, start_run


def cmd_download(args) -> None:
    sources = [s.strip() for s in args.sources.split(",")]
    if "faers" in sources:
        from app.ingest.faers import pull_faers
        pull_faers(months=args.months, per_month=args.per_month)
    if "trials" in sources:
        from app.ingest.trials import pull_trials
        pull_trials()
    if "reviews" in sources:
        from app.ingest.reviews import fetch_reviews
        fetch_reviews()


def cmd_build(args) -> None:
    from app.transform.load import load_all
    conn = connect()
    try:
        init_schema(conn)
        run_id = start_run(conn, "build")
        try:
            stats = load_all(conn, source=args.source)
            finish_run(conn, run_id, "success", str(stats)[:2000])
        except Exception as exc:  # noqa: BLE001
            finish_run(conn, run_id, "failed", str(exc))
            raise
    finally:
        conn.close()


def cmd_labels(args) -> None:
    from app.ingest.labels import fetch_labels
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT drug_normalized AS drug, COUNT(*) AS n
            FROM faers_case_drugs
            JOIN faers_cases USING (case_id, version)
            WHERE is_active = 1 AND drug_normalized IS NOT NULL
            GROUP BY drug_normalized ORDER BY n DESC LIMIT ?
            """,
            (args.top,),
        ).fetchall()
        drugs = [r["drug"] for r in rows]
        run_id = start_run(conn, "labels")
        try:
            fetch_labels(drugs)
            finish_run(conn, run_id, "success", f"{len(drugs)} drugs requested")
        except Exception as exc:  # noqa: BLE001
            finish_run(conn, run_id, "failed", str(exc))
            raise
    finally:
        conn.close()

    # reload just the labels table
    from app.ingest.labels import iter_labels
    conn = connect()
    try:
        conn.execute("DELETE FROM drug_labels")
        rows = list(iter_labels())
        pd.DataFrame(rows).to_sql("drug_labels", conn, if_exists="append", index=False)
        conn.commit()
        print(f"Loaded {len(rows)} labels into the database")
    finally:
        conn.close()


def cmd_analyze(args) -> None:
    from app.analytics.signals import build_signals
    conn = connect()
    try:
        run_id = start_run(conn, "analyze")
        try:
            stats = build_signals(conn)
            set_meta(conn, "last_refresh", now_iso())
            finish_run(conn, run_id, "success", str(stats)[:2000])
        except Exception as exc:  # noqa: BLE001
            finish_run(conn, run_id, "failed", str(exc))
            raise
    finally:
        conn.close()


def cmd_run(args) -> None:
    args.sources = "faers,trials,reviews"
    cmd_download(args)
    cmd_build(args)
    cmd_labels(args)
    cmd_analyze(args)


def cmd_sample(args) -> None:
    """Export a curated sample of the built DB into data/sample/ (committed)."""
    conn = connect()
    try:
        cases = pd.read_sql(
            "SELECT case_id FROM faers_cases WHERE is_active=1 "
            "ORDER BY RANDOM() LIMIT ?",
            conn, params=(args.cases,),
        )["case_id"].tolist()
        if not cases:
            raise SystemExit("no active cases in database — run build first")
        ph = ",".join("?" * len(cases))
        faers = pd.read_sql(
            f"""
            SELECT c.case_id, c.version, c.receive_date, c.event_date, c.reporter_country,
                   c.patient_age, c.patient_sex, c.weight_kg,
                   cd.drug_name, cd.drug_normalized, cd.role_codename, cd.route,
                   r.pt AS pt
            FROM faers_cases c
            LEFT JOIN faers_case_drugs cd ON cd.case_id=c.case_id AND cd.version=c.version
            LEFT JOIN faers_reactions r ON r.case_id=c.case_id AND r.version=c.version
            WHERE c.case_id IN ({ph})
            """,
            conn, params=cases,
        )
        # collapse the drug x reaction cross product back to one row per pair
        faers = faers.drop_duplicates(subset=["case_id", "version", "drug_name", "pt"])
        faers.to_csv(config.SAMPLE_DIR / "sample_faers.csv", index=False)

        trials = pd.read_sql(
            "SELECT * FROM ct_studies ORDER BY RANDOM() LIMIT ?", conn, params=(args.trials,)
        )
        trials.to_csv(config.SAMPLE_DIR / "sample_trials.csv", index=False)

        reviews = pd.read_sql(
            "SELECT * FROM reviews ORDER BY RANDOM() LIMIT ?", conn, params=(args.reviews,)
        )
        reviews.to_csv(config.SAMPLE_DIR / "sample_reviews.csv", index=False)

        labels = pd.read_sql("SELECT * FROM drug_labels", conn)
        labels.to_csv(config.SAMPLE_DIR / "sample_labels.csv", index=False)

        print(
            f"Sample exported: {faers['case_id'].nunique()} cases "
            f"({len(faers)} rows), {len(trials)} trials, {len(reviews)} reviews, "
            f"{len(labels)} labels -> {config.SAMPLE_DIR}"
        )
    finally:
        conn.close()


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="evidenceradar", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download", help="download raw datasets")
    p.add_argument("--sources", default="faers,trials,reviews")
    p.add_argument("--months", type=int, default=config.FAERS_MONTHS)
    p.add_argument("--per-month", type=int, default=config.FAERS_PER_MONTH)
    p.set_defaults(func=cmd_download)

    p = sub.add_parser("build", help="load datasets into SQLite")
    p.add_argument("--source", choices=["auto", "raw", "sample"], default="auto")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("labels", help="fetch FDA labels for top drugs")
    p.add_argument("--top", type=int, default=60)
    p.set_defaults(func=cmd_labels)

    p = sub.add_parser("analyze", help="compute signals and analytics tables")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("run", help="download + build + labels + analyze")
    p.add_argument("--months", type=int, default=config.FAERS_MONTHS)
    p.add_argument("--per-month", type=int, default=config.FAERS_PER_MONTH)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("sample", help="export sample CSVs from the built database")
    p.add_argument("--cases", type=int, default=5000)
    p.add_argument("--trials", type=int, default=400)
    p.add_argument("--reviews", type=int, default=4000)
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("serve", help="run the API server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    p.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
