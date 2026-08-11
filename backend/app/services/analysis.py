"""Repository analysis: run parsers over scanned files and persist graph facts."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.analyzers.python_parser import ParsedFile, parse_python
from app.config import get_settings
from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.import_ import Import
from app.db.models.repository import Repository
from app.services.ingestion import collapse_single_top_dir

settings = get_settings()


def repository_root(repository: Repository) -> Path:
    workdir = settings.upload_dir / str(repository.id)
    if repository.source_type == "zip":
        return collapse_single_top_dir(workdir / "extracted")
    return workdir / "repo"


def _local_modules(files: list[File]) -> set[str]:
    return {Path(f.path).stem for f in files}


def _store_imports(
    db: Session, file_row: File, parsed: ParsedFile, local_modules: set[str]
) -> None:
    refs = list(parsed.imports)
    for entity in parsed.entities:
        refs.extend(entity.imports)
    for ref in refs:
        is_external = ref.module not in local_modules and not ref.module.startswith(".")
        db.add(
            Import(
                file_id=file_row.id,
                module=ref.module,
                local_name=ref.local_name,
                is_external=is_external,
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
            )
        )


def _store_file(
    db: Session,
    repository: Repository,
    file_row: File,
    parsed: ParsedFile,
    local_modules: set[str],
) -> None:
    _store_imports(db, file_row, parsed, local_modules)

    entity_ids: dict[tuple[str, str | None, str], uuid.UUID] = {}
    for entity in parsed.entities:
        row = Entity(
            repository_id=repository.id,
            file_id=file_row.id,
            name=entity.name,
            type=entity.kind,
            parent_id=None,
            signature=entity.signature,
            language="python",
            line_start=entity.line_start,
            line_end=entity.line_end,
            complexity=entity.complexity,
            is_public=entity.is_public,
            docstring=entity.docstring,
            metadata_json={
                "arguments": entity.arguments,
                "return_type": entity.return_type,
                "decorators": entity.decorators,
                "globals": entity.globals_used,
            },
        )
        db.add(row)
        db.flush()
        entity_ids[(entity.kind, entity.parent, entity.name)] = row.id

    for entity in parsed.entities:
        key = (entity.kind, entity.parent, entity.name)
        if entity.parent is not None:
            parent_id = entity_ids.get(("class", None, entity.parent))
            if parent_id is not None:
                parent_row = db.get(Entity, entity_ids[key])
                if parent_row is not None:
                    parent_row.parent_id = parent_id

    name_to_id: dict[str, uuid.UUID] = {}
    for (_, _, name), entity_id in entity_ids.items():
        name_to_id.setdefault(name, entity_id)

    for entity in parsed.entities:
        caller_id = entity_ids[(entity.kind, entity.parent, entity.name)]
        _store_calls(db, repository, caller_id, entity.calls, name_to_id)
    _store_calls(db, repository, None, parsed.module_calls, name_to_id)


def analyze_repository(db: Session, repository: Repository) -> dict[str, int]:
    root = repository_root(repository)
    files = [f for f in repository.files if f.language == "python"]
    local_modules = _local_modules(files)

    entity_count = 0
    analyzed_files = 0
    for file_row in files:
        path = root / file_row.path
        if not path.is_file():
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            parsed = parse_python(source, file_row.path)
        except SyntaxError:
            continue
        _store_file(db, repository, file_row, parsed, local_modules)
        entity_count += len(parsed.entities)
        analyzed_files += 1

    repository.entity_count = entity_count
    db.commit()
    return {"entities": entity_count, "files_analyzed": analyzed_files}
