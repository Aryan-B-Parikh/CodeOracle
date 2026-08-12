"""Impact analysis API & service tests (T-12)."""

import io
import uuid
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models.entity import Entity
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


def test_impact_analysis_endpoint_high_impact(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")
    repo_id = uuid.UUID(repo_id_str)

    with SessionLocal() as db:
        tax_entity = (
            db.query(Entity)
            .filter(Entity.repository_id == repo_id, Entity.name == "calculate_tax")
            .first()
        )
        assert tax_entity is not None
        tax_id_str = str(tax_entity.id)

    response = client.get(f"/api/v1/repositories/{repo_id_str}/entities/{tax_id_str}/impact")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert data["entity"]["name"] == "calculate_tax"
    assert data["entity"]["file"] == "tax.py"
    assert data["impact"] == "HIGH"
    assert "callers across" in data["impactReason"]

    # Verify callers in billing.py and reports.py
    callers = data["callers"]
    assert len(callers) >= 2
    caller_names = {c["caller"] for c in callers}
    caller_files = {c["file"] for c in callers}

    assert "calculate_invoice" in caller_names
    assert "billing.py" in caller_files

    # Verify callees
    callees = data["callees"]
    assert len(callees) >= 1
    callee_names = {c["callee"] for c in callees}
    assert "get_tax_rate" in callee_names


def test_impact_analysis_endpoint_low_impact(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")
    repo_id = uuid.UUID(repo_id_str)

    with SessionLocal() as db:
        leaf_entity = (
            db.query(Entity)
            .filter(Entity.repository_id == repo_id, Entity.name == "main")
            .first()
        )
        if leaf_entity is None:
            leaf_entity = (
                db.query(Entity)
                .filter(Entity.repository_id == repo_id, Entity.name == "format_currency")
                .first()
            )
        assert leaf_entity is not None
        leaf_id_str = str(leaf_entity.id)

    response = client.get(f"/api/v1/repositories/{repo_id_str}/entities/{leaf_id_str}/impact")
    assert response.status_code == 200, response.text

    data = response.json()["data"]
    assert data["impact"] in ("LOW", "MEDIUM")


def test_impact_analysis_404_not_found(client: TestClient) -> None:
    random_repo_id = str(uuid.uuid4())
    random_entity_id = str(uuid.uuid4())

    response = client.get(
        f"/api/v1/repositories/{random_repo_id}/entities/{random_entity_id}/impact"
    )
    assert response.status_code == 404
