"""Entity details and explanation API routes (T-10)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.explanation import EntitySummary, ExplanationEnvelope
from app.schemas.impact import ImpactEnvelope
from app.services.explanation import generate_explanation
from app.services.impact import calculate_impact

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]


@router.get(
    "/repositories/{repository_id}/entities/{entity_id}/explanation",
    response_model=ExplanationEnvelope,
)
def get_entity_explanation(
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    db: DbSession,
) -> ExplanationEnvelope:
    """Return a structured 10-field LLM explanation with evidence citations for an entity."""
    explanation_data = generate_explanation(db, repository_id, entity_id)
    return ExplanationEnvelope(data=explanation_data)


@router.get(
    "/repositories/{repository_id}/entities/{entity_id}/impact",
    response_model=ImpactEnvelope,
)
def get_entity_impact(
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    db: DbSession,
) -> ImpactEnvelope:
    """Return entity callers, callees, aggregated impact level, and impact reason."""
    impact_data = calculate_impact(db, repository_id, entity_id)
    return ImpactEnvelope(data=impact_data)


@router.get(
    "/repositories/{repository_id}/entities/{entity_id}",
    response_model=dict,
)
def get_entity_details(
    repository_id: uuid.UUID,
    entity_id: uuid.UUID,
    db: DbSession,
) -> dict:
    """Return entity metadata and AST facts."""
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")

    entity = db.get(Entity, entity_id)
    if entity is None or entity.repository_id != repository_id:
        raise HTTPException(status_code=404, detail="entity not found")

    file_row = db.get(File, entity.file_id)
    rel_path = file_row.path if file_row else "unknown"

    summary = EntitySummary(
        id=entity.id,
        name=entity.name,
        type=entity.type,
        file=rel_path,
        line_start=entity.line_start,
        line_end=entity.line_end,
    )

    data = {
        "entity": summary.model_dump(by_alias=True),
        "signature": entity.signature,
        "language": entity.language,
        "complexity": entity.complexity,
        "isPublic": entity.is_public,
        "docstring": entity.docstring,
        "metadata": entity.metadata_json or {},
    }
    return {"data": data, "error": None}
