"""Same-package consumer — both imports below are LEGAL."""
from engine.core import helper, public_entry


def run(x: int) -> int:
    return helper(public_entry(x))

