"""Minimal CLI: ``pyaccess check <path>``."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from pyaccess.config import load_config, merge_cli_overrides
from pyaccess.diagnostics import Diagnostic
from pyaccess.engine import check_project


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pyaccess", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check a project for accessibility violations.")
    check.add_argument("path", type=Path, help="Project root to analyse.")
    check.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    check.add_argument(
        "--disable",
        metavar="RULE",
        action="append",
        default=[],
        help="Disable a rule for this run (e.g. --disable PA014). Repeatable.",
    )
    check.add_argument(
        "--default-visibility",
        choices=("public", "internal"),
        default=None,
        help="Override default_visibility for this run.",
    )
    check.add_argument(
        "--root",
        metavar="PKG",
        action="append",
        default=None,
        dest="roots",
        help="Override top-level package roots (e.g. --root src.pkgA). Repeatable.",
    )
    return parser


def _to_json(diagnostics: list[Diagnostic]) -> str:
    payload = [
        {
            "code": d.code,
            "severity": d.severity,
            "message": d.message,
            "file": str(d.file),
            "line": d.line,
            "column": d.column,
        }
        for d in diagnostics
    ]
    return json.dumps(payload, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "check":
        base_config = load_config(args.path)
        config = merge_cli_overrides(
            base_config,
            default_visibility=args.default_visibility,
            roots=args.roots,
            disable=args.disable,
        )
        diagnostics = check_project(args.path, config=config)
        if args.format == "json":
            print(_to_json(diagnostics))
        else:
            for diag in diagnostics:
                print(diag.format())
            if not diagnostics:
                print("pyaccess: 0 issue found.")
            else:
                print(f"pyaccess: {len(diagnostics)} issue(s) found.")
        return 0 if not diagnostics else 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


