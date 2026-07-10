"""Same-package consumer — these imports are LEGAL."""
from core_pkg.api import InternalRegistry, helper, stable_api


def run() -> int:
    reg = InternalRegistry()
    reg.add(helper(stable_api(3)))
    return 0

