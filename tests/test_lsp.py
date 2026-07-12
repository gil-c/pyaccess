"""Smoke tests for the LSP server."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("pygls")
pytest.importorskip("lsprotocol")
from pyaccess.diagnostics import Diagnostic as PADiagnostic  # noqa: E402
from pyaccess.lsp import (  # noqa: E402
    _guess_root,
    _project_opts_in,
    _to_lsp_diagnostic,
    _uri_to_path,
    create_server,
)


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
def test_uri_to_path_windows_drive(tmp_path: Path):
    uri = tmp_path.as_uri()
    assert _uri_to_path(uri).resolve() == tmp_path.resolve()
def test_diagnostic_conversion_uses_zero_based_line(tmp_path: Path):
    pad = PADiagnostic(code="PA001", message="boom", file=tmp_path / "x.py",
                       line=5, column=2, severity="error")
    lsp_diag = _to_lsp_diagnostic(pad)
    assert lsp_diag.range.start.line == 4
    assert lsp_diag.range.start.character == 2
    assert lsp_diag.code == "PA001"
    assert lsp_diag.source == "pyaccess"
def test_diagnostic_range_widens_to_symbol_name(tmp_path: Path):
    pad = PADiagnostic(code="PA001", message="boom", file=tmp_path / "x.py",
                       line=1, column=10, severity="error", symbol="helper")
    lsp_diag = _to_lsp_diagnostic(pad)
    assert lsp_diag.range.start.character == 10
    assert lsp_diag.range.end.character == 10 + len("helper")
def test_diagnostic_range_falls_back_to_one_char_when_no_symbol(tmp_path: Path):
    pad = PADiagnostic(code="PA001", message="boom", file=tmp_path / "x.py",
                       line=1, column=0)
    assert _to_lsp_diagnostic(pad).range.end.character == 1
def test_guess_root_prefers_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    nested = tmp_path / "pkg" / "sub" / "mod.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("x = 1\n")
    assert _guess_root(nested) == tmp_path
def test_guess_root_prefers_nearest_pyproject(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='repo'\n")
    inner = tmp_path / "demos" / "demo_a"
    inner.mkdir(parents=True)
    (inner / "pyproject.toml").write_text("[project]\nname='demo_a'\n")
    nested_file = inner / "pkg" / "mod.py"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("x = 1\n")
    assert _guess_root(nested_file) == inner
def test_refresh_file_publishes_diagnostics_for_violation(tmp_path: Path, monkeypatch):
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\ndependencies=['pyaccess']\n")
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    user = tmp_path / "beta" / "user.py"
    user.write_text("from alpha.core import helper\n")
    server = create_server(watch_rules=False)
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    server.refresh_file(user.as_uri(), source=user.read_text())
    assert len(published) == 1
    uri, diags = published[0]
    assert uri == user.as_uri()
    assert any(d.code == "PA001" for d in diags)
def test_refresh_file_clears_diagnostics_when_buffer_is_fixed(tmp_path: Path, monkeypatch):
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\ndependencies=['pyaccess']\n")
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    user = tmp_path / "beta" / "user.py"
    user.write_text("from alpha.core import helper\n")
    server = create_server(watch_rules=False)
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    server.refresh_file(user.as_uri(), source="# fixed\n")
    assert published[-1][1] == []
def test_refresh_file_routes_each_demo_to_its_own_index(tmp_path: Path, monkeypatch):
    _write(tmp_path, "pyproject.toml", "[project]\nname='repo'\ndependencies=['pyaccess']\n")
    for demo in ("demo_a", "demo_b"):
        _write(tmp_path, f"demos/{demo}/pyproject.toml",
               f"[project]\nname='{demo}'\ndependencies=['pyaccess']\n")
        _write(tmp_path, f"demos/{demo}/alpha/__init__.py", "")
        _write(tmp_path, f"demos/{demo}/alpha/core.py",
               "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
        _write(tmp_path, f"demos/{demo}/beta/__init__.py", "")
        _write(tmp_path, f"demos/{demo}/beta/user.py",
               "from alpha.core import helper\n")
    server = create_server(watch_rules=False)
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    for demo in ("demo_a", "demo_b"):
        user = tmp_path / "demos" / demo / "beta" / "user.py"
        server.refresh_file(user.as_uri(), source=user.read_text())
    assert len(published) == 2
    for _uri, diags in published:
        assert any(d.code == "PA001" for d in diags)


# ---------------------------------------------------------------------------
# Per-project opt-in: an unrelated repo open in the same IDE gets no
# diagnostics, automatically, with no manual per-project IDE configuration.
# ---------------------------------------------------------------------------
def test_project_opts_in_via_pyproject_dependency(tmp_path: Path):
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\ndependencies=['pyaccess']\n")
    assert _project_opts_in(tmp_path) is True
def test_project_opts_in_via_optional_dependency(tmp_path: Path):
    _write(tmp_path, "pyproject.toml",
           "[project]\nname='x'\n[project.optional-dependencies]\nlsp=['pyaccess']\n")
    assert _project_opts_in(tmp_path) is True
def test_project_opts_in_via_tool_section(tmp_path: Path):
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n[tool.pyaccess]\n")
    assert _project_opts_in(tmp_path) is True
def test_project_opts_in_via_standalone_pyaccess_toml(tmp_path: Path):
    _write(tmp_path, "pyproject.toml", "[project]\nname='x'\n")
    _write(tmp_path, "pyaccess.toml", "default_visibility = 'public'\n")
    assert _project_opts_in(tmp_path) is True
def test_project_does_not_opt_in_by_default(tmp_path: Path):
    _write(tmp_path, "pyproject.toml", "[project]\nname='some-other-repo'\ndependencies=['requests']\n")
    assert _project_opts_in(tmp_path) is False
def test_project_without_pyproject_does_not_opt_in(tmp_path: Path):
    assert _project_opts_in(tmp_path) is False
def test_refresh_file_stays_silent_for_a_repo_that_has_not_opted_in(tmp_path: Path, monkeypatch):
    # A completely unrelated Python repo -- no pyaccess dependency anywhere --
    # that just happens to be open in the same IDE/LSP client instance.
    _write(tmp_path, "pyproject.toml", "[project]\nname='unrelated'\ndependencies=['requests']\n")
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    user = tmp_path / "beta" / "user.py"
    user.write_text("from alpha.core import helper\n")
    server = create_server(watch_rules=False)
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    server.refresh_file(user.as_uri(), source=user.read_text())
    assert published == [(user.as_uri(), [])]


# ---------------------------------------------------------------------------
# Hot-reload: editing PyAccess's own source is picked up automatically, with
# no server restart. Exercised against a throwaway fake module so the test
# never mutates the real, currently-running pyaccess package.
# ---------------------------------------------------------------------------
def test_rule_watcher_detects_mtime_change(tmp_path: Path, monkeypatch):
    import sys
    import types

    from pyaccess import lsp as lsp_module

    fake_file = tmp_path / "fake_rule.py"
    fake_file.write_text("VALUE = 1\n")
    fake_module = types.ModuleType("pyaccess.fake_rule_for_test")
    fake_module.__file__ = str(fake_file)
    monkeypatch.setitem(sys.modules, "pyaccess.fake_rule_for_test", fake_module)

    server = create_server(watch_rules=False)
    watcher = lsp_module.RuleWatcher(server, interval=999)
    assert watcher._changed_modules() == []  # nothing touched yet

    # Bump the mtime forward so the change is detected even on filesystems
    # with coarse (e.g. 2s, FAT-style) mtime resolution.
    new_mtime = fake_file.stat().st_mtime + 5
    fake_file.write_text("VALUE = 2\n")
    os.utime(fake_file, (new_mtime, new_mtime))
    assert watcher._changed_modules() == ["pyaccess.fake_rule_for_test"]
    assert watcher._changed_modules() == []  # second call: no further change
def test_rule_watcher_reload_orders_leaves_before_engine_and_relints(monkeypatch):
    from pyaccess import lsp as lsp_module

    server = create_server(watch_rules=False)
    relint_calls = []
    monkeypatch.setattr(server, "rebuild_and_relint", lambda: relint_calls.append(True))

    # Exercise the *orchestration* logic against real, already-loaded pyaccess
    # modules, but stub out importlib.reload itself so the test never
    # mutates the actual running pyaccess package (which other tests in this
    # same process still depend on).
    reload_order = []
    monkeypatch.setattr(
        lsp_module.importlib, "reload", lambda mod: reload_order.append(mod.__name__)
    )

    watcher = lsp_module.RuleWatcher(server, interval=999)  # never auto-fires
    watcher._reload(["pyaccess.rules.access"])

    assert "pyaccess.rules.access" in reload_order
    assert "pyaccess.engine" in reload_order
    # Leaves (rule modules) must be reloaded before pyaccess.engine, which
    # re-imports them -- otherwise engine would keep referencing stale code.
    assert reload_order.index("pyaccess.rules.access") < reload_order.index("pyaccess.engine")
    assert relint_calls == [True]
def test_rule_watcher_stops_and_skips_relint_when_a_reload_fails(monkeypatch):
    from pyaccess import lsp as lsp_module

    server = create_server(watch_rules=False)
    relint_calls = []
    monkeypatch.setattr(server, "rebuild_and_relint", lambda: relint_calls.append(True))

    def _boom(_mod):
        raise SyntaxError("broken rule file")

    monkeypatch.setattr(lsp_module.importlib, "reload", _boom)

    watcher = lsp_module.RuleWatcher(server, interval=999)
    watcher._reload(["pyaccess.rules.access"])  # must not raise

    assert relint_calls == []  # a broken edit must not blow away working diagnostics
def test_rule_watcher_ignores_blocklisted_modules(tmp_path: Path):
    from pyaccess.lsp import _RELOAD_BLOCKLIST, _watched_pyaccess_source_files

    assert "pyaccess.lsp" in _RELOAD_BLOCKLIST
    assert "pyaccess.lsp" not in _watched_pyaccess_source_files()

