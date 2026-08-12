"""T-07 parallel pipeline (Celery) tests.

Runs with ``CELERY_TASK_ALWAYS_EAGER=1`` (see conftest): tasks execute inline,
which lets the whole pipeline flow synchronously while still exercising the
same fan-out/aggregation code path a real worker pool uses.
"""

import io
import time
import uuid
import zipfile
from pathlib import Path

import pytest
from app.db.models.analysis import Analysis
from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.import_ import Import
from app.db.models.inheritance import Inheritance
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"

ANALYSIS_LIMIT_SECONDS = 300


def _fixture_zip(name: str) -> bytes:
    root = FIXTURES / name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, arcname=path.relative_to(root))
    return buffer.getvalue()


def _upload(client: TestClient, name: str) -> uuid.UUID:
    response = client.post(
        "/api/v1/repositories/upload",
        files={"file": (f"{name}.zip", _fixture_zip(name), "application/zip")},
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["data"]["id"])


def _entity_facts(repository_id: uuid.UUID) -> dict[str, object]:
    """Normalized fact sets that are independent of generated UUIDs."""
    with SessionLocal() as db:
        entities: dict[str, object] = {}
        for entity in db.query(Entity).filter(Entity.repository_id == repository_id):
            qualified = entity.metadata_json.get("qualified_name") or entity.name
            entities[qualified] = (
                entity.type,
                entity.line_start,
                entity.line_end,
                entity.complexity,
                entity.signature,
            )

        file_path_by_id = {
            file_row.id: file_row.path for file_row in db.query(File).all()
        }
        calls = set()
        for call in db.query(Call).filter(Call.repository_id == repository_id):
            caller_qualified = None
            if call.caller_id is not None:
                caller = db.get(Entity, call.caller_id)
                if caller is not None:
                    caller_qualified = caller.metadata_json.get("qualified_name") or caller.name
            calls.add(
                (
                    caller_qualified is not None,
                    caller_qualified or "",
                    call.callee_name,
                    call.call_line,
                    call.external,
                    call.dynamic,
                )
            )
        imports = {
            (
                file_path_by_id.get(imp.file_id),
                imp.module,
                imp.local_name,
                imp.is_external,
                imp.kind,
            )
            for imp in db.query(Import).join(File).filter(File.repository_id == repository_id)
        }
        inheritances = {
            (
                edge.entity_id is not None,
                (
                    db.get(Entity, edge.entity_id).metadata_json["qualified_name"]
                    if edge.entity_id is not None
                    else ""
                ),
                edge.parent_name,
                edge.kind,
                edge.line,
            )
            for edge in db.query(Inheritance).filter(Inheritance.repository_id == repository_id)
        }
        return {
            "entities": dict(sorted(entities.items())),
            "calls": sorted(calls),
            "imports": sorted(imports),
            "inheritances": sorted(inheritances),
        }


def test_status_reports_stages_and_completion(client: TestClient) -> None:
    repository_id = _upload(client, "python_basic")

    status = client.get(f"/api/v1/repositories/{repository_id}/status")
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["repositoryStatus"] == "uploaded"
    assert body["analysisStatus"] is None
    assert body["currentStage"] is None

    response = client.post(f"/api/v1/repositories/{repository_id}/analyze")
    assert response.status_code == 202
    assert response.json()["data"]["status"] == "completed"

    status = client.get(f"/api/v1/repositories/{repository_id}/status")
    body = status.json()["data"]
    assert body["repositoryStatus"] == "analyzed"
    assert body["analysisStatus"] == "completed"
    assert body["currentStage"] == "completed"

    stages = body["pipelineState"]
    for stage in ("uploaded", "scanned", "parsing", "aggregating", "graph", "index"):
        assert stages[stage]["state"] == "done", stage
    assert stages["parsing"]["filesTotal"] == 8
    assert stages["parsing"]["filesParsed"] == 8

    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None
        assert repository.status == "analyzed"
        assert repository.entity_count == 23


def test_parallel_pipeline_matches_sequential_analysis(client: TestClient) -> None:
    sequential_id = _upload(client, "python_basic")
    with SessionLocal() as db:
        repository = db.get(Repository, sequential_id)
        assert repository is not None
        analyze_repository(db, repository)

    pipeline_ids = []
    for _ in range(2):
        repository_id = _upload(client, "python_basic")
        assert client.post(f"/api/v1/repositories/{repository_id}/analyze").status_code == 202
        pipeline_ids.append(repository_id)

    reference = _entity_facts(sequential_id)
    assert len(reference["entities"]) == 23
    for pipeline_id in pipeline_ids:
        assert _entity_facts(pipeline_id) == reference


def test_parallel_parse_tasks_produce_identical_facts(client: TestClient) -> None:
    """parse_file_task (the worker path) returns the same facts as direct parsing."""
    from app.workers.tasks import parse_file_task

    repository_id = _upload(client, "python_basic")
    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None
        analyze_repository(db, repository)

        from app.services.analysis import repository_root

        root = str(repository_root(repository))
        total_entities = 0
        for file_row in repository.files:
            payload = parse_file_task(str(repository_id), root, file_row.path, file_row.language)
            assert payload is not None
            assert payload["path"] == file_row.path
            assert {"entities", "module_calls", "imports"} <= set(payload)
            total_entities += len(payload["entities"])
        assert total_entities == 23


def test_unparseable_file_skipped_not_fatal(client: TestClient) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("app.py", "def valid():\n    return 1\n")
        archive.writestr("broken.py", "def broken(:\n    pass\n")
        archive.writestr("main.py", "x = 1\n" * 20)
    response = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("mixed.zip", buffer.getvalue(), "application/zip")},
    )
    assert response.status_code == 201
    repository_id = uuid.UUID(response.json()["data"]["id"])

    assert client.post(f"/api/v1/repositories/{repository_id}/analyze").status_code == 202
    status = client.get(f"/api/v1/repositories/{repository_id}/status").json()["data"]
    assert status["analysisStatus"] == "completed"
    assert status["pipelineState"]["parsing"]["filesTotal"] == 3
    assert status["pipelineState"]["parsing"]["filesParsed"] == 2

    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None
        assert repository.entity_count == 1


def test_rerun_analysis_replaces_facts(client: TestClient) -> None:
    repository_id = _upload(client, "python_basic")
    for _ in range(2):
        assert client.post(f"/api/v1/repositories/{repository_id}/analyze").status_code == 202

    with SessionLocal() as db:
        runs = db.query(Analysis).filter(Analysis.repository_id == repository_id).all()
        assert len(runs) == 2
        assert all(run.status == "completed" for run in runs)
        assert db.query(Entity).filter(Entity.repository_id == repository_id).count() == 23


def test_analyze_rejected_while_running(client: TestClient) -> None:
    repository_id = _upload(client, "python_basic")
    with SessionLocal() as db:
        db.add(
            Analysis(
                repository_id=repository_id,
                status="running",
                pipeline_state={},
            )
        )
        db.commit()

    response = client.post(f"/api/v1/repositories/{repository_id}/analyze")
    assert response.status_code == 409


def _large_repo_zip(target_loc: int = 10000) -> bytes:
    """Deterministic ~10K LOC python fixture: 100 modules x 5 functions."""
    buffer = io.BytesIO()
    module_count = 100
    funcs_per_module = 5
    with zipfile.ZipFile(buffer, "w") as archive:
        for module in range(module_count):
            lines = [f'"""Fixture module {module}."""', ""]
            for func in range(funcs_per_module):
                lines.append(f"def compute_{module}_{func}(a, b):")
                lines.append(f'    """Compute {module}.{func}."""')
                lines.append("    total = a + b + a * b")
                lines.append("    if total > 1000:")
                lines.append("        total -= 500")
                lines.append("    elif total < -1000:")
                lines.append("        total += 500")
                lines.append("    else:")
                lines.append("        total //= 2")
                lines.append("    for i in range(a % 7):")
                lines.append("        total += i")
                lines.append("    while total > 1_000_000:")
                lines.append("        total //= 10")
                if func > 0:
                    lines.append(f"    return compute_{module}_{func - 1}(total, b)")
                else:
                    lines.append("    return total")
                lines.append("")
            archive.writestr(f"mod_{module:03d}.py", "\n".join(lines))
    buffer.seek(0, io.SEEK_END)
    assert buffer.tell() > target_loc, "fixture smaller than 10K LOC"
    return buffer.getvalue()


def test_10k_loc_fixture_analyzes_under_5_minutes(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("large.zip", _large_repo_zip(), "application/zip")},
    )
    assert response.status_code == 201
    repository_id = uuid.UUID(response.json()["data"]["id"])

    started = time.monotonic()
    assert client.post(f"/api/v1/repositories/{repository_id}/analyze").status_code == 202
    elapsed = time.monotonic() - started

    assert elapsed < ANALYSIS_LIMIT_SECONDS, f"analysis took {elapsed:.1f}s"

    status = client.get(f"/api/v1/repositories/{repository_id}/status").json()["data"]
    assert status["analysisStatus"] == "completed"
    assert status["pipelineState"]["parsing"]["filesTotal"] == 100
    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None
        assert repository.entity_count == 500


@pytest.mark.parametrize("fixture", ["python_basic", "java_modern"])
def test_pipeline_state_records_files_total(client: TestClient, fixture: str) -> None:
    repository_id = _upload(client, fixture)
    assert client.post(f"/api/v1/repositories/{repository_id}/analyze").status_code == 202
    status = client.get(f"/api/v1/repositories/{repository_id}/status").json()["data"]
    parsing = status["pipelineState"]["parsing"]
    assert parsing["filesTotal"] > 0
    assert parsing["filesParsed"] == parsing["filesTotal"]