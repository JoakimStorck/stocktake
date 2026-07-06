"""Structural-quality metrics for an emitted figure.

Four measures, established while building the swim-lane layout because
each caught a defect the eye would catch but the others missed:

- crossings          information lines that cross (delegated placement
                     problem; the headline readability number)
- information_length total drawn length of information lines (long
                     swooping lines read badly even without crossings)
- node_overlaps      pairs of node boxes that overlap (a collapse that
                     length and crossings both *reward*, so it must be
                     measured separately)
- edge_node_clips    information lines passing through a node body (a
                     routing defect overlap count misses)

All are computed from the geometry graphviz actually produced, parsed
from `-Tjson`. They need the `dot`/`neato` binary, like rendering, and
add no Python dependencies. Absolute values are proxies (b-spline
control points, not the sampled curve) but consistent across layouts,
which is what a regression guardrail needs.
"""

from __future__ import annotations

import itertools
import json
import math
import subprocess
from dataclasses import dataclass

from .crossings import (
    Point,
    _drawn_edges,
    _proper_intersect,
    count_crossings_from_json,
)


@dataclass(frozen=True)
class DiagramMetrics:
    crossings: int
    information_length: float
    node_overlaps: int
    edge_node_clips: int
    spine_lateral_drift: float | None = None

    def __str__(self) -> str:
        drift = "" if self.spine_lateral_drift is None \
            else f", spine-drift {self.spine_lateral_drift:.0f}"
        return (
            f"crossings {self.crossings}, "
            f"info-length {self.information_length:.0f}, "
            f"overlaps {self.node_overlaps}, "
            f"line-through-node {self.edge_node_clips}"
            f"{drift}"
        )

    def is_clean(self) -> bool:
        """No overlaps and no lines through node bodies: the hard
        legibility floor. Crossings, length and spine drift are
        minimised, not required to be zero."""
        return self.node_overlaps == 0 and self.edge_node_clips == 0


def _render_json(dot_source: str, positioned: bool) -> str:
    engine = ["neato", "-n2"] if positioned else ["dot"]
    return subprocess.run(
        [*engine, "-Tjson"], input=dot_source,
        capture_output=True, text=True, check=True,
    ).stdout


def _nodes(data: dict):
    for obj in data.get("objects", []):
        if "pos" not in obj:
            continue
        x, y = map(float, obj["pos"].split(","))
        w = float(obj.get("width", 0)) * 72
        h = float(obj.get("height", 0)) * 72
        yield obj.get("_gvid"), obj.get("name"), x, y, w, h


def information_length_from_json(dot_json: str) -> float:
    total = 0.0
    for edge in _drawn_edges(dot_json):
        if not edge.is_information:
            continue
        for (x1, y1), (x2, y2) in zip(edge.points, edge.points[1:]):
            total += math.hypot(x2 - x1, y2 - y1)
    return total


def node_overlaps_from_json(dot_json: str) -> int:
    boxes = list(_nodes(json.loads(dot_json)))
    count = 0
    for (_, _, x1, y1, w1, h1), (_, _, x2, y2, w2, h2) in \
            itertools.combinations(boxes, 2):
        ox = min(x1 + w1 / 2, x2 + w2 / 2) - max(x1 - w1 / 2, x2 - w2 / 2)
        oy = min(y1 + h1 / 2, y2 + h2 / 2) - max(y1 - h1 / 2, y2 - h2 / 2)
        if ox > 2 and oy > 2:
            count += 1
    return count


def edge_node_clips_from_json(dot_json: str) -> int:
    data = json.loads(dot_json)
    boxes = {gid: (x - w / 2, x + w / 2, y - h / 2, y + h / 2)
             for gid, _, x, y, w, h in _nodes(data)}

    def edges_of(box) -> list[tuple[Point, Point]]:
        x1, x2, y1, y2 = box
        return [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]

    clips = 0
    for edge in data.get("edges", []):
        points: list[Point] = []
        for op in edge.get("_draw_", []):
            if op.get("op") in ("b", "B", "c", "C") and "points" in op:
                points = [(p[0], p[1]) for p in op["points"]]
        endpoints = {edge.get("tail"), edge.get("head")}
        for gid, box in boxes.items():
            if gid in endpoints:
                continue
            hit = False
            for p1, p2 in zip(points, points[1:]):
                mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
                inside = box[0] < mx < box[1] and box[2] < my < box[3]
                crosses = any(_proper_intersect(p1, p2, q1, q2)
                              for q1, q2 in edges_of(box))
                if inside or crosses:
                    hit = True
                    break
            if hit:
                clips += 1
                break
    return clips


def spine_lateral_drift_from_json(figure: dict, dot_json: str) -> float:
    """Maximum lateral (x) spread within any conserved-flow column. A
    straight Forrester spine drifts 0; this guards the skeleton
    specifically, not just general readability (the material spine
    wandering sideways was one of the original defects)."""
    from .layout import CONSERVED_CHANNELS, _flow_components

    data = json.loads(dot_json)
    xs = {name: x for _, name, x, _, _, _ in _nodes(data)}
    edges = figure.get("edges", [])
    node_ids = [n["id"] for n in figure.get("nodes", [])]
    flow_pairs = [
        (e["from"], e["to"]) for e in edges
        if e.get("channel", "information") in CONSERVED_CHANNELS
    ]
    drift = 0.0
    for comp in _flow_components(node_ids, flow_pairs):
        column_xs = [xs[n] for n in comp if n in xs]
        if len(column_xs) >= 2:
            drift = max(drift, max(column_xs) - min(column_xs))
    return drift


def measure(dot_source: str, positioned: bool = False,
            figure: dict | None = None) -> DiagramMetrics:
    """Measure the structural metrics for a dot graph. Set positioned=True
    for a force-layout dot (pinned pos, rendered with neato -n2). Pass the
    figure declaration to also measure spine lateral drift."""
    dot_json = _render_json(dot_source, positioned)
    return DiagramMetrics(
        crossings=count_crossings_from_json(dot_json).total,
        information_length=information_length_from_json(dot_json),
        node_overlaps=node_overlaps_from_json(dot_json),
        edge_node_clips=edge_node_clips_from_json(dot_json),
        spine_lateral_drift=(
            None if figure is None
            else spine_lateral_drift_from_json(figure, dot_json)
        ),
    )
