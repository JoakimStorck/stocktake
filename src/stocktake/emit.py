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
import re
import subprocess
from pathlib import Path

FORRESTER = {
    "level": "shape=box",
    "aux": "shape=circle, fixedsize=false, margin=0.02",
    "param": "shape=none",
    "source": "shape=ellipse, style=dashed, margin=0.06",
}

CHANNEL = {
    "material": "",
    "personnel": 'color="black:invis:black"',
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


def emit_figure_dot(figure: dict) -> str:
    """Render a validated, audited figure declaration to dot source."""
    kinds = {n["id"]: n.get("kind", "aux") for n in figure.get("nodes", [])}

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
        group = f', group="{node["group"]}"' if node.get("group") else ""
        if kind == "rate":
            lines.append(
                f"  {nid} [shape=none, margin=0{group}, label=<"
                f'<table border="0" cellborder="0" cellspacing="0">'
                f'<tr><td><font face="DejaVu Sans" point-size="24">'
                f"&#8904;</font></td></tr>"
                f'<tr><td>{mathlabel(node["label"], 10)}'
                f"</td></tr></table>>];"
            )
        elif kind == "param":
            lines.append(
                f"  {nid} [shape=none, margin=0{group}, label=<"
                f'<table border="0" cellborder="0" cellspacing="0">'
                f'<tr><td>{mathlabel(node["label"])}</td></tr>'
                f'<tr><td port="c"><font face="DejaVu Sans">'
                f"&#9472;&#8854;&#9472;</font></td></tr></table>>];"
            )
        else:
            lines.append(
                f'  {nid} [label=<{mathlabel(node["label"])}>, '
                f"{FORRESTER[kind]}{group}];"
            )

    lines.append("")
    for edge in figure.get("edges", []):
        channel = edge.get("channel", "information")
        base = CHANNEL[channel]
        tail = _quote(edge["from"])
        if channel == "information" and kinds.get(edge["from"]) == "param":
            # Forrester fig 8-7: the constant IS the bar-through-circle
            # symbol; the information line departs from it undecorated.
            base = "style=dashed, arrowhead=vee"
            tail = f"{tail}:c"
        attrs = [base] if base else []
        if channel in ("material", "personnel") \
                and kinds.get(edge["to"]) == "rate":
            attrs.append("arrowhead=none")
        if edge.get("hints"):
            attrs.append(edge["hints"])
        attr_text = f' [{", ".join(a for a in attrs if a)}]' if attrs else ""
        lines.append(f"  {tail} -> {_quote(edge['to'])}{attr_text};")

    lines.append("")
    for group in figure.get("ranks", []):
        members = "; ".join(_quote(n) for n in group)
        lines.append(f"  {{ rank=same; {members}; }}")
    lines.append("}")
    return "\n".join(lines)


def try_render_dot(dot_path: Path) -> None:
    """Render .dot to PDF and PNG for human review; the rendered images
    are for inspection, the dot source is what tests verify."""
    try:
        for fmt in ("pdf", "png"):
            subprocess.run(
                ["dot", f"-T{fmt}", str(dot_path),
                 "-o", str(dot_path.with_suffix(f".{fmt}"))],
                check=True,
            )
    except FileNotFoundError:
        print("Graphviz 'dot' was not found. Wrote .dot file only.")
    except subprocess.CalledProcessError as exc:
        print(f"Graphviz rendering failed: {exc}")
