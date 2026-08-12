"""Unit and integration tests for the coverage repair loop (T-15)."""

import io
import uuid
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from app.services.test_generator import generate_uncovered_tests

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture_zip(name: str) -> bytes:
    root = FIXTURES / name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, arcname=path.relative_to(root))
    return buffer.getvalue()


def _upload_and_analyze(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/repositories/upload",
        files={"file": (f"{name}.zip", _fixture_zip(name), "application/zip")},
    )
    assert response.status_code == 201
    repository_id = uuid.UUID(response.json()["data"]["id"])
    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None
        analyze_repository(db, repository)
    return str(repository_id)


def test_generate_uncovered_tests_endpoint(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/tests/generate-uncovered?max_iterations=3&target_coverage=60.0"
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "testRunId" in data
    assert data["status"] == "passed"
    assert data["iteration"] <= 3
    assert data["lineCoverage"] >= 60.0
    assert data["targetReached"] is True
    assert data["statusLabel"] == "PASSED"


def test_coverage_repair_loop_service() -> None:
    with SessionLocal() as db:
        repo = Repository(
            id=uuid.uuid4(),
            name="demo-repair-repo",
            source_type="zip",
            languages={"python": True},
            loc=150,
        )
        db.add(repo)
        db.commit()

        final_run = generate_uncovered_tests(
            db, repo, max_iterations=3, target_coverage=60.0
        )
        assert final_run.id is not None
        assert final_run.iteration <= 3
        assert final_run.line_coverage >= 60.0
        assert final_run.target_reached is True


def test_generate_uncovered_404_not_found(client: TestClient) -> None:
    random_id = str(uuid.uuid4())
    response = client.post(f"/api/v1/repositories/{random_id}/tests/generate-uncovered")
    assert response.status_code == 404
