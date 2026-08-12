"""Dependency graph API: React Flow nodes/edges for a repository (T-06)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.graph import GraphEnvelope, GraphPayload
from app.services.graph import build_graph

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/repositories/{repository_id}/graph", response_model=GraphEnvelope)
def get_repository_graph(
    repository_id: uuid.UUID,
    db: DbSession,
) -> GraphEnvelope:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    payload = build_graph(db, repository)
    return GraphEnvelope(data=GraphPayload.model_validate(payload))
