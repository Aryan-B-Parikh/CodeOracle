"""Evidence-cited function explanation tests (T-10)."""

import io
import uuid
import zipfile
from pathlib import Path

from app.db.models.entity import Entity
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


def _upload_and_analyze(client: TestClient, name: str) -> tuple[str, uuid.UUID]:
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
    return str(repository_id), repository_id


def test_entity_explanation_python_basic(client: TestClient) -> None:
    repo_id_str, repository_id = _upload_and_analyze(client, "python_basic")

    with SessionLocal() as db:
        tax_entity = (
            db.query(Entity)
            .filter(Entity.repository_id == repository_id, Entity.name == "calculate_tax")
            .first()
        )
        assert tax_entity is not None
        tax_entity_id = str(tax_entity.id)

    response = client.get(
        f"/api/v1/repositories/{repo_id_str}/entities/{tax_entity_id}/explanation"
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "entity" in data
    assert "explanation" in data
    assert "evidence" in data

    # The provider must be surfaced so consumers can distinguish mock from real AI.
    assert "provider" in data
    assert data["provider"] in ("mock", "openai", "anthropic", None)

    # Verify entity info
    entity = data["entity"]
    assert entity["name"] == "calculate_tax"
    assert entity["type"] == "function"
    assert entity["file"] == "tax.py"
    assert entity["lineStart"] > 0
    assert entity["lineEnd"] >= entity["lineStart"]

    # Verify all 10 required fields
    explanation = data["explanation"]
    required_fields = [
        "purpose",
        "inputs",
        "outputs",
        "sideEffects",
        "dependencies",
        "controlFlow",
        "errorHandling",
        "businessRules",
        "complexity",
        "risks",
    ]
    for field in required_fields:
        assert field in explanation, f"Missing field: {field}"
        assert explanation[field] is not None

    assert isinstance(explanation["complexity"], (int, float))

    # Verify evidence citations
    evidence = data["evidence"]
    assert isinstance(evidence, list)
    assert len(evidence) > 0

    for item in evidence:
        assert "claim" in item and len(item["claim"]) > 0
        assert item["file"] == "tax.py"
        assert "lineStart" in item and item["lineStart"] > 0
        assert "lineEnd" in item and item["lineEnd"] >= item["lineStart"]
        assert "code" in item and len(item["code"]) > 0

    # Spot-check: claims trace to actual fixture code
    claims_text = " ".join(item["claim"] for item in evidence)
    code_text = " ".join(item["code"] for item in evidence)
    terms = ["exempt", "tax", "rate", "calculate_tax", "tax.py"]
    assert any(term in claims_text or term in code_text for term in terms)


def test_entity_details_endpoint(client: TestClient) -> None:
    repo_id_str, repository_id = _upload_and_analyze(client, "python_basic")

    with SessionLocal() as db:
        entity = (
            db.query(Entity)
            .filter(Entity.repository_id == repository_id, Entity.name == "calculate_tax")
            .first()
        )
        assert entity is not None
        entity_id = str(entity.id)

    response = client.get(f"/api/v1/repositories/{repo_id_str}/entities/{entity_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entity"]["name"] == "calculate_tax"
    assert "signature" in data
    assert "complexity" in data


def test_explanation_404_not_found(client: TestClient) -> None:
    random_repo_id = str(uuid.uuid4())
    random_entity_id = str(uuid.uuid4())

    response = client.get(
        f"/api/v1/repositories/{random_repo_id}/entities/{random_entity_id}/explanation"
    )
    assert response.status_code == 404
