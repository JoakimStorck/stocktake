"""Layer 2: concept edges.

Code variables are mapped to named theoretical concepts through the
[variables] dictionary. Unmapped variables fall out of the graph and are
reported: they are code the vocabulary does not yet name.
"""

from __future__ import annotations

from collections import Counter

from .extract import Edge

# Names that are never worth reporting as unmapped, regardless of model.
DEFAULT_IGNORE = frozenset(
    {"float", "int", "len", "sum", "min", "max", "abs",
     "list", "dict", "set", "tuple", "range", "enumerate", "zip"}
)


def map_to_concepts(
    code_edges: list[Edge],
    variables: dict[str, str],
) -> list[Edge]:
    """Map code edges into concept space; edges with an unmapped endpoint
    or a self-loop after mapping are dropped."""
    mapped: set[Edge] = set()

    for edge in code_edges:
        src = variables.get(edge.source)
        tgt = variables.get(edge.target)
        if src and tgt and src != tgt:
            mapped.add(Edge(source=src, target=tgt))

    return sorted(mapped)


def unmapped_variables(
    code_edges: list[Edge],
    variables: dict[str, str],
    ignore: set[str] | frozenset[str] = frozenset(),
    ignore_prefixes: tuple[str, ...] = (),
) -> list[tuple[str, int]]:
    """Variables appearing in code edges that no mapping names, with their
    edge-endpoint counts, most frequent first."""
    counts: Counter[str] = Counter()
    for edge in code_edges:
        counts[edge.source] += 1
        counts[edge.target] += 1

    rows = [
        (name, count)
        for name, count in counts.items()
        if name not in variables
        and name not in DEFAULT_IGNORE
        and name not in ignore
        and not name.startswith(tuple(ignore_prefixes) or ("\0",))
    ]
    rows.sort(key=lambda x: (-x[1], x[0]))
    return rows
