"""stocktake: code-audited stock-and-flow diagrams in Forrester notation.

What the diagram shows is hand-declared; whether it is true of the code
is audited; where it is drawn is generated automatically. What is
rejected is generating the diagram's content from the raw dependency
graph (noise) or hand-drawing it (silent drift).

Repository: github.com/JoakimStorck/stocktake
Extracted from github.com/JoakimStorck/technology-fields
(experiment/cld/), where it audits a dynamic labour-market model and
produces a manuscript figure.
"""

from .audit import AuditRow, audit_figure, unwitnessed_concept_edges
from .build import BuildReport, build
from .concepts import map_to_concepts, unmapped_variables
from .errors import (
    AuditError,
    MissingMechanismError,
    SchemaError,
    StocktakeError,
    UnsupportedWitnessError,
    UnwitnessedEdgeError,
)
from .extract import Edge, extract_code_edges
from .schema import Config, load_config
from .emit import (
    compute_layout,
    emit_figure_dot,
    figure_layout_diagnostics,
)
from .layout import (
    DerivedLayout,
    Layout,
    derive_layout,
    derive_positions,
)
from .metrics import DiagramMetrics, measure

__version__ = "0.3.0"

__all__ = [
    "AuditError",
    "AuditRow",
    "BuildReport",
    "Config",
    "DerivedLayout",
    "DiagramMetrics",
    "Edge",
    "Layout",
    "MissingMechanismError",
    "SchemaError",
    "StocktakeError",
    "UnsupportedWitnessError",
    "UnwitnessedEdgeError",
    "audit_figure",
    "build",
    "compute_layout",
    "derive_layout",
    "derive_positions",
    "emit_figure_dot",
    "figure_layout_diagnostics",
    "measure",
    "extract_code_edges",
    "load_config",
    "map_to_concepts",
    "unmapped_variables",
    "unwitnessed_concept_edges",
    "__version__",
]
