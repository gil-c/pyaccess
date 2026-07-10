"""PA01x — detection of dynamic Python constructs that defeat static analysis.

Unlike PA001/PA002 (which need the whole-project import graph), these checks
are purely local to a single file: each source is parsed once and walked for
a fixed list of "escape the type/analysis system" patterns.

Every diagnostic can be silenced through one of three escape hatches:

* An inline trailing comment on the offending line: ``# pyaccess: allow-dynamic``
* A ``@dynamic`` (or ``@dynamic(reason="...")``) decorator on the enclosing
  function or class — silences every dynamic diagnostic raised anywhere in
  that function/class body.
* A module-level marker comment near the top of the file:
  ``# pyaccess: dynamic-module`` — silences every dynamic diagnostic in the
  whole module.
"""
from __future__ import annotations

import ast
from pathlib import Path

from pyaccess.diagnostics import Diagnostic

PA010 = "PA010"  # getattr/setattr/hasattr/delattr with a non-literal name
PA011 = "PA011"  # eval / exec / compile
PA012 = "PA012"  # importlib.import_module / __import__ with a non-literal target
PA013 = "PA013"  # module-level __getattr__ / __getattribute__
PA014 = "PA014"  # explicit custom metaclass

_ATTR_BUILTINS = {"getattr", "setattr", "hasattr", "delattr"}
_EXEC_BUILTINS = {"eval", "exec", "compile"}
_INLINE_MARKER = "pyaccess: allow-dynamic"
_MODULE_MARKER = "pyaccess: dynamic-module"
_MODULE_MARKER_SCAN_LINES = 20


def _dotted_name(node: ast.expr) -> str:
    """Best-effort dotted name for a ``Call.func`` or decorator expression."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _dotted_name(node.func)
    return ""


def _collect_dynamic_aliases(tree: ast.AST) -> set[str]:
    """Names bound to ``pyaccess.dynamic`` in this module (handles aliasing)."""
    aliases = {"dynamic"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pyaccess"):
            for alias in node.names:
                if alias.name == "dynamic":
                    aliases.add(alias.asname or "dynamic")
    return aliases


def _is_dynamic_decorator(dec: ast.expr, aliases: set[str]) -> bool:
    name = _dotted_name(dec)
    if not name:
        return False
    head = name.split(".", 1)[0]
    tail = name.rsplit(".", 1)[-1]
    return head in aliases or tail == "dynamic"


def _module_marker_present(source: str) -> bool:
    return any(_MODULE_MARKER in line for line in source.splitlines()[:_MODULE_MARKER_SCAN_LINES])


def _inline_allowed_lines(source: str) -> set[int]:
    return {i for i, line in enumerate(source.splitlines(), start=1) if _INLINE_MARKER in line}


def _dynamic_decorated_ranges(tree: ast.AST, aliases: set[str]) -> list[tuple[int, int]]:
    """(start_line, end_line) spans covered by an enclosing ``@dynamic``."""
    ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        is_defish = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        if is_defish and any(_is_dynamic_decorator(dec, aliases) for dec in node.decorator_list):
            start = min((dec.lineno for dec in node.decorator_list), default=node.lineno)
            end = getattr(node, "end_lineno", None) or node.lineno
            ranges.append((start, end))
    return ranges


def _is_literal_str(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _positional_or_keyword(call: ast.Call, index: int, keyword: str) -> ast.expr | None:
    if index < len(call.args):
        return call.args[index]
    for kw in call.keywords:
        if kw.arg == keyword:
            return kw.value
    return None


def check(source: str, module: str, file: Path) -> list[Diagnostic]:  # noqa: ARG001
    """Scan a single file's source for dynamic constructs.

    ``module`` is accepted for symmetry with the other rules but unused here:
    every check in this rule is local to the file's own AST.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    if _module_marker_present(source):
        return []

    aliases = _collect_dynamic_aliases(tree)
    allowed_lines = _inline_allowed_lines(source)
    dynamic_ranges = _dynamic_decorated_ranges(tree, aliases)

    def is_suppressed(lineno: int) -> bool:
        if lineno in allowed_lines:
            return True
        return any(start <= lineno <= end for start, end in dynamic_ranges)

    diagnostics: list[Diagnostic] = []

    def emit(code: str, message: str, node: ast.AST, *, severity: str = "error") -> None:
        lineno = getattr(node, "lineno", 1)
        if is_suppressed(lineno):
            return
        diagnostics.append(
            Diagnostic(
                code=code,
                message=message,
                file=file,
                line=lineno,
                column=getattr(node, "col_offset", 0),
                severity=severity,
            )
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _dotted_name(node.func)
            simple_name = func_name.rsplit(".", 1)[-1]

            if simple_name in _ATTR_BUILTINS and isinstance(node.func, ast.Name):
                name_arg = _positional_or_keyword(node, 1, "name")
                if name_arg is not None and not _is_literal_str(name_arg):
                    emit(
                        PA010,
                        f"'{simple_name}()' is called with a non-literal attribute "
                        "name, which defeats static accessibility analysis.",
                        node,
                    )

            elif simple_name in _EXEC_BUILTINS and isinstance(node.func, ast.Name):
                emit(
                    PA011,
                    f"'{simple_name}()' executes dynamically generated code and "
                    "cannot be statically analysed.",
                    node,
                )

            elif func_name == "importlib.import_module" or (
                isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
            ):
                target = _positional_or_keyword(node, 0, "name")
                if target is not None and not _is_literal_str(target):
                    emit(
                        PA012,
                        "'importlib.import_module()' is called with a non-literal "
                        "module name and cannot be statically resolved.",
                        node,
                    )

            elif simple_name == "__import__" and isinstance(node.func, ast.Name):
                target = _positional_or_keyword(node, 0, "name")
                if target is not None and not _is_literal_str(target):
                    emit(
                        PA012,
                        "'__import__()' is called with a non-literal module name "
                        "and cannot be statically resolved.",
                        node,
                    )

        elif isinstance(node, ast.Module):
            for stmt in node.body:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name in (
                    "__getattr__",
                    "__getattribute__",
                ):
                    emit(
                        PA013,
                        f"module-level '{stmt.name}' intercepts attribute access "
                        "and cannot be statically analysed.",
                        stmt,
                    )

        elif isinstance(node, ast.ClassDef):
            for kw in node.keywords:
                if kw.arg == "metaclass":
                    emit(
                        PA014,
                        f"class '{node.name}' declares an explicit metaclass, "
                        "which can rewrite the class body dynamically.",
                        node,
                        severity="warning",
                    )

    diagnostics.sort(key=lambda d: (d.line, d.column, d.code))
    return diagnostics
