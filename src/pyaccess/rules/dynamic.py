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
PA015 = "PA015"  # direct __dict__ mutation
PA016 = "PA016"  # frame introspection (inspect.currentframe/stack, sys._getframe)
PA017 = "PA017"  # monkey-patching an attribute of an imported name
PA018 = "PA018"  # globals()/locals()/vars() used for a write, not a read

_ATTR_BUILTINS = {"getattr", "setattr", "hasattr", "delattr"}
_EXEC_BUILTINS = {"eval", "exec", "compile"}
_DICT_MUTATORS = {"update", "pop", "popitem", "setdefault", "clear", "__setitem__", "__delitem__"}
_NAMESPACE_BUILTINS = {"globals", "locals", "vars"}
_FRAME_INTROSPECTORS = {"inspect.currentframe", "inspect.stack", "inspect.trace", "sys._getframe"}
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


def _is_dunder_dict(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "__dict__"


def _namespace_builtin_call(node: ast.expr) -> str | None:
    """Return ``"globals"``/``"locals"``/``"vars"`` if ``node`` calls that builtin."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _NAMESPACE_BUILTINS
    ):
        return node.func.id
    return None


def _leftmost_name(node: ast.expr) -> str | None:
    """Walk down an attribute/subscript chain to the base ``Name``, if any."""
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _collect_imported_names(tree: ast.AST) -> set[str]:
    """Top-level names bound by ``import``/``from ... import`` in this file."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != "*":
                    names.add(alias.asname or alias.name)
    return names


def _collect_module_aliases(tree: ast.AST) -> dict[str, str]:
    """``import X [as Y]`` -> ``{local_name: "X"}`` (dotted names kept whole)."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
    return aliases


def _collect_from_aliases(tree: ast.AST) -> dict[str, tuple[str, str]]:
    """``from X import Y [as Z]`` -> ``{local_name: ("X", "Y")}``."""
    aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name != "*":
                    aliases[alias.asname or alias.name] = (node.module, alias.name)
    return aliases


def _assignment_targets(node: ast.Assign | ast.AugAssign) -> list[ast.expr]:
    return node.targets if isinstance(node, ast.Assign) else [node.target]


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
    imported_names = _collect_imported_names(tree)
    module_aliases = _collect_module_aliases(tree)
    from_aliases = _collect_from_aliases(tree)

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

            elif isinstance(node.func, ast.Attribute) and _is_dunder_dict(node.func.value):
                if node.func.attr in _DICT_MUTATORS:
                    emit(
                        PA015,
                        f"'.__dict__.{node.func.attr}()' mutates an object's "
                        "namespace directly, bypassing declared visibility.",
                        node,
                    )

            elif isinstance(node.func, ast.Attribute) and node.func.attr in _DICT_MUTATORS:
                builtin_name = _namespace_builtin_call(node.func.value)
                if builtin_name is not None:
                    emit(
                        PA018,
                        f"'{builtin_name}().{node.func.attr}()' mutates the "
                        "namespace dict directly, bypassing declared visibility.",
                        node,
                    )

            elif isinstance(node.func, ast.Attribute):
                base = _leftmost_name(node.func.value)
                real_module = module_aliases.get(base) if base else None
                if (real_module == "inspect" and node.func.attr in ("currentframe", "stack", "trace")) or (
                    real_module == "sys" and node.func.attr == "_getframe"
                ):
                    emit(
                        PA016,
                        f"'{func_name}()' inspects call-stack frames, which "
                        "escapes static analysis.",
                        node,
                    )

            elif isinstance(node.func, ast.Name):
                mapped = from_aliases.get(node.func.id)
                if mapped in {
                    ("inspect", "currentframe"),
                    ("inspect", "stack"),
                    ("inspect", "trace"),
                    ("sys", "_getframe"),
                }:
                    emit(
                        PA016,
                        f"'{node.func.id}()' inspects call-stack frames, which "
                        "escapes static analysis.",
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

        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            for target in _assignment_targets(node):
                if isinstance(target, ast.Subscript) and _is_dunder_dict(target.value):
                    emit(
                        PA015,
                        "subscript assignment into '__dict__' mutates an "
                        "object's namespace directly, bypassing declared visibility.",
                        node,
                    )
                elif isinstance(target, ast.Attribute) and target.attr == "__dict__":
                    emit(
                        PA015,
                        "direct reassignment of '__dict__' replaces an "
                        "object's whole namespace, bypassing declared visibility.",
                        node,
                    )
                elif isinstance(target, ast.Subscript):
                    builtin_name = _namespace_builtin_call(target.value)
                    if builtin_name is not None:
                        emit(
                            PA018,
                            f"subscript assignment into '{builtin_name}()' mutates "
                            "the namespace dict directly, bypassing declared visibility.",
                            node,
                        )
                elif isinstance(target, ast.Attribute):
                    base = _leftmost_name(target)
                    if base and base in imported_names and base not in ("self", "cls"):
                        emit(
                            PA017,
                            f"assigning to '{base}.{target.attr}' monkey-patches "
                            f"an attribute of the imported name '{base}'.",
                            node,
                        )

        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    builtin_name = _namespace_builtin_call(target.value)
                    if builtin_name is not None:
                        emit(
                            PA018,
                            f"'del {builtin_name}()[...]' mutates the namespace "
                            "dict directly, bypassing declared visibility.",
                            node,
                        )

    diagnostics.sort(key=lambda d: (d.line, d.column, d.code))
    return diagnostics
