"""Language Server Protocol server for PyAccess.

Lets any LSP-aware editor (PyCharm via LSP4IJ, VS Code, Neovim, Helix…) get
live underlining as the user edits Python files.

The server keeps one :class:`ProjectIndex` per workspace root and refreshes it
incrementally on file open / save / change events.

Run it via::

    pyaccess-lsp                # stdio transport (what most clients want)

Requires the optional ``pygls`` dependency::

    pip install 'pyaccess[lsp]'
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

try:  # pragma: no cover - optional dependency
    from lsprotocol import types as lsp
    try:
        # pygls >= 2.0
        from pygls.lsp.server import LanguageServer
    except ImportError:
        # pygls 1.x
        from pygls.server import LanguageServer
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pyaccess-lsp requires the 'pygls' extra. Install with: pip install 'pyaccess[lsp]'"
    ) from exc

from pyaccess import __version__
from pyaccess.diagnostics import Diagnostic as PADiagnostic
from pyaccess.engine import ProjectIndex, build_index, check_source

SERVER_NAME = "pyaccess-lsp"


def _uri_to_path(uri: str) -> Path:
    """Convert a ``file://`` URI into a :class:`Path`."""
    parsed = urlparse(uri)
    path = unquote(parsed.path)
    # On Windows a URI looks like ``file:///D:/foo`` -> path is ``/D:/foo``.
    if path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]
    return Path(path)


def _to_lsp_diagnostic(d: PADiagnostic) -> lsp.Diagnostic:
    severity = (
        lsp.DiagnosticSeverity.Error
        if d.severity == "error"
        else lsp.DiagnosticSeverity.Warning
    )
    # PyAccess emits 1-based lines and 0-based columns; LSP wants both 0-based.
    line = max(d.line - 1, 0)
    col = max(d.column, 0)
    # When the rule knows the offending symbol's name, widen the range to its
    # full length so editors underline the whole identifier instead of a
    # nearly-invisible single character.
    width = len(d.symbol) if getattr(d, "symbol", None) else 1
    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(line=line, character=col),
            end=lsp.Position(line=line, character=col + width),
        ),
        message=d.message,
        severity=severity,
        code=d.code,
        source="pyaccess",
    )


class PyAccessLanguageServer(LanguageServer):
    """One :class:`ProjectIndex` per *project root* — not per LSP workspace.

    A single LSP workspace (e.g. the cloned ``pyaccess`` repo) may contain
    several independent Python projects (each demo under ``demos/`` has its
    own ``pyproject.toml``). We pick the *nearest enclosing* project root
    for every file so that module names resolve correctly.
    """

    def __init__(self) -> None:
        super().__init__(SERVER_NAME, __version__)
        self.indexes: dict[Path, ProjectIndex] = {}

    def index_for_file(self, file_path: Path) -> ProjectIndex:
        """Return (and cache) the index for the project that owns ``file_path``."""
        root = _guess_root(file_path.resolve())
        index = self.indexes.get(root)
        if index is None:
            index = build_index(root)
            self.indexes[root] = index
        return index

    def refresh_file(self, uri: str, source: str | None) -> None:
        path = _uri_to_path(uri).resolve()
        index = self.index_for_file(path)
        diagnostics = check_source(index, file_path=path, source=source)
        self.publish(uri, [_to_lsp_diagnostic(d) for d in diagnostics])

    def publish(self, uri: str, diagnostics: list) -> None:
        """Send ``textDocument/publishDiagnostics`` for ``uri``.

        Wrapping the pygls call in a tiny indirection makes the server easy to
        monkeypatch in tests and shields us from minor API drift between
        pygls 1.x and 2.x.
        """
        params = lsp.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
        if hasattr(self, "text_document_publish_diagnostics"):
            self.text_document_publish_diagnostics(params)
        else:  # pragma: no cover - pygls 1.x fallback
            self.publish_diagnostics(uri, diagnostics)


def _guess_root(path: Path) -> Path:
    """Walk up from ``path`` to find the nearest project root.

    A project root is the closest ancestor directory that contains a
    ``pyproject.toml`` or ``pyaccess.toml``. Falls back to the file's parent
    directory when none is found.
    """
    candidates = [path, *path.parents] if path.is_dir() else list(path.parents)
    for parent in candidates:
        if (parent / "pyproject.toml").exists() or (parent / "pyaccess.toml").exists():
            return parent
    return path.parent


def create_server() -> PyAccessLanguageServer:
    server = PyAccessLanguageServer()

    @server.feature(lsp.INITIALIZED)
    def _on_initialized(ls: PyAccessLanguageServer, params) -> None:  # pragma: no cover  # noqa: ARG001
        # No eager indexing: a single workspace can contain several
        # independent Python projects (e.g. the demos folder). Indexes are
        # built lazily per file, rooted at the nearest enclosing
        # ``pyproject.toml`` / ``pyaccess.toml``.
        logging.getLogger("pyaccess").info(
            "initialized with %d workspace folder(s)",
            len(getattr(ls.workspace, "folders", {}) or {}),
        )

    @server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
    def _on_open(ls: PyAccessLanguageServer, params: lsp.DidOpenTextDocumentParams) -> None:
        ls.refresh_file(params.text_document.uri, params.text_document.text)

    @server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
    def _on_change(ls: PyAccessLanguageServer, params: lsp.DidChangeTextDocumentParams) -> None:
        doc = ls.workspace.get_text_document(params.text_document.uri)
        ls.refresh_file(params.text_document.uri, doc.source)

    @server.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
    def _on_save(ls: PyAccessLanguageServer, params: lsp.DidSaveTextDocumentParams) -> None:
        doc = ls.workspace.get_text_document(params.text_document.uri)
        ls.refresh_file(params.text_document.uri, doc.source)

    return server


def main() -> None:  # pragma: no cover - entrypoint
    log_path = os.environ.get("PYACCESS_LSP_LOG")
    if log_path:
        logging.basicConfig(
            filename=log_path,
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        logging.getLogger("pyaccess").info("pyaccess-lsp starting (pid=%s)", os.getpid())
    create_server().start_io()


if __name__ == "__main__":  # pragma: no cover
    main()







