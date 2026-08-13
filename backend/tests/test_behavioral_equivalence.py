"""Unit tests for Behavioral Equivalence Engine (Requirement 7)."""

from __future__ import annotations

import uuid

from app.db.models.refactor_proposal import RefactorProposalRecord
from app.db.models.test_run import TestRun
from app.db.session import SessionLocal
from app.services.behavior import verify_behavioral_equivalence


def test_behavioral_equivalence_preserved() -> None:
    proposal_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    record = RefactorProposalRecord(
        id=proposal_id,
        repository_id=repo_id,
        entity_id=entity_id,
        entity_name="tax_calc",
        original_checksum="abc",
    )
    test_run = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        tested_proposal_id=proposal_id,
        status="passed",
        tests_passed=5,
        tests_failed=0,
        target_reached=True,
    )

    with SessionLocal() as db:
        status, rationale = verify_behavioral_equivalence(db, record, test_run)
        assert status == "BEHAVIOR_PRESERVED"
        assert "Behavior preserved" in rationale


def test_behavioral_equivalence_mutated_on_failed_tests() -> None:
    proposal_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    record = RefactorProposalRecord(
        id=proposal_id,
        repository_id=repo_id,
        entity_id=entity_id,
        entity_name="tax_calc",
        original_checksum="abc",
    )
    test_run = TestRun(
        id=uuid.uuid4(),
        repository_id=repo_id,
        tested_proposal_id=proposal_id,
        status="failed",
        tests_passed=2,
        tests_failed=1,
        target_reached=False,
    )

    with SessionLocal() as db:
        status, rationale = verify_behavioral_equivalence(db, record, test_run)
        assert status == "BEHAVIOR_MUTATED"
        assert "Refactor test execution failed" in rationale


def test_behavioral_equivalence_unverified_missing_run() -> None:
    proposal_id = uuid.uuid4()
    record = RefactorProposalRecord(
        id=proposal_id,
        repository_id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        entity_name="tax_calc",
        original_checksum="abc",
    )

    with SessionLocal() as db:
        status, rationale = verify_behavioral_equivalence(db, record, None)
        assert status == "UNVERIFIED"
        assert "No sandbox test run" in rationale
