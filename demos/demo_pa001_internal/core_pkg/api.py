"""Core package public surface and internals."""
from pyaccess import internal, public


@public
def stable_api(x: int) -> int:
    """Anyone may call this."""
    return x * 2


@internal
def helper(x: int) -> int:
    """Implementation detail of `core_pkg` — do not import from outside."""
    return x + 1


@internal
class InternalRegistry:
    """Internal storage used by `core_pkg.sibling`."""

    def __init__(self) -> None:
        self._items: list[int] = []

    def add(self, item: int) -> None:
        self._items.append(item)

