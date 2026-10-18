"""Optional Kaggle dataset helper.

Used only when the ``kaggle`` CLI and credentials (``~/.kaggle/kaggle.json`` or
KAGGLE_USERNAME / KAGGLE_KEY env vars) are available; every dataset we use has
an authoritative no-credential mirror, so this is a progressive enhancement.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def kaggle_ready() -> bool:
    if shutil.which("kaggle") is None:
        return False
    has_env = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    has_file = (Path.home() / ".kaggle" / "kaggle.json").exists()
    return has_env or has_file


def kaggle_download(owner: str, slug: str, dest: Path, verbose: bool = True) -> bool:
    """Download + unzip a Kaggle dataset. Returns True on success."""
    if not kaggle_ready():
        if verbose:
            print("kaggle CLI/credentials not found — skipping Kaggle mirror.")
        return False
    dest.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", f"{owner}/{slug}", "-p", str(dest), "--unzip"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        if verbose:
            print(f"kaggle download failed: {exc.stderr or exc}")
        return False
