"""Module owning a strictly private helper."""
from pyaccess import private, public


@private
def _token() -> str:
    """Module-private — must not leak outside ``mypkg.secrets``."""
    return "s3cr3t"


@public
def public_token_hash() -> int:
    """Public façade — this is the legitimate way to obtain a derived value."""
    return hash(_token())

