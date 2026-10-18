"""EvidenceRadar — FastAPI application entrypoint.

Run:  uvicorn app.main:app --reload        (from backend/)
The API serves /api/* (see docs/api.md) and, when the frontend has been built
(frontend/dist), also serves the static dashboard at /.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.config import ROOT

app = FastAPI(
    title="EvidenceRadar API",
    description=(
        "Automated Real-World Evidence intelligence: FAERS disproportionality "
        "signals, FDA label cross-checks, ClinicalTrials.gov intelligence and "
        "patient-reported outcome analytics."
    ),
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local development tool; lock down for deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

_DIST = ROOT / "frontend" / "dist"
if _DIST.exists():
    # serve the built dashboard at / (production single-process mode)
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
