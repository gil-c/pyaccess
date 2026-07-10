"""Project-wide PyAccess configuration.

Looks for a standalone ``pyaccess.toml`` first, then falls back to a
``[tool.pyaccess]`` table in ``pyproject.toml``. Currently supports a single
setting, per roadmap §4.1:

* ``default_visibility`` — the visibility assumed for a symbol that carries
  no ``@public``/``@internal``/``@private`` decorator at all. ``"public"``
  (the default) suits gradual adoption on an existing codebase; ``"internal"``
  is the stricter setting recommended once a project wants every public API
  surface to be explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _parse_default_visibility(raw: object, *, source: Path) -> Visibility:
    if raw is None:
        return _DEFAULT_VISIBILITY
    if not isinstance(raw, str) or raw not in _VALID_DEFAULTS:
        raise ValueError(
            f"{source}: 'default_visibility' must be one of "
            f"{sorted(_VALID_DEFAULTS)!r}, got {raw!r}."
        )
    return _VALID_DEFAULTS[raw]


def load_config(root: Path) -> PyAccessConfig:
    """Load PyAccess configuration for a project rooted at ``root``.

    Returns defaults (``default_visibility = "public"``) if neither
    ``pyaccess.toml`` nor a ``[tool.pyaccess]`` section in ``pyproject.toml``
    is found, or the key is simply absent.
    """
    root = Path(root)

    standalone = root / "pyaccess.toml"
    if standalone.is_file():
        data = tomllib.loads(standalone.read_text(encoding="utf-8"))
        return PyAccessConfig(
            default_visibility=_parse_default_visibility(
                data.get("default_visibility"), source=standalone
            )
        )

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        tool_section = data.get("tool", {}).get("pyaccess", {})
        return PyAccessConfig(
            default_visibility=_parse_default_visibility(
                tool_section.get("default_visibility"), source=pyproject
            )
        )

    return PyAccessConfig()
