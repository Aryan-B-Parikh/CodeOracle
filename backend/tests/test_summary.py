"""Module & repository summary + architecture classification tests (T-11)."""

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


def test_repository_summary_and_architecture_classification(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    response = client.get(f"/api/v1/repositories/{repo_id_str}/summary")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "summary" in data
    assert "highRiskEntities" in data
    assert "provider" in data
    assert data["provider"] in ("mock", "openai", "anthropic", None)

    summary = data["summary"]
    architecture = summary["architecture"]
    assert len(architecture) > 0

    # Layer mapping check: Presentation -> Business Logic -> Data Access
    layer_map = {item["layer"]: item["modules"] for item in architecture}
    assert "Presentation" in layer_map
    assert "app.py" in layer_map["Presentation"]

    assert "Business Logic" in layer_map
    assert any(m in layer_map["Business Logic"] for m in ["billing.py", "customer.py", "tax.py"])

    assert "Data Access" in layer_map
    assert "database.py" in layer_map["Data Access"]

    # Issues check: strictly derived from static facts/graph
    issues = summary["issues"]
    assert isinstance(issues, list)
    kinds = {i["kind"] for i in issues}
    assert kinds.issubset({"circular_dependency", "global_state", "coupling"})

    # Overview check
    assert "overview" in summary
    assert isinstance(summary["overview"], str)


def test_repository_endpoint_includes_analysis_summary(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    # Generate summary explicitly
    client.get(f"/api/v1/repositories/{repo_id_str}/summary")

    response = client.get(f"/api/v1/repositories/{repo_id_str}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "analysis" in data
    assert data["analysis"] is not None
    assert "summary" in data["analysis"]
    assert "highRiskEntities" in data["analysis"]


def test_module_summaries_endpoint(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    response = client.get(f"/api/v1/repositories/{repo_id_str}/modules/summary")
    assert response.status_code == 200
    modules = response.json()["data"]
    assert isinstance(modules, list)
    assert len(modules) > 0

    files = {m["file"] for m in modules}
    assert "tax.py" in files
    assert "billing.py" in files

    tax_mod = next(m for m in modules if m["file"] == "tax.py")
    assert "calculate_tax" in tax_mod["entities"]
    assert tax_mod["entityCount"] >= 2
    assert "purpose" in tax_mod and tax_mod["purpose"] is not None
    assert "responsibilities" in tax_mod and len(tax_mod["responsibilities"]) > 0
    assert "dependencies" in tax_mod
    assert "evidence" in tax_mod and len(tax_mod["evidence"]) > 0
    first_ev = tax_mod["evidence"][0]
    assert "claim" in first_ev and "lineStart" in first_ev and "lineEnd" in first_ev


def test_summary_404_not_found(client: TestClient) -> None:
    random_id = str(uuid.uuid4())
    response = client.get(f"/api/v1/repositories/{random_id}/summary")
    assert response.status_code == 404

    mod_response = client.get(f"/api/v1/repositories/{random_id}/modules/summary")
    assert mod_response.status_code == 404
