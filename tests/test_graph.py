"""Tests for the homemade import graph (pyaccess.graph)."""
from __future__ import annotations

from pyaccess.graph import build_import_graph, downstream, find_cycles, upstream
from pyaccess.imports import ImportRef


def _ref(importer: str, from_module: str, imported_name: str | None = "x") -> ImportRef:
    return ImportRef(
        importer=importer,
        from_module=from_module,
        imported_name=imported_name,
        alias=None,
        lineno=1,
        col_offset=0,
    )


def test_build_import_graph_basic_edges():
    imports = [_ref("app.main", "app.core"), _ref("app.core", "app.utils")]
    graph = build_import_graph(imports)
    assert graph["app.main"] == {"app.core"}
    assert graph["app.core"] == {"app.utils"}
    assert graph["app.utils"] == set()  # leaf node registered even with no outgoing edges


def test_build_import_graph_drops_self_import():
    imports = [_ref("pkg.mod", "pkg.mod")]
    graph = build_import_graph(imports)
    assert graph["pkg.mod"] == set()


def test_downstream_is_transitive():
    imports = [_ref("a", "b"), _ref("b", "c"), _ref("c", "d")]
    graph = build_import_graph(imports)
    assert downstream(graph, "a") == {"b", "c", "d"}
    assert downstream(graph, "c") == {"d"}
    assert downstream(graph, "d") == set()


def test_upstream_is_transitive():
    imports = [_ref("a", "b"), _ref("b", "c"), _ref("c", "d")]
    graph = build_import_graph(imports)
    assert upstream(graph, "d") == {"a", "b", "c"}
    assert upstream(graph, "b") == {"a"}
    assert upstream(graph, "a") == set()


def test_find_cycles_detects_simple_cycle():
    imports = [_ref("a", "b"), _ref("b", "c"), _ref("c", "a")]
    graph = build_import_graph(imports)
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    cycle = cycles[0]
    assert cycle[0] == cycle[-1]
    assert set(cycle[:-1]) == {"a", "b", "c"}


def test_find_cycles_no_cycle_in_dag():
    imports = [_ref("a", "b"), _ref("a", "c"), _ref("b", "d"), _ref("c", "d")]
    graph = build_import_graph(imports)
    assert find_cycles(graph) == []


def test_find_cycles_self_import_is_not_a_cycle():
    # Self-imports are dropped by build_import_graph, so they never surface
    # as cycles here (a real self-import is nonsensical Python anyway).
    imports = [_ref("a", "a")]
    graph = build_import_graph(imports)
    assert find_cycles(graph) == []
