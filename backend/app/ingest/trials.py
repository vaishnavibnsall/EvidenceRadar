"""ClinicalTrials.gov API v2 ingestion.

Pulls study records for a curated list of therapeutic areas (overlapping the
highest-volume FAERS drug classes), including investigator-site locations
with geo-points, which powers the trials map in the frontend.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from app import config
from app.ingest.http import get_json


def pull_trials(
    out_path: Path | None = None,
    conditions: list[str] | None = None,
    per_condition: int | None = None,
    verbose: bool = True,
) -> Path:
    out_path = Path(out_path or config.TRIALS_RAW_JSONL)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    conditions = conditions or config.TRIAL_CONDITIONS
    per_condition = per_condition or config.TRIALS_PER_CONDITION

    seen: set[str] = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    seen.add(json.loads(line).get("protocolSection", {}).get("identificationModule", {}).get("nctId", ""))
                except json.JSONDecodeError:
                    continue

    total_new = 0
    with open(out_path, "a", encoding="utf-8") as fh:
        for cond in conditions:
            cond_new = 0
            page_token: str | None = None
            while cond_new < per_condition:
                params: dict = {
                    "query.cond": cond,
                    "pageSize": min(100, per_condition - cond_new),
                    "format": "json",
                    "countTotal": "true",
                }
                if page_token:
                    params["pageToken"] = page_token
                try:
                    data = get_json(config.CTGOV_STUDIES_URL, params=params)
                except RuntimeError as exc:
                    if verbose:
                        print(f"  [{cond}] stopping: {exc}")
                    break
                studies = data.get("studies", [])
                if not studies:
                    break
                for st in studies:
                    nct = st.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "")
                    if not nct or nct in seen:
                        continue
                    seen.add(nct)
                    st["_condition_query"] = cond
                    fh.write(json.dumps(st, ensure_ascii=False) + "\n")
                    cond_new += 1
                    total_new += 1
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            if verbose:
                print(f"  [{cond}] +{cond_new} studies")
    if verbose:
        print(f"ClinicalTrials.gov pull complete: {total_new} new studies -> {out_path}")
    return out_path


def iter_raw_studies(path: Path | None = None) -> Iterator[dict]:
    path = Path(path or config.TRIALS_RAW_JSONL)
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


def _date_str(struct: dict | None) -> str | None:
    if not struct:
        return None
    d = struct.get("date")
    if not d:
        return None
    return str(d)[:10]


def parse_study(study: dict) -> dict:
    """Flatten a ClinicalTrials.gov v2 study into our ct_studies row shape."""
    p = study.get("protocolSection", {}) or {}
    ident = p.get("identificationModule", {}) or {}
    status = p.get("statusModule", {}) or {}
    design = p.get("designModule", {}) or {}
    sponsors = p.get("sponsorCollaboratorsModule", {}) or {}
    arms = p.get("armsInterventionsModule", {}) or {}
    conditions = (p.get("conditionsModule", {}) or {}).get("conditions", []) or []

    interventions = [
        {
            "name": i.get("name"),
            "type": i.get("type"),
        }
        for i in (arms.get("interventions") or [])
        if i.get("name")
    ]

    locations = []
    for loc in (p.get("contactsLocationsModule", {}) or {}).get("locations", []) or []:
        geo = loc.get("geoPoint", {}) or {}
        locations.append(
            {
                "facility": loc.get("facility"),
                "city": loc.get("city"),
                "state": loc.get("state"),
                "country": loc.get("country"),
                "lat": geo.get("lat"),
                "lon": geo.get("lon"),
            }
        )
    has_geo = any(x.get("lat") is not None and x.get("lon") is not None for x in locations)

    phases = design.get("phases") or []
    phase = phases[0] if phases else None

    return {
        "nct_id": ident.get("nctId", ""),
        "brief_title": ident.get("briefTitle", ""),
        "official_title": ident.get("officialTitle", ""),
        "overall_status": status.get("overallStatus", ""),
        "phase": phase,
        "conditions": json.dumps(conditions, ensure_ascii=False),
        "interventions": json.dumps(interventions, ensure_ascii=False),
        "sponsor": (sponsors.get("leadSponsor", {}) or {}).get("name", ""),
        "enrollment": (design.get("enrollmentInfo", {}) or {}).get("count"),
        "study_type": (design.get("studyType", {}) or {}) if isinstance(design.get("studyType"), str) else design.get("studyType"),
        "start_date": _date_str(status.get("startDateStruct")),
        "completion_date": _date_str(status.get("completionDateStruct")),
        "has_geo": 1 if has_geo else 0,
        "locations": json.dumps(locations, ensure_ascii=False),
    }
