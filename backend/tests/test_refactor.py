"""Tests for refactor proposal service and API endpoint (T-17)."""

import hashlib
import io
import json
import uuid
import zipfile
from pathlib import Path

import pytest
from app.db.models.entity import Entity
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"

VALID_PROPOSAL_JSON = json.dumps(
    {
        "rationale": ["Extracts the inner loop into a helper."],
        "proposed": "def improved(a, b):\n    return a + b\n",
        "behavioral_differences": ["Return type preserved."],
    }
)


class _FakeGateway:
    """Gateway whose LLM 'complete' returns a canned response."""

    def __init__(self, content: str, provider: str = "openai") -> None:
        self._content = content
        self.provider_name = provider

    def complete(self, prompt: str, system: str = "") -> object:
        class _Response:
            def __init__(self, content: str, provider: str) -> None:
                self.content = content
                self.provider = provider

        return _Response(self._content, self.provider_name)


def _fixture_zip(name: str) -> bytes:
    root = FIXTURES / name
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, arcname=path.relative_to(root))
    return buffer.getvalue()


def _upload_and_analyze(client: TestClient, name: str) -> tuple[str, str]:
    """Upload fixture, run analysis, return (repo_id, first_entity_id)."""
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


def test_propose_refactor_endpoint_success(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.refactor as refactor_service

    monkeypatch.setattr(
        refactor_service, "get_llm_gateway", lambda: _FakeGateway(VALID_PROPOSAL_JSON)
    )
    repo_id_str, entity_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{entity_id_str}/propose"
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "proposalId" in data
    assert "entityId" in data
    assert data["entityId"] == entity_id_str
    assert "original" in data
    assert "proposed" in data
    assert isinstance(data["rationale"], list)
    assert isinstance(data["behavioralDifferences"], list)

    # Verify original checksum matches SHA-256 of original field
    original_text = data["original"]
    expected_checksum = hashlib.sha256(original_text.encode()).hexdigest()
    assert data["originalChecksum"] == expected_checksum


def test_propose_refactor_mock_provider_returns_502_without_fabrication(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a real LLM provider the endpoint must fail honestly, not fake a proposal."""
    import app.services.refactor as refactor_service

    monkeypatch.setattr(
        refactor_service,
        "get_llm_gateway",
        lambda: _FakeGateway("", provider="mock"),
    )
    repo_id_str, entity_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{entity_id_str}/propose"
    )
    assert response.status_code == 502, response.text
    assert "LLM" in response.json()["detail"]


def test_propose_refactor_non_json_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed LLM output must not be presented as a proposal."""
    import app.services.refactor as refactor_service

    monkeypatch.setattr(
        refactor_service,
        "get_llm_gateway",
        lambda: _FakeGateway("this is not json at all"),
    )
    repo_id_str, entity_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{entity_id_str}/propose"
    )
    assert response.status_code == 502, response.text


def test_propose_refactor_llm_error_returns_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.refactor as refactor_service

    class _BoomGateway:
        def complete(self, prompt: str, system: str = "") -> object:
            raise RuntimeError("provider down")

    monkeypatch.setattr(refactor_service, "get_llm_gateway", lambda: _BoomGateway())
    repo_id_str, entity_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{entity_id_str}/propose"
    )
    assert response.status_code == 502, response.text


def test_propose_refactor_404_unknown_repository(client: TestClient) -> None:
    random_repo = str(uuid.uuid4())
    random_entity = str(uuid.uuid4())
    response = client.post(
        f"/api/v1/repositories/{random_repo}/refactors/{random_entity}/propose"
    )
    assert response.status_code == 404


def test_propose_refactor_404_unknown_entity(client: TestClient) -> None:
    repo_id_str, _ = _upload_and_analyze(client, "python_basic")
    random_entity = str(uuid.uuid4())

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{random_entity}/propose"
    )
    assert response.status_code == 404


def test_propose_refactor_original_unchanged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify the original repo checksum stays stable across two calls (repo never mutated)."""
    import app.services.refactor as refactor_service

    monkeypatch.setattr(
        refactor_service, "get_llm_gateway", lambda: _FakeGateway(VALID_PROPOSAL_JSON)
    )
    repo_id_str, entity_id_str = _upload_and_analyze(client, "python_basic")

    r1 = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{entity_id_str}/propose"
    )
    r2 = client.post(
        f"/api/v1/repositories/{repo_id_str}/refactors/{entity_id_str}/propose"
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    # The original source and its checksum must be identical across both calls
    d1, d2 = r1.json()["data"], r2.json()["data"]
    assert d1["original"] == d2["original"]
    assert d1["originalChecksum"] == d2["originalChecksum"]


def test_detect_breaking_changes_unit() -> None:
    from app.db.session import SessionLocal
    from app.db.models.entity import Entity
    from app.services.refactor import detect_breaking_changes
    import uuid

    with SessionLocal() as db:
        file_id = uuid.uuid4()
        entity = Entity(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            file_id=file_id,
            name="test_func",
            type="function",
            language="python",
            line_start=1,
            line_end=10,
        )

        # Test 1: No changes
        original = "def test_func(x, y):\n    return x + y"
        proposed = "def test_func(x, y):\n    # docstring\n    return x + y"
        res = detect_breaking_changes(db, entity, original, proposed)
        assert res.detected is False
        assert len(res.changes) == 0

        # Test 2: Removed arg (HIGH)
        proposed = "def test_func(x):\n    return x"
        res = detect_breaking_changes(db, entity, original, proposed)
        assert res.detected is True
        assert len(res.changes) == 1
        assert res.changes[0].impact == "HIGH"
        assert "removed" in res.changes[0].reason

        # Test 3: Added required arg (HIGH)
        proposed = "def test_func(x, y, z):\n    return x + y + z"
        res = detect_breaking_changes(db, entity, original, proposed)
        assert res.detected is True
        assert len(res.changes) == 1
        assert res.changes[0].impact == "HIGH"
        assert "required" in res.changes[0].reason.lower()

        # Test 4: Exception raised (MEDIUM)
        proposed = "def test_func(x, y):\n    raise ValueError('error')"
        res = detect_breaking_changes(db, entity, original, proposed)
        assert res.detected is True
        assert any(c.impact == "MEDIUM" for c in res.changes)

        # Test 5: Java signature change
        java_entity = Entity(
            id=uuid.uuid4(),
            repository_id=uuid.uuid4(),
            file_id=file_id,
            name="calc",
            type="method",
            language="java",
            line_start=1,
            line_end=10,
        )
        original_java = "public int calc(int a, String b) {}"
        proposed_java = "public int calc(int a, String b, double c) {}"
        res = detect_breaking_changes(db, java_entity, original_java, proposed_java)
        assert res.detected is True
        assert res.changes[0].impact == "HIGH"
        assert "parameter count" in res.changes[0].reason.lower()
