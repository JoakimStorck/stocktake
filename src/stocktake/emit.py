"""Emitter: graphviz dot in the notation of Forrester, Industrial
Dynamics (1961), ch. 8.

The notational conventions are settled (six render iterations in the
origin repo) and are not to be relitigated without cause:

- levels: rectangles; rates: valve glyph U+22C8 in the flow channel,
  flow lines enter with arrowhead=none and leave with an arrowhead
- channels: material solid; personnel double line; information dashed
  with a take-off circle at the source
- auxiliaries: circles; sources/sinks: dashed ellipses
- parameters: name above the Forrester constant symbol ---(-)--- in a
  ported table cell; the information line departs from the port
  undecorated (Forrester fig 8-7: the constant IS the bar-through-circle)
- no +/- signs on edges; mechanism lives in the audit CSV
- labels: _token / ^token become sub/sup, newlines become <br/>;
  all fonts DejaVu Sans with explicit face attributes inside HTML
  labels (node-level fontname does not reach into them)
- layout tuning is data, not code: per-edge `hints` (raw dot attribute
  text, trusted input) and top-level `ranks` in the TOML
- deliberately no equation numbers inside symbols (silent-drift bait);
  equation linkage belongs in the caption
"""

from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path

from .layout import (
    CONSERVED_CHANNELS,
    DerivedLayout,
    Layout,
    derive_layout,
    derive_positions,
)

FORRESTER = {
    "level": "shape=box",
    "aux": "shape=circle, fixedsize=false, margin=0.02",
    "param": "shape=none",
    "source": "shape=ellipse, style=dashed, margin=0.06",
    "sink": "shape=ellipse, style=dashed, margin=0.06",
}

# Conserved-flow channels are solid spines distinguished by decoration.
# material/personnel are settled (six render iterations in the origin);
# orders/money/capital line styles are PROVISIONAL until a real figure
# uses them and the rendered proof is inspected. money must not read as
# information's dashed line.
CHANNEL = {
    "material": "",
    "personnel": 'color="black:invis:black"',
    "orders": "style=bold",
    "money": 'color="black:invis:black:invis:black"',
    "capital": "penwidth=2.0",
    "information": "style=dashed, dir=both, arrowtail=odot, arrowhead=vee",
}

_TOKEN = re.compile(r"[_^]([A-Za-z0-9]+)")


def mathlabel(text: str, size: int | None = None) -> str:
    """Convert a plain math-ish label to a graphviz HTML-like label body:
    _token becomes subscript, ^token superscript, newlines become <br/>.
    Tokens are alphanumeric runs, so theta_abs and M_o(0) both work."""
    out = []
    for i, line in enumerate(text.split("\n")):
        if i:
            out.append("<br/>")
        pos = 0
        for m in _TOKEN.finditer(line):
            out.append(html.escape(line[pos:m.start()]))
            tag = "sub" if line[m.start()] == "_" else "sup"
            out.append(f"<{tag}>{html.escape(m.group(1))}</{tag}>")
            pos = m.end()
        out.append(html.escape(line[pos:]))
    body = "".join(out)
    if size is not None:
        return f'<font face="DejaVu Sans" point-size="{size}">{body}</font>'
    return f'<font face="DejaVu Sans">{body}</font>'


def _quote(node_id: str) -> str:
    return '"' + node_id.replace('"', '\\"') + '"'


def emit_figure_dot(figure: dict, positions=None) -> str:
    """Render a validated, audited figure declaration to dot source.

    Without positions this is the STRUCTURAL emission: derived groups
    (spine straight) and constraint=false on draped information edges,
    to be laid out by dot. With positions (the swim-lane force result)
    every node is pinned via pos and the graph is rendered with
    neato -n2, which draws at the given coordinates and routes splines.

    In manual mode nothing is derived and only the user's explicit
    layout is used. User group/hints/ranks always win over derived.
    """
    kinds = {n["id"]: n.get("kind", "aux") for n in figure.get("nodes", [])}

    if figure.get("layout", "principled") == "principled":
        derived = derive_layout(figure)
    else:
        derived = DerivedLayout()

    lines = [
        f"digraph {figure['name']} {{",
        "  graph [rankdir=TB, splines=true, overlap=false,"
        ' nodesep=0.5, ranksep=0.55, fontname="DejaVu Sans"];',
        '  node [fontsize=11, fontname="DejaVu Sans"];',
        '  edge [fontsize=10, fontname="DejaVu Sans", arrowsize=0.7];',
        "",
    ]

    for node in figure.get("nodes", []):
        kind = node.get("kind", "aux")
        nid = _quote(node["id"])
        # User group wins; derived group fills in where the user is silent.
        group_name = node.get("group") or derived.node_groups.get(node["id"])
        group = f', group="{group_name}"' if group_name else ""
        pos_attr = ""
        if positions and node["id"] in positions:
            x, y = positions[node["id"]]
            pos_attr = f', pos="{x:.1f},{y:.1f}"'
        if kind == "rate":
            lines.append(
                f"  {nid} [shape=none, margin=0{group}{pos_attr}, label=<"
                f'<table border="0" cellborder="0" cellspacing="0">'
                f'<tr><td><font face="DejaVu Sans" point-size="24">'
                f"&#8904;</font></td></tr>"
                f'<tr><td>{mathlabel(node["label"], 10)}'
                f"</td></tr></table>>];"
            )
        elif kind == "param":
            lines.append(
                f"  {nid} [shape=none, margin=0{group}{pos_attr}, label=<"
                f'<table border="0" cellborder="0" cellspacing="0">'
                f'<tr><td>{mathlabel(node["label"])}</td></tr>'
                f'<tr><td port="c"><font face="DejaVu Sans">'
                f"&#9472;&#8854;&#9472;</font></td></tr></table>>];"
            )
        else:
            lines.append(
                f'  {nid} [label=<{mathlabel(node["label"])}>, '
                f"{FORRESTER[kind]}{group}{pos_attr}];"
            )

    lines.append("")
    for i, edge in enumerate(figure.get("edges", [])):
        channel = edge.get("channel", "information")
        base = CHANNEL[channel]
        tail = _quote(edge["from"])
        if channel == "information" and kinds.get(edge["from"]) == "param":
            # Forrester fig 8-7: the constant IS the bar-through-circle
            # symbol; the information line departs from it undecorated.
            base = "style=dashed, arrowhead=vee"
            tail = f"{tail}:c"
        attrs = [base] if base else []
        if channel in CONSERVED_CHANNELS and kinds.get(edge["to"]) == "rate":
            attrs.append("arrowhead=none")
        # Derived edge attribute (e.g. constraint=false) applies only
        # where the user gave no explicit hints for this edge.
        if edge.get("hints"):
            attrs.append(edge["hints"])
        elif i in derived.edge_attrs:
            attrs.append(derived.edge_attrs[i])
        attr_text = f' [{", ".join(a for a in attrs if a)}]' if attrs else ""
        lines.append(f"  {tail} -> {_quote(edge['to'])}{attr_text};")

    lines.append("")
    for group in figure.get("ranks", []):
        members = "; ".join(_quote(n) for n in group)
        lines.append(f"  {{ rank=same; {members}; }}")
    lines.append("}")
    return "\n".join(lines)


def _frame_from_dot(dot_source: str):
    """Run dot -Tjson on the structural emission to read the initial
    frame: node positions and sizes (points). Returns (positions,
    sizes) or None if graphviz is unavailable."""
    try:
        result = subprocess.run(
            ["dot", "-Tjson"], input=dot_source,
            capture_output=True, text=True, check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    data = json.loads(result.stdout)
    positions: dict[str, list[float]] = {}
    sizes: dict[str, tuple[float, float]] = {}
    for obj in data.get("objects", []):
        if "pos" not in obj:
            continue
        x, y = obj["pos"].split(",")
        positions[obj["name"]] = [float(x), float(y)]
        sizes[obj["name"]] = (
            float(obj.get("width", 0)) * 72,
            float(obj.get("height", 0)) * 72,
        )
    return positions, sizes


def compute_layout(figure: dict) -> Layout | None:
    """Compute swim-lane force positions for a figure.

    Runs the structural emission through dot to get the initial frame,
    then the pure force balance. Returns None in manual mode or when
    graphviz is not available (the caller falls back to structural
    emission)."""
    if figure.get("layout", "principled") != "principled":
        return None
    frame = _frame_from_dot(emit_figure_dot(figure))
    if frame is None:
        return None
    init_pos, sizes = frame
    if any(n["id"] not in init_pos for n in figure.get("nodes", [])):
        return None
    return derive_positions(figure, init_pos, sizes)


def figure_layout_diagnostics(figure: dict) -> list[str]:
    """The layout diagnostics for a figure (empty in manual mode)."""
    layout = compute_layout(figure)
    if layout is None:
        return []
    return layout.diagnostics


def try_render_dot(dot_path: Path, positioned: bool = False) -> None:
    """Render .dot to PDF and PNG for human review. A positioned dot
    (pinned pos from the force balance) is drawn with neato -n2; a
    structural dot is laid out by dot. Rendered images are for
    inspection; the dot source is what tests verify."""
    engine = ["neato", "-n2"] if positioned else ["dot"]
    try:
        for fmt in ("pdf", "png"):
            subprocess.run(
                [*engine, f"-T{fmt}", str(dot_path),
                 "-o", str(dot_path.with_suffix(f".{fmt}"))],
                check=True,
            )
    except FileNotFoundError:
        print("Graphviz was not found. Wrote .dot file only.")
    except subprocess.CalledProcessError as exc:
        print(f"Graphviz rendering failed: {exc}")
