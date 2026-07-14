"""Tests for project configuration (pyaccess.config)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pyaccess.config import load_config, merge_cli_overrides
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


# ---------------------------------------------------------------------------
# merge_cli_overrides
# ---------------------------------------------------------------------------

def test_merge_no_overrides_returns_same_values(tmp_path: Path):
    base = load_config(tmp_path)
    merged = merge_cli_overrides(base)
    assert merged == base


def test_merge_overrides_default_visibility(tmp_path: Path):
    base = load_config(tmp_path)  # default = PUBLIC
    merged = merge_cli_overrides(base, default_visibility="internal")
    assert merged.default_visibility is Visibility.INTERNAL


def test_merge_default_visibility_invalid_raises(tmp_path: Path):
    base = load_config(tmp_path)
    with pytest.raises(ValueError, match="--default-visibility"):
        merge_cli_overrides(base, default_visibility="protected")


def test_merge_overrides_roots(tmp_path: Path):
    base = load_config(tmp_path)
    merged = merge_cli_overrides(base, roots=["src.pkgA", "src.pkgB"])
    assert merged.roots == ("src.pkgA", "src.pkgB")


def test_merge_disable_accumulates_on_top_of_file_config(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('disabled_rules = ["PA010"]\n')
    base = load_config(tmp_path)
    merged = merge_cli_overrides(base, disable=["PA014"])
    assert merged.disabled_rules == frozenset({"PA010", "PA014"})


def test_merge_disable_empty_list_does_not_override(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('disabled_rules = ["PA010"]\n')
    base = load_config(tmp_path)
    merged = merge_cli_overrides(base, disable=[])
    assert merged.disabled_rules == frozenset({"PA010"})


def test_merge_file_visibility_preserved_when_no_cli_override(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('default_visibility = "internal"\n')
    base = load_config(tmp_path)
    merged = merge_cli_overrides(base)
    assert merged.default_visibility is Visibility.INTERNAL
