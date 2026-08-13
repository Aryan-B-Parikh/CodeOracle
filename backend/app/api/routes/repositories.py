"""Repository ingestion API: upload a ZIP or import from GitHub."""

import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.analysis import Analysis
from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.repository import (
    ImportRequest,
    RepositoryEnvelope,
    RepositoryListEnvelope,
    RepositoryOut,
)
from app.services.ingestion import ingest_git, ingest_zip, validate_git_url

router = APIRouter()
settings = get_settings()

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
_UPLOAD_CHUNK_BYTES = 1024 * 1024

DbSession = Annotated[Session, Depends(get_db)]


class _UploadTooLarge(Exception):
    pass


def _repository_workdir(repository_id: uuid.UUID) -> Path:
    path = settings.upload_dir / str(repository_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _stream_upload(file: UploadFile, dest: Path, max_bytes: int) -> None:
    total = 0
    with dest.open("wb") as out:
        while chunk := await file.read(_UPLOAD_CHUNK_BYTES):
            total += len(chunk)
            if total > max_bytes:
                raise _UploadTooLarge
            out.write(chunk)


@router.post(
    "/repositories/upload",
    response_model=RepositoryEnvelope,
    status_code=201,
)
async def upload_repository(
    file: Annotated[UploadFile, File()],
    db: DbSession,
) -> RepositoryEnvelope:
    filename = Path(file.filename or "repository.zip").stem or "repository"
    repository = Repository(id=uuid.uuid4(), name=filename, source_type="zip")

    workdir = _repository_workdir(repository.id)
    zip_path = workdir / "source.zip"
    try:
        await _stream_upload(file, zip_path, MAX_UPLOAD_BYTES)
    except _UploadTooLarge:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=413, detail="upload exceeds 100MB limit") from None

    try:
        stored = ingest_zip(db, repository, zip_path, workdir)
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    return RepositoryEnvelope(data=RepositoryOut.model_validate(stored))


@router.post(
    "/repositories/import",
    response_model=RepositoryEnvelope,
    status_code=201,
)
def import_repository(
    body: ImportRequest,
    db: DbSession,
) -> RepositoryEnvelope:
    url = validate_git_url(body.github_url)
    name = url.rstrip("/").split("/")[-1].removesuffix(".git") or "repository"
    repository = Repository(id=uuid.uuid4(), name=name, source_type="github", github_url=url)

    workdir = _repository_workdir(repository.id)
    stored = ingest_git(db, repository, url, workdir)
    return RepositoryEnvelope(data=RepositoryOut.model_validate(stored))


@router.get("/repositories", response_model=RepositoryListEnvelope)
def list_repositories(db: DbSession) -> RepositoryListEnvelope:
    """List recent repositories (name, id, language, coverage-relevant stats)."""
    repositories = (
        db.query(Repository).order_by(Repository.created_at.desc()).limit(50).all()
    )
    return RepositoryListEnvelope(
        data=[
            RepositoryOut(
                id=repo.id,
                name=repo.name,
                source_type=repo.source_type,
                github_url=repo.github_url,
                languages=repo.languages,
                language_counts=repo.language_counts,
                loc=repo.loc,
                entity_count=repo.entity_count,
                file_count=repo.file_count,
                warnings=repo.warnings,
                status=repo.status,
                analysis=None,
                created_at=repo.created_at,
                updated_at=repo.updated_at,
            )
            for repo in repositories
        ]
    )


@router.get("/repositories/{repository_id}", response_model=RepositoryEnvelope)
def get_repository(
    repository_id: uuid.UUID,
    db: DbSession,
) -> RepositoryEnvelope:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    out = RepositoryOut.model_validate(repository)
    latest_analysis = (
        db.query(Analysis)
        .filter(Analysis.repository_id == repository_id)
        .order_by(Analysis.created_at.desc())
        .first()
    )
    if latest_analysis and latest_analysis.summary:
        out.analysis = latest_analysis.summary
    return RepositoryEnvelope(data=out)
