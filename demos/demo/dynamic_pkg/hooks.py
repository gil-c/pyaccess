"""PA013 / PA014 — module-level attribute hooks and dynamic metaclasses.

Both constructs let an object's shape change *after* the class/module body
has been parsed, which is exactly what PyAccess statically cannot follow.
"""


def __getattr__(name: str) -> object:  # PA013 -- module-level hook intercepts every lookup on this module
    raise AttributeError(name)


class _Meta(type):
    """A metaclass can rewrite the class body at creation time (add/remove
    members, change bases, ...), which defeats static visibility checks.
    """


class Widget(metaclass=_Meta):  # PA014 -- explicit custom metaclass
    pass
