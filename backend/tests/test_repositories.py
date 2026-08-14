"""Repository ingestion API tests (T-03)."""

import asyncio
import io
import zipfile
from pathlib import Path

import app.services.ingestion as ingestion
import pytest
from app.api.routes import repositories as repo_routes
from fastapi.testclient import TestClient


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
    assert data["languageCounts"] == {"python": 1}
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
    assert data["languageCounts"] == {"python": 1, "java": 1}
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
    assert data["languageCounts"] == {"JavaScript": 1, "other": 1}
    assert data["fileCount"] == 0
    assert any("unsupported" in w for w in data["warnings"])
    assert any("JavaScript" in w for w in data["warnings"])


def test_upload_mixed_unsupported_breakdown(client: TestClient) -> None:
    payload = make_zip(
        {
            "app.py": "x = 1\n",
            "script.js": "console.log(1);\n",
            "legacy.cpp": "#include <iostream>\n",
            "data.sql": "SELECT 1;\n",
            "note.md": "# notes\n",
        }
    )
    response = _upload(client, payload)

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["languages"] == {"python": True, "java": False, "other": True}
    assert data["languageCounts"] == {
        "python": 1,
        "JavaScript": 1,
        "C++": 1,
        "SQL": 1,
        "other": 1,
    }
    assert data["fileCount"] == 1
    assert any("C++" in w and "JavaScript" in w and "SQL" in w for w in data["warnings"])


class _FakeUpload:
    def __init__(self, chunks: list[bytes]):
        self._chunks = chunks
        self._index = 0

    async def read(self, size: int) -> bytes:
        if self._index >= len(self._chunks):
            return b""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def test_stream_upload_writes_chunks(tmp_path: Path) -> None:
    dest = tmp_path / "out.bin"
    chunks = [b"a" * 4096, b"b" * 4096, b"c" * 4096]
    asyncio.run(repo_routes._stream_upload(_FakeUpload(chunks), dest, max_bytes=100_000))
    assert dest.read_bytes() == b"".join(chunks)


def test_stream_upload_enforces_size_limit(tmp_path: Path) -> None:
    dest = tmp_path / "out.bin"
    with pytest.raises(repo_routes._UploadTooLarge):
        asyncio.run(
            repo_routes._stream_upload(_FakeUpload([b"a" * 1000]), dest, max_bytes=100)
        )


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


def test_delete_repository_cascade_cleanup(client: TestClient) -> None:
    """Verify DELETE /repositories/{id} removes every repository-owned record and disk data."""
    import uuid

    from app.config import get_settings
    from app.db.models.analysis import Analysis
    from app.db.models.call import Call
    from app.db.models.chunk import Chunk
    from app.db.models.entity import Entity
    from app.db.models.file import File as FileModel
    from app.db.models.import_ import Import
    from app.db.models.inheritance import Inheritance
    from app.db.models.refactor_proposal import RefactorProposalRecord
    from app.db.models.repository import Repository
    from app.db.models.test_case import TestCase
    from app.db.models.test_run import TestRun
    from app.db.session import SessionLocal
    from app.services.analysis import analyze_repository

    payload = make_zip({"main.py": "class Child(Base):\n    def foo(self):\n        return 42\n"})
    upload_res = _upload(client, payload, "cascade_test.zip")
    assert upload_res.status_code == 201
    repo_id_str = upload_res.json()["data"]["id"]
    repo_id = uuid.UUID(repo_id_str)

    settings = get_settings()
    repo_dir = settings.upload_dir / repo_id_str

    with SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None
        analyze_repository(db, repo)

        assert db.query(FileModel).filter(FileModel.repository_id == repo_id).count() >= 1
        assert db.query(Entity).filter(Entity.repository_id == repo_id).count() >= 1
        assert db.query(Import).join(FileModel).filter(FileModel.repository_id == repo_id).count() >= 0
        assert db.query(Inheritance).filter(Inheritance.repository_id == repo_id).count() >= 0
        assert repo_dir.exists()

    del_res = client.delete(f"/api/v1/repositories/{repo_id_str}")
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deleted"] is True
    assert del_res.json()["data"]["fs_cleaned"] is True

    with SessionLocal() as db:
        assert db.get(Repository, repo_id) is None
        assert db.query(FileModel).filter(FileModel.repository_id == repo_id).count() == 0
        assert db.query(Entity).filter(Entity.repository_id == repo_id).count() == 0
        assert db.query(Call).filter(Call.repository_id == repo_id).count() == 0
        assert db.query(Chunk).filter(Chunk.repository_id == repo_id).count() == 0
        assert db.query(Import).join(FileModel).filter(FileModel.repository_id == repo_id).count() == 0
        assert db.query(Inheritance).filter(Inheritance.repository_id == repo_id).count() == 0
        assert db.query(Analysis).filter(Analysis.repository_id == repo_id).count() == 0
        assert db.query(TestCase).join(TestRun).filter(TestRun.repository_id == repo_id).count() == 0
        assert db.query(TestRun).filter(TestRun.repository_id == repo_id).count() == 0
        assert db.query(RefactorProposalRecord).filter(RefactorProposalRecord.repository_id == repo_id).count() == 0

    assert not repo_dir.exists()
