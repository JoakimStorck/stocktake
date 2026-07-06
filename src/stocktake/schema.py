"""Concept-map schema: loading and structural validation.

The TOML is the single source of truth. Everything a figure declaration
can get structurally wrong is a hard build failure here, before the
audit runs:

- duplicate node ids, duplicate figure names
- an edge endpoint that is not a declared node
- a rank entry that is not a declared node (graphviz would silently
  invent a phantom node otherwise)
- an unknown node kind or channel
- a [variables] value naming a concept absent from [concepts]
- a witness that is malformed or names an unknown concept (so a typo
  reads "unknown concept", not the misleading "no AST support")

Schema layout (see tests/fixtures for a complete example):

  [extract]                # optional
  aliases = { "eq.X" = "X", np = "" }   # "" drops the identifier
  ignore = ["self", "dyn"]              # unmapped-report noise
  ignore_prefixes = ["np."]

  [variables]              # code name -> concept id
  [concepts]               # concept id -> display name

  [[figures]]              # one or more hand-declared figures
  name = "..."
  ranks = [["a", "b"], ...]
  [[figures.nodes]]        # id, kind, label, optional group
  [[figures.edges]]        # from, to, channel, audit/identity/parameter,
                           # mechanism, optional hints
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import SchemaError

NODE_KINDS = {"level", "rate", "aux", "param", "source", "sink"}
CHANNELS = {
    "information",
    "material", "personnel", "orders", "money", "capital",
}
LAYOUT_MODES = {"principled", "manual"}


@dataclass
class Config:
    variables: dict[str, str]
    concepts: dict[str, str]
    figures: list[dict]
    aliases: dict[str, str] = field(default_factory=dict)
    ignore: set[str] = field(default_factory=set)
    ignore_prefixes: tuple[str, ...] = ()


def load_config(path: str | Path) -> Config:
    """Load and validate a concept map. Raises SchemaError on any
    structural defect."""
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    extract = raw.get("extract", {})

    config = Config(
        variables=raw.get("variables", {}),
        concepts=raw.get("concepts", {}),
        figures=raw.get("figures", []),
        aliases=extract.get("aliases", {}),
        ignore=set(extract.get("ignore", [])),
        ignore_prefixes=tuple(extract.get("ignore_prefixes", [])),
    )
    validate(config)
    return config


def parse_witness(witness: str) -> tuple[str, str]:
    """Split a 'source->target' witness string. Raises SchemaError if the
    string is not exactly one arrow between two non-empty concept ids."""
    parts = witness.split("->")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise SchemaError(
            f"malformed witness {witness!r}: expected 'concept->concept'"
        )
    return parts[0], parts[1]


def validate(config: Config) -> None:
    for code_name, concept in config.variables.items():
        if concept not in config.concepts:
            raise SchemaError(
                f"[variables] {code_name} maps to unknown concept "
                f"{concept!r}: add it to [concepts] or fix the mapping"
            )

    seen_names: set[str] = set()
    for figure in config.figures:
        name = figure.get("name")
        if not name:
            raise SchemaError("every [[figures]] entry needs a name")
        if name in seen_names:
            raise SchemaError(f"duplicate figure name {name!r}")
        seen_names.add(name)
        _validate_figure(figure, config.concepts)


def _validate_figure(figure: dict, concepts: dict[str, str]) -> None:
    name = figure["name"]

    mode = figure.get("layout", "principled")
    if mode not in LAYOUT_MODES:
        raise SchemaError(
            f"figure {name}: unknown layout mode {mode!r} "
            f"(expected one of {sorted(LAYOUT_MODES)})"
        )

    ids: set[str] = set()

    for node in figure.get("nodes", []):
        node_id = node.get("id")
        if not node_id:
            raise SchemaError(f"figure {name}: node without id")
        if node_id in ids:
            raise SchemaError(f"figure {name}: duplicate node id {node_id!r}")
        ids.add(node_id)
        kind = node.get("kind", "aux")
        if kind not in NODE_KINDS:
            raise SchemaError(
                f"figure {name}: node {node_id!r} has unknown kind {kind!r} "
                f"(expected one of {sorted(NODE_KINDS)})"
            )
        if "label" not in node:
            raise SchemaError(f"figure {name}: node {node_id!r} has no label")

    for edge in figure.get("edges", []):
        key = f"{edge.get('from')}->{edge.get('to')}"
        for endpoint in ("from", "to"):
            node_id = edge.get(endpoint)
            if node_id not in ids:
                raise SchemaError(
                    f"figure {name}: edge {key} references undeclared "
                    f"node {node_id!r}"
                )
        channel = edge.get("channel", "information")
        if channel not in CHANNELS:
            raise SchemaError(
                f"figure {name}: edge {key} has unknown channel "
                f"{channel!r} (expected one of {sorted(CHANNELS)})"
            )
        for witness in edge.get("audit", []):
            src, tgt = parse_witness(witness)
            for concept in (src, tgt):
                if concept not in concepts:
                    raise SchemaError(
                        f"figure {name}: edge {key} witness {witness!r} "
                        f"names unknown concept {concept!r}"
                    )

    for group in figure.get("ranks", []):
        for node_id in group:
            if node_id not in ids:
                raise SchemaError(
                    f"figure {name}: rank group references undeclared "
                    f"node {node_id!r}; a saved layout must not outlive "
                    f"the declaration"
                )
