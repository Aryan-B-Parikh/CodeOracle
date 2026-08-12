"""Shared static-analysis result types (used by all language parsers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EntityKind = Literal[
    "function", "method", "class", "interface", "enum", "record", "annotation"
]

INHERITANCE_KINDS = ("extends", "implements")


@dataclass(frozen=True)
class ImportRef:
    module: str
    local_name: str | None
    line: int
    kind: str = "normal"


@dataclass(frozen=True)
class CallRef:
    name: str
    line: int
    resolved: bool = False
    dynamic: bool = False


@dataclass(frozen=True)
class InheritanceRef:
    name: str
    kind: str
    line: int


@dataclass(frozen=True)
class ParsedEntity:
    name: str
    kind: EntityKind
    parent: str | None
    qualified_name: str
    signature: str
    line_start: int
    line_end: int
    is_public: bool
    docstring: str | None
    complexity: int
    arguments: list[str]
    return_type: str | None
    decorators: list[str]
    globals_used: list[str]
    calls: list[CallRef] = field(default_factory=list)
    imports: list[ImportRef] = field(default_factory=list)
    inheritances: list[InheritanceRef] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedFile:
    path: str
    entities: list[ParsedEntity]
    imports: list[ImportRef]
    module_calls: list[CallRef]


def _import_ref_to_dict(ref: ImportRef) -> dict[str, object]:
    return {"module": ref.module, "local_name": ref.local_name, "line": ref.line, "kind": ref.kind}


def _call_ref_to_dict(ref: CallRef) -> dict[str, object]:
    return {"name": ref.name, "line": ref.line, "resolved": ref.resolved, "dynamic": ref.dynamic}


def _inheritance_ref_to_dict(ref: InheritanceRef) -> dict[str, object]:
    return {"name": ref.name, "kind": ref.kind, "line": ref.line}


def _import_ref_from_dict(item: dict[str, Any]) -> ImportRef:
    return ImportRef(
        module=str(item["module"]),
        local_name=None if item.get("local_name") is None else str(item["local_name"]),
        line=int(item["line"]),
        kind=str(item.get("kind", "normal")),
    )


def _call_ref_from_dict(item: dict[str, Any]) -> CallRef:
    return CallRef(
        name=str(item["name"]),
        line=int(item["line"]),
        resolved=bool(item["resolved"]),
        dynamic=bool(item["dynamic"]),
    )


def _inheritance_ref_from_dict(item: dict[str, Any]) -> InheritanceRef:
    return InheritanceRef(name=str(item["name"]), kind=str(item["kind"]), line=int(item["line"]))


def parsed_file_to_dict(parsed: ParsedFile) -> dict[str, object]:
    """JSON-serializable representation for the Celery transport."""

    def entity_to_dict(entity: ParsedEntity) -> dict[str, object]:
        return {
            "name": entity.name,
            "kind": entity.kind,
            "parent": entity.parent,
            "qualified_name": entity.qualified_name,
            "signature": entity.signature,
            "line_start": entity.line_start,
            "line_end": entity.line_end,
            "is_public": entity.is_public,
            "docstring": entity.docstring,
            "complexity": entity.complexity,
            "arguments": entity.arguments,
            "return_type": entity.return_type,
            "decorators": entity.decorators,
            "globals_used": entity.globals_used,
            "calls": [_call_ref_to_dict(ref) for ref in entity.calls],
            "imports": [_import_ref_to_dict(ref) for ref in entity.imports],
            "inheritances": [_inheritance_ref_to_dict(ref) for ref in entity.inheritances],
            "metadata": entity.metadata,
        }

    return {
        "path": parsed.path,
        "entities": [entity_to_dict(entity) for entity in parsed.entities],
        "imports": [_import_ref_to_dict(ref) for ref in parsed.imports],
        "module_calls": [_call_ref_to_dict(ref) for ref in parsed.module_calls],
    }


def parsed_file_from_dict(data: dict[str, Any]) -> ParsedFile:
    """Reverse of :func:`parsed_file_to_dict`."""

    def entity_from_dict(item: dict[str, Any]) -> ParsedEntity:
        parent = item.get("parent")
        return_type = item.get("return_type")
        docstring = item.get("docstring")
        return ParsedEntity(
            name=str(item["name"]),
            kind=str(item["kind"]),  # type: ignore[arg-type]
            parent=None if parent is None else str(parent),
            qualified_name=str(item["qualified_name"]),
            signature=str(item["signature"]),
            line_start=int(item["line_start"]),
            line_end=int(item["line_end"]),
            is_public=bool(item["is_public"]),
            docstring=None if docstring is None else str(docstring),
            complexity=int(item["complexity"]),
            arguments=[str(a) for a in item["arguments"]],
            return_type=None if return_type is None else str(return_type),
            decorators=[str(d) for d in item["decorators"]],
            globals_used=[str(g) for g in item["globals_used"]],
            calls=[_call_ref_from_dict(c) for c in item["calls"]],
            imports=[_import_ref_from_dict(i) for i in item["imports"]],
            inheritances=[_inheritance_ref_from_dict(h) for h in item["inheritances"]],
            metadata=dict(item["metadata"]),
        )

    return ParsedFile(
        path=str(data["path"]),
        entities=[entity_from_dict(item) for item in data["entities"]],
        imports=[_import_ref_from_dict(item) for item in data["imports"]],
        module_calls=[_call_ref_from_dict(item) for item in data["module_calls"]],
    )
