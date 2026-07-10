"""Application code — only touches the public surface."""
from library.api import greet


def main() -> None:
    print(greet("world"))

