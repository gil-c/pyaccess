"""Directed import graph, built entirely from already-parsed ``ImportRef`` data.

No third-party dependency (e.g. Grimp) is required here: PyAccess's strict
mode already forbids the dynamic constructs that make import resolution
unreliable (PA010-PA012 — non-literal ``getattr``/``import_module``/``__import__``).
Every edge we ever see is therefore a static, literal ``import X`` /
``from X import Y`` — exactly what :mod:`pyaccess.imports` already extracts
via ``ast``. Building a directed graph on top of that is a few dozen lines of
stdlib code, with full control over the data model instead of adapting to a
third-party one.
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable

from pyaccess.imports import ImportRef

# Adjacency map: importing module -> set of modules it imports from.
ImportGraph = dict[str, set[str]]


def build_import_graph(imports: Iterable[ImportRef]) -> ImportGraph:
    """Build a directed module -> module adjacency map from import references.

    An edge ``a -> b`` means "module ``a`` imports from module ``b``".
    Self-imports are dropped. Target modules are also registered as nodes
    (with no outgoing edges) so downstream/upstream queries work on them too.
    """
    graph: ImportGraph = defaultdict(set)
    for imp in imports:
        graph.setdefault(imp.importer, set())
        if imp.importer == imp.from_module:
            continue
        graph[imp.importer].add(imp.from_module)
        graph.setdefault(imp.from_module, set())
    return dict(graph)


def _bfs(adjacency: ImportGraph, start: str) -> set[str]:
    seen: set[str] = set()
    queue: deque[str] = deque(adjacency.get(start, ()))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(adjacency.get(current, ()))
    return seen


def downstream(graph: ImportGraph, module: str) -> set[str]:
    """Return every module transitively imported by ``module``."""
    return _bfs(graph, module)


def upstream(graph: ImportGraph, module: str) -> set[str]:
    """Return every module that transitively depends on ``module``."""
    reverse: ImportGraph = defaultdict(set)
    for src, targets in graph.items():
        for tgt in targets:
            reverse[tgt].add(src)
    return _bfs(dict(reverse), module)


def find_cycles(graph: ImportGraph) -> list[list[str]]:
    """Detect import cycles via DFS with a three-colour recursion stack.

    Returns each distinct cycle once, as the list of modules forming it
    (path order, with the closing module repeated at the end, e.g.
    ``["a", "b", "c", "a"]``).
    """
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(graph, white)
    cycles: list[list[str]] = []
    seen_cycle_keys: set[frozenset[str]] = set()

    def dfs(node: str, path: list[str]) -> None:
        color[node] = gray
        path.append(node)
        for neighbour in sorted(graph.get(node, ())):
            state = color.get(neighbour, white)
            if state == white:
                dfs(neighbour, path)
            elif state == gray:
                idx = path.index(neighbour)
                cycle = path[idx:] + [neighbour]
                key = frozenset(cycle[:-1])
                if key not in seen_cycle_keys:
                    seen_cycle_keys.add(key)
                    cycles.append(cycle)
        path.pop()
        color[node] = black

    for node in sorted(graph):
        if color.get(node, white) == white:
            dfs(node, [])
    return cycles
