"""Map files to dotted module names relative to a project root."""
from pathlib import Path

from pyaccess.modules import module_name_for, package_of


def test_module_name_for_regular_file(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "a.py").write_text("")
    assert module_name_for(tmp_path / "pkg" / "a.py", tmp_path) == "pkg.a"


def test_module_name_for_init(tmp_path: Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    assert module_name_for(tmp_path / "pkg" / "__init__.py", tmp_path) == "pkg"


def test_module_name_for_nested(tmp_path: Path):
    (tmp_path / "pkg" / "sub").mkdir(parents=True)
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "sub" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "sub" / "b.py").write_text("")
    assert module_name_for(tmp_path / "pkg" / "sub" / "b.py", tmp_path) == "pkg.sub.b"


def test_package_of():
    assert package_of("pkg.a") == "pkg"
    assert package_of("pkg.sub.b") == "pkg.sub"
    assert package_of("pkg") == "pkg"
    assert package_of("toplevel") == "toplevel"


def test_top_level_package():
    # Top-level package is its own root.
    assert package_of("pkg") == "pkg"

