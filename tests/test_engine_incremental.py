"""Single-file checking API used by the LSP server.

The LSP needs to re-check a single buffer on each keystroke. It would be
wasteful to re-discover and re-parse the whole project every time, so we
expose an incremental entry point: ``check_source`` reuses a pre-built
:class:`ProjectIndex` and re-parses only the file under edit.
"""
from pathlib import Path

from pyaccess.engine import ProjectIndex, build_index, check_source


def _write(root: Path, rel: str, content: str) -> str:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return content


def test_build_index_returns_project_index(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "beta/__init__.py", "")
    _write(tmp_path, "beta/user.py", "from alpha.core import helper\n")

    index = build_index(tmp_path)
    assert isinstance(index, ProjectIndex)
    assert "alpha.core" in index.symbols_by_module
    assert "helper" in index.symbols_by_module["alpha.core"]


def test_check_source_returns_only_diagnostics_for_that_file(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "beta/__init__.py", "")
    user_path = tmp_path / "beta" / "user.py"
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text("from alpha.core import helper\n")

    index = build_index(tmp_path)
    diagnostics = check_source(
        index,
        file_path=user_path,
        source=user_path.read_text(),
    )
    assert all(d.file == user_path for d in diagnostics)
    assert any(d.code == "PA001" for d in diagnostics)


def test_check_source_uses_live_buffer_content(tmp_path: Path):
    """When the user fixes the import in their editor, the diagnostic must
    disappear without writing to disk."""
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "beta/__init__.py", "")
    user_path = tmp_path / "beta" / "user.py"
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text("from alpha.core import helper\n")

    index = build_index(tmp_path)
    # Simulate the user removing the offending import in their buffer.
    diagnostics = check_source(index, file_path=user_path, source="# fixed!\n")
    assert [d for d in diagnostics if d.code == "PA001"] == []

