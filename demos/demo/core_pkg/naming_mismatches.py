"""**PA003** — explicit visibility annotation vs. leading-underscore naming.

Long before ``@public``/``@internal`` existed, a leading underscore already
meant "not part of the public API". When both signals are present and
disagree, PyAccess flags it — see ``src/pyaccess/rules/naming.py``.
"""
from typing import Annotated

from pyaccess import internal, public
from pyaccess.markers import Internal, Public


@public
def _looks_hidden_but_is_public():
    """PA003 (error): the underscore says "hidden", @public says the
    opposite — the contradiction most likely to leak something by
    accident.
    """


@internal
def looks_public_but_is_internal():
    """PA003 (warning): no leading underscore, so this reads like public
    API even though @internal restricts it to this package. Softer than
    the error above, since @internal is allowed to override naming
    convention on purpose.
    """


@internal  # pyaccess: ignore[PA003]
def deliberately_unprefixed():
    """Same shape as ``looks_public_but_is_internal`` above, but here the
    mismatch is intentional and silenced with the generic inline
    suppression comment instead of renaming the function.
    """


# PA003 (error) via `Annotated[T, Public]` metadata instead of a decorator —
# the same check applies to module/class attributes, which can't carry a
# decorator.
_hidden_constant: Annotated[int, Public] = 1

# PA003 (warning) via `Annotated[T, Internal]` metadata: no leading
# underscore on a symbol restricted to this package.
shared_constant: Annotated[int, Internal] = 2
