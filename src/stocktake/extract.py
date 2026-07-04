"""Layer 1: code edges.

Variable dependencies extracted from the AST of the simulation source.
Every assignment (Assign, AnnAssign, AugAssign) yields target <- dependency
edges. Extraction is deliberately conservative: a missed dependency is a
false negative that surfaces as a loud audit failure downstream and is
fixed by a mapping entry; a phantom dependency would be a silent false
witness and is not acceptable.

Known blind spots (kept until hardened, with tests marking them):
- dependencies inside bare `return` expressions are not captured; the
  working convention is to map the function name itself as a variable
- attribute prefixes (self.X, dyn.X) need explicit mapping entries
- code in feature-flag branches audits like baseline code

Ported from technology-fields experiment/cld/extract_dynamic_cld.py.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class Edge:
    """A directed dependency edge, source -> target."""

    source: str
    target: str


def _node_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = _node_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
        return node.attr

    if isinstance(node, ast.Subscript):
        return _node_name(node.value)

    if isinstance(node, ast.Call):
        return _node_name(node.func)

    if isinstance(node, ast.Tuple):
        return None

    return None


def _target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}

    if isinstance(node, ast.Tuple):
        names: set[str] = set()
        for element in node.elts:
            names |= _target_names(element)
        return names

    if isinstance(node, ast.Subscript):
        base = _node_name(node.value)
        return {base} if base else set()

    if isinstance(node, ast.Attribute):
        name = _node_name(node)
        return {name} if name else set()

    return set()


def _dependency_names(node: ast.AST) -> set[str]:
    names: set[str] = set()

    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            name = _node_name(child)
            if name:
                names.add(name)
        elif isinstance(child, ast.Subscript):
            name = _node_name(child.value)
            if name:
                names.add(name)

    return names


def extract_code_edges(
    source: str | Path,
    aliases: dict[str, str] | None = None,
) -> list[Edge]:
    """Extract deduplicated, sorted dependency edges from a Python file.

    `aliases` renames extracted identifiers before edges are formed; an
    alias mapping to the empty string drops the identifier (used for
    module prefixes like `np` and `math`).
    """
    aliases = aliases or {}

    def normalise(name: str) -> str:
        return aliases.get(name, name)

    tree = ast.parse(Path(source).read_text(encoding="utf-8"))
    edges: set[Edge] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: set[str] = set()
            for target in node.targets:
                targets |= _target_names(target)
            deps = _dependency_names(node.value)

        elif isinstance(node, ast.AnnAssign):
            targets = _target_names(node.target)
            deps = _dependency_names(node.value) if node.value else set()

        elif isinstance(node, ast.AugAssign):
            targets = _target_names(node.target)
            deps = _dependency_names(node.value)
            deps |= targets

        else:
            continue

        targets = {normalise(t) for t in targets}
        targets.discard("")
        deps = {normalise(d) for d in deps}
        deps.discard("")
        deps -= targets

        for target in targets:
            for dep in deps:
                edges.add(Edge(source=dep, target=target))

    return sorted(edges)
