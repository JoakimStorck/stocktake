"""Structural-quality metrics, and the end-to-end guarantee that the
principled build produces a legible layout (no overlaps, no lines
through node bodies). Graphviz-gated."""

import shutil
from pathlib import Path

import pytest

from stocktake import build, emit_figure_dot, load_config, measure

FIXTURES = Path(__file__).parent / "fixtures"

pytestmark = pytest.mark.skipif(
    shutil.which("dot") is None or shutil.which("neato") is None,
    reason="graphviz not installed",
)


def test_metrics_on_planar_chain_are_zero():
    dot = "digraph { rankdir=TB; a->b; b->c; }"
    m = measure(dot)
    assert m.crossings == 0
    assert m.node_overlaps == 0
    assert m.edge_node_clips == 0


def test_overlap_metric_detects_collapse():
    # two nodes pinned to the same point overlap
    dot = (
        'digraph { node[shape=circle,width=1];'
        ' a[pos="0,0"]; b[pos="0,0"]; a->b; }'
    )
    assert measure(dot, positioned=True).node_overlaps >= 1


def test_principled_build_is_clean():
    """The end-to-end guarantee: a principled build lays the fixture out
    with no overlaps and no lines through node bodies."""
    config = load_config(FIXTURES / "map.toml")
    figure = config.figures[0]
    from stocktake import compute_layout
    layout = compute_layout(figure)
    assert layout is not None
    dot = emit_figure_dot(figure, positions=layout.positions)
    metrics = measure(dot, positioned=True)
    assert metrics.is_clean(), str(metrics)


def test_build_writes_positioned_dot(tmp_path):
    build(FIXTURES / "model.py", FIXTURES / "map.toml", tmp_path)
    dot = (tmp_path / "fixture_figure.dot").read_text()
    # principled build pins positions for neato -n2
    assert "pos=" in dot
