"""Pure Python static analysis via the `ast` module + radon.

Extracts entities (functions/methods/classes), signatures, line ranges,
calls (file-local resolution), imports, global usage, and Radon cyclomatic
complexity. No I/O beyond the given source string, no LLM.
"""

from __future__ import annotations

import ast
import builtins
from collections.abc import Iterator

from radon.complexity import cc_visit

from app.analyzers.types import CallRef, EntityKind, ImportRef, ParsedEntity, ParsedFile

__all__ = ["CallRef", "EntityKind", "ImportRef", "ParsedEntity", "ParsedFile", "parse_python"]

EntityNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef

BUILTIN_NAMES = frozenset(dir(builtins))


def _iter_entities(tree: ast.Module) -> list[tuple[EntityNode, EntityKind, str | None, str]]:
    items: list[tuple[EntityNode, EntityKind, str | None, str]] = []

    def visit_body(
        body: list[ast.stmt], parent_qualified: str | None, parent_is_class: bool
    ) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind: EntityKind = "method" if parent_is_class else "function"
                qualified = _join_qualified(parent_qualified, node.name)
                items.append((node, kind, parent_qualified, qualified))
                visit_body(node.body, qualified, False)
            elif isinstance(node, ast.ClassDef):
                qualified = _join_qualified(parent_qualified, node.name)
                items.append((node, "class", parent_qualified, qualified))
                visit_body(node.body, qualified, True)

    visit_body(tree.body, None, False)
    return items


def _join_qualified(parent: str | None, name: str) -> str:
    return name if parent is None else f"{parent}.{name}"


def _signature(node: EntityNode) -> str:
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(base) for base in node.bases)
        return f"{node.name}({bases})" if bases else node.name
    arguments = ast.unparse(node.args)
    returns = ast.unparse(node.returns) if node.returns else None
    return f"{node.name}({arguments})" + (f" -> {returns}" if returns else "")


def _arguments(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names = [arg.arg for arg in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return names


def _is_nested_def(node: ast.AST) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))


def _walk_excluding_nested(node: ast.AST) -> Iterator[ast.AST]:
    for child in ast.iter_child_nodes(node):
        if _is_nested_def(child):
            continue
        yield child


def _globals_used(node: EntityNode, arguments: list[str]) -> list[str]:
    local = set(arguments)

    def collect_stores(current: ast.AST) -> None:
        for child in _walk_excluding_nested(current):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                local.add(child.id)
            collect_stores(child)

    collect_stores(node)

    loaded: set[str] = set()

    def collect_loads(current: ast.AST) -> None:
        for child in _walk_excluding_nested(current):
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                loaded.add(child.id)
            collect_loads(child)

    collect_loads(node)

    return sorted(loaded - local - BUILTIN_NAMES)


def _call_name(func: ast.AST) -> str:
    return ast.unparse(func)


def _dynamic_call_kind(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name) and func.id == "getattr":
        return "getattr"
    if isinstance(func, ast.Call):
        inner = func.func
        if isinstance(inner, ast.Name) and inner.id == "getattr":
            return "getattr"
    if isinstance(func, ast.Subscript):
        return "subscript"
    return None


def _dynamic_call_name(child: ast.Call) -> str:
    if isinstance(child.func, (ast.Call, ast.Subscript)):
        return ast.unparse(child.func)
    return ast.unparse(child)


def _collect_calls(node: EntityNode | ast.Module, local_names: set[str]) -> list[CallRef]:
    result: list[CallRef] = []

    def walk(current: ast.AST) -> None:
        for child in _walk_excluding_nested(current):
            if isinstance(child, ast.Call):
                dynamic = _dynamic_call_kind(child.func) is not None
                name = _dynamic_call_name(child) if dynamic else _call_name(child.func)
                result.append(
                    CallRef(
                        name=name,
                        line=child.lineno,
                        resolved=(not dynamic) and _is_local_call(name, local_names),
                        dynamic=dynamic,
                    )
                )
            walk(child)

    walk(node)
    return result


def _is_local_call(name: str, local_names: set[str]) -> bool:
    return name in local_names or name.rsplit(".", 1)[-1] in local_names


def _collect_imports(node: EntityNode | ast.Module) -> list[ImportRef]:
    result: list[ImportRef] = []

    def walk(current: ast.AST) -> None:
        for child in _walk_excluding_nested(current):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    result.append(
                        ImportRef(module=alias.name, local_name=alias.asname, line=child.lineno)
                    )
            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                for alias in child.names:
                    result.append(
                        ImportRef(
                            module=module,
                            local_name=alias.asname or alias.name,
                            line=child.lineno,
                        )
                    )
            walk(child)

    walk(node)
    return result


def _complexity_map(source: str) -> dict[tuple[str, str], int]:
    mapping: dict[tuple[str, str], int] = {}
    for block in cc_visit(source):
        if type(block).__name__ == "Class":
            mapping[("", block.name)] = block.complexity
        else:
            mapping[(block.classname or "", block.name)] = block.complexity
    return mapping


def parse_python(source: str, path: str) -> ParsedFile:
    tree = ast.parse(source)
    complexity_map = _complexity_map(source)
    items = _iter_entities(tree)
    local_names = {node.name for node, _, _, _ in items}

    entities: list[ParsedEntity] = []
    for node, kind, parent, qualified in items:
        arguments = (
            _arguments(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            else []
        )
        return_type = (
            ast.unparse(node.returns)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.returns is not None
            else None
        )
        complexity = complexity_map.get((parent or "", node.name))
        if complexity is None:
            complexity = complexity_map.get(("", node.name), 1)
        entities.append(
            ParsedEntity(
                name=node.name,
                kind=kind,
                parent=parent,
                qualified_name=qualified,
                signature=_signature(node),
                line_start=node.lineno,
                line_end=node.end_lineno or node.lineno,
                is_public=not node.name.startswith("_"),
                docstring=ast.get_docstring(node),
                complexity=complexity,
                arguments=arguments,
                return_type=return_type,
                decorators=[ast.unparse(dec) for dec in node.decorator_list],
                globals_used=_globals_used(node, arguments),
                calls=_collect_calls(node, local_names),
                imports=_collect_imports(node),
            )
        )

    return ParsedFile(
        path=path,
        entities=entities,
        imports=_collect_imports(tree),
        module_calls=_collect_calls(tree, local_names),
    )
