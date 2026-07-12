"""Stable entry point for PyCharm/LSP4IJ's *global* PyAccess language server definition.

LSP4IJ registers user-defined language servers at the IDE-application level, not
per project (confirmed: PyCharm stores the command line in
``%APPDATA%\\JetBrains\\<product>\\options\\UserDefinedLanguageServerSettings.xml``,
shared by every project window). That means the "Command" field can only ever
point at ONE path -- it cannot itself differ per worktree/project.

This script solves that by being the thing that path points at (configure once,
never touch it again). It contains no third-party dependencies (stdlib only) so
it can run with any Python 3 interpreter, and at every launch it:

1. Resolves the *current* project root -- LSP4IJ spawns the server process with
   its cwd set to the project root, so ``os.getcwd()`` is normally enough. As a
   safety net we also walk a few parent directories in case cwd is a
   subdirectory of the project (e.g. a nested source root).
2. Looks for that project's OWN dedicated venv (``venv/Scripts/pyaccess-lsp.exe``
   on Windows, ``venv/bin/pyaccess-lsp`` elsewhere) and, if found, execs it
   in-place (``os.execv``) so the *editable install living in that exact
   worktree* is what actually serves diagnostics -- always the right rule
   version for whichever worktree/project window PyCharm happens to be running,
   with zero manual reconfiguration when a new worktree is created.
3. Otherwise (no venv yet, or an unrelated repo that never opted into
   PyAccess) exits immediately without starting any server and without
   creating anything. This script never builds a venv itself -- that is
   .githooks/post-checkout's job (core.hooksPath=.githooks, shared repo-wide),
   which already builds it the moment a new worktree is created, before
   anyone opens PyCharm. If a project has no venv yet, PyAccess just stays
   silent there until the hook (or a manual `pip install -e .[dev,lsp]`) has
   run -- no diagnostics, no crash, no hidden background work from the IDE.

Combined with PyAccess's own pyproject.toml opt-in check (``_project_opts_in``
in ``pyaccess.lsp``), unrelated repos that don't opt into PyAccess never get
diagnostics and never even spawn a process for it.

Configure once in PyCharm's LSP4IJ language server settings (Settings ->
Languages & Frameworks -> Language Servers -> PyAccess -> Command):

    py -3 D:\\Dev\\pyaccess\\scripts\\pyaccess-lsp-dispatch.py

Point it at the MAIN checkout's copy of this script (not a worktree's), since
the main checkout is never deleted, so the command line never needs updating
again -- not even when worktrees are created or removed.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_MAX_PARENT_HOPS = 4


def _venv_lsp_executable(project_root: Path) -> Path | None:
    if os.name == "nt":
        candidate = project_root / "venv" / "Scripts" / "pyaccess-lsp.exe"
    else:
        candidate = project_root / "venv" / "bin" / "pyaccess-lsp"
    return candidate if candidate.is_file() else None


def _find_project_lsp_executable() -> Path | None:
    root = Path.cwd()
    for _ in range(_MAX_PARENT_HOPS + 1):
        found = _venv_lsp_executable(root)
        if found is not None:
            return found
        if (root / "pyproject.toml").is_file() or (root / ".git").exists():
            # Reached the project boundary; no per-project venv here, stop
            # looking further up rather than accidentally picking up an
            # unrelated ancestor project's venv.
            return None
        parent = root.parent
        if parent == root:
            return None
        root = parent
    return None


def main() -> int:
    executable = _find_project_lsp_executable()
    if executable is None:
        # No venv for this project (not built yet, or an unrelated repo that
        # never opted in): exit quietly, no server, no diagnostics.
        return 0

    argv = [str(executable), *sys.argv[1:]]
    os.execv(str(executable), argv)
    return 0  # pragma: no cover - execv does not return on success


if __name__ == "__main__":
    sys.exit(main())
