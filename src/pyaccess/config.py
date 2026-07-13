"""Project-wide PyAccess configuration.

Looks for a standalone ``pyaccess.toml`` first, then falls back to a
``[tool.pyaccess]`` table in ``pyproject.toml``. Currently supports a single
setting, per roadmap §4.1:

* ``default_visibility`` — the visibility assumed for a symbol that carries
  no ``@public``/``@internal``/``@private`` decorator at all. ``"public"``
  (the default) suits gradual adoption on an existing codebase; ``"internal"``
  is the stricter setting recommended once a project wants every public API
  surface to be explicit.
* ``roots`` — explicit dotted-prefix list of the top-level package
  boundaries used by PA001. Overrides the default heuristic (first dotted
  segment of the module name), which collapses when the analysis root isn't
  the direct parent of the packages (e.g. a ``src/`` layout or a monorepo
  scanned from its top).
* ``disabled_rules`` — rule codes (e.g. ``"PA010"``) to skip entirely.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python >= 3.11 (stdlib)
except ModuleNotFoundError:  # pragma: no cover - only exercised on Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from pyaccess.markers import Visibility

_DEFAULT_VISIBILITY = Visibility.PUBLIC
_VALID_DEFAULTS = {"public": Visibility.PUBLIC, "internal": Visibility.INTERNAL}


@dataclass(frozen=True)
class PyAccessConfig:
    default_visibility: Visibility = _DEFAULT_VISIBILITY
    roots: tuple[str, ...] = ()
    disabled_rules: frozenset[str] = field(default_factory=frozenset)


def _parse_default_visibility(raw: object, *, source: Path) -> Visibility:
    if raw is None:
        return _DEFAULT_VISIBILITY
    if not isinstance(raw, str) or raw not in _VALID_DEFAULTS:
        raise ValueError(
            f"{source}: 'default_visibility' must be one of "
            f"{sorted(_VALID_DEFAULTS)!r}, got {raw!r}."
        )
    return _VALID_DEFAULTS[raw]


def _parse_str_list(raw: object, *, key: str, source: Path) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(v, str) for v in raw):
        raise ValueError(f"{source}: '{key}' must be a list of strings, got {raw!r}.")
    return tuple(raw)


def _config_from_mapping(data: dict, *, source: Path) -> PyAccessConfig:
    return PyAccessConfig(
        default_visibility=_parse_default_visibility(
            data.get("default_visibility"), source=source
        ),
        roots=_parse_str_list(data.get("roots"), key="roots", source=source),
        disabled_rules=frozenset(
            _parse_str_list(data.get("disabled_rules"), key="disabled_rules", source=source)
        ),
    )


def load_config(root: Path) -> PyAccessConfig:
    """Load PyAccess configuration for a project rooted at ``root``.

    Returns defaults if neither ``pyaccess.toml`` nor a ``[tool.pyaccess]``
    section in ``pyproject.toml`` is found, or a key is simply absent.
    """
    root = Path(root)

    standalone = root / "pyaccess.toml"
    if standalone.is_file():
        data = tomllib.loads(standalone.read_text(encoding="utf-8"))
        return _config_from_mapping(data, source=standalone)

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        tool_section = data.get("tool", {}).get("pyaccess", {})
        return _config_from_mapping(tool_section, source=pyproject)

    return PyAccessConfig()
