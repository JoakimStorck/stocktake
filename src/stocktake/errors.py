"""Error hierarchy.

Every failure the audit or the schema validation can produce is a hard
build failure raised as a subclass of StocktakeError. The CLI translates
these to a non-zero exit code; library consumers catch them as exceptions.
"""

from __future__ import annotations


class StocktakeError(Exception):
    """Base class for all stocktake build failures."""


class SchemaError(StocktakeError):
    """The concept map or figure declaration is structurally invalid."""


class AuditError(StocktakeError):
    """A declared figure edge fails its code audit."""


class UnwitnessedEdgeError(AuditError):
    """A figure edge lists no witnesses and is not identity/parameter."""


class UnsupportedWitnessError(AuditError):
    """A witness has no AST support: the figure no longer matches the code."""


class MissingMechanismError(AuditError):
    """An identity or parameter edge does not state its mechanism."""
