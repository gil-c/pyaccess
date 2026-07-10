"""Engine core."""
from pyaccess import internal, private, public


@public
def public_entry(x: int) -> int:
    return helper(x) + 10


@internal
def helper(x: int) -> int:
    """Visible inside the ``engine`` package only."""
    return x * 3


@private
def _secret() -> str:
    """Visible only from within this module."""
    return "shhh"

