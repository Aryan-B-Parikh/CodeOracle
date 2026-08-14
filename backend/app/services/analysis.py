"""Repository analysis: run parsers over scanned files and persist graph facts.

Two entry points share the same pure parse step and deterministic aggregation:

- ``parse_source`` — parse a single file's source (used directly by Celery worker
  tasks so files are parsed in parallel, T-07).
- ``store_parse_results`` — aggregate per-file results into the repository graph
  facts in a deterministic order (sorted by path), so parallel workers can never
  produce a different graph than sequential parsing.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.analyzers.java_parser import parse_java
from app.analyzers.python_parser import ParsedFile, parse_python
from app.analyzers.types import ImportRef
from app.config import get_settings
from app.db.models.call import Call
from app.db.models.chunk import Chunk
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.import_ import Import
from app.db.models.inheritance import Inheritance
from app.db.models.repository import Repository
from app.services.ingestion import collapse_single_top_dir

settings = get_settings()

ANALYZED_LANGUAGES = ("python", "java")


def repository_root(repository: Repository) -> Path:
    workdir = settings.upload_dir / str(repository.id)
    if repository.source_type == "zip":
        return collapse_single_top_dir(workdir / "extracted")
    return workdir / "repo"


def parse_source(source: str, path: str, language: str) -> ParsedFile | None:
    """Parse a single file, returning ``None`` when the source is unparseable."""
    try:
        parser = parse_python if language == "python" else parse_java
        return parser(source, path)
    except SyntaxError:
        return None


def _local_names(files: list[File], language: str) -> set[str]:
    return {Path(f.path).stem for f in files if f.language == language}


def _is_external_import(ref: ImportRef, language: str, local_names: set[str]) -> bool:
    if language == "java":
        return ref.module.split(".")[-1] not in local_names
    return ref.module not in local_names and not ref.module.startswith(".")


def _store_imports(
    db: Session,
    file_row: File,
    parsed: ParsedFile,
    language: str,
    local_names: set[str],
) -> None:
    refs = list(parsed.imports)
    for entity in parsed.entities:
        refs.extend(entity.imports)
    for ref in refs:
        is_external = _is_external_import(ref, language, local_names)
        db.add(
            Import(
                file_id=file_row.id,
                module=ref.module,
                local_name=ref.local_name,
                is_external=is_external,
                kind=ref.kind,
                line=ref.line,
            )
        )


def _store_calls(
    db: Session,
    repository: Repository,
    caller_id: uuid.UUID | None,
    calls: list,
    name_to_id: dict[str, uuid.UUID],
) -> None:
    for ref in calls:
        callee_id: uuid.UUID | None = None
        if ref.resolved:
            callee_id = name_to_id.get(ref.name) or name_to_id.get(
                ref.name.rsplit(".", 1)[-1]
            )
        db.add(
            Call(
                repository_id=repository.id,
                caller_id=caller_id,
                callee_id=callee_id,
                callee_name=ref.name,
                call_line=ref.line,
                external=callee_id is None,
                dynamic=ref.dynamic,
            )
        )


def _store_file(
    db: Session,
    repository: Repository,
    file_row: File,
    parsed: ParsedFile,
    language: str,
    local_names: set[str],
) -> None:
    _store_imports(db, file_row, parsed, language, local_names)

    entity_ids: dict[str, uuid.UUID] = {}
    for entity in parsed.entities:
        row = Entity(
            repository_id=repository.id,
            file_id=file_row.id,
            name=entity.name,
            type=entity.kind,
            parent_id=None,
            signature=entity.signature,
            language=language,
            line_start=entity.line_start,
            line_end=entity.line_end,
            complexity=entity.complexity,
            is_public=entity.is_public,
            docstring=entity.docstring,
            metadata_json={
                "qualified_name": entity.qualified_name,
                "arguments": entity.arguments,
                "return_type": entity.return_type,
                "decorators": entity.decorators,
                "globals": entity.globals_used,
                **entity.metadata,
            },
        )
        db.add(row)
        db.flush()
        entity_ids[entity.qualified_name] = row.id

    for entity in parsed.entities:
        if entity.parent is not None:
            parent_id = entity_ids.get(entity.parent)
            if parent_id is not None:
                parent_row = db.get(Entity, entity_ids[entity.qualified_name])
                if parent_row is not None:
                    parent_row.parent_id = parent_id

    name_to_id: dict[str, uuid.UUID] = {}
    for qualified, entity_id in entity_ids.items():
        name_to_id.setdefault(qualified.rsplit(".", 1)[-1], entity_id)

    for entity in parsed.entities:
        for ref in entity.inheritances:
            db.add(
                Inheritance(
                    repository_id=repository.id,
                    file_id=file_row.id,
                    entity_id=entity_ids[entity.qualified_name],
                    parent_id=name_to_id.get(ref.name),
                    parent_name=ref.name,
                    kind=ref.kind,
                    line=ref.line,
                )
            )

    for entity in parsed.entities:
        caller_id = entity_ids[entity.qualified_name]
        _store_calls(db, repository, caller_id, entity.calls, name_to_id)
    _store_calls(db, repository, None, parsed.module_calls, name_to_id)


def delete_analysis_facts(db: Session, repository_id: uuid.UUID) -> None:
    """Remove all persisted analysis facts before a fresh repository analysis.

    Chunks normally carry the repository id, but older/partially written rows can
    still reference an entity from the repository while having an inconsistent
    repository id. Delete by both ownership paths before deleting entities so a
    rerun cannot violate ``chunks.entity_id -> entities.id``.
    """
    repository_entities = select(Entity.id).where(Entity.repository_id == repository_id)
    db.query(Chunk).filter(
        or_(
            Chunk.repository_id == repository_id,
            Chunk.entity_id.in_(repository_entities),
        )
    ).delete(synchronize_session=False)

    for model in (Inheritance, Call, Entity):
        db.query(model).filter(model.repository_id == repository_id).delete(
            synchronize_session=False
        )
    file_ids = select(File.id).where(File.repository_id == repository_id)
    db.query(Import).filter(Import.file_id.in_(file_ids)).delete(synchronize_session=False)


def store_parse_results(
    db: Session,
    repository: Repository,
    results: list[tuple[str, ParsedFile]],
) -> dict[str, object]:
    """Aggregate parsed files into graph facts.

    Deterministic: ``(language, path)`` ordering is imposed regardless of the order
    in which parallel workers finished, so the persisted graph never varies.
    """
    ordered = sorted(
        results,
        key=lambda item: (ANALYZED_LANGUAGES.index(item[0]), item[1].path),
    )

    entity_count = 0
    analyzed_files = 0
    counts: dict[str, int] = {lang: 0 for lang in ANALYZED_LANGUAGES}

    files_by_path = {f.path: f for f in repository.files}
    by_language: dict[str, list[ParsedFile]] = {lang: [] for lang in ANALYZED_LANGUAGES}
    for language, parsed in ordered:
        by_language[language].append(parsed)
        counts[language] += 1

    for language in ANALYZED_LANGUAGES:
        parsed_list = by_language[language]
        if not parsed_list:
            continue
        local_names = _local_names(repository.files, language)
        for parsed in parsed_list:
            file_row = files_by_path.get(parsed.path)
            if file_row is None:
                continue
            _store_file(db, repository, file_row, parsed, language, local_names)
            entity_count += len(parsed.entities)
            analyzed_files += 1

    repository.entity_count = entity_count
    db.commit()
    return {"entities": entity_count, "files_analyzed": analyzed_files, "languages": counts}


def analyze_repository(db: Session, repository: Repository) -> dict[str, object]:
    """Sequential analysis (single process) using the same primitives as the pipeline."""
    delete_analysis_facts(db, repository.id)
    db.commit()
    db.expire_all()
    root = repository_root(repository)
    results: list[tuple[str, ParsedFile]] = []
    for language in ANALYZED_LANGUAGES:
        files = [f for f in repository.files if f.language == language]
        for file_row in files:
            path = root / file_row.path
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_source(source, file_row.path, language)
            if parsed is not None:
                results.append((language, parsed))
    stats = store_parse_results(db, repository, results)
    create_index(db, repository)
    return stats


def create_index(db: Session, repository: Repository) -> int:
    """Build the semantic index (T-08); returns chunk count."""
    from app.index.service import create_index as _create_index

    return _create_index(db, repository)
