"""Repository and module summary API routes (T-11)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.summary import ModuleSummaryEnvelope, SummaryEnvelope
from app.services.summary import generate_module_summaries, generate_repository_summary

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/repositories/{repository_id}/summary",
    response_model=SummaryEnvelope,
)
def get_repository_summary(
    repository_id: uuid.UUID,
    db: DbSession,
) -> SummaryEnvelope:
    """Return repository overview, architecture classification, and architectural issues."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    payload = generate_repository_summary(db, repository)
    return SummaryEnvelope(data=payload)


@router.get(
    "/repositories/{repository_id}/modules/summary",
    response_model=ModuleSummaryEnvelope,
)
def get_module_summaries(
    repository_id: uuid.UUID,
    db: DbSession,
) -> ModuleSummaryEnvelope:
    """Return per-module entity summaries for a repository."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    modules = generate_module_summaries(db, repository)
    return ModuleSummaryEnvelope(data=modules)
