"""Refactor proposal API routes (T-17)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.refactor import RefactorProposal, RefactorProposalEnvelope
from app.services.refactor import propose_refactor

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/repositories/{repository_id}/refactors/{entity_id}/propose",
    response_model=RefactorProposalEnvelope,
    status_code=200,
)
def propose_refactor_endpoint(
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    db: DbSession,
) -> RefactorProposalEnvelope:
    """Generate a modernization proposal (original vs. proposed + WHY list).

    The original repository files are never modified; the response includes
    a SHA-256 checksum of the original source to verify this post-request.
    """
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    try:
        proposal: RefactorProposal = propose_refactor(db, repository, entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RefactorProposalEnvelope(data=proposal)
