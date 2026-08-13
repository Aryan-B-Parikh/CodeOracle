from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_returns_ok_envelope() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}, "error": None}
