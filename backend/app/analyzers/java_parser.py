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

from app.analyzers.types import CallRef, ImportRef, ParsedEntity, ParsedFile

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
_MEMBER_TYPES = frozenset(
    {"class_declaration", "method_declaration", "constructor_declaration"}
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


def _member_kind(node: Node) -> str:
    if node.type == "class_declaration":
        return "class"
    return "method"


def _iter_members(container: Node) -> list[tuple[Node, str | None]]:
    result: list[tuple[Node, str | None]] = []
    pending: list[str] = []
    for child in container.children:
        if child.type in _COMMENT_TYPES:
            pending.append(_text(child))
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
        scoped = _field(declaration, "scoped_identifier")
        if scoped is None:
            scoped = next(
                (c for c in declaration.children if c.type == "scoped_identifier"), None
            )
        module = _text(scoped)
        if module.endswith(".*"):
            module = module[:-2]
        if module:
            result.append(
                ImportRef(module=module, local_name=None, line=declaration.start_point.row + 1)
            )
    return result


def parse_java(source: str | bytes, path: str) -> ParsedFile:
    if isinstance(source, str):
        source = source.encode("utf-8")
    root = _PARSER.parse(source).root_node

    module_imports = _imports(root)
    class_nodes: list[tuple[Node, str | None]] = []
    method_specs: list[tuple[Node, str | None, str, set[str]]] = []

    for class_node, class_doc in _iter_members(root):
        if _member_kind(class_node) != "class":
            continue
        class_name = _entity_name(class_node)
        body = _field(class_node, "body") or class_node
        class_fields = _class_fields(class_node)
        class_nodes.append((class_node, class_doc))
        for member, doc in _iter_members(body):
            if _member_kind(member) == "method":
                method_specs.append((member, doc, class_name, class_fields))

    local_names = {_entity_name(node) for node, _ in class_nodes}
    for member, _, _, _ in method_specs:
        local_names.add(_entity_name(member))

    method_entities: list[ParsedEntity] = []
    for member, doc, class_name, class_fields in method_specs:
        name = _entity_name(member)
        method_entities.append(
            ParsedEntity(
                name=name,
                kind="method",
                parent=class_name,
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
            )
        )

    complexities_by_class: dict[str, list[int]] = {}
    for method in method_entities:
        complexities_by_class.setdefault(method.parent or "", []).append(method.complexity)

    class_entities = [
        ParsedEntity(
            name=_entity_name(node),
            kind="class",
            parent=None,
            signature=_entity_name(node),
            line_start=node.start_point.row + 1,
            line_end=node.end_point.row + 1,
            is_public=_is_public(node),
            docstring=doc,
            complexity=max(complexities_by_class.get(_entity_name(node), []), default=1),
            arguments=[],
            return_type=None,
            decorators=[],
            globals_used=[],
        )
        for node, doc in class_nodes
    ]

    entities = class_entities + method_entities
    return ParsedFile(path=path, entities=entities, imports=module_imports, module_calls=[])

