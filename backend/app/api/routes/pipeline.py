"""Analysis pipeline API: start a Celery analysis job + live status (T-07)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.analysis import Analysis
from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.analysis import AnalysisEnvelope, AnalysisOut, RepositoryStatusOut, StatusEnvelope
from app.services.pipeline import (
    current_stage,
    initial_pipeline_state,
    latest_analysis,
)
from app.workers.tasks import run_analysis_task

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]

_RUNNING_STATES = ("queued", "running")


@router.post(
    "/repositories/{repository_id}/analyze",
    response_model=AnalysisEnvelope,
    status_code=202,
)
def start_analysis(
    repository_id: uuid.UUID,
    db: DbSession,
) -> AnalysisEnvelope:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    existing = latest_analysis(db, repository_id)
    if existing is not None and existing.status in _RUNNING_STATES:
        raise HTTPException(status_code=409, detail="analysis already in progress")

    analysis = Analysis(
        repository_id=repository_id,
        status="queued",
        pipeline_state=initial_pipeline_state(),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    run_analysis_task.delay(str(repository_id))
    db.refresh(analysis)
    return AnalysisEnvelope(data=AnalysisOut.model_validate(analysis))


@router.get("/repositories/{repository_id}/status", response_model=StatusEnvelope)
def get_repository_status(
    repository_id: uuid.UUID,
    db: DbSession,
) -> StatusEnvelope:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    analysis = latest_analysis(db, repository_id)
    pipeline_state = dict(analysis.pipeline_state or {}) if analysis is not None else {}
    payload = RepositoryStatusOut(
        repository_status=repository.status,
        analysis_status=analysis.status if analysis is not None else None,
        current_stage=current_stage(pipeline_state),
        pipeline_state=pipeline_state,
    )
    return StatusEnvelope(data=payload)