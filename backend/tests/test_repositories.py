"""Repository ingestion API tests (T-03)."""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.services.ingestion as ingestion


def make_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _upload(client: TestClient, payload: bytes, filename: str = "repo.zip"):
    return client.post(
        "/api/v1/repositories/upload",
        files={"file": (filename, payload, "application/zip")},
    )


def test_upload_python_zip(client: TestClient) -> None:
    payload = make_zip({"billing.py": "def calc():\n    return 1\n"})
    response = _upload(client, payload, "billing.zip")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "billing"
    assert data["sourceType"] == "zip"
    assert data["languages"] == {"python": True, "java": False, "other": False}
    assert data["loc"] == 2
    assert data["fileCount"] == 1
    assert data["status"] == "uploaded"
    assert data["warnings"] == []

    fetched = client.get(f"/api/v1/repositories/{data['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["data"]["loc"] == 2


def test_upload_mixed_languages(client: TestClient) -> None:
    payload = make_zip(
        {
            "app.py": "import os\nprint(os.name)\n",
            "src/Main.java": "public class Main {}\n",
        }
    )
    response = _upload(client, payload, "mixed.zip")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["languages"] == {"python": True, "java": True, "other": False}
    assert data["fileCount"] == 2


def test_upload_unsupported_only_is_not_failure(client: TestClient) -> None:
    payload = make_zip(
        {
            "README.md": "# hello\n",
            "script.js": "console.log(1);\n",
        }
    )
    response = _upload(client, payload, "docs.zip")

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["languages"] == {"python": False, "java": False, "other": True}
    assert data["fileCount"] == 0
    assert any("unsupported" in w for w in data["warnings"])


def test_upload_invalid_zip_is_rejected(client: TestClient) -> None:
    response = _upload(client, b"this is not a zip archive")
    assert response.status_code == 422


def test_upload_zip_with_path_traversal_is_rejected(client: TestClient) -> None:
    payload = make_zip({"../evil.py": "import os\n"})
    response = _upload(client, payload)
    assert response.status_code == 422


def test_upload_single_top_dir_is_collapsed(client: TestClient) -> None:
    payload = make_zip({"repo-name/billing.py": "x = 1\n"})
    response = _upload(client, payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["languages"] == {"python": True, "java": False, "other": False}
    assert data["fileCount"] == 1


def test_import_rejects_local_path(client: TestClient) -> None:
    response = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "file:///etc/passwd"},
    )
    assert response.status_code == 422


def test_import_creates_row_and_scans(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_clone(url: str, dest: Path, timeout: int = 300) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "app.py").write_text("def main():\n    return 0\n")

    monkeypatch.setattr(ingestion, "clone_repository", fake_clone)
    response = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "https://github.com/example/legacy-billing-system.git"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["sourceType"] == "github"
    assert data["name"] == "legacy-billing-system"
    assert data["languages"]["python"] is True
    assert data["fileCount"] == 1


@pytest.mark.network
def test_import_real_github_repo(client: TestClient) -> None:
    try:
        import httpx

        httpx.get("https://github.com", timeout=5)
    except Exception:
        pytest.skip("no network access to github")

    response = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "https://github.com/octocat/Hello-World.git"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["id"]
    assert data["sourceType"] == "github"
