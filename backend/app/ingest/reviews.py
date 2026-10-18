"""Patient drug-review ingestion.

Two mirrors of patient-reported drug experience data are supported:

1. Kaggle "drug review dataset (drugs.com)" (paultimothymooney) — 270k
   crawled Drugs.com reviews with rating, condition, date, usefulCount.
   Used automatically when the kaggle CLI + credentials are available.
2. UCI ML Repository dataset 461 "Drug Review Dataset (Druglib.com)"
   (CC BY 4.0, no credentials required) — ~8k reviews with rating,
   categorical side-effect severity and free-text side-effect narratives.

Both are reduced to a unified review record at load time.
"""
from __future__ import annotations

import csv
import zipfile
from pathlib import Path
from typing import Iterator

from app import config
from app.ingest.http import download_file
from app.ingest.kaggle_ds import kaggle_download

DRUGLIB_SIDEEFFECT_MAP = {
    "no side effects": "None",
    "mild side effects": "Mild",
    "moderate side effects": "Moderate",
    "severe side effects": "Severe",
}


def _have(out_dir: Path, files: list[str]) -> bool:
    return all((out_dir / f).exists() for f in files)


def fetch_reviews(out_dir: Path | None = None, verbose: bool = True) -> list[Path]:
    """Ensure review files exist locally: Kaggle first, then UCI druglib."""
    out_dir = Path(out_dir or config.REVIEWS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    if _have(out_dir, config.DRUGSCOM_FILES) or _have(out_dir, config.DRUGLIB_FILES):
        return sorted(p for p in out_dir.iterdir() if p.suffix.lower() in (".tsv", ".csv"))

    # 1) Kaggle mirror (Drugs.com crawl) — used when kaggle credentials exist
    owner, slug = config.KAGGLE_DATASETS["reviews"]
    if kaggle_download(owner, slug, out_dir, verbose=verbose) and _have(out_dir, config.DRUGSCOM_FILES):
        if verbose:
            print("Drug reviews obtained from Kaggle (drugs.com crawl).")
        return sorted(p for p in out_dir.iterdir() if p.suffix.lower() in (".tsv", ".csv"))

    # 2) UCI mirror (druglib, CC BY 4.0, no credentials required)
    if verbose:
        print("Downloading drug review dataset (druglib) from UCI ML Repository ...")
    zip_path = download_file(config.UCI_DRUGLIB_URL, config.REVIEWS_ZIP)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            name = Path(member).name
            if name in config.DRUGLIB_FILES:
                with zf.open(member) as src, open(out_dir / name, "wb") as dst:
                    dst.write(src.read())
    if not _have(out_dir, config.DRUGLIB_FILES):
        raise RuntimeError("drug review dataset extraction failed")
    if verbose:
        print(f"Drug reviews extracted -> {out_dir}")
    return sorted(p for p in out_dir.iterdir() if p.suffix.lower() in (".tsv", ".csv"))


def _iter_drugscom(path: Path) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            rating = row.get("rating", "")
            yield {
                "review_id": f"dcom-{row.get('uniqueID', '').strip()}",
                "drug_name": (row.get("drugName") or "").strip(),
                "condition": (row.get("condition") or "").strip(),
                "rating": int(rating) if str(rating).isdigit() else None,
                "review_date": row.get("date", "").strip() or None,
                "review_text": (row.get("review") or "").strip(),
                "useful_count": int(row["usefulCount"])
                if str(row.get("usefulCount", "")).strip().isdigit()
                else 0,
                "side_effect_severity": None,
            }


def _iter_druglib(path: Path, tag: str = "lib") -> Iterator[dict]:
    # The druglib export embeds newlines inside quoted free-text fields, so
    # csv quote handling is required to reconstruct full records; the ID
    # column header is left empty in this export.
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            return
        if header and not header[0].strip():
            header[0] = "id"
        idx = {name: i for i, name in enumerate(header)}

        def get(row: list[str], key: str) -> str:
            i = idx.get(key)
            return row[i].strip() if i is not None and i < len(row) else ""

        for row in reader:
            if not row or len(row) < 3:
                continue
            rating = get(row, "rating")
            severity_raw = get(row, "sideEffects").lower()
            review_parts = [
                get(row, "sideEffectsReview"),
                get(row, "benefitsReview"),
                get(row, "commentsReview"),
            ]
            yield {
                "review_id": f"{tag}-{get(row, 'id') or format(hash(tuple(row)) & 0xFFFFFFFF, '08x')}",
                "drug_name": get(row, "urlDrugName"),
                "condition": get(row, "condition"),
                "rating": int(rating) if rating.isdigit() else None,
                "review_date": None,  # druglib dataset has no review dates
                "review_text": " ".join(p for p in review_parts if p),
                "useful_count": 0,
                "side_effect_severity": DRUGLIB_SIDEEFFECT_MAP.get(severity_raw),
            }


def iter_reviews(paths: list[Path] | None = None) -> Iterator[dict]:
    """Yield unified review dicts from whichever mirror is present."""
    paths = paths or sorted(p for p in config.REVIEWS_DIR.iterdir() if p.suffix.lower() in (".tsv", ".csv"))
    for path in paths:
        if not path.exists():
            continue
        if path.name.lower().startswith("drugscom"):
            yield from _iter_drugscom(path)
        elif path.name.lower().startswith("druglib"):
            # the two druglib files restart their row IDs: namespace per file
            tag = "lib-train" if "train" in path.name.lower() else "lib-test"
            yield from _iter_druglib(path, tag=tag)
