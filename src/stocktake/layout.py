"""Principled layout: the swim-lane force model.

The layout is derived from the declared structure so the user needs
group/ranks/hints only as exceptions. It has two parts:

1. derive_layout (structural): each conserved-flow component becomes a
   group holding its spine straight, and non-anchor information edges
   get constraint=false. This produces the initial dot frame from which
   column x-positions and node sizes are read.

2. derive_positions (swim-lane force balance): the actual placement.
   The model, established empirically against four metrics (crossings,
   information-line length, node overlaps, lines through node bodies):

   - Flows are rigid vertical columns (the spine, straight) that may be
     TRANSLATED VERTICALLY as units to align with their variables.
   - Between and outside the columns are SWIM LANES: vertical bands the
     variables live in, confined so they can never collapse onto a flow.
   - The unit of lane assignment is a variable's CONNECTED COMPONENT,
     not the individual node: a component bridging two columns goes in
     the lane between them; a multi-node component on one column stays
     together and goes central; a lone node goes to the periphery. (A
     hub like A_K that feeds two variables which in turn feed a rate is
     only reachable transitively -- the component captures that link,
     which per-node assignment splits and tangles.)
   - Placement inside the lanes is a spring-electrical equilibrium:
     attraction along edges plus soft repulsion between all nodes. The
     repulsion is what spreads a connected mesh into a convex,
     untangled shape instead of collapsing it into a knot -- the goal
     is the force balance, not minimum length. A hard minimum-gap pass
     guarantees zero overlap as a floor under the soft repulsion.

Both functions are pure and deterministic. derive_positions takes the
initial frame (positions + sizes from a dot pass) and returns final
positions; the graphviz calls live in emit.compute_layout. Derived
positions are merged UNDER explicit user layout (user wins).
"""

from __future__ import annotations

import itertools
import math
import statistics
from dataclasses import dataclass, field

CONSERVED_CHANNELS = {"material", "personnel", "orders", "money", "capital"}
BOUNDARY_KINDS = {"source", "sink"}

# --- Force-balance parameters (documented defaults) ------------------
# Tuned against Figure 2 of the origin manuscript to reach zero on all
# four structural metrics. They are data, not magic: raise IDEAL_EDGE_LEN
# to spread nodes further, raise REPULSION to untangle denser meshes.
IDEAL_EDGE_LEN = 70.0      # spring rest length (points)
REPULSION = IDEAL_EDGE_LEN * IDEAL_EDGE_LEN
INIT_TEMPERATURE = 60.0    # max node displacement per step, initially
COOLING = 0.985            # geometric temperature decay per iteration
MIN_TEMPERATURE = 6.0
ITERATIONS = 300
NODE_GAP = 12.0            # hard minimum clearance between node boxes
LANE_CLEARANCE = 52.0      # keep variables this far off a flow column
OUTER_LANE_WIDTH = 190.0   # width of a peripheral (outer) lane
COLUMN_PULL = 0.02         # strength of cross-lane pull on a column

# Anchor preference: a floating node anchors to its most "decisive"
# neighbour (P5: rates are decision points), rates first.
_ANCHOR_PRIORITY = {"rate": 0, "level": 1, "aux": 2,
                    "param": 3, "source": 4, "sink": 4}


@dataclass
class DerivedLayout:
    """Derived layout, merged under explicit user layout at emit time."""

    node_groups: dict[str, str] = field(default_factory=dict)
    edge_attrs: dict[int, str] = field(default_factory=dict)  # edge index
    diagnostics: list[str] = field(default_factory=list)


def _flow_components(node_ids: list[str], flow_pairs: list[tuple[str, str]]):
    """Weakly connected components of the conserved-flow subgraph, in
    first-appearance order (deterministic)."""
    adjacency: dict[str, set[str]] = {}
    for a, b in flow_pairs:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    seen: set[str] = set()
    components: list[list[str]] = []
    for node_id in node_ids:
        if node_id in adjacency and node_id not in seen:
            stack, comp = [node_id], []
            seen.add(node_id)
            while stack:
                current = stack.pop()
                comp.append(current)
                for neighbour in sorted(adjacency[current]):
                    if neighbour not in seen:
                        seen.add(neighbour)
                        stack.append(neighbour)
            components.append(comp)
    return components


def derive_layout(figure: dict) -> DerivedLayout:
    """Derive groups and edge attributes from the declared structure."""
    layout = DerivedLayout()
    nodes = figure.get("nodes", [])
    edges = figure.get("edges", [])
    kind = {n["id"]: n.get("kind", "aux") for n in nodes}
    node_ids = [n["id"] for n in nodes]

    flow_indices = [
        i for i, e in enumerate(edges)
        if e.get("channel", "information") in CONSERVED_CHANNELS
    ]
    flow_pairs = [(edges[i]["from"], edges[i]["to"]) for i in flow_indices]
    flow_nodes = {n for pair in flow_pairs for n in pair}

    # P1/P9: one derived group per flow component holds each spine
    # straight; several components sit side by side.
    components = _flow_components(node_ids, flow_pairs)
    for comp_number, comp in enumerate(components, start=1):
        group = f"flow{comp_number}"
        for node_id in comp:
            layout.node_groups[node_id] = group
    if components:
        layout.diagnostics.append(
            f"derived {len(components)} flow group(s): "
            + ", ".join(f"flow{i+1}({len(c)} nodes)"
                        for i, c in enumerate(components))
        )

    # P3: anchor-edge selection for floating nodes.
    floating = [n for n in node_ids if n not in flow_nodes]
    outgoing: dict[str, list[int]] = {}
    incoming: dict[str, list[int]] = {}
    for i, e in enumerate(edges):
        if i in set(flow_indices):
            continue
        outgoing.setdefault(e["from"], []).append(i)
        incoming.setdefault(e["to"], []).append(i)

    anchors: set[int] = set()
    for node_id in floating:
        candidates = [(edges[i]["to"], i) for i in outgoing.get(node_id, [])]
        direction = "->"
        if not candidates:
            # A pure receiver (e.g. a reporting auxiliary): anchor by its
            # most decisive upstream instead.
            candidates = [(edges[i]["from"], i)
                          for i in incoming.get(node_id, [])]
            direction = "<-"
        if not candidates:
            layout.diagnostics.append(
                f"node {node_id!r} has no edges: left to dot"
            )
            continue
        counterpart, index = min(
            candidates,
            key=lambda c: (_ANCHOR_PRIORITY.get(kind[c[0]], 9), c[1]),
        )
        anchors.add(index)
        layout.diagnostics.append(
            f"anchored {node_id} {direction} {counterpart} "
            f"({kind[counterpart]})"
        )

    # Every non-anchor information edge drapes.
    draped = 0
    for i, e in enumerate(edges):
        if i in set(flow_indices) or i in anchors:
            continue
        layout.edge_attrs[i] = "constraint=false"
        draped += 1
    if draped:
        layout.diagnostics.append(
            f"set {draped} information edge(s) constraint=false"
        )

    return layout


@dataclass
class Layout:
    """Result of the swim-lane force balance."""

    positions: dict[str, tuple[float, float]]
    lanes: dict[str, tuple[float, float]]
    columns: list[list[str]]
    diagnostics: list[str] = field(default_factory=list)


def _variable_components(
    variables: list[str], edges: list[dict]
) -> list[list[str]]:
    """Connected components of the subgraph induced on variables by the
    edges among them. This is the unit of lane assignment: a transitive
    link (A_K -> disp -> rate, A_K -> gate -> rate) keeps A_K, disp and
    gate in one component so they are not split across a flow."""
    var_set = set(variables)
    adjacency: dict[str, set[str]] = {v: set() for v in variables}
    for e in edges:
        a, b = e["from"], e["to"]
        if a in var_set and b in var_set:
            adjacency[a].add(b)
            adjacency[b].add(a)
    seen: set[str] = set()
    components: list[list[str]] = []
    for v in variables:
        if v in seen:
            continue
        stack, comp = [v], []
        seen.add(v)
        while stack:
            u = stack.pop()
            comp.append(u)
            for w in adjacency[u]:
                if w not in seen:
                    seen.add(w)
                    stack.append(w)
        components.append(comp)
    return components


def _columns(figure: dict, init_pos: dict[str, list[float]]):
    """Flow components as vertical columns, left to right by median x."""
    edges = figure.get("edges", [])
    node_ids = [n["id"] for n in figure.get("nodes", [])]
    flow_pairs = [
        (e["from"], e["to"]) for e in edges
        if e.get("channel", "information") in CONSERVED_CHANNELS
    ]
    components = _flow_components(node_ids, flow_pairs)
    components.sort(
        key=lambda c: statistics.median(init_pos[n][0] for n in c)
    )
    col_x = [statistics.median(init_pos[n][0] for n in c)
             for c in components]
    col_of = {n: ci for ci, c in enumerate(components) for n in c}
    return components, col_x, col_of


def assign_lanes(figure, components, col_x, col_of, init_pos):
    """Assign each variable an x-range (its swim lane), per component.

    Bridging component -> lane between its extreme columns. Connected
    cluster on one column -> central side. Lone node -> periphery,
    alternating sides when several attach to the same column."""
    nc = len(components)
    clr = LANE_CLEARANCE
    edges = figure.get("edges", [])
    node_ids = [n["id"] for n in figure.get("nodes", [])]
    flow_nodes = set(col_of)
    variables = [n for n in node_ids if n not in flow_nodes]

    neighbours: dict[str, set[str]] = {n: set() for n in node_ids}
    for e in edges:
        neighbours[e["from"]].add(e["to"])
        neighbours[e["to"]].add(e["from"])

    def between(i, j):
        return (col_x[i] + clr, col_x[j] - clr)

    def outer(ci, side):
        x = col_x[ci]
        return (x - OUTER_LANE_WIDTH, x - clr) if side < 0 \
            else (x + clr, x + OUTER_LANE_WIDTH)

    def central(ci):
        if nc <= 1:
            return (col_x[ci] - OUTER_LANE_WIDTH, col_x[ci] - clr)
        if ci == 0:
            return between(0, 1)
        if ci == nc - 1:
            return between(nc - 2, nc - 1)
        return between(ci, ci + 1)

    def periphery(ci):
        return outer(ci, +1 if ci == nc - 1 else -1)

    lanes: dict[str, tuple[float, float]] = {}
    diagnostics: list[str] = []
    singleton_side: dict[int, int] = {}
    for comp in _variable_components(variables, edges):
        cols = sorted({col_of[m] for v in comp
                       for m in neighbours[v] if m in col_of})
        if len(cols) >= 2:
            rng = between(cols[0], cols[-1])
            diagnostics.append(
                f"bridging {'+'.join(comp)} between columns "
                f"{cols[0]}..{cols[-1]}"
            )
        elif len(cols) == 1:
            ci = cols[0]
            if len(comp) > 1:
                rng = central(ci)
                diagnostics.append(
                    f"cluster {'+'.join(comp)} central to column {ci}"
                )
            else:
                k = singleton_side.get(ci, 0)
                singleton_side[ci] = k + 1
                rng = periphery(ci) if k % 2 == 0 else central(ci)
                diagnostics.append(
                    f"lone {comp[0]} {'peripheral' if k % 2 == 0 else 'central'}"
                    f" to column {ci}"
                )
        else:
            xs = [init_pos[m][0] for v in comp
                  for m in neighbours[v] if m in init_pos]
            mx = statistics.median(xs) if xs else 0.0
            if nc > 1:
                i = min(range(nc), key=lambda k: abs(col_x[k] - mx))
                rng = between(max(0, i - 1), min(nc - 1, i + 1))
            else:
                rng = (mx - 90, mx + 90)
        for v in comp:
            lanes[v] = rng
    return lanes, diagnostics


def derive_positions(figure, init_pos, sizes) -> Layout:
    """Swim-lane spring-electrical placement.

    init_pos maps every node to an initial [x, y] (from a dot pass);
    sizes maps every node to (width, height) in points. Returns a
    Layout with final positions. Pure and deterministic: no randomness,
    fixed iteration count and cooling schedule."""
    edges = figure.get("edges", [])
    node_ids = [n["id"] for n in figure.get("nodes", [])]
    edge_pairs = [(e["from"], e["to"]) for e in edges]

    components, col_x, col_of = _columns(figure, init_pos)
    flow_nodes = set(col_of)

    # User overrides (the priority model, honoured in principled mode as
    # well as manual). A node with an explicit pos is PINNED: excluded
    # from displacement, an immovable anchor the rest of the layout
    # arranges around. Nodes sharing a user `ranks` group are RANK-LOCKED:
    # frozen to a common y, free to move only laterally within their lane.
    pinned: dict[str, tuple[float, float]] = {}
    for node in figure.get("nodes", []):
        if node.get("pos"):
            xy = _parse_pos(node["pos"])
            if xy is not None:
                pinned[node["id"]] = xy
    immovable = flow_nodes | set(pinned)
    variables = [n for n in node_ids if n not in immovable]
    lanes, diagnostics = assign_lanes(
        figure, components, col_x, col_of, init_pos
    )

    pos = {n: list(init_pos[n]) for n in node_ids}
    # Hold each flow column on a single x: the spine is straight by
    # construction (not merely as straight as the initial frame happened
    # to be). Flow nodes never move in x thereafter.
    for ci, comp in enumerate(components):
        for n in comp:
            pos[n][0] = col_x[ci]
    for n, (x, y) in pinned.items():
        pos[n] = [x, y]
    for v in variables:
        lo, hi = lanes[v]
        ys = [init_pos[m][1] for m in _neighbours(v, edges)
              if m in init_pos]
        my = statistics.median(ys) if ys else init_pos[v][1]
        pos[v] = [(lo + hi) / 2, my]

    # Rank-lock: variables in a user `ranks` group share a frozen y.
    var_set = set(variables)
    y_locked: dict[str, float] = {}
    for group in figure.get("ranks", []):
        members = [m for m in group if m in var_set and m in init_pos]
        if members:
            y = statistics.mean(init_pos[m][1] for m in members)
            for m in members:
                y_locked[m] = y
                pos[m][1] = y

    if pinned:
        diagnostics.append("pinned (user pos): " + ", ".join(sorted(pinned)))
    if y_locked:
        diagnostics.append(
            "rank-locked (user ranks): " + ", ".join(sorted(y_locked))
        )

    def clamp_x(v):
        lo, hi = lanes[v]
        pos[v][0] = min(max(pos[v][0], lo), hi)

    # --- spring-electrical iteration -------------------------------
    temperature = INIT_TEMPERATURE
    for _ in range(ITERATIONS):
        disp = {v: [0.0, 0.0] for v in variables}
        # soft repulsion: each variable pushed from every other node
        for v in variables:
            vx, vy = pos[v]
            for u in node_ids:
                if u == v:
                    continue
                dx = vx - pos[u][0]
                dy = vy - pos[u][1]
                d2 = dx * dx + dy * dy or 1.0
                d = math.sqrt(d2)
                f = REPULSION / d2
                disp[v][0] += dx / d * f
                disp[v][1] += dy / d * f
        # attraction along edges (Fruchterman-Reingold: d^2 / K)
        for a, b in edge_pairs:
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            d = math.hypot(dx, dy) or 1.0
            f = d * d / IDEAL_EDGE_LEN
            fx, fy = dx / d * f, dy / d * f
            if a in disp:
                disp[a][0] -= fx
                disp[a][1] -= fy
            if b in disp:
                disp[b][0] += fx
                disp[b][1] += fy
        for v in variables:
            dx, dy = disp[v]
            length = math.hypot(dx, dy) or 1.0
            step = min(length, temperature)
            pos[v][0] += dx / length * step
            if v not in y_locked:
                pos[v][1] += dy / length * step
            clamp_x(v)
        # columns translate vertically as rigid units
        col_force = [0.0] * len(components)
        for a, b in edge_pairs:
            if a in col_of and b not in flow_nodes:
                col_force[col_of[a]] += COLUMN_PULL * (pos[b][1] - pos[a][1])
            if b in col_of and a not in flow_nodes:
                col_force[col_of[b]] += COLUMN_PULL * (pos[a][1] - pos[b][1])
        for ci, comp in enumerate(components):
            shift = max(-temperature, min(temperature, col_force[ci]))
            for n in comp:
                pos[n][1] += shift
        temperature = max(MIN_TEMPERATURE, temperature * COOLING)

    _resolve_overlaps(pos, sizes, immovable, lanes, y_locked)

    return Layout(
        positions={n: (pos[n][0], pos[n][1]) for n in node_ids},
        lanes=lanes,
        columns=components,
        diagnostics=diagnostics,
    )


def _parse_pos(value):
    """Parse a 'x,y' position string into (x, y), or None if malformed."""
    try:
        x, y = str(value).split(",")
        return float(x), float(y)
    except (ValueError, AttributeError):
        return None


def _neighbours(node: str, edges: list[dict]) -> set[str]:
    out: set[str] = set()
    for e in edges:
        if e["from"] == node:
            out.add(e["to"])
        elif e["to"] == node:
            out.add(e["from"])
    return out


def _resolve_overlaps(pos, sizes, immovable, lanes, y_locked=frozenset()) \
        -> bool:
    """Hard minimum-gap floor: push overlapping boxes apart. Immovable
    nodes (flow spine and user-pinned) never move; rank-locked nodes move
    only laterally; movable variables stay in their lane. Returns True if
    anything moved."""
    names = list(pos)
    any_moved = False
    for _ in range(80):
        moved = False
        for a, b in itertools.combinations(names, 2):
            wa, ha = sizes.get(a, (0, 0))
            wb, hb = sizes.get(b, (0, 0))
            gx = (wa + wb) / 2 + NODE_GAP - abs(pos[a][0] - pos[b][0])
            gy = (ha + hb) / 2 + NODE_GAP - abs(pos[a][1] - pos[b][1])
            if gx <= 0 or gy <= 0:
                continue
            a_free = a not in immovable
            b_free = b not in immovable
            if not a_free and not b_free:
                continue
            dx = pos[a][0] - pos[b][0] or 0.1
            dy = pos[a][1] - pos[b][1] or 0.1
            d = math.hypot(dx, dy)
            ux, uy = dx / d, dy / d
            shove = min(gx, gy) + 1
            share = 0.5 if (a_free and b_free) else 1.0

            def push(n, sign):
                pos[n][0] += sign * ux * shove * share
                if n not in y_locked:
                    pos[n][1] += sign * uy * shove * share
                if n in lanes:
                    lo, hi = lanes[n]
                    pos[n][0] = min(max(pos[n][0], lo), hi)

            if a_free:
                push(a, +1)
            if b_free:
                push(b, -1)
            moved = any_moved = True
        if not moved:
            break
    return any_moved
