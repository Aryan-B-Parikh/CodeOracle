"""Pure Java static analysis via tree-sitter-java.

Extracts classes, methods (incl. constructors), signatures, line ranges,
method invocations (file-local resolution), imports, field usage, and a
cyclomatic complexity count. No I/O beyond the given source, no LLM.

Note: the stack lists JavaParser; the actual MVP parser is tree-sitter-java so
the backend host needs no JVM. See DECISIONS.md.
"""

from __future__ import annotations

from collections.abc import Iterator

from tree_sitter import Language, Node, Parser
from tree_sitter_java import language as java_language

from app.analyzers.types import (
    CallRef,
    EntityKind,
    ImportRef,
    InheritanceRef,
    ParsedEntity,
    ParsedFile,
)

_LANGUAGE = Language(java_language())
_PARSER = Parser(_LANGUAGE)

_DECISION_TYPES = frozenset(
    {
        "if_statement",
        "while_statement",
        "for_statement",
        "enhanced_for_statement",
        "do_statement",
        "catch_clause",
        "conditional_expression",
        "switch_expression",
        "switch_statement",
        "switch_label",
    }
)
_LOGICAL_OPERATORS = frozenset({"&&", "||"})
_COMMENT_TYPES = frozenset({"line_comment", "block_comment"})

_TYPE_TO_KIND: dict[str, EntityKind] = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "record_declaration": "record",
    "annotation_type_declaration": "annotation",
}

_MEMBER_TYPES = frozenset(
    {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "annotation_type_declaration",
        "method_declaration",
        "constructor_declaration",
        "compact_constructor_declaration",
        "annotation_type_element_declaration",
    }
)

_METHOD_MEMBER_TYPES = frozenset(
    {
        "method_declaration",
        "constructor_declaration",
        "compact_constructor_declaration",
        "annotation_type_element_declaration",
    }
)


def _text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode("utf-8")


def _field(node: Node, name: str) -> Node | None:
    return node.child_by_field_name(name)


def _iter_type(node: Node, node_type: str) -> Iterator[Node]:
    if node.type == node_type:
        yield node
    for child in node.children:
        yield from _iter_type(child, node_type)


def _member_kind(node: Node) -> EntityKind:
    return _TYPE_TO_KIND.get(node.type, "method")


def _iter_members(container: Node) -> list[tuple[Node, str | None]]:
    result: list[tuple[Node, str | None]] = []
    pending: list[str] = []
    for child in container.children:
        if child.type in _COMMENT_TYPES:
            pending.append(_text(child))
        elif child.type == "enum_body_declarations":
            result.extend(_iter_members(child))
        elif child.type in _MEMBER_TYPES:
            doc = "\n".join(pending).strip() or None
            result.append((child, doc))
            pending = []
        else:
            pending = []
    return result


def _is_public(node: Node) -> bool:
    modifiers = _field(node, "modifiers")
    if modifiers is None:
        modifiers = next(
            (c for c in node.children if c.type == "modifiers"), None
        )
    if modifiers is None:
        return True
    return "public" in _text(modifiers)


def _entity_name(node: Node) -> str:
    return _text(_field(node, "name"))


def _signature(node: Node, name: str) -> str:
    parameters = _field(node, "parameters")
    params = (
        ", ".join(_text(p) for p in parameters.children if p.type == "formal_parameter")
        if parameters is not None
        else ""
    )
    return_type = _text(_field(node, "type"))
    return f"{name}({params})" + (f" -> {return_type}" if return_type else "")


def _arguments(node: Node) -> list[str]:
    parameters = _field(node, "parameters")
    if parameters is None:
        return []
    return [
        _text(_field(p, "name"))
        for p in parameters.children
        if p.type == "formal_parameter"
    ]


def _complexity(node: Node) -> int:
    count = 0
    if node.type in _DECISION_TYPES:
        count += 1
    elif node.type == "binary_expression":
        count += sum(1 for child in node.children if child.type in _LOGICAL_OPERATORS)
    for child in node.children:
        count += _complexity(child)
    return count


def _method_complexity(node: Node) -> int:
    body = _field(node, "body") or node
    return 1 + _complexity(body)


def _class_fields(node: Node) -> set[str]:
    fields: set[str] = set()
    for declaration in _iter_type(node, "field_declaration"):
        for declarator in _iter_type(declaration, "variable_declarator"):
            name = _text(_field(declarator, "name"))
            if name:
                fields.add(name)
    return fields


def _globals_used(node: Node, fields: set[str]) -> list[str]:
    used: set[str] = set()
    for identifier in _iter_type(node, "identifier"):
        used.add(_text(identifier))
    for access in _iter_type(node, "field_access"):
        text = _text(access)
        if text.startswith("this."):
            used.add(text.split(".", 1)[1])
    return sorted(used & fields)


def _calls(node: Node, local_names: set[str]) -> list[CallRef]:
    result: list[CallRef] = []
    for invocation in _iter_type(node, "method_invocation"):
        name = _text(_field(invocation, "name"))
        obj = _text(_field(invocation, "object"))
        full = f"{obj}.{name}" if obj else name
        resolved = name in local_names or full in local_names
        result.append(
            CallRef(name=full, line=invocation.start_point.row + 1, resolved=resolved)
        )
    return result


def _imports(tree: Node) -> list[ImportRef]:
    result: list[ImportRef] = []
    for declaration in _iter_type(tree, "import_declaration"):
        module = _text(declaration).strip()
        module = module.removeprefix("import").strip()
        module = module.removeprefix("static").strip().rstrip(";").strip()
        if not module:
            continue
        kind = "static" if any(c.type == "static" for c in declaration.children) else "normal"
        result.append(
            ImportRef(
                module=module,
                local_name=None,
                kind=kind,
                line=declaration.start_point.row + 1,
            )
        )
    return result


def _parse_javadoc(text: str | None) -> dict[str, object] | None:
    if not text:
        return None
    description: list[str] = []
    tags: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        line = line.removeprefix("/**").removeprefix("/*").removeprefix("//").strip()
        line = line.removesuffix("*/").strip()
        line = line.lstrip("*").strip()
        if not line:
            continue
        if line.startswith("@"):
            parts = line.split(None, 1)
            tag = parts[0][1:]
            current = tag
            tags.setdefault(tag, []).append(parts[1] if len(parts) > 1 else "")
        elif current is None:
            description.append(line)
        else:
            tags[current][-1] += " " + line
    return {
        "description": " ".join(description).strip() or None,
        "tags": tags or None,
    }


def _class_body(class_node: Node) -> Node:
    return _field(class_node, "body") or class_node


def _iter_class_nodes(
    container: Node, parent_qualified: str | None
) -> list[tuple[Node, str | None, str | None, EntityKind]]:
    """Recursively collect type declarations with their qualified parent and kind."""
    result: list[tuple[Node, str | None, str | None, EntityKind]] = []
    for member, doc in _iter_members(container):
        if member.type not in _TYPE_TO_KIND:
            continue
        name = _entity_name(member)
        qualified = name if parent_qualified is None else f"{parent_qualified}.{name}"
        result.append((member, doc, parent_qualified, _member_kind(member)))
        result.extend(_iter_class_nodes(_class_body(member), qualified))
    return result


def _iter_method_specs(
    class_node: Node, class_qualified: str
) -> list[tuple[Node, str | None, str, set[str]]]:
    """Recursively collect (method_node, doc, class_qualified, fields) incl. nested types."""
    result: list[tuple[Node, str | None, str, set[str]]] = []
    class_fields = _class_fields(class_node)
    for member, doc in _iter_members(_class_body(class_node)):
        if member.type in _METHOD_MEMBER_TYPES:
            result.append((member, doc, class_qualified, class_fields))
        elif member.type in _TYPE_TO_KIND:
            nested_qualified = f"{class_qualified}.{_entity_name(member)}"
            result.extend(_iter_method_specs(member, nested_qualified))
    return result


def _inheritance_type_texts(container: Node) -> list[str]:
    """Extract type texts from a superclass / super_interfaces / extends_interfaces node."""
    result: list[str] = []
    for child in container.children:
        if child.type in ("implements", "extends", ","):
            continue
        if child.type == "type_list":
            result.extend(_inheritance_type_texts(child))
        else:
            result.append(_text(child))
    return result


def _inheritances(node: Node) -> list[InheritanceRef]:
    """Extract extends/implements edges for a type declaration node."""
    line = node.start_point.row + 1
    refs: list[InheritanceRef] = []
    if node.type == "class_declaration":
        superclass = _field(node, "superclass")
        if superclass is not None:
            types = _inheritance_type_texts(superclass)
            if types:
                refs.append(InheritanceRef(name=types[0], kind="extends", line=line))
        refs.extend(_interfaces_refs(node, "interfaces", "implements", line))
    elif node.type == "interface_declaration":
        refs.extend(_interfaces_refs(node, "extends_interfaces", "extends", line))
    elif node.type in ("enum_declaration", "record_declaration"):
        refs.extend(_interfaces_refs(node, "interfaces", "implements", line))
    return refs


def _interfaces_refs(
    node: Node, field_name: str, kind: str, line: int
) -> list[InheritanceRef]:
    interfaces = _field(node, field_name)
    if interfaces is None:
        interfaces = next(
            (c for c in node.children if c.type == "extends_interfaces"), None
        )
    if interfaces is None:
        return []
    return [
        InheritanceRef(name=name, kind=kind, line=line)
        for name in _inheritance_type_texts(interfaces)
    ]


def parse_java(source: str | bytes, path: str) -> ParsedFile:
    if isinstance(source, str):
        source = source.encode("utf-8")
    root = _PARSER.parse(source).root_node

    module_imports = _imports(root)
    class_nodes = _iter_class_nodes(root, None)
    method_specs: list[tuple[Node, str | None, str, set[str]]] = []
    for class_node, _, parent_qualified, _ in class_nodes:
        if parent_qualified is None:
            method_specs.extend(
                _iter_method_specs(class_node, _entity_name(class_node))
            )

    local_names = {_entity_name(node) for node, _, _, _ in class_nodes}
    for member, _, _, _ in method_specs:
        local_names.add(_entity_name(member))

    method_entities: list[ParsedEntity] = []
    for member, doc, class_qualified, class_fields in method_specs:
        name = _entity_name(member)
        method_entities.append(
            ParsedEntity(
                name=name,
                kind="method",
                parent=class_qualified,
                qualified_name=f"{class_qualified}.{name}",
                signature=_signature(member, name),
                line_start=member.start_point.row + 1,
                line_end=member.end_point.row + 1,
                is_public=_is_public(member),
                docstring=doc,
                complexity=_method_complexity(member),
                arguments=_arguments(member),
                return_type=_text(_field(member, "type")),
                decorators=[],
                globals_used=_globals_used(_field(member, "body") or member, class_fields),
                calls=_calls(_field(member, "body") or member, local_names),
                metadata={"javadoc": _parse_javadoc(doc)},
            )
        )

    complexities_by_class: dict[str, list[int]] = {}
    for method in method_entities:
        complexities_by_class.setdefault(method.parent or "", []).append(method.complexity)

    class_entities: list[ParsedEntity] = []
    for node, class_doc, parent_qualified, kind in class_nodes:
        name = _entity_name(node)
        qualified = name if parent_qualified is None else f"{parent_qualified}.{name}"
        class_entities.append(
            ParsedEntity(
                name=name,
                kind=kind,
                parent=parent_qualified,
                qualified_name=qualified,
                signature=qualified,
                line_start=node.start_point.row + 1,
                line_end=node.end_point.row + 1,
                is_public=_is_public(node),
                docstring=class_doc,
                complexity=max(complexities_by_class.get(qualified, []), default=1),
                arguments=[],
                return_type=None,
                decorators=[],
                globals_used=[],
                inheritances=_inheritances(node),
                metadata={"javadoc": _parse_javadoc(class_doc)},
            )
        )

    entities = class_entities + method_entities
    return ParsedFile(path=path, entities=entities, imports=module_imports, module_calls=[])

