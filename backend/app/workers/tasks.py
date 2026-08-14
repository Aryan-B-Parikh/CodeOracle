"""Celery tasks: parallel per-file parsing with deterministic aggregation (T-07).

Pipeline: ``analysis.run`` (driver) fans out one ``analysis.parse_file`` task per
file — these run concurrently on the prefork pool and never touch the DB — then
aggregates the returned facts into the repository graph in a fixed
``(language, path)`` order. Every stage transition is persisted to
``analyses.pipeline_state``.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from celery import group
from sqlalchemy.orm import Session

from app.analyzers.python_parser import ParsedFile
from app.analyzers.types import parsed_file_from_dict, parsed_file_to_dict
from app.db.models.analysis import Analysis
from app.db.models.repository import Repository
from app.db.session import SessionLocal
from app.services.analysis import (
    delete_analysis_facts,
    parse_source,
    repository_root,
    store_parse_results,
)
from app.services.pipeline import (
    STAGE_DONE,
    STAGE_RUNNING,
    files_for_analysis,
    latest_analysis,
    mark_failed,
    set_stage,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Acceptance gate: a 10K-LOC fixture must analyze in under 5 minutes.
ANALYSIS_TIMEOUT_SECONDS = 300


@celery_app.task(name="analysis.parse_file")
def parse_file_task(
    repository_id: str,
    root: str,
    rel_path: str,
    language: str,
) -> dict | None:
    """Parse a single file; returns JSON-serializable facts or ``None`` on failure."""
    path = Path(root) / rel_path
    if not path.is_file():
        return None
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_source(source, rel_path, language)
    except OSError:
        logger.warning("repo=%s parse read failed path=%s", repository_id, rel_path)
        return None
    if parsed is None:
        logger.warning("repo=%s unparseable file path=%s", repository_id, rel_path)
        return None
    return parsed_file_to_dict(parsed)


@celery_app.task(name="analysis.run")
def run_analysis_task(repository_id_raw: str) -> None:
    """Pipeline driver: stage transitions, parallel parse fan-out, aggregation."""
    repository_id = uuid.UUID(repository_id_raw)
    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        analysis = latest_analysis(db, repository_id)
        if repository is None or analysis is None:
            logger.error(
                "repo=%s analysis.abort missing repository or analysis row", repository_id
            )
            return
        if analysis.status == "running":
            logger.warning("repo=%s analysis.duplicate run ignored", repository_id)
            return

        analysis.status = "running"
        repository.status = "parsing"
        db.commit()
        set_stage(db, analysis, "uploaded", STAGE_DONE)
        set_stage(db, analysis, "scanned", STAGE_DONE)

        files = files_for_analysis(repository)
        total = len(files)
        set_stage(
            db,
            analysis,
            "parsing",
            STAGE_RUNNING,
            filesTotal=total,
            filesParsed=0,
        )

        root = str(repository_root(repository))
        try:
            serialized = [
                parse_file_task(repository_id_raw, root, path, language)
                for path, language in files
            ]
        except Exception as exc:  # noqa: BLE001
            logger.error("repo=%s parse stage failed: %s", repository_id, exc)
            _fail(repository_id, analysis.id, "parsing")
            return

        if len(serialized) != len(files):
            logger.error(
                "repo=%s parse results mismatch files=%d results=%d",
                repository_id,
                len(files),
                len(serialized),
            )
            _fail(repository_id, analysis.id, "parsing")
            return

        results: list[tuple[str, ParsedFile]] = []
        parsed_count = 0
        for (path, language), item in zip(files, serialized, strict=True):
            if not isinstance(item, dict):
                logger.warning("repo=%s skipped failed parse path=%s", repository_id, path)
                continue
            results.append((language, parsed_file_from_dict(item)))
            parsed_count += 1

        set_stage(
            db,
            analysis,
            "parsing",
            STAGE_DONE,
            filesTotal=total,
            filesParsed=parsed_count,
        )
        try:
            _aggregate(db, repository, analysis, results)
        except Exception as exc:  # noqa: BLE001
            logger.error("repo=%s aggregation failed: %s", repository_id, exc)
            db.rollback()
            _fail(repository_id, analysis.id, "aggregating")
            return
        logger.info(
            "repo=%s analysis completed files=%d entities=%s",
            repository_id,
            parsed_count,
            repository.entity_count,
        )


def _aggregate(
    db: Session,
    repository: Repository,
    analysis: Analysis,
    results: list[tuple[str, ParsedFile]],
) -> None:
    set_stage(db, analysis, "aggregating", STAGE_RUNNING)
    delete_analysis_facts(db, repository.id)
    db.commit()
    db.expire_all()
    stats = store_parse_results(db, repository, results)
    set_stage(db, analysis, "aggregating", STAGE_DONE)
    set_stage(db, analysis, "graph", STAGE_DONE)
    # Keep the analysis in `running` until semantic indexing completes. The UI
    # uses analysisStatus/currentStage to decide when it is safe to stop polling.
    repository.status = "analyzing"
    analysis.status = "running"
    db.commit()
    _index(db, repository, analysis)
    db.refresh(repository)
    logger.info(
        "repo=%s aggregate entities=%d files=%d",
        repository.id,
        stats["entities"],
        stats["files_analyzed"],
    )


def _index(db: Session, repository: Repository, analysis: Analysis) -> None:
    """Build the semantic index after graph facts exist (T-08)."""
    from app.index.service import create_index

    set_stage(db, analysis, "index", STAGE_RUNNING)
    try:
        chunks = create_index(db, repository)
    except Exception as exc:  # noqa: BLE001
        logger.error("repo=%s index stage failed: %s", repository.id, exc)
        _fail(repository.id, analysis.id, "index")
        return
    set_stage(db, analysis, "index", STAGE_DONE, chunks=chunks)
    repository.status = "analyzed"
    analysis.status = "completed"
    db.commit()


def _fail(repository_id: uuid.UUID, analysis_id: uuid.UUID, stage: str) -> None:
    with SessionLocal() as db:
        repository = db.get(Repository, repository_id)
        analysis = db.get(Analysis, analysis_id)
        if repository is None or analysis is None:
            return
        mark_failed(db, analysis, repository, stage)
