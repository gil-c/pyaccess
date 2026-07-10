"""Public API of the library."""
from pyaccess import internal, public


@public
def greet(name: str) -> str:
    return f"hello, {_polish(name)}!"


@internal
def _polish(name: str) -> str:
    return name.strip().title()

