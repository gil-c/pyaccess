"""Cross-package consumer.

The two imports below cross a top-level package boundary while pulling in
``@internal`` symbols. PyAccess flags each of them with PA001.
"""
from core_pkg.api import InternalRegistry  # PA001 — internal class
from core_pkg.api import helper            # PA001 — internal function
from core_pkg.api import stable_api        # OK — @public symbol


def use() -> int:
    reg = InternalRegistry()
    reg.add(helper(stable_api(1)))
    return 0

