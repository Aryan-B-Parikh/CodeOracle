"""Refactor proposal API routes (T-17).

W4 guard: this router ONLY reads and proposes — it never writes to repository files.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.refactor_proposal import RefactorProposalRecord
from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.refactor import RefactorProposal, RefactorProposalEnvelope
from app.services.refactor import propose_refactor

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


def _record_to_proposal(record: RefactorProposalRecord) -> RefactorProposal:
    return RefactorProposal(
        proposal_id=record.id,
        entity_id=record.entity_id,
        entity_name=record.entity_name,
        file_path=record.file_path,
        original=record.original,
        proposed=record.proposed,
        rationale=list(record.rationale or []),
        behavioral_differences=list(record.behavioral_differences or []),
        original_checksum=record.original_checksum,
        syntax_valid=(record.syntax_valid != "invalid"),
        validation_error=record.validation_error,
        read_only=True,
    )


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
    """Generate a validated modernization proposal (original vs. proposed + WHY list).

    W4 contract: this endpoint is read-only. It never modifies repository files.
    The response includes:
      - original_checksum: SHA-256 of original source at proposal time
      - syntax_valid: whether proposed code passed ast.parse / brace balance check
      - read_only: always True — application requires a separate future endpoint
    """
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    try:
        proposal: RefactorProposal = propose_refactor(db, repository, entity_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return RefactorProposalEnvelope(data=proposal)


@router.get(
    "/repositories/{repository_id}/refactors/{proposal_id}",
    response_model=RefactorProposalEnvelope,
    status_code=200,
)
def get_refactor_proposal(
    repository_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: DbSession,
) -> RefactorProposalEnvelope:
    """Retrieve a previously generated proposal by ID.

    W3 contract: the immutable record (original + checksum) is always reproducible.
    """
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    record = db.get(RefactorProposalRecord, proposal_id)
    if record is None or record.repository_id != repository_id:
        raise HTTPException(status_code=404, detail="proposal not found")

    return RefactorProposalEnvelope(data=_record_to_proposal(record))
