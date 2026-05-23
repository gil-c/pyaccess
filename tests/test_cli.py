"""CLI smoke tests."""
from pathlib import Path

from pyaccess.cli import main


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_cli_returns_zero_on_clean_project(tmp_path: Path, capsys):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/a.py", "x = 1\n")
    rc = main(["check", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0 issue" in out or "no issues" in out.lower()


def test_cli_returns_nonzero_on_violation(tmp_path: Path, capsys):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "beta/__init__.py", "")
    _write(tmp_path, "beta/user.py", "from alpha.core import helper\n")

    rc = main(["check", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc != 0
    assert "PA001" in out

