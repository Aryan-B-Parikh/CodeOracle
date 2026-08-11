"""Repository ingestion API: upload a ZIP or import from GitHub."""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models.repository import Repository
from app.db.session import get_db
from app.schemas.repository import ImportRequest, RepositoryEnvelope, RepositoryOut
from app.services.ingestion import ingest_git, ingest_zip, validate_git_url

router = APIRouter()
settings = get_settings()

MAX_UPLOAD_BYTES = 100 * 1024 * 1024

DbSession = Annotated[Session, Depends(get_db)]


def _repository_workdir(repository_id: uuid.UUID) -> Path:
    path = settings.upload_dir / str(repository_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post(
    "/repositories/upload",
    response_model=RepositoryEnvelope,
    status_code=201,
)
async def upload_repository(
    file: Annotated[UploadFile, File()],
    db: DbSession,
) -> RepositoryEnvelope:
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload exceeds 100MB limit")

    filename = Path(file.filename or "repository.zip").stem or "repository"
    repository = Repository(id=uuid.uuid4(), name=filename, source_type="zip")

    workdir = _repository_workdir(repository.id)
    zip_path = workdir / "source.zip"
    zip_path.write_bytes(content)

    stored = ingest_zip(db, repository, zip_path, workdir)
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


@router.get("/repositories/{repository_id}", response_model=RepositoryEnvelope)
def get_repository(
    repository_id: uuid.UUID,
    db: DbSession,
) -> RepositoryEnvelope:
    repository = db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return RepositoryEnvelope(data=RepositoryOut.model_validate(repository))
