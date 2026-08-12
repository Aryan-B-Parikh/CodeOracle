"""Analysis pipeline helpers: stage state machine persisted in ``pipeline_state``.

Stages mirror the live pipeline UI (docs/02-architecture.md): ``uploaded`` and
``scanned`` happen during ingestion; ``parsing`` runs per-file Celery workers in
parallel; ``aggregating`` merges results deterministically into the graph facts;
``graph`` is marked done once facts are complete (the NetworkX graph is derived
on demand by ``GET .../graph``).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models.analysis import Analysis
from app.db.models.repository import Repository
from app.services.analysis import ANALYZED_LANGUAGES

PIPELINE_STAGES = ("uploaded", "scanned", "parsing", "aggregating", "graph", "index")

STAGE_PENDING = "pending"
STAGE_RUNNING = "running"
STAGE_DONE = "done"
STAGE_ERROR = "error"


def initial_pipeline_state() -> dict[str, dict[str, object]]:
    return {stage: {"state": STAGE_PENDING} for stage in PIPELINE_STAGES}


def set_stage(
    db: Session,
    analysis: Analysis,
    stage: str,
    state: str,
    **extra: object,
) -> None:
    """Persist one stage transition (eagerly committed for live status polling)."""
    current = dict(analysis.pipeline_state or initial_pipeline_state())
    current[stage] = {"state": state, **extra}
    analysis.pipeline_state = current
    db.commit()


def mark_failed(db: Session, analysis: Analysis, repository: Repository, stage: str) -> None:
    current = dict(analysis.pipeline_state or initial_pipeline_state())
    for candidate in PIPELINE_STAGES:
        if candidate == stage:
            current[candidate] = {"state": STAGE_ERROR}
            break
    analysis.pipeline_state = current
    analysis.status = "failed"
    repository.status = "failed"
    db.commit()


def latest_analysis(db: Session, repository_id: uuid.UUID) -> Analysis | None:
    return (
        db.query(Analysis)
        .filter(Analysis.repository_id == repository_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .first()
    )


def current_stage(pipeline_state: dict | None) -> str | None:
    """First stage that is not done, or ``completed`` when everything finished."""
    if not pipeline_state:
        return None
    for stage in PIPELINE_STAGES:
        entry = pipeline_state.get(stage) or {}
        if entry.get("state") != STAGE_DONE:
            return stage
    return "completed"


def files_for_analysis(repository: Repository) -> list[tuple[str, str]]:
    """(path, language) pairs for the parallel parse group, sorted for determinism."""
    files = [
        (file_row.path, file_row.language)
        for file_row in repository.files
        if file_row.language in ANALYZED_LANGUAGES
    ]
    return sorted(files, key=lambda item: (ANALYZED_LANGUAGES.index(item[1]), item[0]))


def analysis_files_total(repository: Repository) -> int:
    return sum(1 for f in repository.files if f.language in ANALYZED_LANGUAGES)