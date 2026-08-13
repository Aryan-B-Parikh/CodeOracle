"""Host-side tests for the sandbox runner (T-02).

The pure unit test (build_command hardening) always runs. The integration
tests spin up real Docker containers and are skipped unless the daemon is
reachable and the `codeoracle/sandbox:latest` image is present.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SANDBOX_DIR = Path(__file__).resolve().parents[1] / "sandbox"
sys.path.insert(0, str(SANDBOX_DIR))

import run as sandbox_run  # noqa: E402
import stage as sandbox_stage  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_build_command_enforces_hardening() -> None:
    command = " ".join(
        sandbox_run.build_command(Path("."), "python", "codeoracle-sandbox-test", sandbox_run.IMAGE)
    )
    assert "--network none" in command
    assert "--cpus 1.0" in command
    assert "--memory-swap 512m" in command
    assert "--read-only" in command
    assert "--cap-drop ALL" in command
    assert "--pids-limit 128" in command
    assert "--user codeoracle" in command
    assert "/sandbox:ro" in command


def test_staging_enforces_source_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "big.py").write_text("# " + "x" * 500 + "\n")
    monkeypatch.setattr(sandbox_stage, "MAX_STAGED_SOURCE_BYTES", 100)
    with pytest.raises(sandbox_stage.StageLimitError):
        sandbox_stage.stage(source, "python", None, tmp_path / "stage")


def test_staging_enforces_tests_size_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.py").write_text("x = 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text("# " + "y" * 500 + "\n")
    monkeypatch.setattr(sandbox_stage, "MAX_GENERATED_TESTS_BYTES", 100)
    with pytest.raises(sandbox_stage.StageLimitError):
        sandbox_stage.stage(source, "python", tests, tmp_path / "stage")


def test_parse_tests_report_pytest_junit() -> None:
    stdout = (
        '<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="3" '
        'failures="1" errors="0" skipped="0">'
        '<testcase name="test_a_main_branch" classname="test_generated" time="0.012"/>'
        '<testcase name="test_b_main_branch" classname="test_generated" time="0.008">'
        "<failure>assert 0 == 1</failure></testcase>"
        '<testcase name="test_c_main_branch" classname="test_generated" time="0.021"/>'
        "</testsuite></testsuites>"
    )
    report = sandbox_run.parse_tests_report(stdout)
    assert report is not None
    assert report["generated"] == 3
    assert report["passed"] == 2
    assert report["failed"] == 1
    assert report["cases"][0] == {
        "name": "test_a_main_branch",
        "durationMs": 12,
        "status": "passed",
    }
    assert report["cases"][1]["status"] == "failed"


def test_parse_tests_report_surefire() -> None:
    stdout = (
        '<?xml version="1.0"?><testsuite name="GeneratedUnitTestSuite" tests="2" '
        'failures="0" errors="0" skipped="0">'
        '<testcase name="test_a_main_branch" classname="GeneratedUnitTestSuite" time="0.10"/>'
        '<testcase name="test_b_main_branch" classname="GeneratedUnitTestSuite" time="0.20"/>'
        "</testsuite>"
    )
    report = sandbox_run.parse_tests_report(stdout)
    assert report is not None
    assert report["generated"] == 2
    assert report["passed"] == 2
    assert report["failed"] == 0


def test_parse_tests_report_missing_returns_none() -> None:
    assert sandbox_run.parse_tests_report("no report here") is None
    assert sandbox_run.parse_tests_report("") is None


class _FakeFile:
    def __init__(self, language: str, path: str) -> None:
        self.language = language
        self.path = path


class _FakeEntity:
    def __init__(self, language: str) -> None:
        self.language = language


class _FakeRepo:
    def __init__(self, files: list, entities: list, languages: dict) -> None:
        self.files = files
        self.entities = entities
        self.languages = languages


def test_choose_language_java_repo_not_dict_order() -> None:
    """Regression: a Java-only repo must run the Java/JUnit+JaCoCo path.

    `repository.languages` always contains a key per supported language, so
    iterating its keys always yielded 'python' and Java never executed.
    """
    from app.services.sandbox_runner import _choose_language

    repo = _FakeRepo(
        files=[_FakeFile("java", "src/App.java"), _FakeFile("java", "src/Util.java")],
        entities=[_FakeEntity("java")],
        languages={"python": False, "java": True, "other": False},
    )
    assert _choose_language(repo) == "java"


def test_choose_language_python_default() -> None:
    from app.services.sandbox_runner import _choose_language

    repo = _FakeRepo(
        files=[_FakeFile("python", "app.py")],
        entities=[_FakeEntity("python")],
        languages={"python": True, "java": False, "other": False},
    )
    assert _choose_language(repo) == "python"


def test_choose_language_mixed_prefers_python() -> None:
    from app.services.sandbox_runner import _choose_language

    repo = _FakeRepo(
        files=[
            _FakeFile("java", "src/App.java"),
            _FakeFile("python", "app.py"),
            _FakeFile("python", "model.py"),
        ],
        entities=[],
        languages={"python": True, "java": True, "other": False},
    )
    assert _choose_language(repo) == "python"


def test_execute_sandbox_test_run_uses_reported_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a Docker run present, counts come from the junit/surefire report only."""
    import uuid

    from app.db.models.repository import Repository
    from app.db.session import SessionLocal
    from app.services import sandbox_runner
    from app.services.sandbox_runner import execute_sandbox_test_run

    monkeypatch.setattr(sandbox_runner, "is_docker_sandbox_ready", lambda: True)
    monkeypatch.setattr(
        sandbox_runner.sandbox_stage,
        "stage",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        sandbox_runner.sandbox_run,
        "run",
        lambda *args, **kwargs: {
            "exitCode": 0,
            "timedOut": False,
            "reason": "completed",
            "coverage": {
                "lineCoverage": 61.0,
                "branchCoverage": 40.0,
                "uncoveredLines": [],
            },
            "tests": {
                "generated": 3,
                "passed": 2,
                "failed": 1,
                "cases": [
                    {"name": "test_a_main_branch", "durationMs": 12, "status": "passed"},
                    {"name": "test_b_main_branch", "durationMs": 8, "status": "passed"},
                    {"name": "test_c_main_branch", "durationMs": 21, "status": "failed"},
                ],
            },
            "log": "",
        },
    )

    with SessionLocal() as db:
        repo = Repository(
            id=uuid.uuid4(),
            name="stats-repo",
            source_type="zip",
            languages={"python": True},
            loc=100,
        )
        db.add(repo)
        db.commit()

        test_run = execute_sandbox_test_run(db, repo, test_code="def test_x(): pass\n")
        assert test_run.status == "passed"
        assert test_run.tests_generated == 3
        assert test_run.tests_passed == 2
        assert test_run.tests_failed == 1
        assert test_run.line_coverage == 61.0
        assert test_run.target_reached is True
        assert len(test_run.failed_tests) == 1
        assert test_run.failed_tests[0]["name"] == "test_c_main_branch"

        from app.db.models.test_case import TestCase

        cases = (
            db.query(TestCase).filter(TestCase.test_run_id == test_run.id).all()
        )
        assert len(cases) == 3
        assert {c.name for c in cases} == {
            "test_a_main_branch",
            "test_b_main_branch",
            "test_c_main_branch",
        }
        assert {c.duration_ms for c in cases} == {12, 8, 21}
        # Coverage lines are only stored when actually measured per test.
        assert all(c.coverage_line_nums is None for c in cases)


def _sandbox_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(
            ["docker", "image", "inspect", sandbox_run.IMAGE],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return False
    return True


@pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image not available")
def test_python_fixture_returns_coverage_json(tmp_path: Path) -> None:
    source = FIXTURES / "python_basic"
    sandbox_stage.stage(source, "python", source / "tests", tmp_path)
    result = sandbox_run.run(tmp_path, "python", timeout=180, image=sandbox_run.IMAGE)
    assert result["exitCode"] == 0
    assert result["timedOut"] is False
    assert result["coverage"] is not None
    assert "lineCoverage" in result["coverage"]
    assert "uncoveredLines" in result["coverage"]


@pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image not available")
def test_java_fixture_returns_coverage_json(tmp_path: Path) -> None:
    source = FIXTURES / "java_basic"
    sandbox_stage.stage(source, "java", None, tmp_path)
    result = sandbox_run.run(tmp_path, "java", timeout=240, image=sandbox_run.IMAGE)
    assert result["exitCode"] == 0
    assert result["coverage"] is not None
    assert result["coverage"]["lineCoverage"] > 0
    assert "uncoveredLines" in result["coverage"]


@pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image not available")
def test_timeout_kills_runaway_fixture(tmp_path: Path) -> None:
    source = FIXTURES / "escape" / "python" / "busy_loop"
    sandbox_stage.stage(source, "python", source / "tests", tmp_path)
    result = sandbox_run.run(tmp_path, "python", timeout=15, image=sandbox_run.IMAGE)
    assert result["timedOut"] is True
    assert result["exitCode"] == 124


@pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image not available")
def test_memory_limit_kills_hog_fixture(tmp_path: Path) -> None:
    source = FIXTURES / "escape" / "python" / "memory_hog"
    sandbox_stage.stage(source, "python", source / "tests", tmp_path)
    result = sandbox_run.run(tmp_path, "python", timeout=120, image=sandbox_run.IMAGE)
    assert result["timedOut"] is False
    assert result["exitCode"] == 137


@pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image not available")
def test_stdout_limit_kills_flood_fixture(tmp_path: Path) -> None:
    source = FIXTURES / "escape" / "python" / "stdout_flood"
    sandbox_stage.stage(source, "python", source / "tests", tmp_path)
    result = sandbox_run.run(tmp_path, "python", timeout=60, image=sandbox_run.IMAGE)
    assert result["reason"] == "stdout limit exceeded"
    assert result["exitCode"] == 125


@pytest.mark.skipif(not _sandbox_ready(), reason="sandbox image not available")
def test_stderr_limit_kills_flood_fixture(tmp_path: Path) -> None:
    source = FIXTURES / "escape" / "python" / "stderr_flood"
    sandbox_stage.stage(source, "python", source / "tests", tmp_path)
    result = sandbox_run.run(tmp_path, "python", timeout=60, image=sandbox_run.IMAGE)
    assert result["reason"] == "stderr limit exceeded"
    assert result["exitCode"] == 125


def test_execute_sandbox_test_run_service() -> None:
    import uuid

    from app.db.models.repository import Repository
    from app.db.session import SessionLocal
    from app.services.sandbox_runner import execute_sandbox_test_run

    with SessionLocal() as db:
        repo = Repository(
            id=uuid.uuid4(),
            name="test-repo",
            source_type="zip",
            languages={"python": True},
            loc=100,
        )
        db.add(repo)
        db.commit()

        test_run = execute_sandbox_test_run(db, repo, test_code="def test_sample(): assert True")
        assert test_run.id is not None
        assert test_run.status in ("passed", "failed")
        assert test_run.line_coverage >= 0.0
        assert isinstance(test_run.uncovered_lines, list)

