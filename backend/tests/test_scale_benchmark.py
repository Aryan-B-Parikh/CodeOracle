"""Priority 5: 10,000 LOC Scalability Benchmark Test.

Creates a synthetic 10,000+ LOC multi-module repository fixture and benchmarks
the end-to-end processing pipeline:
  Scan -> AST Facts -> Graph -> Semantic Index -> Architectural Summary

Asserts that wall-clock processing time is under 300 seconds (5 minutes) and
RECORDS a benchmark artifact (benchmark-results/scalability.json) with the
measured evidence: actual scanned LOC, file count, entity count, graph edges,
vector count, upload time, wall time, and peak Python memory (tracemalloc) —
so the result is auditable per run, not just a pass/fail print.
"""

from __future__ import annotations

import io
import time
import tracemalloc
import uuid
import zipfile

import pytest
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from fastapi.testclient import TestClient
from tests.benchmark_report import write_artifact


def _generate_10k_loc_zip() -> bytes:
    """Dynamically generate synthetic zip archive containing 10,000-10,500 scanner LOC."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        # 75 modules * ~137 lines per module = 10,275 LOC
        for m in range(1, 76):
            lines: list[str] = [
                f'"""Module {m} enterprise transaction processor."""',
                "import os",
                "import sys",
                "import math",
                "",
                f"class Processor{m}:",
                f'    """Enterprise scaling domain model {m}."""',
                "",
                "    def __init__(self, config_id: int) -> None:",
                "        self.config_id = config_id",
                "        self.processed_count = 0",
                "",
            ]
            for f in range(1, 10):
                lines.extend([
                    f"    def compute_subtask_{f}(self, val: float, mult: int = 1) -> float:",
                    f'        """Execute subtask {f} with audit logging."""',
                    "        if val < 0.0:",
                    '            raise ValueError("val cannot be negative")',
                    "        val_a = math.sqrt(abs(val)) * mult + self.config_id",
                    "        val_b = math.pow(val_a, 1.05) - (mult * 0.5)",
                    "        val_c = math.log1p(abs(val_b)) + self.processed_count",
                    "        result = val_a + val_b + val_c",
                    f'        audit_msg = f"Task {f} in module {m} processed value {{result}}"',
                    "        if len(audit_msg) > 100:",
                    "            audit_msg = audit_msg[:100]",
                    "        self.processed_count += 1",
                    "        return result",
                    "",
                ])
            archive.writestr(f"pkg/module_{m}.py", "\n".join(lines))
    return buffer.getvalue()


@pytest.mark.scalability
def test_10k_loc_scalability_benchmark(client: TestClient) -> None:
    """Benchmark full analysis pipeline on exactly 10,000-10,500 scanner LOC codebase."""
    t0 = time.time()
    zip_bytes = _generate_10k_loc_zip()

    t_upload_start = time.time()
    upload_resp = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("scale_10k_demo.zip", zip_bytes, "application/zip")},
    )
    assert upload_resp.status_code == 201
    upload_ms = round((time.time() - t_upload_start) * 1000, 2)
    repo_id = uuid.UUID(upload_resp.json()["data"]["id"])

    with SessionLocal() as db:
        repository = db.get(Repository, repo_id)
        assert repository is not None

        # Execute full analysis pipeline (Scan -> AST Facts -> Graph -> Index -> Summary)
        # under tracemalloc to record the peak Python allocation during analysis.
        tracemalloc.start()
        try:
            analyze_repository(db, repository)
        finally:
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        peak_memory_mb = round(peak_bytes / (1024 * 1024), 2)

        tot_loc = repository.loc

        file_count = db.query(File).filter(File.repository_id == repo_id).count()
        entity_count = db.query(Entity).filter(Entity.repository_id == repo_id).count()

        from app.db.models.call import Call
        from app.db.models.chunk import Chunk

        call_edges_count = db.query(Call).filter(Call.repository_id == repo_id).count()
        vector_count = db.query(Chunk).filter(Chunk.repository_id == repo_id).count()

    wall_time_ms = round((time.time() - t0) * 1000, 2)

    # Strict Requirement 3 Assertions
    assert 10_000 <= tot_loc <= 10_500, f"Expected 10,000-10,500 LOC, measured {tot_loc}"
    assert file_count >= 60, f"Expected >=60 files, measured {file_count}"
    assert entity_count >= 500, f"Expected >=500 entities, measured {entity_count}"
    assert wall_time_ms < 300_000.0, f"Exceeded 5 min budget: {wall_time_ms}ms"

    # Record the auditable benchmark artifact (also uploaded from CI).
    artifact = write_artifact(
        "scalability",
        {
            "benchmark": "10k-loc-scalability",
            "scannedLoc": tot_loc,
            "files": file_count,
            "entities": entity_count,
            "graphEdges": call_edges_count,
            "vectors": vector_count,
            "uploadMs": upload_ms,
            "wallTimeMs": wall_time_ms,
            "peakMemoryMb": peak_memory_mb,
            "limits": {"locMin": 10_000, "locMax": 10_500, "wallTimeMsMax": 300_000},
            "pass": True,
        },
    )

    print(
        f"\n[10K LOC BENCHMARK TELEMETRY] LOC={tot_loc:,} | Files={file_count} | "
        f"Entities={entity_count} | GraphEdges={call_edges_count} | Vectors={vector_count} | "
        f"UploadMs={upload_ms}ms | WallTimeMs={wall_time_ms}ms | "
        f"PeakMemMB={peak_memory_mb}MB | Artifact={artifact}"
    )
