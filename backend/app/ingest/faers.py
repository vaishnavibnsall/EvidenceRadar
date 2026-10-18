"""FAERS ingestion via the openFDA drug/event API.

The FDA Adverse Event Reporting System (FAERS) quarterly data is republished
by the FDA as the public openFDA ``drug/event`` API.  We pull receive-date
month windows with shallow pagination (1000 records/page) which keeps the
walk robust and reproducible, and write one raw JSON record per line for
provenance.  Raw records are normalised into case/drug/reaction rows at build
time (see ``app.transform.load``).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

from app import config
from app.ingest.http import get_json

# CDISC/FAERS patient-onset-age-unit codes -> conversion to years.
# (Best-effort mapping of the codes commonly seen in FAERS submissions.)
AGE_UNIT_TO_YEARS = {
    "800": 10.0,           # decade
    "801": 1.0,            # years
    "802": 1 / 12.0,       # months
    "803": 1 / 52.0,       # weeks
    "804": 1 / 365.0,      # days
    "805": 1 / 8760.0,     # hours
    "806": 1 / 525600.0,   # minutes
    "1000": 1.0,           # legacy years code seen in some submissions
}

# DRUGCHARACTERIZATION codes -> FAERS role codenames
ROLE_MAP = {"1": "PS", "2": "C", "3": "I"}  # suspect / concomitant / interacting


def month_windows(months: int = config.FAERS_MONTHS, lag: int = config.FAERS_LAG_MONTHS) -> list[tuple[str, str, str]]:
    """Return (month_key, search_expression, label) windows ending `lag` months ago.

    month_key is 'YYYY-MM'; the openFDA search expression limits on receivedate.
    """
    today = date.today()
    # go back `lag` months, then collect `months` windows
    y, m = today.year, today.month
    for _ in range(lag):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    windows: list[tuple[str, str, str]] = []
    for _ in range(months):
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        first = date(y, m, 1)
        last = date(ny, nm, 1) - timedelta(days=1)
        key = f"{y:04d}-{m:02d}"
        expr = f"receivedate:[{first.strftime('%Y%m%d')} TO {last.strftime('%Y%m%d')}]"
        windows.append((key, expr, key))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    windows.reverse()
    return windows


def pull_faers(
    out_path: Path | None = None,
    months: int | None = None,
    per_month: int | None = None,
    verbose: bool = True,
) -> Path:
    """Pull FAERS records from openFDA into a JSONL file (idempotent per month).

    Returns the path of the JSONL file.
    """
    out_path = Path(out_path or config.FAERS_RAW_JSONL)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    done_months: set[str] = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    done_months.add(json.loads(line).get("_month", ""))
                except json.JSONDecodeError:
                    continue

    windows = month_windows(months or config.FAERS_MONTHS)
    per_month = per_month or config.FAERS_PER_MONTH
    fetched = 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for month_key, expr, _label in windows:
            if month_key in done_months:
                continue
            offset = 0
            written_this_month = 0
            while written_this_month < per_month:
                page_size = min(config.FAERS_PAGE_SIZE, per_month - written_this_month)
                params = {
                    "search": expr,
                    "limit": page_size,
                    "skip": offset,
                }
                try:
                    data = get_json(config.FAERS_EVENT_URL, params=params)
                except RuntimeError as exc:
                    # offset beyond openFDA's window for this month: stop early
                    if verbose:
                        print(f"  [{month_key}] stopping pagination: {exc}")
                    break
                results = data.get("results", [])
                if not results:
                    break
                for rec in results:
                    rec["_month"] = month_key
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fetched += len(results)
                written_this_month += len(results)
                if len(results) < page_size:
                    break
                offset += page_size
            if verbose:
                print(f"  [{month_key}] +{written_this_month} cases")
    if verbose:
        print(f"FAERS pull complete: {fetched} new records -> {out_path}")
    return out_path


def iter_raw_records(path: Path | None = None) -> Iterator[dict]:
    path = Path(path or config.FAERS_RAW_JSONL)
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ------------------------------------------------------------- normalise ---

def _int_version(raw: str | int | None) -> int:
    if raw is None:
        return 1
    digits = re.sub(r"\D", "", str(raw))
    return int(digits) if digits else 1


def _parse_date(raw: str | None) -> str | None:
    """openFDA dates are 'YYYYMMDD' (or with time); normalise to ISO."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return None


def _age_years(value, unit) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    factor = AGE_UNIT_TO_YEARS.get(str(unit).strip(), 1.0)
    if str(unit).strip() not in AGE_UNIT_TO_YEARS:
        # unknown unit: only trust values that already look like years
        if not (0 <= v <= 120):
            return None
        years = v
    else:
        years = v * factor
    if not (0 <= years <= 120):
        return None
    return round(years, 1)


def _sex(raw) -> str:
    s = str(raw or "").strip().upper()
    return s if s in ("M", "F") else "I"


def parse_record(rec: dict) -> dict:
    """Normalise one openFDA adverse-event record.

    Returns {"case": {...}, "drugs": [...], "reactions": [...]}.
    """
    patient = rec.get("patient", {}) or {}
    case = {
        "case_id": str(rec.get("caseid") or rec.get("safetyreportid") or "").strip(),
        "version": _int_version(rec.get("caseversion")),
        "receive_date": _parse_date(rec.get("receivedate")),
        "event_date": _parse_date(patient.get("patienteventstartdate")),
        "reporter_country": (rec.get("primarysourcecountry") or rec.get("occurcountry") or "").upper() or None,
        "patient_age": _age_years(patient.get("patientonsetage"), patient.get("patientonsetageunit")),
        "patient_sex": _sex(patient.get("patientsex")),
        "weight_kg": float(patient["patientweight"])
        if str(patient.get("patientweight", "")).replace(".", "").isdigit()
        else None,
    }
    drugs = []
    for d in patient.get("drug", []) or []:
        openfda = d.get("openfda", {}) or {}
        name = (
            (openfda.get("generic_name") or [None])[0]
            or (openfda.get("brand_name") or [None])[0]
            or d.get("medicinename")
            or ""
        ).strip()
        if not name:
            continue
        drugs.append(
            {
                "case_id": case["case_id"],
                "version": case["version"],
                "drug_name": name,
                "role_codename": ROLE_MAP.get(str(d.get("drugcharacterization", "")).strip(), "U"),
                "route": (d.get("route") or d.get("drugadministrationroute") or "").strip() or None,
            }
        )
    reactions = []
    seen_pts: set[str] = set()
    for r in patient.get("reaction", []) or []:
        pt = (r.get("reactionmeddrapt") or "").strip()
        if not pt or pt.lower() in seen_pts:
            continue
        seen_pts.add(pt.lower())
        reactions.append(
            {
                "case_id": case["case_id"],
                "version": case["version"],
                "pt": pt,
            }
        )
    return {"case": case, "drugs": drugs, "reactions": reactions}
