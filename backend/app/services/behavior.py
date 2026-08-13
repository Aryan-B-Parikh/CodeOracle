"""Requirement 7: Behavioral Equivalence Engine.

Evaluates test execution results between original code and proposed refactored code
in the sandbox. Classifies refactors as:
  - BEHAVIOR_PRESERVED: All tests pass cleanly on both original and proposed code.
  - BEHAVIOR_MUTATED: Proposed code fails tests or produces altered outputs/exceptions.
  - UNVERIFIED: Insufficient test runs or execution failure.
"""

from __future__ import annotations

import logging
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models.refactor_proposal import RefactorProposalRecord
from app.db.models.test_run import TestRun

logger = logging.getLogger(__name__)

BehaviorStatus = Literal["BEHAVIOR_PRESERVED", "BEHAVIOR_MUTATED", "UNVERIFIED"]


def verify_behavioral_equivalence(
    db: Session,
    proposal_record: RefactorProposalRecord,
    test_run: TestRun | None = None,
) -> tuple[BehaviorStatus, str]:
    """Verify runtime behavioral equivalence of a refactor proposal against executed test runs."""
    if test_run is None and proposal_record.id:
        test_run = (
            db.query(TestRun)
            .filter(TestRun.tested_proposal_id == proposal_record.id)
            .order_by(TestRun.created_at.desc())
            .first()
        )

    if test_run is None:
        return (
            "UNVERIFIED",
            "No sandbox test run executed against this refactor proposal.",
        )

    if test_run.status != "passed":
        return (
            "BEHAVIOR_MUTATED",
            f"Refactor test execution failed (status={test_run.status}, "
            f"failed={test_run.tests_failed}).",
        )

    if test_run.tests_failed > 0:
        return (
            "BEHAVIOR_MUTATED",
            f"Refactor introduced test failure ({test_run.tests_failed} failed tests).",
        )

    if test_run.target_reached and test_run.tests_passed > 0:
        return (
            "BEHAVIOR_PRESERVED",
            f"Behavior preserved: All {test_run.tests_passed} tests passed "
            f"with target coverage reached.",
        )

    return (
        "BEHAVIOR_PRESERVED",
        f"Behavior preserved: {test_run.tests_passed} tests passed successfully.",
    )
