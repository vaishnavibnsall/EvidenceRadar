"""FAERS case deduplication.

FAERS receives multiple versions of the same case as reporters send follow-up
information.  The standard rule: for each CASEID, keep only the latest
version.  We store every version (for auditability) and mark the active one.
"""
from __future__ import annotations

import sqlite3


def apply_dedupe(conn: sqlite3.Connection) -> dict:
    """Mark is_active=1 for the newest version of each case. Returns stats."""
    conn.execute("UPDATE faers_cases SET is_active = 0")
    cur = conn.execute(
        """
        UPDATE faers_cases
        SET is_active = 1
        WHERE version = (
            SELECT MAX(version) FROM faers_cases AS c
            WHERE c.case_id = faers_cases.case_id
        )
        """
    )
    conn.commit()
    total = conn.execute("SELECT COUNT(*) AS n FROM faers_cases").fetchone()["n"]
    active = conn.execute("SELECT COUNT(*) AS n FROM faers_cases WHERE is_active = 1").fetchone()["n"]
    return {
        "total_versions": total,
        "active_cases": active,
        "duplicates_removed": total - active,
        "updated_rows": cur.rowcount,
    }
