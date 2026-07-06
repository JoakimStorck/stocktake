"""Principled layout derivation: the P1-P9 principles as tests (T1-T7).

These assert on the derived layout object and on the emitted dot
structure, not on pixels. Rendered figures remain for human review.
"""

import subprocess
from pathlib import Path

import pytest

from stocktake import derive_layout, emit_figure_dot, load_config
from stocktake.layout import DerivedLayout

FIXTURES = Path(__file__).parent / "fixtures"


def _figure(**overrides):
    """A small figure: source -> fill(rate) -> S(level) -> drain(rate)
    -> sink, with an auxiliary P and a constant gamma feeding fill, and
    an information take-off from S back to drain (the many-information
    case for T1)."""
    figure = {
        "name": "t",
        "nodes": [
            {"id": "src", "kind": "source", "label": "src"},
            {"id": "fill", "kind": "rate", "label": "fill"},
            {"id": "S", "kind": "level", "label": "S"},
            {"id": "drain", "kind": "rate", "label": "drain"},
            {"id": "snk", "kind": "sink", "label": "snk"},
            {"id": "P", "kind": "aux", "label": "P"},
            {"id": "gamma", "kind": "param", "label": "g"},
        ],
        "edges": [
            {"from": "src", "to": "fill", "channel": "material"},
            {"from": "fill", "to": "S", "channel": "material"},
            {"from": "S", "to": "drain", "channel": "material"},
            {"from": "drain", "to": "snk", "channel": "material"},
            {"from": "P", "to": "fill", "channel": "information"},
            {"from": "gamma", "to": "fill", "channel": "information"},
            {"from": "S", "to": "drain", "channel": "information"},
            {"from": "S", "to": "P", "channel": "information"},
        ],
    }
    figure.update(overrides)
    return figure


def _node_rows(dot: str) -> dict[str, float]:
    """Rasterless: run dot -Tplain and return node -> y (rank proxy)."""
    plain = subprocess.run(
        ["dot", "-Tplain"], input=dot, capture_output=True, text=True
    ).stdout
    ys = {}
    for line in plain.splitlines():
        p = line.split()
        if p and p[0] == "node":
            ys[p[1].strip('"')] = float(p[3])
    return ys


# --- T1: information does not constrain the spine ---------------------

def test_t1_information_edges_are_unconstrained():
    layout = derive_layout(_figure())
    # the three information edges are indices 4,5,6,7; the S->drain
    # information edge (6) and S->P (7) and one of the fill feeders is
    # the anchor, the rest drape.
    draped = {i for i, a in layout.edge_attrs.items()
              if "constraint=false" in a}
    # material edges (0-3) never drape
    assert draped.isdisjoint({0, 1, 2, 3})
    # at least the duplicate S->drain information edge drapes
    assert 6 in draped


def test_t1_flow_order_preserved_under_many_information_edges():
    dot = emit_figure_dot(_figure())
    ys = _node_rows(dot)
    # monotone descent along the material spine
    assert ys["src"] > ys["fill"] > ys["S"] > ys["drain"] > ys["snk"]


# --- T2: rate inputs are local ---------------------------------------

def test_t2_rate_inputs_anchor_near_rate():
    layout = derive_layout(_figure())
    # gamma and P both feed the rate 'fill' and should anchor to it
    assert "anchored gamma -> fill (rate)" in layout.diagnostics
    assert "anchored P -> fill (rate)" in layout.diagnostics


# --- T3: auxiliary between source and rate ---------------------------

def test_t3_auxiliary_not_on_spine():
    layout = derive_layout(_figure())
    # P is floating (no conserved-flow edge), so it is not in a flow group
    assert "P" not in layout.node_groups
    # but S, fill, drain (spine) are grouped together
    assert layout.node_groups["S"] == layout.node_groups["fill"]


def test_t3_auxiliary_anchors_to_rate_not_level():
    # P receives info from S (level) and feeds fill (rate). Its anchor is
    # the rate it feeds, per the rate>level priority.
    layout = derive_layout(_figure())
    assert "anchored P -> fill (rate)" in layout.diagnostics


# --- T4: constant is peripheral --------------------------------------

def test_t4_constant_does_not_join_spine():
    layout = derive_layout(_figure())
    assert "gamma" not in layout.node_groups


# --- T5: source/sink at channel ends ---------------------------------

def test_t5_source_and_sink_at_ends():
    dot = emit_figure_dot(_figure())
    ys = _node_rows(dot)
    assert ys["src"] == max(ys.values())
    assert ys["snk"] == min(ys.values())


# --- T6: multiple channels remain separate ---------------------------

def test_t6_two_flow_components_separate_groups():
    figure = {
        "name": "t6",
        "nodes": [
            {"id": "a1", "kind": "source", "label": "a1"},
            {"id": "a2", "kind": "rate", "label": "a2"},
            {"id": "a3", "kind": "level", "label": "a3"},
            {"id": "b1", "kind": "source", "label": "b1"},
            {"id": "b2", "kind": "rate", "label": "b2"},
            {"id": "b3", "kind": "level", "label": "b3"},
            {"id": "shared", "kind": "aux", "label": "sh"},
        ],
        "edges": [
            {"from": "a1", "to": "a2", "channel": "material"},
            {"from": "a2", "to": "a3", "channel": "material"},
            {"from": "b1", "to": "b2", "channel": "personnel"},
            {"from": "b2", "to": "b3", "channel": "personnel"},
            {"from": "shared", "to": "a2", "channel": "information"},
            {"from": "shared", "to": "b2", "channel": "information"},
        ],
    }
    layout = derive_layout(figure)
    assert layout.node_groups["a1"] == layout.node_groups["a3"]
    assert layout.node_groups["b1"] == layout.node_groups["b3"]
    assert layout.node_groups["a1"] != layout.node_groups["b1"]
    # shared auxiliary belongs to neither spine
    assert "shared" not in layout.node_groups


# --- T7: user layout overrides derived layout ------------------------

def test_t7_user_group_overrides_derived():
    # Force P into a user group; derived layout would leave it ungrouped.
    figure = _figure()
    figure["nodes"][5]["group"] = "myspine"  # P
    dot = emit_figure_dot(figure)
    line = next(l for l in dot.splitlines() if l.strip().startswith('"P"'))
    assert 'group="myspine"' in line


def test_t7_user_hints_override_derived_edge_attr():
    figure = _figure()
    # edge 6 (duplicate S->drain information) would drape; pin it instead
    figure["edges"][6]["hints"] = "constraint=true, color=red"
    dot = emit_figure_dot(figure)
    line = [l for l in dot.splitlines() if '"S" -> "drain"' in l]
    # two S->drain edges exist (material + information); the information
    # one now carries the user hint and not the derived constraint=false
    assert any("color=red" in l for l in line)
    assert not any("color=red" in l and "constraint=false" in l
                   for l in line)


def test_t7_manual_mode_derives_nothing():
    figure = _figure(layout="manual")
    layout_dot = emit_figure_dot(figure)
    # no derived groups: no group= attributes at all (fixture declares none)
    assert "group=" not in layout_dot
    # no derived constraint=false either
    assert "constraint=false" not in layout_dot


# --- swim-lane force engine (pure math, no graphviz) -----------------

from stocktake import derive_positions
from stocktake.layout import assign_lanes, _columns, _variable_components


def _two_column_frame():
    """Synthetic frame: two flow columns (a-chain at x=0, b-chain at
    x=300), a bridging variable v (feeds a2 and b2), a cluster {h, c1}
    where h feeds c1 and c1 feeds a2, and a lone k feeding b2."""
    figure = {
        "name": "syn",
        "nodes": [
            {"id": "a1", "kind": "source", "label": "a1"},
            {"id": "a2", "kind": "rate", "label": "a2"},
            {"id": "a3", "kind": "level", "label": "a3"},
            {"id": "b1", "kind": "source", "label": "b1"},
            {"id": "b2", "kind": "rate", "label": "b2"},
            {"id": "b3", "kind": "level", "label": "b3"},
            {"id": "v", "kind": "aux", "label": "v"},
            {"id": "h", "kind": "aux", "label": "h"},
            {"id": "c1", "kind": "aux", "label": "c1"},
            {"id": "k", "kind": "param", "label": "k"},
        ],
        "edges": [
            {"from": "a1", "to": "a2", "channel": "material"},
            {"from": "a2", "to": "a3", "channel": "material"},
            {"from": "b1", "to": "b2", "channel": "personnel"},
            {"from": "b2", "to": "b3", "channel": "personnel"},
            {"from": "v", "to": "a2", "channel": "information"},
            {"from": "v", "to": "b2", "channel": "information"},
            {"from": "h", "to": "c1", "channel": "information"},
            {"from": "c1", "to": "a2", "channel": "information"},
            {"from": "k", "to": "b2", "channel": "information"},
        ],
    }
    init_pos = {
        "a1": [0, 300], "a2": [0, 200], "a3": [0, 100],
        "b1": [300, 300], "b2": [300, 200], "b3": [300, 100],
        "v": [150, 250], "h": [150, 150], "c1": [150, 180], "k": [150, 220],
    }
    sizes = {n: (40, 30) for n in init_pos}
    return figure, init_pos, sizes


def test_variable_components_follow_transitive_links():
    figure, _, _ = _two_column_frame()
    variables = ["v", "h", "c1", "k"]
    comps = _variable_components(variables, figure["edges"])
    comp_sets = {frozenset(c) for c in comps}
    # h and c1 are one component (h->c1); v and k are singletons
    assert frozenset({"h", "c1"}) in comp_sets
    assert frozenset({"v"}) in comp_sets
    assert frozenset({"k"}) in comp_sets


def test_bridging_variable_lane_is_between_columns():
    figure, init_pos, _ = _two_column_frame()
    components, col_x, col_of = _columns(figure, init_pos)
    lanes, _ = assign_lanes(figure, components, col_x, col_of, init_pos)
    lo, hi = lanes["v"]
    assert col_x[0] < lo and hi < col_x[1]  # strictly between the columns


def test_force_positions_stay_in_lanes():
    figure, init_pos, sizes = _two_column_frame()
    layout = derive_positions(figure, init_pos, sizes)
    for v in ("v", "h", "c1", "k"):
        lo, hi = layout.lanes[v]
        x, _ = layout.positions[v]
        assert lo - 1 <= x <= hi + 1


def test_force_positions_have_no_overlaps():
    figure, init_pos, sizes = _two_column_frame()
    layout = derive_positions(figure, init_pos, sizes)
    import itertools
    names = list(layout.positions)
    for a, b in itertools.combinations(names, 2):
        (xa, ya), (xb, yb) = layout.positions[a], layout.positions[b]
        wa, ha = sizes[a]
        wb, hb = sizes[b]
        ox = (wa + wb) / 2 - abs(xa - xb)
        oy = (ha + hb) / 2 - abs(ya - yb)
        assert not (ox > 2 and oy > 2), f"{a}/{b} overlap"


def test_flow_spine_stays_straight():
    # a-chain shares one x; the force pass only translates columns
    # vertically, never bends them.
    figure, init_pos, sizes = _two_column_frame()
    layout = derive_positions(figure, init_pos, sizes)
    xs = {round(layout.positions[n][0], 3) for n in ("a1", "a2", "a3")}
    assert len(xs) == 1


def test_manual_mode_emits_no_positions():
    from stocktake import compute_layout
    figure, _, _ = _two_column_frame()
    figure["layout"] = "manual"
    assert compute_layout(figure) is None
