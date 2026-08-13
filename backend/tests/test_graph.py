"""Dependency graph API tests (T-06)."""

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


def _graph(client: TestClient, repository_id: str) -> dict:
    response = client.get(f"/api/v1/repositories/{repository_id}/graph")
    assert response.status_code == 200
    return response.json()["data"]


def _node_index(payload: dict) -> dict[str, dict]:
    return {node["id"]: node for node in payload["nodes"]}


def _edges_by_kind(payload: dict, kind: str) -> set[tuple[str, str]]:
    return {
        (edge["source"], edge["target"])
        for edge in payload["edges"]
        if edge["kind"] == kind
    }


def test_graph_python_basic_contract(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "python_basic")
    payload = _graph(client, repository_id)
    nodes = _node_index(payload)

    assert nodes["billing.py"]["type"] == "module"
    assert nodes["tax.py"]["type"] == "module"

    invoice = nodes["billing.py::calculate_invoice"]
    assert invoice["type"] == "function"
    assert invoice["file"] == "billing.py"
    assert invoice["complexity"] == 1

    contains = _edges_by_kind(payload, "contains")
    assert ("billing.py", "billing.py::calculate_invoice") in contains

    calls = _edges_by_kind(payload, "call")
    assert ("billing.py::calculate_invoice", "tax.py::calculate_tax") in calls
    assert ("billing.py::calculate_invoice", "database.py::insert") in calls
    assert ("billing.py::calculate_invoice", "database.py::fetch_all") in calls
    assert ("billing.py::calculate_invoice", "customer.py::load_customer") in calls

    cross_module_via_import = (
        "database.py::resolve_invoice",
        "billing.py::describe_invoice",
    )
    assert cross_module_via_import in calls
    assert ("app.py::main", "billing.py::calculate_invoice") in calls

    imports = _edges_by_kind(payload, "imports")
    assert ("billing.py", "database.py") in imports
    assert ("database.py", "billing.py") in imports

    cycles = payload["meta"]["circularDependencies"]
    assert any(set(c["cycle"]) == {"billing.py", "database.py"} for c in cycles)

    high_risk = payload["meta"]["highRiskNodeIds"]
    assert "billing.py::calculate_invoice" in high_risk
    scored_nodes = [
        node for node in payload["nodes"] if node.get("riskScore") is not None
    ]
    assert scored_nodes, "expected risk scores on entities with edges"
    max_score = max(node["riskScore"] for node in scored_nodes)
    assert nodes[high_risk[0]]["riskScore"] == max_score
    invoice_node = nodes["billing.py::calculate_invoice"]
    assert invoice_node["riskScore"] == 8


def test_graph_java_modern_inheritance_edge(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "java_modern")
    payload = _graph(client, repository_id)
    nodes = _node_index(payload)

    premium = next(
        n for n in nodes.values() if n.get("qualifiedName") == "PremiumCustomer"
    )
    customer = next(n for n in nodes.values() if n.get("qualifiedName") == "Customer")
    assert premium["type"] == "class"
    assert customer["type"] == "class"

    inherits = _edges_by_kind(payload, "inherits")
    assert (premium["id"], customer["id"]) in inherits
    assert (
        premium["file"].endswith("main/java/com/example/modern/ModernFeatures.java")
    )

    kinds = {node["type"] for node in nodes.values() if node["type"] != "module"}
    assert {"class", "interface", "enum", "record", "annotation"} <= kinds


def test_graph_layout_for_java_classes_and_methods(client: TestClient) -> None:
    repository_id = _upload_and_analyze(client, "java_basic")
    payload = _graph(client, repository_id)
    nodes = _node_index(payload)

    tax_calculator = next(
        n for n in nodes.values() if n.get("qualifiedName") == "TaxCalculator"
    )
    contains = _edges_by_kind(payload, "contains")
    expected_edge = (
        tax_calculator["id"],
        f"{tax_calculator['id'].split('::')[0]}::TaxCalculator.rateFor",
    )
    assert expected_edge in contains

    calls = _edges_by_kind(payload, "call")
    tax_file = tax_calculator["id"].split("::")[0]
    assert (f"{tax_file}::TaxCalculator.calculateTax", f"{tax_file}::TaxCalculator.round2") in calls


def test_graph_missing_repository_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/repositories/{uuid.uuid4()}/graph")
    assert response.status_code == 404