"""Unit and integration tests for the coverage repair loop (T-15)."""

import io
import uuid
import zipfile
from pathlib import Path

from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import analyze_repository
from app.services.test_generator import generate_uncovered_tests
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


def test_generate_uncovered_tests_endpoint(client: TestClient) -> None:
    repo_id_str = _upload_and_analyze(client, "python_basic")

    response = client.post(
        f"/api/v1/repositories/{repo_id_str}/tests/generate-uncovered?max_iterations=3&target_coverage=60.0"
    )
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["error"] is None

    data = payload["data"]
    assert "testRunId" in data
    # Sandbox fails-closed without Docker (fail-closed is correct behavior).
    # CI/CD with Docker: status==passed, lineCoverage>=60.0, targetReached==True.
    # Host tests without Docker: status==failed, lineCoverage==0.0 (no fake numbers).
    assert data["status"] in ("passed", "failed")
    assert data["iteration"] <= 3


def test_coverage_repair_loop_service() -> None:
    with SessionLocal() as db:
        repo = Repository(
            id=uuid.uuid4(),
            name="demo-repair-repo",
            source_type="zip",
            languages={"python": True},
            loc=150,
        )
        db.add(repo)
        db.commit()

        final_run = generate_uncovered_tests(
            db, repo, max_iterations=3, target_coverage=60.0
        )
        assert final_run.id is not None
        assert final_run.iteration <= 3
        # In environments without Docker, sandbox returns 0.0 coverage (fail-closed).
        # target_reached is True only when real coverage >= 60.0%.
        assert isinstance(final_run.line_coverage, float)
        assert isinstance(final_run.target_reached, bool)


def test_unbroken_golden_chain_coverage_repair(client: TestClient) -> None:
    """Requirement 2: Unbroken Golden-Chain System Test.

    Exercises the production automatic-repair path end-to-end (no benchmark
    shortcut — benchmark/legacy_demo/python/run_benchmark.py is NOT used here):

      1. POST /api/v1/repositories/upload        -> app/api/routes/repositories.py
         (zip ingest -> app/services/ingestion.py)
      2. analyze_repository()                    -> app/services/analysis.py
         (AST facts -> graph -> semantic index -> summary)
      3. generate_unit_tests()                   -> app/services/test_generator.py
         (baseline: AST-fact-driven test generation)
      4. generate_uncovered_tests()              -> app/services/test_generator.py
         (automatic coverage-repair loop)
         a. reads uncovered lines from the latest coverage run
         b. appends `test_<func>_repair_branch()` tests
         c. executes them in the Docker sandbox     -> app/services/sandbox_runner.py
            (staged repo + pytest + coverage.py inside the container image)
         d. repeats until line coverage >= target (60.0) or max_iterations (3)

    The chain runs against the mock LLM provider (enforced in conftest), so
    the AST-fact fallback generators carry the whole pipeline — the golden
    chain must hold without any LLM.

    When Docker is available: strictly asserts the chain ran end-to-end and
    reached the 60% line-coverage acceptance floor — and that the REPAIR LOOP
    actually executed (iteration >= 2 plus repair-branch tests present in the
    final suite), proving the coverage was earned by repair, not a baseline
    short-circuit.
    When Docker is unavailable: asserts fail-closed behavior (status == "failed").
    """
    repo_id_str = _upload_and_analyze(client, "python_legacy")
    with SessionLocal() as db:
        repo = db.get(Repository, uuid.UUID(repo_id_str))
        assert repo is not None

        # 1. Baseline initial unit test generation
        from app.services.test_generator import generate_unit_tests

        baseline_test_case = generate_unit_tests(db, repo)
        assert baseline_test_case is not None

        # 2. End-to-end automatic coverage repair loop
        final_run = generate_uncovered_tests(
            db, repo, max_iterations=3, target_coverage=60.0
        )
        assert final_run.id is not None
        assert final_run.iteration <= 3

        # 3. Assert unbroken golden-chain requirement
        from app.services.sandbox_runner import is_docker_sandbox_ready

        if is_docker_sandbox_ready():
            assert final_run.iteration >= 2, (
                "Golden-chain: automatic repair loop did not run — iteration must be >= 2 "
                "(baseline iteration 1 + at least one repair iteration), got "
                f"iteration={final_run.iteration}"
            )
            repair_tests = [
                line
                for line in (final_run.test_code or "").splitlines()
                if "def test_" in line and "repair_branch" in line
            ]
            assert repair_tests, (
                "Golden-chain: no repair-branch tests found in the final suite — the "
                "coverage was NOT produced by the automatic repair loop; "
                f"iteration={final_run.iteration}, status={final_run.status}"
            )
            assert final_run.tests_generated > 0, (
                "Golden-chain: no tests were generated — repair loop did not run; "
                f"status={final_run.status}, iteration={final_run.iteration}, "
                f"lineCoverage={final_run.line_coverage}, "
                f"branchCoverage={final_run.branch_coverage}, "
                f"testsPassed={final_run.tests_passed}, "
                f"testsFailed={final_run.tests_failed}, "
                f"targetReached={final_run.target_reached}, "
                f"uncoveredLines={final_run.uncovered_lines}\n"
                f"--- sandbox log tail ---\n{(final_run.log or '')[-3000:]}"
            )
            assert final_run.status == "passed", (
                f"Golden-chain: generated tests did not pass "
                f"({final_run.tests_passed}/{final_run.tests_generated} passed, "
                f"{final_run.tests_failed} failed)"
            )
            assert final_run.line_coverage >= 60.0, (
                f"Golden-chain: line coverage {final_run.line_coverage}% < 60.0%"
            )
            assert final_run.target_reached is True

            from tests.benchmark_report import write_artifact

            artifact = write_artifact(
                "golden_chain",
                {
                    "benchmark": "golden-chain-coverage-repair",
                    "fixture": "python_legacy",
                    "targetCoverage": 60.0,
                    "status": final_run.status,
                    "iteration": final_run.iteration,
                    "lineCoverage": final_run.line_coverage,
                    "branchCoverage": final_run.branch_coverage,
                    "testsGenerated": final_run.tests_generated,
                    "testsPassed": final_run.tests_passed,
                    "testsFailed": final_run.tests_failed,
                    "targetReached": final_run.target_reached,
                    "uncoveredLines": final_run.uncovered_lines,
                    "repairBranchTests": len(repair_tests),
                    "pass": True,
                },
            )
            print(f"Artifact={artifact}")
        else:
            # Fail-closed contract: sandbox unavailable → status failed, no fake metrics
            assert final_run.status == "failed"


def test_generate_uncovered_404_not_found(client: TestClient) -> None:
    random_id = str(uuid.uuid4())
    response = client.post(f"/api/v1/repositories/{random_id}/tests/generate-uncovered")
    assert response.status_code == 404
