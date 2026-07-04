"""The build pipeline: extract -> map -> audit -> emit.

Outputs, per build:
- code_edges.csv                 layer 1, for inspection
- concept_edges.csv              layer 2, for inspection
- unmapped_variables.csv         code the vocabulary does not yet name
- unwitnessed_concept_edges.csv  mechanisms the code has that no figure
                                 cites: deliberate omissions become
                                 decisions
and per figure:
- {name}.dot                     Forrester notation
- {name}_audit.csv               the audit trail
- {name}.pdf / {name}.png        if render=True and graphviz is present
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .audit import (
    AuditRow,
    audit_figure,
    unwitnessed_concept_edges,
    write_audit_csv,
)
from .concepts import map_to_concepts, unmapped_variables
from .emit import emit_figure_dot, try_render_dot
from .extract import Edge, extract_code_edges
from .schema import Config, load_config


@dataclass
class BuildReport:
    code_edges: list[Edge]
    concept_edges: list[Edge]
    unmapped: list[tuple[str, int]]
    unwitnessed: list[Edge]
    audits: dict[str, list[AuditRow]]  # figure name -> rows

    def summary(self) -> str:
        lines = [
            f"{len(self.code_edges)} code edges, "
            f"{len(self.concept_edges)} concept edges, "
            f"{len(self.unmapped)} unmapped variables, "
            f"{len(self.unwitnessed)} concept edges uncited by any figure"
        ]
        for name, rows in self.audits.items():
            counts: dict[str, int] = {}
            for row in rows:
                counts[row.status] = counts.get(row.status, 0) + 1
            detail = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
            lines.append(f"{name}: {len(rows)} edges audited ({detail})")
        return "\n".join(lines)


def _write_edges_csv(path: Path, edges: list[Edge]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target"])
        writer.writerows((e.source, e.target) for e in edges)


def _write_counts_csv(path: Path, rows: list[tuple[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["variable", "count"])
        writer.writerows(rows)


def build(
    source: str | Path,
    concept_map: str | Path | Config,
    out_dir: str | Path,
    render: bool = False,
) -> BuildReport:
    """Run the full audited build. Raises SchemaError or an AuditError
    subclass on any failure; on success all outputs are written to
    out_dir and a BuildReport is returned."""
    config = (
        concept_map
        if isinstance(concept_map, Config)
        else load_config(concept_map)
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    code_edges = extract_code_edges(source, config.aliases)
    concept_edges = map_to_concepts(code_edges, config.variables)
    unmapped = unmapped_variables(
        code_edges, config.variables, config.ignore, config.ignore_prefixes
    )

    # Audit every figure before emitting anything: a build with a failing
    # figure leaves no partially updated diagram behind.
    audits = {
        figure["name"]: audit_figure(figure, concept_edges)
        for figure in config.figures
    }
    unwitnessed = unwitnessed_concept_edges(concept_edges, config.figures)

    _write_edges_csv(out / "code_edges.csv", code_edges)
    _write_edges_csv(out / "concept_edges.csv", concept_edges)
    _write_counts_csv(out / "unmapped_variables.csv", unmapped)
    _write_edges_csv(out / "unwitnessed_concept_edges.csv", unwitnessed)

    for figure in config.figures:
        name = figure["name"]
        write_audit_csv(out / f"{name}_audit.csv", audits[name])
        dot_path = out / f"{name}.dot"
        dot_path.write_text(emit_figure_dot(figure), encoding="utf-8")
        if render:
            try_render_dot(dot_path)

    return BuildReport(
        code_edges=code_edges,
        concept_edges=concept_edges,
        unmapped=unmapped,
        unwitnessed=unwitnessed,
        audits=audits,
    )
