"""PA002 — cross-module import of a symbol marked ``@private``.

A ``@private`` symbol is only visible inside its defining module. Any
``from other.module import X`` performed from a *different* module — even
inside the same package — is a violation.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from pyaccess.diagnostics import Diagnostic
from pyaccess.imports import ImportRef
from pyaccess.markers import Visibility
from pyaccess.symbols import Symbol

CODE = "PA002"


def check(
    imports: Iterable[ImportRef],
    symbols_by_module: Mapping[str, Mapping[str, Symbol]],
    files_by_module: Mapping[str, Path],
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for imp in imports:
        if imp.imported_name in (None, "*"):
            continue
        target_symbols = symbols_by_module.get(imp.from_module)
        if target_symbols is None:
            continue
        symbol = target_symbols.get(imp.imported_name)
        if symbol is None or symbol.visibility is not Visibility.PRIVATE:
            continue
        if imp.importer == imp.from_module:
            continue  # same module: allowed (and shouldn't really happen on imports)
        file = files_by_module.get(imp.importer)
        if file is None:
            continue
        diagnostics.append(
            Diagnostic(
                code=CODE,
                message=(
                    f"'{imp.imported_name}' is marked @private in "
                    f"'{imp.from_module}' and cannot be imported from "
                    f"another module ('{imp.importer}')."
                ),
                file=file,
                line=imp.lineno,
                column=imp.col_offset,
                symbol=imp.imported_name,
            )
        )
    return diagnostics


