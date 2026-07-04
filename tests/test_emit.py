"""Emitter: structural verification of the dot source. No pixel
comparison -- rendered figures are for human review; the dot source is
the testable artifact. Layout hints may change without breaking these."""

from pathlib import Path

import pytest

from stocktake import load_config
from stocktake.emit import emit_figure_dot, mathlabel

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def dot():
    config = load_config(FIXTURES / "map.toml")
    return emit_figure_dot(config.figures[0])


def test_level_is_box(dot):
    assert '"S" [label=' in dot and "shape=box" in dot


def test_rate_carries_valve_glyph(dot):
    assert "&#8904;" in dot  # U+22C8 bowtie valve


def test_param_carries_constant_symbol_and_port(dot):
    assert "&#9472;&#8854;&#9472;" in dot  # ---(-)--- constant glyph
    assert 'port="c"' in dot


def test_param_information_edge_departs_from_port_undecorated(dot):
    # Forrester fig 8-7: no odot at a constant; the glyph is the circle.
    line = next(l for l in dot.splitlines() if '"gamma":c ->' in l)
    assert "arrowtail=odot" not in line
    assert "style=dashed" in line


def test_information_edge_has_takeoff_circle(dot):
    line = next(l for l in dot.splitlines() if '"P" -> "fill"' in l)
    assert "arrowtail=odot" in line and "style=dashed" in line


def test_material_flow_enters_rate_without_arrowhead(dot):
    line = next(l for l in dot.splitlines() if '"src" -> "fill"' in l)
    assert "arrowhead=none" in line


def test_material_flow_leaves_rate_with_arrowhead(dot):
    line = next(l for l in dot.splitlines() if '"fill" -> "S"' in l)
    assert "arrowhead=none" not in line


def test_ranks_emitted(dot):
    assert '{ rank=same; "src"; "P"; }' in dot


def test_no_sign_labels(dot):
    # Industrial Dynamics carries mechanism in the rate equations; we
    # carry it in the audit CSV, never as +/- on edges.
    assert 'label="+"' not in dot and 'label="-"' not in dot


def test_fonts_reach_into_html_labels(dot):
    assert 'face="DejaVu Sans"' in dot


def test_mathlabel_sub_sup_and_newline():
    assert mathlabel("theta_abs") == (
        '<font face="DejaVu Sans">theta<sub>abs</sub></font>'
    )
    assert "<sup>D</sup>" in mathlabel("Gamma^D")
    assert "<br/>" in mathlabel("a\nb")
    assert "M<sub>o</sub>(0)" in mathlabel("M_o(0)")


def test_mathlabel_escapes_html():
    assert "&lt;" in mathlabel("a<b")
