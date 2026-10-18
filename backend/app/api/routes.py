"""FastAPI routers for the EvidenceRadar REST API (see docs/api.md)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import __version__, api
from app.db import connect

router = APIRouter()


@router.get("/health")
def health():
    conn = connect()
    try:
        n = conn.execute("SELECT COUNT(*) n FROM signals").fetchone()["n"]
        return {"status": "ok", "database": True, "signals": n, "version": __version__}
    finally:
        conn.close()


@router.get("/overview")
def overview():
    conn = connect()
    try:
        return api.queries.overview(conn)
    finally:
        conn.close()


@router.get("/signals")
def signals(
    min_cases: int = Query(3, ge=0),
    min_score: float = Query(0.0, ge=0, le=100),
    q: str | None = None,
    sort: str = "evidence_score",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = connect()
    try:
        return api.queries.list_signals(
            conn, min_cases=min_cases, min_score=min_score, q=q, sort=sort,
            limit=limit, offset=offset,
        )
    finally:
        conn.close()


@router.get("/drugs")
def drugs(
    q: str | None = None,
    sort: str = "cases",
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = connect()
    try:
        return api.queries.list_drugs(conn, q=q, sort=sort, limit=limit, offset=offset)
    finally:
        conn.close()


@router.get("/drugs/{name}")
def drug_detail(name: str):
    conn = connect()
    try:
        detail = api.queries.drug_detail(conn, name)
    finally:
        conn.close()
    if detail is None:
        raise HTTPException(status_code=404, detail=f"drug '{name}' not found")
    return detail


@router.get("/reactions/{pt}")
def reaction_detail(pt: str):
    conn = connect()
    try:
        detail = api.queries.reaction_detail(conn, pt)
    finally:
        conn.close()
    if detail is None:
        raise HTTPException(status_code=404, detail=f"reaction '{pt}' not found")
    return detail


@router.get("/trials")
def trials(
    condition: str | None = None,
    status: str | None = None,
    phase: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    conn = connect()
    try:
        return api.queries.list_trials(
            conn, condition=condition, status=status, phase=phase, q=q,
            limit=limit, offset=offset,
        )
    finally:
        conn.close()


@router.get("/trials/geo")
def trials_geo(condition: str | None = None):
    conn = connect()
    try:
        return api.queries.trials_geo(conn, condition=condition)
    finally:
        conn.close()


@router.get("/trials/facets")
def trials_facets():
    conn = connect()
    try:
        return api.queries.trials_facets(conn)
    finally:
        conn.close()


@router.get("/reviews/stats")
def reviews_stats(
    limit: int = Query(50, ge=1, le=300),
    sort: str = "reviews",
):
    conn = connect()
    try:
        return api.queries.review_stats(conn, limit=limit, sort=sort)
    finally:
        conn.close()


@router.get("/methodology")
def methodology():
    conn = connect()
    try:
        return api.queries.methodology(conn)
    finally:
        conn.close()
