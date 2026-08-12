"""Chunk text builders (module / class / function) for the semantic index (T-08).

Chunks are built from persisted static-analysis facts (signature, docstring,
arguments, calls, globals, inheritance) — never from raw source dumps — so the
index exposes the same ground truth the LLM retrieval layer will consume.
"""

from __future__ import annotations

from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.import_ import Import
from app.db.models.inheritance import Inheritance

_TYPE_LEVELS = {
    "class": "class",
    "interface": "class",
    "enum": "class",
    "record": "class",
    "annotation": "class",
}


def level_for(entity: Entity) -> str:
    return _TYPE_LEVELS.get(entity.type, "function")


def _qualified_name(entity: Entity) -> str:
    if entity.metadata_json:
        qualified = entity.metadata_json.get("qualified_name")
        if isinstance(qualified, str) and qualified:
            return qualified
    return entity.name


def _call_names(entity: Entity, calls_by_caller: dict[str, list[Call]]) -> list[str]:
    names = []
    for call in calls_by_caller.get(str(entity.id), []):
        names.append(call.callee_name or "")
    return names


def _inheritance_names(
    entity: Entity,
    inheritances_by_entity: dict[str, list[Inheritance]],
) -> list[str]:
    return [edge.parent_name for edge in inheritances_by_entity.get(str(entity.id), [])]


def entity_chunk_text(
    entity: Entity,
    calls_by_caller: dict[str, list[Call]],
    inheritances_by_entity: dict[str, list[Inheritance]],
) -> str:
    metadata = entity.metadata_json or {}
    lines = [entity.signature or entity.name, f"file: {_qualified_name(entity)}"]
    if entity.docstring:
        lines.append(entity.docstring)
    arguments = metadata.get("arguments") or []
    if arguments:
        lines.append(f"arguments: {', '.join(arguments)}")
    calls = _call_names(entity, calls_by_caller)
    if calls:
        lines.append(f"calls: {', '.join(sorted(set(calls)))}")
    inherited = _inheritance_names(entity, inheritances_by_entity)
    if inherited:
        lines.append(f"inherits: {', '.join(sorted(set(inherited)))}")
    globals_used = metadata.get("globals") or []
    if globals_used:
        lines.append(f"globals: {', '.join(sorted(globals_used))}")
    return "\n".join(lines)


def module_chunk_text(file_row: File, imports: list[Import], entities: list[Entity]) -> str:
    lines = [file_row.path, f"language: {file_row.language}"]
    modules = sorted({imp.module for imp in imports})
    if modules:
        lines.append(f"imports: {', '.join(modules)}")
    entity_names = sorted(_qualified_name(e) for e in entities if not e.parent_id)
    if entity_names:
        lines.append(f"entities: {', '.join(entity_names)}")
    return "\n".join(lines)