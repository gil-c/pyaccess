"""Tests for project configuration (pyaccess.config)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pyaccess.config import load_config
from pyaccess.markers import Visibility


def test_defaults_when_no_config_file_present(tmp_path: Path):
    config = load_config(tmp_path)
    assert config.default_visibility is Visibility.PUBLIC


def test_standalone_pyaccess_toml_sets_default_visibility(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('default_visibility = "internal"\n')
    config = load_config(tmp_path)
    assert config.default_visibility is Visibility.INTERNAL


def test_pyproject_tool_section_sets_default_visibility(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyaccess]\ndefault_visibility = \"internal\"\n"
    )
    config = load_config(tmp_path)
    assert config.default_visibility is Visibility.INTERNAL


def test_standalone_toml_takes_precedence_over_pyproject(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('default_visibility = "internal"\n')
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyaccess]\ndefault_visibility = \"public\"\n"
    )
    config = load_config(tmp_path)
    assert config.default_visibility is Visibility.INTERNAL


def test_pyproject_without_pyaccess_section_uses_defaults(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    config = load_config(tmp_path)
    assert config.default_visibility is Visibility.PUBLIC


def test_invalid_default_visibility_value_raises(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('default_visibility = "protected"\n')
    with pytest.raises(ValueError, match="default_visibility"):
        load_config(tmp_path)


def test_missing_default_visibility_key_uses_defaults(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('some_other_key = 1\n')
    config = load_config(tmp_path)
    assert config.default_visibility is Visibility.PUBLIC


def test_defaults_have_empty_roots_and_disabled_rules(tmp_path: Path):
    config = load_config(tmp_path)
    assert config.roots == ()
    assert config.disabled_rules == frozenset()


def test_standalone_pyaccess_toml_sets_roots_and_disabled_rules(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text(
        'roots = ["src.pkgA", "src.pkgB"]\n'
        'disabled_rules = ["PA010", "PA011"]\n'
    )
    config = load_config(tmp_path)
    assert config.roots == ("src.pkgA", "src.pkgB")
    assert config.disabled_rules == frozenset({"PA010", "PA011"})


def test_pyproject_tool_section_sets_roots_and_disabled_rules(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyaccess]\n"
        'roots = ["alpha", "beta"]\n'
        'disabled_rules = ["PA002"]\n'
    )
    config = load_config(tmp_path)
    assert config.roots == ("alpha", "beta")
    assert config.disabled_rules == frozenset({"PA002"})


def test_standalone_toml_roots_take_precedence_over_pyproject(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('roots = ["a"]\n')
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyaccess]\nroots = [\"b\"]\n"
    )
    config = load_config(tmp_path)
    assert config.roots == ("a",)


def test_invalid_roots_type_raises(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('roots = "not-a-list"\n')
    with pytest.raises(ValueError, match="roots"):
        load_config(tmp_path)


def test_invalid_roots_element_type_raises(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('roots = ["ok", 1]\n')
    with pytest.raises(ValueError, match="roots"):
        load_config(tmp_path)


def test_invalid_disabled_rules_type_raises(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('disabled_rules = 42\n')
    with pytest.raises(ValueError, match="disabled_rules"):
        load_config(tmp_path)
