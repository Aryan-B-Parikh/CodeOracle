"""Test environment: sqlite in-memory DB + temp upload dir, set before app import."""

import os
import tempfile

os.environ.setdefault("DATABASE_URL", "sqlite://")
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="codeoracle-tests-")
os.environ.setdefault("UPLOAD_DIR", _TEST_UPLOAD_DIR)
# Run Celery tasks inline (no broker needed); set before any app import.
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "1")

import app.db.models  # noqa: E402, F401
import pytest  # noqa: E402
from app.db.session import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@pytest.fixture()
def client(_schema: None) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
