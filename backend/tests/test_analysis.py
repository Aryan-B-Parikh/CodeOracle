"""Analysis service persistence tests (T-04)."""

import io
import uuid
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
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


def test_analyze_python_basic_persists_graph(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("python_basic.zip", _fixture_zip("python_basic"), "application/zip")},
    )
    assert response.status_code == 201
    repository_id = uuid.UUID(response.json()["data"]["id"])

    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None

        result = analyze_repository(db, repository)
        assert result["files_analyzed"] == 8
        assert result["entities"] == 23

        entity_count = db.query(Entity).filter(Entity.repository_id == repository_id).count()
        assert entity_count == 23

        db.refresh(repository)
        assert repository.entity_count == 23

        calls = db.query(Call).filter(Call.repository_id == repository_id).all()
        resolved = next(c for c in calls if c.callee_name == "apply_discount" and c.caller is not None)
        assert resolved.callee_id is not None
        assert resolved.external is False
        external = next(c for c in calls if c.callee_name == "customer.load_customer")
        assert external.callee_id is None
        assert external.external is True

        billing = (
            db.query(File)
            .filter(File.repository_id == repository_id, File.path == "billing.py")
            .one()
        )
        assert {i.module for i in billing.imports} == {"database", "customer", "tax"}
        assert all(not i.is_external for i in billing.imports)

        database_file = (
            db.query(File)
            .filter(File.repository_id == repository_id, File.path == "database.py")
            .one()
        )
        typing_import = next(i for i in database_file.imports if i.module == "typing")
        assert typing_import.is_external is True

        tax_file = (
            db.query(File)
            .filter(File.repository_id == repository_id, File.path == "tax.py")
            .one()
        )
        tax_entity = (
            db.query(Entity)
            .filter(
                Entity.repository_id == repository_id,
                Entity.file_id == tax_file.id,
                Entity.name == "get_tax_rate",
            )
            .one()
        )
        assert tax_entity.complexity == 2
        assert tax_entity.metadata_json["globals"] == ["TAX_RATES", "UnknownRegionError"]

        invoice_error = (
            db.query(Entity)
            .filter(
                Entity.repository_id == repository_id,
                Entity.file_id == billing.id,
                Entity.name == "InvoiceError",
            )
            .one()
        )
        assert invoice_error.type == "class"


def test_analyze_java_basic_persists_graph(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/upload",
        files={"file": ("java_basic.zip", _fixture_zip("java_basic"), "application/zip")},
    )
    assert response.status_code == 201
    repository_id = uuid.UUID(response.json()["data"]["id"])

    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        assert repository is not None

        result = analyze_repository(db, repository)
        assert result["entities"] == 27

        db.refresh(repository)
        assert repository.entity_count == 27

        invoice_file = (
            db.query(File)
            .filter(
                File.repository_id == repository_id,
                File.path.endswith("Invoice.java"),
            )
            .one()
        )
        total = (
            db.query(Entity)
            .filter(
                Entity.repository_id == repository_id,
                Entity.file_id == invoice_file.id,
                Entity.name == "total",
            )
            .one()
        )
        resolved_call = next(
            c
            for c in total.calls_made
            if c.callee_name == "discount" and c.caller_id == total.id
        )
        assert resolved_call.callee_id is not None
        assert resolved_call.external is False

        import_modules = {i.module for i in invoice_file.imports}
        assert import_modules == {"java.util.List", "java.util.Map"}
        assert all(i.is_external for i in invoice_file.imports)
