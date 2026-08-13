"""Test environment: isolated DB + temp upload dir, set before app import."""

import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="codeoracle-tests-")
os.environ.setdefault("UPLOAD_DIR", _TEST_UPLOAD_DIR)
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")
# Tests must be hermetic: the LLM gateway falls back to deterministic AST-fact
# generators, so the pipeline never depends on a live model or a local .env key.
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ["LLM_API_KEY"] = ""

import app.db.models  # noqa: E402, F401
import pytest  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Prepare local SQLite schema without destroying CI's migrated PostgreSQL schema.

    CI runs Alembic against PostgreSQL before pytest. Keeping that schema intact
    ensures migration-owned objects such as the pgvector HNSW index are tested
    exactly as production creates them.
    """
    if engine.dialect.name == "sqlite":
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


@pytest.fixture()
def client(_schema: None) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
