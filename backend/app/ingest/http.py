"""Small HTTP helper shared by all ingestion modules.

Provides a configured session with retries/backoff and a polite delay between
calls so the public FDA / NIH APIs are treated kindly.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from app import config

_session: httpx.Client | None = None


def session() -> httpx.Client:
    global _session
    if _session is None or _session.is_closed:
        _session = httpx.Client(
            timeout=60.0,
            headers={"User-Agent": config.USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )
    return _session


def get_json(url: str, params: dict[str, Any] | None = None) -> dict:
    """GET JSON with retries + exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(config.HTTP_RETRIES):
        try:
            resp = session().get(url, params=params)
            if resp.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(
                    f"retryable status {resp.status_code}", request=resp.request, response=resp
                )
            if resp.status_code >= 400:
                # non-retryable client error (e.g. openFDA keyless limit, bad query)
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}: {resp.text[:200]}",
                    request=resp.request,
                    response=resp,
                )
            resp.raise_for_status()
            time.sleep(config.HTTP_SLEEP_S)
            return resp.json()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:  # type: ignore[misc]
            last_exc = exc
            wait = 1.5 * (2 ** attempt)
            time.sleep(wait)
    raise RuntimeError(f"GET failed after {config.HTTP_RETRIES} attempts: {url}") from last_exc


def download_file(url: str, dest, params: dict[str, Any] | None = None) -> Path:
    """Stream a file download to disk (idempotent: skips if already present)."""
    from pathlib import Path

    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_exc: Exception | None = None
    for attempt in range(config.HTTP_RETRIES):
        try:
            with session().stream("GET", url, params=params) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=1 << 16):
                        fh.write(chunk)
            time.sleep(config.HTTP_SLEEP_S)
            return dest
        except httpx.HTTPError as exc:
            last_exc = exc
            dest.unlink(missing_ok=True)
            time.sleep(1.5 * (2 ** attempt))
    raise RuntimeError(f"download failed: {url}") from last_exc


# late import for type annotation only
from pathlib import Path  # noqa: E402
