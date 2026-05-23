"""Symbol extraction with visibility from decorators."""
from pyaccess.markers import Visibility
from pyaccess.symbols import collect_symbols


def test_collects_function_with_internal_decorator():
    source = """
from pyaccess import internal, public

@internal
def helper():
    pass

@public
def api():
    pass

def undecorated():
    pass
"""
    syms = {s.name: s for s in collect_symbols(source, module="pkg.mod")}
    assert syms["helper"].visibility is Visibility.INTERNAL
    assert syms["api"].visibility is Visibility.PUBLIC
    assert syms["undecorated"].visibility is None  # default policy applied later
    assert syms["helper"].module == "pkg.mod"
    assert syms["helper"].lineno >= 1


def test_collects_class_and_methods():
    source = """
from pyaccess import internal, private

@internal
class C:
    @private
    def secret(self): ...
    def normal(self): ...
"""
    syms = list(collect_symbols(source, module="pkg.mod"))
    by_qual = {s.qualname: s for s in syms}
    assert by_qual["C"].visibility is Visibility.INTERNAL
    assert by_qual["C"].kind == "class"
    assert by_qual["C.secret"].visibility is Visibility.PRIVATE
    assert by_qual["C.secret"].kind == "method"
    assert by_qual["C.normal"].visibility is None


def test_aliased_decorator_import_is_recognised():
    source = """
from pyaccess import internal as _hidden

@_hidden
def helper(): ...
"""
    syms = {s.name: s for s in collect_symbols(source, module="pkg.mod")}
    assert syms["helper"].visibility is Visibility.INTERNAL


def test_syntax_error_yields_no_symbols_but_does_not_raise():
    source = "def broken(:\n"
    assert list(collect_symbols(source, module="pkg.mod")) == []

