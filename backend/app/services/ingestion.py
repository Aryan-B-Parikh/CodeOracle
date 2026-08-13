"""Repository ingestion: zip extraction, git clone, and initial scan persistence."""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.analyzers.scanner import SUPPORTED_LANGUAGES, ScanResult, scan_directory
from app.db.models.file import File as FileRecord
from app.db.models.repository import Repository

MAX_EXTRACT_BYTES = 200 * 1024 * 1024
MAX_EXTRACT_FILES = 20_000
GIT_CLONE_TIMEOUT = 300

ALLOWED_GIT_SCHEMES = {"http", "https", "ssh", "file"}


def validate_git_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme in ALLOWED_GIT_SCHEMES:
        return url.strip()
    if parsed.scheme == "" and url.strip().startswith("git@"):
        return url.strip()
    raise HTTPException(status_code=422, detail=f"unsupported git url: {url}")


def extract_zip(zip_path: Path, dest: Path) -> None:
    dest_root = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path) as archive:
            total_bytes = 0
            for member in archive.infolist():
                total_bytes += member.file_size
                if total_bytes > MAX_EXTRACT_BYTES:
                    raise HTTPException(status_code=413, detail="archive too large")
                target = (dest_root / member.filename).resolve()
                if not target.is_relative_to(dest_root):
                    raise HTTPException(
                        status_code=422, detail="archive path escapes extraction dir"
                    )
            if len(archive.infolist()) > MAX_EXTRACT_FILES:
                raise HTTPException(status_code=413, detail="too many files in archive")
            archive.extractall(dest)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="invalid zip archive") from exc


def collapse_single_top_dir(root: Path) -> Path:
    entries = [p for p in root.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


def clone_repository(url: str, dest: Path, timeout: int = GIT_CLONE_TIMEOUT) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="git clone timed out") from exc
    if result.returncode != 0:
        raise HTTPException(status_code=422, detail=f"git clone failed: {result.stderr.strip()}")


def _language_flags(result: ScanResult) -> dict[str, bool]:
    present = {f.language for f in result.files}
    flags = {language: language in present for language in SUPPORTED_LANGUAGES}
    flags["other"] = result.unsupported_count > 0
    return flags


def scan_and_store(db: Session, repository: Repository, root: Path) -> Repository:
    result = scan_directory(root)
    repository.languages = _language_flags(result)
    repository.language_counts = result.language_counts
    repository.loc = sum(f.loc for f in result.files)
    repository.file_count = len(result.files)
    repository.warnings = result.warnings
    db.add(repository)
    db.flush()
    for detected in result.files:
        db.add(
            FileRecord(
                repository_id=repository.id,
                path=detected.path,
                language=detected.language,
                loc=detected.loc,
                sha256=detected.sha256,
            )
        )
    db.commit()
    db.refresh(repository)
    return repository


def ingest_zip(db: Session, repository: Repository, zip_path: Path, workdir: Path) -> Repository:
    extracted = workdir / "extracted"
    shutil.rmtree(extracted, ignore_errors=True)
    extract_zip(zip_path, extracted)
    root = collapse_single_top_dir(extracted)
    return scan_and_store(db, repository, root)


def ingest_git(db: Session, repository: Repository, url: str, workdir: Path) -> Repository:
    dest = workdir / "repo"
    shutil.rmtree(dest, ignore_errors=True)
    clone_repository(url, dest)
    return scan_and_store(db, repository, dest)
