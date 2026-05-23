"""End-to-end test of the access rule via the engine."""
from pathlib import Path

from pyaccess.engine import check_project


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_cross_package_import_of_internal_is_flagged(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "beta/__init__.py", "")
    _write(tmp_path, "beta/user.py", "from alpha.core import helper\n")

    diagnostics = check_project(tmp_path)

    codes = [d.code for d in diagnostics]
    assert "PA001" in codes
    msg = next(d for d in diagnostics if d.code == "PA001")
    assert "helper" in msg.message
    assert "alpha.core" in msg.message
    assert msg.file.name == "user.py"
    assert msg.line >= 1


def test_same_package_import_of_internal_is_allowed(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "alpha/user.py", "from alpha.core import helper\n")

    diagnostics = check_project(tmp_path)
    assert [d for d in diagnostics if d.code == "PA001"] == []


def test_public_symbol_is_importable_cross_package(tmp_path: Path):
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import public\n@public\ndef api():\n    pass\n",
    )
    _write(tmp_path, "beta/__init__.py", "")
    _write(tmp_path, "beta/user.py", "from alpha.core import api\n")

    diagnostics = check_project(tmp_path)
    assert [d for d in diagnostics if d.code == "PA001"] == []


def test_subpackage_is_considered_same_package_root(tmp_path: Path):
    # alpha.sub.* should be able to import alpha.core internals: same top-level package.
    _write(tmp_path, "alpha/__init__.py", "")
    _write(
        tmp_path,
        "alpha/core.py",
        "from pyaccess import internal\n@internal\ndef helper():\n    pass\n",
    )
    _write(tmp_path, "alpha/sub/__init__.py", "")
    _write(tmp_path, "alpha/sub/user.py", "from alpha.core import helper\n")

    diagnostics = check_project(tmp_path)
    assert [d for d in diagnostics if d.code == "PA001"] == []


def test_unknown_external_symbol_is_ignored(tmp_path: Path):
    # Importing from a module outside the project must not crash or produce noise.
    _write(tmp_path, "alpha/__init__.py", "")
    _write(tmp_path, "alpha/user.py", "import os\nfrom collections import OrderedDict\n")

    diagnostics = check_project(tmp_path)
    assert diagnostics == []

