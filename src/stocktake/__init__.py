"""stocktake: code-audited stock-and-flow diagrams in Forrester notation.

The figure is hand-declared and code-audited, not code-generated.
Auto-layout of raw dependency graphs produces noise; hand-drawn diagrams
silently drift from the code. The audit removes the drift failure mode
while keeping human judgement over what the diagram says.

Origin: extracted from github.com/JoakimStorck/technology-fields
(experiment/cld/, commit 69ec1fd), where it audits the dynamic
labour-market model and produces a manuscript figure.
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

__version__ = "0.2.0"

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
