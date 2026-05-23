"""Smoke tests for the LSP server."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pygls")
pytest.importorskip("lsprotocol")
from pyaccess.diagnostics import Diagnostic as PADiagnostic  # noqa: E402
from pyaccess.lsp import (  # noqa: E402
    _guess_root,
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
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\n")
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    user = tmp_path / "beta" / "user.py"
    user.write_text("from alpha.core import helper\n")
    server = create_server()
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    server.refresh_file(user.as_uri(), source=user.read_text())
    assert len(published) == 1
    uri, diags = published[0]
    assert uri == user.as_uri()
    assert any(d.code == "PA001" for d in diags)
def test_refresh_file_clears_diagnostics_when_buffer_is_fixed(tmp_path: Path, monkeypatch):
    _write(tmp_path, "pyproject.toml", "[project]\nname='demo'\n")
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    user = tmp_path / "beta" / "user.py"
    user.write_text("from alpha.core import helper\n")
    server = create_server()
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    server.refresh_file(user.as_uri(), source="# fixed\n")
    assert published[-1][1] == []
def test_refresh_file_routes_each_demo_to_its_own_index(tmp_path: Path, monkeypatch):
    _write(tmp_path, "pyproject.toml", "[project]\nname='repo'\n")
    for demo in ("demo_a", "demo_b"):
        _write(tmp_path, f"demos/{demo}/pyproject.toml", f"[project]\nname='{demo}'\n")
        _write(tmp_path, f"demos/{demo}/alpha/__init__.py", "")
        _write(tmp_path, f"demos/{demo}/alpha/core.py",
               "from pyaccess import internal\n@internal\ndef helper():\n    pass\n")
        _write(tmp_path, f"demos/{demo}/beta/__init__.py", "")
        _write(tmp_path, f"demos/{demo}/beta/user.py",
               "from alpha.core import helper\n")
    server = create_server()
    published = []
    monkeypatch.setattr(server, "publish",
                        lambda uri, diags: published.append((uri, diags)))
    for demo in ("demo_a", "demo_b"):
        user = tmp_path / "demos" / demo / "beta" / "user.py"
        server.refresh_file(user.as_uri(), source=user.read_text())
    assert len(published) == 2
    for _uri, diags in published:
        assert any(d.code == "PA001" for d in diags)
