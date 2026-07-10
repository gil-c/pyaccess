"""Same-package consumer: importing internals is fine here."""
from library.api import _polish, greet


def main() -> str:
    return greet(_polish("  alice "))

