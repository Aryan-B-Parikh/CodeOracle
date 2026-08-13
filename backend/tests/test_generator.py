"""Test generator service and API endpoint tests (T-13)."""

import ast
import io
import uuid
import zipfile
from pathlib import Path

from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from fastapi.testclient import TestClient

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


def test_generate_unit_tests_python(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(f"/api/v1/repositories/{repo_id_str}/tests/generate")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert data["repositoryId"] == repo_id_str
    assert data["language"] in ("python", "unknown")
    assert "code" in data
    assert len(data["targetFunctions"]) > 0

    code = data["code"]
    assert isinstance(code, str)
    # Ensure generated code is syntactically valid Python
    parsed = ast.parse(code)
    assert parsed is not None

    # Ensure main branch and exception path tests are generated
    assert "def test_" in code
    assert "pytest.raises" in code or "Exception" in code


def test_get_latest_test_run_endpoint(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    # Generate tests first
    client.post(f"/api/v1/repositories/{repo_id_str}/tests/generate")

    response = client.get(f"/api/v1/repositories/{repo_id_str}/tests/latest")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "testRunId" in data
    # The sandbox fails-closed when Docker is unavailable in test environments.
    # Accept both passed (Docker present) and failed (Docker absent, fail-closed).
    assert data["status"] in ("passed", "failed")
    assert data["testsGenerated"] > 0
    assert data["target"] == 60.0
    assert "uncoveredLines" in data
    assert "failedTests" in data


def test_tests_endpoints_404_not_found(client: TestClient) -> None:
    random_id = str(uuid.uuid4())

    gen_resp = client.post(f"/api/v1/repositories/{random_id}/tests/generate")
    assert gen_resp.status_code == 404

    latest_resp = client.get(f"/api/v1/repositories/{random_id}/tests/latest")
    assert latest_resp.status_code == 404
