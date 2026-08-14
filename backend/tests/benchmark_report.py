"""Shared benchmark-artifact writer.

Records measured benchmark results as versioned JSON files under
<repo-root>/benchmark-results/, so every run (local or CI) leaves a
comparable, auditable artifact: actual LOC, wall time, peak memory,
graph size, vector count, judge breakdown, and pass/fail verdict.

CI uploads this directory as a workflow artifact (actions/upload-artifact).
The committed golden files under benchmark-results/ are the recorded
baselines; refresh them whenever the numbers meaningfully change.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "benchmark-results"


def write_artifact(name: str, data: dict) -> Path:
    """Persist a benchmark artifact as <repo>/benchmark-results/<name>.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        **data,
    }
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path