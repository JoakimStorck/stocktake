"""Crossing counter: a structural-quality metric for emitted figures.

Counts edge crossings from the geometry graphviz actually produced, by
parsing `dot -Tjson` (the drawn spline, arrowheads excluded). This makes
principle VI decidable and serves the success-measure "few crossing
information lines": it turns an ocular impression into a number to
improve against.

Crossing minimization stays delegated to dot (principle XII); this
module only measures the outcome. It needs the `dot` binary, like
rendering, and adds no Python dependencies.

The count is a proxy: graphviz reports b-spline control points, not the
sampled curve, so absolute counts can differ by a couple from the pixels.
It is consistent across layouts, which is what a comparison metric needs.

Classification is by line style: our information channel is the only
dashed one, so a dashed edge is information and anything else is flow.
The breakdown info x info / info x flow / flow x flow follows without
mapping drawn edges back to figure edges (ambiguous when two nodes carry
both a flow and an information edge).
"""

from __future__ import annotations

import itertools
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

Point = tuple[float, float]


@dataclass(frozen=True)
class DrawnEdge:
    points: tuple[Point, ...]
    is_information: bool


@dataclass(frozen=True)
class CrossingReport:
    total: int
    info_info: int
    info_flow: int
    flow_flow: int

    def __str__(self) -> str:
        return (
            f"crossings: {self.total} total "
            f"(info\u00d7info {self.info_info}, "
            f"info\u00d7flow {self.info_flow}, "
            f"flow\u00d7flow {self.flow_flow})"
        )


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _proper_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True only for a proper crossing: the four orientations strictly
    alternate. Touching at a shared endpoint (an incidence between edges
    at a common node) yields a zero orientation and is excluded."""
    d1 = _orient(p3, p4, p1)
    d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3)
    d4 = _orient(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _polyline_crossings(a: DrawnEdge, b: DrawnEdge) -> int:
    count = 0
    for s1a, s1b in zip(a.points, a.points[1:]):
        for s2a, s2b in zip(b.points, b.points[1:]):
            if _proper_intersect(s1a, s1b, s2a, s2b):
                count += 1
    return count


def _drawn_edges(dot_json: str) -> list[DrawnEdge]:
    data = json.loads(dot_json)
    edges: list[DrawnEdge] = []
    for edge in data.get("edges", []):
        points: list[Point] = []
        for op in edge.get("_draw_", []):
            if op.get("op") in ("b", "B", "c", "C") and "points" in op:
                points = [(p[0], p[1]) for p in op["points"]]
        style = str(edge.get("style", ""))
        if len(points) >= 2:
            edges.append(
                DrawnEdge(points=tuple(points), is_information="dashed" in style)
            )
    return edges


def count_crossings_from_json(dot_json: str) -> CrossingReport:
    edges = _drawn_edges(dot_json)
    total = info_info = info_flow = flow_flow = 0
    for a, b in itertools.combinations(edges, 2):
        c = _polyline_crossings(a, b)
        if not c:
            continue
        total += c
        if a.is_information and b.is_information:
            info_info += c
        elif a.is_information or b.is_information:
            info_flow += c
        else:
            flow_flow += c
    return CrossingReport(total, info_info, info_flow, flow_flow)


def count_crossings(dot_source: str | Path) -> CrossingReport:
    """Count crossings in a dot graph. Accepts dot source or a path to a
    .dot file; shells out to `dot -Tjson`."""
    if isinstance(dot_source, Path):
        text = dot_source.read_text(encoding="utf-8")
    elif "\n" not in dot_source and Path(dot_source).exists():
        text = Path(dot_source).read_text(encoding="utf-8")
    else:
        text = dot_source
    result = subprocess.run(
        ["dot", "-Tjson"], input=text, capture_output=True, text=True,
        check=True,
    )
    return count_crossings_from_json(result.stdout)


def _main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m stocktake.crossings",
        description="Count edge crossings in an emitted figure.",
    )
    parser.add_argument("dot", help="path to a .dot file")
    args = parser.parse_args(argv)
    print(count_crossings(Path(args.dot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
