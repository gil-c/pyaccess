"""Tests for per-rule documentation and the `pyaccess explain` CLI command (Phase A)."""
from __future__ import annotations

import pytest

from pyaccess.cli import main
from pyaccess.docs import ALL_RULES, get_rule, list_rules

# ---------------------------------------------------------------------------
# docs.py unit tests
# ---------------------------------------------------------------------------

ALL_CODES = [
    "PA001", "PA002", "PA003",
    "PA010", "PA011", "PA012", "PA013", "PA014", "PA015", "PA016", "PA017", "PA018",
]


def test_all_rules_present():
    codes = {r.code for r in list_rules()}
    for code in ALL_CODES:
        assert code in codes, f"{code} missing from docs"


def test_all_rules_count():
    assert len(ALL_RULES) == 12


def test_get_rule_returns_correct_doc():
    rule = get_rule("PA001")
    assert rule is not None
    assert rule.code == "PA001"
    assert "internal" in rule.title.lower()


def test_get_rule_case_insensitive():
    assert get_rule("pa001") is not None
    assert get_rule("PA001") is not None


def test_get_rule_unknown_returns_none():
    assert get_rule("PA999") is None
    assert get_rule("") is None


@pytest.mark.parametrize("code", ALL_CODES)
def test_rule_fields_non_empty(code: str):
    rule = get_rule(code)
    assert rule is not None
    assert rule.title.strip()
    assert rule.what.strip()
    assert rule.why.strip()
    assert rule.example_bad.strip()
    assert rule.example_good.strip()
    assert rule.escape.strip()
    assert rule.severity in {"error", "warning", "hint"}


@pytest.mark.parametrize("code", ALL_CODES)
def test_rule_render_contains_code(code: str):
    rule = get_rule(code)
    assert rule is not None
    rendered = rule.render()
    assert code in rendered
    assert rule.title in rendered
    assert rule.severity in rendered


def test_pa017_default_severity_is_warning():
    """PA017 is a warning by default (monkey-patching, less severe than hard violations)."""
    assert get_rule("PA017").severity == "warning"


def test_pa001_pa002_pa003_are_errors():
    for code in ("PA001", "PA002", "PA003"):
        assert get_rule(code).severity == "error", f"{code} should default to error"


# ---------------------------------------------------------------------------
# CLI: pyaccess explain
# ---------------------------------------------------------------------------


def test_explain_single_rule_exits_zero(capsys):
    rc = main(["explain", "PA001"])
    assert rc == 0


def test_explain_single_rule_outputs_doc(capsys):
    main(["explain", "PA017"])
    out = capsys.readouterr().out
    assert "PA017" in out
    assert "monkey" in out.lower()
    assert "warning" in out


def test_explain_all_rules_exits_zero(capsys):
    rc = main(["explain"])
    assert rc == 0


def test_explain_all_lists_all_codes(capsys):
    main(["explain"])
    out = capsys.readouterr().out
    for code in ALL_CODES:
        assert code in out, f"{code} missing from explain output"


def test_explain_all_shows_rule_count(capsys):
    main(["explain"])
    out = capsys.readouterr().out
    assert "12 rules" in out


def test_explain_unknown_code_exits_2(capsys):
    rc = main(["explain", "PA999"])
    assert rc == 2


def test_explain_unknown_code_suggests_list(capsys):
    main(["explain", "PA999"])
    err = capsys.readouterr().err
    assert "explain" in err.lower()


def test_explain_pa003_both_sub_cases_documented(capsys):
    main(["explain", "PA003"])
    out = capsys.readouterr().out
    assert "warning" in out.lower()
    assert "error" in out.lower()
