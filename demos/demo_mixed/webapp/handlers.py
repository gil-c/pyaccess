"""Web layer.

This file mixes legitimate and illegitimate imports on purpose so the
underlining in PyCharm is obvious side-by-side.
"""
from engine.core import _secret        # PA002 — module-private symbol
from engine.core import helper         # PA001 — package-internal symbol
from engine.core import public_entry   # OK


def handle(request_value: int) -> dict[str, object]:
    return {
        "ok": public_entry(request_value),
        "leaked": helper(request_value),
        "secret": _secret(),
    }

