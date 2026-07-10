"""Another module in the same package.

Pulling ``_token`` here is illegal, even though we sit in the same package:
``@private`` is *module*-scoped, not package-scoped.
"""
from mypkg.secrets import _token             # PA002 — private symbol
from mypkg.secrets import public_token_hash  # OK — @public symbol


def leak() -> str:
    return _token()


def correct_usage() -> int:
    return public_token_hash()

