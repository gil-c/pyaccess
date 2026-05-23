"""Import extraction from a Python source."""
from pyaccess.imports import collect_imports


def test_from_import_simple():
    source = "from pkg.other import helper, api\n"
    imps = collect_imports(source, module="pkg.mod")
    pairs = {(i.from_module, i.imported_name) for i in imps}
    assert pairs == {("pkg.other", "helper"), ("pkg.other", "api")}
    assert all(i.importer == "pkg.mod" for i in imps)


def test_plain_import_does_not_resolve_a_named_symbol():
    # `import pkg.other` imports a module, not a named symbol — for the POC
    # we expose it with imported_name=None so rules can ignore it.
    source = "import pkg.other\n"
    imps = collect_imports(source, module="pkg.mod")
    assert len(imps) == 1
    assert imps[0].from_module == "pkg.other"
    assert imps[0].imported_name is None


def test_relative_import_is_resolved_against_current_module():
    source = "from .sibling import thing\n"
    imps = collect_imports(source, module="pkg.mod")
    assert len(imps) == 1
    assert imps[0].from_module == "pkg.sibling"
    assert imps[0].imported_name == "thing"


def test_relative_import_two_dots():
    source = "from ..other import x\n"
    imps = collect_imports(source, module="pkg.sub.mod")
    assert imps[0].from_module == "pkg.other"


def test_aliased_import_keeps_original_name():
    source = "from pkg.other import helper as h\n"
    imps = collect_imports(source, module="pkg.mod")
    assert imps[0].imported_name == "helper"
    assert imps[0].alias == "h"


def test_syntax_error_returns_empty():
    assert collect_imports("from x import (", module="m") == []


def test_col_offset_points_at_imported_name_not_from_keyword():
    """Editors underline ``range start..end``; we want it on the symbol name."""
    source = "from pkg.other import helper\n"
    imps = collect_imports(source, module="pkg.mod")
    assert imps[0].col_offset == source.index("helper")


def test_col_offset_per_name_in_multi_import():
    source = "from pkg.other import helper, api\n"
    imps = collect_imports(source, module="pkg.mod")
    by_name = {i.imported_name: i.col_offset for i in imps}
    assert by_name["helper"] == source.index("helper")
    assert by_name["api"] == source.index("api")


