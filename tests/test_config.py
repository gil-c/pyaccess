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
