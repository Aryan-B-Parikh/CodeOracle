"""Semantic index search tests (T-08)."""

import io
import uuid
import zipfile
from pathlib import Path

from app.db.models.chunk import Chunk
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


def _search(client: TestClient, repository_id: str, query: str) -> list[dict]:
    response = client.get(
        f"/api/v1/repositories/{repository_id}/search", params={"q": query}
    )
    assert response.status_code == 200
    return response.json()["data"]["results"]


def test_index_store_levels_and_entities(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "python_basic")
    with SessionLocal() as db:
        chunks = db.query(Chunk).filter(Chunk.repository_id == uuid.UUID(repository_id)).all()
        levels = {chunk.level for chunk in chunks}
        assert {"module", "function", "class"} <= levels
        entity_chunks = [c for c in chunks if c.entity_id is not None]
        assert len(entity_chunks) == 20  # test/conftest sources are excluded
        assert all(len(c.embedding) > 0 for c in chunks)


def test_search_python_ranks_tax_calculation(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "python_basic")
    results = _search(client, repository_id, "calculate tax")

    names = [r["qualifiedName"] or "" for r in results]
    assert "calculate_tax" in names[:3]

    top_entity = next((r for r in results if r["entityId"]), None)
    assert top_entity is not None
    assert top_entity["qualifiedName"] == "calculate_tax"
    assert top_entity["file"] == "tax.py"
    assert top_entity["type"] == "function"
    assert top_entity["lineStart"] and top_entity["lineEnd"]
    assert 0.0 < top_entity["score"] <= 1.0
    assert results[0]["score"] >= results[1]["score"]


def test_search_python_matches_invoice_logic(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "python_basic")
    results = _search(client, repository_id, "invoice discount customer")

    names = [r["qualifiedName"] or "" for r in results]
    assert any(
        "calculate_invoice" in n or "apply_discount" in n or "describe_invoice" in n
        for n in names[:5]
    )


def test_search_module_level_chunk(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "python_basic")
    results = _search(client, repository_id, "data layer connection fetch invoices")

    module_results = [
        r for r in results if r["level"] == "module" and r["file"] == "database.py"
    ]
    assert module_results, "expected a database.py module chunk in the results"


def test_search_java_ranks_payment_charge(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "java_legacy")
    results = _search(client, repository_id, "payment charge refund")

    assert results
    top = results[0]
    assert top["file"].endswith("PaymentService.java")
    assert top["type"] == "method"


def test_search_empty_query_rejected(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "python_basic")
    response = client.get(
        f"/api/v1/repositories/{repository_id}/search", params={"q": ""}
    )
    assert response.status_code == 422


def test_search_missing_repository_returns_404(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/repositories/{uuid.uuid4()}/search", params={"q": "tax"}
    )
    assert response.status_code == 404