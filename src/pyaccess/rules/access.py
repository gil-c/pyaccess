"""PA001 — cross-package import of a symbol marked ``@internal``.

This is the foundational rule of PyAccess. It walks every import site in the
project and reports those that resolve to an ``@internal`` symbol defined in
a *different* top-level package.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from pyaccess.diagnostics import Diagnostic
from pyaccess.imports import ImportRef
from pyaccess.markers import Visibility
from pyaccess.modules import top_level_package
from pyaccess.symbols import Symbol

CODE = "PA001"


def check(
    imports: Iterable[ImportRef],
    symbols_by_module: Mapping[str, Mapping[str, Symbol]],
    files_by_module: Mapping[str, Path],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for imp in imports:
        if imp.imported_name in (None, "*"):
            # `import pkg.mod` and star imports are out of scope for the POC.
            continue
        target_symbols = symbols_by_module.get(imp.from_module)
        if target_symbols is None:
            continue  # external dependency or undiscovered module
        symbol = target_symbols.get(imp.imported_name)
        if symbol is None or symbol.visibility is not Visibility.INTERNAL:
            continue
        if top_level_package(imp.importer) == top_level_package(imp.from_module):
            continue  # same top-level package — allowed
        file = files_by_module.get(imp.importer)
        if file is None:
            continue
        diagnostics.append(
            Diagnostic(
                code=CODE,
                message=(
                    f"'{imp.imported_name}' is marked @internal in "
                    f"'{imp.from_module}' and cannot be imported from "
                    f"package '{top_level_package(imp.importer)}'."
                ),
                file=file,
                line=imp.lineno,
                column=imp.col_offset,
                symbol=imp.imported_name,
            )
        )
    return diagnostics


