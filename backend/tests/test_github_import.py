"""Requirement 4: GitHub Repository Import End-to-End Acceptance Test.

Verifies POST /api/v1/repositories/import endpoint flow:
  GitHub URL -> Git Clone -> Scan -> AST Facts -> Graph -> Semantic Index -> Summary

Performs deterministic local Git repository clone test and compares normalized
semantic outputs (LOC, language counts, entity definitions, and graph edges).
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

from app.db.models.call import Call
from app.db.models.chunk import Chunk
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "python_basic"


def _create_local_git_repo(tmp_path: Path) -> Path:
    """Initialize a local git repository fixture for deterministic offline import testing."""
    repo_dir = tmp_path / "sample_git_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixture files
    for item in FIXTURES.glob("*.py"):
        (repo_dir / item.name).write_text(item.read_text(encoding="utf-8"), encoding="utf-8")

    # Git init and initial commit
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "TestUser"], cwd=repo_dir, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@oracle.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True
    )
    return repo_dir


def test_github_repository_import_e2e(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test POST /api/v1/repositories/import with mocked public git repository."""
    import app.services.ingestion as ingestion

    git_repo_path = _create_local_git_repo(tmp_path)
    public_git_url = "https://github.com/example/python-basic.git"

    def fake_clone(url: str, dest: Path, timeout: int = 300) -> None:
        shutil.copytree(git_repo_path, dest, dirs_exist_ok=True)

    import shutil
    monkeypatch.setattr(ingestion, "clone_repository", fake_clone)

    response = client.post(
        "/api/v1/repositories/import",
        json={"github_url": public_git_url},
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    assert payload["error"] is None
    repo_data = payload["data"]

    assert repo_data["sourceType"] == "github"
    assert repo_data["githubUrl"] == public_git_url
    repo_id = uuid.UUID(repo_data["id"])

    with SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        assert repo is not None

        # Execute full analysis pipeline
        analyze_repository(db, repo)

        file_count = db.query(File).filter(File.repository_id == repo_id).count()
        entity_count = db.query(Entity).filter(Entity.repository_id == repo_id).count()
        call_count = db.query(Call).filter(Call.repository_id == repo_id).count()
        chunk_count = db.query(Chunk).filter(Chunk.repository_id == repo_id).count()

        # Normalized semantic assertions
        assert repo.loc > 0
        assert file_count >= 2
        assert entity_count >= 3
        assert call_count >= 1
        assert chunk_count >= 1
        assert "python" in repo.languages


def test_github_import_security_rejections(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify security rejection of unauthorized schemes and local addresses."""
    # 1. file:// scheme
    res = client.post("/api/v1/repositories/import", json={"github_url": "file:///etc/passwd"})
    assert res.status_code == 422

    # 2. ssh:// scheme
    res = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "ssh://git@internal-server/repo.git"},
    )
    assert res.status_code == 422

    # 3. git@ scp syntax
    res = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "git@github.com:owner/repo.git"},
    )
    assert res.status_code == 422

    # 4. localhost SSRF attempt
    res = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "http://localhost:8080/repo.git"},
    )
    assert res.status_code == 422

    # 5. IPv4 loopback IP SSRF attempt
    res = client.post("/api/v1/repositories/import", json={"github_url": "https://127.0.0.1/repo.git"})
    assert res.status_code == 422

    # 6. IPv4 private network IP SSRF attempt (10.x, 172.16.x, 192.168.x)
    for priv_ip in ["10.0.0.1", "172.16.0.1", "192.168.1.1"]:
        res = client.post(
            "/api/v1/repositories/import",
            json={"github_url": f"https://{priv_ip}/repo.git"},
        )
        assert res.status_code == 422

    # 7. IPv4 link-local (169.254.x)
    res = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "https://169.254.169.254/repo.git"},
    )
    assert res.status_code == 422

    # 8. IPv4 reserved & unspecified (0.0.0.0, 240.0.0.1, 100.64.0.1)
    for res_ip in ["0.0.0.0", "240.0.0.1", "100.64.0.1"]:
        res = client.post(
            "/api/v1/repositories/import",
            json={"github_url": f"https://{res_ip}/repo.git"},
        )
        assert res.status_code == 422

    # 9. IPv6 loopback, link-local, and unique local
    for ip6 in ["::1", "fe80::1", "fc00::1"]:
        res = client.post(
            "/api/v1/repositories/import",
            json={"github_url": f"https://[{ip6}]/repo.git"},
        )
        assert res.status_code == 422

    # 10. DNS failure fail-closed rejection
    res = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "https://nonexistent-domain-that-fails-dns-xyz987.invalid/repo.git"},
    )
    assert res.status_code == 422
    assert "DNS lookup failed" in res.json()["detail"] or "Failed to resolve" in res.json()["detail"]

    # 11. Mixed DNS A + AAAA resolution where one IP is private
    import socket

    def fake_getaddrinfo(host: str, port: object, **kwargs: object) -> list[object]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),  # Public IPv4
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fe80::1", 0, 0, 0)),  # Private IPv6
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    res = client.post(
        "/api/v1/repositories/import",
        json={"github_url": "https://mixed-resolution.example.com/repo.git"},
    )
    assert res.status_code == 422
    assert "restricted IP" in res.json()["detail"]


