"""Language Server Protocol server for PyAccess.

Lets any LSP-aware editor (PyCharm via LSP4IJ, VS Code, Neovim, Helix…) get
live underlining as the user edits Python files.

The server keeps one :class:`ProjectIndex` per workspace root and refreshes it
incrementally on file open / save / change events.

Two extra behaviours make it practical to run one PyAccess checkout per
worktree, each hacking on the rules independently, all inside the same IDE
installation at once:

* **Per-project opt-in** (:func:`_project_opts_in`): a project is only
  linted if it declares ``pyaccess`` as a dependency or ships a
  ``pyaccess.toml`` / ``[tool.pyaccess]`` section. Editors like PyCharm
  register a language server IDE-wide, not per project, so without this an
  unrelated repo opened in the same IDE window would get PyAccess
  diagnostics too.
* **Hot-reloading rules** (:class:`RuleWatcher`): PyAccess is normally
  installed editable (``pip install -e .``), so editing a rule already
  changes what the *next* CLI run sees. The LSP server, however, is one
  long-lived process — this watcher polls its own source files and
  reloads+re-lints automatically on change, so there is no server restart
  and no manual step between editing a rule and seeing updated squiggles.

Run it via::

    pyaccess-lsp                # stdio transport (what most clients want)

Requires the optional ``pygls`` dependency::

    pip install 'pyaccess[lsp]'
"""
from __future__ import annotations

import contextlib
import importlib
import logging
import os
import sys
import threading
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
from pyaccess import engine as engine_mod
from pyaccess.diagnostics import Diagnostic as PADiagnostic
from pyaccess.engine import ProjectIndex  # noqa: F401 - re-exported for type hints only

SERVER_NAME = "pyaccess-lsp"

# Rule/engine modules that are safe to hot-reload in-process. Deliberately
# excludes ``pyaccess.lsp`` (the module driving the currently-running server)
# and ``pyaccess.cli``: reloading the code that is on the call stack right
# now is unsafe, and neither module is a "rule" a user would iterate on.
_RELOAD_BLOCKLIST = {"pyaccess.lsp", "pyaccess.cli", "pyaccess"}

# Reload leaves before the modules that import them, so that by the time
# ``pyaccess.engine`` is reloaded it re-imports already-fresh rule modules.
_RELOAD_ORDER_HINT = (
    "pyaccess.markers",
    "pyaccess.diagnostics",
    "pyaccess.discovery",
    "pyaccess.modules",
    "pyaccess.imports",
    "pyaccess.symbols",
    "pyaccess.graph",
    "pyaccess.reexports",
    "pyaccess.config",
    "pyaccess.rules",
    "pyaccess.rules.access",
    "pyaccess.rules.private",
    "pyaccess.rules.dynamic",
    "pyaccess.engine",
)


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


def _project_opts_in(root: Path) -> bool:
    """Return whether ``root`` actually wants PyAccess to run on it.

    The LSP client (e.g. PyCharm/LSP4IJ) typically registers ``pyaccess-lsp``
    for every ``*.py`` file in the IDE, regardless of which project window is
    focused -- LSP4IJ's server registrations are IDE-wide, not per-project
    (see the project README for details). To avoid linting unrelated repos
    that happen to be open in the same editor, a project must *opt in* by
    either declaring ``pyaccess`` as a dependency in its ``pyproject.toml``
    or by shipping a ``pyaccess.toml`` / ``[tool.pyaccess]`` section. A repo
    with neither gets zero diagnostics, silently and automatically -- no
    per-project IDE configuration required.
    """
    if (root / "pyaccess.toml").is_file():
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        import tomllib  # Python >= 3.11
    except ModuleNotFoundError:  # pragma: no cover - Python 3.10
        import tomli as tomllib  # type: ignore[no-redef]
    try:
        data = tomllib.loads(text)
    except Exception:  # pragma: no cover - malformed pyproject.toml
        return False
    if "pyaccess" in data.get("tool", {}):
        return True
    project = data.get("project", {})
    deps = list(project.get("dependencies", ()))
    for extra_deps in project.get("optional-dependencies", {}).values():
        deps.extend(extra_deps)
    return any(
        dep.split(";", 1)[0].strip().split(">")[0].split("=")[0].split("<")[0].strip().lower()
        == "pyaccess"
        for dep in deps
    )


def _watched_pyaccess_source_files() -> dict[str, Path]:
    """Map every currently-loaded, hot-reloadable ``pyaccess.*`` module to
    its backing ``.py`` file, for mtime-based change detection.
    """
    files: dict[str, Path] = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith("pyaccess.") and name != "pyaccess":
            continue
        if name in _RELOAD_BLOCKLIST:
            continue
        path = getattr(module, "__file__", None)
        if path:
            files[name] = Path(path)
    return files


class RuleWatcher:
    """Hot-reloads PyAccess's own rule/engine code when it changes on disk.

    Because ``pyaccess-lsp`` is installed editable (``pip install -e .``),
    editing a file under ``src/pyaccess/rules/`` already changes what the
    *next* run of the CLI sees for free. The LSP server, however, is a
    long-lived process that imported those modules once at startup -- Python
    does not re-execute module code just because the file on disk changed.

    This watcher polls the mtimes of PyAccess's own source files on a
    background thread and, on any change, calls :func:`importlib.reload` on
    the affected modules (leaves first, ``pyaccess.engine`` last) and then
    asks the server to drop its cached project indexes and re-lint every
    open document. The net effect: editing a rule and saving is reflected in
    PyCharm's live squiggles within ``interval`` seconds, with no server
    restart and no manual action.
    """

    def __init__(self, server: PyAccessLanguageServer, interval: float = 1.0) -> None:
        self._server = server
        self._interval = interval
        self._mtimes: dict[str, float] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot()

    def _snapshot(self) -> None:
        for name, path in _watched_pyaccess_source_files().items():
            with contextlib.suppress(OSError):
                self._mtimes[name] = path.stat().st_mtime

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="pyaccess-rule-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:  # pragma: no cover - timing-dependent
        logger = logging.getLogger("pyaccess")
        while not self._stop.wait(self._interval):
            try:
                changed = self._changed_modules()
                if changed:
                    self._reload(changed)
            except Exception:
                # A single bad iteration (e.g. the LSP client hasn't
                # finished initializing yet, or a reload/relint edge case)
                # must never kill this daemon thread -- otherwise every
                # future edit would silently stop hot-reloading until the
                # whole server process is restarted, defeating the point.
                logger.exception("pyaccess: rule watcher iteration failed")

    def _changed_modules(self) -> list[str]:
        changed = []
        for name, path in _watched_pyaccess_source_files().items():
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if self._mtimes.get(name) != mtime:
                self._mtimes[name] = mtime
                changed.append(name)
        return changed

    def _reload(self, changed: list[str]) -> None:
        logger = logging.getLogger("pyaccess")
        ordered = [n for n in _RELOAD_ORDER_HINT if n in sys.modules]
        extra = [
            n
            for n in sys.modules
            if (n.startswith("pyaccess.") or n == "pyaccess")
            and n not in _RELOAD_BLOCKLIST
            and n not in ordered
        ]
        for name in [*extra, *ordered]:
            try:
                importlib.reload(sys.modules[name])
            except Exception:
                logger.exception("pyaccess: hot-reload of %s failed", name)
                return
        logger.info("pyaccess: hot-reloaded %s", ", ".join(sorted(changed)))
        self._server.rebuild_and_relint()


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
        self._opt_in_cache: dict[Path, bool] = {}
        self.rule_watcher: RuleWatcher | None = None

    def index_for_file(self, file_path: Path) -> ProjectIndex | None:
        """Return (and cache) the index for the project that owns ``file_path``.

        Returns ``None`` if the owning project hasn't opted in to PyAccess
        (see :func:`_project_opts_in`) -- e.g. an unrelated repo that just
        happens to be open in the same IDE instance.
        """
        root = _guess_root(file_path.resolve())
        opted_in = self._opt_in_cache.get(root)
        if opted_in is None:
            opted_in = _project_opts_in(root)
            self._opt_in_cache[root] = opted_in
        if not opted_in:
            return None
        index = self.indexes.get(root)
        if index is None:
            # Always call through the module so a hot-reloaded
            # ``pyaccess.engine`` (see RuleWatcher) is picked up immediately,
            # even though this method itself was never reloaded.
            index = engine_mod.build_index(root)
            self.indexes[root] = index
        return index

    def refresh_file(self, uri: str, source: str | None) -> None:
        path = _uri_to_path(uri).resolve()
        index = self.index_for_file(path)
        if index is None:
            self.publish(uri, [])
            return
        diagnostics = engine_mod.check_source(index, file_path=path, source=source)
        self.publish(uri, [_to_lsp_diagnostic(d) for d in diagnostics])

    def rebuild_and_relint(self) -> None:
        """Drop every cached project index and re-check all open documents.

        Called by :class:`RuleWatcher` right after a hot-reload so that a
        change to a rule's implementation is reflected in already-open
        editors automatically, without the user re-opening files or
        restarting the server.
        """
        self.indexes.clear()
        self._opt_in_cache.clear()
        try:
            documents = list(self.workspace.text_documents.items())
        except RuntimeError:
            # The LSP client hasn't finished the initialize handshake yet
            # (e.g. a rule file was edited moments after the server
            # process started). There are no open documents to re-lint
            # yet -- the cleared caches above are enough to make the very
            # first refresh_file() call use the fresh code.
            return
        for uri, doc in documents:
            self.refresh_file(uri, doc.source)

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


def create_server(*, watch_rules: bool = True) -> PyAccessLanguageServer:
    server = PyAccessLanguageServer()

    if watch_rules and not os.environ.get("PYACCESS_LSP_NO_WATCH"):
        # Hot-reload PyAccess's own rules on change -- see RuleWatcher's
        # docstring. Disable with PYACCESS_LSP_NO_WATCH=1 (e.g. for a
        # packaged/non-editable install where the source never changes).
        server.rule_watcher = RuleWatcher(server)
        server.rule_watcher.start()

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







