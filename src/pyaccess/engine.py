"""High-level orchestrator: discover → parse → collect → enforce.

Two entry points are exposed:

* :func:`check_project` — full project scan, used by the CLI.
* :func:`build_index` + :func:`check_source` — incremental API used by the
  LSP server to re-check a single buffer on every keystroke without
  re-walking the whole project.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pyaccess.diagnostics import Diagnostic
from pyaccess.discovery import discover_python_files
from pyaccess.imports import ImportRef, collect_imports
from pyaccess.modules import module_name_for
from pyaccess.rules import access as access_rule
from pyaccess.rules import dynamic as dynamic_rule
from pyaccess.rules import private as private_rule
from pyaccess.symbols import Symbol, collect_symbols


@dataclass
class ProjectIndex:
    """Pre-computed view of a project: file ↔ module mapping and symbols."""

    root: Path
    files_by_module: dict[str, Path] = field(default_factory=dict)
    modules_by_file: dict[Path, str] = field(default_factory=dict)
    symbols_by_module: dict[str, dict[str, Symbol]] = field(default_factory=dict)
    imports_by_module: dict[str, list[ImportRef]] = field(default_factory=dict)
    # Per-file diagnostics from rules that only need one file's AST (PA01x).
    dynamic_diagnostics_by_module: dict[str, list[Diagnostic]] = field(default_factory=dict)


def _top_level_symbol_index(symbols: list[Symbol]) -> dict[str, Symbol]:
    """Keep only module-scope symbols (those addressable by ``from mod import X``)."""
    top_level: dict[str, Symbol] = {}
    for s in symbols:
        if s.kind in ("function", "class") and "." not in s.qualname:
            top_level[s.name] = s
    return top_level


def _parse_file(source: str, module: str) -> tuple[dict[str, Symbol], list[ImportRef]]:
    symbols = collect_symbols(source, module=module)
    imports = collect_imports(source, module=module)
    return _top_level_symbol_index(symbols), imports


def build_index(root: Path) -> ProjectIndex:
    """Scan ``root``, parse every file once, return a reusable index."""
    root = Path(root).resolve()
    index = ProjectIndex(root=root)
    for file in discover_python_files(root):
        module = module_name_for(file, root)
        if module is None:
            continue
        file = file.resolve()
        index.files_by_module[module] = file
        index.modules_by_file[file] = module
        try:
            source = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        top_level, imports = _parse_file(source, module)
        index.symbols_by_module[module] = top_level
        index.imports_by_module[module] = imports
        index.dynamic_diagnostics_by_module[module] = dynamic_rule.check(source, module, file)
    return index


def _run_rules(
    imports: list[ImportRef],
    symbols_by_module: Mapping[str, Mapping[str, Symbol]],
    files_by_module: Mapping[str, Path],
    dynamic_diagnostics_by_module: Mapping[str, list[Diagnostic]],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(access_rule.check(imports, symbols_by_module, files_by_module))
    diagnostics.extend(private_rule.check(imports, symbols_by_module, files_by_module))
    for diags in dynamic_diagnostics_by_module.values():
        diagnostics.extend(diags)
    return diagnostics


def check_project(root: Path) -> list[Diagnostic]:
    """Run all enabled rules on the project rooted at ``root``."""
    index = build_index(root)
    all_imports: list[ImportRef] = []
    for refs in index.imports_by_module.values():
        all_imports.extend(refs)
    return _run_rules(
        all_imports,
        index.symbols_by_module,
        index.files_by_module,
        index.dynamic_diagnostics_by_module,
    )


def check_source(
    index: ProjectIndex,
    file_path: Path,
    source: str | None = None,
) -> list[Diagnostic]:
    """Re-check a single buffer against a pre-built ``index``.

    ``source`` is the live editor content; when ``None`` we read from disk.
    Only diagnostics whose location is inside ``file_path`` are returned.
    """
    file_path = Path(file_path).resolve()
    module = index.modules_by_file.get(file_path)
    if module is None:
        module = module_name_for(file_path, index.root)
        if module is None:
            return []
        index.files_by_module[module] = file_path
        index.modules_by_file[file_path] = module

    if source is None:
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

    top_level, imports = _parse_file(source, module)
    # Update the live index so cross-file checks see the latest version.
    index.symbols_by_module[module] = top_level
    index.imports_by_module[module] = imports
    index.dynamic_diagnostics_by_module[module] = dynamic_rule.check(source, module, file_path)

    all_imports: list[ImportRef] = []
    for refs in index.imports_by_module.values():
        all_imports.extend(refs)
    diagnostics = _run_rules(
        all_imports,
        index.symbols_by_module,
        index.files_by_module,
        index.dynamic_diagnostics_by_module,
    )
    return [d for d in diagnostics if d.file == file_path]


