"""Extraction: covered patterns are asserted; the documented blind spots
are xfail so hardening (goal 3) turns them green deliberately.

Conservatism contract: false negatives (missed witness -> loud failure ->
human adds mapping) are acceptable; false positives (phantom witnesses)
are not.
"""

from pathlib import Path

import pytest

from stocktake import Edge, extract_code_edges

FIXTURES = Path(__file__).parent / "fixtures"
ALIASES = {"np": "", "state.stock": "stock"}


@pytest.fixture
def edges():
    return set(extract_code_edges(FIXTURES / "model.py", ALIASES))


def test_assign_dependencies(edges):
    assert Edge("demand", "pressure") in edges
    assert Edge("GAMMA", "inflow") in edges
    assert Edge("pressure", "inflow") in edges


def test_alias_drops_exact_name_only(edges):
    """Aliases are exact-name, as in the origin: `np` is dropped but
    `np.tanh` survives as a dependency and is filtered from the
    unmapped report via ignore_prefixes. Prefix semantics for aliases
    is a goal-3 design decision, not current behaviour."""
    sources = {e.source for e in edges}
    assert "np" not in sources
    assert any(s.startswith("np.") for s in sources)


def test_alias_renames_attribute(edges):
    # state.stock -> stock via alias; outflow = state.stock / delay
    assert Edge("stock", "outflow") in edges


def test_augassign_flows_into_target(edges):
    assert Edge("inflow", "stock") in edges
    assert Edge("outflow", "stock") in edges


def test_annassign_dependencies(edges):
    assert Edge("inflow", "report") in edges


def test_no_self_loops(edges):
    assert not any(e.source == e.target for e in edges)


@pytest.mark.xfail(
    reason="known blind spot: dependencies inside bare return "
    "expressions are not extracted (goal 3); the working convention "
    "is to map the function name itself",
    strict=True,
)
def test_return_expression_dependencies(edges):
    assert Edge("demand", "hidden_dependency") in edges


@pytest.mark.xfail(
    reason="known blind spot: feature-flag branches audit like "
    "baseline code (goal 3: consider explicit variant tagging)",
    strict=True,
)
def test_variant_branches_distinguished():
    pytest.fail("variant tagging not designed yet")
