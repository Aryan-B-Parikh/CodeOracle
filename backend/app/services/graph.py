"""Dependency graph builder (NetworkX) -> React Flow payload (T-06).

Builds Repository -> module -> class -> function -> call graph from persisted
static-analysis facts, re-resolving file-local calls at repository scope
(cross-module calls like ``tax.calculate_tax`` and import aliases such as
``from billing import describe_invoice``), adds INHERITS/IMPLEMENTS and local
IMPORTS edges, detects circular dependencies, and scores high-risk nodes
(complexity x callers).
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
from sqlalchemy.orm import Session

from app.db.models.call import Call
from app.db.models.entity import Entity
from app.db.models.file import File
from app.db.models.import_ import Import
from app.db.models.inheritance import Inheritance
from app.db.models.repository import Repository

HIGH_RISK_TOP_N = 10

_ENTITY_KINDS = {"function", "method", "class", "interface", "enum", "record", "annotation"}


def _entity_node_id(file_path: str, qualified_name: str) -> str:
    return f"{file_path}::{qualified_name}"


def _qualified_name(entity: Entity) -> str:
    if entity.metadata_json:
        qualified = entity.metadata_json.get("qualified_name")
        if isinstance(qualified, str) and qualified:
            return qualified
    return entity.name


@dataclass
class _GraphData:
    files_by_id: dict[uuid.UUID, File] = field(default_factory=dict)
    file_by_stem: dict[str, list[File]] = field(default_factory=dict)
    entities_by_name: dict[str, list[Entity]] = field(default_factory=dict)
    entities_by_id: dict[uuid.UUID, Entity] = field(default_factory=dict)
    names_in_file: dict[str, set[str]] = field(default_factory=dict)
    imports_by_file: dict[str, list[Import]] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)
    inheritances: list[Inheritance] = field(default_factory=list)


def _load(repository: Repository) -> _GraphData:
    data = _GraphData()
    for file_row in repository.files:
        data.files_by_id[file_row.id] = file_row
        data.file_by_stem.setdefault(Path(file_row.path).stem, []).append(file_row)
        data.names_in_file[file_row.path] = {e.name for e in file_row.entities}
        data.imports_by_file[file_row.path] = list(file_row.imports)
    for entity in repository.entities:
        data.entities_by_name.setdefault(entity.name, []).append(entity)
        data.entities_by_id[entity.id] = entity
    data.calls = list(repository.calls)
    data.inheritances = list(repository.inheritances)
    return data


def _find_in_file(data: _GraphData, file_path: str, name: str) -> Entity | None:
    for entity in data.entities_by_name.get(name, []):
        if data.files_by_id[entity.file_id].path == file_path:
            return entity
    return None


def _import_target(data: _GraphData, file_path: str, module_head: str) -> File | None:
    """Map an import module (or its last component) to a local file."""
    stems = data.file_by_stem.get(module_head)
    if stems:
        return stems[0]
    for imported in data.imports_by_file.get(file_path, []):
        last = imported.module.rsplit(".", 1)[-1]
        if last == module_head:
            stems = data.file_by_stem.get(last)
            if stems:
                return stems[0]
    return None


def _resolve_by_name(data: _GraphData, name: str) -> Entity | None:
    matches = data.entities_by_name.get(name.rsplit(".", 1)[-1], [])
    if len(matches) == 1:
        return matches[0]
    return None


def _resolve(data: _GraphData, callee_name: str, caller_file: str | None) -> Entity | None:
    if not callee_name or not caller_file:
        return None
    last = callee_name.rsplit(".", 1)[-1]

    if last in data.names_in_file.get(caller_file, set()):
        found = _find_in_file(data, caller_file, last)
        if found is not None:
            return found

    if "." in callee_name:
        head = callee_name.split(".", 1)[0]
        target = _import_target(data, caller_file, head)
        if target is not None:
            found = _find_in_file(data, target.path, last)
            if found is not None:
                return found

    for imported in data.imports_by_file.get(caller_file, []):
        if imported.local_name in (callee_name, last):
            target = _import_target(data, caller_file, imported.module.rsplit(".", 1)[-1])
            if target is not None:
                found = _find_in_file(data, target.path, last)
                if found is not None:
                    return found

    matches = data.entities_by_name.get(last, [])
    if len(matches) == 1:
        return matches[0]
    return None


def build_graph(db: Session, repository: Repository) -> dict[str, object]:
    data = _load(repository)

    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    entity_node_ids: dict[uuid.UUID, str] = {}
    node_index: dict[str, dict[str, object]] = {}

    for file_row in data.files_by_id.values():
        module_node: dict[str, object] = {
            "id": file_row.path,
            "label": file_row.path,
            "type": "module",
        }
        nodes.append(module_node)
        node_index[file_row.path] = module_node

    for entity in repository.entities:
        file_path = data.files_by_id[entity.file_id].path
        node_id = _entity_node_id(file_path, _qualified_name(entity))
        entity_node_ids[entity.id] = node_id
        entity_node: dict[str, object] = {
            "id": node_id,
            "label": entity.name,
            "type": entity.type,
            "complexity": entity.complexity,
            "file": file_path,
            "line_start": entity.line_start,
            "line_end": entity.line_end,
            "qualified_name": _qualified_name(entity),
        }
        nodes.append(entity_node)
        node_index[node_id] = entity_node

    for entity in repository.entities:
        file_path = data.files_by_id[entity.file_id].path
        node_id = entity_node_ids[entity.id]
        if entity.parent_id is not None and entity.parent_id in entity_node_ids:
            edges.append(
                {
                    "source": entity_node_ids[entity.parent_id],
                    "target": node_id,
                    "kind": "contains",
                }
            )
        else:
            edges.append({"source": file_path, "target": node_id, "kind": "contains"})

    call_edges: list[tuple[str, str]] = []
    caller_count: Counter[str] = Counter()
    callee_count: Counter[str] = Counter()
    for call in data.calls:
        if call.dynamic:
            continue
        caller_entity = data.entities_by_id.get(call.caller_id) if call.caller_id else None
        caller_file = (
            data.files_by_id[caller_entity.file_id].path if caller_entity else None
        )
        callee = data.entities_by_id.get(call.callee_id) if call.callee_id else None
        if callee is None:
            callee = _resolve(data, call.callee_name, caller_file)
        if callee is None:
            continue
        target_id = entity_node_ids[callee.id]
        if caller_entity is None:
            if caller_file is not None:
                edges.append(
                    {"source": caller_file, "target": target_id, "kind": "call"}
                )
                call_edges.append((caller_file, target_id))
                caller_count[target_id] += 1
            continue
        source_id = entity_node_ids[caller_entity.id]
        if source_id == target_id:
            continue
        edges.append({"source": source_id, "target": target_id, "kind": "call"})
        call_edges.append((source_id, target_id))
        caller_count[target_id] += 1
        callee_count[source_id] += 1

    for file_row in data.files_by_id.values():
        for imported in data.imports_by_file.get(file_row.path, []):
            target = _import_target(
                data, file_row.path, imported.module.rsplit(".", 1)[-1]
            )
            if target is not None and target.path != file_row.path:
                edges.append(
                    {
                        "source": file_row.path,
                        "target": target.path,
                        "kind": "imports",
                    }
                )

    for inheritance in data.inheritances:
        inh_source = (
            entity_node_ids.get(inheritance.entity_id) if inheritance.entity_id else None
        )
        inh_target = (
            entity_node_ids.get(inheritance.parent_id)
            if inheritance.parent_id
            else None
        )
        if inh_target is None:
            resolved = _resolve_by_name(data, inheritance.parent_name)
            inh_target = entity_node_ids.get(resolved.id) if resolved else None
        if inh_source is not None and inh_target is not None:
            edges.append(
                {
                    "source": inh_source,
                    "target": inh_target,
                    "kind": "inherits" if inheritance.kind == "extends" else "implements",
                }
            )

    risk_scores = _risk_scores(repository.entities, entity_node_ids, caller_count, callee_count)
    for entity in repository.entities:
        node_id = entity_node_ids[entity.id]
        if node_id in risk_scores:
            node_index[node_id]["risk_score"] = risk_scores[node_id]

    circular = _module_cycles(_module_dependency_graph(edges))

    high_risk = sorted(
        risk_scores,
        key=lambda node_id: (-risk_scores[node_id], node_id),
    )[:HIGH_RISK_TOP_N]

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "circular_dependencies": [{"cycle": cycle} for cycle in circular],
            "high_risk_node_ids": high_risk,
        },
    }


def _risk_scores(
    entities: list[Entity],
    entity_node_ids: dict[uuid.UUID, str],
    caller_count: Counter[str],
    callee_count: Counter[str],
) -> dict[str, int]:
    """Risk = complexity x (callers + callees + 1) for entities with any edge."""
    scores: dict[str, int] = {}
    for entity in entities:
        node_id = entity_node_ids[entity.id]
        in_degree = caller_count.get(node_id, 0)
        out_degree = callee_count.get(node_id, 0)
        if in_degree + out_degree > 0:
            scores[node_id] = entity.complexity * (in_degree + out_degree + 1)
    return scores


def _module_dependency_graph(edges: list[dict[str, object]]) -> nx.DiGraph:
    """MODULE-level dependency graph from call + local-import edges."""
    graph = nx.DiGraph()
    for edge in edges:
        if edge["kind"] not in ("call", "imports"):
            continue
        source = str(edge["source"]).split("::", 1)[0]
        target = str(edge["target"]).split("::", 1)[0]
        if source != target:
            graph.add_edge(source, target)
    return graph


def _module_cycles(graph: nx.DiGraph) -> list[list[str]]:
    cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for cycle in nx.simple_cycles(graph):
        key = tuple(sorted(cycle))
        if key in seen:
            continue
        seen.add(key)
        cycles.append(list(cycle))
    return cycles
