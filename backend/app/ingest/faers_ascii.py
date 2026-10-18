"""Parser for the FDA's bulk FAERS quarterly ASCII files (DEMO/DRUG/REAC).

openFDA covers recent quarters via its API; the FDA also publishes complete
quarterly ASCII archives (zip files containing DEMO.TXT, DRUG.TXT, REAC.TXT,
...).  Drop such a zip into ``data/raw/faers_ascii/`` and this parser will
load it through the same normalisation path as the API pull, so the platform
is not coupled to a single acquisition route.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Iterator

from app.ingest.faers import _age_years, _int_version, _parse_date, _sex

REQUIRED_MEMBERS = {"DEMO.TXT", "DRUG.TXT", "REAC.TXT"}


def _open_member(zf: zipfile.ZipFile, member: str):
    """Return a text stream for a member, tolerating case differences."""
    names = {n.upper(): n for n in zf.namelist()}
    real = names.get(member.upper())
    if real is None:
        raise KeyError(f"{member} not found in archive")
    return io.TextIOWrapper(zf.open(real), encoding="utf-8", errors="replace")


def _read_table(handle, expected_cols: list[str]) -> Iterator[dict]:
    """Read a FAERS ASCII table (tab- or '$'-delimited, header in row 1)."""
    sample = handle.read(4096)
    handle.seek(0)
    delim = "\t" if "\t" in sample.splitlines()[0] else "$"
    reader = csv.DictReader(handle, delimiter=delim)
    # normalise header casing/whitespace
    mapping = {(h or "").strip().upper(): h for h in (reader.fieldnames or [])}
    cols = {c: mapping.get(c) for c in expected_cols}
    for row in reader:
        yield {c: (row.get(src) if src else None) for c, src in cols.items()}


def iter_quarter_cases(zip_path: Path) -> Iterator[dict]:
    """Yield normalised {case, drugs, reactions} dicts from one quarterly zip."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        upper_members = {n.upper() for n in zf.namelist()}
        missing = REQUIRED_MEMBERS - upper_members
        if missing:
            raise ValueError(f"{zip_path.name} missing required members: {sorted(missing)}")

        # ---- DEMO.TXT: one row per case version
        cases: dict[str, dict] = {}
        with _open_member(zf, "DEMO.TXT") as fh:
            for r in _read_table(
                fh,
                [
                    "CASEID", "VERSION", "RECEIPTDATE", "EVENT_DT", "OCCR_COUNTRY",
                    "PATIENTONSETAGE", "PATIENTONSETAGEUNIT", "PATIENTSEX", "PATIENTWT",
                ],
            ):
                case_id = (r["CASEID"] or "").strip()
                if not case_id:
                    continue
                cases[case_id] = {
                    "case": {
                        "case_id": case_id,
                        "version": _int_version(r["VERSION"]),
                        "receive_date": _parse_date(r["RECEIPTDATE"]),
                        "event_date": _parse_date(r["EVENT_DT"]),
                        "reporter_country": (r["OCCR_COUNTRY"] or "").strip().upper() or None,
                        "patient_age": _age_years(r["PATIENTONSETAGE"], r["PATIENTONSETAGEUNIT"]),
                        "patient_sex": _sex(r["PATIENTSEX"]),
                        "weight_kg": float(r["PATIENTWT"]) if (r["PATIENTWT"] or "").strip().replace(".", "").isdigit() else None,
                    },
                    "drugs": [],
                    "reactions": [],
                }

        # ---- DRUG.TXT
        with _open_member(zf, "DRUG.TXT") as fh:
            for r in _read_table(fh, ["CASEID", "DRUGNAME", "DRUGCHARACTERIZATION", "ROUTE"]):
                case = cases.get((r["CASEID"] or "").strip())
                name = (r["DRUGNAME"] or "").strip()
                if case is None or not name:
                    continue
                case["drugs"].append(
                    {
                        "case_id": case["case"]["case_id"],
                        "version": case["case"]["version"],
                        "drug_name": name,
                        "role_codename": {"1": "PS", "2": "C", "3": "I"}.get(
                            (r["DRUGCHARACTERIZATION"] or "").strip(), "U"
                        ),
                        "route": (r["ROUTE"] or "").strip() or None,
                    }
                )

        # ---- REAC.TXT
        with _open_member(zf, "REAC.TXT") as fh:
            for r in _read_table(fh, ["CASEID", "REACTIONMEDDRAPT"]):
                case = cases.get((r["CASEID"] or "").strip())
                pt = (r["REACTIONMEDDRAPT"] or "").strip()
                if case is None or not pt:
                    continue
                case["reactions"].append(
                    {
                        "case_id": case["case"]["case_id"],
                        "version": case["case"]["version"],
                        "pt": pt,
                    }
                )

        yield from cases.values()
