"""Integration tests: inline ``# pyaccess: ignore`` suppression and PA003
wired through :func:`pyaccess.engine.check_project` / :func:`check_source`.
"""
from __future__ import annotations

from pathlib import Path

from pyaccess.engine import build_index, check_project, check_source


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_inline_ignore_suppresses_cross_file_pa001(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef _helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    _write(tmp_path, "beta/user.py",
           "from alpha.core import _helper  # pyaccess: ignore[PA001]\n")
    assert check_project(tmp_path) == []
def test_inline_ignore_does_not_suppress_other_codes(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/core.py",
           "from pyaccess import internal\n@internal\ndef _helper():\n    pass\n")
    _write(tmp_path, "beta/__init__.py", "")
    _write(tmp_path, "beta/user.py",
           "from alpha.core import _helper  # pyaccess: ignore[PA002]\n")
    diagnostics = check_project(tmp_path)
    assert any(d.code == "PA001" for d in diagnostics)
def test_bare_inline_ignore_suppresses_pa003(tmp_path: Path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py",
           "from pyaccess import public\n\n@public  # pyaccess: ignore\ndef _secret():\n    pass\n")
    diagnostics = check_project(tmp_path)
    assert not any(d.code == "PA003" for d in diagnostics)
def test_check_project_reports_pa003_by_default(tmp_path: Path):
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py",
           "from pyaccess import public\n\n@public\ndef _secret():\n    pass\n")
    diagnostics = check_project(tmp_path)
    assert any(d.code == "PA003" for d in diagnostics)
def test_disabled_rules_can_turn_off_pa003(tmp_path: Path):
    _write(tmp_path, "pyaccess.toml", 'disabled_rules = ["PA003"]\n')
    _write(tmp_path, "pkg/__init__.py", "")
    _write(tmp_path, "pkg/mod.py",
           "from pyaccess import public\n\n@public\ndef _secret():\n    pass\n")
    diagnostics = check_project(tmp_path)
    assert not any(d.code == "PA003" for d in diagnostics)


def test_check_source_respects_inline_ignore_on_live_buffer(tmp_path: Path):
    _write(tmp_path, "pkg/__init__.py", "")
    mod = tmp_path / "pkg" / "mod.py"
    mod.write_text("from pyaccess import public\n\n@public\ndef _secret():\n    pass\n")
    index = build_index(tmp_path)
    live_source = (
        "from pyaccess import public\n\n@public  # pyaccess: ignore[PA003]\ndef _secret():\n    pass\n"
    )
    diagnostics = check_source(index, mod, source=live_source)
    assert not any(d.code == "PA003" for d in diagnostics)
def test_check_source_updates_sources_by_module_for_suppression(tmp_path: Path):
    _write(tmp_path, "pkg/__init__.py", "")
    mod = tmp_path / "pkg" / "mod.py"
    mod.write_text("from pyaccess import public\n\n@public\ndef _secret():\n    pass\n")
    index = build_index(tmp_path)
    assert any(d.code == "PA003" for d in check_source(index, mod, source=mod.read_text()))
    live_source = (
        "from pyaccess import public\n\n@public  # pyaccess: ignore[PA003]\ndef _secret():\n    pass\n"
    )
    check_source(index, mod, source=live_source)
    assert index.sources_by_module["pkg.mod"] == live_source
