"""Unit and integration tests for Executive Report export API (T-21)."""

import io
import uuid
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture_zip(name: str) -> bytes:
    root = FIXTURES / name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, arcname=path.relative_to(root))
    return buffer.getvalue()


def _upload_and_analyze(client: TestClient, name: str) -> tuple[str, str]:
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
    return str(repository_id), response.json()["data"]["name"]


def test_executive_report_markdown_endpoint_success(client: TestClient) -> None:
    repo_id_str, repo_name = _upload_and_analyze(client, "python_basic")

    response = client.get(f"/api/v1/repositories/{repo_id_str}/report")
    assert response.status_code == 200
    assert "text/markdown" in response.headers["content-type"]
    assert "attachment;" in response.headers["content-disposition"]

    markdown_text = response.text
    assert f"# Executive Architecture & Safety Report: {repo_name}" in markdown_text
    assert "## 1. Repository Overview" in markdown_text
    assert "## 2. Architectural Layer Structure" in markdown_text
    assert "## 3. High-Risk & Architectural Warnings" in markdown_text
    assert "## 4. Test Coverage & Quality Gates" in markdown_text


def test_executive_report_404_not_found(client: TestClient) -> None:
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/repositories/{random_id}/report")
    assert response.status_code == 404
