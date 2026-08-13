"""Unit and integration tests for Breaking-Change detection and Refactor Safety Score (T-18 & T-19)."""

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
        entity = (
            db.query(Entity)
            .filter(
                Entity.repository_id == repository.id,
                Entity.type.in_(["function", "method"]),
            )
            .first()
        )
        entity_id = str(entity.id) if entity else str(uuid.uuid4())
    return str(repository_id), entity_id


def test_get_refactor_safety_score_endpoint_success(client: TestClient) -> None:
    from app.db.models.refactor_proposal import RefactorProposalRecord

    repo_id_str, entity_id_str = _upload_and_analyze(client, "python_basic")
    proposal_id = uuid.uuid4()

    with SessionLocal() as db:
        record = RefactorProposalRecord(
            id=proposal_id,
            repository_id=uuid.UUID(repo_id_str),
            entity_id=uuid.UUID(entity_id_str),
            entity_name="calculate_tax",
            file_path="tax.py",
            original="def calculate_tax(rate, amount):\n    return rate * amount",
            proposed="def calculate_tax(rate: float, amount: float) -> float:\n    return rate * amount",
            original_checksum="hash123",
            rationale=["Add type annotations"],
            behavioral_differences=[],
            syntax_valid="valid",
        )
        db.add(record)
        db.commit()

    # Request Refactor Safety Score
    safety_resp = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{proposal_id}/safety"
    )
    assert safety_resp.status_code == 200, safety_resp.text

    payload = safety_resp.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "total" in data
    assert 0 <= data["total"] <= 100
    assert "apiCompatibility" in data
    assert "testCompatibility" in data
    assert "dependencyImpact" in data
    assert "behavioralRisk" in data
    assert data["riskLevel"] in ("low", "medium", "high")
    assert isinstance(data["breakingChanges"], list)
    assert isinstance(data["recommendations"], list)


def test_get_refactor_safety_score_404_not_found(client: TestClient) -> None:
    random_repo = str(uuid.uuid4())
    random_proposal = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/repositories/{random_repo}/refactors/{random_proposal}/safety"
    )
    assert response.status_code == 404
