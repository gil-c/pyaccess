"""Tests for per-rule severity configuration (Phase A — D6)."""
from __future__ import annotations

from pathlib import Path

import pytest

from pyaccess.config import PyAccessConfig, load_config
from pyaccess.engine import check_project

# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


def test_defaults_have_empty_severity(tmp_path: Path):
    config = load_config(tmp_path)
    assert config.severity == {}


def test_severity_parsed_from_pyaccess_toml(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text(
        "[severity]\n"
        'PA017 = "warning"\n'
        'PA003 = "hint"\n'
    )
    config = load_config(tmp_path)
    assert config.severity == {"PA017": "warning", "PA003": "hint"}


def test_severity_parsed_from_pyproject_toml(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyaccess.severity]\n"
        'PA011 = "warning"\n'
    )
    config = load_config(tmp_path)
    assert config.severity == {"PA011": "warning"}


def test_severity_none_is_valid(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('[severity]\nPA010 = "none"\n')
    config = load_config(tmp_path)
    assert config.severity == {"PA010": "none"}


def test_severity_invalid_level_raises(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('[severity]\nPA010 = "critical"\n')
    with pytest.raises(ValueError, match="severity"):
        load_config(tmp_path)


def test_severity_not_a_table_raises(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text('severity = ["PA010"]\n')
    with pytest.raises(ValueError, match="severity"):
        load_config(tmp_path)


def test_severity_all_valid_levels(tmp_path: Path):
    (tmp_path / "pyaccess.toml").write_text(
        "[severity]\n"
        'PA010 = "error"\n'
        'PA011 = "warning"\n'
        'PA012 = "hint"\n'
        'PA013 = "none"\n'
    )
    config = load_config(tmp_path)
    assert config.severity == {
        "PA010": "error",
        "PA011": "warning",
        "PA012": "hint",
        "PA013": "none",
    }


# ---------------------------------------------------------------------------
# Engine: severity overrides applied to diagnostics
# ---------------------------------------------------------------------------


def _make_project(tmp_path: Path, src: str) -> Path:
    """Minimal project with a single module that triggers PA003."""
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(src)
    return tmp_path


def test_severity_override_changes_diagnostic_severity(tmp_path: Path):
    """PA003 is 'warning' by default for @internal on non-underscore name.
    Overriding it to 'error' should be reflected on the diagnostic."""
    _make_project(
        tmp_path,
        "from pyaccess import internal\n\n@internal\ndef my_func(): pass\n",
    )
    config = PyAccessConfig(severity={"PA003": "error"})
    diags = check_project(tmp_path, config=config)
    pa003 = [d for d in diags if d.code == "PA003"]
    assert pa003, "Expected at least one PA003 diagnostic"
    assert all(d.severity == "error" for d in pa003)


def test_severity_override_hint(tmp_path: Path):
    _make_project(
        tmp_path,
        "from pyaccess import internal\n\n@internal\ndef my_func(): pass\n",
    )
    config = PyAccessConfig(severity={"PA003": "hint"})
    diags = check_project(tmp_path, config=config)
    pa003 = [d for d in diags if d.code == "PA003"]
    assert pa003
    assert all(d.severity == "hint" for d in pa003)


def test_severity_none_silences_rule(tmp_path: Path):
    """severity = 'none' should suppress diagnostics for that rule entirely."""
    _make_project(
        tmp_path,
        "from pyaccess import internal\n\n@internal\ndef my_func(): pass\n",
    )
    config = PyAccessConfig(severity={"PA003": "none"})
    diags = check_project(tmp_path, config=config)
    assert not any(d.code == "PA003" for d in diags)


def test_severity_none_equivalent_to_disabled_rules(tmp_path: Path):
    """Both severity='none' and disabled_rules should produce identical results."""
    src = "from pyaccess import internal\n\n@internal\ndef my_func(): pass\n"
    _make_project(tmp_path, src)

    via_severity = check_project(tmp_path, config=PyAccessConfig(severity={"PA003": "none"}))
    via_disabled = check_project(tmp_path, config=PyAccessConfig(disabled_rules=frozenset({"PA003"})))

    codes_sev = {d.code for d in via_severity}
    codes_dis = {d.code for d in via_disabled}
    assert codes_sev == codes_dis


def test_severity_override_loaded_from_config_file(tmp_path: Path):
    """End-to-end: severity override from pyaccess.toml reaches diagnostics."""
    _make_project(
        tmp_path,
        "from pyaccess import internal\n\n@internal\ndef my_func(): pass\n",
    )
    (tmp_path / "pyaccess.toml").write_text('[severity]\nPA003 = "hint"\n')
    diags = check_project(tmp_path)  # loads config from disk
    pa003 = [d for d in diags if d.code == "PA003"]
    assert pa003
    assert all(d.severity == "hint" for d in pa003)


def test_unoverridden_rules_keep_default_severity(tmp_path: Path):
    """Rules not listed in severity keep their built-in default."""
    _make_project(
        tmp_path,
        "from pyaccess import internal\n\n@internal\ndef my_func(): pass\n",
    )
    config = PyAccessConfig(severity={"PA001": "warning"})  # PA003 not overridden
    diags = check_project(tmp_path, config=config)
    pa003 = [d for d in diags if d.code == "PA003"]
    assert pa003
    # PA003 default severity for @internal-without-underscore is "warning"
    assert all(d.severity == "warning" for d in pa003)
