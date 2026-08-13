"""Sandbox execution service (T-14): Docker container test execution & coverage measurement."""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path
from typing import Any as _Any

from sqlalchemy.orm import Session

from app.db.models.entity import Entity
from app.db.models.repository import Repository
from app.db.models.test_case import TestCase
from app.db.models.test_run import TestRun
from app.services.analysis import repository_root

SANDBOX_DIR = Path(__file__).resolve().parents[2] / "sandbox"
if str(SANDBOX_DIR) not in sys.path:
    sys.path.insert(0, str(SANDBOX_DIR))

sandbox_run: _Any = None
sandbox_stage: _Any = None
try:
    import importlib as _il

    sandbox_run = _il.import_module("run")
    sandbox_stage = _il.import_module("stage")
    _SANDBOX_AVAILABLE = True
except Exception:
    _SANDBOX_AVAILABLE = False

logger = logging.getLogger(__name__)

LANGS = ("python", "java")


def _choose_language(repository: Repository) -> str:
    """Pick the execution language from actual source files, not dict key order.

    ``repository.languages`` always contains an entry per supported language
    (plus ``other``), so its key order is meaningless. This uses the same
    logic as the test generator: majority of non-test source files.
    """
    file_languages = [
        f.language
        for f in repository.files
        if f.language in LANGS and "test" not in f.path.lower()
    ]
    if not file_languages:
        entity_languages = [
            e.language for e in repository.entities if e.language in LANGS
        ]
        file_languages = entity_languages
    if not file_languages:
        present = [
            lang for lang in LANGS if repository.languages.get(lang, False)
        ]
        if present:
            return present[0]
        return "python"
    counts = Counter(file_languages)
    return max(counts, key=lambda lang: (counts[lang], lang == "python"))


def _match_target_entity(
    db: Session, repository_id: uuid.UUID, case_name: str
) -> uuid.UUID | None:
    """Best-effort link: junitxml case names are ``test_<entity>_...``."""
    tail = case_name[len("test_") :] if case_name.startswith("test_") else case_name
    for sep in ("_main_branch", "_exception_path", "_uncovered"):
        if sep in tail:
            tail = tail.split(sep)[0]
            break
    else:
        tail = tail.split("_")[0]
    entity = (
        db.query(Entity)
        .filter(Entity.repository_id == repository_id, Entity.name == tail)
        .first()
    )
    return entity.id if entity else None


def is_docker_sandbox_ready() -> bool:
    """Check if Docker daemon is running and sandbox image is available."""
    if not _SANDBOX_AVAILABLE or shutil.which("docker") is None:
        return False
    try:
        import subprocess

        res = subprocess.run(
            ["docker", "image", "inspect", sandbox_run.IMAGE],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except Exception:
        return False


def execute_sandbox_test_run(
    db: Session,
    repository: Repository,
    test_code: str | None = None,
    timeout: int = 60,
) -> TestRun:
    """Execute tests inside the hardened Docker sandbox and capture coverage metrics.

    Test counts and per-testcase records come from the runner's junit/surefire
    report (``pytest --junitxml`` / Maven surefire); nothing is derived arithmetically.
    """
    language = _choose_language(repository)
    try:
        root_dir = repository_root(repository)
    except Exception:
        from app.config import get_settings

        root_dir = get_settings().upload_dir / str(repository.id)
        root_dir.mkdir(parents=True, exist_ok=True)

    with (
        tempfile.TemporaryDirectory(prefix="codeoracle-run-") as tmp_dir,
        tempfile.TemporaryDirectory(prefix="codeoracle-tests-") as input_tests_tmp,
    ):
        staging_dir = Path(tmp_dir)
        input_tests_dir = Path(input_tests_tmp)

        if test_code:
            test_file_name = (
                "test_generated.py" if language == "python" else "GeneratedTest.java"
            )
            (input_tests_dir / test_file_name).write_text(test_code, encoding="utf-8")

        tests_report: dict | None = None
        timed_out = False
        exit_code = 0
        reason = "completed"
        coverage_data: dict | None = None
        log_output = ""

        if is_docker_sandbox_ready():
            try:
                sandbox_stage.stage(
                    root_dir, language, input_tests_dir if test_code else None, staging_dir
                )
                run_res = sandbox_run.run(
                    staging_dir, language, timeout=timeout, image=sandbox_run.IMAGE
                )
                exit_code = int(run_res.get("exitCode", 0))
                timed_out = bool(run_res.get("timedOut", False))
                reason = str(run_res.get("reason", "completed"))
                coverage_data = (
                    run_res.get("coverage")
                    if isinstance(run_res.get("coverage"), dict)
                    else None
                )
                tests_report = (
                    run_res.get("tests")
                    if isinstance(run_res.get("tests"), dict)
                    else None
                )
                log_output = str(run_res.get("log", ""))
            except Exception as exc:
                logger.warning("Docker sandbox run exception: %s", exc)
                exit_code = 125
                reason = f"sandbox error: {exc}"
        else:
            logger.warning("Docker sandbox unavailable; failing test run closed")
            exit_code = 125
            reason = "Docker daemon unavailable (sandbox environment requirement)"
            log_output = (
                "Execution failed closed: Docker sandbox daemon is offline or image missing."
            )

        is_passed = (exit_code == 0) and not timed_out
        status = "passed" if is_passed else "failed"

        line_coverage = (
            float(coverage_data.get("lineCoverage", 0.0)) if coverage_data else 0.0
        )
        branch_coverage = (
            float(coverage_data.get("branchCoverage", 0.0)) if coverage_data else 0.0
        )
        uncovered_lines = (
            coverage_data.get("uncoveredLines", [])
            if coverage_data and isinstance(coverage_data.get("uncoveredLines"), list)
            else []
        )
        target_reached = (line_coverage >= 60.0) and is_passed

        cases = (
            tests_report.get("cases", [])
            if isinstance(tests_report, dict)
            and isinstance(tests_report.get("cases"), list)
            else []
        )
        tests_generated = int(tests_report.get("generated", 0)) if tests_report else 0
        tests_passed = sum(1 for c in cases if c.get("status") == "passed")
        tests_failed = sum(1 for c in cases if c.get("status") == "failed")
        if not cases and tests_report:
            tests_passed = int(tests_report.get("passed", 0))
            tests_failed = int(tests_report.get("failed", 0))

        failed_tests = [
            {
                "name": str(c.get("name", "")),
                "targetEntity": (
                    str(target_id)
                    if (
                        target_id := _match_target_entity(
                            db, repository.id, str(c.get("name", ""))
                        )
                    )
                    else None
                ),
                "message": f"Test failed (exit code {exit_code}, reason: {reason})",
            }
            for c in cases
            if c.get("status") == "failed"
        ]
        if not is_passed and not failed_tests and status == "failed" and cases:
            failed_tests.append(
                {
                    "name": "sandbox_execution",
                    "targetEntity": "sandbox",
                    "message": f"Execution failed ({reason}, exit code {exit_code})",
                }
            )

        test_run = TestRun(
            repository_id=repository.id,
            status=status,
            iteration=1,
            tests_generated=tests_generated,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            target=60.0,
            target_reached=target_reached,
            uncovered_lines=uncovered_lines,
            failed_tests=failed_tests,
            test_code=test_code,
            log=log_output,
        )
        db.add(test_run)
        db.commit()
        db.refresh(test_run)

        for case in cases:
            target_entity_id = _match_target_entity(
                db, repository.id, str(case.get("name", ""))
            )
            db.add(
                TestCase(
                    test_run_id=test_run.id,
                    name=str(case.get("name", "unknown")),
                    target_entity_id=target_entity_id,
                    status=str(case.get("status", "passed")),
                    coverage_line_nums=None,
                    duration_ms=int(case.get("durationMs", 0)),
                )
            )
        db.commit()

        return test_run