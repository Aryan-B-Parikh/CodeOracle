"""Refactor Safety Score API routes (T-18 & T-19)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.refactor_proposal import RefactorProposalRecord
from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.safety import SafetyScoreEnvelope
from app.services.safety import calculate_safety_score

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/repositories/{repository_id}/refactors/{proposal_id}/safety",
    response_model=SafetyScoreEnvelope,
    status_code=200,
)
@router.get(
    "/repositories/{repository_id}/refactors/{proposal_id}/safety",
    response_model=SafetyScoreEnvelope,
    status_code=200,
)
def get_refactor_safety_score(
    repository_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: DbSession,
) -> SafetyScoreEnvelope:
    """Compute the 0-100 Refactor Safety Score and list breaking changes."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    proposal_record = db.get(RefactorProposalRecord, proposal_id)
    if proposal_record is None or proposal_record.repository_id != repository_id:
        raise HTTPException(status_code=404, detail="proposal not found")

    safety_data = calculate_safety_score(db, repository, proposal_record)
    return SafetyScoreEnvelope(data=safety_data)
