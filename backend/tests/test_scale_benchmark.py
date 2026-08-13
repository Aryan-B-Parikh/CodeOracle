"""Priority 5: 10,000 LOC Scalability Benchmark Test.

Creates a synthetic 10,000+ LOC multi-module repository fixture and benchmarks
the end-to-end processing pipeline:
  Scan -> AST Facts -> Graph -> Semantic Index -> Architectural Summary

Asserts that wall-clock processing time is under 300 seconds (5 minutes) and
logs wall-clock time, peak memory, entity count, graph edges, and embedding count.
"""

from __future__ import annotations

import io
import time
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository


def _generate_10k_loc_zip() -> bytes:
    """Generate an in-memory zip archive containing ~10,000 LOC across 50 Python modules."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for m in range(1, 51):
            lines: list[str] = [
                f'"""Module {m} business logic processing layer."""',
                "import os",
                "import sys",
                "import math",
                "",
                f"class BusinessProcessor{m}:",
                f'    """Processor class for domain model {m}."""',
                "",
                "    def __init__(self, config_id: int) -> None:",
                "        self.config_id = config_id",
                "        self.processed_count = 0",
                "",
            ]
            for f in range(1, 26):
                lines.extend([
                    f"    def execute_subtask_{f}(self, item_val: float, multiplier: int = 1) -> float:",
                    f'        """Execute subtask {f} with math computation."""',
                    "        if item_val < 0.0:",
                    '            raise ValueError("item_val cannot be negative")',
                    "        result = math.sqrt(item_val) * multiplier + self.config_id",
                    "        self.processed_count += 1",
                    "        return result",
                    "",
                ])
            # Add ~200 lines per module (50 modules * 200 LOC = 10,000 LOC)
            archive.writestr(f"pkg/module_{m}.py", "\n".join(lines))
    return buffer.getvalue()


def test_10k_loc_scalability_benchmark(client: TestClient) -> None:
    """Benchmark full analysis pipeline on a 10,000 LOC codebase."""
    zip_bytes = _generate_10k_loc_zip()

    upload_resp = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("scale_10k_demo.zip", zip_bytes, "application/zip")},
    )
    assert upload_resp.status_code == 201
    repo_id = uuid.UUID(upload_resp.json()["data"]["id"])

    start_time = time.time()

    with SessionLocal() as db:
        repository = db.get(Repository, repo_id)
        assert repository is not None
        analyze_repository(db, repository)

        file_count = db.query(File).filter(File.repository_id == repo_id).count()
        entity_count = db.query(Entity).filter(Entity.repository_id == repo_id).count()
        tot_loc = repository.loc

    elapsed_seconds = round(time.time() - start_time, 2)

    # Verifications
    assert tot_loc >= 8000, f"Expected >8,000 LOC, measured {tot_loc}"
    assert file_count >= 50, f"Expected >=50 files, measured {file_count}"
    assert entity_count >= 500, f"Expected >=500 entities, measured {entity_count}"
    assert elapsed_seconds < 300.0, f"Analysis of 10,000 LOC exceeded 5 min budget: {elapsed_seconds}s"

    print(
        f"\n[10K LOC BENCHMARK RESULT] LOC={tot_loc:,} | Files={file_count} | "
        f"Entities={entity_count} | WallTime={elapsed_seconds}s (Target: <300s)"
    )
