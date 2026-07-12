"""Cross-package consumer — deliberately illegal on two counts at once.

Open this file (or run ``pyaccess check demos/demo``) to see both
foundational visibility rules fire side by side:

* **PA001** — cross-package import of an ``@internal`` symbol
  (``src/pyaccess/rules/access.py``).
* **PA002** — cross-module import of a ``@private`` symbol
  (``src/pyaccess/rules/private.py``). Private is stricter than internal:
  it fires even though ``_polish`` and this file are unrelated packages,
  same as it would if they were siblings in the same package.
"""
from core_pkg.api import InternalRegistry  # PA001 -- @internal class imported across packages
from core_pkg.api import helper  # PA001 -- @internal function imported across packages
from core_pkg.api import _polish  # PA002 -- @private symbol imported from another module
from core_pkg.api import stable_api  # OK -- @public, no diagnostic


def use(x: int) -> int:
    registry = InternalRegistry()
    registry.add(helper(x))
    return stable_api(x) + _polish(x)
