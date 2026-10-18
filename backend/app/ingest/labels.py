"""FDA structured product label ingestion (openFDA drug/label).

Used to cross-check detected FAERS signals against the label: a drug-reaction
pair that already appears in the label is "labelled" (lower novelty), while a
strong disproportionality signal *absent* from the label is a potential
unlabelled safety signal — the classic pharmacovigilance use case.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app import config
from app.ingest.http import get_json


def fetch_labels(
    drugs: Iterable[str],
    out_path: Path | None = None,
    verbose: bool = True,
) -> Path:
    """Fetch the FDA label for each drug (generic-name exact search)."""
    out_path = Path(out_path or config.LABELS_RAW_JSONL)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    have: set[str] = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    have.add(json.loads(line).get("drug_normalized", ""))
                except json.JSONDecodeError:
                    continue

    added = 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for drug in drugs:
            if not drug or drug in have:
                continue
            params = {"search": f'openfda.generic_name:"{drug}"', "limit": 1}
            try:
                data = get_json(config.FAERS_LABEL_URL, params=params)
            except RuntimeError as exc:
                if verbose:
                    print(f"  [{drug}] label lookup failed: {exc}")
                continue
            results = data.get("results", [])
            if not results:
                have.add(drug)
                continue
            rec = results[0]
            openfda = rec.get("openfda", {}) or {}

            def section(key: str) -> str | None:
                vals = rec.get(key) or []
                return " ".join(str(v) for v in vals).strip() or None

            fh.write(
                json.dumps(
                    {
                        "drug_normalized": drug,
                        "brand_name": (openfda.get("brand_name") or [None])[0],
                        "generic_name": (openfda.get("generic_name") or [None])[0],
                        "indications": section("indications_and_usage"),
                        "adverse_reactions": section("adverse_reactions"),
                        "warnings": section("warnings_and_cautions") or section("boxed_warning"),
                        "boxed_warning": 1 if section("boxed_warning") else 0,
                        "source_url": (
                            "https://api.fda.gov/drug/label.json?"
                            f'search=openfda.generic_name%3A%22{drug.replace(" ", "+")}%22'
                        ),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            have.add(drug)
            added += 1
            if verbose and added % 10 == 0:
                print(f"  labels fetched: {added}")
    if verbose:
        print(f"Label pull complete: {added} new labels -> {out_path}")
    return out_path


def iter_labels(path: Path | None = None):
    path = Path(path or config.LABELS_RAW_JSONL)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
