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
