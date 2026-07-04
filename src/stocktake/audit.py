"""Layer 3: the figure audit.

Every declared figure edge must list concept-level witnesses that exist
with AST support, or carry identity = true (definitional, mechanism
stated) or parameter = true (a constant is a declaration, not a dataflow
claim). An unwitnessed edge is a hard build failure.

A green audit certifies figure-code correspondence; it does not certify
that signs or economic interpretations are right. Those remain declared,
and the audit rows carry the mechanism text.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .errors import (
    MissingMechanismError,
    UnsupportedWitnessError,
    UnwitnessedEdgeError,
)
from .extract import Edge
from .schema import parse_witness


@dataclass(frozen=True)
class AuditRow:
    edge: str
    status: str  # "ast" | "identity" | "parameter"
    witnesses: tuple[str, ...]
    mechanism: str


def audit_figure(figure: dict, concept_edges: list[Edge]) -> list[AuditRow]:
    """Audit one figure declaration against the AST-supported concept
    graph. Raises an AuditError subclass on the first failing edge."""
    supported = {(e.source, e.target) for e in concept_edges}
    name = figure["name"]

    rows: list[AuditRow] = []
    for edge in figure.get("edges", []):
        key = f"{edge['from']}->{edge['to']}"

        if edge.get("identity", False):
            status = "identity"
        elif edge.get("parameter", False):
            status = "parameter"
        else:
            witnesses = edge.get("audit", [])
            if not witnesses:
                raise UnwitnessedEdgeError(
                    f"figure {name}: edge {key} has no audit witnesses "
                    f"and no identity/parameter mark"
                )
            missing = [w for w in witnesses
                       if parse_witness(w) not in supported]
            if missing:
                raise UnsupportedWitnessError(
                    f"figure {name}: edge {key}: no AST support for "
                    f"witness(es) {missing}; the figure no longer "
                    f"matches the code"
                )
            status = "ast"

        if status != "ast" and not edge.get("mechanism"):
            raise MissingMechanismError(
                f"figure {name}: edge {key}: {status} edges must state "
                f"their mechanism"
            )

        rows.append(
            AuditRow(
                edge=key,
                status=status,
                witnesses=tuple(edge.get("audit", [])),
                mechanism=edge.get("mechanism", ""),
            )
        )

    return rows


def unwitnessed_concept_edges(
    concept_edges: list[Edge],
    figures: list[dict],
) -> list[Edge]:
    """The dual direction of the audit: AST-supported concept edges that
    no figure edge cites as a witness. These are mechanisms the code has
    that the diagrams omit -- deliberate omissions become decisions."""
    cited: set[tuple[str, str]] = set()
    for figure in figures:
        for edge in figure.get("edges", []):
            for witness in edge.get("audit", []):
                cited.add(parse_witness(witness))

    return [e for e in concept_edges if (e.source, e.target) not in cited]


def write_audit_csv(path: Path, rows: list[AuditRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["edge", "status", "witnesses", "mechanism"]
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "edge": row.edge,
                    "status": row.status,
                    "witnesses": "; ".join(row.witnesses),
                    "mechanism": row.mechanism,
                }
            )
