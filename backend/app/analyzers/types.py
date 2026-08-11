"""Shared static-analysis result types (used by all language parsers)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EntityKind = Literal["function", "method", "class"]


@dataclass(frozen=True)
class ImportRef:
    module: str
    local_name: str | None
    line: int


@dataclass(frozen=True)
class CallRef:
    name: str
    line: int
    resolved: bool = False
    dynamic: bool = False


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


@dataclass(frozen=True)
class ParsedFile:
    path: str
    entities: list[ParsedEntity]
    imports: list[ImportRef]
    module_calls: list[CallRef]
