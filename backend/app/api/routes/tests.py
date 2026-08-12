"""Test generation, execution, and coverage repair loop API routes (T-13, T-14, T-15)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.models.test_run import TestRun
from app.db.session import get_db
from app.schemas.test_run import (
    FailedTestItem,
    GenerateTestCodeEnvelope,
    TestRunData,
    TestRunEnvelope,
    UncoveredLineItem,
)
from app.services.test_generator import (
    generate_uncovered_tests,
    generate_unit_tests,
)

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


def _format_test_run_envelope(latest_run: TestRun) -> TestRunEnvelope:
    """Helper to convert database TestRun record into API TestRunEnvelope payload."""
    uncovered = [
        UncoveredLineItem(
            file=str(item.get("file", "")),
            line=int(item.get("line", 0)),
            branch=bool(item.get("branch", False)),
        )
        for item in (latest_run.uncovered_lines or [])
        if isinstance(item, dict)
    ]

    failed = [
        FailedTestItem(
            name=str(item.get("name", "")),
            target_entity=str(item.get("targetEntity", item.get("target_entity", ""))),
            message=str(item.get("message", "")),
        )
        for item in (latest_run.failed_tests or [])
        if isinstance(item, dict)
    ]

    status_label = "PASSED" if latest_run.status == "passed" else "FAILED"

    data = TestRunData(
        test_run_id=latest_run.id,
        status=latest_run.status,
        iteration=latest_run.iteration,
        tests_generated=latest_run.tests_generated,
        tests_passed=latest_run.tests_passed,
        tests_failed=latest_run.tests_failed,
        line_coverage=latest_run.line_coverage,
        branch_coverage=latest_run.branch_coverage,
        target=latest_run.target,
        target_reached=latest_run.target_reached,
        status_label=status_label,
        uncovered_lines=uncovered,
        failed_tests=failed,
        test_code=latest_run.test_code,
        created_at=latest_run.created_at,
    )

    return TestRunEnvelope(data=data)


@router.post(
    "/repositories/{repository_id}/tests/generate",
    response_model=GenerateTestCodeEnvelope,
    status_code=200,
)
def generate_tests(
    repository_id: uuid.UUID,
    db: DbSession,
) -> GenerateTestCodeEnvelope:
    """Generate runnable pytest (Python) or JUnit 4 (Java) test suite."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    result = generate_unit_tests(db, repository)
    return GenerateTestCodeEnvelope(data=result)


@router.post(
    "/repositories/{repository_id}/tests/generate-uncovered",
    response_model=TestRunEnvelope,
    status_code=200,
)
def generate_uncovered_tests_endpoint(
    repository_id: uuid.UUID,
    db: DbSession,
    max_iterations: int = Query(3, ge=1, le=10),
    target_coverage: float = Query(60.0, ge=0.0, le=100.0),
) -> TestRunEnvelope:
    """Run coverage repair loop targeting uncovered lines until target coverage is met."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    final_run = generate_uncovered_tests(
        db,
        repository,
        max_iterations=max_iterations,
        target_coverage=target_coverage,
    )
    return _format_test_run_envelope(final_run)


@router.get(
    "/repositories/{repository_id}/tests/latest",
    response_model=TestRunEnvelope,
)
def get_latest_test_run(
    repository_id: uuid.UUID,
    db: DbSession,
) -> TestRunEnvelope:
    """Return the latest test run metrics, coverage, and uncovered lines."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    latest_run = (
        db.query(TestRun)
        .filter(TestRun.repository_id == repository_id)
        .order_by(TestRun.created_at.desc())
        .first()
    )

    if latest_run is None:
        raise HTTPException(status_code=404, detail="no test run found for repository")

    return _format_test_run_envelope(latest_run)
